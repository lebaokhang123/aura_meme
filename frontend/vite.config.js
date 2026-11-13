import { defineConfig } from 'vite';
const target=new URL(process.env.AURAMEME_API_TARGET||'http://127.0.0.1:8000');
if(target.protocol!=='http:'||!['localhost','127.0.0.1','[::1]'].includes(target.hostname)||target.username||target.password||target.search||target.hash||target.pathname!=='/')throw Error('Local API proxy requires a loopback HTTP origin.');
const proxy={'/api':{target:target.origin,changeOrigin:false}};
export default defineConfig({
  base:'/',
  server:{host:'localhost',port:5173,strictPort:true,proxy},
  preview:{host:'localhost',proxy},
});
