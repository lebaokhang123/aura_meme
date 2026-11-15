import test from 'node:test';
import assert from 'node:assert/strict';
import { BACKGROUND_EFFECTS, mountBackground } from '../src/background-effects.js';

function fixture(t, reduced = false, width = 375, height = 812) {
  const original = new Map();
  const install = (name, value) => { original.set(name, Object.getOwnPropertyDescriptor(globalThis, name)); Object.defineProperty(globalThis, name, { configurable: true, writable: true, value }); };
  const listeners = new Set();
  class Target extends EventTarget {
    addEventListener(type, fn, options) { listeners.add(fn); super.addEventListener(type, fn, options); }
    removeEventListener(type, fn) { listeners.delete(fn); super.removeEventListener(type, fn); }
  }
  const win = new Target(), doc = new Target(), media = new Target();
  doc.hidden = false; media.matches = reduced; win.matchMedia = () => media; win.devicePixelRatio = 3;
  const frames = new Map(), observers = [];
  let next = 0, draws = 0;
  class Observer {
    constructor(callback) { this.callback = callback; this.disconnected = false; observers.push(this); }
    observe() {}
    disconnect() { this.disconnected = true; }
  }
  const cx = new Proxy({}, { get(target, key) {
    if (key === 'createLinearGradient') return () => ({ addColorStop() {} });
    return target[key] ?? (() => { draws++; });
  } });
  const canvas = { getContext: () => cx };
  const root = { isConnected: true, querySelector: () => canvas, getBoundingClientRect: () => ({ left: 0, top: 0, width, height }), style: { setProperty() {} } };
  install('window', win); install('document', doc); install('getComputedStyle', () => ({ getPropertyValue: () => '#948f9a' }));
  install('ResizeObserver', Observer); install('IntersectionObserver', Observer);
  install('requestAnimationFrame', fn => { frames.set(++next, fn); return next; });
  install('cancelAnimationFrame', id => frames.delete(id));
  t.after(() => { for (const [name, descriptor] of original) { if (descriptor) Object.defineProperty(globalThis, name, descriptor); else delete globalThis[name]; } });
  return { win, doc, media, frames, listeners, observers, canvas, root, draws: () => draws,
    tick() { const queued = [...frames.values()]; frames.clear(); queued.forEach(fn => fn(performance.now() + 16)); },
  };
}

test('effect allowlist rejects arbitrary catalog values without opening a canvas', () => {
  assert.equal(BACKGROUND_EFFECTS.length, 5);
  for (const effect of [null, undefined, 'unknown', '__proto__', 'violet-base']) {
    assert.doesNotThrow(() => mountBackground({ querySelector() { throw Error('unexpected canvas'); } }, effect)());
  }
});

for (const effect of BACKGROUND_EFFECTS.filter(value => value !== 'violet-base')) {
  test(`${effect}: one RAF, hidden/offscreen pause, live reduced motion and complete cleanup`, t => {
    const f = fixture(t);
    const cleanup = mountBackground(f.root, effect);
    assert.equal(f.frames.size, 1);
    assert.equal(f.canvas.width, 469); // Mobile DPR is capped at 1.25.
    f.tick(); assert.equal(f.frames.size, 1);
    f.doc.hidden = true; f.doc.dispatchEvent(new Event('visibilitychange'));
    assert.equal(f.frames.size, 0);
    f.doc.hidden = false; f.doc.dispatchEvent(new Event('visibilitychange'));
    assert.equal(f.frames.size, 1);
    f.observers[1].callback([{ isIntersecting: false }]); assert.equal(f.frames.size, 0);
    f.observers[1].callback([{ isIntersecting: true }]); assert.equal(f.frames.size, 1);
    f.media.matches = true; f.media.dispatchEvent(new Event('change'));
    assert.equal(f.frames.size, 0);
    const before = f.draws();
    const move = new Event('pointermove'); Object.assign(move, { clientX: 100, clientY: 100 }); f.win.dispatchEvent(move);
    assert.equal(f.draws(), before, 'reduced motion stays static on pointer movement');
    f.media.matches = false; f.media.dispatchEvent(new Event('change')); assert.equal(f.frames.size, 1);
    cleanup(); assert.equal(f.frames.size, 0); assert.equal(f.listeners.size, 0);
    assert.ok(f.observers.every(observer => observer.disconnected));
    f.observers[1].callback([{ isIntersecting: true }]); assert.equal(f.frames.size, 0, 'queued observer cannot restart after disposal');
  });
  test(`${effect}: initial reduced motion paints a static equivalent without a loop`, t => {
    const f = fixture(t, true);
    const cleanup = mountBackground(f.root, effect);
    assert.equal(f.frames.size, 0); assert.ok(f.draws() > 0); cleanup();
  });
}

test('desktop raster size stays bounded on very large screens', t => {
  const f = fixture(t, false, 7680, 4320);
  const cleanup = mountBackground(f.root, 'lucian-330');
  assert.ok(f.canvas.width * f.canvas.height <= 4005000);
  cleanup();
});
