import { expect, test, type Page } from '@playwright/test';
const id = '00000000-0000-0000-0000-000000000011';
const asset = { id: '00000000-0000-0000-0000-000000000012', slug: 'server-selected-icon', kind: 'icon', rarity: 'D', media_url: '/assets/illustrations/brand-placeholder.svg' };
const pagination = { page: 1, page_size: 20, total: 1, total_pages: 1 };
const caseItem = { id, slug: 'common', label: 'Synthetic common case', cost_khi_van: 3, status: 'active' };
async function setup(page: Page, empty = false) {
  await page.route('**/api/v1/users/me', r => r.fulfill({ json: { id: 'fixture-owner', username: 'fixture', display_name: 'Synthetic Owner', roles: ['USER'], status: 'active' } }));
  await page.route('**/api/v1/auth/csrf', r => r.fulfill({ json: { csrf_token: 'fixture-only' } }));
  await page.route('**/api/v1/vault/cases?*', r => r.fulfill({ json: { items: empty ? [] : [caseItem], pagination: { ...pagination, total: empty ? 0 : 1 } } }));
  await page.route('**/api/v1/vault/cases/' + id, r => r.fulfill({ json: { case: caseItem, bands: [{ min_earned_xp: 0, max_earned_xp: null, odds_version: 1, weights_bps: { D: 6000, C: 2500, B: 1000, A: 450, S: 50 } }] } }));
  await page.route('**/api/v1/inventory/me?*', r => r.fulfill({ json: { items: [], pagination: { ...pagination, total: 0, total_pages: 0 } } }));
}
for (const width of [375, 768, 1024, 1440]) {
  test(`Vault API empty state fits ${width}px without pretending rewards`, async ({ page }) => {
    await setup(page, true); await page.setViewportSize({ width, height: 900 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/vault');
    await expect(page.getByRole('heading', { name: 'Vault', exact: true })).toBeVisible();
    await expect(page.getByText('No cases have been published.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open case', exact: true })).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.screenshot({ path: test.info().outputPath(`vault-${width}.png`), fullPage: true });
  });
}
test('503 never shows a reward and reload preserves per-user intent key', async ({ page }) => {
  await setup(page); const keys: (string | undefined)[] = [];
  await page.route('**/api/v1/vault/cases/' + id + '/open', r => { keys.push(r.request().headers()['idempotency-key']); return r.fulfill({ status: 503, json: { error: { code: 'NOT_READY' } } }); });
  await page.goto('/vault'); await page.getByRole('button', { name: 'Open case', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('not ready');
  await expect(page.getByRole('heading', { name: 'Reward confirmed' })).toHaveCount(0);
  await page.reload(); await expect(page.getByRole('button', { name: 'Recover last opening' })).toBeVisible();
  expect(keys).toHaveLength(1); await page.getByRole('button', { name: 'Recover last opening' }).click();
  await expect.poll(() => keys.length).toBe(2); expect(keys[0]).toBe(keys[1]); expect(keys[0]?.length).toBeGreaterThanOrEqual(12);
});
test('server reward is authoritative with keyboard, reduced motion and recovery', async ({ page }) => {
  await setup(page); await page.emulateMedia({ reducedMotion: 'reduce' }); const keys: (string | undefined)[] = [];
  await page.route('**/api/v1/vault/cases/' + id + '/open', r => { keys.push(r.request().headers()['idempotency-key']); return r.fulfill({ json: { open_id: 'fixture-open', case_id: id, reward: asset, cost_khi_van: 0, khi_van_balance: 10, already_processed: keys.length > 1 } }); });
  await page.goto('/vault'); await page.getByRole('button', { name: 'Open case', exact: true }).focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Reward confirmed' })).toBeFocused();
  await expect(page.getByText('server-selected-icon', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Skip animation' })).toHaveCount(0);
  expect(await page.locator('[data-reward]').evaluate(e => e.getAnimations().filter(a => a.playState === 'running').length)).toBe(0);
  await page.reload(); await page.getByRole('button', { name: 'Recover last opening' }).click();
  await expect(page.getByText('Recovered server result.')).toBeVisible(); expect(keys[0]).toBe(keys[1]);
});

test('skip animation keeps the server result and keyboard focus', async ({ page }) => {
  await setup(page); await page.emulateMedia({ reducedMotion: 'no-preference' });
  await page.route('**/api/v1/vault/cases/' + id + '/open', r => r.fulfill({ json: { open_id: 'fixture-skip', case_id: id, reward: asset, cost_khi_van: 0, khi_van_balance: 10, already_processed: false } }));
  await page.goto('/vault'); await expect(page.getByRole('button', { name: 'Open case', exact: true })).toBeVisible();
  await page.clock.install(); await page.clock.pauseAt(new Date(Date.now()+1000));
  await page.getByRole('button', { name: 'Open case', exact: true }).click();
  await page.getByRole('button', { name: 'Skip animation' }).click();
  await expect(page.getByRole('heading', { name: 'Reward confirmed' })).toBeFocused();
  await expect(page.getByText('server-selected-icon', { exact: true })).toBeVisible();
});
test('duplicate clicks send one intent and blocked retry storage sends nothing', async ({ page }) => {
  await setup(page); let requests = 0;
  await page.route('**/api/v1/vault/cases/' + id + '/open', async r => { requests++; await new Promise(resolve => setTimeout(resolve,100)); return r.fulfill({ status:503,json:{error:{code:'NOT_READY'}} }); });
  await page.goto('/vault'); const open = page.getByRole('button',{name:'Open case',exact:true});
  await open.evaluate(button => { (button as HTMLButtonElement).click(); (button as HTMLButtonElement).click(); });
  await expect(page.getByRole('alert')).toContainText('not ready'); expect(requests).toBe(1);
  await page.addInitScript(() => { Storage.prototype.setItem = () => { throw new DOMException('Storage blocked'); }; });
  await page.reload(); await page.getByRole('button',{name:'Recover last opening'}).click();
  await expect(page.getByRole('alert')).toContainText('Opening was not sent'); expect(requests).toBe(1);
});
test('equipment state changes only after the server confirms it', async ({ page }) => {
  await setup(page); let equipped = false; const bodies: unknown[] = [];
  await page.route('**/api/v1/inventory/me?*', r => r.fulfill({json:{items:[{asset,quantity:1,equipped}],pagination}}));
  await page.route('**/api/v1/inventory/equipment/icon', async r => { const body = r.request().postDataJSON(); bodies.push(body); equipped = body.asset_id !== null; return r.fulfill({json:{slot_kind:'icon',asset_id:body.asset_id}}); });
  await page.goto('/vault'); await page.getByRole('button',{name:'Equip server-selected-icon',exact:true}).click();
  await page.getByRole('button',{name:'Unequip server-selected-icon',exact:true}).click();
  await expect(page.getByRole('button',{name:'Equip server-selected-icon',exact:true})).toBeVisible();
  expect(bodies).toEqual([{asset_id:asset.id},{asset_id:null}]);
});

for (const width of [375,1440]) {
  test(`published fixture odds and long server reward fit ${width}px`, async ({page}) => {
    await setup(page); await page.setViewportSize({width,height:900}); await page.emulateMedia({reducedMotion:'reduce'});
    const longAsset = {...asset,slug:'server-'+ 'long'.repeat(20)};
    await page.route('**/api/v1/vault/cases/'+id+'/open',r=>r.fulfill({json:{open_id:'fixture-layout',case_id:id,reward:longAsset,cost_khi_van:0,khi_van_balance:10,already_processed:false}}));
    await page.goto('/vault'); const odds=page.getByRole('region',{name:'Published case odds'});
    await odds.focus(); await expect(odds).toBeFocused();
    if(width===375) expect(await odds.evaluate(e=>e.scrollWidth>e.clientWidth)).toBe(true);
    await page.getByRole('button',{name:'Open case',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Reward confirmed'})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await page.evaluate(() => { (document.activeElement as HTMLElement)?.blur(); window.scrollTo(0,0); });
    await page.screenshot({path:test.info().outputPath(`vault-fixture-filled-${width}.png`),fullPage:true});
  });
}
test('logout cancels an equipment mutation still waiting for CSRF', async ({page}) => {
  await setup(page); let csrfSeen=false, release=()=>{}, puts=0;
  await page.route('**/api/v1/inventory/me?*',r=>r.fulfill({json:{items:[{asset,quantity:1,equipped:false}],pagination}}));
  await page.route('**/api/v1/auth/csrf',async r=>{
    if(!csrfSeen){csrfSeen=true;await new Promise<void>(resolve=>{release=resolve;});}
    try{await r.fulfill({json:{csrf_token:'fixture-only'}});}catch{/* Request may have been canceled on logout. */}
  });
  await page.route('**/api/v1/auth/logout',r=>r.fulfill({status:204}));
  await page.route('**/api/v1/inventory/equipment/icon',r=>{puts++;return r.fulfill({json:{slot_kind:'icon',asset_id:asset.id}});});
  await page.goto('/vault'); await page.getByRole('button',{name:'Equip server-selected-icon',exact:true}).click();
  await expect.poll(()=>csrfSeen).toBe(true);
  await page.getByRole('button',{name:'Sign out',exact:true}).click();
  await expect(page.getByRole('link',{name:'Sign in to view your collection'})).toBeVisible();
  release();await page.waitForLoadState('networkidle');expect(puts).toBe(0);
});
