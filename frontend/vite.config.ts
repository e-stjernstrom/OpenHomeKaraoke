import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The built page is served by Flask from /static/app/ (see app.py, route "/").
// During development, `npm run dev` proxies the API and the WebSocket to a running
// OpenHomeKaraoke (OHK_URL, default http://localhost:5000).
const target = (globalThis as any).process?.env?.OHK_URL || 'http://localhost:5000';
const proxied = ['/api', '/nowplaying', '/get_queue', '/enqueue', '/skip', '/pause', '/transpose', '/play_vocal',
  '/play_speed', '/seek', '/audio_delay', '/subtitle_delay', '/toggle_subtitle', '/restart', '/vol', '/suggest',
  '/download', '/check_download', '/qrcode', '/user_rename', '/auto_username', '/add_spoken', '/get_ASR',
  '/save_delays', '/norm_vol', '/set_vocal_model', '/vocal_split', '/bg-process', '/change_language',
  '/update_ytdl', '/quit', '/shutdown', '/reboot', '/expand_fs', '/logo'];

export default defineConfig({
  base: '/static/app/',
  plugins: [react()],
  build: {
    outDir: '../static/app',
    emptyOutDir: true,
    chunkSizeWarningLimit: 900,
  },
  server: {
    host: '0.0.0.0',
    proxy: Object.fromEntries([
      ...proxied.map((p) => [p, { target }]),
      ['/ws_init', { target, ws: true }],
    ]),
  },
});
