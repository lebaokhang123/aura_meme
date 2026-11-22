import {auth,MOCK_AUTH} from './auth.js';
import { readPreferences, translate } from './preferences.js';
export const USER_KEY = 'aurameme-stitch-demo-user';
export const DEMO_USERS = [
  { displayName: 'Khang Dev', username: 'Khang_dev', avatar: '/assets/demo/khang.jpg' },
  { displayName: 'Kien Dev', username: 'Kien_dev', avatar: '/assets/demo/kien.jpg' },
  { displayName: 'Gigachad', username: 'Gigachad', avatar: '/assets/demo/gigachad.jpg' },
];

let cachedSnapshotUser = null;
let cachedResultUser = null;

export function readDemoUser() {
  if(!MOCK_AUTH){
    const user=auth.snapshot().user;
    if(!user){
      cachedSnapshotUser = null;
      cachedResultUser = null;
      return null;
    }
    if(user === cachedSnapshotUser && cachedResultUser !== null){
      return cachedResultUser;
    }
    cachedSnapshotUser = user;
    cachedResultUser = Object.freeze({
      ...user,
      displayName: user.display_name,
      avatar: user.avatar_url || '/assets/identity/default-avatar.svg',
      membershipTier: user.membership_tier || user.membershipTier || 'free',
      membership_tier: user.membership_tier || user.membershipTier || 'free',
    });
    return cachedResultUser;
  }
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (raw === null) return null;
    const saved = JSON.parse(raw);
    return DEMO_USERS.find(user => user.username === saved?.username) || DEMO_USERS[0];
  } catch {
    return null;
  }
}

export function identifyDemoUser(identifier) {
  const input = identifier.toLowerCase();
  return DEMO_USERS.find(user => input.includes(user.username.toLowerCase().replace('_dev', ''))) || DEMO_USERS[0];
}

export function applyDemoIdentity() {
  const user = readDemoUser();
  if (!user) return;
  document.querySelectorAll('[data-current-user-avatar]').forEach(image => {
    image.src = user.avatar;
    image.alt = translate(`Ảnh đại diện ${user.displayName}`, readPreferences().language);
  });
}
