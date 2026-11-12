import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readPreferences, translate } from '../src/preferences.js';
test('preferences validate saved values, preserve dark/VI defaults and tolerate blocked storage', () => {
  assert.deepEqual(readPreferences({getItem:()=>null}),{theme:'dark',language:'vi'});
  assert.deepEqual(readPreferences({getItem:()=>'{}'}),{theme:'dark',language:'vi'});
  assert.deepEqual(readPreferences({getItem:()=>'{"theme":"light","language":"en"}'}),{theme:'light',language:'en'});
  assert.deepEqual(readPreferences({getItem:()=>{throw Error('blocked')}}),{theme:'dark',language:'vi'});
});
test('translations retain whitespace and demo user content, translate UI and accessible labels', () => {
  assert.equal(translate('  Trang chủ\n','en'),'  Home\n');
  assert.equal(translate('Trang chủ','vi'),'Trang chủ');
  assert.equal(translate('Khang Dev','en'),'Khang Dev');
  assert.equal(translate('Ảnh đại diện Khang Dev','en'),'Avatar of Khang Dev');
});
