const CACHE_NAME = 'sadakchef-v1';
const urlsToCache = [
    '/',
    '/static/css/style.css',
    '/static/js/app.js',
    '/static/js/notifications.js',
    '/static/generated-icon.png'
];

// Install event
self.addEventListener('install', event => {
    console.log('[SW] Installing service worker');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('[SW] Caching app shell');
                return cache.addAll(urlsToCache);
            })
            .then(() => {
                console.log('[SW] Service worker installed');
                return self.skipWaiting();
            })
    );
});

// Activate event
self.addEventListener('activate', event => {
    console.log('[SW] Activating service worker');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => {
            console.log('[SW] Service worker activated');
            return self.clients.claim();
        })
    );
});

// Fetch event
self.addEventListener('fetch', event => {
    // Handle session-related requests specially
    if (event.request.url.includes('/login') || event.request.url.includes('/dashboard')) {
        event.respondWith(fetch(event.request));
        return;
    }

    // Handle navigation requests (when app is opened)
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request).catch(() => {
                // If network fails, redirect to login
                return fetch('/login');
            })
        );
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Return cached version or fetch from network
                return response || fetch(event.request);
            })
    );
});

// Push event - Handle incoming push notifications
self.addEventListener('push', event => {
    console.log('[SW] Push event received');

    let options = {
        icon: '/static/generated-icon.png',
        badge: '/static/generated-icon.png',
        vibrate: [300, 100, 300, 100, 300],
        requireInteraction: true,
        actions: [
            {
                action: 'view',
                title: 'View',
                icon: '/static/generated-icon.png'
            },
            {
                action: 'close',
                title: 'Close',
                icon: '/static/generated-icon.png'
            }
        ]
    };

    if (event.data) {
        try {
            const pushData = event.data.json();
            console.log('[SW] Push data:', pushData);

            options = {
                ...options,
                ...pushData,
                data: pushData.data || {}
            };

            event.waitUntil(
                self.registration.showNotification(
                    pushData.title || 'SadakChef Notification',
                    options
                )
            );
        } catch (error) {
            console.error('[SW] Error parsing push data:', error);
            event.waitUntil(
                self.registration.showNotification(
                    'SadakChef Notification',
                    {
                        ...options,
                        body: 'You have a new notification'
                    }
                )
            );
        }
    } else {
        event.waitUntil(
            self.registration.showNotification(
                'SadakChef Notification',
                {
                    ...options,
                    body: 'You have a new notification'
                }
            )
        );
    }
});

// Notification click event
self.addEventListener('notificationclick', event => {
    console.log('[SW] Notification clicked:', event.notification);

    event.notification.close();

    if (event.action === 'close') {
        return;
    }

    // Handle view action or notification click
    const urlToOpen = event.notification.data?.url || '/dashboard';

    event.waitUntil(
        clients.matchAll({
            type: 'window',
            includeUncontrolled: true
        }).then(clientList => {
            // Check if app is already open
            for (const client of clientList) {
                if (client.url.includes(self.location.origin)) {
                    client.focus();
                    if (urlToOpen !== '/dashboard') {
                        client.navigate(urlToOpen);
                    }
                    return;
                }
            }

            // Open new window
            return clients.openWindow(urlToOpen);
        })
    );
});

// Background sync for offline functionality
self.addEventListener('sync', event => {
    console.log('[SW] Background sync:', event.tag);

    if (event.tag === 'background-sync') {
        event.waitUntil(
            // Handle background sync tasks
            syncData()
        );
    }
});

async function syncData() {
    try {
        // Implement any offline data sync logic here
        console.log('[SW] Syncing offline data');
    } catch (error) {
        console.error('[SW] Sync failed:', error);
    }
}

// Handle messages from main thread
self.addEventListener('message', event => {
    console.log('[SW] Message received:', event.data);

    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});