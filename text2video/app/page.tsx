"use client";

import { useEffect, useMemo, useState } from "react";

type Voice = { id: string; label: string };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export default function Home() {
  const [projectId, setProjectId] = useState<number>(1);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [voiceId, setVoiceId] = useState<string>("default");
  const [text, setText] = useState<string>(
    "Welcome to Text2Video. This is a quick narration test."
  );

  const [status, setStatus] = useState<string>("");
  const [videoUrl, setVideoUrl] = useState<string>("");

  const videoSrc = useMemo(() => {
    if (!projectId) return "";
    // Always stream from backend endpoint (never local file paths)
    return `${API_BASE}/studio/video/${projectId}?t=${Date.now()}`;
  }, [projectId]);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/studio/voices`);
        if (!res.ok) throw new Error(await res.text());
        const data = (await res.json()) as Voice[];
        setVoices(data);
        if (data.length && !data.find(v => v.id === voiceId)) {
          setVoiceId(data[0].id);
        }
      } catch (e: any) {
        setStatus(`Failed to load voices: ${e?.message ?? e}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function generateNarration() {
    setStatus("Generating narration...");
    try {
      const res = await fetch(`${API_BASE}/studio/narrate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, text, voice_id: voiceId }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Narration created (narration.wav).");
    } catch (e: any) {
      setStatus(`Narration failed: ${e?.message ?? e}`);
    }
  }

  async function renderVideo() {
    setStatus("Rendering video...");
    try {
      // IMPORTANT:
      // Replace this URL with YOUR existing render endpoint.
      // Examples (pick the one your backend has):
      //  - POST `${API_BASE}/projects/${projectId}/render`
      //  - POST `${API_BASE}/projects/render?project_id=${projectId}`
      //
      const res = await fetch(`${API_BASE}/projects/${projectId}/render`, {
        method: "POST",
      });

      if (!res.ok) throw new Error(await res.text());

      // After render, refresh player by updating state with cache-busted URL
      setVideoUrl(`${videoSrc}&r=${Date.now()}`);
      setStatus("Render complete. Video updated.");
    } catch (e: any) {
      setStatus(`Render failed: ${e?.message ?? e}`);
    }
  }

  return (
    <main style={{ maxWidth: 980, margin: "0 auto", padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 28, fontWeight: 700 }}>Text2Video Studio</h1>
      <p style={{ opacity: 0.8, marginTop: 6 }}>
        Paste text, choose voice, generate narration, then render. The player always loads from backend.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 18 }}>
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
          <label style={{ display: "block", fontWeight: 600 }}>Project ID</label>
          <input
            type="number"
            value={projectId}
            onChange={(e) => setProjectId(parseInt(e.target.value || "1", 10))}
            style={{ width: "100%", marginTop: 8, padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
          />

          <label style={{ display: "block", fontWeight: 600, marginTop: 14 }}>Voice</label>
          <select
            value={voiceId}
            onChange={(e) => setVoiceId(e.target.value)}
            style={{ width: "100%", marginTop: 8, padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
          >
            {voices.map((v) => (
              <option key={v.id} value={v.id}>{v.label}</option>
            ))}
          </select>

          <label style={{ display: "block", fontWeight: 600, marginTop: 14 }}>Script</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={10}
            style={{ width: "100%", marginTop: 8, padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
          />

          <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
            <button
              onClick={generateNarration}
              style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #333", background: "#fff", cursor: "pointer" }}
            >
              Generate Narration
            </button>
            <button
              onClick={renderVideo}
              style={{ padding: "10px 12px", borderRadius: 10, border: "1px solid #333", background: "#111", color: "#fff", cursor: "pointer" }}
            >
              Render Video
            </button>
          </div>

          <div style={{ marginTop: 12, fontSize: 13, opacity: 0.85, whiteSpace: "pre-wrap" }}>
            {status}
          </div>
        </div>

        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>Preview</h2>
            <a
              href={`${API_BASE}/studio/video/${projectId}`}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: 13 }}
            >
              Download / open video
            </a>
          </div>

          <div style={{ marginTop: 10 }}>
            <video
              key={videoUrl || videoSrc}
              controls
              style={{ width: "100%", borderRadius: 12, background: "#000" }}
              src={videoUrl || videoSrc}
            />
          </div>

          <p style={{ fontSize: 13, opacity: 0.75, marginTop: 10 }}>
            Video URL: <code>{videoUrl || videoSrc}</code>
          </p>
        </div>
      </div>
    </main>
  );
}
