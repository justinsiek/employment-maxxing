# Resume Tailor — V1 Spec

## Overview

An AI-powered system that takes a job posting URL, extracts the job description, selects the most relevant projects/experiences from the user's project bank, and generates a tailored LaTeX resume compiled to PDF.

### V1 Scope (MVP)

User pastes a job link → system scrapes the posting → LLM picks the best projects and tailors bullet points → LaTeX resume is compiled → saved to `resumes/<job_name>/Justin_S_Resume.pdf`.

### Future Scope (out of scope for V1)

- Overleaf integration (push compiled resume to Overleaf)
- Auto-apply to the job posting
- Dashboard UI showing applied jobs, generated resumes, and responses
- Cover letter generation
- Tracking application status / responses

---

## Architecture

```
┌──────────────┐       POST /api/tailor        ┌──────────────────┐
│   Next.js    │  ──────────────────────────►   │   Flask Server   │
│   Client     │                                │   (server.py)    │
│              │  ◄──────────────────────────   │                  │
└──────────────┘       { pdf_path, ... }        └───────┬──────────┘
                                                        │
                                        ┌───────────────┼───────────────┐
                                        ▼               ▼               ▼
                                  ┌──────────┐   ┌──────────┐   ┌──────────┐
                                  │ Scraper  │   │ LLM      │   │ LaTeX    │
                                  │ Module   │   │ Module   │   │ Compiler │
                                  └──────────┘   └──────────┘   └──────────┘
```

### Components

| Component | Responsibility |
|---|---|
| **Next.js Client** | UI with a text input for the job URL, submit button, and status/result display |
| **Flask Server** | Orchestrates the pipeline: scrape → tailor → compile |
| **Scraper Module** | Fetches and extracts the job description text from a URL |
| **LLM Module** | Selects relevant projects and generates tailored resume content |
| **LaTeX Compiler** | Renders the final resume from a LaTeX template to PDF |

---

## Data: Project Bank

A JSON file at `server/data/projects.json` that contains all of the user's projects, experiences, skills, and education. This is the source of truth the LLM draws from when building a resume.

### Schema

```json
{
  "personal": {
    "name": "Justin Siek",
    "email": "...",
    "phone": "...",
    "linkedin": "...",
    "github": "...",
    "website": "..."
  },
  "education": [
    {
      "school": "...",
      "degree": "...",
      "graduation": "...",
      "gpa": "...",
      "coursework": ["..."]
    }
  ],
  "skills": {
    "languages": ["Python", "JavaScript", "..."],
    "frameworks": ["React", "Flask", "..."],
    "tools": ["Git", "Docker", "..."]
  },
  "experiences": [
    {
      "id": "exp_1",
      "title": "Software Engineer Intern",
      "company": "...",
      "dates": "Jun 2025 – Aug 2025",
      "bullets": [
        "Built X using Y, resulting in Z"
      ],
      "tags": ["backend", "python", "aws"]
    }
  ],
  "projects": [
    {
      "id": "proj_1",
      "name": "Project Name",
      "technologies": ["React", "Node.js"],
      "dates": "Jan 2025 – Mar 2025",
      "bullets": [
        "Designed and implemented X..."
      ],
      "tags": ["fullstack", "ai", "web"],
      "url": "https://github.com/..."
    }
  ]
}
```

> **Note:** The `tags` field on experiences and projects helps the LLM with initial filtering, but the LLM ultimately decides relevance based on the full job description.

---

## Pipeline Detail

### Step 1: Scrape Job Posting

**Module:** `server/scraper.py`

**Input:** Job posting URL (string)

**Output:** Structured job data:
```json
{
  "title": "Software Engineer",
  "company": "Acme Corp",
  "description": "Full job description text...",
  "url": "https://..."
}
```

**Approach:**
1. Make an HTTP request to the URL with a browser-like User-Agent header.
2. Parse HTML with BeautifulSoup.
3. For common job boards (LinkedIn, Greenhouse, Lever, Workday), use board-specific selectors to extract structured data.
4. **Fallback:** If no board-specific parser matches, extract all visible text from the page body and pass it to the LLM in Step 2 to parse out the relevant job info.
5. Return the structured job data.

**Edge cases:**
- LinkedIn and some boards require authentication or render client-side → for V1, if a simple GET fails, return an error and ask the user to paste the job description text directly into a fallback textarea on the frontend.
- Rate limiting → add a short delay + retry with exponential backoff (max 3 retries).

**Dependencies:** `requests`, `beautifulsoup4`

---

### Step 2: Tailor Resume via LLM

**Module:** `server/tailor.py`

**Input:** Job data (from Step 1) + full project bank (from `projects.json`)

**Output:** Structured resume content:
```json
{
  "selected_experiences": ["exp_1", "exp_2"],
  "selected_projects": ["proj_1", "proj_3", "proj_5"],
  "tailored_bullets": {
    "exp_1": ["Rewritten bullet 1...", "Rewritten bullet 2..."],
    "proj_1": ["Rewritten bullet 1...", "Rewritten bullet 2..."]
  },
  "skills": {
    "languages": ["Python", "JavaScript"],
    "frameworks": ["React", "Flask"],
    "tools": ["Docker", "AWS"]
  },
  "summary": "Optional 1-line professional summary if relevant"
}
```

**Approach:**
1. Load `projects.json`.
2. Construct a prompt that includes:
   - The full job description
   - All projects and experiences from the bank
   - Instructions to:
     - Select the **most relevant** experiences (all, if applicable) and **3–4 projects**
     - Rewrite bullet points to emphasize skills/keywords from the job description
     - **Bullet length constraint:** each bullet must be either **105–110 characters** (single line) or **210–220 characters** (exactly two lines). No partial third lines — bullets should fill their lines cleanly.
     - Select the most relevant subset of skills
     - Quantify impact where possible
     - Maintain truthfulness — no fabrication, only reframing
