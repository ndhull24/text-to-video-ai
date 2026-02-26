export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type Project = { id: number; title: string };

export type ProjectStatus = {
  project_id: number;
  scenes: number;
  shots_total: number;
  shots_by_status: Record<string, number>;
  done_pct: number;
};

async function http<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const msg = await res.text().catch(() => "");
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function createProject(title: string): Promise<Project> {
  return http<Project>(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function uploadChapter(projectId: number, text: string) {
  return http<{ ok: true }>(`${API_BASE}/projects/${projectId}/chapter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export async function planProject(projectId: number, body?: { target_minutes?: number, style?: string, max_scenes?: number }) {
  return http<{ ok: true; scenes: number }>(`${API_BASE}/projects/${projectId}/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}

export async function generateProject(projectId: number) {
  return http<{ ok: true; enqueued_shots: number; ran_inline: number }>(
    `${API_BASE}/projects/${projectId}/generate`,
    { method: "POST" }
  );
}

export async function projectStatus(projectId: number) {
  return http<ProjectStatus>(`${API_BASE}/projects/${projectId}/status`);
}

export async function createAudio(projectId: number, rate: number) {
  return http<{ ok: true }>(`${API_BASE}/projects/${projectId}/audio?rate=${rate}`, {
    method: "POST",
  });
}

export async function renderVideo(projectId: number) {
  return http<{ ok: true; output_path: string }>(`${API_BASE}/projects/${projectId}/render`, {
    method: "POST",
  });
}

export function projectVideoUrl(projectId: number, cacheBust?: number) {
  const base = `${API_BASE}/projects/${projectId}/video`;
  return cacheBust ? `${base}?t=${cacheBust}` : base;
}

export function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}
