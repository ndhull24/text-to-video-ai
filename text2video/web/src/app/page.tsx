"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  API_BASE,
  createAudio,
  createProject,
  generateProject,
  planProject,
  projectStatus,
  projectVideoUrl,
  renderVideo,
  sleep,
  uploadChapter,
  type ProjectStatus,
} from "@/lib/api";

type StepKey = "create" | "chapter" | "plan" | "generate" | "audio" | "render";
type StepState = "idle" | "running" | "done" | "error";

type Step = {
  key: StepKey;
  title: string;
  desc: string;
};

const STEPS: Step[] = [
  { key: "create", title: "Create project", desc: "Initialize a new video namespace." },
  { key: "chapter", title: "Upload chapter", desc: "Process your NLP script text." },
  { key: "plan", title: "Plan scenes", desc: "Intelligently sequence visual shots." },
  { key: "generate", title: "Generate visuals", desc: "Leverage AI models for cinematic processing." },
  { key: "audio", title: "Create narration", desc: "Synthesize crisp voiceovers." },
  { key: "render", title: "Render final video", desc: "Compile sequences into a polished MP4." },
];

function badgeClasses(state: StepState) {
  if (state === "done") return "bg-emerald-500/10 text-emerald-400 ring-1 ring-emerald-500/50 shadow-[0_0_10px_rgba(52,211,153,0.2)]";
  if (state === "running") return "bg-blue-500/10 text-blue-400 ring-1 ring-blue-500/50 shadow-[0_0_10px_rgba(59,130,246,0.3)] animate-pulse";
  if (state === "error") return "bg-rose-500/10 text-rose-400 ring-1 ring-rose-500/50 shadow-[0_0_10px_rgba(244,63,94,0.2)]";
  return "bg-slate-800/50 text-slate-400 ring-1 ring-slate-700/50";
}

function prettyState(state: StepState) {
  if (state === "idle") return "Idle";
  if (state === "running") return "Running";
  if (state === "done") return "Done";
  return "Error";
}

function clamp(n: number, a = 0, b = 100) {
  return Math.max(a, Math.min(b, n));
}

