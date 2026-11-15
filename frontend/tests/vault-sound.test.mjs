import test from 'node:test';
import assert from 'node:assert/strict';
import { createVaultSound } from '../src/vault-sound.js';

test('sound stays silent until a gesture, caches original PCM and obeys mute/visibility/disposal', () => {
  const doc = new EventTarget(); doc.hidden = false;
  let created = 0, started = 0, stopped = 0, closed = 0;
  const buffers = [];
  class AudioContext {
    constructor() { created++; this.sampleRate = 8000; this.state = 'running'; }
    createBuffer(channels, length) { const data = new Float32Array(length); const buffer = { getChannelData: () => data }; buffers.push(buffer); return buffer; }
    resume() { return Promise.resolve(); }
    close() { closed++; return Promise.resolve(); }
    createBufferSource() { return { connect() {}, disconnect() {}, start() { started++; }, stop() { stopped++; } }; }
  }
  const sound = createVaultSound({ AudioContext, document: doc });
  sound.setMuted(false); sound.tick(); sound.reveal('S'); assert.equal(created, 0); assert.equal(started, 0);
  sound.unlock(); sound.unlock(); assert.equal(created, 1); assert.equal(buffers.length, 6);
  assert.ok(buffers.every(buffer => buffer.getChannelData().some(value => value !== 0)));
  sound.tick(); sound.reveal('S'); assert.equal(started, 2);
  sound.setMuted(true); assert.equal(stopped, 2); sound.tick(); assert.equal(started, 2);
  sound.setMuted(false); sound.tick(); assert.equal(started, 3);
  doc.hidden = true; doc.dispatchEvent(new Event('visibilitychange')); assert.equal(stopped, 3); sound.tick(); assert.equal(started, 3);
  doc.hidden = false; sound.reveal('A'); assert.equal(started, 4);
  sound.dispose(); sound.dispose(); assert.equal(closed, 1); sound.unlock(); sound.tick(); assert.equal(created, 1); assert.equal(started, 4);
});

test('unavailable or failing audio never throws into the opening flow', () => {
  for (const AudioContext of [null, class { constructor() { throw Error('blocked'); } }]) {
    const sound = createVaultSound({ AudioContext, document: new EventTarget() });
    assert.doesNotThrow(() => { sound.unlock(); sound.setMuted(false); sound.tick(); sound.reveal('S'); sound.dispose(); });
  }
});
