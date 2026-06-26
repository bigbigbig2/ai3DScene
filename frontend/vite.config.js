import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
var apiTarget = 'http://10.7.3.50:8181';
export default defineConfig({
    plugins: [vue()],
    server: {
        host: '0.0.0.0',
        port: 5174,
        strictPort: true,
        fs: {
            allow: ['..'],
        },
        proxy: {
            '/api': {
                target: apiTarget,
                changeOrigin: true,
            },
            '/health': {
                target: apiTarget,
                changeOrigin: true,
            },
            '/ready': {
                target: apiTarget,
                changeOrigin: true,
            },
        },
    },
});