3. Call the OpenAI API (`gpt-4o` or similar) with structured output (JSON mode).
4. Parse and validate the response.

**LLM Provider:** OpenAI API via `openai` Python package. API key stored in `.env` as `OPENAI_API_KEY`.

**Prompt design principles:**
- System prompt establishes the role: "You are an expert resume writer..."
- User prompt provides the job description + project bank
- Request JSON output matching the schema above
- Temperature: `0.3` (low creativity, high precision)

---

### Step 3: Compile LaTeX Resume

**Module:** `server/compiler.py`

**Input:** Tailored resume content (from Step 2) + LaTeX template

**Output:** Compiled PDF at `resumes/<job_name>/Justin_S_Resume.pdf`

**Approach:**
1. Load a base LaTeX template from `server/templates/resume_template.tex`.
   - The template uses placeholder tokens (e.g., `%%EXPERIENCE_SECTION%%`, `%%PROJECTS_SECTION%%`, `%%SKILLS_SECTION%%`) that get replaced programmatically.
2. Populate the template with the tailored content:
   - Build LaTeX strings for each section from the structured JSON
   - Escape any special LaTeX characters in the content (`&`, `%`, `$`, `#`, `_`, `{`, `}`)
3. Write the populated `.tex` file to a temp directory.
4. Compile with `pdflatex` (must be installed on the system).
5. Copy the resulting PDF to `resumes/<sanitized_job_name>/Justin_S_Resume.pdf`.
6. Clean up temp files.

**LaTeX template style:**
- Clean, single-column, one-page resume
- Jake's Resume template style (widely used CS resume format)
- Sections: Education, Experience, Projects, Skills

**Dependencies:** `pdflatex` (system), `jinja2` (optional, for templating)

---

## API Endpoint

### `POST /api/tailor`

**Request body:**
```json
{
  "url": "https://boards.greenhouse.io/company/jobs/12345",
  "description": null
}
```

> If `url` is provided, the server scrapes it. If `description` is provided (fallback), scraping is skipped.

**Response (success):**
```json
{
  "success": true,
  "job": {
    "title": "Software Engineer",
    "company": "Acme Corp"
  },
  "pdf_path": "resumes/acme_corp_software_engineer/Justin_S_Resume.pdf",
  "resume_content": { ... }
}
```

**Response (error):**
```json
{
  "success": false,
  "error": "Could not scrape the job posting. Please paste the description manually.",
  "needs_manual_input": true
}
```

---

## Frontend (Next.js Client)

### Page: `/` (Home)

A single-page UI with:

1. **Text input** — paste job posting URL
2. **Submit button** — "Generate Resume"
3. **Loading state** — spinner + status messages ("Scraping job posting...", "Tailoring resume...", "Compiling PDF...")
4. **Result display:**
   - Job title & company
   - Download link for the generated PDF
   - Expandable view of the tailored resume content (which projects were selected, the rewritten bullets)
5. **Fallback textarea** — if scraping fails, a textarea appears for the user to paste the job description directly, with a "Retry" button

---

## File Structure

```
employment-maxxing/
├── client/                        # Next.js frontend
│   ├── app/
│   │   ├── page.tsx               # Main UI
│   │   ├── layout.tsx
│   │   └── globals.css
│   └── package.json
├── server/
│   ├── server.py                  # Flask app + /api/tailor endpoint
│   ├── scraper.py                 # Job posting scraper
│   ├── tailor.py                  # LLM resume tailoring logic
│   ├── compiler.py                # LaTeX compilation
│   ├── templates/
│   │   └── resume_template.tex    # Base LaTeX template
│   ├── data/
│   │   └── projects.json          # Project/experience bank
│   ├── requirements.txt
│   └── .env                       # OPENAI_API_KEY
├── resumes/                       # Generated resumes (git-ignored)
│   └── <job_name>/
│       └── Justin_S_Resume.pdf
└── specs/
    └── resume_tailor_v1.md        # This spec
```

---

## Dependencies

### Server (Python)
```
flask
flask-cors
requests
beautifulsoup4
openai
python-dotenv
```

### System
- `pdflatex` — install via `brew install --cask mactex-no-gui` or `brew install basictex`
  - After install, ensure `pdflatex` is on PATH
  - May need LaTeX packages: `latexmk`, `enumitem`, `titlesec`, `geometry`, etc.

### Client (Node.js)
- Already set up with Next.js 16 + React 19 + Tailwind

---

## Implementation Order

1. **Set up project bank** — create and populate `server/data/projects.json` with real data
2. **Build scraper** — `server/scraper.py` with board-specific parsers + fallback
3. **Build tailor** — `server/tailor.py` with LLM prompt + structured output
4. **Build compiler** — `server/compiler.py` + `server/templates/resume_template.tex`
5. **Wire up endpoint** — `POST /api/tailor` in `server/server.py`
6. **Build frontend** — input form, loading states, result display in `client/app/page.tsx`
7. **End-to-end test** — paste a real job URL and verify the full pipeline

---

## Environment Variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for OpenAI (used in `tailor.py`) |

Store in `server/.env`, loaded via `python-dotenv`.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Scraping fails (auth wall, JS-rendered page) | Return error with `needs_manual_input: true`, frontend shows fallback textarea |
| LLM API error (rate limit, timeout) | Retry up to 2 times with backoff, then return error |
| LaTeX compilation fails | Return error with the `pdflatex` log for debugging |
| Invalid URL format | Return 400 with validation error |
| Missing `projects.json` | Return 500 with descriptive error |
