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

export default function Dashboard() {
  const router = useRouter();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);

  // Form state
  const [jobTitle, setJobTitle] = useState("");
  const [jobCompany, setJobCompany] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!jobDescription.trim()) {
      setError("Job description is required");
      return;
    }

    setGenerating(true);
    setError(null);
    setStatusMessage("Starting generation process...");

    try {
      // Use EventSource for Server-Sent Events
      const url = new URL("http://127.0.0.1:5001/api/generate/stream");
      url.searchParams.append("job_title", jobTitle);
      url.searchParams.append("job_company", jobCompany);
      url.searchParams.append("job_description", jobDescription);

      const eventSource = new EventSource(url.toString());

      eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === "progress") {
          setStatusMessage(data.message);
        } else if (data.type === "complete") {
          eventSource.close();
          // Navigate to the editor for the new resume
          router.push(`/editor/${data.data.id}`);
        } else if (data.type === "error") {
          eventSource.close();
          setError(data.message || "An error occurred during generation.");
          setGenerating(false);
          setStatusMessage(null);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setError("Connection to server lost. Please try again.");
        setGenerating(false);
        setStatusMessage(null);
      };

    } catch (err: any) {
      console.error(err);
      setError(err.message || "An error occurred during generation.");
      setGenerating(false);
      setStatusMessage(null);
    }
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

      {/* Main Area: Generation Form */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto p-8 lg:p-12">
          <div className="mb-8">
            <h2 className="text-3xl font-bold tracking-tight mb-2">Create New Resume</h2>
            <p className="text-zinc-500 dark:text-zinc-400">
              Paste a job description below and our AI will pick your most relevant projects,
              rewrite your bullets to match the requirements, and compile a tailored LaTeX PDF.
            </p>
          </div>

          <form onSubmit={handleGenerate} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium">Job Title</label>
                <input
                  type="text"
                  value={jobTitle}
                  onChange={(e) => setJobTitle(e.target.value)}
                  placeholder="e.g. Frontend Engineer"
                  className="w-full p-3 rounded-md border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 focus:ring-2 focus:ring-blue-500 outline-none transition"
                  disabled={generating}
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
                  disabled={generating}
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
                disabled={generating}
              />
            </div>

            {error && (
              <div className="p-4 rounded-md bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm border border-red-200 dark:border-red-800">
                {error}
              </div>
            )}

            {generating && statusMessage && (
              <div className="p-4 rounded-md bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-sm border border-blue-200 dark:border-blue-800 flex items-center gap-3">
                <svg className="animate-spin h-4 w-4 text-blue-500 shrink-0" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="font-mono">{statusMessage}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={generating || !jobDescription.trim()}
              className="w-full md:w-auto px-8 py-3 bg-zinc-900 hover:bg-zinc-800 dark:bg-white dark:hover:bg-zinc-200 text-white dark:text-black font-semibold rounded-md transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {generating ? "Generating..." : "Generate Tailored Resume"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
