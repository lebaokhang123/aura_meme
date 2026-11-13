import test from 'node:test';
import assert from 'node:assert/strict';
import { createAuthClient } from '../src/auth-client.js';
const user={id:'123e4567-e89b-42d3-a456-426614174000',username:'khang_dev',display_name:'Khang Dev',roles:['USER','ADMIN'],status:'active'};
function transport(queue) { const calls=[]; return {calls,fetch:async(path,options)=>{calls.push({path,...options});const value=queue.shift();if(value instanceof Error)throw value;return value;}}; }
const ok=body=>Response.json(body),failure=(status,code)=>Response.json({error:{code,message:'safe'}},{status});
test('server session is authoritative; csrf and credentials accompany mutations without storing identity',async()=>{
 const t=transport([ok({csrf_token:'test-csrf'}),ok({...user,username:'ignored-login-response'}),ok(user)]),c=createAuthClient({fetch:t.fetch});
 await c.login('Khang_dev@example.com','synthetic-password');
 assert.deepEqual(c.snapshot().user,user);
 assert.deepEqual(t.calls.map(v=>v.path),['/api/v1/auth/csrf','/api/v1/auth/login','/api/v1/users/me']);
 for(const v of t.calls){assert.equal(v.credentials,'include');assert.equal(v.cache,'no-store');}
 assert.equal(t.calls[1].headers['X-CSRF-Token'],'test-csrf');
 assert.equal(JSON.parse(t.calls[1].body).email,'Khang_dev@example.com');
});
test('missing/revoked session becomes guest, but network failure is not fabricated as guest',async()=>{
 const t=transport([failure(401,'UNAUTHORIZED'),new TypeError('offline')]),c=createAuthClient({fetch:t.fetch});
 await c.refresh();assert.equal(c.snapshot().status,'guest');
 await assert.rejects(c.refresh(),{code:'NETWORK_ERROR'});assert.equal(c.snapshot().status,'unavailable');
});
test('logout failure preserves current identity; successful logout clears memory',async()=>{
 const t=transport([ok(user),ok({csrf_token:'one'}),new TypeError('offline'),ok({csrf_token:'two'}),new Response(null,{status:204})]),c=createAuthClient({fetch:t.fetch});
 await c.refresh();await assert.rejects(c.logout(),{code:'NETWORK_ERROR'});assert.equal(c.snapshot().user.id,user.id);
 await c.logout();assert.equal(c.snapshot().user,null);assert.equal(c.snapshot().status,'guest');
});
for(const [status,code] of [[401,'UNAUTHORIZED'],[403,'CSRF_INVALID'],[409,'CONFLICT'],[422,'VALIDATION_ERROR'],[429,'RATE_LIMITED']]){
 test('HTTP '+status+' is reported without creating a session',async()=>{
  const t=transport([ok({csrf_token:'test'}),failure(status,code)]),c=createAuthClient({fetch:t.fetch});
  await assert.rejects(c.login('x@example.com','wrong'),{status,code});assert.equal(c.snapshot().user,null);
 });
}
test('register sends only the account fields and does not automatically sign in',async()=>{
 const t=transport([ok({csrf_token:'test'}),ok(user)]),c=createAuthClient({fetch:t.fetch});
 await c.register({username:'new_user',email:'new@example.com',password:'synthetic-password',display_name:'New User',roles:['ADMIN']});
 assert.deepEqual(Object.keys(JSON.parse(t.calls[1].body)).sort(),['display_name','email','password','username']);
 assert.equal(c.snapshot().user,null);
});
test('malformed user/response is rejected; a late session read cannot undo logout',async()=>{
 const broken=transport([ok({...user,roles:['ROOT']})]),bad=createAuthClient({fetch:broken.fetch});
 await assert.rejects(bad.refresh(),{code:'PROTOCOL_ERROR'});assert.equal(bad.snapshot().user,null);
 let release;const t=transport([ok(user)]),c=createAuthClient({fetch:async(path,options)=>{
  if(path.endsWith('/users/me')&&release===undefined)return new Promise(resolve=>{release=resolve;});
  return path.endsWith('/csrf')?ok({csrf_token:'test'}):new Response(null,{status:204});
 }});
 const pending=c.refresh();await c.logout();release(ok(user));await pending;assert.equal(c.snapshot().user,null);
});

test('a blocked session cookie rejects login and a forbidden session read stays unavailable',async()=>{
 const c=createAuthClient({fetch:transport([ok({csrf_token:'test'}),ok(user),failure(401,'UNAUTHORIZED')]).fetch});
 await assert.rejects(c.login('x@example.com','synthetic-password'),{code:'SESSION_EXPIRED'});
 assert.equal(c.snapshot().user,null);
 const forbidden=createAuthClient({fetch:transport([failure(403,'FORBIDDEN')]).fetch});
 await assert.rejects(forbidden.refresh(),{status:403});assert.equal(forbidden.snapshot().status,'unavailable');
});

test('generic Social mutation reuses session CSRF and supports multipart without a JSON content type',async()=>{
 const t=transport([ok({csrf_token:'csrf'}),ok({id:user.id}),ok({csrf_token:'next'}),ok({reaction_type:'love'})]);
 const c=createAuthClient({fetch:t.fetch}),data=new FormData();data.append('file',new Blob(['synthetic']), 'fixture.png');
 await c.write('POST','/media',data);assert.equal(t.calls[1].body,data);assert.equal(t.calls[1].headers['Content-Type'],undefined);
 await c.write('PUT','/posts/'+user.id+'/reactions',{reaction_type:'love'});
 assert.equal(t.calls[3].headers['X-CSRF-Token'],'next');assert.equal(t.calls[3].credentials,'include');
});
