export const KHANG_DEV_ID = 'abcfa9f6-c9d2-4181-9b4b-118a4bb6c647';
export const KIEN_DEV_ID = 'c44f393b-4314-4f83-9b2e-9d1fe73ef64c';

export function computeProfileDecorations(user) {
  const isKhangDev = String(user?.id || '').toLowerCase() === KHANG_DEV_ID;
  const isKienDev = String(user?.id || '').toLowerCase() === KIEN_DEV_ID;
  const hasAuraMemeSeal = isKhangDev || isKienDev;
  return { isKhangDev, isKienDev, hasAuraMemeSeal };
}
