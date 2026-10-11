import { useEffect, useRef, useState } from "react";
import { api, captureFrame } from "../api";
import { playDenied, playGranted } from "../sound";

const INTERVAL_MS = 500;
const WINDOW = 5;
const REQUIRED = 3;
const CAPTURE_WIDTH = 480;
const COLORS = {
  green: "#16a34a",
  red: "#dc2626",
  yellow: "#eab308",
  orange: "#f59e0b",
  grey: "#64748b",
};

function decide(history) {
  const counts = {};
  history.forEach((name) => {
    counts[name] = (counts[name] || 0) + 1;
  });
  const [top, count] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0] || [];
  return count >= REQUIRED ? top : null;
}

function drawBox(ctx, [x1, y1, x2, y2], color, label) {
  ctx.lineWidth = 4;
  ctx.strokeStyle = color;
  ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  ctx.font = "600 16px system-ui, sans-serif";
  const textWidth = ctx.measureText(label).width;
  const top = Math.max(0, y1 - 28);
  ctx.fillStyle = color;
  ctx.fillRect(x1, top, textWidth + 16, 26);
  ctx.fillStyle = "#ffffff";
  ctx.fillText(label, x1 + 8, top + 18);
}

export default function RealTime() {
  const videoRef = useRef(null);
  const overlayRef = useRef(null);
  const historyRef = useRef([]);
  const busyRef = useRef(false);
  const lastDecisionRef = useRef(null);
  const [status, setStatus] = useState({ kind: "idle", title: "Caméra", message: "Autorisez la caméra." });
  const [camera, setCamera] = useState(false);

  useEffect(() => {
    let stream;
    let timer;
    let cancelled = false;

    async function tick() {
      if (busyRef.current || !videoRef.current || !videoRef.current.videoWidth) return;
      busyRef.current = true;
      try {
        const blob = await captureFrame(videoRef.current, CAPTURE_WIDTH);
        const result = await api.analyze(blob);
        draw(result);
      } catch (error) {
        setStatus({ kind: "err", title: "SERVEUR", message: error.message });
      } finally {
        busyRef.current = false;
      }
    }

    function draw(result) {
      const overlay = overlayRef.current;
      if (!overlay) return;
      overlay.width = result.width;
      overlay.height = result.height;
      const ctx = overlay.getContext("2d");
      ctx.clearRect(0, 0, overlay.width, overlay.height);

      if (result.faces.length === 0) {
        historyRef.current = [];
        lastDecisionRef.current = null;
        setStatus({ kind: "idle", title: "AUCUN VISAGE", message: "Placez votre visage dans le champ de la caméra." });
        return;
      }

      if (result.faces.length > 1) {
        historyRef.current = [];
        result.faces.forEach((face) => drawBox(ctx, face.bbox, COLORS.orange, "VISAGE"));
        setStatus({ kind: "warn", title: "PLUSIEURS VISAGES", message: "Une seule personne doit être visible." });
        return;
      }

      const face = result.faces[0];
      const size = Math.min(face.bbox[2] - face.bbox[0], face.bbox[3] - face.bbox[1]);

      if (size < result.quality.min_face_px) {
        historyRef.current = [];
        drawBox(ctx, face.bbox, COLORS.grey, "TROP LOIN");
        setStatus({ kind: "warn", title: "TROP LOIN", message: "Rapprochez-vous de la caméra." });
        return;
      }

      if (!result.identity || result.identity.error) {
        historyRef.current = [];
        drawBox(ctx, face.bbox, COLORS.grey, "SEUIL ?");
        setStatus({ kind: "err", title: "CONFIGURATION", message: result.identity?.error || "Identité indisponible." });
        return;
      }

      const name = result.identity.recognized ? result.identity.name : "__inconnu__";
      historyRef.current = [...historyRef.current, name].slice(-WINDOW);
      const decided = decide(historyRef.current);
      const score = result.identity.score?.toFixed(2) ?? "";

      if (decided === null) {
        drawBox(ctx, face.bbox, COLORS.yellow, "ANALYSE");
        setStatus({
          kind: "analyse",
          title: "ANALYSE EN COURS",
          message: `Confirmation de l'identité : ${historyRef.current.length}/${REQUIRED} images.`,
        });
      } else if (decided === "__inconnu__") {
        if (lastDecisionRef.current !== "__inconnu__") {
          playDenied();
          lastDecisionRef.current = "__inconnu__";
        }
        drawBox(ctx, face.bbox, COLORS.red, "INCONNU");
        setStatus({ kind: "err", title: "NON RECONNU", message: "Cette personne n'est pas dans la base." });
      } else {
        if (lastDecisionRef.current !== decided) {
          playGranted();
          lastDecisionRef.current = decided;
        }
        drawBox(ctx, face.bbox, COLORS.green, `${decided}  ${score}`);
        setStatus({ kind: "ok", title: "RECONNU", message: `Bienvenue, ${decided}.` });
      }
    }

    navigator.mediaDevices
      .getUserMedia({ video: { width: 640, height: 480 } })
      .then(async (media) => {
        if (cancelled) {
          media.getTracks().forEach((track) => track.stop());
          return;
        }
        stream = media;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCamera(true);
        timer = setInterval(tick, INTERVAL_MS);
      })
      .catch(() => {
        setStatus({ kind: "err", title: "CAMÉRA", message: "Caméra inaccessible. Vérifiez l'autorisation du navigateur." });
      });

    return () => {
      cancelled = true;
      clearInterval(timer);
      if (stream) stream.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const palette = {
    ok: "from-green-500 to-green-700",
    warn: "from-amber-400 to-amber-600",
    err: "from-red-500 to-red-700",
    analyse: "from-yellow-400 to-yellow-600",
    idle: "from-slate-500 to-slate-700",
  };

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="card lg:col-span-3">
        <h3 className="mb-3 text-base font-semibold text-slate-800">Reconnaissance en direct</h3>
        <div className="relative overflow-hidden rounded-xl bg-slate-900">
          <video ref={videoRef} className="block w-full" muted playsInline />
          <canvas ref={overlayRef} className="pointer-events-none absolute inset-0 h-full w-full" />
          {!camera && (
            <div className="absolute inset-0 flex items-center justify-center text-sm text-white/70">
              Initialisation de la caméra…
            </div>
          )}
        </div>
      </div>

      <div className="space-y-4 lg:col-span-2">
        <div className={`rounded-2xl bg-gradient-to-br p-5 text-white shadow ${palette[status.kind]}`}>
          <div className="text-xs font-bold uppercase tracking-widest opacity-90">{status.title}</div>
          <div className="mt-2 text-lg font-semibold">{status.message}</div>
        </div>
        <div className="card text-sm text-slate-600">
          Le cadre est <b className="text-green-700">vert</b> avec le nom si la personne est reconnue,{" "}
          <b className="text-red-700">rouge « INCONNU »</b> sinon. La décision est confirmée sur 3 images
          identiques parmi les 5 dernières.
        </div>
      </div>
    </div>
  );
}