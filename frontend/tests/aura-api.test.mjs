import test from 'node:test';
import assert from 'node:assert/strict';
import {apiAuraProgress,apiAuraCheckIn,resetSeconds} from '../src/aura-api.js';
const progress={earned_xp:125,bonus_xp:0,total_xp:125,level:10,fair_level:10,realm:'Luyện Khí',level_xp:8,next_level_xp:20,xp_to_next:12,streak_days:3,checked_in:false,effective_day:'2026-11-14',next_reset_at:'2026-11-15T00:00:00Z',server_time:'2026-11-14T23:59:00Z'};
test('Aura DTO preserves server policy and separates earned/bonus without inventing levels',()=>{
 assert.deepEqual(apiAuraProgress(progress),progress);
 assert.equal(apiAuraProgress({...progress,level:100,next_level_xp:null,xp_to_next:0}).level,100);
 for(const patch of [{level:101},{earned_xp:-1},{next_reset_at:'bad'},{checked_in:1},{effective_day:'bad'},{streak_days:1.5},{next_reset_at:progress.server_time},{server_time:'2026-11-14T23:59:00'}])assert.throws(()=>apiAuraProgress({...progress,...patch}),/PROTOCOL_ERROR/);
 assert.equal(resetSeconds(progress,1000,31000),30);assert.equal(resetSeconds(progress,1000,62000),0);
});
test('check-in receipt requires real integer XP and no legacy wallet reward',()=>{
 const receipt={effective_day:'2026-11-14',already_checked_in:false,earned_xp_delta:15,bonus_xp_delta:0,khi_van_delta:0,streak_days:4};
 assert.deepEqual(apiAuraCheckIn(receipt),receipt);assert.throws(()=>apiAuraCheckIn({...receipt,khi_van_delta:50}),/PROTOCOL_ERROR/);
});
