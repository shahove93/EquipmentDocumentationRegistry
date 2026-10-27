const spaNavigation = (req: { method?: string; url?: string; headers: { accept?: string } }) => {
  const path = (req.url ?? '').split('?')[0];
  if (req.method === 'GET' && (req.headers.accept ?? '').includes('text/html') &&
      (path === '/batches' || /^\/batches\/\d+\/?$/.test(path))) return '/index.html';
  return undefined;
};

export default {
  server: {
    host: '0.0.0.0',
    port: 5176,
    strictPort: true,
    proxy: {
      '/batches': { target: 'http://127.0.0.1:8002', changeOrigin: true, bypass: spaNavigation },
      '/products': { target: 'http://127.0.0.1:8002', changeOrigin: true },
    },
  },
};
