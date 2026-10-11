"""Feuille de style de l'application : palette, cartes, statuts, écran d'accès et animations."""

CSS: str = """
:root {
  --navy: #0b1f3a; --navy-2: #0f3d5e; --teal: #0d9488; --teal-soft: #ccfbf1;
  --ink: #1e293b; --muted: #64748b; --line: #e2e8f0; --bg: #f8fafc;
  --ok: #16a34a; --warn: #f59e0b; --err: #dc2626; --idle: #64748b;
}
.gradio-container {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
  max-width: 1200px !important; background: var(--bg);
}
.hero {
  background: linear-gradient(120deg, var(--navy) 0%, var(--navy-2) 55%, var(--teal) 100%);
  color: #fff; border-radius: 18px; padding: 24px 30px; margin: 8px 0 12px 0;
  box-shadow: 0 10px 30px rgba(11,31,58,0.22);
}
.hero h1 { margin: 0; font-size: 26px; font-weight: 700; color: #fff; }
.hero p { margin: 6px 0 0 0; opacity: 0.88; font-size: 14px; }
.notice {
  background: #f0fdfa; border: 1px solid #99f6e4; border-left: 4px solid var(--teal);
  padding: 10px 16px; border-radius: 10px; font-size: 13px; color: #134e4a; margin-bottom: 12px;
}
.card {
  background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px;
  box-shadow: 0 1px 3px rgba(15,23,42,0.05); margin-bottom: 12px;
}
.card h3 { margin: 0 0 8px 0; color: var(--navy); font-size: 15px; font-weight: 700; }
.muted { color: var(--muted); font-size: 13px; }
.status { border-radius: 12px; padding: 14px 16px; color: #fff; }
.status.ok { background: linear-gradient(135deg, #22c55e, #15803d); }
.status.warn { background: linear-gradient(135deg, #fbbf24, #d97706); }
.status.err { background: linear-gradient(135deg, #f87171, #b91c1c); }
.status.idle { background: linear-gradient(135deg, #94a3b8, #475569); }
.status.analyse { background: linear-gradient(135deg, #facc15, #ca8a04); color: #1c1917; }
.status-title { font-size: 11px; letter-spacing: 1.3px; font-weight: 700; opacity: 0.92; }
.status-msg { font-size: 16px; font-weight: 600; margin: 4px 0 10px 0; }
.bar { height: 8px; background: rgba(255,255,255,0.35); border-radius: 6px; overflow: hidden; }
.bar > div { height: 100%; background: #fff; transition: width 0.3s ease; }
.bar-label { font-size: 12px; margin-top: 6px; opacity: 0.92; }
.result { border-left: 5px solid var(--line); }
.result.ok { border-left-color: var(--ok); }
.result.no { border-left-color: var(--err); }
.result-title { font-size: 19px; font-weight: 700; color: var(--navy); margin-bottom: 6px; }
.pill { padding: 3px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.pill-ok { background: #dcfce7; color: #166534; }
.pill-no { background: #fee2e2; color: #991b1b; }
.pill-wait { background: #fef9c3; color: #854d0e; }
.table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
.table th { text-align: left; color: var(--muted); font-weight: 600; border-bottom: 2px solid var(--line); padding: 8px; }
.table td { border-bottom: 1px solid var(--line); padding: 8px; color: var(--ink); }
.device-scene { display: flex; justify-content: center; padding: 8px 0; }
.device {
  width: 190px; height: 330px; background: #111827; border-radius: 32px; padding: 14px;
  box-shadow: 0 14px 34px rgba(0,0,0,0.28); display: flex; align-items: center; justify-content: center;
}
.screen {
  width: 100%; height: 100%; border-radius: 22px; display: flex; flex-direction: column;
  align-items: center; justify-content: center; text-align: center; padding: 14px; color: #fff;
}
.screen.granted { background: linear-gradient(160deg, #16a34a, #065f46); animation: pulse 1.2s ease-out 1; }
.screen.denied { background: linear-gradient(160deg, #dc2626, #7f1d1d); animation: shake 0.5s ease-in-out 1; }
.screen.idle { background: linear-gradient(160deg, #475569, #1e293b); }
.screen-icon { font-size: 48px; margin-bottom: 8px; }
.screen-title { font-weight: 700; font-size: 15px; letter-spacing: 0.5px; margin-bottom: 6px; }
.screen-msg { font-size: 13px; opacity: 0.92; line-height: 1.35; }
.footer { text-align: center; color: var(--muted); font-size: 12px; margin: 18px 0 6px 0; }
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(22,163,74,0.7); }
  100% { box-shadow: 0 0 0 26px rgba(22,163,74,0); }
}
@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20% { transform: translateX(-8px); }
  40% { transform: translateX(8px); }
  60% { transform: translateX(-6px); }
  80% { transform: translateX(6px); }
}
"""