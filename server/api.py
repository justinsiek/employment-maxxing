import os
import uuid
import time
from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import json
import threading
import queue

from tailor import tailor_resume
from compiler import compile_tex_to_pdf

app = Flask(__name__)
# Enable CORS for the Next.js frontend (running on a different port)
CORS(app)

RESUMES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'resumes'))

# Global jobs dictionary and queue
jobs_db = {}
job_queue = queue.Queue()

def background_worker():
    """Continuously processes jobs from the queue."""
    while True:
        job_id = job_queue.get()
        if job_id not in jobs_db:
            job_queue.task_done()
            continue
            
        job = jobs_db[job_id]
        job['status'] = 'generating'
        job['message'] = 'Starting generation process...'
        
        try:
            def progress_callback(msg):
                if jobs_db.get(job_id, {}).get('status') == 'cancelling':
                    raise InterruptedError("Job cancelled by user")
                jobs_db[job_id]['message'] = msg
                
            result = tailor_resume(
                job['job_description'], 
                job_title=job['job_title'], 
                job_company=job['job_company'], 
                progress_callback=progress_callback
            )
            
            # If it was cancelled during generation, don't mark as completed
            if jobs_db.get(job_id, {}).get('status') == 'cancelling':
                raise InterruptedError("Job cancelled by user")
            
            dir_path = os.path.dirname(result['tex_path'])
            resume_id = os.path.basename(dir_path)
            
            job['status'] = 'completed'
            job['message'] = 'Complete!'
            job['resume_id'] = resume_id
            
        except InterruptedError as e:
            job['status'] = 'cancelled'
            job['message'] = 'Cancelled by user.'
        except Exception as e:
            import traceback
            traceback.print_exc()
            job['status'] = 'error'
            job['message'] = str(e)
            
        finally:
            job_queue.task_done()

# Start the background worker thread when the app starts
threading.Thread(target=background_worker, daemon=True).start()

@app.route('/api/resumes', methods=['GET'])
def list_resumes():
    """List all generated resumes."""
    resumes = []
    if os.path.exists(RESUMES_DIR):
        for dirname in os.listdir(RESUMES_DIR):
            dir_path = os.path.join(RESUMES_DIR, dirname)
            if os.path.isdir(dir_path):
                tex_path = os.path.join(dir_path, 'resume.tex')
                pdf_path = os.path.join(dir_path, 'Justin_S_Resume.pdf')
                if os.path.exists(tex_path) and os.path.exists(pdf_path):
                    # We only have the folder name (e.g. "zipline_software_engineering_intern"). Let's infer title/company
                    # or just return the ID.
                    parts = dirname.split('_', 1)
                    company = parts[0].capitalize()
                    title = parts[1].replace('_', ' ').title() if len(parts) > 1 else ""
                    
                    resumes.append({
                        "id": dirname,
                        "job_company": company,
                        "job_title": title,
                        "created_at": os.path.getctime(pdf_path) # Basic timestamp for sorting later if needed
                    })
    
    # Sort by created_at descending (newest first)
    resumes.sort(key=lambda x: x["created_at"], reverse=True)
    return jsonify({"resumes": resumes})

