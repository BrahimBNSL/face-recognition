let context = null;

function getContext() {
  if (!context) {
    context = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (context.state === "suspended") {
    context.resume();
  }
  return context;
}

function tone(frequency, start, duration, volume, type = "sine") {
  const ctx = getContext();
  const oscillator = ctx.createOscillator();
  const gain = ctx.createGain();
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, ctx.currentTime + start);
  gain.gain.setValueAtTime(0, ctx.currentTime + start);
  gain.gain.linearRampToValueAtTime(volume, ctx.currentTime + start + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + duration);
  oscillator.connect(gain);
  gain.connect(ctx.destination);
  oscillator.start(ctx.currentTime + start);
  oscillator.stop(ctx.currentTime + start + duration + 0.05);
}

export function playGranted() {
  tone(523.25, 0, 0.18, 0.25);
  tone(659.25, 0.12, 0.18, 0.25);
  tone(783.99, 0.24, 0.35, 0.25);
}

export function playDenied() {
  tone(220, 0, 0.25, 0.3, "square");
  tone(165, 0.22, 0.4, 0.3, "square");
}

export function playLivenessPassed() {
  tone(880, 0, 0.12, 0.2);
  tone(1174.66, 0.1, 0.2, 0.2);
}