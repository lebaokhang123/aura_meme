import test from 'node:test';
import assert from 'node:assert/strict';
import {buildReelV2, reelOffsets, reelTickTimes, sampleRarity, REEL_DURATION_MS} from '../src/vault-reel-v2.js';

const asset = rarity => ({ id: rarity, kind: 'background', rarity, available: true, display_name: rarity });
const pool = ['D','C','B','A','S'].map(asset);

test('visual probability boundary uses exact fixed weights', () => {
  for (const [n, expected] of [[0,'D'],[.688999,'D'],[.689,'C'],[.888999,'C'],[.889,'B'],[.988999,'B'],[.989,'A'],[.998999,'A'],[.999,'S'],[.999999,'S']]) {
    assert.equal(sampleRarity(() => n), expected);
  }
});

test('fixed receipt always stops exactly at server-picked reward', () => {
  const reward = asset('S');
  const reel = buildReelV2(pool, reward, {count:52, random:()=>.1});
  assert.equal(reel.items.length, 52);
  assert.equal(reel.items[reel.winnerIndex], reward);
  const {startPx,endPx}=reelOffsets(reel.items.length,reel.winnerIndex);
  assert.ok(startPx>endPx);
});

test('can fill a reel from only five backgrounds, duplicates are normal', () => {
  const reel=buildReelV2(pool,asset('B'),{count:60,random:()=>.05});
  assert.equal(reel.items.length,60);
  assert.equal(reel.items[reel.winnerIndex].rarity,'B');
  assert.ok(reel.items.filter(a=>a.rarity==='D').length>=50);
});

test('tick cues become increasingly spaced as visual reel slows down', () => {
  const t=reelTickTimes(47,REEL_DURATION_MS);
  assert.equal(t.length,47);
  assert.ok(t.every((value,i)=>i===0||value>t[i-1]));
  assert.ok(t[1]-t[0]<t.at(-1)-t.at(-2));
  assert.ok(t.at(-1)<REEL_DURATION_MS);
});
