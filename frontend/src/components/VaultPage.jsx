import React, { useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { auth } from '../auth.js';
import { usePreferences } from '../PreferencesContext.jsx';
import { apiId, apiPage } from '../social-api.js';
import { vaultAsset, vaultCatalog, vaultCases, vaultReceipt, readPendingOpen, vaultOdds } from '../vault-api.js';
import { createVaultSound } from '../vault-sound.js';
import { buildReelV2, reelOffsets, reelTickTimes, REEL_DURATION_MS } from '../vault-reel-v2.js';
import '../vault-page.css';

async function readVault(path){try{return await auth.read(path)}catch(error){if(error.status===401)auth.refresh().catch(()=>{});throw error;}}

const PENDING_KEY = 'aurameme-vault-pending';
const RARITIES = ['D', 'C', 'B', 'A', 'S'];
function inventoryPage(value) {
  const page = apiPage(value);
  return { ...page, items: page.items.map(item => {
    if (!Number.isSafeInteger(item.quantity) || item.quantity < 1 || typeof item.equipped !== 'boolean') throw Error('PROTOCOL_ERROR');
    return { ...item, asset: vaultAsset(item.asset), owned: true };
  }) };
}
function savePending(value, owner = value?.owner) { try { const key = `${PENDING_KEY}:${owner}`; if (value) sessionStorage.setItem(key, JSON.stringify(value)); else sessionStorage.removeItem(key); } catch { /* The in-memory key still survives retries while this page is open. */ } }
function pendingFor(owner) { try { return readPendingOpen(sessionStorage.getItem(`${PENDING_KEY}:${owner}`), owner); } catch { return null; } }
function AssetImage({ asset }) {
  return asset.image ? <img src={asset.image} alt={asset.display_name} loading="lazy" /> : <span className="vault-no-image" aria-label={asset.display_name}>◇</span>;
}

export default function VaultPage() {
  const session = useSyncExternalStore(auth.subscribe, auth.snapshot);
  const owner = session.user?.id || null;
  const { language = 'vi', reducedMotion } = usePreferences() || {};
  const t = (vi, en) => language === 'en' ? en : vi;
  const [kind, setKind] = useState('avatar'), [scope, setScope] = useState('catalog');
  const [query, setQuery] = useState(''), [search, setSearch] = useState(''), [rarity, setRarity] = useState(''), [page, setPage] = useState(1);
  const [cases, setCases] = useState([]), [casesLoaded, setCasesLoaded] = useState(false), [casesError, setCasesError] = useState(null), [stats, setStats] = useState(null), [equipment, setEquipment] = useState({});
  const [collection, setCollection] = useState(null), [loading, setLoading] = useState(false), [loadError, setLoadError] = useState('');
  const [revision, setRevision] = useState(0), [error, setError] = useState(''), [pending, setPending] = useState(null), [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null), [spinning, setSpinning] = useState(false), [nextAt, setNextAt] = useState(0), [now, setNow] = useState(Date.now());
  const [detail, setDetail] = useState(null), [equipping, setEquipping] = useState(false), [muted, setMuted] = useState(()=>{try{return localStorage.getItem('aurameme-vault-muted')==='1';}catch{return false;}});
  const sound = useRef(null), opening = useRef(false), mounted = useRef(false), pendingRef = useRef(null), timers = useRef([]), dialog = useRef(null);
  const countVersions = useRef({ avatar: 0, background: 0 });
  const equipmentGeneration = useRef(0), ownEquipmentEvent = useRef(null);
  const receiptOwnership = useRef(new Set()), collectionView = useRef({ scope, kind });
  collectionView.current = { scope, kind };
  const currentOwner = useRef(owner); currentOwner.current = owner;
  const oddsDialog = useRef(null), oddsGeneration = useRef(0);
  const [odds, setOdds] = useState(null), [oddsError, setOddsError] = useState(false);
  useEffect(() => { oddsGeneration.current++; oddsDialog.current?.close(); setOdds(null); }, [owner, kind]);
  const readyCase = cases.find(item => item.runtime_kind === kind);
  const waiting = Math.max(0, Math.ceil((nextAt - now) / 1000));
  function clearTimers() { timers.current.forEach(clearTimeout); timers.current = []; }
  useEffect(() => {
    mounted.current = true; sound.current = createVaultSound();
    return () => { mounted.current = false; clearTimers(); sound.current?.dispose(); sound.current = null; };
  }, []);
  useEffect(() => { const timer = setTimeout(() => { setSearch(query.trim()); setPage(1); }, 250); return () => clearTimeout(timer); }, [query]);
  useEffect(() => {
    if (!nextAt) return;
    const timer = setInterval(() => {
      const current = Date.now(); setNow(current);
      if (current >= nextAt) { clearInterval(timer); setNextAt(0); }
    }, 250);
    return () => clearInterval(timer);
  }, [nextAt]);
  useEffect(() => {
    const saved = owner ? pendingFor(owner) : null; pendingRef.current = saved; setPending(saved);
    opening.current = false; setBusy(false); setSpinning(false); setEquipping(false);
    receiptOwnership.current.clear();
    setReceipt(null); setDetail(null); setNextAt(0); setError(''); setStats(null); setEquipment({});
    return clearTimers;
  }, [owner]);
  useEffect(() => {
    if (!owner) return;
    let active = true; setCasesLoaded(false); setCasesError(null);
    readVault('/vault/cases').then(vaultCases).then(value => { if (active) { setCases(value); setCasesLoaded(true); } }).catch(cause => { if (active) { setCases([]); setCasesError(cause); setCasesLoaded(true); } });
    ['avatar', 'background'].forEach(itemKind => refreshCount(itemKind, owner));
    const refreshEquipment = async () => {
      const generation = ++equipmentGeneration.current;
      try {
        const value = await readVault('/inventory/equipment');
        if (!Array.isArray(value?.items)) throw Error('PROTOCOL_ERROR');
        const next = Object.fromEntries(value.items.filter(item => !['frame', 'icon', 'effect'].includes(item?.slot_kind)).map(item => { if (!['avatar', 'background'].includes(item?.slot_kind)) throw Error('PROTOCOL_ERROR'); const asset = vaultAsset(item.asset); if (asset.kind !== item.slot_kind) throw Error('PROTOCOL_ERROR'); return [item.slot_kind, asset.id]; }));
        if (active && generation === equipmentGeneration.current) setEquipment(next);
      } catch { if (active && generation === equipmentGeneration.current) setEquipment({}); }
    };
    const changed = event => { if (event !== ownEquipmentEvent.current) refreshEquipment(); };
    const channel = typeof BroadcastChannel === 'undefined' ? null : new BroadcastChannel('aurameme-equipment');
    if (channel) channel.onmessage = refreshEquipment;
    window.addEventListener('aurameme-equipment-changed', changed); window.addEventListener('focus', refreshEquipment);
    refreshEquipment();
    return () => { active = false; channel?.close(); window.removeEventListener('aurameme-equipment-changed', changed); window.removeEventListener('focus', refreshEquipment); };
  }, [owner]);
  useEffect(() => {
    setCollection(null); setLoadError('');
    if (!owner) return;
    let active = true; setLoading(true);
    const params = new URLSearchParams({ kind, page: String(page), page_size: '15' });
    if (scope === 'catalog') { if (rarity) params.set('rarity', rarity); if (search) params.set('q', search); }
    readVault(`${scope === 'catalog' ? '/catalog' : '/inventory/me'}?${params}`).then(scope === 'catalog' ? vaultCatalog : inventoryPage)
      .then(value => { if (active) setCollection(scope === 'catalog' ? { ...value, items: value.items.map(item => receiptOwnership.current.has(item.asset.id) ? { ...item, owned: true } : item) } : value); }).catch(() => { if (active) setLoadError(t('Không tải được bộ sưu tập. Hãy thử lại.', 'Could not load the collection. Please retry.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [owner, kind, scope, rarity, search, page, revision, language]);
  useEffect(() => { if (detail && !dialog.current?.open) dialog.current?.showModal(); else if (!detail) dialog.current?.close(); }, [detail]);
  useEffect(() => {
    if (!reducedMotion || !spinning || !receipt) return;
    clearTimers(); setSpinning(false); setBusy(false); opening.current = false;
    setDetail({ asset: receipt.reward, owned: true, received: true }); sound.current?.reveal(receipt.reward.rarity);
  }, [reducedMotion, spinning, receipt]);

  async function showOdds() {
    if (!readyCase) return;
    const generation = ++oddsGeneration.current;
    setOdds(null); setOddsError(false); oddsDialog.current.showModal();
    try {
      const value = vaultOdds(await readVault(`/vault/cases/${readyCase.id}`), readyCase.id);
      if (mounted.current && generation === oddsGeneration.current) setOdds(value);
    } catch { if (mounted.current && generation === oddsGeneration.current) setOddsError(true); }
  }
  function chooseKind(value) { setKind(value); setPage(1); setRarity(''); setQuery(''); setReceipt(null); setError(''); }
  function refreshCount(itemKind, requestOwner) {
    const version = ++countVersions.current[itemKind];
    setStats(value => ({ ...value, [itemKind]: null }));
    readVault(`/inventory/me?kind=${itemKind}&page=1&page_size=1`).then(inventoryPage).then(value => {
      if (mounted.current && currentOwner.current === requestOwner && countVersions.current[itemKind] === version) setStats(previous => ({ ...previous, [itemKind]: value.pagination.total }));
    }).catch(() => { /* Keep this counter unknown if its authoritative read fails. */ });
  }
  function failMessage(cause) {
    if (cause?.code === 'NOT_READY') return t('Rương hiện chưa có đủ vật phẩm để mở.', 'This case does not have enough items yet.');
    if (cause?.status === 429) return t('Vui lòng chờ trước khi thử lại lượt mở này.', 'Please wait before retrying this opening.');
    if (cause?.status === 401) return t('Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.', 'Your session expired. Please sign in again.');
    return t('Chưa xác nhận được kết quả. Thử lại để kiểm tra cùng lượt mở; hệ thống không tạo lượt mới.', 'The result is not confirmed. Retry to check the same opening; this will not create a new draw.');
  }
  async function openChest() {
    if (!owner || opening.current || waiting || (!readyCase && !pendingRef.current)) return;
    clearTimers(); if (!muted) sound.current?.unlock(); sound.current?.setMuted(muted);
    opening.current = true; setBusy(true); setError(''); setReceipt(null);
    const requestOwner = owner;
    const wasPending = pendingRef.current;
    const request = wasPending || { owner, caseId: readyCase.id, key: crypto.randomUUID() };
    pendingRef.current = request; setPending(request); savePending(request);
    try {
      let response;
      if (wasPending) {
        try { response = await readVault(`/vault/opens/by-request?key=${encodeURIComponent(request.key)}`); }
        catch (cause) { if (cause.status !== 404) throw cause; }
      }
      if (!response) response = await auth.write('POST', `/vault/cases/${request.caseId}/open`, undefined, { idempotencyKey: request.key });
      const confirmed = vaultReceipt(response);
      if (confirmed.case_id !== request.caseId) throw Error('PROTOCOL_ERROR');
      if (!mounted.current || currentOwner.current !== requestOwner) return;
      savePending(null, requestOwner); pendingRef.current = null; setPending(null); setReceipt(confirmed); setNow(Date.now()); setNextAt(confirmed.next_open_at ? Date.parse(confirmed.next_open_at) : 0);
      refreshCount(confirmed.reward.kind, requestOwner);
      receiptOwnership.current.add(confirmed.reward.id);
      if (collectionView.current.scope === 'inventory') {
        if (collectionView.current.kind === confirmed.reward.kind) setRevision(value => value + 1);
      } else setCollection(value => value ? { ...value, items: value.items.map(item => item.asset.id === confirmed.reward.id ? { ...item, owned: true } : item) } : value);
      const finish = () => {
        if (!mounted.current || currentOwner.current !== requestOwner) return;
        clearTimers();
        setSpinning(false); setBusy(false); opening.current = false;
        setDetail({ asset: confirmed.reward, owned: true, received: true }); sound.current?.reveal(confirmed.reward.rarity); window.dispatchEvent(new Event('aurameme:aura:invalidate'));
      };
      if (reducedMotion) finish();
      else {
        setSpinning(true);
        for (const ms of reelTickTimes(47, REEL_DURATION_MS)) timers.current.push(setTimeout(() => sound.current?.tick(), ms));
        timers.current.push(setTimeout(finish, REEL_DURATION_MS));
      }
    } catch (cause) {
      if (!mounted.current || currentOwner.current !== requestOwner) return;
      if (cause.code === 'NOT_READY') {savePending(null, requestOwner); pendingRef.current = null; setPending(null); setCases(value => value.filter(item => item.id !== request.caseId));}
      if (cause.status === 429) { const delay = Number(cause.retryAfter); setNextAt(cause.nextOpenAt ? Date.parse(cause.nextOpenAt) : Date.now() + (Number.isFinite(delay) ? delay : 2) * 1000); setNow(Date.now()); }
      setError(failMessage(cause)); setBusy(false); opening.current = false;
    }
  }
  async function equip(asset, reset = false) {
    if (!owner || equipping) return;
    const requestOwner = owner; setEquipping(true); setError('');
    try {
      const slot = reset ? kind : asset.kind;
      const assetId = reset ? null : apiId(asset.id);
      const result = await auth.write('PUT', `/inventory/equipment/${slot}`, { asset_id: assetId });
      if (result?.slot_kind !== slot || result.asset_id !== assetId) throw Error('PROTOCOL_ERROR');
      if (!mounted.current || currentOwner.current !== requestOwner) return;
      equipmentGeneration.current++;
      setEquipment(value => ({ ...value, [slot]: result.asset_id }));
      if (slot === 'avatar') await auth.refresh().catch(() => {});
      const event = new Event('aurameme-equipment-changed'); ownEquipmentEvent.current = event;
      window.dispatchEvent(event); ownEquipmentEvent.current = null;
      setRevision(value => value + 1); setDetail(null);
    } catch { if (mounted.current && currentOwner.current === requestOwner) setError(t('Không thể trang bị. Vui lòng thử lại.', 'Could not equip this item. Please retry.')); }
    finally { if (mounted.current && currentOwner.current === requestOwner) setEquipping(false); }
  }
  const assets = (collection?.items || []).map(item => item.asset).filter(asset => asset.available);
  const reelData = useMemo(()=>receipt ? buildReelV2(assets, receipt.reward) : {items: assets.slice(0,9), winnerIndex: Math.floor(Math.min(9,assets.length)/2)}, [collection,receipt?.open_id,kind]);
  const reelAssets = reelData.items;
  const offsets = reelAssets.length ? reelOffsets(reelAssets.length,reelData.winnerIndex) : {startPx:0,endPx:0};
  return <main className="vault-page"><div className="vault-content">
    <header className="vault-hero"><svg className="vault-hero-atmosphere" aria-hidden="true" width="100%" height="100%"><defs><pattern id="vault-page-circuits" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M 10 10 L 40 10 L 40 40 M 70 20 L 70 70 L 30 70 M 0 50 L 20 50 L 35 65" fill="none" stroke="currentColor" strokeOpacity=".3" strokeWidth="1" /><circle cx="10" cy="10" r="2" fill="currentColor" opacity=".6" /><circle cx="40" cy="40" r="2" fill="currentColor" opacity=".6" /><circle cx="70" cy="70" r="2" fill="currentColor" opacity=".6" /></pattern><radialGradient id="vault-page-header-glow" cx="80%" cy="30%" r="60%"><stop offset="0%" stopColor="#4cd7f6" stopOpacity=".3" /><stop offset="60%" stopColor="#d0bcff" stopOpacity=".1" /><stop offset="100%" stopColor="#12131b" stopOpacity="0" /></radialGradient></defs><rect width="100%" height="100%" fill="url(#vault-page-circuits)" /><rect width="100%" height="100%" fill="url(#vault-page-header-glow)" /></svg><div><h1>{t('Bảo Khố', 'Aura Vault')}</h1><p>{t('Khám phá, sưu tập và trang bị dấu ấn Aura của riêng bạn.', 'Discover, collect and equip your own Aura signature.')}</p></div>
      <div className="vault-stats">{[[t('Tổng sở hữu', 'Total owned'), Number.isSafeInteger(stats?.avatar) && Number.isSafeInteger(stats?.background) ? stats.avatar + stats.background : '—'], [t('Bộ Meme', 'Memes'), stats?.avatar ?? '—'], [t('Background', 'Backgrounds'), stats?.background ?? '—']].map(([label, value]) => <div key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    </header>
    {!owner ? <p className="vault-empty" role="status">{session.status === 'loading' ? t('Đang kiểm tra phiên đăng nhập…', 'Checking your session…') : <a href="/login">{t('Đăng nhập để khám phá Bảo Khố.', 'Sign in to explore the Vault.')}</a>}</p> : <>
      <section className="vault-chamber" aria-label={t('Mở rương', 'Open a case')}>
        <div className="vault-chamber-tools"><div className="vault-case-tabs" role="group" aria-label={t('Loại rương', 'Case type')}>{['avatar', 'background'].map(value => <button type="button" key={value} aria-pressed={kind === value} disabled={busy} onClick={() => chooseKind(value)}><span aria-hidden="true" className="material-symbols-outlined">{value === 'avatar' ? 'view_carousel' : 'wallpaper'}</span>{value === 'avatar' ? t('Rương Meme', 'Meme case') : t('Rương Background', 'Background case')}</button>)}</div>
          <button type="button" className="vault-sound-toggle" aria-pressed={!muted} onClick={() => { const value = !muted; if (!value) sound.current?.unlock(); sound.current?.setMuted(value); setMuted(value);try{localStorage.setItem('aurameme-vault-muted',value?'1':'0')}catch{}}}>{muted ? t('Âm thanh: Tắt', 'Sound: Off') : t('Âm thanh: Bật', 'Sound: On')}</button>
        </div>
        <div className="vault-roulette"><div className="vault-reel-frame"><div className="vault-needle" aria-hidden="true" />
          {reelAssets.length ? <div className={`vault-reel${spinning ? ' is-spinning' : ''}`} style={{ '--reel-start': `${offsets.startPx}px`, '--reel-end': `${offsets.endPx}px`, '--reel-offset': `${offsets.endPx}px` }} aria-hidden="true">{reelAssets.map((asset, index) => <div className="vault-reel-card" data-rarity={asset.rarity} key={`${asset.id}-${index}`}><AssetImage asset={asset} /><strong>{asset.display_name}</strong></div>)}</div> : <p className="vault-empty">{t('Chưa có vật phẩm được duyệt để xem trước.', 'No approved items are available to preview.')}</p>}
        </div>
          <button className="vault-open-button" type="button" disabled={busy || waiting > 0 || (!readyCase && !pending)} onClick={openChest}><span className="material-symbols-outlined" aria-hidden="true">auto_awesome</span>{busy ? t('Đang mở…', 'Opening…') : waiting ? `${t('Chờ', 'Wait')} ${waiting}s` : pending ? t('Kiểm tra / thử lại lượt mở', 'Check / retry opening') : t('Mở Rương', 'Open Case')}</button>
        </div>
          {casesError && casesError.code !== 'NOT_READY' && <p className="vault-chamber-note" role="alert">{t('Không tải được rương. Vui lòng thử lại.', 'Could not load cases. Please retry.')} <button type="button" onClick={() => location.reload()}>{t('Tải lại rương', 'Reload cases')}</button></p>}
        {(!casesLoaded || pending) && <p className="vault-visually-hidden" role="status">{!casesLoaded ? t('Đang tải rương…','Loading cases…') : t('Đang kiểm tra kết quả lượt mở trước.','Checking the previous opening.')}</p>}
          {receipt && !spinning && <p className="vault-result" role="status">{t('Đã nhận', 'Received')}: <strong>{receipt.reward.display_name}</strong> · {receipt.reward.rarity}</p>}
      </section>
      {error && <p className="vault-error" role="alert">{error}</p>}
      <section className="vault-collection" aria-labelledby="vault-collection-title"><div className="vault-collection-tools"><div className="vault-collection-heading"><h2 id="vault-collection-title">{scope === 'catalog' ? t('Bộ Sưu Tập', 'Collection') : t('Kho của tôi', 'My inventory')}</h2>{scope === 'catalog' && <button type="button" className="vault-odds-trigger" aria-label={t('Xem tỷ lệ xuất hiện', 'View drop rates')} aria-haspopup="dialog" disabled={!readyCase} onClick={showOdds}>?</button>}</div>
        <div className="vault-collection-actions"><button type="button" onClick={() => { setScope(scope === 'catalog' ? 'inventory' : 'catalog'); setPage(1); }}>{scope === 'catalog' ? t('Kho của tôi', 'My inventory') : t('Bộ Sưu Tập', 'Collection')}</button>{scope === 'catalog' && <input type="search" aria-label={t('Tìm kiếm vật phẩm', 'Search items')} placeholder={t('Tìm kiếm vật phẩm…', 'Search items…')} value={query} onChange={event => setQuery(event.target.value)} />}</div>
      </div>
        {scope === 'catalog' && <div className="vault-rarity-filters" role="group" aria-label={t('Độ hiếm', 'Rarity')}>{['', ...RARITIES].map(value => <button type="button" key={value} aria-pressed={rarity === value} onClick={() => { setRarity(value); setPage(1); }}>{value ? `${t('Hạng', 'Tier')} ${value}` : t('Tất cả', 'All')}</button>)}</div>}
        {kind === 'avatar' && <div className="vault-reset"><button type="button" disabled={equipping || !equipment.avatar} onClick={() => equip(null, true)}>{t('Dùng Avatar mặc định', 'Use default avatar')}</button></div>}
        {kind === 'background' && <div className="vault-reset"><span>{t('Background xem trước bằng ảnh tĩnh.', 'Background previews are static images.')}</span><button type="button" disabled={equipping || !equipment.background} onClick={() => equip(null, true)}>{t('Dùng nền mặc định', 'Use default background')}</button></div>}
        {loading ? <p className="vault-empty" role="status">{t('Đang tải…', 'Loading…')}</p> : loadError ? <div className="vault-empty" role="alert"><p>{loadError}</p><button type="button" onClick={() => setRevision(value => value + 1)}>{t('Thử lại', 'Retry')}</button></div> : !collection?.items.length ? <p className="vault-empty">{scope === 'inventory' ? t('Bạn chưa sở hữu vật phẩm nào trong mục này.', 'You do not own any items in this category yet.') : t('Chưa có vật phẩm phù hợp trong danh mục đã duyệt.', 'No matching approved catalog items yet.')}</p> : <div className="vault-card-grid">{collection.items.map(item => <button type="button" className="vault-item-card" data-rarity={item.asset.rarity} key={item.asset.id} onClick={() => { setError(''); setDetail(item); }}><div className="vault-item-image"><AssetImage asset={item.asset} /></div><div className="vault-item-label"><h3>{item.asset.display_name}</h3><span className="vault-rarity">{t('Hạng', 'Tier')} {item.asset.rarity}</span></div><small>{equipment[item.asset.kind] === item.asset.id ? t('Đang trang bị', 'Equipped') : item.owned ? t('Đã sở hữu', 'Owned') : t('Chưa sở hữu', 'Not owned')}{item.quantity ? ` · ×${item.quantity}` : ''}</small></button>)}</div>}
        {collection && collection.pagination.total_pages > 1 && <nav className="vault-pagination" aria-label={t('Phân trang bộ sưu tập', 'Collection pages')}><button type="button" disabled={page <= 1 || loading} onClick={() => setPage(value => value - 1)}>{t('Trước', 'Previous')}</button><span>{page} / {collection.pagination.total_pages}</span><button type="button" disabled={page >= collection.pagination.total_pages || loading} onClick={() => setPage(value => value + 1)}>{t('Sau', 'Next')}</button></nav>}
      </section>
    </>}
    <dialog ref={oddsDialog} className="vault-odds" aria-labelledby="vault-odds-title" onClose={() => { oddsGeneration.current++; }}><div className="vault-odds-heading"><h2 id="vault-odds-title"><span className="material-symbols-outlined" aria-hidden="true">pie_chart</span>{t('Tỷ lệ xuất hiện:', 'Drop rates:')}</h2><button type="button" aria-label={t('Đóng tỷ lệ xuất hiện', 'Close drop rates')} onClick={() => oddsDialog.current.close()}>×</button></div>{oddsError ? <p role="alert">{t('Không tải được tỷ lệ. Vui lòng đóng và thử lại.', 'Could not load drop rates. Please close and retry.')}</p> : !odds ? <p role="status">{t('Đang tải tỷ lệ…', 'Loading drop rates…')}</p> : <div className="vault-odds-grid">{odds.map(row => <div className="vault-odds-card" data-rarity={row.rarity} key={row.rarity}><strong>{t('Hạng', 'Tier')} {row.rarity}</strong><div><b>{row.percent}%</b><i aria-hidden="true" /></div><span className="vault-odds-track" aria-hidden="true"><span style={{ width: `${row.percent}%` }} /></span></div>)}</div>}</dialog>
    <dialog ref={dialog} className="vault-detail" aria-labelledby="vault-detail-title" onCancel={() => setDetail(null)} onClose={() => setDetail(null)}>{detail && <><div className="vault-detail-bar"><span className="vault-rarity" data-rarity={detail.asset.rarity}>{t('Hạng', 'Tier')} {detail.asset.rarity}</span><button type="button" aria-label={t('Đóng', 'Close')} onClick={() => setDetail(null)}>×</button></div><div className="vault-detail-main"><div className="vault-detail-image"><AssetImage asset={detail.asset} /></div><div><p className="vault-detail-kicker">{detail.received ? t('Đã nhận vật phẩm', 'Item received') : detail.owned ? t('Đã sở hữu', 'Owned') : t('Bộ Sưu Tập', 'Collection')}</p><h2 id="vault-detail-title">{detail.asset.display_name}</h2>{detail.quantity && <p>{t('Số lượng sở hữu', 'Quantity owned')}: ×{detail.quantity}</p>}<p>{detail.asset.kind === 'avatar' ? t('Meme đã sở hữu có thể trang bị làm Avatar và dùng làm Reaction.', 'Owned memes can be equipped as your avatar and used as reactions.') : t('Trang bị để áp dụng nền cho tài khoản của bạn trên toàn website.', 'Equip to apply this background to your account across the website.')}</p></div></div>{detail.owned && <button className="vault-equip-button" type="button" disabled={equipping || equipment[detail.asset.kind] === detail.asset.id || !detail.asset.available} onClick={() => equip(detail.asset)}>{equipping ? t('Đang trang bị…', 'Equipping…') : equipment[detail.asset.kind] === detail.asset.id ? t('Đang trang bị', 'Equipped') : detail.asset.kind === 'avatar' ? t('Trang bị Avatar', 'Equip avatar') : t('Trang bị Background', 'Equip background')}</button>}{error && <p className="vault-error" role="alert">{error}</p>}</>}</dialog>
  </div></main>;
}
