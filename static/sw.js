self.addEventListener('install', (e) => {
  console.log('[Service Worker] Install');
});

self.addEventListener('fetch', (e) => {
  // Minimal fetch handler to satisfy PWA requirements
  e.respondWith(fetch(e.request));
});
