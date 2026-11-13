export class AuthError extends Error {
  constructor(status,code){super(code);this.name='AuthError';this.status=status;this.code=code;}
}
function sessionUser(value){
  if(!value||!(/^[0-9a-f-]{36}$/i).test(value.id)||!(/^[a-z0-9_]{3,32}$/).test(value.username)
    ||typeof value.display_name!=='string'||value.status!=='active'||!Array.isArray(value.roles)
    ||value.roles.some(role=>!['USER','ADMIN'].includes(role)))throw new AuthError(0,'PROTOCOL_ERROR');
  const user={id:value.id,username:value.username,display_name:value.display_name,roles:Object.freeze([...value.roles]),status:value.status};
  if(typeof value.email==='string')user.email=value.email;
  if(typeof value.avatar_url==='string'&&/^\/api\/v1\/media\/[0-9a-f-]{36}$/i.test(value.avatar_url))user.avatar_url=value.avatar_url;
  return Object.freeze(user);
}
export function createAuthClient({fetch=globalThis.fetch,notify=()=>{}}={}){
  let state={status:'loading',user:null,error:null},generation=0;
  const listeners=new Set(),publish=next=>{state=Object.freeze(next);for(const listener of listeners)listener();};
  async function request(path,options={}){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);timer.unref?.();
    try{
      const response=await fetch('/api/v1'+path,{credentials:'include',cache:'no-store',redirect:'error',...options,signal:controller.signal,headers:{Accept:'application/json',...options.headers}});
      if(response.status===204)return null;
      let body;try{body=await response.json();}catch{throw new AuthError(response.status,'PROTOCOL_ERROR');}
      if(!response.ok)throw new AuthError(response.status,typeof body?.error?.code==='string'?body.error.code:'API_ERROR');
      return body;
    }catch(error){if(error instanceof AuthError)throw error;throw new AuthError(0,'NETWORK_ERROR');}
    finally{clearTimeout(timer);}
  }
  async function refresh(){
    const current=++generation;
    try{
      const body=await request('/users/me');if(current!==generation)return state.user;
      const user=sessionUser(body);publish({status:'authenticated',user,error:null});return user;
    }catch(error){
      if(current!==generation)return state.user;
      if(error.status===401){const expired=state.user!==null;publish({status:'guest',user:null,error:expired?new AuthError(error.status,'SESSION_EXPIRED'):null});return null;}
      publish({...state,status:state.user?'authenticated':'unavailable',error});throw error;
    }
  }
  async function write(method,path,body){
    try{
      const csrf=await request('/auth/csrf');
      if(typeof csrf?.csrf_token!=='string'||!csrf.csrf_token)throw new AuthError(0,'PROTOCOL_ERROR');
      const multipart=typeof FormData!=='undefined'&&body instanceof FormData;
      return await request(path,{method,headers:{'X-CSRF-Token':csrf.csrf_token,...(body&&!multipart?{'Content-Type':'application/json'}:{})},...(body?{body:multipart?body:JSON.stringify(body)}:{})});
    }catch(error){if(error.status===401)await refresh().catch(()=>{});throw error;}
  }
  const mutation=(path,body)=>write('POST','/auth/'+path,body);
  return {
    snapshot:()=>state,
    subscribe:listener=>{listeners.add(listener);return()=>listeners.delete(listener);},
    refresh,
    read:request,write,
    async login(email,password){await mutation('login',{email,password});if(!await refresh())throw new AuthError(401,'SESSION_EXPIRED');notify();},
    async register({username,email,password,display_name}){return mutation('register',{username,email,password,display_name});},
    async logout(){await mutation('logout');generation++;publish({status:'guest',user:null,error:null});notify();},
  };
}
export function authMessage(error,language='vi'){
  const messages={
    NETWORK_ERROR:['Không kết nối được máy chủ. Vui lòng thử lại.','Cannot reach the server. Please try again.'],
    PROTOCOL_ERROR:['Phản hồi xác thực không hợp lệ. Vui lòng thử lại.','Invalid authentication response. Please try again.'],
    SESSION_EXPIRED:['Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.','Your session has expired. Please sign in again.'],
    CSRF_INVALID:['Phiên xác thực đã thay đổi. Vui lòng thử lại.','The authentication session changed. Please try again.'],
    CONFLICT:['Tên đăng nhập hoặc email đã được sử dụng.','Username or email is already in use.'],
    VALIDATION_ERROR:['Thông tin chưa hợp lệ. Mật khẩu cần 12–128 ký tự; tên đăng nhập dùng chữ thường, số hoặc dấu gạch dưới.','Invalid details. Use a 12–128 character password and lowercase letters, numbers or underscores for the username.'],
    RATE_LIMITED:['Quá nhiều lần thử. Vui lòng thử lại sau.','Too many attempts. Please try again later.'],
  };
  if(error?.code==='SESSION_EXPIRED')return messages.SESSION_EXPIRED[language==='en'?1:0];
  if(error?.status===401)return language==='en'?'Incorrect email or password.':'Email hoặc mật khẩu không đúng.';
  const pair=messages[error?.code]||['Không thể xác thực. Vui lòng thử lại.','Unable to authenticate. Please try again.'];
  return pair[language==='en'?1:0];
}
