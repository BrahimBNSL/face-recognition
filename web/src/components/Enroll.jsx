import { useEffect, useRef, useState } from "react";
import { api, captureFrame } from "../api";
import { playDenied, playGranted } from "../sound";

const INTERVAL_MS = 600;
const STABLE = 5;
const BORDER = { ok: "#16a34a", warning: "#f59e0b", error: "#dc2626", idle: "#64748b" };
const PALETTE = {
  ok: "from-green-500 to-green-700",
  warning: "from-amber-400 to-amber-600",
  error: "from-red-500 to-red-700",
  idle: "from-slate-500 to-slate-700",
};

export default function Enroll() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const timerRef = useRef(null);
  const streamRef = useRef(null);
  const busyRef = useRef(false);
  const streakRef = useRef(0);
  const bestRef = useRef({ score: 0, blob: null });

  const [camera, setCamera] = useState("starting");
  const [status, setStatus] = useState({
    level: "idle",
    title: "CAMÉRA",
    message: "Autorisez la caméra et placez-vous face à l'objectif.",
    streak: 0,
  });
  const [preview, setPreview] = useState(null);
  const [lockedBlob, setLockedBlob] = useState(null);
  const [name, setName] = useState("");
  const [consent, setConsent] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const [people, setPeople] = useState([]);
  const [selected, setSelected] = useState("");
  const [saving, setSaving] = useState(false);

  async function loadPeople() {
    try {
      setPeople(await api.people());
    } catch {
      setPeople([]);
    }
  }

  useEffect(() => {
    loadPeople();
  }, []);

  useEffect(() => {
    let cancelled = false;
    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480 } })
      .then(async (stream) => {
        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }
        streamRef.current = stream;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCamera("on");
      })
      .catch(() => setCamera("error"));
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    if (camera !== "on" || lockedBlob) return undefined;
    timerRef.current = setInterval(tick, INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [camera, lockedBlob]);

  function drawOverlay(result) {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || !video.videoWidth) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const q = result.quality;
    const scaleX = canvas.width / result.width;
    const scaleY = canvas.height / result.height;
    const color = BORDER[q.level] || BORDER.idle;

    if (q.bbox) {
      const [x1, y1, x2, y2] = q.bbox;
      ctx.lineWidth = 4;
      ctx.strokeStyle = color;
      ctx.strokeRect(x1 * scaleX, y1 * scaleY, (x2 - x1) * scaleX, (y2 - y1) * scaleY);
    }

    ctx.font = "600 16px system-ui, sans-serif";
    const labelWidth = ctx.measureText(q.label).width;
    ctx.fillStyle = color;
    ctx.fillRect(10, 10, labelWidth + 20, 28);
    ctx.fillStyle = "#ffffff";
    ctx.fillText(q.label, 20, 30);
  }

  async function tick() {
    if (busyRef.current || !videoRef.current || !videoRef.current.videoWidth) return;
    busyRef.current = true;
    try {
      const blob = await captureFrame(videoRef.current);
      const result = await api.analyze(blob);
      drawOverlay(result);
      const q = result.quality;

      if (q.ok) {
        streakRef.current += 1;
        if (q.score > bestRef.current.score) {
          bestRef.current = { score: q.score, blob };
        }
      } else {
        streakRef.current = 0;
        bestRef.current = { score: 0, blob: null };
      }

      if (streakRef.current >= STABLE && bestRef.current.blob) {
        const chosen = bestRef.current.blob;
        setPreview(URL.createObjectURL(chosen));
        setLockedBlob(chosen);
        setStatus({
          level: "ok",
          title: "PHOTO RETENUE",
          message: "Capture réussie. Vous pouvez enregistrer la personne.",
          streak: STABLE,
        });
      } else {
        setStatus({
          level: q.level,
          title: q.label,
          message: q.message,
          streak: q.ok ? streakRef.current : 0,
        });
      }
    } catch (error) {
      setStatus({ level: "error", title: "SERVEUR", message: error.message, streak: 0 });
    } finally {
      busyRef.current = false;
    }
  }

  function resetCapture() {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    setLockedBlob(null);
    streakRef.current = 0;
    bestRef.current = { score: 0, blob: null };
    setStatus({
      level: "idle",
      title: "CAMÉRA",
      message: "Capture réinitialisée. Placez-vous face à l'objectif.",
      streak: 0,
    });
  }

  function onUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    setLockedBlob(file);
    setStatus({
      level: "ok",
      title: "IMAGE IMPORTÉE",
      message: "Image prête à être enregistrée.",
      streak: 0,
    });
  }

  async function enroll() {
    setFeedback(null);
    if (!name.trim()) {
      setFeedback({ ok: false, title: "Nom manquant", text: "Saisissez le nom de la personne." });
      playDenied();
      return;
    }
    if (!consent) {
      setFeedback({ ok: false, title: "Consentement requis", text: "Cochez la case avant d'enregistrer." });
      playDenied();
      return;
    }
    if (!lockedBlob) {
      setFeedback({ ok: false, title: "Aucune photo", text: "Capturez le visage ou importez une image." });
      playDenied();
      return;
    }

    setSaving(true);
    try {
      const data = await api.enroll({ name: name.trim(), consent: true, blob: lockedBlob });
      setFeedback({
        ok: true,
        title: `${data.name} enregistré(e)`,
        text: data.sufficient
          ? `Vecteurs dans la base : ${data.count}. Enregistrement suffisant.`
          : `Vecteurs dans la base : ${data.count}. Minimum conseillé : ${data.minimum}.`,
      });
      playGranted();
      resetCapture();
      await loadPeople();
    } catch (error) {
      setFeedback({ ok: false, title: "Enregistrement refusé", text: error.message });
      playDenied();
    } finally {
      setSaving(false);
    }
  }

  async function removeSelected() {
    if (!selected) return;
    if (!window.confirm(`Supprimer définitivement ${selected} et toutes ses données ?`)) return;
    try {
      await api.removePerson(selected);
      setSelected("");
      await loadPeople();
      setFeedback({ ok: true, title: "Supprimé", text: "Toutes les données ont été effacées." });
    } catch (error) {
      setFeedback({ ok: false, title: "Suppression impossible", text: error.message });
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-3">
        <div className="card">
          <h3 className="mb-3 text-base font-semibold text-slate-800">Capture guidée</h3>
          <div className="relative overflow-hidden rounded-xl bg-slate-900">
            <video ref={videoRef} className="hidden" muted playsInline />
            {preview ? (
              <img src={preview} alt="Photo retenue" className="block w-full" />
            ) : (
              <canvas ref={canvasRef} className="block w-full" />
            )}
            {camera === "starting" && (
              <div className="absolute inset-0 flex items-center justify-center text-sm text-white/70">
                Initialisation de la caméra…
              </div>
            )}
            {camera === "error" && (
              <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-white/80">
                Caméra inaccessible. Autorisez-la dans le navigateur, ou importez une photo ci-dessous.
              </div>
            )}
          </div>
          <div className="mt-3 flex flex-wrap gap-3">
            <button className="btn-secondary" onClick={resetCapture}>
              Recommencer la capture
            </button>
            <label className="btn-secondary cursor-pointer">
              Importer une photo
              <input type="file" accept="image/*" className="hidden" onChange={onUpload} />
            </label>
          </div>
        </div>

        <div className={`rounded-2xl bg-gradient-to-br p-5 text-white shadow ${PALETTE[status.level] || PALETTE.idle}`}>
          <div className="text-xs font-bold uppercase tracking-widest opacity-90">{status.title}</div>
          <div className="mt-2 text-lg font-semibold">{status.message}</div>
          {!preview && (
            <div className="mt-3">
              <div className="h-2 overflow-hidden rounded-full bg-white/30">
                <div
                  className="h-full bg-white transition-all"
                  style={{ width: `${(Math.min(status.streak, STABLE) / STABLE) * 100}%` }}
                />
              </div>
              <div className="mt-1 text-xs opacity-90">
                Stabilité {Math.min(status.streak, STABLE)}/{STABLE}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4 lg:col-span-2">
        <div className="card space-y-4">
          <h3 className="text-base font-semibold text-slate-800">Nouvelle personne</h3>
          <div>
            <label className="label" htmlFor="name">Nom</label>
            <input
              id="name"
              className="input"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={64}
              placeholder="Prénom Nom"
            />
          </div>
          <label className="flex items-start gap-3 text-sm text-slate-600">
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 accent-teal-600"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            <span>La personne a consenti à cet enregistrement biométrique.</span>
          </label>
          <button className="btn-primary w-full" onClick={enroll} disabled={saving || !lockedBlob}>
            {saving ? "Enregistrement…" : "Enregistrer la photo"}
          </button>
          {feedback && (
            <div
              className={`rounded-xl border p-3 text-sm ${
                feedback.ok ? "border-green-200 bg-green-50 text-green-800" : "border-red-200 bg-red-50 text-red-800"
              }`}
            >
              <div className="font-semibold">{feedback.title}</div>
              <div>{feedback.text}</div>
            </div>
          )}
        </div>

        <div className="card space-y-4">
          <h3 className="text-base font-semibold text-slate-800">Base de connaissance</h3>
          {people.length === 0 ? (
            <p className="text-sm text-slate-500">La base est vide.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="py-2">Personne</th>
                  <th className="py-2">Vecteurs</th>
                </tr>
              </thead>
              <tbody>
                {people.map((person) => (
                  <tr key={person.name} className="border-b border-slate-100">
                    <td className="py-2 font-medium text-slate-800">{person.name}</td>
                    <td className="py-2 text-slate-600">{person.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="flex gap-2">
            <select className="input" value={selected} onChange={(event) => setSelected(event.target.value)}>
              <option value="">Choisir une personne</option>
              {people.map((person) => (
                <option key={person.name} value={person.name}>
                  {person.name}
                </option>
              ))}
            </select>
            <button className="btn-danger" onClick={removeSelected} disabled={!selected}>
              Supprimer
            </button>
          </div>
          <button className="btn-secondary w-full" onClick={loadPeople}>
            Actualiser la liste
          </button>
        </div>
      </div>
    </div>
  );
}