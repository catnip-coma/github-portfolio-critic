# GitGauge 🎯

> **Recruiter-grade GitHub Portfolio Critic & Auditor**  
> An 6-hour hackathon project providing deterministic scoring and AI-powered portfolio insights for developers.

---

## ⚡ What is GitGauge?
GitGauge analyzes any public GitHub profile and its repositories, runs deterministic heuristics across 5 core hiring dimensions, and synthesizes the findings into actionable, recruiter-focused critiques powered by Google Gemini.

### 5 Scoring Dimensions (Weighted 0–100)
1. **Technical Depth (25%)**: Complexity, codebase size, language diversity, non-fork core work.
2. **Project Quality (25%)**: Stars, repository completeness, open-source licenses, test/CI signals.
3. **Documentation & Presentation (20%)**: Profile README, bio, repo descriptions, clear documentation.
4. **Activity & Consistency (15%)**: Pushes in the last 30d, 90d, 180d, and active repository distribution.
5. **Recruiter Readiness (15%)**: Measurable hiring signals (live demos, homepage links, clean repo curation).

---

## 🛠️ Tech Stack
* **Language & Runtime**: Python 3.12
* **Backend**: FastAPI, Uvicorn, Pydantic v2
* **HTTP Client**: `httpx` (async) with in-memory TTL caching
* **AI Engine**: Google Gemini 2.5 Flash
* **Frontend**: Jinja2 + Tailwind CSS (CDN) + Lucide Icons (Zero npm/build overhead)

---

## 🚀 Quickstart

### 1. Clone & Set Up Environment
```bash
# Clone the repository
git clone https://github.com/catnip-coma/github-portfolio-critic.git
cd github-portfolio-critic

# Create and activate virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\activate  # On Windows
# source .venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Add your optional `GITHUB_TOKEN` (for higher rate limits) and `GEMINI_API_KEY` (for AI critiques).

### 3. Run Application
```bash
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --port 8000
```
Open your browser at `http://127.0.0.1:8000`.

---

## 🧪 Testing
```bash
pytest -v
```
