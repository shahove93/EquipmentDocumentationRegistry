const target = 'http://127.0.0.1:8001'
const spaNavigation = (req: { method?: string; url?: string; headers: { accept?: string } }) => {
  if (req.method !== 'GET' || !(req.headers.accept ?? '').includes('text/html')) return undefined
  const path = (req.url ?? '').split('?')[0]
  return path === '/batches' || /^\/batches\/\d+\/?$/.test(path) ? '/index.html' : undefined
}

export default {
  server: {
    host: '0.0.0.0',
    port: 5175,
    strictPort: true,
    watch: { usePolling: true, interval: 150 },
    proxy: {
      '/products': { target, changeOrigin: true },
      '/batches': { target, changeOrigin: true, bypass: spaNavigation },
    },
  },
}
