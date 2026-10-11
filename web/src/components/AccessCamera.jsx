import { useEffect, useRef, useState } from "react";
import { captureFrame } from "../api";

export default function AccessCamera({ preview, onCapture, onReset }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [camera, setCamera] = useState("starting");

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
      streamRef.current = null;
    };
  }, []);

  async function snapshot() {
    try {
      onCapture(await captureFrame(videoRef.current, 640));
    } catch (error) {
      onCapture(null, error.message);
    }
  }

  return (
    <div className="card">
      <h3 className="mb-3 text-base font-semibold text-slate-800">Photo du visage</h3>
      <div className="relative flex min-h-[260px] items-center justify-center overflow-hidden rounded-xl bg-slate-900">
        <video ref={videoRef} muted playsInline className={`block w-full ${preview ? "hidden" : ""}`} />
        {preview && <img src={preview} alt="Photo à vérifier" className="max-h-[420px] w-full object-contain" />}
        {!preview && camera === "starting" && (
          <div className="absolute inset-0 flex items-center justify-center text-sm text-white/70">
            Initialisation de la caméra…
          </div>
        )}
        {!preview && camera === "error" && (
          <div className="absolute inset-0 flex items-center justify-center p-6 text-center text-sm text-white/80">
            Caméra inaccessible. Autorisez-la dans le navigateur, ou importez une photo.
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-3">
        {preview ? (
          <button className="btn-secondary" onClick={onReset}>
            Reprendre
          </button>
        ) : (
          <button className="btn-secondary" onClick={snapshot} disabled={camera !== "on"}>
            Capturer
          </button>
        )}
      </div>
    </div>
  );
}