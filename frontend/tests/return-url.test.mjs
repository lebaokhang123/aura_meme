import {test} from 'node:test';
import assert from 'node:assert/strict';
import {safeReturnUrl} from '../src/return-url.js';
test('safe local return only, including encoded redirects and login loops',()=>{
 for(const value of ['https://evil.test','//evil.test','/\\evil.test','/%2fevil.test','/%5cevil.test','/login','/register?next=/contact','javascript:alert(1)','/contact\n'])assert.equal(safeReturnUrl(value),'/');
 for(const value of ['/contact','/vault','/profile/alice?view=posts'])assert.equal(safeReturnUrl(value),value);
});
