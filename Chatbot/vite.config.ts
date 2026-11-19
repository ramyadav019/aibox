import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendTarget = process.env.BACKEND_URL || env.BACKEND_URL || 'http://localhost:8000';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/chat': { target: backendTarget, changeOrigin: true },
        '/conversation': { target: backendTarget, changeOrigin: true },
      },
    },
  };
});

