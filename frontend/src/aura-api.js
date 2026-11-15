// Validate server DTOs; progression policy belongs exclusively to the server.
const integer=value=>Number.isSafeInteger(value)&&value>=0;
const day=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value));
const timestamp=value=>typeof value==='string'&&/(?:Z|[+-]\d{2}:\d{2})$/.test(value)&&Number.isFinite(Date.parse(value));
const bad=()=>{throw Error('PROTOCOL_ERROR')};
export function apiAuraProgress(value){
 if(!value||!['earned_xp','bonus_xp','total_xp','level_xp','xp_to_next','streak_days'].every(k=>integer(value[k]))||!['level','fair_level'].every(k=>integer(value[k])&&value[k]>=1&&value[k]<=100)||!(value.next_level_xp===null||integer(value.next_level_xp))||typeof value.realm!=='string'||!value.realm||typeof value.checked_in!=='boolean'||!day(value.effective_day)||!timestamp(value.next_reset_at)||!timestamp(value.server_time)||Date.parse(value.next_reset_at)<=Date.parse(value.server_time))bad();
 return value;
}
export function apiAuraCheckIn(value){
 if(!value||!day(value.effective_day)||typeof value.already_checked_in!=='boolean'||!['earned_xp_delta','bonus_xp_delta','streak_days'].every(k=>integer(value[k]))||value.khi_van_delta!==0)bad();
 return value;
}
export function resetSeconds(progress,receivedAt,now=Date.now()){
 return Math.max(0,Math.ceil((Date.parse(progress.next_reset_at)-Date.parse(progress.server_time)-(now-receivedAt))/1000));
}
