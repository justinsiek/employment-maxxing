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

BULLET_TUNING_SYSTEM = """You are an elite resume editor specializing in software engineering roles. Your job is to select and subtly refine bullet points from a provided "Bullet Bank" to perfectly match a specific job description.

You will receive:
- A job description to tailor toward
- A "Bullet Bank" of pre-written, highly polished achievements for this role/project
- Optionally, a list of phrases/metrics that MUST appear verbatim in your final selection

## YOUR TASK
1. **Select** exactly the requested number of bullets from the Bullet Bank that are MOST relevant to the job's requirements.
2. **Refine** the selected bullets by making MINOR keyword substitutions to better match the terminology used in the job description (e.g., if the bank says "React" but the JD emphasizes "Next.js", and the project supports it, swap it).

## STRICT RULES for REFINEMENT
1. **Aggressive ATS Keyword Optimization:** You MUST swap out frameworks/languages in the bullets for equivalents requested in the Job Description when broadly applicable to the project domain. For example, if the JD asks for "Express" and the bullet says "Flask", change it to "Express". If the JD asks for "React" and the bullet says "NextJS", change it. Your goal is to map the candidate's achievements perfectly to the JD's technology stack.
2. **Never change the metrics or numbers.** If the bank says "500M+ nodes", you must keep exactly "500M+ nodes".
3. **Never change the core grammatical structure.** Keep the original verbs and sentence flow. You are an editor substituting keywords, NOT a creative writer.
4. **No abbreviations.** If a bullet uses an acronym, ensure it matches standard industry usage or the JD exactly.
5. **Zero Redundancy/Repetition:** Do not repeat the same keyword, technology, or phrase multiple times within a single bullet point or across chosen bullets. If a substitution would result in awkward repetition (e.g. "Built a React web app using React"), you must rewrite or omit the duplicate word so it flows naturally.
6. **STRICT CHARACTER LENGTH CONSTRAINTS:** Every single bullet returned MUST be either exactly 100-110 characters OR exactly 200-210 characters long. Count carefully. If you substitute a longer word, you must trim a different word so the final count falls into one of these two buckets.

## OUTPUT FORMAT
Return a JSON object containing exactly the requested number of refined bullets in an array:
{
  "bullets": ["refined bullet 1", "refined bullet 2", "refined bullet 3"]
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

    for attempt in range(5):
        try:
            result = call_llm(PROJECT_SELECTION_SYSTEM, user_prompt)
            fourth_project = result['selected_project']
            selected = ALWAYS_INCLUDE_PROJECTS + [fourth_project]
            print(f"  Always included: {ALWAYS_INCLUDE_PROJECTS}")
            print(f"  LLM picked: {fourth_project}")
            return selected
        except Exception as e:
            if attempt == 4:
                print(f"  Project selection failed after 5 attempts: {e}")
                raise
            print(f"  Project selection attempt {attempt + 1} failed: {e}. Retrying...")


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
    user_prompt = f"""## Job Description

{job_description}

## Resume Section to Tailor ({section_type})

Title: {section_data.get('title') or section_data.get('name')}
Company/Technologies: {section_data.get('company', section_data.get('technologies', ''))}

Bullet Bank:
{json.dumps(section_data.get('bullet_bank', []), indent=2)}

Select and refine exactly {num_bullets} bullet points from the Bullet Bank."""

    for attempt in range(5):
        try:
            result = call_llm(BULLET_TUNING_SYSTEM, user_prompt)

            # Validate bullet count
            if len(result['bullets']) != num_bullets:
                raise ValueError(f"Expected {num_bullets} bullets, got {len(result['bullets'])}")
            
            # Sanitize and log character counts
            sanitized = []
            for i, b in enumerate(result['bullets']):
                b = sanitize_bullet(b)
                length = len(b)
                print(f"    Bullet {i+1}: {length} chars")
                if not ((100 <= length <= 110) or (200 <= length <= 210)):
                    raise ValueError(f"Bullet {i+1} has invalid length {length}. Must be 100-110 or 200-210 chars.")
                sanitized.append(b)

            return sanitized
        except Exception as e:
            if attempt == 4:
                print(f"  Bullet tuning failed after 5 attempts: {e}")
                raise
            print(f"  Bullet tuning attempt {attempt + 1} failed: {e}. Retrying...")




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
