import asyncio
import json
import logging
import re
from typing import Dict, List, Optional, Any

from app.models.schemas import (
    GitHubUserData,
    PortfolioScoreResult,
    RecruiterCritique,
    PriorityAction,
    RoadmapStep
)

logger = logging.getLogger(__name__)

# System instructions enforcing recruiter persona, strictly factual interpretation, and prohibition of unsupported numerical claims
RECRUITER_SYSTEM_PROMPT = """You are an experienced Senior Engineering Hiring Manager and Technical Recruiter conducting a rapid portfolio review.

Your task is to interpret the provided deterministic portfolio scores and factual GitHub evidence.

STRICT RULES:
1. DO NOT recalculate, modify, or question the numerical scores. The provided scores are already mathematically verified.
2. ONLY interpret the provided facts. Every single observation, strength, and weakness MUST directly align with the factual evidence provided.
3. NEVER make unsupported numerical or outcome claims.
   - FORBIDDEN: Do not claim 'increases recruiter click-through by 3x', 'guarantees an interview', 'recruiters spend X seconds', or any other fabricated statistics.
   - PERMITTED: Explain qualitative benefits (e.g., 'A live demo enables recruiters to test the application immediately without cloning the code').
4. If the profile has 0 repositories or is inactive, honestly assess it as incomplete or dormant without inventing projects.
5. Provide actionable, high-leverage feedback formatted exactly to the requested JSON schema.
"""


class RecruiterCriticService:
    """Service that synthesizes deterministic portfolio scores and factual evidence into recruiter critiques."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.model_name = model_name

    async def generate_critique(
        self,
        user_data: GitHubUserData,
        score_result: PortfolioScoreResult
    ) -> RecruiterCritique:
        """
        Generate structured recruiter critique.
        Uses Gemini if an API key is available; falls back to deterministic synthesis otherwise.
        """
        if self.api_key:
            try:
                critique = await self._call_gemini_api(user_data, score_result)
                if critique:
                    return self._sanitize_critique(critique)
            except Exception as exc:
                logger.warning(f"Gemini API generation failed ({exc}). Falling back to algorithmic synthesis.")

        return self._generate_deterministic_fallback(user_data, score_result)

    async def _call_gemini_api(
        self,
        user_data: GitHubUserData,
        score_result: PortfolioScoreResult
    ) -> Optional[RecruiterCritique]:
        """Calls Google Gemini API using structured response schema."""
        from google import genai
        from google.genai import types

        prompt = self._build_evaluation_prompt(user_data, score_result)

        def _sync_generate():
            client = genai.Client(api_key=self.api_key)
            config = types.GenerateContentConfig(
                system_instruction=RECRUITER_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=RecruiterCritique,
                temperature=0.2,  # Low temperature for factual consistency
            )
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text

        # Execute in worker thread to prevent blocking async event loop
        response_text = await asyncio.to_thread(_sync_generate)
        if not response_text:
            return None

        data = json.loads(response_text)
        critique = RecruiterCritique(**data)
        critique.is_ai_generated = True
        critique.ai_model = self.model_name
        return critique

    def _build_evaluation_prompt(
        self,
        user_data: GitHubUserData,
        score_result: PortfolioScoreResult
    ) -> str:
        """Constructs concise, evidence-dense prompt for Gemini."""
        profile = user_data.profile
        metrics = score_result.metric_values

        evidence_bullets = "\n".join(f"- {item.evidence}" for item in score_result.all_evidence)

        # Summarize featured repos
        featured_repos_summary = []
        for r in user_data.repositories[:5]:
            featured_repos_summary.append(
                f"- Repository: {r.name} (Language: {r.language or 'None'}, Stars: {r.stargazers_count}, Fork: {r.is_fork})\n"
                f"  Description: {r.description or 'None'}\n"
                f"  Homepage/Demo: {r.homepage or 'None'}\n"
                f"  README: {'Present (' + str(r.readme_char_count) + ' chars)' if r.has_readme else 'Missing'}\n"
                f"  Snippet Excerpt: {r.readme_snippet[:300] if r.readme_snippet else 'None'}"
            )
        repos_text = "\n".join(featured_repos_summary) if featured_repos_summary else "No repositories."

        return f"""Candidate GitHub Portfolio Assessment Data:

