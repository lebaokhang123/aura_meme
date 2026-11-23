export class AuthError extends Error {
  constructor(status,code,metadata={}){super(code);this.name='AuthError';this.status=status;this.code=code;if(Number.isSafeInteger(metadata.retryAfter)&&metadata.retryAfter>0&&metadata.retryAfter<=86400)this.retryAfter=metadata.retryAfter;if(typeof metadata.nextOpenAt==='string'&&/^\d{4}-\d{2}-\d{2}T/.test(metadata.nextOpenAt)&&Number.isFinite(Date.parse(metadata.nextOpenAt)))this.nextOpenAt=metadata.nextOpenAt;}
}
function sessionUser(value){
  if(!value||!(/^[0-9a-f-]{36}$/i).test(value.id)||!(/^[a-z0-9_]{3,32}$/).test(value.username)
    ||typeof value.display_name!=='string'||value.status!=='active'||!Array.isArray(value.roles)
    ||value.roles.some(role=>!['USER','ADMIN'].includes(role)))throw new AuthError(0,'PROTOCOL_ERROR');
  const user={id:value.id,username:value.username,display_name:value.display_name,roles:Object.freeze([...value.roles]),status:value.status};
  if(typeof value.email==='string')user.email=value.email;
  if(typeof value.avatar_url==='string'&&/^\/api\/v1\/(?:media|catalog\/assets)\/[0-9a-f-]{36}$/i.test(value.avatar_url))user.avatar_url=value.avatar_url;
  if(typeof value.title==='string'&&value.title.trim())user.title=value.title.trim();
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
      if(!response.ok)throw new AuthError(response.status,typeof body?.error?.code==='string'?body.error.code:'API_ERROR',{retryAfter:Number(response.headers.get('Retry-After')),nextOpenAt:body?.error?.details?.next_open_at});
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
  async function write(method,path,body,{idempotencyKey}={}){
    if(idempotencyKey!==undefined&&(typeof idempotencyKey!=='string'||idempotencyKey.length<12||idempotencyKey.length>128||!idempotencyKey.trim()||idempotencyKey.includes('\x00')))throw new AuthError(422,'VALIDATION_ERROR');
    try{
      const csrf=await request('/auth/csrf');
      if(typeof csrf?.csrf_token!=='string'||!csrf.csrf_token)throw new AuthError(0,'PROTOCOL_ERROR');
      const multipart=typeof FormData!=='undefined'&&body instanceof FormData;
      return await request(path,{method,headers:{'X-CSRF-Token':csrf.csrf_token,...(idempotencyKey===undefined?{}:{'Idempotency-Key':idempotencyKey}),...(body&&!multipart?{'Content-Type':'application/json'}:{})},...(body?{body:multipart?body:JSON.stringify(body)}:{})});
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
    async forgotPassword(email){return mutation('forgot-password',{email});},
    async resetPassword(token,new_password){return mutation('reset-password',{token,new_password});},
    async googleConfig(){return request('/auth/google/config');},
    async googleLogin(id_token,nonce,username){const res=await mutation('google/login',{id_token,...(nonce?{nonce}:{}),...(username?{username}:{})});if(res?.status==='needs_onboarding')return res;if(!await refresh())throw new AuthError(401,'SESSION_EXPIRED');notify();return res;},
    async googleOnboarding(onboarding_token,username){const res=await mutation('google/onboarding',{onboarding_token,username});if(!await refresh())throw new AuthError(401,'SESSION_EXPIRED');notify();return res;},
    async verifyEmail(token){return mutation('verify-email',{token});},
  };
}
export function authMessage(error,language='vi'){
  const messages={
    NETWORK_ERROR:['Không kết nối được máy chủ. Vui lòng thử lại.','Cannot reach the server. Please try again.'],
    PROTOCOL_ERROR:['Phản hồi xác thực không hợp lệ. Vui lòng thử lại.','Invalid authentication response. Please try again.'],
    SESSION_EXPIRED:['Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.','Your session has expired. Please sign in again.'],
    CSRF_INVALID:['Phiên xác thực đã thay đổi. Vui lòng thử lại.','The authentication session changed. Please try again.'],
    CONFLICT:['Tên đăng nhập hoặc email đã được sử dụng.','Username or email is already in use.'],
    USERNAME_EXISTS:['Tag này đã được sử dụng. Vui lòng chọn tag khác.','This tag is already in use. Please choose another one.'],
    EMAIL_EXISTS:['Email này đã được đăng ký. Vui lòng đăng nhập.','This email is already registered. Please sign in.'],
    VALIDATION_ERROR:['Thông tin chưa hợp lệ. Mật khẩu cần 12–128 ký tự; tên đăng nhập dùng chữ thường, số hoặc dấu gạch dưới.','Invalid details. Use a 12–128 character password and lowercase letters, numbers or underscores for the username.'],
    RATE_LIMITED:['Quá nhiều lần thử. Vui lòng thử lại sau.','Too many attempts. Please try again later.'],
    ACCOUNT_LINK_REQUIRED:['Email này đã thuộc về tài khoản hiện có. Vui lòng đăng nhập bằng mật khẩu trước rồi liên kết Google.','This email belongs to an existing account. Sign in with your password first to link Google safely.'],
    ACCOUNT_UNVERIFIED:['Tài khoản chưa được kích hoạt. Vui lòng kiểm tra hộp thư email để xác minh tài khoản trước khi đăng nhập.','Account is not verified yet. Please check your email to activate your account.'],
    INVALID_VERIFICATION_TOKEN:['Liên kết xác minh không hợp lệ hoặc đã hết hạn.','Verification link is invalid or has expired.'],
    ALREADY_REGISTERED:['Tài khoản đã được kích hoạt trước đó. Vui lòng đăng nhập.','Account has already been verified. Please sign in.'],
    INVALID_ONBOARDING_TOKEN:['Phiên đăng ký Google không hợp lệ hoặc đã hết hạn. Vui lòng đăng nhập lại.','Google onboarding session is invalid or expired. Please sign in again.'],
    ONBOARDING_TOKEN_EXPIRED:['Phiên đăng ký Google đã hết hạn. Vui lòng đăng nhập lại.','Google onboarding session has expired. Please sign in again.'],
    INVALID_RESET_TOKEN:['Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.','This password reset link is invalid or has expired.'],
    GOOGLE_ONLY_ACCOUNT:['Tài khoản này đăng nhập bằng Google và không dùng mật khẩu cục bộ.','This account signs in with Google and does not have a local password.'],
    GOOGLE_AUTH_NOT_CONFIGURED:['Đăng nhập Google chưa được cấu hình trên máy chủ.','Google sign-in is not configured on this server yet.'],
    RESTORE_WINDOW_EXPIRED:['Đã quá thời hạn 30 ngày khôi phục tài khoản.','The 30-day account restoration window has expired.'],
    INVALID_FILENAME_FORMAT:['Tên file sai quy chuẩn <Rank>_<ddmmyy>_<stt>.jpg|.png (ví dụ: S_231126_01.jpg).','Filename violates the <Rank>_<ddmmyy>_<stt>.jpg|.png convention (e.g. S_231126_01.jpg).'],
    INVALID_FILENAME_DATE:['Phần ngày tháng <ddmmyy> trong tên file không hợp lệ (ví dụ: 231126).','The <ddmmyy> date part in the filename is invalid (e.g. 231126).'],
    INVALID_FILENAME_SEQUENCE:['Phần số thứ tự <stt> trong tên file không hợp lệ (ví dụ: 01).','The <stt> sequence number in the filename is invalid (e.g. 01).'],
    UNSUPPORTED_FILE_TYPE:['Định dạng file không được hỗ trợ. Chỉ chấp nhận .jpg, .png hoặc .zip chứa .jpg/.png.','Unsupported file format. Only .jpg, .png or .zip containing .jpg/.png are allowed.'],
    DUPLICATE_IMAGE_HASH:['Ảnh Meme này đã tồn tại trong danh mục (trùng mã băm SHA-256).','This Meme image already exists in the catalog (duplicate SHA-256 hash).'],
    DUPLICATE_FILE_IN_BATCH:['Trùng tên file trong cùng gói ZIP tải lên.','Duplicate filename inside the uploaded ZIP archive.'],
    ZIP_PATH_TRAVERSAL:['Phát hiện đường dẫn không an toàn trong gói ZIP.','Unsafe file path detected inside the ZIP archive.'],
    NESTED_ZIP_FORBIDDEN:['Không cho phép gói ZIP lồng nhau.','Nested ZIP archives are not permitted.'],
  };
  if(error?.code==='SESSION_EXPIRED')return messages.SESSION_EXPIRED[language==='en'?1:0];
  if(error?.status===401)return language==='en'?'Incorrect email or password.':'Email hoặc mật khẩu không đúng.';
  const pair=messages[error?.code]||['Không thể xác thực. Vui lòng thử lại.','Unable to authenticate. Please try again.'];
  return pair[language==='en'?1:0];
}
