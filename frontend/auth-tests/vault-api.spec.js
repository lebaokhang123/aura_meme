import { test, expect } from '@playwright/test';

// API-mode transport regressions with synthetic fixtures; these are not real-data acceptance.
const uuid = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`;
const users = [1, 2].map(n => ({ id: uuid(n), username: `vault_user_${n}`, display_name: `Vault User ${n}`, roles: ['USER'], status: 'active', avatar_url: null }));
const asset = (n, kind, name, effect_key = null) => ({ id: uuid(n), slug: `fixture-${n}`, kind, display_name: name, rarity: 'D', effect_key, available: true, media_url: `/api/v1/catalog/assets/${uuid(n)}` });
const ownedMeme = asset(10, 'avatar', 'Meme đã có'), rewardMeme = asset(11, 'avatar', 'Meme máy chủ chọn'), background = asset(12, 'background', 'Nền thử nghiệm', 'violet-base');
const assets = [ownedMeme, rewardMeme, background];
const caseId = kind => uuid(kind === 'avatar' ? 20 : 21);
const storageKey = owner => `aurameme-vault-pending:${owner}`;

async function transport(context) {
  const owners = new Map(users.map(user => [user.id, { quantities: new Map([[ownedMeme.id, 2], [background.id, 1]]), equipment: {} }]));
  const api = { user: users[0], requests: [], receipts: new Map(), nextPost: null };
  await context.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname.slice('/api/v1'.length), method = request.method();
    let body; try { body = request.postDataJSON(); } catch {}
    const key = request.headers()['idempotency-key'], owner = api.user?.id, state = owners.get(owner);
    api.requests.push({ path, method, body, key, owner, query: Object.fromEntries(url.searchParams), csrf: request.headers()['x-csrf-token'] });
    const send = (status, value) => route.fulfill({ status, contentType: 'application/json', body: status === 204 ? '' : JSON.stringify(value) });
    const fail = (status, code) => send(status, { error: { code, message: 'Synthetic Vault fixture' } });
    const page = items => {
      const n = Number(url.searchParams.get('page') || 1), size = Number(url.searchParams.get('page_size') || 12);
      return { items: items.slice((n - 1) * size, n * size), pagination: { page: n, page_size: size, total: items.length, total_pages: Math.ceil(items.length / size) } };
    };
    if (path.startsWith('/catalog/assets/')) return route.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a6S8AAAAASUVORK5CYII=', 'base64') });
    if (path === '/users/me') return api.user ? send(200, api.user) : fail(401, 'UNAUTHORIZED');
    if (path === '/auth/csrf') return send(200, { csrf_token: 'vault-fixture-csrf' });
    if (path === '/categories' || path === '/posts') return send(200, page([]));
    if (!state) return fail(401, 'UNAUTHORIZED');
    if (method !== 'GET' && request.headers()['x-csrf-token'] !== 'vault-fixture-csrf') return fail(403, 'CSRF_INVALID');
    if (path === '/auth/logout') {api.user=null;return send(204);}
    if (path === '/vault/cases' && api.casesError) return route.abort('failed');
    if (path === '/vault/cases') return send(200, { items: ['avatar', 'background'].filter(kind=>!api.backgroundOnly||kind==='background').map(kind => ({ id: caseId(kind), runtime_kind: kind, label: kind, cost_khi_van: 0, status: 'active' })) });
    if (/^\/vault\/cases\/[^/]+$/.test(path)) return api.oddsUnavailable ? fail(503,'NOT_READY') : send(200, {case:{id:caseId('avatar'),runtime_kind:'avatar',label:'Meme',cost_khi_van:0,status:'active'},bands:[{min_earned_xp:0,max_earned_xp:null,odds_version:1,weights_bps:{D:6890,C:2000,B:1000,A:100,S:10}}]});
    if (path === '/catalog') return send(200, page(assets.filter(value => value.kind === url.searchParams.get('kind') && (!url.searchParams.get('rarity') || value.rarity === url.searchParams.get('rarity')) && value.display_name.includes(url.searchParams.get('q') || '')).map(value => ({ asset: value, owned: state.quantities.has(value.id) }))));
    if (path === '/inventory/me' && api.expireInventory) {api.user=null;return fail(401,'UNAUTHORIZED');}
    if (path === '/inventory/me') return send(200, page(assets.filter(value => value.kind === url.searchParams.get('kind') && state.quantities.has(value.id)).map(value => ({ asset: value, quantity: state.quantities.get(value.id), equipped: state.equipment[value.kind] === value.id }))));
    if (path === '/inventory/equipment') return send(200, { items: Object.entries(state.equipment).filter(([, id]) => id).map(([slot_kind, id]) => ({ slot_kind, asset: assets.find(value => value.id === id) })) });
    if (path.startsWith('/inventory/equipment/') && method === 'PUT') {
      const slot = path.split('/').at(-1), value = assets.find(value => value.id === body.asset_id);
      if (body.asset_id !== null && (!value || value.kind !== slot || !state.quantities.has(value.id))) return fail(403, 'FORBIDDEN');
      state.equipment[slot] = body.asset_id; return send(200, { slot_kind: slot, asset_id: body.asset_id });
    }
    if (path === '/vault/opens/by-request') {
      const receipt = api.receipts.get(`${owner}:${url.searchParams.get('key')}`);
      return receipt ? send(200, { ...receipt, already_processed: true }) : fail(404, 'NOT_FOUND');
    }
    if (path.endsWith('/open') && method === 'POST') {
      if (api.nextPost === 'not-ready') {api.nextPost=null;return fail(503,'NOT_READY');}
      if (api.nextPost === 'fail') { api.nextPost = null; return fail(503, 'SERVICE_UNAVAILABLE'); }
      if (!key) return fail(422, 'VALIDATION_ERROR');
      const lookup = `${owner}:${key}`;
      let receipt = api.receipts.get(lookup);
      if (!receipt) {
        receipt = { open_id: uuid(30 + api.receipts.size), case_id: path.split('/')[3], reward: rewardMeme, cost_khi_van: 0, khi_van_balance: 0, already_processed: false, next_open_at: new Date(Date.now() - 1000).toISOString() };
        state.quantities.set(rewardMeme.id, (state.quantities.get(rewardMeme.id) || 0) + 1); api.receipts.set(lookup, receipt);
      }
      if (api.nextPost === 'lose') { api.nextPost = null; return route.abort('failed'); }
      return send(200, receipt);
    }
    return fail(404, 'NOT_FOUND');
  });
  return api;
}
async function enter(page) { await page.emulateMedia({ reducedMotion: 'reduce' }); await page.goto('/vault'); await expect(page.locator('.vault-item-card')).toHaveCount(2); }
const open = page => page.getByRole('button', { name: 'Mở Rương', exact: true });
const retry = page => page.getByRole('button', { name: 'Kiểm tra / thử lại lượt mở', exact: true });
const rewardCard = page => page.locator('.vault-item-card').filter({ hasText: rewardMeme.display_name });

test('global catalog includes unowned items; inventory is owner-only and receipt patches catalog without a reload', async ({ page, context }) => {
  const api = await transport(context); await enter(page);
  await expect(rewardCard(page)).toContainText('Chưa sở hữu');
  await page.getByRole('button', { name: 'Kho của tôi', exact: true }).click();
  await expect(page.locator('.vault-item-card')).toHaveCount(1); await expect(page.locator('.vault-item-card')).toContainText('×2');
  await page.getByRole('button', { name: 'Bộ Sưu Tập', exact: true }).click(); await expect(rewardCard(page)).toBeVisible();
  const before = api.requests.filter(row => row.path === '/catalog').length;
  await rewardCard(page).locator('img').evaluate(image => { image.dataset.domIdentity = 'preserved'; });
  await open(page).click(); await expect(page.getByRole('dialog')).toContainText('Đã nhận vật phẩm');
  await page.getByRole('button', { name: 'Đóng', exact: true }).click();
  await expect(rewardCard(page)).toContainText('Đã sở hữu');
  await expect(rewardCard(page).locator('img')).toHaveAttribute('data-dom-identity', 'preserved');
  expect(api.requests.filter(row => row.path === '/catalog')).toHaveLength(before);
  const write = api.requests.find(row => row.method === 'POST' && row.path.endsWith('/open'));
  expect(write.csrf).toBe('vault-fixture-csrf'); expect(write.body).toBeNull(); expect(write.key).toMatch(/^[0-9a-f-]{36}$/);
});

test('failed POST never announces a reward; retry checks the same request and grants once', async ({ page, context }) => {
  const api = await transport(context); api.nextPost = 'fail'; await enter(page);
  await open(page).click(); await expect(page.getByRole('alert')).toContainText('Chưa xác nhận');
  await expect(page.getByRole('dialog')).toHaveCount(0); await expect(rewardCard(page)).toContainText('Chưa sở hữu'); expect(api.receipts.size).toBe(0);
  const pending = await page.evaluate(key => JSON.parse(sessionStorage.getItem(key)), storageKey(users[0].id));
  expect(Object.keys(pending).sort()).toEqual(['caseId', 'key', 'owner']);
  await retry(page).click(); await expect(page.getByRole('dialog')).toContainText(rewardMeme.display_name);
  const posts = api.requests.filter(row => row.method === 'POST' && row.path.endsWith('/open'));
  expect(posts.map(row => row.key)).toEqual([pending.key, pending.key]); expect(api.receipts.size).toBe(1);
  expect(api.requests.some(row => row.path === '/vault/opens/by-request' && row.query.key === pending.key)).toBe(true);
});

test('lost response survives reload and another owner without clobbering either pending key', async ({ page, context }) => {
  const api = await transport(context); api.nextPost = 'lose'; await enter(page); await open(page).click(); await expect(retry(page)).toBeVisible();
  const a = await page.evaluate(key => sessionStorage.getItem(key), storageKey(users[0].id)); expect(a).not.toBeNull();
  api.user = users[1]; api.nextPost = 'lose'; await page.reload(); await expect(open(page)).toBeVisible(); await open(page).click(); await expect(retry(page)).toBeVisible();
  const b = await page.evaluate(key => sessionStorage.getItem(key), storageKey(users[1].id)); expect(b).not.toBeNull(); expect(b).not.toBe(a);
  expect(await page.evaluate(key => sessionStorage.getItem(key), storageKey(users[0].id))).toBe(a);
  api.user = users[0]; await page.reload(); await expect(retry(page)).toBeVisible(); await retry(page).click(); await expect(page.getByRole('dialog')).toContainText('Đã nhận vật phẩm');
  expect(await page.evaluate(key => sessionStorage.getItem(key), storageKey(users[0].id))).toBeNull();
  expect(await page.evaluate(key => sessionStorage.getItem(key), storageKey(users[1].id))).toBe(b);
  expect(api.requests.filter(row => row.method === 'POST' && row.path.endsWith('/open'))).toHaveLength(2); expect(api.receipts.size).toBe(2);
});

test('owned background equip/reset synchronize the shell and selection across tabs', async ({ page, context }) => {
  const api = await transport(context); await enter(page);
  const other = await context.newPage(); await enter(other);
  for (const tab of [page, other]) { await tab.getByRole('button', { name: 'Rương Background', exact: true }).click(); await expect(tab.locator('.vault-item-card')).toHaveCount(1); }
  await page.locator('.vault-item-card').click(); await page.getByRole('button', { name: 'Trang bị Background', exact: true }).click();
  await expect(page.locator('.global-background')).toHaveAttribute('data-effect', 'violet-base');
  await expect(other.locator('.global-background')).toHaveAttribute('data-effect', 'violet-base'); await expect(other.locator('.vault-item-card')).toContainText('Đang trang bị');
  await other.getByRole('button', { name: 'Dùng nền mặc định', exact: true }).click();
  await expect(page.locator('.global-background')).toHaveCount(0); await expect(other.locator('.global-background')).toHaveCount(0);
  await expect(page.locator('.vault-item-card')).toContainText('Đã sở hữu');
  expect(api.requests.filter(row => row.method === 'PUT').map(row => row.body)).toEqual([{ asset_id: background.id }, { asset_id: null }]);
});

test('Vault polish retains responsive grid and shows server odds in an accessible closable dialog', async ({ page, context }) => {
  const api = await transport(context); await enter(page);
  await expect(page.getByRole('button',{name:'Mở Rương',exact:true})).toBeVisible();
  await expect(page.getByText('Miễn phí · Không tiêu hao Khí Vận · Phần thưởng do máy chủ xác nhận.',{exact:true})).toHaveCount(0);
  await expect(page.getByText('Danh mục chung cho mọi thành viên. Vật phẩm chưa sở hữu vẫn hiển thị.',{exact:true})).toHaveCount(0);
  for(const [width,columns] of [[375,2],[768,3],[1440,5]]) {
    await page.setViewportSize({width,height:900});
    expect(await page.locator('.vault-card-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length)).toBe(columns);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const geometry=await page.evaluate(()=>{const reel=document.querySelector('.vault-reel-frame').getBoundingClientRect(),collection=document.querySelector('.vault-collection').getBoundingClientRect(),wrapper=getComputedStyle(document.querySelector('.vault-roulette'));return {left:Math.abs(reel.left-collection.left),right:Math.abs(reel.right-collection.right),background:wrapper.backgroundImage,padding:wrapper.padding};});
    expect(geometry.left).toBeLessThan(1);expect(geometry.right).toBeLessThan(1);expect(geometry.background).toBe('none');expect(geometry.padding).toBe('0px');
  }
  const trigger=page.getByRole('button',{name:'Xem tỷ lệ xuất hiện',exact:true});await trigger.click();
  const dialog=page.getByRole('dialog',{name:'Tỷ lệ xuất hiện:'});await expect(dialog).toBeVisible();
  for(const value of ['68.9%','20.0%','10.0%','1.0%','0.1%']) await expect(dialog.getByText(value,{exact:true})).toBeVisible();
  await page.keyboard.press('Escape');await expect(dialog).not.toBeVisible();await expect(trigger).toBeFocused();
  api.oddsUnavailable=true;await trigger.click();await expect(dialog.getByRole('alert')).toContainText('Không tải được tỷ lệ');await expect(dialog.getByText('68.9%',{exact:true})).toHaveCount(0);await dialog.getByRole('button',{name:'Đóng tỷ lệ xuất hiện'}).click();await expect(trigger).toBeFocused();
});

test('expired inventory GET refreshes the session and leaves the private Vault',async({page,context})=>{
 const api=await transport(context);api.expireInventory=true;await page.goto('/vault');await expect(page).toHaveURL(/\/login\?next=%2Fvault$/);await expect(page.locator('.vault-item-card')).toHaveCount(0);
});
test('owned avatar can be equipped and restored to the default avatar',async({page,context})=>{
 const api=await transport(context);await enter(page);await page.locator('.vault-item-card').filter({hasText:ownedMeme.display_name}).click();await page.getByRole('button',{name:'Trang bị Avatar',exact:true}).click();await expect(page.locator('.vault-item-card').filter({hasText:ownedMeme.display_name})).toContainText('Đang trang bị');await page.getByRole('button',{name:'Dùng Avatar mặc định',exact:true}).click();await expect(page.locator('.vault-item-card').filter({hasText:ownedMeme.display_name})).not.toContainText('Đang trang bị');expect(api.requests.filter(row=>row.method==='PUT').map(row=>row.body)).toEqual([{asset_id:ownedMeme.id},{asset_id:null}]);
});

test('incomplete avatar pool stays NOT_READY while a real background case remains selectable',async({page,context})=>{
 const api=await transport(context);api.backgroundOnly=true;await enter(page);await expect(open(page)).toBeDisabled();await expect(page.locator('.vault-chamber-note')).toHaveCount(0);await page.getByRole('button',{name:'Rương Background',exact:true}).click();await expect(open(page)).toBeEnabled();expect(api.requests.filter(row=>row.method==='POST'&&row.path.endsWith('/open'))).toHaveLength(0);
});
test('explicit NOT_READY confirms no award and clears the pending attempt',async({page,context})=>{
 const api=await transport(context);api.nextPost='not-ready';await enter(page);await open(page).click();await expect(page.locator('.vault-error')).toContainText('Rương hiện chưa có đủ vật phẩm để mở.');await expect(open(page)).toBeDisabled();await expect(page.locator('.vault-result')).toHaveCount(0);expect(api.receipts.size).toBe(0);expect(await page.evaluate(key=>sessionStorage.getItem(key),storageKey(users[0].id))).toBeNull();
});

test('background server equipment survives reload, clears at logout and stays owner-scoped',async({page,context})=>{
 const api=await transport(context);await enter(page);await page.getByRole('button',{name:'Rương Background',exact:true}).click();await page.locator('.vault-item-card').click();await page.getByRole('button',{name:'Trang bị Background',exact:true}).click();await expect(page.locator('.global-background')).toHaveAttribute('data-effect','violet-base');await page.reload();await expect(page.locator('.global-background')).toHaveAttribute('data-effect','violet-base');
 await page.locator('[aria-controls="site-account-menu"]').click();await page.getByRole('button',{name:'Đăng xuất',exact:true}).click();await expect(page.locator('.account-avatar')).toHaveCount(0);await expect(page.locator('.global-background')).toHaveCount(0);api.user=users[1];await page.goto('/vault');await expect(page.locator('.vault-item-card')).toHaveCount(2);await expect(page.locator('.global-background')).toHaveCount(0);api.user=users[0];await page.reload();await expect(page.locator('.global-background')).toHaveAttribute('data-effect','violet-base');
});
test('Vault screenshot matrix preserves approved controls, columns and muted sound in VI EN dark light',async({page,context},info)=>{
 await transport(context);await enter(page);
 for(const width of [375,768,1440])for(const theme of ['dark','light'])for(const language of ['vi','en']){
  await page.setViewportSize({width,height:960});if(await page.locator('html').getAttribute('data-theme')!==theme)await page.locator('.u219-tg').click();await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
  if((await page.locator('.u267-cd').textContent()).toLowerCase()!==language){await page.locator('.u267-gb').click();await page.getByRole('option',{name:language==='en'?'English':'Tiếng Việt',exact:true}).click();}
  await expect(page.locator('.vault-item-card')).toHaveCount(2);await expect(page.getByRole('button',{name:language==='en'?'Open Case':'Mở Rương',exact:true})).toBeVisible();await expect(page.locator('.vault-sound-toggle')).toHaveAttribute('aria-pressed','true');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect(await page.locator('.vault-card-grid').evaluate(el=>getComputedStyle(el).gridTemplateColumns.split(' ').length)).toBe(width===375?2:width===768?3:5);
  await page.screenshot({path:info.outputPath('vault-'+width+'-'+theme+'-'+language+'.png'),fullPage:true});
 }
});

test('case network failure is not labelled NOT_READY and can be retried',async({page,context})=>{
 const api=await transport(context);api.casesError=true;await enter(page);await expect(page.locator('.vault-chamber-note')).toContainText('Không tải được rương');await expect(page.locator('.vault-chamber-note')).not.toContainText('NOT_READY');await expect(open(page)).toBeDisabled();api.casesError=false;await page.getByRole('button',{name:'Tải lại rương',exact:true}).click();await expect(open(page)).toBeEnabled();
});

test('MVP sound defaults on and persisted mute survives reload',async({page,context})=>{
 await transport(context);await enter(page);const sound=page.locator('.vault-sound-toggle');await expect(sound).toHaveAttribute('aria-pressed','true');await sound.click();await expect(sound).toHaveAttribute('aria-pressed','false');await page.reload();await expect(sound).toHaveAttribute('aria-pressed','false');await sound.click();await page.reload();await expect(sound).toHaveAttribute('aria-pressed','true');
});
test('MVP 52-card reel stops on the server receipt after 6.2 seconds',async({page,context})=>{
 await transport(context);await enter(page);await page.emulateMedia({reducedMotion:'no-preference'});await open(page).click();await expect(page.locator('.vault-reel.is-spinning')).toBeVisible();await expect(page.locator('.vault-reel-card')).toHaveCount(52);await expect(page.locator('.vault-reel-card').nth(47)).toContainText(rewardMeme.display_name);expect(await page.locator('.vault-reel').evaluate(e=>getComputedStyle(e).animationDuration)).toBe('6.2s');await expect(page.getByRole('dialog')).toContainText(rewardMeme.display_name,{timeout:9000});
});
