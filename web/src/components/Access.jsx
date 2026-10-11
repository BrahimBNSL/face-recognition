import { useEffect, useState } from "react";
import { api } from "../api";
import AccessCamera from "./AccessCamera";
import AccessPanel from "./AccessPanel";

export default function Access() {
  const [preview, setPreview] = useState(null);
  const [blob, setBlob] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [journal, setJournal] = useState([]);

  async function loadJournal() {
    try {
      setJournal(await api.journal());
    } catch {
      setJournal([]);
    }
  }

  useEffect(() => {
    loadJournal();
  }, []);

  function setPhoto(file) {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(URL.createObjectURL(file));
    setBlob(file);
    setResult(null);
  }

  function reset() {
    if (preview) URL.revokeObjectURL(preview);
    setPreview(null);
    setBlob(null);
    setResult(null);
  }

  function onCapture(file, error) {
    if (error) {
      setResult({ error });
      return;
    }
    setPhoto(file);
  }

  function onUpload(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (file) setPhoto(file);
  }

  async function verify() {
    if (!blob) {
      setResult({ error: "Capturez ou importez une photo du visage." });
      return;
    }
    setBusy(true);
    setResult(null);
    try {
      setResult({ data: await api.verify({ blob, target: "Téléphone" }) });
    } catch (error) {
      setResult({ error: error.message });
    } finally {
      setBusy(false);
      loadJournal();
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="space-y-4 lg:col-span-3">
        <AccessCamera preview={preview} onCapture={onCapture} onReset={reset} />

        <div className="card">
          <div className="flex flex-wrap gap-3">
            <label className="btn-secondary cursor-pointer">
              Importer une photo
              <input type="file" accept="image/*" className="hidden" onChange={onUpload} />
            </label>
            <button className="btn-primary" onClick={verify} disabled={busy || !blob}>
              {busy ? "Vérification…" : "Vérifier et ouvrir"}
            </button>
          </div>
        </div>
      </div>

      <AccessPanel target="Téléphone" result={result} journal={journal} onRefresh={loadJournal} />
    </div>
  );
}