@app.route('/api/resumes/<resume_id>/tex', methods=['GET'])
def get_resume_tex(resume_id):
    """Get the LaTeX source code for a specific resume."""
    tex_path = os.path.join(RESUMES_DIR, resume_id, 'resume.tex')
    if not os.path.exists(tex_path):
        return jsonify({"error": "Resume source not found"}), 404
        
    with open(tex_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    return jsonify({"tex_content": content})

@app.route('/api/resumes/<resume_id>/pdf', methods=['GET'])
def get_resume_pdf(resume_id):
    """Serve the compiled PDF for a specific resume."""
    pdf_path = os.path.join(RESUMES_DIR, resume_id, 'Justin_S_Resume.pdf')
    if not os.path.exists(pdf_path):
        return jsonify({"error": "Resume PDF not found"}), 404
    return send_file(pdf_path, mimetype='application/pdf')

@app.route('/api/resumes/<resume_id>', methods=['DELETE'])
def delete_resume(resume_id):
    """Delete a specific resume from disk."""
    dir_path = os.path.join(RESUMES_DIR, resume_id)
    if not os.path.exists(dir_path):
        return jsonify({"error": "Resume not found"}), 404
        
    try:
        import shutil
        shutil.rmtree(dir_path)
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_resume():
    """Generate a new tailored resume."""
    data = request.json
    job_description = data.get('job_description')
    job_title = data.get('job_title', 'Software Engineer')
    job_company = data.get('job_company', 'Company')
    
    if not job_description:
        return jsonify({"error": "job_description is required"}), 400
        
    try:
        # tailor_resume handles the LLM calls and initial PDF compilation
        result = tailor_resume(job_description, job_title=job_title, job_company=job_company)
        
        # Determine the generated ID from the path (tailor.py creates the folder)
        # result['tex_path'] looks like .../resumes/<id>/resume.tex
        dir_path = os.path.dirname(result['tex_path'])
        resume_id = os.path.basename(dir_path)
        
        return jsonify({
            "success": True,
            "id": resume_id,
            "job_title": job_title,
            "job_company": job_company
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/jobs', methods=['GET'])
def list_jobs():
    """Return all known jobs, sorted by creation time (implicitly by dict insertion order but let's be safe)."""
    return jsonify({"jobs": list(jobs_db.values())})

@app.route('/api/jobs', methods=['POST'])
def create_job():
    """Queue a new resume generation job."""
    data = request.json
    job_description = data.get('job_description')
    job_title = data.get('job_title', 'Software Engineer')
    job_company = data.get('job_company', 'Company')
    
    if not job_description:
        return jsonify({"error": "job_description is required"}), 400
        
    job_id = str(uuid.uuid4())
    
    jobs_db[job_id] = {
        "id": job_id,
        "job_title": job_title,
        "job_company": job_company,
        "job_description": job_description,
        "status": "queued",
        "message": "Waiting in queue...",
        "created_at": time.time()
    }
    
    job_queue.put(job_id)
    return jsonify({"success": True, "job_id": job_id})

@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def dismiss_job(job_id):
    """Remove a job from the UI. If it's running, cancel it first."""
    if job_id in jobs_db:
        if jobs_db[job_id]['status'] in ['queued', 'generating']:
            jobs_db[job_id]['status'] = 'cancelling'
        else:
            del jobs_db[job_id]
        return jsonify({"success": True})
    return jsonify({"error": "Job not found"}), 404

@app.route('/api/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a running or queued job, leaving it in the UI as 'cancelled'."""
    if job_id in jobs_db:
        job = jobs_db[job_id]
        if job['status'] == 'queued':
            job['status'] = 'cancelled'
            job['message'] = 'Cancelled by user.'
        elif job['status'] == 'generating':
            job['status'] = 'cancelling'
            job['message'] = 'Cancelling...'
        return jsonify({"success": True, "status": job['status']})
    return jsonify({"error": "Job not found"}), 404

@app.route('/api/compile', methods=['POST'])
def compile_resume():
    """Update LaTeX source and recompile the PDF."""
    data = request.json
    resume_id = data.get('id')
    tex_content = data.get('tex_content')
    
    if not resume_id or not tex_content:
        return jsonify({"error": "id and tex_content are required"}), 400
        
    dir_path = os.path.join(RESUMES_DIR, resume_id)
    tex_path = os.path.join(dir_path, 'resume.tex')
    
    if not os.path.exists(dir_path):
        return jsonify({"error": "Resume ID not found"}), 404
        
    try:
        # Write the updated content
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(tex_content)
            
        # Recompile
        compile_tex_to_pdf(tex_path, output_dir=dir_path)
        
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Run on port 5001 to avoid conflicting with Next.js on 3000
    app.run(port=5001, debug=True)
