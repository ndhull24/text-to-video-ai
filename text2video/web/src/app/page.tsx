"use client";

import { useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

type CreateProjectResp = { id: number; title?: string };

export default function Page() {
  const [title, setTitle] = useState("Local Studio Test");
  const [projectId, setProjectId] = useState<number>(1);

  const [chapterText, setChapterText] = useState(
    "This is a test script. Scene one introduces the idea. Scene two demonstrates it. Scene three ends with a call to action."
  );

  const [rate, setRate] = useState<number>(175);
  const [status, setStatus] = useState<string>("");

  // ✅ Fix: compute cache-bust only after client actions (avoid Date.now() during render)
  const [cacheBust, setCacheBust] = useState<number>(0);

  // ✅ Busy state to disable buttons while running
  const [busy, setBusy] = useState(false);

  const videoUrl = useMemo(() => {
    const base = `${API_BASE}/projects/${projectId}/video`;
    return cacheBust ? `${base}?t=${cacheBust}` : base;
  }, [projectId, cacheBust]);

  function sleep(ms: number) {
    return new Promise((r) => setTimeout(r, ms));
  }

  async function waitForShotsDone(timeoutMs = 10 * 60 * 1000) {
    const start = Date.now();
    while (true) {
      const res = await fetch(`${API_BASE}/projects/${projectId}/status`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      // expected shape: { shots_by_status: {PENDING, RUNNING, SUCCEEDED, FAILED}, done_pct }
      const by = data?.shots_by_status ?? {};
      const pending = Number(by.PENDING ?? 0);
      const running = Number(by.RUNNING ?? 0);

      setStatus(
        `Status: ${data?.done_pct ?? "?"}% | pending=${pending} running=${running} ` +
          `succeeded=${by.SUCCEEDED ?? 0} failed=${by.FAILED ?? 0}`
      );

      if (pending === 0 && running === 0) return data;

      if (Date.now() - start > timeoutMs) {
        throw new Error("Timed out waiting for shots to finish.");
      }
      await sleep(1500);
    }
  }

  async function createProject() {
    setStatus("Creating project...");
    try {
      const res = await fetch(`${API_BASE}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as CreateProjectResp;
      setProjectId(data.id);
      setStatus(`Project created. project_id = ${data.id}`);
    } catch (e: any) {
      setStatus(`Create project failed: ${e?.message ?? e}`);
    }
  }

  async function uploadChapter() {
    setStatus("Uploading chapter...");
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/chapter`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: chapterText }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Chapter uploaded.");
    } catch (e: any) {
      setStatus(`Chapter upload failed: ${e?.message ?? e}`);
    }
  }

  async function plan() {
    setStatus("Planning scenes...");
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/plan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });

      if (!res.ok) throw new Error(await res.text());
      setStatus("Plan complete.");
    } catch (e: any) {
      setStatus(`Plan failed: ${e?.message ?? e}`);
    }
  }

  async function generate() {
    setStatus("Generating shots... (this can take a bit)");
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10 * 60 * 1000); // 10 min

    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/generate`, {
        method: "POST",
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Generate complete.");
    } catch (e: any) {
      const msg =
        e?.name === "AbortError"
          ? "Generate timed out (client aborted). Backend may still be working—check /status."
          : (e?.message ?? String(e));
      setStatus(`Generate failed: ${msg}`);
    } finally {
      clearTimeout(timeout);
    }
  }

  async function audio() {
    setStatus("Generating audio...");
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/audio?rate=${rate}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Audio complete.");
    } catch (e: any) {
      setStatus(`Audio failed: ${e?.message ?? e}`);
    }
  }

  async function render() {
    setStatus("Rendering final video...");
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/render`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      setStatus("Render complete. Preview should update.");
      setCacheBust(Date.now()); // <-- refresh video src
    } catch (e: any) {
      setStatus(`Render failed: ${e?.message ?? e}`);
    }
  }

  async function checkStatus() {
    setStatus("Fetching status...");
    try {
      const res = await fetch(`${API_BASE}/projects/${projectId}/status`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setStatus(JSON.stringify(data, null, 2));
    } catch (e: any) {
      setStatus(`Status failed: ${e?.message ?? e}`);
    }
  }

  async function runAll() {
    setBusy(true);
    try {
      await uploadChapter();
      await plan();

      await generate();
      await waitForShotsDone();

      await audio();
      await render(); // render bumps cacheBust already
      setStatus("✅ All steps complete. Video updated.");
    } catch (e: any) {
      setStatus(`❌ Run All failed: ${e?.message ?? e}`);
    } finally {
      setBusy(false);
    }
  }

  async function createAndRunAll() {
    setBusy(true);
    try {
      await createProject();
      // tiny delay so state updates to new projectId before next calls
      await new Promise((r) => setTimeout(r, 100));
      await runAll();
    } catch (e: any) {
      setStatus(`❌ Create + Run All failed: ${e?.message ?? e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 24, fontFamily: "system-ui, sans-serif" }}>
      <h1 style={{ fontSize: 28, fontWeight: 800 }}>Text2Video — Local Studio</h1>
      <p style={{ opacity: 0.7 }}>
        Backend: <code>{API_BASE}</code>
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 16, marginTop: 16 }}>
        <section style={{ border: "1px solid #ddd", borderRadius: 14, padding: 16 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={{ fontWeight: 700 }}>Project Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                style={{ width: "100%", marginTop: 6, padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
              />
            </div>
            <div>
              <label style={{ fontWeight: 700 }}>Project ID</label>
              <input
                type="number"
                value={projectId}
                onChange={(e) => setProjectId(parseInt(e.target.value || "1", 10))}
                style={{ width: "100%", marginTop: 6, padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginTop: 12 }}>
            <button style={btnLight} onClick={createProject} disabled={busy}>
              1) Create
            </button>

            <button style={btnDark} onClick={createAndRunAll} disabled={busy}>
              Create + Run All
            </button>

            <button style={btnDark} onClick={runAll} disabled={busy}>
              Run All
            </button>

            <button style={btnLight} onClick={uploadChapter} disabled={busy}>
              2) Chapter
            </button>
            <button style={btnLight} onClick={plan} disabled={busy}>
              3) Plan
            </button>
            <button style={btnLight} onClick={generate} disabled={busy}>
              4) Generate
            </button>
            <button style={btnDark} onClick={audio} disabled={busy}>
              5) Audio
            </button>
            <button style={btnDark} onClick={render} disabled={busy}>
              6) Render
            </button>
            <button style={btnLight} onClick={checkStatus} disabled={busy}>
              Status
            </button>
          </div>

          <div style={{ marginTop: 12 }}>
            <label style={{ fontWeight: 700 }}>Rate</label>
            <input
              type="number"
              value={rate}
              onChange={(e) => setRate(parseInt(e.target.value || "175", 10))}
              style={{ width: "100%", marginTop: 6, padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
            />
          </div>

          <div style={{ marginTop: 12 }}>
            <label style={{ fontWeight: 700 }}>Chapter Text</label>
            <textarea
              value={chapterText}
              onChange={(e) => setChapterText(e.target.value)}
              rows={10}
              style={{ width: "100%", marginTop: 6, padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
            />
          </div>

          <pre style={{ marginTop: 12, fontSize: 12, whiteSpace: "pre-wrap", opacity: 0.85 }}>{status}</pre>
        </section>

        <section style={{ border: "1px solid #ddd", borderRadius: 14, padding: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>Preview</h2>
            <a href={`${API_BASE}/projects/${projectId}/video`} target="_blank" rel="noreferrer" style={{ fontSize: 13 }}>
              Open / Download
            </a>
          </div>

          <div style={{ marginTop: 10 }}>
            <video controls style={{ width: "100%", borderRadius: 12, background: "#000" }} src={videoUrl} />
          </div>

          <p style={{ fontSize: 12, opacity: 0.7, marginTop: 10 }}>
            <code>{videoUrl}</code>
          </p>
        </section>
      </div>
    </main>
  );
}

const btnLight: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #333",
  background: "#fff",
  cursor: "pointer",
};

const btnDark: React.CSSProperties = {
  padding: "10px 12px",
  borderRadius: 10,
  border: "1px solid #333",
  background: "#111",
  color: "#fff",
  cursor: "pointer",
};
