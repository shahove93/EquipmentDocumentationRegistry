import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend is a plain FastAPI app served on localhost. The frontend talks to
// it over relative URLs only; the dev server proxies the API path prefixes, so
// the browser sees one origin and no CORS policy (and certainly no `*`) is
// needed. Nothing here is a secret — the target is a loopback address.
const API_TARGET = 'http://127.0.0.1:8000'

const proxyTarget = { target: API_TARGET, changeOrigin: true }

/**
 * The card route `/documents/:id` is both a client-side route and a prefix of
 * the backend API, so a plain prefix rule would swallow a direct visit to the
 * card and answer it with FastAPI's JSON 404.
 *
 * The two cases are told apart by what the caller asks for. A browser
 * navigation carries `Accept: text/html`; the typed API client always sends
 * `Accept: application/json`. So an HTML navigation to exactly `/documents/<id>`
 * is handed back to Vite, which serves the SPA shell, while everything else
 * under the prefix goes to the backend. Only that one route shape is treated as
 * HTML, so a later request for a file body — `/documents/<id>/files/<file>`
 * opened in a tab, which also carries `Accept: text/html` — is still proxied.
 *
 * Returning the shell path is the documented `bypass` contract: Vite rewrites
 * the request URL and lets its own middleware serve it.
 *
 * The rule is deliberately narrow: exactly one path segment after `/documents`,
 * and no deeper. A single-segment `GET /documents/<id>` can only ever be the
 * integer document lookup, so matching a non-numeric id costs nothing and keeps
 * a typed URL consistent with an in-app link. Anything with further segments is
 * left alone.
 */
const DOCUMENT_CARD_ROUTE = /^\/documents\/[^/]+\/?$/

/** The small slice of a Node request this rule reads; avoids a @types/node import. */
interface ProxyRequest {
  method?: string
  url?: string
  headers: { accept?: string }
}

const serveSpaForCardNavigation = (req: ProxyRequest): string | undefined => {
  if (req.method !== 'GET') {
    return undefined
  }
  if (!(req.headers.accept ?? '').includes('text/html')) {
    return undefined
  }
  const path = (req.url ?? '').split('?')[0]
  return DOCUMENT_CARD_ROUTE.test(path) ? '/index.html' : undefined
}

// Ordered specific-first; `http-proxy` matches a prefix, and a prefix declared
// for the narrower path must not be shadowed by a shorter one.
const proxy = {
  '/document-types': proxyTarget,
  '/documents': { ...proxyTarget, bypass: serveSpaForCardNavigation },
  '/manufacturers': proxyTarget,
  '/products': proxyTarget,
  '/variants': proxyTarget,
  '/issuers': proxyTarget,
  '/health': proxyTarget,
}

export default defineConfig({
  plugins: [react()],
  server: {
    proxy,
  },
})