Candidate: {profile.login} ({profile.name or 'Name not specified'})
Bio: {profile.bio or 'No bio provided'}
Personal Website / Blog: {profile.blog or 'None'}
Public Repositories Count: {profile.public_repos}

Deterministic Scores (Fixed 0-100 scale):
- Overall Portfolio Score: {score_result.overall_score}/100
- Technical Depth (25% weight): {score_result.category_scores['technical_depth'].score}/100
- Project Quality (25% weight): {score_result.category_scores['project_quality'].score}/100
- Documentation & Presentation (20% weight): {score_result.category_scores['documentation_and_presentation'].score}/100
- Activity & Consistency (15% weight): {score_result.category_scores['activity_and_consistency'].score}/100
- Recruiter Readiness (15% weight): {score_result.category_scores['recruiter_readiness'].score}/100

Factual Evidence Items:
{evidence_bullets}

Featured Repositories Analyzed:
{repos_text}

Generate a concise, honest, and strictly evidence-backed recruiter review conforming to the requested schema.
"""

    def _sanitize_critique(self, critique: RecruiterCritique) -> RecruiterCritique:
        """Sanitizes generated critique to enforce prohibition of unsupported numerical claims."""
        forbidden_regex = re.compile(
            r'(\b\d+x\b|\b\d+%\s*increase|\bguarantees?\s*(an?\s*)?(interview|job|offer)|\brecruiters?\s*spend\s*\d+\s*seconds)',
            re.IGNORECASE
        )

        def clean_str(text: str) -> str:
            return forbidden_regex.sub("significantly improves recruiter review efficiency", text)

        critique.recruiter_in_30_seconds = clean_str(critique.recruiter_in_30_seconds)
        critique.strengths = [clean_str(s) for s in critique.strengths]
        critique.weaknesses = [clean_str(w) for w in critique.weaknesses]
        for fix in critique.top_3_fixes:
            fix.qualitative_impact = clean_str(fix.qualitative_impact)
            fix.action = clean_str(fix.action)

        return critique

    def _generate_deterministic_fallback(
        self,
        user_data: GitHubUserData,
        score_result: PortfolioScoreResult
    ) -> RecruiterCritique:
        """
        Deterministic, offline synthesis engine that formats factual evidence into
        a structured recruiter review without requiring external LLM API availability.
        """
        profile = user_data.profile
        overall = score_result.overall_score
        cats = score_result.category_scores
        metrics = score_result.metric_values
        total_repos = len(user_data.repositories)

        # 1. Level assessment
        if total_repos == 0:
            level = "Early Stage / Empty Profile"
        elif overall >= 85:
            level = "Senior-Caliber Independent Builder"
        elif overall >= 70:
            level = "Well-Structured Mid-Level Developer"
        elif overall >= 50:
            level = "Promising Junior Builder"
        else:
            level = "Foundational / Incomplete Portfolio"

        # 2. Recruiter in 30 Seconds
        if total_repos == 0:
            r30 = "No public repositories are currently visible on this GitHub profile. Recruiters cannot evaluate coding abilities until original projects are published."
        elif overall >= 75:
            r30 = (
                f"Candidate demonstrates strong portfolio maturity with an overall score of {overall}/100. "
                "Repositories showcase clear project substance, solid documentation, and steady engineering activity that allows recruiters to quickly assess capabilities."
            )
        elif overall >= 50:
            strongest_cat = max(cats.values(), key=lambda c: c.score)
            weakest_cat = min(cats.values(), key=lambda c: c.score)
            r30 = (
                f"Candidate presents solid technical foundations ({strongest_cat.name}: {strongest_cat.score}/100), "
                f"but portfolio presentation is constrained by {weakest_cat.name.lower()} ({weakest_cat.score}/100). "
                "Targeted documentation and curation fixes would significantly streamline recruiter evaluations."
            )
        else:
            r30 = (
                f"Portfolio currently scores {overall}/100. Key hiring signals such as project descriptions, "
                "licenses, or active repositories are missing, making it difficult for technical recruiters to evaluate code quality during quick screenings."
            )

        # 3. Strengths (strictly factual evidence items)
        strengths: List[str] = []
        if metrics.get("original_repositories", 0) > 0:
            orig = metrics["original_repositories"]
            strengths.append(f"Demonstrates genuine builder intent with {orig} original (non-fork) repositories.")
        if metrics.get("distinct_languages", 0) >= 2:
            num_l = metrics["distinct_languages"]
            strengths.append(f"Technical stack includes {num_l} distinct programming languages detected across projects.")
        if metrics.get("repositories_pushed_last_90_days", 0) >= 2:
            p90 = metrics["repositories_pushed_last_90_days"]
            strengths.append(f"Sustained engineering activity with {p90} repositories updated within the last 90 days.")
        if metrics.get("profile_bio_present"):
            strengths.append("Clear profile bio establishes professional context for visitors.")
        if metrics.get("profile_readme_present"):
            strengths.append("Dedicated profile README provides an introduction to the developer's work.")
        if not strengths:
            strengths.append("GitHub profile is publicly initialized and available for review.")

        # 4. Weaknesses / Red Flags (strictly factual missing signals)
        weaknesses: List[str] = []
        if metrics.get("repositories_with_descriptions", 0) < total_repos and total_repos > 0:
            missing_desc = total_repos - metrics.get("repositories_with_descriptions", 0)
            weaknesses.append(f"{missing_desc} of {total_repos} analyzed repositories lack concise descriptions explaining what the project does.")
        if metrics.get("repositories_with_licenses", 0) == 0 and total_repos > 0:
            weaknesses.append("No open-source licenses detected across analyzed repositories, leaving intellectual property status ambiguous.")
        if metrics.get("repositories_with_demo_links", 0) == 0 and total_repos > 0:
            weaknesses.append("No live demo or project homepage links attached to repository headers.")
        if metrics.get("repositories_pushed_last_90_days", 0) == 0 and total_repos > 0:
            weaknesses.append("No repository push activity recorded within the past 90 days.")
        if not metrics.get("profile_bio_present"):
            weaknesses.append("Missing profile bio, requiring recruiters to guess developer focus and background.")
        if not weaknesses:
            weaknesses.append("Portfolio is well-organized with few structural red flags detected.")

        # 5. Top 3 Fixes (prioritized practical qualitative improvements)
        fixes: List[PriorityAction] = []
        if total_repos == 0:
            fixes = [
                PriorityAction(
                    title="Publish Your First Original Project",
                    priority="High",
                    issue="No public repositories exist on this GitHub profile.",
                    action="Push a clean, functional project repository with well-organized code and a descriptive commit history.",
                    qualitative_impact="Provides technical recruiters with tangible evidence of your coding ability and engineering standards."
                ),
                PriorityAction(
                    title="Write a Professional Profile Bio",
                    priority="Medium",
                    issue="Profile bio is currently empty.",
                    action="Add a 1-2 sentence bio highlighting your technical stack, key interests, and current focus.",
                    qualitative_impact="Instantly introduces your background to recruiters visiting your profile page."
                ),
                PriorityAction(
                    title="Create a Dedicated Profile README",
                    priority="Low",
                    issue="No profile overview repository (username/username) detected.",
                    action="Create a repository with your username to display an introductory overview of your projects and skills.",
                    qualitative_impact="Creates an engaging landing page that highlights your best work before recruiters dig into individual repositories."
                )
            ]
        else:
            if metrics.get("repositories_with_demo_links", 0) == 0:
                fixes.append(PriorityAction(
                    title="Add Live Demo & Deployment Links",
                    priority="High",
                    issue="Projects lack visible deployment or interactive demo links in repository settings.",
                    action="Deploy top projects (via Vercel, Netlify, or Render) and paste the live URL into the repository About section.",
                    qualitative_impact="Allows recruiters and interviewers to interact with the finished product immediately without cloning and configuring the code locally."
                ))
            if metrics.get("repositories_with_descriptions", 0) < total_repos:
                fixes.append(PriorityAction(
                    title="Write 1-Sentence Repository Descriptions",
                    priority="High",
                    issue="Multiple repositories display empty descriptions on the GitHub profile page.",
                    action="Add a clear one-sentence summary for each project explaining the problem it solves and key tech stack used.",
                    qualitative_impact="Enables recruiters scanning project lists to immediately understand technical domain and relevance to open roles."
                ))
            if metrics.get("repositories_with_licenses", 0) == 0:
                fixes.append(PriorityAction(
                    title="Add Open-Source Licenses",
                    priority="Medium",
                    issue="Key original repositories do not include a LICENSE file.",
                    action="Add standard MIT or Apache 2.0 license files to top repositories.",
                    qualitative_impact="Demonstrates open-source hygiene and professional software development practices."
                ))
            if not metrics.get("profile_bio_present"):
                fixes.append(PriorityAction(
                    title="Complete GitHub Profile Bio",
                    priority="Medium",
                    issue="Profile bio is currently empty.",
                    action="Write a crisp 1-2 sentence bio outlining primary languages, frameworks, and engineering interests.",
                    qualitative_impact="Establishes immediate professional identity during quick recruiter scans."
                ))

            # Supplemental improvements to ensure exactly 3 high-impact fixes
            supplemental_fixes = [
                PriorityAction(
                    title="Add Architecture Visuals to Featured READMEs",
                    priority="Low",
                    issue="Primary project documentation is text-heavy without diagrams or UI screenshots.",
                    action="Add at least one architecture flowchart or UI screenshot into the README of your primary project.",
                    qualitative_impact="Gives visual context and allows hiring teams to quickly grasp system structure."
                ),
                PriorityAction(
                    title="Add Automated GitHub Actions / CI Workflows",
                    priority="Medium",
                    issue="No automated continuous integration testing workflows detected in primary repositories.",
                    action="Add a simple GitHub Actions workflow (.github/workflows/ci.yml) to run automated unit tests on every pull request.",
                    qualitative_impact="Demonstrates to engineering hiring managers that you build production-ready code with automated verification."
                ),
                PriorityAction(
                    title="Curate Pinned Repositories on Profile",
                    priority="Low",
                    issue="Default profile layout shows recently updated repos rather than your highest-impact projects.",
                    action="Pin your 3 strongest, most complete repositories to the top of your GitHub profile page.",
                    qualitative_impact="Ensures that visiting recruiters immediately see your best work without having to sift through smaller experimental repositories."
                )
            ]

            for supp in supplemental_fixes:
                if len(fixes) < 3 and all(f.title != supp.title for f in fixes):
                    fixes.append(supp)

        fixes = fixes[:3]

        # 6. Roadmap
        roadmap = [
            RoadmapStep(
                timeframe="Immediate (Day 1)",
                actions=[
                    "Add 1-sentence descriptions and live demo links to top 3 repositories.",
                    "Update profile bio with current technical specialization and links."
                ]
            ),
            RoadmapStep(
                timeframe="Short-Term (Weeks 1-2)",
                actions=[
                    "Add MIT licenses and clean install/usage commands to featured READMEs.",
                    "Curate portfolio by pinning your strongest 3 original projects."
                ]
            ),
            RoadmapStep(
                timeframe="Medium-Term (Month 1+)",
                actions=[
                    "Maintain steady commit cadence on primary repositories.",
                    "Add automated CI test workflows or visual architecture diagrams."
                ]
            )
        ]

        return RecruiterCritique(
            recruiter_in_30_seconds=r30,
            candidate_level_assessment=level,
            strengths=strengths[:4],
            weaknesses=weaknesses[:4],
            top_3_fixes=fixes,
            roadmap=roadmap,
            is_ai_generated=False,
            ai_model="algorithmic-fallback"
        )
