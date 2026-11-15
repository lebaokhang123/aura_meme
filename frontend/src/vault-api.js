import {apiId,apiPage,vaultAsset} from './social-api.js';
export {vaultAsset} from './social-api.js';
const fail=()=>{throw Error('PROTOCOL_ERROR')};
const validTime=value=>value===null||typeof value==='string'&&Number.isFinite(Date.parse(value));
export function vaultCatalog(value){const page=apiPage(value);return {...page,items:page.items.map(item=>{if(typeof item?.owned!=='boolean')fail();return {...item,asset:vaultAsset(item.asset)};})};}
export function vaultCases(value){if(!Array.isArray(value?.items))fail();return value.items.filter(item=>item.runtime_kind!=null).map(item=>{apiId(item.id);if(!['avatar','background'].includes(item.runtime_kind)||item.cost_khi_van!==0||item.status!=='active'||typeof item.label!=='string')fail();return item;});}
export function vaultReceipt(value){apiId(value?.open_id);apiId(value.case_id);if(value.cost_khi_van!==0||!Number.isSafeInteger(value.khi_van_balance)||value.khi_van_balance<0||typeof value.already_processed!=='boolean'||!validTime(value.next_open_at))fail();return {...value,reward:vaultAsset(value.reward)};}
export function readPendingOpen(json,owner){try{const value=JSON.parse(json);if(value.owner!==owner)return null;apiId(value.owner);apiId(value.caseId);apiId(value.key);return {owner:value.owner,caseId:value.caseId,key:value.key};}catch{return null;}}

export function vaultOdds(value,caseId){
 if(value?.case?.id!==apiId(caseId)||vaultCases({items:[value.case]}).length!==1||!Array.isArray(value.bands)||value.bands.length!==1)fail();
 const band=value.bands[0],weights=band.weights_bps,rarities=['D','C','B','A','S'];
 if(band.min_earned_xp!==0||band.max_earned_xp!==null||!Number.isSafeInteger(band.odds_version)||band.odds_version<1||!weights||Object.keys(weights).length!==5||!rarities.every(r=>Number.isSafeInteger(weights[r])&&weights[r]>=0)||Object.values(weights).reduce((n,w)=>n+w,0)!==10000)fail();
 return rarities.map(rarity=>({rarity,percent:(weights[rarity]/100).toFixed(1)}));
}
