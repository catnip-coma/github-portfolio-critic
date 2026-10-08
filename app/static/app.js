/**
 * GitGauge Client Application
 * Communicates with /api/analyze/{username} and renders recruiter dashboard.
 * STRICT DATA INTEGRITY: Does NOT calculate, alter, or synthesize any scores or text.
 */

document.addEventListener("DOMContentLoaded", () => {
    const searchForm = document.getElementById("search-form");
    const usernameInput = document.getElementById("username-input");
    const analyzeBtn = document.getElementById("analyze-btn");
    const loadingState = document.getElementById("loading-state");
    const loadingMessage = document.getElementById("loading-message");
    const errorBanner = document.getElementById("error-banner");
    const errorMessage = document.getElementById("error-message");
    const resultsContainer = document.getElementById("results-container");

    // Demo chips
    document.querySelectorAll(".demo-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const user = btn.getAttribute("data-username");
            if (user) {
                usernameInput.value = user;
                triggerAnalysis(user);
            }
        });
    });

    searchForm.addEventListener("submit", (e) => {
        e.preventDefault();
        const username = usernameInput.value.trim();
        if (username) {
            triggerAnalysis(username);
        }
    });

    let loadingInterval = null;

    function setLoading(isLoading) {
        if (isLoading) {
            analyzeBtn.disabled = true;
            usernameInput.disabled = true;
            analyzeBtn.classList.add("opacity-50", "cursor-not-allowed");
            loadingState.classList.remove("hidden");
            errorBanner.classList.add("hidden");
            resultsContainer.classList.add("hidden");

            // Phased loading indicator messages
            const messages = [
                "Fetching GitHub profile and public repositories...",
                "Inspecting repository READMEs and metadata...",
                "Calculating deterministic portfolio heuristics...",
                "Synthesizing recruiter review and actionable fixes..."
            ];
            let msgIndex = 0;
            loadingMessage.textContent = messages[0];
            loadingInterval = setInterval(() => {
                msgIndex = (msgIndex + 1) % messages.length;
                loadingMessage.textContent = messages[msgIndex];
            }, 1800);
        } else {
            analyzeBtn.disabled = false;
            usernameInput.disabled = false;
            analyzeBtn.classList.remove("opacity-50", "cursor-not-allowed");
            loadingState.classList.add("hidden");
            if (loadingInterval) {
                clearInterval(loadingInterval);
                loadingInterval = null;
            }
        }
    }

    function showError(msg) {
        setLoading(false);
        resultsContainer.classList.add("hidden");
        errorBanner.classList.remove("hidden");
        errorMessage.textContent = msg;
    }

    async function triggerAnalysis(username) {
        setLoading(true);

        try {
            const resp = await fetch(`/api/analyze/${encodeURIComponent(username)}`);
            const data = await resp.json();

            if (!resp.ok) {
                if (resp.status === 404) {
                    showError(`GitHub user "${username}" was not found. Please verify the username.`);
                } else if (resp.status === 429) {
                    showError(data.detail || "GitHub API rate limit exceeded. Please configure a GITHUB_TOKEN in your .env file.");
                } else {
                    showError(data.detail || `Server error (${resp.status}): Unable to analyze portfolio.`);
                }
                return;
            }

            // Render complete report exactly as returned by the backend
            renderReport(data);
            setLoading(false);
            resultsContainer.classList.remove("hidden");

            // Smooth scroll into results
            resultsContainer.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (err) {
            console.error("Fetch failure:", err);
            showError("Network connection failed. Please check your connection and try again.");
        }
    }

    function renderReport(data) {
        const { profile, scores, critique } = data;

        // 1. Profile Header
        renderProfileHeader(profile);

        // 2. Overall Portfolio Score
        renderOverallScore(scores.overall_score, critique.candidate_level_assessment);

        // 3. Recruiter in 30 Seconds
        renderRecruiter30s(critique);

        // 4. Five Category Scores
        renderCategoryScores(scores.category_scores);

        // 5. Strengths vs Weaknesses
        renderStrengthsAndWeaknesses(critique.strengths, critique.weaknesses);

        // 6. Evidence-backed Analysis
        renderEvidenceAnalysis(scores.all_evidence, scores.category_scores);

        // 7. Top 3 Things to Fix
        renderTopFixes(critique.top_3_fixes);

        // 8. Practical Improvement Roadmap
        renderRoadmap(critique.roadmap);

        // Re-initialize Lucide icons if loaded
        if (window.lucide) {
            window.lucide.createIcons();
        }
    }

    // -------------------------------------------------------------------------
    // 1. Profile Header
    // -------------------------------------------------------------------------
    function renderProfileHeader(profile) {
        const avatar = document.getElementById("profile-avatar");
        const login = document.getElementById("profile-login");
        const name = document.getElementById("profile-name");
        const bio = document.getElementById("profile-bio");
        const reposCount = document.getElementById("profile-repos-count");
        const followersCount = document.getElementById("profile-followers-count");
        const followingCount = document.getElementById("profile-following-count");
        const githubLink = document.getElementById("profile-github-link");
        const profileReadmeBadge = document.getElementById("profile-readme-badge");

        avatar.src = profile.avatar_url;
        avatar.alt = profile.login;
        login.textContent = `@${profile.login}`;
        name.textContent = profile.name || profile.login;
        bio.textContent = profile.bio ? profile.bio : "No bio provided on GitHub profile.";
        reposCount.textContent = profile.public_repos;
        followersCount.textContent = profile.followers;
        followingCount.textContent = profile.following;
        githubLink.href = profile.html_url;

        if (profile.has_profile_readme) {
            profileReadmeBadge.classList.remove("hidden");
        } else {
            profileReadmeBadge.classList.add("hidden");
        }
    }

    // -------------------------------------------------------------------------
    // 2. Overall Portfolio Score
    // -------------------------------------------------------------------------
    function renderOverallScore(score, levelAssessment) {
        const scoreVal = document.getElementById("overall-score-value");
        const scoreRing = document.getElementById("overall-score-ring");
        const levelBadge = document.getElementById("candidate-level-badge");

        scoreVal.textContent = Math.round(score);
        levelBadge.textContent = levelAssessment || "Evaluated Candidate";

        // SVG circle math: r=70 -> circumference = 2 * PI * 70 ≈ 439.82
        const radius = 70;
        const circumference = 2 * Math.PI * radius;
        const offset = circumference - (score / 100) * circumference;

        scoreRing.style.strokeDasharray = `${circumference} ${circumference}`;
        scoreRing.style.strokeDashoffset = `${offset}`;

        // Color coding
        scoreRing.classList.remove("text-emerald-500", "text-amber-500", "text-rose-500");
        scoreVal.classList.remove("text-emerald-400", "text-amber-400", "text-rose-400");
        levelBadge.classList.remove(
            "bg-emerald-500/10", "text-emerald-400", "border-emerald-500/20",
            "bg-amber-500/10", "text-amber-400", "border-amber-500/20",
            "bg-rose-500/10", "text-rose-400", "border-rose-500/20"
        );

        if (score >= 75) {
            scoreRing.classList.add("text-emerald-500");
            scoreVal.classList.add("text-emerald-400");
            levelBadge.classList.add("bg-emerald-500/10", "text-emerald-400", "border-emerald-500/20");
        } else if (score >= 50) {
            scoreRing.classList.add("text-amber-500");
            scoreVal.classList.add("text-amber-400");
            levelBadge.classList.add("bg-amber-500/10", "text-amber-400", "border-amber-500/20");
        } else {
            scoreRing.classList.add("text-rose-500");
            scoreVal.classList.add("text-rose-400");
            levelBadge.classList.add("bg-rose-500/10", "text-rose-400", "border-rose-500/20");
        }
    }

    // -------------------------------------------------------------------------
    // 3. Recruiter in 30 Seconds
    // -------------------------------------------------------------------------
    function renderRecruiter30s(critique) {
        const textElem = document.getElementById("recruiter-30s-text");
        const aiBadge = document.getElementById("ai-mode-badge");

        textElem.textContent = critique.recruiter_in_30_seconds;

        if (critique.is_ai_generated) {
            aiBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> AI Synthesized (${critique.ai_model || "Gemini"})`;
            aiBadge.className = "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950/60 text-emerald-300 border border-emerald-800/50";
        } else {
            aiBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-slate-400"></span> Heuristic Synthesis (Offline)`;
            aiBadge.className = "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700";
        }
    }

    // -------------------------------------------------------------------------
    // 4. Five Category Scores
    // -------------------------------------------------------------------------
    function renderCategoryScores(catScores) {
        const container = document.getElementById("category-scores-container");
        container.innerHTML = "";

        const orderedKeys = [
            "technical_depth",
            "project_quality",
            "documentation_and_presentation",
            "activity_and_consistency",
            "recruiter_readiness"
        ];

        orderedKeys.forEach(key => {
            const cat = catScores[key];
            if (!cat) return;

            const weightPercent = Math.round(cat.weight * 100);
            const scoreRound = Math.round(cat.score);

            let barColor = "bg-rose-500";
            let textColor = "text-rose-400";
            if (scoreRound >= 75) {
                barColor = "bg-emerald-500";
                textColor = "text-emerald-400";
            } else if (scoreRound >= 50) {
                barColor = "bg-amber-500";
                textColor = "text-amber-400";
            }

            const card = document.createElement("div");
            card.className = "p-4 rounded-xl bg-slate-900/60 border border-slate-800 card-hover";
            card.innerHTML = `
                <div class="flex items-center justify-between mb-2">
                    <div>
                        <span class="text-sm font-semibold text-slate-200">${cat.name}</span>
                        <span class="ml-2 text-xs text-slate-500 font-mono">${weightPercent}% weight</span>
                    </div>
                    <span class="text-base font-bold font-mono ${textColor}">${scoreRound}<span class="text-xs text-slate-500">/100</span></span>
                </div>
                <div class="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div class="${barColor} h-2 rounded-full transition-all duration-700 ease-out" style="width: ${scoreRound}%;"></div>
                </div>
            `;
            container.appendChild(card);
        });
    }

    // -------------------------------------------------------------------------
    // 5. Strengths vs Weaknesses
    // -------------------------------------------------------------------------
    function renderStrengthsAndWeaknesses(strengths, weaknesses) {
        const strengthsList = document.getElementById("strengths-list");
        const weaknessesList = document.getElementById("weaknesses-list");

        strengthsList.innerHTML = "";
        weaknessesList.innerHTML = "";

        strengths.forEach(s => {
            const li = document.createElement("li");
            li.className = "flex items-start gap-3 text-sm text-slate-300";
            li.innerHTML = `
                <span class="mt-0.5 p-1 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800/40 shrink-0">
                    <i data-lucide="check" class="w-3.5 h-3.5"></i>
                </span>
                <span>${s}</span>
            `;
            strengthsList.appendChild(li);
        });

        weaknesses.forEach(w => {
            const li = document.createElement("li");
            li.className = "flex items-start gap-3 text-sm text-slate-300";
            li.innerHTML = `
                <span class="mt-0.5 p-1 rounded bg-rose-950/60 text-rose-400 border border-rose-800/40 shrink-0">
                    <i data-lucide="alert-triangle" class="w-3.5 h-3.5"></i>
                </span>
                <span>${w}</span>
            `;
            weaknessesList.appendChild(li);
        });
    }

    // -------------------------------------------------------------------------
    // 6. Evidence-backed Analysis
    // -------------------------------------------------------------------------
    function renderEvidenceAnalysis(allEvidence, catScores) {
        const container = document.getElementById("evidence-accordion-container");
        container.innerHTML = "";

        // Display evidence categorized by category
        Object.entries(catScores).forEach(([key, cat]) => {
            const group = document.createElement("div");
            group.className = "p-4 rounded-xl bg-slate-900/50 border border-slate-800/80";

            let itemsHtml = "";
            cat.evidence.forEach(item => {
                itemsHtml += `
                    <div class="py-2.5 border-b border-slate-800/50 last:border-b-0 flex items-start justify-between gap-4">
                        <div class="flex items-start gap-2.5">
                            <span class="mt-1 w-1.5 h-1.5 rounded-full bg-indigo-400 shrink-0"></span>
                            <span class="text-sm text-slate-300">${item.evidence}</span>
                        </div>
                        <span class="px-2 py-0.5 rounded bg-slate-800 text-xs font-mono text-slate-400 shrink-0 border border-slate-700/60">
                            ${formatMetricValue(item.value, item.total)}
                        </span>
                    </div>
                `;
            });

            group.innerHTML = `
                <div class="flex items-center justify-between mb-3 pb-2 border-b border-slate-800">
                    <h4 class="text-sm font-semibold text-slate-200">${cat.name} Evidence</h4>
                    <span class="text-xs text-indigo-400 font-mono">${cat.evidence.length} verified facts</span>
                </div>
                <div class="space-y-1">
                    ${itemsHtml}
                </div>
            `;
            container.appendChild(group);
        });
    }

    function formatMetricValue(val, total) {
        if (typeof val === "boolean") {
            return val ? "Verified" : "Missing";
        }
        if (typeof val === "number") {
            return total !== null && total !== undefined ? `${val}/${total}` : `${val}`;
        }
        if (typeof val === "object" && val !== null) {
            return "Structured";
        }
        return val ? String(val) : "None";
    }

    // -------------------------------------------------------------------------
    // 7. Top 3 Things to Fix
    // -------------------------------------------------------------------------
    function renderTopFixes(fixes) {
        const container = document.getElementById("top-fixes-container");
        container.innerHTML = "";

        fixes.forEach((fix, idx) => {
            let badgeClass = "bg-rose-950/60 text-rose-300 border-rose-800/60";
            if (fix.priority === "Medium") {
                badgeClass = "bg-amber-950/60 text-amber-300 border-amber-800/60";
            } else if (fix.priority === "Low") {
                badgeClass = "bg-blue-950/60 text-blue-300 border-blue-800/60";
            }

            const card = document.createElement("div");
            card.className = "p-5 rounded-xl bg-slate-900/70 border border-slate-800 card-hover relative overflow-hidden";
            card.innerHTML = `
                <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-2">
                        <span class="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-300 border border-slate-700">
                            #${idx + 1}
                        </span>
                        <h4 class="text-base font-semibold text-slate-100">${fix.title}</h4>
                    </div>
                    <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold border ${badgeClass}">
                        ${fix.priority} Priority
                    </span>
                </div>
                
                <div class="space-y-2.5 text-sm">
                    <div class="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80">
                        <span class="block text-xs uppercase tracking-wider font-semibold text-slate-500 mb-1">Issue Identified:</span>
                        <p class="text-slate-300">${fix.issue}</p>
                    </div>

                    <div class="p-3 rounded-lg bg-indigo-950/20 border border-indigo-900/30">
                        <span class="block text-xs uppercase tracking-wider font-semibold text-indigo-400 mb-1">Recommended Action:</span>
                        <p class="text-slate-200">${fix.action}</p>
                    </div>

                    <div class="p-3 rounded-lg bg-emerald-950/20 border border-emerald-900/30">
                        <span class="block text-xs uppercase tracking-wider font-semibold text-emerald-400 mb-1">Recruiter Benefit:</span>
                        <p class="text-slate-300">${fix.qualitative_impact}</p>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    }

    // -------------------------------------------------------------------------
    // 8. Practical Improvement Roadmap
    // -------------------------------------------------------------------------
    function renderRoadmap(roadmap) {
        const container = document.getElementById("roadmap-container");
        container.innerHTML = "";

        roadmap.forEach((step, idx) => {
            const card = document.createElement("div");
            card.className = "p-5 rounded-xl bg-slate-900/60 border border-slate-800 card-hover";

            const actionsHtml = step.actions.map(act => `
                <li class="flex items-start gap-2.5 text-sm text-slate-300">
                    <span class="mt-1 w-2 h-2 rounded-full bg-indigo-500 shrink-0"></span>
                    <span>${act}</span>
                </li>
            `).join("");

            card.innerHTML = `
                <div class="flex items-center gap-2 mb-3 pb-2 border-b border-slate-800">
                    <span class="text-xs font-mono font-bold px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/50">
                        Phase ${idx + 1}
                    </span>
                    <h4 class="text-sm font-semibold text-slate-200">${step.timeframe}</h4>
                </div>
                <ul class="space-y-2">
                    ${actionsHtml}
                </ul>
            `;
            container.appendChild(card);
        });
    }
});
