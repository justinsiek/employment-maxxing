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

PROJECT_SELECTION_SYSTEM = """You are an expert resume curator for software engineering roles. Given a job description and a bank of projects, select the 4 most relevant projects.

Return a JSON object with this exact schema:
{
  "selected_projects": ["proj_id1", "proj_id2", "proj_id3", "proj_id4"]
}

Select projects whose technologies, skills, and problem domains best match the job requirements. Prioritize projects that demonstrate the most relevant technical skills."""

BULLET_TUNING_SYSTEM = """You are an expert resume bullet point writer for software engineering roles. Your job is to craft bullet points for a single resume section, tailored for a specific job posting.

You will receive a description of the work done and a list of phrases/metrics that MUST appear in the bullets.

CRITICAL RULES:
- You must return exactly 3 bullet points
- Bullet 1: MUST be 210-220 characters (exactly two lines on a resume)
- Bullet 2: MUST be 210-220 characters (exactly two lines on a resume)
- Bullet 3: MUST be 105-110 characters (exactly one line on a resume)
- COUNT CHARACTERS CAREFULLY. This is the most important constraint.
- Every item in the "must_include" list MUST appear in at least one bullet
- Emphasize skills and keywords from the job description
- Maintain truthfulness — only reframe existing work, never fabricate
- Keep LaTeX escape characters exactly as provided (\\%, \\&, \\emph{}, etc.)
- Bullets should NOT start with a dash or bullet character — just the text content

Return a JSON object:
{
  "bullets": ["bullet1 (210-220 chars)", "bullet2 (210-220 chars)", "bullet3 (105-110 chars)"]
}"""

SKILLS_SYSTEM = """You are an expert resume writer. Given a job description and a full skills bank, select the most relevant subset of skills to highlight on a resume.

Return a JSON object:
{
  "languages": ["Python", "JavaScript"],
  "frameworks": ["React", "Flask"],
  "libraries": ["pandas", "OpenCV"],
  "tools": ["AWS", "Docker"]
}"""


def load_projects():
    with open(PROJECTS_PATH, 'r') as f:
        return json.load(f)


def sanitize_job_name(title, company):
    raw = f"{company}_{title}".lower()
    return re.sub(r'[^a-z0-9]+', '_', raw).strip('_')


def call_llm(system_prompt, user_prompt):
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)


def select_projects(job_description, projects_data):
    """Call 1: Pick the 4 most relevant projects."""
    projects_summary = json.dumps(projects_data['projects'], indent=2)
    user_prompt = f"""## Job Description

{job_description}

## Available Projects

{projects_summary}

Select the 4 most relevant projects for this job."""

    result = call_llm(PROJECT_SELECTION_SYSTEM, user_prompt)
    print(f"  Selected projects: {result['selected_projects']}")
    return result['selected_projects']


def tune_section_bullets(job_description, section_data, section_type):
    """Call per section: Craft bullets for one experience or project from its description."""
    must_include = json.dumps(section_data.get('must_include', []))
    user_prompt = f"""## Job Description

{job_description}

## Resume Section to Tailor ({section_type})

Title: {section_data.get('title') or section_data.get('name')}
Company/Technologies: {section_data.get('company', section_data.get('technologies', ''))}

Description of work:
{section_data['description']}

Must include these phrases/metrics in the bullets:
{must_include}

Craft exactly 3 tailored bullet points following the character length rules."""

    result = call_llm(BULLET_TUNING_SYSTEM, user_prompt)

    # Validate bullet count
    if len(result['bullets']) != 3:
        raise ValueError(f"Expected 3 bullets, got {len(result['bullets'])}")

    # Log character counts for debugging
    for i, b in enumerate(result['bullets']):
        print(f"    Bullet {i+1}: {len(b)} chars")

    return result['bullets']


def select_skills(job_description, projects_data):
    """Select relevant skills subset."""
    user_prompt = f"""## Job Description

{job_description}

## Full Skills Bank

{json.dumps(projects_data['skills'], indent=2)}

Select the most relevant skills for this job."""

    return call_llm(SKILLS_SYSTEM, user_prompt)


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


def fill_template(experience_tex, project_tex, skills):
    with open(TEMPLATE_PATH, 'r') as f:
        tex = f.read()

    tex = tex.replace('<<experience_entries>>', experience_tex)
    tex = tex.replace('<<project_entries>>', project_tex)
    tex = tex.replace('<<skills_languages>>', ', '.join(skills.get('languages', [])))
    tex = tex.replace('<<skills_frameworks>>', ', '.join(skills.get('frameworks', [])))
    tex = tex.replace('<<skills_libraries>>', ', '.join(skills.get('libraries', [])))
    tex = tex.replace('<<skills_tools>>', ', '.join(skills.get('tools', [])))
    return tex


def tailor_resume(job_description, job_title='Unknown Position', job_company='Unknown Company'):
    """
    Full pipeline: 7 LLM calls → fill template → compile PDF.

    Call 1: Select 4 projects
    Calls 2-3: Tune each experience section (always keep all experiences)
    Calls 4-7: Tune each selected project section
    Skills are kept as-is from projects.json.
    """
    projects_data = load_projects()
    tailored_bullets = {}

    # Call 1: Select projects
    print("Step 1/7: Selecting projects...")
    selected_project_ids = select_projects(job_description, projects_data)

    # Calls 2-3: Tune experience bullets (always keep all experiences)
    for i, exp in enumerate(projects_data['experiences']):
        print(f"Step {2+i}/7: Tuning experience - {exp['title']}...")
        tailored_bullets[exp['id']] = tune_section_bullets(job_description, exp, 'Experience')

    # Calls 4-7: Tune project bullets
    for i, proj_id in enumerate(selected_project_ids):
        proj = next(p for p in projects_data['projects'] if p['id'] == proj_id)
        print(f"Step {4+i}/7: Tuning project - {proj['name']}...")
        tailored_bullets[proj_id] = tune_section_bullets(job_description, proj, 'Project')

    # Skills stay as-is from projects.json
    skills = projects_data['skills']

    # Build LaTeX
    experience_tex = build_experience_tex(projects_data['experiences'], tailored_bullets)
    project_tex = build_project_tex(selected_project_ids, projects_data, tailored_bullets)
    tex_content = fill_template(experience_tex, project_tex, skills)

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

    return {
        'pdf_path': result['pdf_path'],
        'tex_path': os.path.abspath(tex_dest),
        'job_title': job_title,
        'job_company': job_company,
        'selected_projects': selected_project_ids,
        'tailored_bullets': tailored_bullets,
        'skills': skills,
    }


if __name__ == '__main__':
    test_file = os.path.join(os.path.dirname(__file__), 'data', 'test_job_description.txt')
    with open(test_file, 'r') as f:
        test_description = f.read()

    print("Tailoring resume...\n")
    result = tailor_resume(test_description, job_title='ML Engineer Intern Simulation', job_company='Zoox')
    print(f"\nPDF saved to: {result['pdf_path']}")
    print(f"TeX saved to: {result['tex_path']}")