export default function Page() {
  const [title, setTitle] = useState("Introduction to NLP");
  const [projectId, setProjectId] = useState<number>(1);
  const [loadId, setLoadId] = useState<string>("1");

  const [chapterText, setChapterText] = useState(
    "Natural Language Processing, or NLP, is the fascinating intersection of linguistics and artificial intelligence. It empowers machines to understand, interpret, and generate human language.\n\nImagine a world where your computer comprehends the nuance of sarcasm, or translates a poem while preserving its emotional weight. This is achieved through complex architectures like Transformers that map tokens to dense, high-dimensional embeddings.\n\nToday, we're exploring the core architectures that make this possible, diving deep into attention mechanisms. Welcome to the future of communication!"
  );

  const [rate, setRate] = useState<number>(175);
  const [targetMinutes, setTargetMinutes] = useState<number>(60);
  const [videoStyle, setVideoStyle] = useState<string>("cinematic_nlp");

  const [stepState, setStepState] = useState<Record<StepKey, StepState>>({
    create: "idle", chapter: "idle", plan: "idle", generate: "idle", audio: "idle", render: "idle",
  });

  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string>("");
  const [status, setStatus] = useState<ProjectStatus | null>(null);
  const [cacheBust, setCacheBust] = useState(0);
  const [activeStep, setActiveStep] = useState<StepKey>("chapter");

  const pollRef = useRef<{ stop: boolean }>({ stop: false });
  const videoUrl = useMemo(() => projectVideoUrl(projectId, cacheBust), [projectId, cacheBust]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const s = await projectStatus(projectId);
        if (alive) setStatus(s ?? null);
      } catch {
        if (alive) setStatus(null);
      }
    })();
    return () => { alive = false; };
  }, [projectId]);

  useEffect(() => {
    return () => { pollRef.current.stop = true; };
  }, []);

  function setStep(key: StepKey, state: StepState) { setStepState((prev) => ({ ...prev, [key]: state })); }

  function resetLaterSteps(fromKey: StepKey) {
    const keys: StepKey[] = ["create", "chapter", "plan", "generate", "audio", "render"];
    const idx = keys.indexOf(fromKey);
    setStepState((prev) => {
      const next = { ...prev };
      for (let i = idx + 1; i < keys.length; i++) next[keys[i]] = "idle";
      return next;
    });
  }

  function canRun(key: StepKey) {
    if (busy) return false;
    if (key === "create") return true;
    if (!projectId || projectId < 1) return false;
    if (key === "chapter") return true;
    if (key === "plan") return stepState.chapter === "done";
    if (key === "generate") return stepState.plan === "done";
    if (key === "audio") return stepState.generate === "done";
    if (key === "render") return stepState.audio === "done";
    return false;
  }

  function completedCount() {
    const order: StepKey[] = ["create", "chapter", "plan", "generate", "audio", "render"];
    return order.reduce((acc, k) => acc + (stepState[k] === "done" ? 1 : 0), 0);
  }

  function overallProgressPct(generatePct?: number) {
    const order: StepKey[] = ["create", "chapter", "plan", "generate", "audio", "render"];
    const total = order.length;
    const genIndex = order.indexOf("generate");
    const done = completedCount();

    if (stepState.generate === "running" && typeof generatePct === "number") {
      const doneBeforeGenerate = order
        .slice(0, genIndex)
        .reduce((acc, k) => acc + (stepState[k] === "done" ? 1 : 0), 0);
      const partial = doneBeforeGenerate + clamp(generatePct, 0, 100) / 100;
      return clamp((partial / total) * 100, 0, 99.9);
    }
    return clamp((done / total) * 100, 0, 100);
  }

  async function runCreate() {
    setBusy(true); setMessage(""); setStep("create", "running");
    try {
      const p = await createProject(title.trim() || "Untitled");
      setProjectId(p.id); setLoadId(String(p.id));
      setStep("create", "done"); setActiveStep("chapter");
      setMessage(`✅ Created project ${p.id}`); resetLaterSteps("create");
    } catch (e: any) {
      setStep("create", "error"); setMessage(`❌ Create failed: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  }

  async function runChapter() {
    setBusy(true); setMessage(""); setStep("chapter", "running");
    try {
      await uploadChapter(projectId, chapterText);
      setStep("chapter", "done"); setActiveStep("plan");
      setMessage("✅ Script uploaded successfully"); resetLaterSteps("chapter");
    } catch (e: any) {
      setStep("chapter", "error"); setMessage(`❌ Upload failed: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  }

  async function runPlan() {
    setBusy(true); setMessage(""); setStep("plan", "running");
    try {
      const out = await planProject(projectId, { target_minutes: targetMinutes, style: videoStyle });
      setStep("plan", "done"); setActiveStep("generate");
      setMessage(`✅ Planned ${out.scenes} cinematic scenes`); resetLaterSteps("plan");
    } catch (e: any) {
      setStep("plan", "error"); setMessage(`❌ Plan failed: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  }

  async function pollUntilShotsDone(timeoutMs = 12 * 60 * 1000) {
    const start = Date.now(); pollRef.current.stop = false;
    while (true) {
      if (pollRef.current.stop) return;
      const s = await projectStatus(projectId); setStatus(s);
      const by = s.shots_by_status || {};
      const pending = Number(by.PENDING ?? 0);
      const running = Number(by.RUNNING ?? 0);
      if (pending === 0 && running === 0) return;
      if (Date.now() - start > timeoutMs) throw new Error("Timed out waiting for visuals.");
      await sleep(2500);
    }
  }

  async function runGenerate() {
    setBusy(true); setMessage(""); setStep("generate", "running");
    try {
      await generateProject(projectId);
      setMessage("⏳ Generating visuals... checking progress");
      await pollUntilShotsDone();
      setStep("generate", "done"); setActiveStep("audio");
      setMessage("✅ All visuals generated"); resetLaterSteps("generate");
    } catch (e: any) {
      setStep("generate", "error"); setMessage(`❌ Generation failed: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  }

  async function runAudio() {
    setBusy(true); setMessage(""); setStep("audio", "running");
    try {
      await createAudio(projectId, rate);
      setStep("audio", "done"); setActiveStep("render");
      setMessage("✅ Narration synthesized"); resetLaterSteps("audio");
    } catch (e: any) {
      setStep("audio", "error"); setMessage(`❌ Audio failed: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  }

  async function runRender() {
    setBusy(true); setMessage(""); setStep("render", "running");
    try {
      await renderVideo(projectId);
      setStep("render", "done"); setCacheBust(Date.now());
      setMessage("✅ Final assembly complete — video updated");
    } catch (e: any) {
      setStep("render", "error"); setMessage(`❌ Render failed: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  }

  async function runAll() {
    setBusy(true); setMessage(""); pollRef.current.stop = false;
    try {
      if (stepState.chapter !== "done") {
        setStep("chapter", "running"); await uploadChapter(projectId, chapterText); setStep("chapter", "done");
      }
      if (stepState.plan !== "done") {
        setStep("plan", "running"); await planProject(projectId, { target_minutes: targetMinutes, style: videoStyle }); setStep("plan", "done");
      }
      if (stepState.generate !== "done") {
        setStep("generate", "running"); await generateProject(projectId); await pollUntilShotsDone(); setStep("generate", "done");
      }
      if (stepState.audio !== "done") {
        setStep("audio", "running"); await createAudio(projectId, rate); setStep("audio", "done");
      }
      if (stepState.render !== "done") {
        setStep("render", "running"); await renderVideo(projectId); setStep("render", "done"); setCacheBust(Date.now());
      }
      setActiveStep("render"); setMessage("✅ Full pipeline complete. Video is ready.");
    } catch (e: any) {
      setMessage(`❌ Pipeline halted: ${e?.message ?? e}`);
    } finally { setBusy(false); }
  }

  const handleLoadProject = () => {
    const v = parseInt(loadId, 10);
    if (!Number.isFinite(v) || v < 1) return;
    setProjectId(v);
    setStepState({ create: "done", chapter: "done", plan: "done", generate: "done", audio: "done", render: "done" });
    setCacheBust(Date.now());
    setMessage(`✅ Loaded existing project ID ${v}`);
  };

  const generatePct = status?.done_pct ?? 0;
  const overallPct = overallProgressPct(stepState.generate === "running" ? generatePct : undefined);
  const by = status?.shots_by_status ?? {};
  const shotsLine = status
    ? `${status.shots_total} chunks • ${by.SUCCEEDED ?? 0} ok • ${by.FAILED ?? 0} failed • ${by.PENDING ?? 0} pending • ${by.RUNNING ?? 0} running`
    : "No network data yet";

  return (
    <main className="relative min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-blue-500/30 overflow-x-hidden">
      {/* Background aesthetics */}
      <div className="absolute inset-0 z-0 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(56,189,248,0.15),rgba(255,255,255,0))] mix-blend-screen pointer-events-none" />
      <div className="absolute top-1/3 -left-40 w-96 h-96 bg-blue-600/20 blur-[120px] rounded-full pointer-events-none" />
      <div className="absolute bottom-1/3 -right-40 w-96 h-96 bg-emerald-600/10 blur-[120px] rounded-full pointer-events-none" />

      <div className="relative z-10 mx-auto max-w-7xl px-5 py-12">
        {/* Header Section */}
        <header className="flex flex-col gap-6 md:flex-row md:items-end justify-between backdrop-blur-sm bg-white/[0.02] border border-white/5 rounded-3xl p-8 shadow-2xl">
          <div className="flex-1">
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-900/80 px-4 py-1.5 text-xs text-blue-300 ring-1 ring-blue-500/30 shadow-[0_0_15px_rgba(59,130,246,0.15)]">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
              Nexus API Cluster • <span className="font-mono text-blue-200">{API_BASE}</span>
            </div>
            <h1 className="mt-5 text-4xl md:text-5xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-br from-white via-slate-200 to-slate-500">
              Antigravity Studio
            </h1>
            <p className="mt-2 max-w-2xl text-base text-slate-400 font-light">
              Transform robust educational scripts into context-aware, highly cinematic visualizations harnessing AI.
            </p>
          </div>

          <div className="w-full max-w-md bg-slate-900/50 p-5 rounded-2xl border border-white/5 shadow-inner">
            <div className="flex items-center justify-between text-sm font-medium text-slate-200">
              <span>Pipeline Progress</span>
              <span className="font-mono text-blue-400">{overallPct.toFixed(0)}%</span>
            </div>
            <div className="mt-3 h-3 w-full overflow-hidden rounded-full bg-black/50 ring-1 ring-white/10 shadow-inner">
              <div
                className="h-full rounded-full bg-gradient-to-r from-blue-500 via-indigo-400 to-emerald-400 transition-all duration-700 ease-out shadow-[0_0_10px_rgba(59,130,246,0.8)]"
                style={{ width: `${overallPct}%` }}
              />
            </div>
            <div className="mt-3 text-xs text-slate-500 font-medium tracking-wide string">{shotsLine}</div>
          </div>
        </header>

        {/* Top Navbar / Loader */}
        <div className="mt-6 flex flex-col md:flex-row items-center justify-between gap-4 backdrop-blur-md bg-white/[0.03] border border-white/5 rounded-2xl p-4 px-6">
          <div className="text-sm text-slate-400">
            Currently working on Project Space <span className="text-blue-400 font-mono bg-blue-500/10 px-2 py-0.5 rounded-md">#{projectId}</span>
          </div>
          <div className="flex items-center gap-3 w-full md:w-auto">
            <input
              className="w-full md:w-40 rounded-xl border border-white/10 bg-slate-900/80 px-4 py-2 text-sm outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all placeholder:text-slate-600"
              type="number" min={1}
              placeholder="Load ID..."
              value={loadId}
              onChange={(e) => setLoadId(e.target.value)}
            />
            <button
              onClick={handleLoadProject}
              className="shrink-0 rounded-xl bg-slate-800 px-4 py-2 text-sm font-medium hover:bg-slate-700 hover:text-white transition-colors border border-white/5 active:scale-95 shadow-sm"
            >
              Load Project
            </button>
          </div>
        </div>

        {/* Main Grid */}
        <div className="mt-6 grid gap-6 lg:grid-cols-[460px_1fr]">

          {/* Controls Section */}
          <section className="flex flex-col gap-6">
            <div className="rounded-3xl bg-white/[0.02] p-6 lg:p-8 border border-white/5 shadow-2xl backdrop-blur-xl">
              <h2 className="text-lg font-semibold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">Project Parameters</h2>

              <div className="mt-5 space-y-4">
                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5 block">Project Title</label>
                  <input
                    className="w-full rounded-xl border border-slate-700/50 bg-slate-900/50 px-4 py-2.5 text-sm outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all shadow-inner"
                    value={title} onChange={(e) => setTitle(e.target.value)}
                    placeholder="E.g. The Architecture of GPT"
                  />
                </div>

                <div>
                  <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5 block">Educational Script (NLP)</label>
                  <textarea
                    className="h-40 w-full resize-none rounded-xl border border-slate-700/50 bg-slate-900/50 px-4 py-3 text-sm outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all shadow-inner leading-relaxed"
                    value={chapterText}
                    onChange={(e) => {
                      setChapterText(e.target.value);
                      if (stepState.chapter === "done") {
                        setStep("chapter", "idle"); setStep("plan", "idle"); setStep("generate", "idle"); setStep("audio", "idle"); setStep("render", "idle");
                      }
                    }}
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5 block">Duration (min)</label>
                    <input
                      className="w-full rounded-xl border border-slate-700/50 bg-slate-900/50 px-4 py-2.5 text-sm outline-none focus:border-blue-500/50 transition-all shadow-inner"
                      type="number" value={targetMinutes} onChange={(e) => setTargetMinutes(parseInt(e.target.value || "60", 10))}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5 block">Video Style</label>
                    <select
                      className="w-full rounded-xl border border-slate-700/50 bg-slate-900/50 px-4 py-2.5 text-sm outline-none focus:border-blue-500/50 transition-all shadow-inner cursor-pointer"
                      value={videoStyle} onChange={(e) => setVideoStyle(e.target.value)}
                    >
                      <option value="cinematic_nlp" className="bg-slate-900">Cinematic NLP (Realism)</option>
                      <option value="lecture" className="bg-slate-900">Lecture (Long Shots)</option>
                      <option value="cinematic" className="bg-slate-900">Cinematic (Fast Cuts)</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-[1fr_auto] gap-4 items-end pt-2">
                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 mb-1.5 block">Narration Rate</label>
                    <input
                      className="w-full rounded-xl border border-slate-700/50 bg-slate-900/50 px-4 py-2.5 text-sm outline-none focus:border-blue-500/50 transition-all shadow-inner"
                      type="number" value={rate} onChange={(e) => setRate(parseInt(e.target.value || "175", 10))}
                    />
                  </div>
                  <button
                    onClick={runAll} disabled={busy}
                    className="rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-2.5 text-sm font-semibold text-white shadow-[0_0_20px_rgba(79,70,229,0.4)] transition-all hover:shadow-[0_0_30px_rgba(79,70,229,0.6)] hover:scale-[1.02] active:scale-95 pos-relative overflow-hidden disabled:opacity-50 disabled:pointer-events-none group"
                  >
                    <span className="relative z-10 font-bold uppercase tracking-wider">Automate Sequence</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Individual Steps Grid */}
            <div className="rounded-3xl bg-white/[0.02] p-6 lg:p-8 border border-white/5 shadow-2xl backdrop-blur-xl">
              <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest mb-4">Manual Diagnostics</h2>
              <div className="grid grid-cols-3 gap-2">
                {STEPS.map((s, idx) => {
                  const fns = [runCreate, runChapter, runPlan, runGenerate, runAudio, runRender];
                  return (
                    <button key={s.key} onClick={fns[idx]} disabled={!canRun(s.key)}
                      className="rounded-xl bg-slate-800/50 px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-slate-300 ring-1 ring-white/5 transition-all hover:bg-slate-700 hover:text-white disabled:opacity-30 disabled:hover:bg-slate-800/50 active:scale-95"
                    >
                      {s.key}
                    </button>
                  );
                })}
              </div>

              <div className="mt-6 rounded-2xl bg-black/40 p-4 border border-black/50 shadow-inner">
                <div className="text-[10px] uppercase font-bold text-slate-500 tracking-widest">System Output Logs</div>
                <div className="mt-2 text-xs text-slate-300 font-mono h-12 overflow-y-auto leading-relaxed">{message || "Awaiting task dispatch..."}</div>
              </div>
            </div>
          </section>

          {/* Visualization Section */}
          <section className="flex flex-col gap-6">
            <div className="rounded-3xl bg-white/[0.02] p-6 lg:p-8 border border-white/5 shadow-2xl backdrop-blur-xl flex flex-col h-full">

              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
                <div>
                  <h2 className="text-xl font-bold text-white">Playback & Delivery</h2>
                  <p className="text-sm text-slate-400 mt-1">Rendered video is streamed directly from the Nexus core.</p>
                </div>
              </div>

              {/* The Player */}
              <div className="flex-1 rounded-2xl overflow-hidden bg-black/80 ring-1 ring-white/10 shadow-[0_20px_40px_rgba(0,0,0,0.5)] flex items-center justify-center relative group min-h-[300px]">
                <video
                  key={videoUrl}
                  controls
                  className="absolute inset-0 w-full h-full object-contain"
                  src={videoUrl}
                  poster="https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?q=80&w=1280&auto=format&fit=crop"
                />
              </div>

              {/* Actions & Insights */}
              <div className="mt-6 grid lg:grid-cols-2 gap-4">
                {/* Watch & Download Actions */}
                <div className="flex gap-3 h-full">
                  <a
                    href={`${API_BASE}/projects/${projectId}/video`}
                    target="_blank" rel="noreferrer"
                    className="flex-1 flex flex-col items-center justify-center gap-1 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 p-4 ring-1 ring-white/20 transition-all hover:scale-[1.02] hover:shadow-[0_0_25px_rgba(99,102,241,0.5)] active:scale-95 cursor-pointer text-center group"
                  >
                    <span className="text-sm font-bold text-white uppercase tracking-wider">Watch in Browser</span>
                  </a>

                  <a
                    href={`${API_BASE}/projects/${projectId}/video?download=true`}
                    download={`project_${projectId}.mp4`}
                    className="flex-1 flex flex-col items-center justify-center gap-1 rounded-2xl bg-white/[0.05] hover:bg-white/[0.1] p-4 ring-1 ring-white/20 transition-all hover:scale-[1.02] hover:shadow-[0_0_15px_rgba(255,255,255,0.1)] active:scale-95 cursor-pointer text-center group"
                  >
                    <span className="text-sm font-bold text-slate-300 uppercase tracking-wider group-hover:text-white transition-colors">Download MP4</span>
                  </a>
                </div>

                {/* Node States */}
                <div className="rounded-2xl bg-black/30 border border-white/5 p-4 flex flex-col justify-center">
                  <div className="text-[10px] uppercase font-bold text-slate-500 tracking-widest mb-1.5">Network Sequence</div>
                  <div className="flex flex-col gap-2 h-20 overflow-y-auto pr-2 custom-scrollbar">
                    {STEPS.map(s => {
                      if (stepState[s.key] !== "idle") {
                        return (
                          <div key={s.key} className="flex justify-between items-center bg-white/[0.03] px-3 py-1.5 rounded-lg">
                            <span className="text-xs text-slate-300 font-medium">{s.title}</span>
                            <span className={"text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md " + badgeClasses(stepState[s.key])}>
                              {stepState[s.key]}
                            </span>
                          </div>
                        );
                      }
                      return null;
                    })}
                    {stepState.create === "idle" && <div className="text-xs text-slate-500 italic mt-2 text-center">No active pipeline.</div>}
                  </div>
                </div>
              </div>

            </div>
          </section>

        </div>
      </div>
    </main>
  );
}
