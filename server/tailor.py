import os
import re
import json
import tempfile
import shutil
from openai import OpenAI
from dotenv import load_dotenv
from compiler import compile_tex_to_pdf

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

PROJECTS_PATH = os.path.join(os.path.dirname(__file__), 'data', 'projects.json')
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates', 'resume_template.tex')
RESUMES_DIR = os.path.join(os.path.dirname(__file__), '..', 'resumes')

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# --- Prompts ---

ALWAYS_INCLUDE_PROJECTS = ['proj_flywheel', 'proj_aom', 'proj_makersafe']

PROJECT_SELECTION_SYSTEM = """You are an expert resume curator for software engineering roles. Given a job description and a set of candidate projects, select the 1 project that best complements the resume for this specific job.

Return a JSON object with this exact schema:
{
  "selected_project": "proj_id"
}

Select the project whose technologies, skills, and problem domains best match the job requirements."""

BULLET_TUNING_SYSTEM = """You are an elite resume writer specializing in software engineering internship and new-grad resumes. Your job is to craft 3 bullet points for ONE resume section, tailored for a specific job posting.

You will receive:
- A job description to tailor toward
- A description of the candidate's work in this role/project
- Optionally, a list of phrases/metrics that MUST appear verbatim in the bullets

## WRITING FRAMEWORK — USE THE XYZ FORMULA

Structure every bullet as: "Accomplished [X] as measured by [Y], by doing [Z]"
- X = the result or impact (what improved, what was built, what was delivered)
- Y = the quantifiable metric (percentage, count, scale, speed, accuracy)
- Z = the specific technical action, tools, or methods used

This can be rearranged for flow, but every bullet MUST contain all three components (action, method, measurable result).

## STYLE RULES

1. **Start with a strong, unique action verb.** Use a DIFFERENT verb for each bullet. 
   Good verbs: Architected, Engineered, Developed, Constructed, Implemented, Designed, Built, Deployed, Optimized, Achieved, Spearheaded, Led, Automated, Integrated, Accelerated, Reduced, Streamlined, Launched
   NEVER use: Utilized, Helped, Assisted, Worked on, Was responsible for

2. **Be specific and technical.** Name exact technologies, frameworks, algorithms, and architectures. Vague descriptions like "improved the system" are unacceptable.

3. **Quantify everything.** Every bullet must include at least one number (percentage, count, dollar amount, scale, latency, accuracy, etc.). Use real numbers from the description — do NOT invent or fabricate metrics.

4. **Write in past tense, no subject.** Bullets should read like "Built X..." not "I built X..." or "Building X..."

5. **Each bullet must be ONE complete, flowing sentence.** No fragments. No sentences that end abruptly with a period after a single word. No appending disconnected clauses.

6. **Consistency across bullets:**
   - Hackathon wins must ALWAYS use the format: winning \\emph{Award Name} at a hackathon with over N participants
   - Numbers: always use digits, not words (write "3" not "three")
   - Percentages: always use the format "N\\%" 
   - Lists of technologies: separate with commas, no "and" before the last item

7. **ATS keyword optimization.** This is critical for passing automated resume screeners:
   - FIRST PRIORITY: Extract EXACT keywords, phrases, and technology names from the job description and weave as many as possible into the bullets. If the job says "distributed systems", use that exact phrase — don't paraphrase to "multi-node architecture"
   - SECOND PRIORITY: Include technologies that are genuinely part of the described work, even if not in the JD — these show breadth and help with general ATS matching
   - Do NOT inject buzzwords that have nothing to do with the actual project. Only mention technologies the candidate actually used
   - For abbreviations: mirror whatever form the job description uses. If the JD says "CI/CD", use "CI/CD"
   - Spread job description keywords across ALL 3 bullets rather than cramming them into one
   - Do NOT keyword stuff — every keyword must be part of a natural, readable sentence that describes real work

## ANTI-PATTERNS — NEVER DO THESE

- ❌ Single-word sentence fragments: "...for monitoring. Iteratively."
- ❌ Repeating the same verb across bullets
- ❌ Inconsistent award formatting: don't say "among 600 participants" in one bullet and "(500 participants)" in another
- ❌ Vague impact: "improved performance" without a number
- ❌ Starting a bullet with "Utilized" or "Responsible for"
- ❌ Ending a bullet with a dangling technology name or fragment
- ❌ Bullets that are just a list of technologies with no context
- ❌ Inventing fake metrics — only use numbers stated or clearly implied in the description
- ❌ Filler adjectives like "massive", "robust", "cutting-edge", "innovative", "comprehensive", "sophisticated" — let the numbers speak for themselves (say "property graph with 500M+ nodes" not "massive property graph with 500M+ nodes")
- ❌ Repeating the same phrase or fact across multiple bullets — if "hackathon with over 500 participants" appears in one bullet, do NOT say it again in another bullet. Each bullet must contain unique information.
- ❌ Forcing unimpressive or trivial statistics just to have a number. The number "1" is almost NEVER impressive. BAD examples: "1 product cycle", "1 PostgreSQL schema", "1 microservice deployed", "3 user metrics", "2 file types", "4 hyperparameters", "5 pipeline stages". These are meaningless counts that weaken the bullet. Only quantify when the number demonstrates meaningful scale (500M+ nodes), speed (30\\% faster), accuracy (88\\%), or impact (3 production products). If a bullet doesn't have a genuinely impressive number, just describe the technical work without forcing a count.
- ❌ Using non-standard acronyms that ATS won't recognize — write "knowledge graph" not "KG", write "hand history" not "HH". Only use acronyms that are universally recognized in CS (GNN, CNN, API, REST, CI/CD, ETL, LLM, RLHF, DPO, SQL, etc.)

## CHARACTER LENGTH CONSTRAINTS

Each bullet must be EXACTLY one of these two sizes:
- **1-line bullet:** 100-110 characters
- **2-line bullet:** 205-215 characters

You must return exactly the number of bullets requested. Choose whatever mix of 1-line and 2-line bullets best fits the content naturally. Do not force content into an unnatural length.
Count characters carefully. This determines how the resume renders in LaTeX.

## MUST-INCLUDE ITEMS (if provided)

If a "must_include" list is provided, every item MUST appear verbatim in EXACTLY ONE bullet — not zero, not two. Distribute them across the 3 bullets so no single bullet is overloaded. Copy them exactly as provided, including any LaTeX formatting like \\emph{} or \\%. NEVER repeat a must_include item or its data in a different bullet.

## OUTPUT FORMAT

Return a JSON object with exactly 3 bullets. For each bullet, also return its target type:
{
  "bullets": ["bullet text", "bullet text", "bullet text"]
}"""



