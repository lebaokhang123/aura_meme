// Canonical 10-realm cultivation mapping synchronized with backend/app/aura_v1.py.
// Never infers admin/special titles from username on the frontend; trusts backend-provided title only.

export const REALMS = Object.freeze([
  'Luyện Khí',   // 1: LVL 1-10
  'Trúc Cơ',     // 2: LVL 11-20
  'Kim Đan',     // 3: LVL 21-30
  'Nguyên Anh',  // 4: LVL 31-40
  'Hóa Thần',    // 5: LVL 41-50
  'Luyện Hư',    // 6: LVL 51-60
  'Hợp Thể',     // 7: LVL 61-70
  'Đại Thừa',    // 8: LVL 71-80
  'Độ Kiếp',     // 9: LVL 81-90
  'Phi Thăng',   // 10: LVL 91-100
]);

export const SPECIAL_TITLE_KINDS = Object.freeze({
  'Sáng Thế Thần': 'creator',
});

export function parseLevel(value) {
  if (Number.isSafeInteger(value) && value >= 1 && value <= 100) {
    return value;
  }
  if (typeof value === 'string') {
    const match = /^\s*(?:lvl\s*)?(\d{1,3})\s*$/i.exec(value);
    if (match) {
      const parsed = Number(match[1]);
      if (Number.isSafeInteger(parsed) && parsed >= 1 && parsed <= 100) {
        return parsed;
      }
    }
  }
  return null;
}

export function realmTierForLevel(level) {
  const num = parseLevel(level);
  return num === null ? null : Math.floor((num - 1) / 10) + 1;
}

export function realmNameForLevel(level) {
  const tier = realmTierForLevel(level);
  return tier === null ? '' : REALMS[tier - 1];
}

export function specialTitleKind(title) {
  if (typeof title !== 'string') return null;
  const trimmed = title.trim();
  return Object.hasOwn(SPECIAL_TITLE_KINDS, trimmed) ? SPECIAL_TITLE_KINDS[trimmed] : null;
}

export function resolveRealmBadges({ level, realm, title } = {}) {
  const levelNum = parseLevel(level);
  if (levelNum === null) {
    return {
      levelNum: null,
      levelLabel: '',
      realmTier: null,
      realmName: '',
      titleText: '',
      specialKind: null,
    };
  }
  const realmTier = Math.floor((levelNum - 1) / 10) + 1;
  const derivedRealm = REALMS[realmTier - 1];
  const realmName = typeof realm === 'string' && realm.trim() ? realm.trim() : derivedRealm;
  const rawTitle = typeof title === 'string' && title.trim() ? title.trim() : '';
  const titleText = rawTitle || realmName;
  const specialKind = specialTitleKind(titleText);

  return {
    levelNum,
    levelLabel: `LVL ${levelNum}`,
    realmTier,
    realmName,
    titleText,
    specialKind,
  };
}
