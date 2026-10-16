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
    // changeOrigin: false — бэкенду нужен настоящий Host запроса: по нему он отличает телефон от локального браузера.
    proxy: {
      '/api': {target: 'http://127.0.0.1:8000', changeOrigin: false},
      '/login': {target: 'http://127.0.0.1:8000', changeOrigin: false},
    },
  },
});
