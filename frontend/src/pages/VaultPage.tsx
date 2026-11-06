import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, ApiError, errorMessage } from '../api';
import type { Page } from '../blog';
import { Pagination } from '../components/Pagination';
import { useAuth } from '../context/AuthContext';
import { useResource } from '../hooks/useResource';
import type { Asset, CaseDefinition, CaseDetail, InventoryItem, OpenResult } from '../types/vault';

function AssetPreview({ asset }: { asset: Asset }) {
  const [failed, setFailed] = useState(false);
  return <div className="h-24 w-24 shrink-0 rounded-xl grid place-items-center bg-surface-container-high border border-primary/20 overflow-hidden">
    {failed ? <span className="text-xs p-2 text-on-surface-variant">Image unavailable</span> : <img src={asset.media_url} alt="" className="max-h-full max-w-full object-contain" onError={() => setFailed(true)} />}
  </div>;
}
const amount = (value: number) => Number.isSafeInteger(value) && value >= 0;

export function VaultPage() {
  const auth = useAuth();
  const cases = useResource<Page<CaseDefinition>>('/vault/cases?page=1&page_size=20');
  const [selected, setSelected] = useState('');
  const [inventoryPage, setInventoryPage] = useState(1);
  const accountReady = !!auth.user && !auth.pending && !auth.error;
  const inventory = useResource<Page<InventoryItem>>(accountReady ? `/inventory/me?page=${inventoryPage}&page_size=20` : null);
  const detail = useResource<CaseDetail>(selected ? '/vault/cases/' + selected : null);
  const storageKey = accountReady && selected ? `aurameme:open:${auth.user!.id}:${selected}` : '';
  const activeKey = useRef(storageKey); activeKey.current = storageKey;
  const operation = useRef<AbortController | null>(null);
  const equipmentOperation = useRef<AbortController | null>(null);
  const [requestKey, setRequestKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [equipBusy, setEquipBusy] = useState(false);
  const [fault, setFault] = useState('');
  const [receipt, setReceipt] = useState<{ key: string; value: OpenResult } | null>(null);
  const result = receipt?.key === storageKey ? receipt.value : null;
  const [animate, setAnimate] = useState(false);
  const rewardHeading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    equipmentOperation.current?.abort(); equipmentOperation.current = null; setEquipBusy(false);
    return () => equipmentOperation.current?.abort();
  }, [auth.user?.id]);
  useEffect(() => { if (cases.data && !cases.data.items.some(c => c.id === selected)) setSelected(cases.data.items[0]?.id ?? ''); }, [cases.data, selected]);
  useEffect(() => {
    operation.current?.abort(); operation.current = null; setBusy(false); setReceipt(null); setFault(''); setAnimate(false);
    try { setRequestKey(storageKey ? sessionStorage.getItem(storageKey) : null); }
    catch { setRequestKey(null); setFault('Retry storage is unavailable. Opening will not be sent.'); }
    return () => operation.current?.abort();
  }, [storageKey]);
  useEffect(() => { if (result) rewardHeading.current?.focus(); }, [result?.open_id]);
  useEffect(() => { if (!animate) return; const timer = window.setTimeout(() => setAnimate(false), 750); return () => window.clearTimeout(timer); }, [animate]);

  async function open(fresh: boolean) {
    if (!storageKey || operation.current || !detail.data) return;
    const keyAtStart = storageKey, controller = new AbortController();
    operation.current = controller; setBusy(true); setFault('');
    try {
      const key = fresh || !requestKey ? crypto.randomUUID() : requestKey;
      // Persist only the per-user intent key, never credentials or a fabricated result.
      try { sessionStorage.setItem(keyAtStart, key); } catch { throw new Error('Cannot preserve retry key. Opening was not sent.'); }
      setRequestKey(key);
      const value = await api<OpenResult>(`/vault/cases/${selected}/open`, { method: 'POST', idempotencyKey: key, signal: controller.signal });
      if (controller.signal.aborted || activeKey.current !== keyAtStart) return;
      if (value.case_id !== selected || !amount(value.cost_khi_van) || !amount(value.khi_van_balance)) throw new Error('Unsupported server result. Preserve the retry key and contact the owner.');
      setReceipt({ key: keyAtStart, value }); setAnimate(!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
      inventory.reload();
    } catch (error) {
      if (!controller.signal.aborted && activeKey.current === keyAtStart) {
        setFault(errorMessage(error));
        if (error instanceof ApiError && error.status === 401) void auth.refresh();
      }
    } finally { if (operation.current === controller) { operation.current = null; setBusy(false); } }
  }
  async function equip(item: InventoryItem) {
    if (equipmentOperation.current || !accountReady || item.asset.kind === 'generator') return;
    const controller = new AbortController();
    equipmentOperation.current = controller; setEquipBusy(true); setFault('');
    try {
      await api('/inventory/equipment/' + item.asset.kind, { method: 'PUT', signal: controller.signal, body: { asset_id: item.equipped ? null : item.asset.id } });
      if (!controller.signal.aborted) inventory.reload();
    } catch (error) {
      if (!controller.signal.aborted) {
        setFault(errorMessage(error));
        if (error instanceof ApiError && error.status === 401) void auth.refresh();
      }
    } finally { if (equipmentOperation.current === controller) { equipmentOperation.current = null; setEquipBusy(false); } }
  }
  return <section className="max-w-6xl w-full mx-auto px-4 py-10 min-w-0">
    <div className="surface-panel rounded-2xl border border-primary/25 bg-gradient-to-br from-primary/10 via-surface-container-low to-secondary/10 p-6 sm:p-10">
      <p className="text-xs tracking-widest text-secondary uppercase">Catalog & collection preview</p>
      <h1 className="text-4xl font-bold mt-3">Vault</h1>
      <p className="mt-4 max-w-2xl text-on-surface-variant">Explore published cases and your owned items. Opening and rewards remain unavailable until policies and assets are approved.</p>
    </div>
    {fault && <p role="alert" className="my-5 p-4 rounded-lg border border-error text-error">{fault}</p>}
    <div className="grid lg:grid-cols-2 gap-6 mt-8 min-w-0">
      <section className="rounded-xl p-5 bg-surface-container-low min-w-0" aria-labelledby="cases-heading">
        <h2 id="cases-heading" className="text-2xl font-bold">Cases</h2>
        {cases.pending ? <p role="status" className="mt-4">Loading cases…</p> : cases.error ? <><p role="alert">{cases.error}</p><button className="underline min-h-11" onClick={cases.reload}>Retry cases</button></> : !cases.data?.items.length ? <p className="mt-4 text-on-surface-variant">No cases have been published.</p> : <>
          <div className="flex flex-wrap gap-3 my-4">{cases.data.items.map(item => <button key={item.id} aria-pressed={selected === item.id} className="min-h-11 px-4 py-3 rounded-lg border border-primary/40 break-words min-w-0 max-w-full" onClick={() => setSelected(item.id)}>{item.label}</button>)}</div>
          {detail.pending ? <p role="status">Loading odds…</p> : detail.error ? <><p role="alert">{detail.error}</p><button className="underline min-h-11" onClick={detail.reload}>Retry odds</button></> : detail.data && <>
            <p>Listed cost: {amount(detail.data.case.cost_khi_van) ? detail.data.case.cost_khi_van : 'Unavailable'} Khí Vận. The server determines any free quota and final debit.</p>
            <div className="mt-4 overflow-x-auto" role="region" aria-label="Published case odds" tabIndex={0}><table className="w-full text-sm min-w-80">
              <caption className="text-left mb-2">Odds by earned XP, excluding bonus</caption><thead><tr><th className="text-left p-2">Band / version</th>{['D','C','B','A','S'].map(x => <th key={x} className="p-2">{x}</th>)}</tr></thead>
              <tbody>{detail.data.bands.map(b => <tr key={b.min_earned_xp}><th className="text-left p-2">{b.min_earned_xp}–{b.max_earned_xp ?? '∞'} / v{b.odds_version}</th>{(['D','C','B','A','S'] as const).map(x => <td key={x} className="p-2">{b.weights_bps[x] / 100}%</td>)}</tr>)}</tbody>
            </table></div>
            {accountReady ? <button className="mt-5 min-h-11 px-5 py-3 rounded-lg bg-primary text-on-primary disabled:opacity-50" disabled={busy || !amount(detail.data.case.cost_khi_van)} onClick={() => void open(!!result)}>{busy ? 'Waiting for server…' : result ? 'Open another case' : requestKey ? 'Recover last opening' : 'Open case'}</button> : <Link className="inline-flex min-h-11 items-center mt-4 text-secondary underline" to="/login">Sign in to use the Vault</Link>}
          </>}
        </>}
      </section>
      <section className="rounded-xl p-5 bg-surface-container-low min-w-0" aria-labelledby="inventory-heading">
        <h2 id="inventory-heading" className="text-2xl font-bold">Your collection</h2>
        {auth.pending ? <p role="status">Checking session…</p> : auth.error ? <><p role="alert">{auth.error}</p><button className="min-h-11 underline" onClick={() => void auth.refresh()}>Retry session</button></> : !auth.user ? <Link className="inline-flex min-h-11 items-center underline text-secondary" to="/login">Sign in to view your collection</Link> : inventory.pending ? <p role="status">Loading collection…</p> : inventory.error ? <><p role="alert">{inventory.error}</p><button className="min-h-11 underline" onClick={inventory.reload}>Retry collection</button></> : inventory.data && <>
          {inventory.data.items.length ? <ul className="space-y-4 mt-4">{inventory.data.items.map(item => <li key={item.asset.id} className="flex flex-wrap gap-4 p-4 rounded-xl bg-surface-container">
            <AssetPreview key={item.asset.media_url} asset={item.asset} /><div className="min-w-0 flex-1"><h3 className="break-words font-semibold">{item.asset.slug}</h3><p className="text-sm text-on-surface-variant">{item.asset.rarity} · {item.asset.kind} · Quantity {item.quantity}</p>
              {item.asset.kind !== 'generator' && <button className="min-h-11 underline text-secondary" disabled={equipBusy} onClick={() => void equip(item)}>{item.equipped ? 'Unequip' : 'Equip'} {item.asset.slug}</button>}
            </div></li>)}</ul> : <p className="mt-4 text-on-surface-variant">You have no owned items.</p>}
          <Pagination value={inventory.data.pagination} onPage={setInventoryPage} />
        </>}
      </section>
    </div>
    {result && <section data-reward className={`mt-6 rounded-xl p-6 border border-secondary/40 bg-secondary/5 ${animate ? 'vault-reveal' : ''}`} aria-label="Server opening result">
      <h2 ref={rewardHeading} tabIndex={-1} className="text-2xl font-bold">Reward confirmed</h2>
      <p role="status">{result.already_processed ? 'Recovered server result.' : 'Confirmed by the server.'}</p>
      <div className="flex flex-wrap items-center gap-4 my-4"><AssetPreview key={result.reward.media_url} asset={result.reward} /><p className="font-semibold break-words min-w-0 max-w-full">{result.reward.slug}</p></div>
      <p>Cost: {result.cost_khi_van} Khí Vận · Balance: {result.khi_van_balance}</p>
      {animate && <button className="min-h-11 underline text-secondary" onClick={() => { setAnimate(false); rewardHeading.current?.focus(); }}>Skip animation</button>}
    </section>}
  </section>;
}
