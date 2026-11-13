import base from './playwright.config.mjs';
import {fileURLToPath} from 'node:url';
export default {
 ...base,testIgnore:'auth-real.spec.js',testDir:fileURLToPath(new URL('../frontend/auth-tests',import.meta.url)),
 use:{...base.use,baseURL:'http://localhost:4187'},
 webServer:{...base.webServer,command:'npm run preview -- --port 4187 --strictPort --host localhost',url:'http://localhost:4187'},
};
