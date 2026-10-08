import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

from app.models.schemas import (
    GitHubUserData,
    GitHubRepo,
    GitHubUserProfile,
    CategoryScore,
    EvidenceItem,
    PortfolioScoreResult
)

# Dimension Weights (Total = 1.00 / 100%)
WEIGHT_TECHNICAL_DEPTH = 0.25
WEIGHT_PROJECT_QUALITY = 0.25
WEIGHT_DOCUMENTATION = 0.20
WEIGHT_ACTIVITY = 0.15
WEIGHT_RECRUITER_READINESS = 0.15


class PortfolioScorer:
    """
    Deterministic heuristics engine for scoring GitHub portfolios across five dimensions.
    Produces repeatable, strictly factual scores and verifiable evidence items.
    """

    def __init__(self, user_data: GitHubUserData, as_of_date: Optional[datetime] = None):
        self.user_data = user_data
        self.profile = user_data.profile
        self.repos = user_data.repositories
        self.total_repos = len(self.repos)
        # Use user_data.fetched_at or custom as_of_date for deterministic date math
        self.now = as_of_date or user_data.fetched_at
        if self.now.tzinfo is None:
            self.now = self.now.replace(tzinfo=timezone.utc)

        # Precompute common slices
        self.original_repos = [r for r in self.repos if not r.is_fork]
        self.fork_repos = [r for r in self.repos if r.is_fork]
        self.total_original = len(self.original_repos)

    def calculate_score(self) -> PortfolioScoreResult:
        """Run all dimension evaluations and return the consolidated portfolio score."""
        if self.total_repos == 0:
            return self._calculate_empty_profile_result()

        tech_score = self._evaluate_technical_depth()
        qual_score = self._evaluate_project_quality()
        doc_score = self._evaluate_documentation()
        act_score = self._evaluate_activity()
        rec_score = self._evaluate_recruiter_readiness()

        category_scores: Dict[str, CategoryScore] = {
            "technical_depth": tech_score,
            "project_quality": qual_score,
            "documentation_and_presentation": doc_score,
            "activity_and_consistency": act_score,
            "recruiter_readiness": rec_score,
        }

        weighted_total = sum(cat.weighted_score for cat in category_scores.values())
        overall_score = round(max(0.0, min(100.0, weighted_total)), 1)

        # Aggregate all evidence and metric values
        all_evidence: List[EvidenceItem] = []
        metric_values: Dict[str, Any] = {}
        for cat in category_scores.values():
            for item in cat.evidence:
                all_evidence.append(item)
                metric_values[item.metric] = item.value

        return PortfolioScoreResult(
            overall_score=overall_score,
            category_scores=category_scores,
            metric_values=metric_values,
            all_evidence=all_evidence
        )

    def _calculate_empty_profile_result(self) -> PortfolioScoreResult:
        """Handles user with 0 public repositories gracefully without division errors."""
        empty_evidence = [
            EvidenceItem(
                metric="total_repositories",
                value=0,
                total=0,
                evidence="0 public repositories found on this GitHub profile."
            ),
            EvidenceItem(
                metric="profile_bio_present",
                value=bool(self.profile.bio and self.profile.bio.strip()),
                total=None,
                evidence="Profile bio is present." if (self.profile.bio and self.profile.bio.strip()) else "No profile bio found."
            )
        ]

        categories = {
            "technical_depth": CategoryScore(name="Technical Depth", weight=WEIGHT_TECHNICAL_DEPTH, score=0.0, weighted_score=0.0, evidence=empty_evidence),
            "project_quality": CategoryScore(name="Project Quality", weight=WEIGHT_PROJECT_QUALITY, score=0.0, weighted_score=0.0, evidence=empty_evidence),
            "documentation_and_presentation": CategoryScore(name="Documentation & Presentation", weight=WEIGHT_DOCUMENTATION, score=0.0, weighted_score=0.0, evidence=empty_evidence),
            "activity_and_consistency": CategoryScore(name="Activity & Consistency", weight=WEIGHT_ACTIVITY, score=0.0, weighted_score=0.0, evidence=empty_evidence),
            "recruiter_readiness": CategoryScore(name="Recruiter Readiness", weight=WEIGHT_RECRUITER_READINESS, score=0.0, weighted_score=0.0, evidence=empty_evidence),
        }

        return PortfolioScoreResult(
            overall_score=0.0,
            category_scores=categories,
            metric_values={"total_repositories": 0},
            all_evidence=empty_evidence
        )

    # -------------------------------------------------------------------------
    # 1. Technical Depth (25%)
    # -------------------------------------------------------------------------
    def _evaluate_technical_depth(self) -> CategoryScore:
        score = 0.0
        evidence: List[EvidenceItem] = []

        # (a) Meaningful original repository count (Core substance, max 45 pts)
        if self.total_original >= 5:
            score += 45.0
        elif self.total_original >= 3:
            score += 35.0
        elif self.total_original >= 1:
            score += 20.0

        evidence.append(EvidenceItem(
            metric="original_repositories",
            value=self.total_original,
            total=self.total_repos,
            evidence=f"{self.total_original} of {self.total_repos} analyzed repositories are original (not forks)."
        ))

        # (b) Codebase size presence as supporting signal (size_kb >= 50) (max 20 pts)
        substantial_repos = [r for r in self.original_repos if r.size_kb >= 50]
        substantial_count = len(substantial_repos)
        if self.total_original > 0:
            size_ratio = substantial_count / self.total_original
            score += round(size_ratio * 20.0, 1)

        evidence.append(EvidenceItem(
            metric="substantial_repositories_size",
            value=substantial_count,
            total=self.total_original,
            evidence=f"{substantial_count} of {self.total_original} original repositories have a recorded codebase size >= 50 KB (excluding empty repositories)."
        ))

        # (c) Programming language focus & presence (Supporting signal, max 20 pts)
        # Avoids over-rewarding language hopping; recognizes depth in 1-2 core languages
        languages = [r.language for r in self.repos if r.language and r.language.strip()]
        lang_counts = Counter(languages)
        distinct_langs = list(lang_counts.keys())
        num_langs = len(distinct_langs)

        if num_langs >= 2:
            score += 20.0
        elif num_langs == 1:
            score += 15.0

        top_langs_str = ", ".join(f"{lang} ({cnt})" for lang, cnt in lang_counts.most_common(3))
        evidence.append(EvidenceItem(
            metric="distinct_languages",
            value=num_langs,
            total=None,
            evidence=f"{num_langs} distinct programming languages detected across repositories: {top_langs_str or 'None'}."
        ))

        # (d) Repository topic tags (Discoverability metadata, max 15 pts)
        repos_with_topics = [r for r in self.repos if len(r.topics) > 0]
        topics_count = len(repos_with_topics)
        if self.total_repos > 0:
            topics_ratio = topics_count / self.total_repos
            score += round(topics_ratio * 15.0, 1)

        evidence.append(EvidenceItem(
            metric="repositories_with_topics",
            value=topics_count,
            total=self.total_repos,
            evidence=f"{topics_count} of {self.total_repos} analyzed repositories have topic tags for discoverability."
        ))

        final_score = round(max(0.0, min(100.0, score)), 1)
        return CategoryScore(
            name="Technical Depth",
            weight=WEIGHT_TECHNICAL_DEPTH,
            score=final_score,
            weighted_score=round(final_score * WEIGHT_TECHNICAL_DEPTH, 2),
            evidence=evidence
        )

    # -------------------------------------------------------------------------
    # 2. Project Quality (25%)
    # -------------------------------------------------------------------------
    def _evaluate_project_quality(self) -> CategoryScore:
        score = 0.0
        evidence: List[EvidenceItem] = []

        # (a) Original vs Fork ratio (max 25 pts)
        orig_ratio = self.total_original / max(self.total_repos, 1)
        score += round(orig_ratio * 25.0, 1)
        evidence.append(EvidenceItem(
            metric="original_ratio_percent",
            value=round(orig_ratio * 100, 1),
            total=100,
            evidence=f"{round(orig_ratio * 100)}% of analyzed repositories are original projects."
        ))

        # (b) Repository descriptions presence (max 25 pts)
        repos_with_desc = [r for r in self.repos if r.description and r.description.strip()]
        desc_count = len(repos_with_desc)
        desc_ratio = desc_count / max(self.total_repos, 1)
        score += round(desc_ratio * 25.0, 1)
        evidence.append(EvidenceItem(
            metric="repositories_with_descriptions",
            value=desc_count,
            total=self.total_repos,
            evidence=f"{desc_count} of {self.total_repos} analyzed repositories have descriptions."
        ))

        # (c) README presence (max 25 pts)
        # Evaluated across top analyzed repositories where readme was checked
        repos_with_readme = [r for r in self.repos if r.has_readme]
        readme_count = len(repos_with_readme)
        checked_repos_count = sum(1 for r in self.repos if r.has_readme or r.readme_char_count > 0 or r == self.repos[0])
        # Use analyzed repos baseline
        readme_ratio = readme_count / max(min(self.total_repos, 5), 1)
        score += round(min(readme_ratio, 1.0) * 25.0, 1)
        evidence.append(EvidenceItem(
            metric="featured_repositories_with_readmes",
            value=readme_count,
            total=min(self.total_repos, 5),
            evidence=f"{readme_count} of {min(self.total_repos, 5)} top featured repositories contain a README."
        ))

        # (d) Open source license presence (max 15 pts)
        repos_with_license = [r for r in self.repos if r.license_name and r.license_name.strip()]
        license_count = len(repos_with_license)
        license_ratio = license_count / max(self.total_repos, 1)
        score += round(license_ratio * 15.0, 1)
        evidence.append(EvidenceItem(
            metric="repositories_with_licenses",
            value=license_count,
            total=self.total_repos,
            evidence=f"{license_count} of {self.total_repos} analyzed repositories include an open-source license."
        ))

        # (e) Weak supporting signal: demo/homepage links & stars (max 10 pts)
        repos_with_homepage = [r for r in self.repos if r.homepage and r.homepage.strip()]
        homepage_count = len(repos_with_homepage)
        if homepage_count > 0:
            score += 5.0

        total_stars = sum(r.stargazers_count for r in self.repos)
        if total_stars >= 10:
            score += 5.0
        elif total_stars >= 1:
            score += 2.0

        evidence.append(EvidenceItem(
            metric="repositories_with_demo_links",
            value=homepage_count,
            total=self.total_repos,
            evidence=f"{homepage_count} of {self.total_repos} analyzed repositories have a live demo or homepage link."
        ))
        evidence.append(EvidenceItem(
            metric="total_stargazers",
            value=total_stars,
            total=None,
            evidence=f"{total_stars} total stars accumulated across analyzed repositories."
        ))

        final_score = round(max(0.0, min(100.0, score)), 1)
        return CategoryScore(
            name="Project Quality",
            weight=WEIGHT_PROJECT_QUALITY,
            score=final_score,
            weighted_score=round(final_score * WEIGHT_PROJECT_QUALITY, 2),
            evidence=evidence
        )

    # -------------------------------------------------------------------------
    # 3. Documentation & Presentation (20%)
    # -------------------------------------------------------------------------
    def _evaluate_documentation(self) -> CategoryScore:
        score = 0.0
        evidence: List[EvidenceItem] = []

        # (a) Profile Bio & Profile README (max 25 pts)
        has_bio = bool(self.profile.bio and self.profile.bio.strip())
        if has_bio:
            score += 10.0
        evidence.append(EvidenceItem(
            metric="profile_bio_present",
            value=has_bio,
            total=None,
            evidence="Profile bio is present." if has_bio else "No profile bio found."
        ))

        has_profile_readme = bool(self.profile.has_profile_readme)
        if has_profile_readme:
            score += 15.0
        evidence.append(EvidenceItem(
            metric="profile_readme_present",
            value=has_profile_readme,
            total=None,
            evidence="Special profile README detected." if has_profile_readme else "No profile README detected."
        ))

        # (b) Repository descriptions presence (max 20 pts)
        desc_count = sum(1 for r in self.repos if r.description and r.description.strip())
        desc_ratio = desc_count / max(self.total_repos, 1)
        score += round(desc_ratio * 20.0, 1)

        # (c) README presence and length on featured repos (max 25 pts)
        readmes_with_content = [r for r in self.repos if r.has_readme and r.readme_char_count > 0]
        if readmes_with_content:
            avg_chars = sum(r.readme_char_count for r in readmes_with_content) / len(readmes_with_content)
            if avg_chars >= 1200:
                score += 25.0
            elif avg_chars >= 500:
                score += 18.0
            elif avg_chars >= 200:
                score += 10.0
            else:
                score += 5.0
            evidence.append(EvidenceItem(
                metric="average_readme_char_length",
                value=round(avg_chars),
                total=None,
                evidence=f"Average README length across inspected repositories is {round(avg_chars)} characters."
            ))
        else:
            evidence.append(EvidenceItem(
                metric="average_readme_char_length",
                value=0,
                total=None,
                evidence="0 inspected repositories had non-empty README content."
            ))

        # (d) Structural signals in READMEs: setup/install, usage, visual elements (max 30 pts)
        all_snippets = " ".join([r.readme_snippet.lower() for r in self.repos if r.readme_snippet])

        setup_keywords = ["install", "setup", "getting started", "build", "prerequisite", "npm install", "pip install"]
        has_setup = any(k in all_snippets for k in setup_keywords)
        if has_setup:
            score += 12.0
        evidence.append(EvidenceItem(
            metric="readme_setup_instructions_detected",
            value=has_setup,
            total=None,
            evidence="Setup/installation instructions detected in repository READMEs." if has_setup else "No setup/installation instructions detected in repository READMEs."
        ))

        usage_keywords = ["usage", "example", "how to use", "quickstart", "run", "python main", "npm start"]
        has_usage = any(k in all_snippets for k in usage_keywords)
        if has_usage:
            score += 10.0
        evidence.append(EvidenceItem(
            metric="readme_usage_instructions_detected",
            value=has_usage,
            total=None,
            evidence="Usage or quickstart instructions detected in repository READMEs." if has_usage else "No usage or quickstart instructions detected in repository READMEs."
        ))

        # Images/Screenshots/GIFs pattern
        visual_pattern = re.compile(r"(!\[|<img|\.png|\.jpg|\.jpeg|\.gif|\.svg)", re.IGNORECASE)
        has_visuals = bool(visual_pattern.search(all_snippets))
        if has_visuals:
            score += 8.0
        evidence.append(EvidenceItem(
            metric="readme_visuals_detected",
            value=has_visuals,
            total=None,
            evidence="Visual elements (e.g., images, diagrams, or screenshots) detected in repository READMEs." if has_visuals else "No visual elements detected in repository READMEs."
        ))

        final_score = round(max(0.0, min(100.0, score)), 1)
        return CategoryScore(
            name="Documentation & Presentation",
            weight=WEIGHT_DOCUMENTATION,
            score=final_score,
            weighted_score=round(final_score * WEIGHT_DOCUMENTATION, 2),
            evidence=evidence
        )

    # -------------------------------------------------------------------------
    # 4. Activity & Consistency (15%)
    # -------------------------------------------------------------------------
    def _evaluate_activity(self) -> CategoryScore:
        score = 0.0
        evidence: List[EvidenceItem] = []

        # Find push dates
        push_dates = []
        for r in self.repos:
            if r.pushed_at:
                p_date = r.pushed_at
                if p_date.tzinfo is None:
                    p_date = p_date.replace(tzinfo=timezone.utc)
                push_dates.append(p_date)

        if not push_dates:
            evidence.append(EvidenceItem(
                metric="days_since_latest_push",
                value=None,
                total=None,
                evidence="No repository push activity recorded."
            ))
            return CategoryScore(
                name="Activity & Consistency",
                weight=WEIGHT_ACTIVITY,
                score=0.0,
                weighted_score=0.0,
                evidence=evidence
            )

        latest_push = max(push_dates)
        days_since_latest = max(0, (self.now - latest_push).days)

        # (a) Recency of most recent push (max 30 pts)
        if days_since_latest <= 14:
            score += 30.0
        elif days_since_latest <= 30:
            score += 25.0
        elif days_since_latest <= 90:
            score += 15.0
        elif days_since_latest <= 180:
            score += 10.0

        evidence.append(EvidenceItem(
            metric="days_since_latest_push",
            value=days_since_latest,
            total=None,
            evidence=f"Most recent repository activity was {days_since_latest} days ago."
        ))

        # (b) Repositories pushed in last 30, 90, 180 days (max 60 pts)
        p30_count = sum(1 for p in push_dates if (self.now - p).days <= 30)
        p90_count = sum(1 for p in push_dates if (self.now - p).days <= 90)
        p180_count = sum(1 for p in push_dates if (self.now - p).days <= 180)

        # 90-day activity (sustained momentum) (max 35 pts)
        if p90_count >= 3:
            score += 35.0
        elif p90_count == 2:
            score += 25.0
        elif p90_count == 1:
            score += 15.0

        # 180-day activity (medium-term continuity) (max 25 pts)
        if p180_count >= 3:
            score += 25.0
        elif p180_count >= 1:
            score += 15.0

        evidence.append(EvidenceItem(
            metric="repositories_pushed_last_30_days",
            value=p30_count,
            total=self.total_repos,
            evidence=f"{p30_count} of {self.total_repos} analyzed repositories were pushed within the last 30 days."
        ))
        evidence.append(EvidenceItem(
            metric="repositories_pushed_last_90_days",
            value=p90_count,
            total=self.total_repos,
            evidence=f"{p90_count} of {self.total_repos} analyzed repositories were pushed within the last 90 days."
        ))
        evidence.append(EvidenceItem(
            metric="repositories_pushed_last_180_days",
            value=p180_count,
            total=self.total_repos,
            evidence=f"{p180_count} of {self.total_repos} analyzed repositories were pushed within the last 180 days (6 months)."
        ))

        # (c) Distribution of activity across repositories (max 10 pts)
        # Avoids rewarding a single isolated push as sustained activity
        is_distributed = p90_count >= 2
        if is_distributed:
            score += 10.0

        evidence.append(EvidenceItem(
            metric="activity_distributed_across_repositories",
            value=is_distributed,
            total=None,
            evidence=f"Recent activity is distributed across {p90_count} separate repositories in the last 90 days."
        ))

        final_score = round(max(0.0, min(100.0, score)), 1)
        return CategoryScore(
            name="Activity & Consistency",
            weight=WEIGHT_ACTIVITY,
            score=final_score,
            weighted_score=round(final_score * WEIGHT_ACTIVITY, 2),
            evidence=evidence
        )

    # -------------------------------------------------------------------------
    # 5. Recruiter Readiness (15%)
    # -------------------------------------------------------------------------
    def _evaluate_recruiter_readiness(self) -> CategoryScore:
        score = 0.0
        evidence: List[EvidenceItem] = []

        # (a) Measurable Profile Presentation (max 25 pts)
        has_bio = bool(self.profile.bio and self.profile.bio.strip())
        has_profile_readme = bool(self.profile.has_profile_readme)
        has_link = bool(self.profile.blog and self.profile.blog.strip())

        if has_bio:
            score += 10.0
        if has_profile_readme or has_link:
            score += 15.0

        evidence.append(EvidenceItem(
            metric="profile_completeness_signals",
            value={"bio": has_bio, "profile_readme": has_profile_readme, "website": has_link},
            total=None,
            evidence=f"Profile presentation: Bio ({'Yes' if has_bio else 'No'}), Website/Blog ({'Yes' if has_link else 'No'}), Profile README ({'Yes' if has_profile_readme else 'No'})."
        ))

        # (b) Featured/Strongest project clarity (max 35 pts)
        # Evaluated on top 3 original repositories: do they have both description AND readme?
        top_3_original = self.original_repos[:3]
        ready_top_repos = [
            r for r in top_3_original
            if (r.description and r.description.strip()) and (r.has_readme or r.readme_char_count > 0)
        ]
        ready_count = len(ready_top_repos)
        top_count = max(len(top_3_original), 1)

        clarity_ratio = ready_count / top_count
        score += round(clarity_ratio * 35.0, 1)

        evidence.append(EvidenceItem(
            metric="featured_repositories_fully_presented",
            value=ready_count,
            total=len(top_3_original),
            evidence=f"{ready_count} of {len(top_3_original)} primary original repositories have both a description and a README."
        ))

        # (c) Live demo / homepage links in portfolio (max 20 pts)
        repos_with_demo = [r for r in self.repos if r.homepage and r.homepage.strip()]
        has_demo = len(repos_with_demo) > 0
        if has_demo:
            score += 20.0

        evidence.append(EvidenceItem(
            metric="portfolio_live_demos_available",
            value=len(repos_with_demo),
            total=self.total_repos,
            evidence=f"{len(repos_with_demo)} live demo or project homepage links detected in repository settings."
        ))

        # (d) Portfolio curation / low noise (max 20 pts)
        # High ratio of original projects signals focused builder rather than accidental tutorial fork accumulator
        orig_ratio = self.total_original / max(self.total_repos, 1)
        if orig_ratio >= 0.75:
            score += 20.0
        elif orig_ratio >= 0.50:
            score += 10.0

        evidence.append(EvidenceItem(
            metric="portfolio_curation_original_ratio",
            value=round(orig_ratio * 100, 1),
            total=100,
            evidence=f"{round(orig_ratio * 100)}% of repositories in portfolio are original (not forks)."
        ))

        final_score = round(max(0.0, min(100.0, score)), 1)
        return CategoryScore(
            name="Recruiter Readiness",
            weight=WEIGHT_RECRUITER_READINESS,
            score=final_score,
            weighted_score=round(final_score * WEIGHT_RECRUITER_READINESS, 2),
            evidence=evidence
        )


def calculate_portfolio_score(
    user_data: GitHubUserData,
    as_of_date: Optional[datetime] = None
) -> PortfolioScoreResult:
    """Helper entrypoint to calculate deterministic portfolio scores from GitHubUserData."""
    scorer = PortfolioScorer(user_data=user_data, as_of_date=as_of_date)
    return scorer.calculate_score()
