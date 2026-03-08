"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import Editor from "@monaco-editor/react";

export default function EditorPage() {
    const router = useRouter();
    const params = useParams();
    const resumeId = params.id as string;

    const [texContent, setTexContent] = useState("");
    const [loading, setLoading] = useState(true);
    const [compiling, setCompiling] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [pdfTimestamp, setPdfTimestamp] = useState(Date.now()); // Used to force PDF iframe to reload
    const [editorTheme, setEditorTheme] = useState("light");

    // Create a ref for the iframe to force reloads cleanly if needed
    const iframeRef = useRef<HTMLIFrameElement>(null);

    useEffect(() => {
        // Sync Monaco theme with system preference
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        setEditorTheme(mediaQuery.matches ? "vs-dark" : "light");

        const changeHandler = (e: MediaQueryListEvent) => {
            setEditorTheme(e.matches ? "vs-dark" : "light");
        };
        mediaQuery.addEventListener('change', changeHandler);

        fetchTexContent();

        return () => mediaQuery.removeEventListener('change', changeHandler);
    }, [resumeId]);

    const fetchTexContent = async () => {
        try {
            const res = await fetch(`http://127.0.0.1:5001/api/resumes/${resumeId}/tex`);
            const data = await res.json();

            if (!res.ok) throw new Error(data.error || "Failed to load LaTeX source");

            setTexContent(data.tex_content);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const handleEditorChange = (value: string | undefined) => {
        if (value !== undefined) {
            setTexContent(value);
        }
    };

    const handleRecompile = async () => {
        setCompiling(true);
        setError(null);

        try {
            const res = await fetch("http://127.0.0.1:5001/api/compile", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    id: resumeId,
                    tex_content: texContent,
                }),
            });

            const data = await res.json();

            if (!res.ok || !data.success) {
                throw new Error(data.error || "Compilation failed");
            }

            // Force iframe reload by updating the timestamp appended to the URL
            setPdfTimestamp(Date.now());

        } catch (err: any) {
            setError(err.message);
        } finally {
            setCompiling(false);
        }
    };

    const handleDelete = async () => {
        if (!confirm("Are you sure you want to delete this resume?")) {
            return;
        }
        try {
            const res = await fetch(`http://127.0.0.1:5001/api/resumes/${resumeId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error("Failed to delete resume");
            router.push("/");
        } catch (err) {
            console.error(err);
            alert("Failed to delete resume");
        }
    };

    // Keyboard shortcut (Cmd+S or Ctrl+S) to recompile
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 's') {
                e.preventDefault();
                handleRecompile();
            }
        };

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [texContent, resumeId]);

    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-white font-sans">
                <div className="flex flex-col items-center gap-4">
                    <svg className="animate-spin h-8 w-8 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <div className="font-medium text-zinc-500 dark:text-zinc-400">Loading editor...</div>
                </div>
            </div>
        );
    }

    const pdfUrl = `http://127.0.0.1:5001/api/resumes/${resumeId}/pdf?t=${pdfTimestamp}`;

    return (
        <div className="flex flex-col h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-white font-sans overflow-hidden">
            {/* Top Bar */}
            <div className="h-14 border-b border-zinc-200 dark:border-zinc-800 flex items-center justify-between px-4 shrink-0 bg-white dark:bg-zinc-900">
                <div className="flex items-center gap-4">
                    <Link
                        href="/"
                        className="text-sm font-medium text-zinc-500 dark:text-zinc-400 hover:text-black dark:hover:text-white transition-colors flex items-center gap-1"
                    >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="m15 18-6-6 6-6" />
                        </svg>
                        Dashboard
                    </Link>
                    <div className="h-4 w-[1px] bg-zinc-300 dark:bg-zinc-700"></div>
                    <div className="font-mono text-sm text-zinc-700 dark:text-zinc-300">
                        {resumeId}
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {error && (
                        <div className="text-sm text-red-400 max-w-md truncate" title={error}>
                            Error: {error}
                        </div>
                    )}

                    <button
                        onClick={handleRecompile}
                        disabled={compiling}
                        className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                        {compiling ? (
                            <>
                                <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                </svg>
                                Compiling...
                            </>
                        ) : (
                            <>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
                                    <path d="M21 3v5h-5" />
                                </svg>
                                Recompile (⌘S)
                            </>
                        )}
                    </button>

                    <div className="h-6 w-[1px] bg-zinc-300 dark:bg-zinc-700 ml-2"></div>

                    <button
                        onClick={handleDelete}
                        className="p-1.5 text-zinc-500 hover:text-red-600 dark:text-zinc-400 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                        title="Delete Resume"
                    >
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M3 6h18" />
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
                            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        </svg>
                    </button>
                </div>
            </div>

            {/* Split Pane */}
            <div className="flex-1 flex overflow-hidden">
                {/* Left: LaTeX Editor */}
                <div className="w-1/2 border-r border-zinc-200 dark:border-zinc-800 h-full flex flex-col">
                    <div className="h-8 bg-zinc-100 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 flex items-center px-4 shrink-0">
                        <span className="text-xs font-mono text-zinc-500">resume.tex</span>
                    </div>
                    <div className="flex-1 bg-white dark:bg-zinc-950">
                        <Editor
                            height="100%"
                            defaultLanguage="latex"
                            theme={editorTheme}
                            value={texContent}
                            onChange={handleEditorChange}
                            options={{
                                wordWrap: "on",
                                minimap: { enabled: false },
                                fontSize: 13,
                                fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                                lineHeight: 22,
                                padding: { top: 16 },
                                scrollBeyondLastLine: false,
                                smoothScrolling: true,
                            }}
                        />
                    </div>
                </div>

                {/* Right: PDF Preview */}
                <div className="w-1/2 h-full bg-zinc-200 dark:bg-[#525659] flex flex-col">
                    <div className="h-8 bg-zinc-100 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800 flex items-center px-4 shrink-0 justify-between">
                        <span className="text-xs font-mono text-zinc-500">Preview</span>
                    </div>
                    <div className="flex-1 w-full h-full p-0">
                        {/* 
              Using an iframe pointing directly to the PDF is the most reliable and performant 
              way to render PDFs in modern browsers without needing heavy WASM libraries like react-pdf 
            */}
                        <iframe
                            ref={iframeRef}
                            src={`${pdfUrl}#toolbar=0&navpanes=0&scrollbar=1&view=FitH`}
                            className="w-full h-full border-none"
                            title="Resume PDF Preview"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
