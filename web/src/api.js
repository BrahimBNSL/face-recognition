const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  if (!response.ok) {
    let detail = `Erreur ${response.status}`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      detail = detail;
    }
    throw new Error(detail);
  }
  return response.json();
}

function withFile(fields, file) {
  const form = new FormData();
  Object.entries(fields).forEach(([key, value]) => form.append(key, value ?? ""));
  form.append("file", file, "capture.jpg");
  return form;
}

export function captureFrame(video, maxWidth = 640) {
  return new Promise((resolve, reject) => {
    if (!video || !video.videoWidth) {
      reject(new Error("La caméra n'est pas prête."));
      return;
    }
    const scale = Math.min(1, maxWidth / video.videoWidth);
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Capture impossible."))),
      "image/jpeg",
      0.85,
    );
  });
}

export const api = {
  health: () => request("/api/health"),

  analyze: (blob) => request("/api/analyze", { method: "POST", body: withFile({}, blob) }),

  livenessStart: () => request("/api/liveness/start", { method: "POST" }),

  livenessFrame: (sessionId, blob) =>
    request("/api/liveness/frame", {
      method: "POST",
      body: withFile({ session_id: sessionId }, blob),
    }),

  enroll: ({ name, consent, blob, sessionId }) =>
    request("/api/enroll", {
      method: "POST",
      body: withFile({ name, consent: String(consent), session_id: sessionId }, blob),
    }),

  people: () => request("/api/people"),

  removePerson: (name) =>
    request(`/api/people/${encodeURIComponent(name)}`, { method: "DELETE" }),

  verify: ({ blob, target, sessionId }) =>
    request("/api/verify", {
      method: "POST",
      body: withFile({ target, session_id: sessionId }, blob),
    }),

  journal: () => request("/api/journal"),
};