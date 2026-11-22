import test from 'node:test';
import assert from 'node:assert/strict';
import {
  REALMS,
  parseLevel,
  realmTierForLevel,
  realmNameForLevel,
  specialTitleKind,
  resolveRealmBadges,
} from '../src/realm-tier.js';

const BOUNDARIES = [
  [1, 1, 'Luyện Khí'],
  [10, 1, 'Luyện Khí'],
  [11, 2, 'Trúc Cơ'],
  [20, 2, 'Trúc Cơ'],
  [21, 3, 'Kim Đan'],
  [30, 3, 'Kim Đan'],
  [31, 4, 'Nguyên Anh'],
  [40, 4, 'Nguyên Anh'],
  [41, 5, 'Hóa Thần'],
  [50, 5, 'Hóa Thần'],
  [51, 6, 'Luyện Hư'],
  [60, 6, 'Luyện Hư'],
  [61, 7, 'Hợp Thể'],
  [70, 7, 'Hợp Thể'],
  [71, 8, 'Đại Thừa'],
  [80, 8, 'Đại Thừa'],
  [81, 9, 'Độ Kiếp'],
  [90, 9, 'Độ Kiếp'],
  [91, 10, 'Phi Thăng'],
  [99, 10, 'Phi Thăng'],
  [100, 10, 'Phi Thăng'],
];

test('all 10 realms and 21 boundary levels map identically to backend Aura V1', () => {
  assert.equal(REALMS.length, 10);
  for (const [level, expectedTier, expectedRealm] of BOUNDARIES) {
    assert.equal(parseLevel(level), level);
    assert.equal(parseLevel(`LVL ${level}`), level);
    assert.equal(realmTierForLevel(level), expectedTier);
    assert.equal(realmNameForLevel(level), expectedRealm);
    const resolved = resolveRealmBadges({ level, realm: expectedRealm, title: expectedRealm });
    assert.deepEqual(resolved, {
      levelNum: level,
      levelLabel: `LVL ${level}`,
      realmTier: expectedTier,
      realmName: expectedRealm,
      titleText: expectedRealm,
      specialKind: null,
    });
  }
});

test('special cosmetic titles preserve real level/realm tier and never fabricate without level', () => {
  const khang = resolveRealmBadges({ level: 79, realm: 'Đại Thừa', title: 'Bá Chủ Thiên Lôi' });
  assert.equal(khang.levelNum, 79);
  assert.equal(khang.realmTier, 8);
  assert.equal(khang.realmName, 'Đại Thừa');
  assert.equal(khang.titleText, 'Bá Chủ Thiên Lôi');
  assert.equal(khang.specialKind, 'thunder');

  // After leveling up to 100, special title remains while tier upgrades to 10
  const khang100 = resolveRealmBadges({ level: 100, realm: 'Phi Thăng', title: 'Bá Chủ Thiên Lôi' });
  assert.equal(khang100.realmTier, 10);
  assert.equal(khang100.specialKind, 'thunder');

  const kien = resolveRealmBadges({ level: 'LVL 12', realm: 'Trúc Cơ', title: 'Thiên Tướng Độ Ách' });
  assert.equal(kien.levelNum, 12);
  assert.equal(kien.realmTier, 2);
  assert.equal(kien.specialKind, 'warden');

  assert.equal(specialTitleKind('Phi Thăng'), null);
  assert.equal(specialTitleKind('constructor'), null);

  // Missing or invalid levels never fabricate realm or title
  for (const bad of [null, undefined, 0, -5, 101, 1.5, '', 'LVL 0', 'LVL 101', 'abc']) {
    const empty = resolveRealmBadges({ level: bad, realm: 'Phi Thăng', title: 'Bá Chủ Thiên Lôi' });
    assert.equal(empty.levelNum, null);
    assert.equal(empty.realmTier, null);
    assert.equal(empty.titleText, '');
    assert.equal(empty.specialKind, null);
  }
});
