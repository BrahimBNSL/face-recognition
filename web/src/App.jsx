import { useEffect, useState } from "react";
import { api } from "./api";
import RealTime from "./components/RealTime";
import Enroll from "./components/Enroll";
import Access from "./components/Access";

const TABS = [
  { id: "live", label: "Temps réel" },
  { id: "enroll", label: "Enregistrement" },
  { id: "access", label: "Simulation d'accès" },
];

export default function App() {
  const [tab, setTab] = useState("live");
  const [server, setServer] = useState({ online: false, threshold: null });

  useEffect(() => {
    api
      .health()
      .then((data) => setServer({ online: true, threshold: data.threshold }))
      .catch(() => setServer({ online: false, threshold: null }));
  }, []);

  return (
    <div className="min-h-screen">
      <header className="bg-gradient-to-r from-navy-900 via-navy-800 to-teal-600 text-white shadow-lg">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Reconnaissance faciale</h1>
            <p className="mt-1 text-sm text-white/80">
              Temps réel, enregistrement et contrôle d'accès simulé
            </p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1.5 font-medium ${
                server.online ? "bg-emerald-500/20 text-emerald-100" : "bg-red-500/20 text-red-100"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${server.online ? "bg-emerald-400" : "bg-red-400"}`}
              />
              {server.online ? "Serveur connecté" : "Serveur hors ligne"}
            </span>
            {server.online && (
              <span className="rounded-full bg-white/10 px-3 py-1.5 text-white/90">
                Seuil {server.threshold ?? "non défini"}
              </span>
            )}
          </div>
        </div>
      </header>

      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl gap-1 px-6">
          {TABS.map((item) => (
            <button
              key={item.id}
              onClick={() => setTab(item.id)}
              className={`-mb-px border-b-2 px-4 py-3.5 text-sm font-semibold transition ${
                tab === item.id
                  ? "border-teal-600 text-teal-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-6 py-8">
        {tab === "live" && <RealTime />}
        {tab === "enroll" && <Enroll />}
        {tab === "access" && <Access />}
      </main>

      <footer className="pb-8 text-center text-xs text-slate-500">
        Traitement local · Aucune photo conservée · Projet académique
      </footer>
    </div>
  );
}