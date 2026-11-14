export function safeReturnUrl(value){
 if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//')||/[\\\s]/.test(value))return '/';
 let decoded;try{decoded=decodeURIComponent(value)}catch{return '/'}
 if(decoded.startsWith('//')||/[\\\s]/.test(decoded)||/^\/(login|register)([/?#]|$)/.test(decoded))return '/';
 return value;
}
export const loginUrl=()=>'/login?next='+encodeURIComponent(safeReturnUrl(location.pathname+location.search));
