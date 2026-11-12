import {test} from 'node:test';
import assert from 'node:assert/strict';
import {checkImageBytes,MAX_FILE_BYTES} from '../src/social-files.js';
test('image boundary rejects oversized, mislabeled, truncated and decompression-sized input',()=>{
 const png=new Uint8Array(24);png.set([137,80,78,71,13,10,26,10]);png.set([0,0,0,64,0,0,0,64],16);
 assert.deepEqual(checkImageBytes(png,'image/png',24),{width:64,height:64});
 assert.throws(()=>checkImageBytes(png,'image/png',MAX_FILE_BYTES+1),/FILE_SIZE/);
 assert.throws(()=>checkImageBytes(new TextEncoder().encode('<svg onload=alert(1)>'),'image/png',20),/FILE_TYPE/);
 assert.throws(()=>checkImageBytes(png,'image/svg+xml',24),/FILE_TYPE/);
 png.set([127,255,255,255],16);assert.throws(()=>checkImageBytes(png,'image/png',24),/FILE_DIMENSIONS/);
});