def load_projects():
    with open(PROJECTS_PATH, 'r') as f:
        return json.load(f)


def sanitize_job_name(title, company):
    raw = f"{company}_{title}".lower()
    return re.sub(r'[^a-z0-9]+', '_', raw).strip('_')


def call_llm(system_prompt, user_prompt):
    response = client.chat.completions.create(
        model="o4-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def select_projects(job_description, projects_data):
    """Pick projects: 3 are always included, LLM picks the 4th from the rest."""
    # Filter to only the candidates the LLM can choose from
    candidates = [p for p in projects_data['projects'] if p['id'] not in ALWAYS_INCLUDE_PROJECTS]
    candidates_summary = json.dumps(candidates, indent=2)
    user_prompt = f"""## Job Description

{job_description}

## Candidate Projects (pick 1)

{candidates_summary}

Select the 1 most relevant project for this job."""

    result = call_llm(PROJECT_SELECTION_SYSTEM, user_prompt)
    fourth_project = result['selected_project']
    selected = ALWAYS_INCLUDE_PROJECTS + [fourth_project]
    print(f"  Always included: {ALWAYS_INCLUDE_PROJECTS}")
    print(f"  LLM picked: {fourth_project}")
    return selected


def sanitize_bullet(text):
    """Escape LaTeX special characters the LLM might introduce, while preserving
    intentional LaTeX commands from must_include items (like \\emph{}, \\%)."""
    # Don't touch text that already has proper LaTeX commands
    # Only escape bare special chars that aren't part of LaTeX commands
    
    # Fix unescaped & (but not \\&)
    text = re.sub(r'(?<!\\)&', r'\\&', text)
    # Fix unescaped % (but not \\%)
    text = re.sub(r'(?<!\\)%', r'\\%', text)
    # Fix unescaped # (but not \\#)  
    text = re.sub(r'(?<!\\)#', r'\\#', text)
    # Fix unescaped _ outside of math mode (but not \\_)
    # Be careful: _ is common in tech terms but breaks LaTeX
    # Only escape if not already escaped and not inside a LaTeX command
    text = re.sub(r'(?<!\\)_(?![a-zA-Z]*})', r'\\_', text)
    
    return text


def tune_section_bullets(job_description, section_data, section_type):
    """Call per section: Craft bullets for one experience or project from its description."""
    num_bullets = section_data.get('num_bullets', 3)
    must_include = section_data.get('must_include', [])
    
    must_include_block = ""
    if must_include:
        must_include_block = f"""\nMust include these phrases/metrics verbatim in the bullets:
{json.dumps(must_include)}"""

    user_prompt = f"""## Job Description

{job_description}

## Resume Section to Tailor ({section_type})

Title: {section_data.get('title') or section_data.get('name')}
Company/Technologies: {section_data.get('company', section_data.get('technologies', ''))}

Description of work:
{section_data['description']}{must_include_block}

Craft exactly {num_bullets} tailored bullet points following the character length rules."""

    result = call_llm(BULLET_TUNING_SYSTEM, user_prompt)

    # Validate bullet count
    if len(result['bullets']) != num_bullets:
        raise ValueError(f"Expected {num_bullets} bullets, got {len(result['bullets'])}")
    # Sanitize and log character counts
    sanitized = []
    for i, b in enumerate(result['bullets']):
        b = sanitize_bullet(b)
        print(f"    Bullet {i+1}: {len(b)} chars")
        sanitized.append(b)

    return sanitized




def build_experience_tex(experiences, tailored_bullets):
    lines = []
    for exp in experiences:
        bullets = tailored_bullets[exp['id']]
        lines.append(f'    \\resumeSubheading')
        lines.append(f'      {{{exp["title"]}}}{{{exp["dates"]}}}')
        lines.append(f'      {{{exp["company"]}}}{{{exp["location"]}}}')
        lines.append(f'      \\resumeItemListStart')
        for b in bullets:
            lines.append(f'        \\resumeItem{{{b}}}')
        lines.append(f'      \\resumeItemListEnd')
        lines.append('')
    return '\n'.join(lines)


def build_project_tex(selected_ids, projects_data, tailored_bullets):
    lines = []
    for proj_id in selected_ids:
        proj = next(p for p in projects_data['projects'] if p['id'] == proj_id)
        bullets = tailored_bullets[proj_id]
        name_part = f'\\textbf{{{proj["name"]}}}'
        if proj.get('url'):
            name_part += f' $|$ \\href{{{proj["url"]}}}{{\\emph{{Code}}}}'
        lines.append(f'     \\resumeProjectHeading')
        lines.append(f'          {{{name_part}}}{{{proj["technologies"]}}}')
        lines.append(f'          \\resumeItemListStart')
        for b in bullets:
            lines.append(f'            \\resumeItem{{{b}}}')
        lines.append(f'          \\resumeItemListEnd')
    return '\n'.join(lines)


def fill_template(experience_tex, project_tex):
    with open(TEMPLATE_PATH, 'r') as f:
        tex = f.read()

    tex = tex.replace('<<experience_entries>>', experience_tex)
    tex = tex.replace('<<project_entries>>', project_tex)
    return tex


def tailor_resume(job_description, job_title='Unknown Position', job_company='Unknown Company', progress_callback=None):
    """
    Full pipeline: 7 LLM calls → fill template → compile PDF.

    Call 1: Select 4 projects
    Calls 2-3: Tune each experience section (always keep all experiences)
    Calls 4-7: Tune each selected project section
    Skills are hardcoded in the LaTeX template.
    """
    def log_progress(msg):
        print(msg)
        if progress_callback:
            progress_callback(msg)

    projects_data = load_projects()
    tailored_bullets = {}

    # Call 1: Select projects
    log_progress("Step 1/7: Selecting projects...")
    selected_project_ids = select_projects(job_description, projects_data)

    # Calls 2-3: Tune experience bullets (always keep all experiences)
    for i, exp in enumerate(projects_data['experiences']):
        log_progress(f"Step {2+i}/7: Tuning experience - {exp['title']}...")
        tailored_bullets[exp['id']] = tune_section_bullets(job_description, exp, 'Experience')

    # Calls 4-7: Tune project bullets
    for i, proj_id in enumerate(selected_project_ids):
        proj = next(p for p in projects_data['projects'] if p['id'] == proj_id)
        log_progress(f"Step {4+i}/7: Tuning project - {proj['name']}...")
        tailored_bullets[proj_id] = tune_section_bullets(job_description, proj, 'Project')

    # Build LaTeX
    log_progress("Building LaTeX and compiling PDF...")
    experience_tex = build_experience_tex(projects_data['experiences'], tailored_bullets)
    project_tex = build_project_tex(selected_project_ids, projects_data, tailored_bullets)
    tex_content = fill_template(experience_tex, project_tex)

    # Write and compile
    job_dir_name = sanitize_job_name(job_title, job_company)
    output_dir = os.path.join(RESUMES_DIR, job_dir_name)
    os.makedirs(output_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile(mode='w', suffix='.tex', delete=False) as f:
        f.write(tex_content)
        tmp_tex_path = f.name

    try:
        result = compile_tex_to_pdf(tmp_tex_path, output_dir=output_dir)
        tex_dest = os.path.join(output_dir, 'resume.tex')
        shutil.copy2(tmp_tex_path, tex_dest)
    finally:
        os.unlink(tmp_tex_path)

    log_progress("Done!")
    return {
        'pdf_path': result['pdf_path'],
        'tex_path': os.path.abspath(tex_dest),
        'job_title': job_title,
        'job_company': job_company,
        'selected_projects': selected_project_ids,
        'tailored_bullets': tailored_bullets,
    }


if __name__ == '__main__':
    test_file = os.path.join(os.path.dirname(__file__), 'data', 'test_job_description.txt')
    with open(test_file, 'r') as f:
        test_description = f.read()

    print("Tailoring resume...\n")
    result = tailor_resume(test_description, job_title='Software Engineering Intern', job_company='Zipline')
    print(f"\nPDF saved to: {result['pdf_path']}")
    print(f"TeX saved to: {result['tex_path']}")
