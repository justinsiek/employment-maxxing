# Resume Tailor — V1 Spec

## Overview

A web-based resume management tool: paste a job description → AI generates a tailored LaTeX resume → edit the LaTeX in an Overleaf-style editor → recompile to PDF.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Next.js Client                 │
│                                             │
│  ┌─────────────┐   ┌─────────────────────┐  │
│  │ Dashboard    │   │ Editor              │  │
│  │ • Resume list│   │ ┌──────┬──────────┐ │  │
│  │ • New Resume │   │ │Monaco│ react-pdf│ │  │
│  │   form       │   │ │LaTeX │ preview  │ │  │
│  └─────────────┘   │ └──────┴──────────┘ │  │
│                     └─────────────────────┘  │
└──────────────────────┬──────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────┐
│              Flask Server                    │
│                                              │
│  POST /api/generate  → tailor.py → PDF       │
│  POST /api/compile   → compiler.py → PDF     │
│  GET  /api/resumes   → list resumes/         │
│  GET  /api/resumes/:id/tex  → .tex content   │
│  GET  /api/resumes/:id/pdf  → serve PDF      │
└──────────────────────────────────────────────┘
```

### Hosting

- **Next.js** → Vercel (free)
- **Flask** → Railway or Fly.io (free tier, supports `apt-get install texlive`)

---

## Flask API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/resumes` | GET | List all generated resumes `[{id, job_title, job_company, created_at}]` |
| `/api/resumes/:id/tex` | GET | Return the `.tex` content as text |
| `/api/resumes/:id/pdf` | GET | Serve the compiled PDF file |
| `/api/generate` | POST | `{job_description, job_title, job_company}` → runs `tailor_resume()` → returns `{id, job_title, job_company}` |
| `/api/compile` | POST | `{id, tex_content}` → writes `.tex`, runs `compile_tex_to_pdf()` → returns `{success}` |

**File:** `server/api.py` — thin Flask app that imports from existing `tailor.py` and `compiler.py`.

---

## Next.js Frontend

### Page: `/` (Dashboard)

Two-panel layout:

**Left sidebar** — List of all generated resumes, pulled from `GET /api/resumes`. Each item shows job title + company. Clicking one navigates to the editor.

**Main area** — "New Resume" form:
- Job Title input
- Company input
- Job Description textarea
- Generate button → calls `POST /api/generate`, shows loading state, then navigates to editor on completion

### Page: `/editor/[id]` (Editor)

Overleaf-style split view:

**Left panel** — Monaco editor (`@monaco-editor/react`) with LaTeX syntax highlighting, loaded from `GET /api/resumes/:id/tex`

**Right panel** — PDF preview via `react-pdf`, loaded from `GET /api/resumes/:id/pdf`

**Controls:**
- "Recompile" button → sends current editor content to `POST /api/compile`, refreshes PDF preview
- "Back to Dashboard" link

---

## Build Order (staged for incremental testing)

### Stage 1: Flask API

Build `server/api.py` with all 5 endpoints. Uses the existing `tailor.py` and `compiler.py` unchanged.

**You test:** Start Flask with `python server/api.py`. Use curl/Postman to:
- `GET /api/resumes` → should list existing resumes from `resumes/`
- `GET /api/resumes/zipline_software_engineering_intern/tex` → should return .tex text
- `GET /api/resumes/zipline_software_engineering_intern/pdf` → should return the PDF
- `POST /api/compile` with an id + .tex content → should recompile
- `POST /api/generate` with a job description → should generate a new resume

---

### Stage 2: Dashboard Page

Replace `client/app/page.tsx` with the dashboard UI — resume list on the left, generation form on the right. Calls the Flask API.

**You test:** Run both Flask and Next.js. Open `localhost:3000`:
- Should see existing resumes in the sidebar
- Fill out the form, click Generate → should show loading, then the new resume should appear in the sidebar

---

### Stage 3: Editor Page

Build `client/app/editor/[id]/page.tsx` with Monaco + react-pdf split view. Clicking a resume from the dashboard navigates here.

**You test:** Click a resume from the sidebar:
- LaTeX should load in the left editor
- PDF should render on the right
- Edit a bullet in the LaTeX → click Recompile → PDF should update

---

## Dependencies

### Server (add to existing)
```
flask
flask-cors
```

### Client (add to existing)
```
@monaco-editor/react
react-pdf
```

---

## File Structure (new/modified files only)

```
server/
  api.py              [NEW]  Flask API server

client/app/
  page.tsx            [MODIFY]  Dashboard with resume list + generation form
  editor/
    [id]/
      page.tsx        [NEW]  Overleaf-style LaTeX editor + PDF preview
  globals.css         [MODIFY]  Styling for dashboard and editor
```
