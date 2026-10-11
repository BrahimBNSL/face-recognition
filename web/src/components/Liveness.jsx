import { useEffect, useRef, useState } from "react";
import { api, captureFrame } from "../api";
import { playLivenessPassed } from "../sound";

const INTERVAL_MS = 500;

const TONES = {
  idle: "border-slate-200 bg-slate-50 text-slate-700",
  starting: "border-slate-200 bg-slate-50 text-slate-700",
  running: "border-teal-200 bg-teal-50 text-teal-800",
  passed: "border-green-300 bg-green-50 text-green-800",
  expired: "border-amber-300 bg-amber-50 text-amber-800",
  error: "border-red-300 bg-red-50 text-red-800",
};

export default function Liveness({ onPassed }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const busyRef = useRef(false);
  const sessionRef = useRef(null);
  const onPassedRef = useRef(onPassed);
  const [phase, setPhase] = useState("idle");
  const [message, setMessage] = useState("Réalisez le défi pour prouver que vous êtes présent.");

  useEffect(() => {
    onPassedRef.current = onPassed;
  }, [onPassed]);

  function stopAll() {
    clearInterval(timerRef.current);
    timerRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }

  useEffect(() => stopAll, []);

  async function tick() {
    if (busyRef.current || !videoRef.current?.videoWidth) return;
    busyRef.current = true;
    try {
      const blob = await captureFrame(videoRef.current, 480);
      const data = await api.livenessFrame(sessionRef.current, blob);
      if (data.status === "passed") {
        stopAll();
        setPhase("passed");
        setMessage("Vérification de vivacité réussie.");
        playLivenessPassed();
        onPassedRef.current(sessionRef.current);
      } else if (data.status === "expired") {
        stopAll();
        setPhase("expired");
        setMessage(data.message);
      } else {
        setMessage(data.message);
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      busyRef.current = false;
    }
  }

  async function start() {
    stopAll();
    setPhase("starting");
    setMessage("Ouverture de la caméra…");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      const session = await api.livenessStart();
      sessionRef.current = session.session_id;
      setPhase("running");
      setMessage("Regardez la caméra, face à vous.");
      timerRef.current = setInterval(tick, INTERVAL_MS);
    } catch (error) {
      stopAll();
      setPhase("error");
      setMessage(error.message || "Caméra inaccessible.");
    }
  }

  const busy = phase === "starting" || phase === "running";

  return (
    <div className="card space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-slate-800">Vérification de vivacité</h3>
        {phase === "passed" && (
          <span className="rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-bold text-green-800">Validée</span>
        )}
      </div>

      <div className={`rounded-xl border p-3 text-sm ${TONES[phase]}`}>{message}</div>

      {phase !== "passed" && (
        <div className="relative overflow-hidden rounded-xl bg-slate-900">
          <video
            ref={videoRef}
            muted
            playsInline
            className={`block w-full ${phase === "running" ? "" : "opacity-40"}`}
          />
        </div>
      )}

      {phase !== "passed" && (
        <button className="btn-secondary w-full" onClick={start} disabled={busy}>
          {phase === "idle" ? "Démarrer le défi" : "Recommencer le défi"}
        </button>
      )}
    </div>
  );
}