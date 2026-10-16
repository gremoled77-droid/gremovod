import {defineConfig} from 'vite';

// Удалённый доступ (телефон) включается только переменной STUDIO_REMOTE_HOSTS: тогда разрешены эти имена хоста.
const remoteHosts = (process.env.STUDIO_REMOTE_HOSTS || '')
  .split(',')
  .map(h => h.trim())
  .filter(Boolean);
export default defineConfig({
  server: {
    port: 5173,
    allowedHosts: remoteHosts,
    proxy: {'/api': 'http://127.0.0.1:8000', '/login': 'http://127.0.0.1:8000'},
  },
});
