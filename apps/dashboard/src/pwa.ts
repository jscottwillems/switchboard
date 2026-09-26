/** Register the ops service worker. Dev stays uncached so Vite can reload. */

export function registerOpsServiceWorker(): void {
  if (!import.meta.env.PROD) return
  if (!('serviceWorker' in navigator)) return
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(() => {
      // Insecure LAN HTTP cannot install a worker. The page still loads over the network.
    })
  })
}
