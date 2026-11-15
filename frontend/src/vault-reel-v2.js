/**
 * AuraMeme Vault visual reel V2 — display only. The server-authorized receipt
 * is the ONLY authoritative reward. This module never changes drop odds.
 * No dependencies; safe to unit test with Node.
 */
export const RARITY_WEIGHTS = Object.freeze({ D: 6890, C: 2000, B: 1000, A: 100, S: 10 });
export const REEL_CARD_STEP = 146; // CSS 136px card + 10px gap
export const REEL_DURATION_MS = 6200;

export function sampleRarity(random = Math.random) {
  const v = random();
  if (!Number.isFinite(v) || v < 0 || v >= 1) throw new RangeError('Invalid random source');
  const n = Math.min(9999, Math.floor(v * 10000 + 1e-9));
  let current = 0;
  for (const [rarity, weight] of Object.entries(RARITY_WEIGHTS)) {
    current += weight;
    if (n < current) return rarity;
  }
  throw new Error('Rarity weights are incomplete');
}

export function buildReelV2(assets, confirmedReward, { count = 52, random = Math.random } = {}) {
  if (!Array.isArray(assets) || !confirmedReward?.id || !confirmedReward?.rarity) {
    throw new TypeError('Reel requires a confirmed server receipt');
  }
  if (!Number.isSafeInteger(count) || count < 24 || count > 100) throw new RangeError('Unsupported reel size');
  const pool = assets.filter(a => a && typeof a.id === 'string' &&
    Object.hasOwn(RARITY_WEIGHTS, a.rarity) && a.available !== false && a.kind === confirmedReward.kind);
  const buckets = Object.fromEntries(Object.keys(RARITY_WEIGHTS).map(r => [r, pool.filter(a => a.rarity === r)]));
  const fallback = pool.length ? pool : [confirmedReward];
  const winnerIndex = count - 5; // Keep a short tail so the selected item sits under the needle.
  const items = [];
  for (let i = 0; i < count; i++) {
    if (i === winnerIndex) { items.push(confirmedReward); continue; }
    const rarity = sampleRarity(random);
    const choices = buckets[rarity]?.length ? buckets[rarity] : fallback;
    const v = random();
    if (!Number.isFinite(v) || v < 0 || v >= 1) throw new RangeError('Invalid random source');
    items.push(choices[Math.floor(v * choices.length)]);
  }
  // RNG above controls only the decor. No pick can override confirmedReward.
  return { items, winnerIndex };
}

export function reelOffsets(length, winnerIndex, cardStep = REEL_CARD_STEP) {
  if (!Number.isSafeInteger(length) || length <= 0 || winnerIndex < 0 || winnerIndex >= length) {
    throw new RangeError('Invalid reel geometry');
  }
  const center = (length - 1) * cardStep / 2;
  return { startPx: center, endPx: center - winnerIndex * cardStep };
}

/** Crossing times approximate ease-out distance, so tick cadence slows naturally. */
export function reelTickTimes(steps = 47, duration = REEL_DURATION_MS) {
  if (!Number.isSafeInteger(steps) || steps < 1 || steps > 100 || duration <= 0) throw new RangeError('Invalid timing');
  const result = [];
  for (let i = 1; i <= steps; i++) {
    const progress = i / (steps + 1);
    result.push(Math.floor(duration * (1 - Math.cbrt(1 - progress))));
  }
  return result;
}
