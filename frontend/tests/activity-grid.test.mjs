import {test} from 'node:test';
import assert from 'node:assert/strict';
import {activityGrid} from '../src/activity-grid.js';
function calendar(start='2024-02-26',today='2025-03-01') {const day=new Date(start+'T00:00:00Z');return {timezone:'Asia/Ho_Chi_Minh',start_date:start,end_date:today,total:0,days:Array.from({length:371},(_,i)=>({date:new Date(+day+i*86400000).toISOString().slice(0,10),posts:0,comments:0,count:0}))};}
test('53 Monday weeks preserve leap day and month positions without timezone drift',()=>{
 const source=calendar(),grid=activityGrid(source,'vi');assert.equal(grid.weeks.length,53);assert.ok(grid.weeks.every(w=>w.length===7));assert.equal(grid.weeks[0][3].date,'2024-02-29');assert.equal(grid.weeks[0][4].date,'2024-03-01');assert.equal(grid.months[0].week,0);assert.equal(grid.months[0].month,3);assert.equal(grid.todayIndex,369);
});
test('true counts aggregate levels and future cells remain excluded',()=>{
 const source=calendar();Object.assign(source.days[2],{posts:1,comments:2,count:3});source.total=3;const grid=activityGrid(source,'en');assert.equal(grid.weeks[0][2].level,2);assert.equal(grid.weeks[52][6].future,true);assert.equal(grid.total,3);assert.match(grid.weeks[0][2].label,/3/);
});
test('malformed, partial, forged total and future activity are rejected',()=>{
 for(const mutate of [s=>s.days.pop(),s=>s.days[2].date='2024-02-30',s=>s.total=1,s=>s.days[0].count=-1,s=>s.days[370].count=1,s=>s.timezone='UTC']){const source=calendar();mutate(source);assert.throws(()=>activityGrid(source,'vi'),/ACTIVITY_PROTOCOL/);}
});
