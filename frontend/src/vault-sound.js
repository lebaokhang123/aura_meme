// Original procedural PCM cues; no downloaded recordings or third-party samples.
export function createVaultSound({ AudioContext = globalThis.AudioContext || globalThis.webkitAudioContext, document = globalThis.document } = {}) {
  let context = null, muted = true, disposed = false;
  const buffers = new Map(), nodes = new Set();
  function stop() { for (const node of nodes) { try { node.stop(); } catch {} node.disconnect(); } nodes.clear(); }
  function unlock() {
    if (disposed || !AudioContext) return;
    try {
      if (!context) {
        context = new AudioContext();
        for (const [key, frequency, duration] of [['tick', 880, .035], ['D', 330, .32], ['C', 440, .4], ['B', 550, .48], ['A', 660, .56], ['S', 880, .72]]) {
          const buffer = context.createBuffer(1, Math.ceil(context.sampleRate * duration), context.sampleRate), data = buffer.getChannelData(0);
          for (let i = 0; i < data.length; i++) {
            const time = i / context.sampleRate, progress = time / duration;
            const envelope = Math.min(1, time / .005) * (1 - progress) ** 2;
            data[i] = envelope * (Math.sin(2 * Math.PI * frequency * time) + .3 * Math.sin(2 * Math.PI * frequency * 1.5 * time)) * .12;
          }
          buffers.set(key, buffer);
        }
      }
      context.resume()?.catch(() => {});
    } catch { stop(); }
  }
  function play(key) {
    if (disposed || muted || document?.hidden || !context || context.state !== 'running' || !buffers.has(key)) return;
    try {
      const node = context.createBufferSource(); node.buffer = buffers.get(key); node.connect(context.destination); nodes.add(node);
      node.onended = () => { nodes.delete(node); node.disconnect(); }; node.start();
    } catch { /* Audio is optional; opening and receipt recovery continue. */ }
  }
  const visibility = () => { if (document.hidden) stop(); };
  document?.addEventListener('visibilitychange', visibility);
  return {
    unlock,
    setMuted(value) { muted = Boolean(value); if (muted) stop(); },
    tick() { play('tick'); },
    reveal(rarity) { play(rarity); },
    dispose() {
      if (disposed) return; disposed = true; stop(); buffers.clear();
      document?.removeEventListener('visibilitychange', visibility);
      try { context?.close()?.catch(() => {}); } catch {}
      context = null;
    },
  };
}
