"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

interface Resume {
  id: string;
  job_company: string;
  job_title: string;
  created_at: number;
}

interface QueueItem {
  id: string;
  job_company: string;
  job_title: string;
  job_description: string;
  status: 'queued' | 'generating' | 'completed' | 'error';
  message?: string;
  resume_id?: string;
}

export default function Dashboard() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [jobTitle, setJobTitle] = useState("");
  const [jobCompany, setJobCompany] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  // Queue state
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const isGenerating = queue.some(q => q.status === 'generating');

  useEffect(() => {
    fetchResumes();
  }, []);

  const fetchResumes = async () => {
    try {
      const res = await fetch("http://127.0.0.1:5001/api/resumes");
      const data = await res.json();
      setResumes(data.resumes || []);
    } catch (err) {
      console.error("Failed to fetch resumes:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.preventDefault(); // Prevent navigating to the editor

    if (!confirm("Are you sure you want to delete this resume?")) {
      return;
    }

    try {
      const res = await fetch(`http://127.0.0.1:5001/api/resumes/${id}`, {
        method: 'DELETE',
      });

      if (!res.ok) {
        throw new Error("Failed to delete resume");
      }

      // Remove from state
      setResumes(resumes.filter(r => r.id !== id));
    } catch (err) {
      console.error(err);
      alert("Failed to delete resume");
    }
  };

  const handleQueueJob = (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobDescription.trim()) {
      setFormError("Job description is required");
      return;
    }
    setFormError(null);
    const newJob: QueueItem = {
      id: crypto.randomUUID(),
      job_company: jobCompany || "Unknown Company",
      job_title: jobTitle || "Software Engineer",
      job_description: jobDescription,
      status: 'queued'
    };
    setQueue(prev => [...prev, newJob]);
    // reset form for the next job
    setJobTitle("");
    setJobCompany("");
    setJobDescription("");
  };

  useEffect(() => {
    const active = queue.find(q => q.status === 'generating');
    if (!active) {
      const next = queue.find(q => q.status === 'queued');
      if (next) {
        startJob(next);
      }
    }
  }, [queue]);

  const startJob = (job: QueueItem) => {
    setQueue(prev => prev.map(q => q.id === job.id ? { ...q, status: 'generating', message: 'Starting generation process...' } : q));

    try {
      const url = new URL("http://127.0.0.1:5001/api/generate/stream");
      url.searchParams.append("job_title", job.job_title);
      url.searchParams.append("job_company", job.job_company);
      url.searchParams.append("job_description", job.job_description);

      const eventSource = new EventSource(url.toString());

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "progress") {
          setQueue(prev => prev.map(q => q.id === job.id ? { ...q, message: data.message } : q));
        } else if (data.type === "complete") {
          eventSource.close();
          setQueue(prev => prev.map(q => q.id === job.id ? { ...q, status: 'completed', message: 'Complete!', resume_id: data.data.id } : q));
          fetchResumes(); // Silent refresh of sidebar
        } else if (data.type === "error") {
          eventSource.close();
          setQueue(prev => prev.map(q => q.id === job.id ? { ...q, status: 'error', message: data.message || "An error occurred." } : q));
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setQueue(prev => prev.map(q => q.id === job.id ? { ...q, status: 'error', message: "Connection lost." } : q));
      };

    } catch (err: any) {
      console.error(err);
      setQueue(prev => prev.map(q => q.id === job.id ? { ...q, status: 'error', message: err.message || "An error occurred." } : q));
    }
  };

  const handleDismissJob = (id: string) => {
    setQueue(prev => prev.filter(q => q.id !== id));
  };

  return (
    <div className="flex h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 font-sans">
      {/* Sidebar: Resume List */}
      <div className="w-80 border-r border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 flex flex-col">
        <div className="p-6 border-b border-zinc-200 dark:border-zinc-800">
          <h1 className="text-xl font-semibold tracking-tight">Resume Tailor</h1>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <h2 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3 px-2">
            Generated Resumes
          </h2>

          {loading ? (
            <div className="text-sm text-zinc-500 px-2 animate-pulse">Loading resumes...</div>
          ) : resumes.length === 0 ? (
            <div className="text-sm text-zinc-500 px-2">No resumes generated yet.</div>
          ) : (
            resumes.map((resume) => (
              <div key={resume.id} className="group relative">
                <Link
                  href={`/editor/${resume.id}`}
                  className="block p-3 pr-10 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
                >
                  <div className="font-medium truncate">{resume.job_company}</div>
                  <div className="text-sm text-zinc-500 dark:text-zinc-400 truncate">
                    {resume.job_title || "Software Engineer"}
                  </div>
                  <div className="text-xs text-zinc-400 dark:text-zinc-500 mt-1">
                    {new Date(resume.created_at * 1000).toLocaleDateString()}
                  </div>
                </Link>
                <button
                  onClick={(e) => handleDelete(e, resume.id)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-2 text-zinc-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity bg-zinc-100 dark:bg-zinc-800 rounded-md"
                  title="Delete Resume"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M3 6h18"></path>
                    <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"></path>
                    <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"></path>
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Area: Generation Form and Queue */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-8 lg:p-12">
          <div className="mb-8">
            <h2 className="text-3xl font-bold tracking-tight mb-2">Create New Resume</h2>
            <p className="text-zinc-500 dark:text-zinc-400">
              Paste a job description below. We'll queue it up, rewrite your bullets to match, and compile a tailored LaTeX PDF automatically.
            </p>
          </div>

          {/* Queue UI */}
          {queue.length > 0 && (
            <div className="mb-10 space-y-3">
              <h3 className="text-sm font-semibold text-zinc-500 uppercase tracking-wider mb-3 px-1">Generation Queue ({queue.length})</h3>
              <div className="space-y-3">
                {queue.map(job => (
                  <div key={job.id} className={`p-4 rounded-lg border flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 transition-colors ${job.status === 'generating' ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-900/10' : 'border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900'}`}>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-zinc-900 dark:text-white truncate">
                        {job.job_company} <span className="text-zinc-400 dark:text-zinc-500">— {job.job_title}</span>
                      </div>
                      <div className="text-sm mt-1.5 flex items-center gap-2">
                        {job.status === 'queued' && <span className="text-zinc-500 dark:text-zinc-400">Waiting in queue...</span>}
                        {job.status === 'generating' && (
                          <>
                            <svg className="animate-spin h-3.5 w-3.5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            <span className="text-blue-600 dark:text-blue-400 font-medium">{job.message}</span>
                          </>
                        )}
                        {job.status === 'error' && <span className="text-red-600 dark:text-red-400 font-medium">Error: {job.message}</span>}
                        {job.status === 'completed' && <span className="text-green-600 dark:text-green-500 font-medium">Successfully generated!</span>}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {job.status === 'completed' && job.resume_id && (
                        <Link href={`/editor/${job.resume_id}`} className="text-sm font-medium bg-zinc-900 hover:bg-zinc-800 text-white dark:bg-white dark:hover:bg-zinc-100 dark:text-zinc-900 px-4 py-2 rounded-md transition-colors">
                          Open Editor
                        </Link>
                      )}
                      {(job.status === 'completed' || job.status === 'error' || job.status === 'queued') && (
                        <button onClick={() => handleDismissJob(job.id)} className="p-2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-md transition-colors" title="Dismiss">
                          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <form onSubmit={handleQueueJob} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium">Job Title</label>
                <input
                  type="text"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  placeholder="e.g. Frontend Engineer"
                  className="w-full p-3 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 focus:ring-2 focus:ring-blue-500 outline-none transition"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Company Name</label>
                <input
                  type="text"
                  value={jobCompany}
                  onChange={(e) => setJobCompany(e.target.value)}
                  placeholder="e.g. Stripe"
                  className="w-full p-3 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 focus:ring-2 focus:ring-blue-500 outline-none transition"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Job Description</label>
              <textarea
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
                placeholder="Paste the full job description here..."
                rows={15}
                className="w-full p-4 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 focus:ring-2 focus:ring-blue-500 outline-none transition resize-y font-mono text-sm"
              />
            </div>

            {formError && (
              <div className="p-4 rounded-md bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm border border-red-200 dark:border-red-800">
                {formError}
              </div>
            )}

            <button
              type="submit"
              disabled={!jobDescription.trim()}
              className="w-full md:w-auto px-8 py-3 bg-zinc-900 hover:bg-zinc-800 dark:bg-white dark:hover:bg-zinc-200 text-white dark:text-black font-semibold rounded-md transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              Add to Queue
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
