import { useEffect } from "react";
import { playDenied, playGranted } from "../sound";

const SCREEN_STYLE = {
  idle: "from-slate-500 to-slate-700",
  granted: "from-green-500 to-green-700",
  denied: "from-red-500 to-red-700",
};

const GLYPH = { Téléphone: "📱", Portail: "🚧", Porte: "🚪" };

export default function AccessPanel({ target, result, journal, onRefresh }) {
  let state = "idle";
  let title = "EN ATTENTE";
  let message = "Capturez ou importez une photo, puis lancez la vérification.";
  let glyph = GLYPH[target];

  if (result?.error) {
    state = "denied";
    title = "ERREUR";
    message = result.error;
    glyph = "⚠️";
  } else if (result?.data?.granted) {
    state = "granted";
    title = "ACCÈS ACCORDÉ";
    message = `Bienvenue, ${result.data.identity.name}.`;
    glyph = "🔓";
  } else if (result?.data) {
    state = "denied";
    title = "ACCÈS REFUSÉ";
    message = "Personne non reconnue.";
    glyph = "🔒";
  }

  const similarity = result?.data?.identity?.candidates?.[0]?.score;

  useEffect(() => {
    if (!result) return;
    if (state === "granted") playGranted();
    if (state === "denied") playDenied();
  }, [result, state]);

  return (
    <div className="space-y-4 lg:col-span-2">
      <div className="card">
        <div className="device-scene">
          <div className="device">
            <div className={`screen bg-gradient-to-br ${SCREEN_STYLE[state]} ${state}`}>
              <div className="screen-icon">{glyph}</div>
              <div className="screen-title">{title}</div>
              <div className="screen-msg">{message}</div>
            </div>
          </div>
        </div>
        {similarity !== undefined && (
          <div className="mt-4 rounded-xl border border-slate-200 p-3 text-sm text-slate-600">
            Similarité : <b>{similarity.toFixed(3)}</b> · seuil : <b>{result.data.identity.threshold}</b>
          </div>
        )}
      </div>

      <div className="card">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-800">Journal des tentatives</h3>
          <button className="text-xs font-semibold text-teal-700 hover:underline" onClick={onRefresh}>
            Actualiser
          </button>
        </div>
        {journal.length === 0 ? (
          <p className="text-sm text-slate-500">Aucune tentative pour le moment.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-2">Heure</th>
                <th className="py-2">Cible</th>
                <th className="py-2">Personne</th>
                <th className="py-2">Résultat</th>
              </tr>
            </thead>
            <tbody>
              {journal.map((entry, index) => (
                <tr key={index} className="border-b border-slate-100">
                  <td className="py-2 text-slate-600">{entry.time}</td>
                  <td className="py-2 text-slate-600">{entry.target}</td>
                  <td className="py-2 font-medium text-slate-800">{entry.person}</td>
                  <td className="py-2">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                        entry.granted ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
                      }`}
                    >
                      {entry.granted ? "Accordé" : "Refusé"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}