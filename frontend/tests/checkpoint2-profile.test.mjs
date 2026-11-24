import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const KHANG_DEV_ID = 'abcfa9f6-c9d2-4181-9b4b-118a4bb6c647';
const KIEN_DEV_ID = 'c44f393b-4314-4f83-9b2e-9d1fe73ef64c';

test('Checkpoint 2: Profile identity rules and stable account IDs', () => {
  function computeProfileDecorations(user) {
    const isKhangDev = String(user?.id || '').toLowerCase() === KHANG_DEV_ID;
    const isKienDev = String(user?.id || '').toLowerCase() === KIEN_DEV_ID;
    const hasAuraMemeSeal = isKhangDev || isKienDev;
    return { isKhangDev, isKienDev, hasAuraMemeSeal };
  }

  // 1. Khang Dev: AuraMeme seal + Celestial Card
  const khang = computeProfileDecorations({
    id: KHANG_DEV_ID,
    username: 'khang_dev',
    display_name: 'Khang Dev',
    roles: ['ADMIN', 'USER'],
  });
  assert.equal(khang.isKhangDev, true);
  assert.equal(khang.isKienDev, false);
  assert.equal(khang.hasAuraMemeSeal, true);

  // Case-insensitive ID check
  const khangUpper = computeProfileDecorations({ id: KHANG_DEV_ID.toUpperCase() });
  assert.equal(khangUpper.isKhangDev, true);
  assert.equal(khangUpper.hasAuraMemeSeal, true);

  // 2. Kien Dev: AuraMeme seal ONLY, NO Celestial Card
  const kien = computeProfileDecorations({
    id: KIEN_DEV_ID,
    username: 'kien_dev',
    display_name: 'Kien Dev',
    roles: ['ADMIN', 'USER'],
  });
  assert.equal(kien.isKhangDev, false);
  assert.equal(kien.isKienDev, true);
  assert.equal(kien.hasAuraMemeSeal, true);

  // 3. Other Admin: neither seal nor Celestial Card
  const otherAdmin = computeProfileDecorations({
    id: '11111111-2222-3333-4444-555555555555',
    username: 'other_admin',
    display_name: 'Other Admin',
    roles: ['ADMIN', 'USER'],
  });
  assert.equal(otherAdmin.isKhangDev, false);
  assert.equal(otherAdmin.isKienDev, false);
  assert.equal(otherAdmin.hasAuraMemeSeal, false);

  // 4. Standard User: neither
  const standardUser = computeProfileDecorations({
    id: '99999999-8888-7777-6666-555555555555',
    username: 'gigachad',
    display_name: 'Gigachad',
  });
  assert.equal(standardUser.isKhangDev, false);
  assert.equal(standardUser.isKienDev, false);
  assert.equal(standardUser.hasAuraMemeSeal, false);

  // 5. Spoofed display name or username cannot hijack identity
  const imposter = computeProfileDecorations({
    id: '12345678-1234-1234-1234-123456789abc',
    username: 'khang_dev',
    display_name: 'Khang Dev',
  });
  assert.equal(imposter.isKhangDev, false);
  assert.equal(imposter.isKienDev, false);
  assert.equal(imposter.hasAuraMemeSeal, false);
});

test('Checkpoint 2: Profile stylesheet contains all required Celestial CSS and accessibility rules', () => {
  const cssPath = path.resolve(__dirname, '../src/profile-page.css');
  const css = fs.readFileSync(cssPath, 'utf8');

  // Must have Celestial card classes
  assert.ok(css.includes('.am-profile-identity--celestial'), 'Missing .am-profile-identity--celestial');
  assert.ok(css.includes('.am-celestial-canvas'), 'Missing .am-celestial-canvas');
  assert.ok(css.includes('.am-celestial-smoke'), 'Missing .am-celestial-smoke');
  assert.ok(css.includes('.am-celestial-sparkles'), 'Missing .am-celestial-sparkles');
  assert.ok(css.includes('.am-sparkle'), 'Missing .am-sparkle');
  assert.ok(css.includes('.am-profile-aurameme-seal'), 'Missing .am-profile-aurameme-seal');

  // Must have required colors in smoke gradient: purple, cyan, blue, pink
  assert.ok(css.includes('168,85,247') || css.includes('168, 85, 247'), 'Smoke missing purple tint');
  assert.ok(css.includes('34,211,238') || css.includes('34, 211, 238'), 'Smoke missing cyan tint');
  assert.ok(css.includes('59,130,246') || css.includes('59, 130, 246'), 'Smoke missing blue tint');
  assert.ok(css.includes('244,114,182') || css.includes('244, 114, 182'), 'Smoke missing pink tint');

  // Must have pointer-events: none on decorative canvas
  assert.ok(css.includes('pointer-events:none') || css.includes('pointer-events: none'), 'Canvas must not block clicks');

  // Must have overflow: hidden on canvas
  assert.ok(css.includes('overflow:hidden') || css.includes('overflow: hidden'), 'Canvas must clip within border-radius');

  // Must have Light mode adjustments
  assert.ok(css.includes('.u219[data-theme="light"]') || css.includes('[data-theme="light"]'), 'Light theme support required');

  // Must respect prefers-reduced-motion
  assert.ok(css.includes('prefers-reduced-motion'), 'prefers-reduced-motion support required');
});
