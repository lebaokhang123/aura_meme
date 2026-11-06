export interface Asset { id: string; slug: string; kind: 'avatar' | 'frame' | 'icon' | 'effect' | 'generator'; rarity: 'D' | 'C' | 'B' | 'A' | 'S'; media_url: string }
export interface CaseDefinition { id: string; slug: string; label: string; cost_khi_van: number; status: 'active' | 'retired' }
export interface CaseDetail { case: CaseDefinition; bands: { min_earned_xp: number; max_earned_xp: number | null; odds_version: number; weights_bps: Record<Asset['rarity'], number> }[] }
export interface InventoryItem { asset: Asset; quantity: number; equipped: boolean }
export interface OpenResult { open_id: string; case_id: string; reward: Asset; cost_khi_van: number; khi_van_balance: number; already_processed: boolean }
