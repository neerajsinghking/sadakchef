// Enhanced JavaScript for Kitchen Management System with Push Notifications

// Global variables (prevent duplicate declarations)
if (typeof window.socket === 'undefined') {
    window.socket = null;
}
if (typeof window.notificationManager === 'undefined') {
    window.notificationManager = null;
}
let pushSubscription = null;

// Subscribe to push notifications
async function subscribeToPushNotifications(registration, vapidPublicKey) {
    try {
        console.log('Subscribing to push notifications...');

        const subscription = await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
        });

        console.log('Push subscription successful:', subscription);
        pushSubscription = subscription;

        // Save subscription to server
        await savePushSubscription(subscription);

        if (window.notificationManager) {
            notificationManager.success('🔔 Push notifications activated! You will receive real-time updates.', 5000);
        }

    } catch (error) {
        console.error('Failed to subscribe to push notifications:', error);
        if (window.notificationManager) {
            notificationManager.error('Failed to activate push notifications. Please try again.', 5000);
        }
    }
}

// Save push subscription to server
async function savePushSubscription(subscription) {
    try {
        console.log('💾 Saving push subscription to server...');

        const subscriptionData = subscription.toJSON();
        console.log('📤 Subscription data:', subscriptionData);

        const response = await fetch('/api/push-subscription', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(subscriptionData)
        });

        if (!response.ok) {
            throw new Error(`Server returned ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        if (result.success) {
            console.log('✅ Push subscription saved to server successfully');
        } else {
            console.error('❌ Failed to save push subscription:', result.error);
            throw new Error(result.error || 'Unknown server error');
        }
    } catch (error) {
        console.error('❌ Error saving push subscription:', error);
        if (window.notificationManager) {
            notificationManager.error('Failed to save notification settings: ' + error.message, 5000);
        }
        throw error;
    }
}

// Convert VAPID key
function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// Initialize application
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 DOM loaded, initializing app...');
    console.log('User Agent:', navigator.userAgent);
    console.log('Is Mobile Device:', isMobileDevice());

    // Check if this is a PWA
    const isPWA = window.matchMedia('(display-mode: standalone)').matches || 
                  window.navigator.standalone === true;
    console.log('Is PWA:', isPWA);

    // Handle PWA session restoration
    if (isPWA) {
        handlePWASessionRestore();
    }

    initializeSocket();
    initializeSocketIO();
    initializeServiceWorker();
    initializeFeatures();

    // Add mobile notification button after a delay
    setTimeout(() => {
        addNotificationButton();
    }, 3000);

    // Force enable notifications for mobile devices
    if (isMobileDevice()) {
        setTimeout(enableMobileNotifications, 2000);
    }

    // Request notification permissions
    requestNotificationPermission();

    console.log('✅ App initialization complete');
});

// Utility function to get IST time
function getISTTime() {
    const now = new Date();
    // Convert to IST (UTC + 5:30)
    const istOffset = 5.5 * 60; // IST is UTC + 5:30
    const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
    const ist = new Date(utc + (istOffset * 60000));
    return ist;
}

// Format IST time for display
function formatISTTime(date = null) {
    const istTime = date ? new Date(date) : getISTTime();
    return istTime.toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: true
    });
}

// Initialize Socket.IO
function initializeSocket() {
    if (typeof io !== 'undefined') {
        window.socket = io();

        window.socket.on('connect', function() {
            console.log('Connected to server');
            // Join kitchen room if user is authenticated
            if (window.userKitchenId) {
                console.log('Joining kitchen:', window.userKitchenId);
                window.socket.emit('join_kitchen', {kitchen_id: window.userKitchenId});
            }
        });

        window.socket.on('disconnect', function() {
            console.log('Disconnected from server');
        });

        window.socket.on('notification', function(data) {
            console.log('Received notification via socket:', data);
            handleNotification(data);
        });

        window.socket.on('status', function(data) {
            console.log('Status:', data.msg);
        });

        window.socket.on('connect_error', function(error) {
            console.error('Socket connection error:', error);
        });
    } else {
        console.error('Socket.IO not loaded');
    }
}

// Initialize Service Worker and Push Notifications
async function initializeServiceWorker() {
    if ('serviceWorker' in navigator) {
        try {
            console.log('🔧 Registering Service Worker...');
            const registration = await navigator.serviceWorker.register('/sw.js', {
                scope: '/'
            });
            console.log('✅ Service Worker registered successfully:', registration);

            // Wait for service worker to be ready
            await navigator.serviceWorker.ready;
            console.log('✅ Service Worker is ready');

            // Initialize push notifications after service worker is ready
            await initializePushNotifications(registration);

        } catch (error) {
            console.error('❌ Service Worker registration failed:', error);
            if (window.notificationManager) {
                notificationManager.error('Failed to initialize notifications. Please try again.', 5000);
            }
        }
    } else {
        console.warn('⚠️ Service Worker not supported');
        if (window.notificationManager) {
            notificationManager.warning('Your browser does not support push notifications.', 5000);
        }
    }
}

// Initialize Push Notifications
async function initializePushNotifications(registration) {
    if (!('PushManager' in window)) {
        console.warn('⚠️ Push messaging is not supported');
        if (window.notificationManager) {
            notificationManager.warning('Your browser does not support push messaging.', 5000);
        }
        return;
    }

    try {
        console.log('🔔 Initializing push notifications...');

        // Request notification permission first
        const permission = await Notification.requestPermission();
        console.log('📱 Notification permission:', permission);

        if (permission !== 'granted') {
            console.warn('❌ Notification permission denied');
            if (window.notificationManager) {
                notificationManager.warning('Notifications blocked. Please enable them in browser settings.', 8000);
            }
            return;
        }

        // Get VAPID public key from server
        console.log('🔑 Getting VAPID public key...');
        const response = await fetch('/api/vapid-public-key');

        if (!response.ok) {
            throw new Error('Failed to get VAPID key from server');
        }

        const data = await response.json();
        const vapidPublicKey = data.public_key;

        console.log('✅ Got VAPID public key:', vapidPublicKey);

        // Convert VAPID key to Uint8Array
        const applicationServerKey = urlBase64ToUint8Array(vapidPublicKey);

        // Check if already subscribed
        const existingSubscription = await registration.pushManager.getSubscription();

        if (existingSubscription) {
            console.log('📱 Found existing subscription');
            pushSubscription = existingSubscription;
            await savePushSubscription(pushSubscription);
        } else {
            console.log('📱 Creating new subscription...');
            // Subscribe to push notifications
            pushSubscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: applicationServerKey
            });

            console.log('✅ Push subscription successful:', pushSubscription);

            // Save subscription to server
            await savePushSubscription(pushSubscription);
        }

        console.log('🎉 Push notifications initialized successfully');
        if (window.notificationManager) {
            notificationManager.success('Push notifications enabled successfully!', 3000);
        }

    } catch (error) {
        console.error('❌ Failed to initialize push notifications:', error);
        if (window.notificationManager) {
            notificationManager.error('Failed to enable push notifications: ' + error.message, 8000);
        }
    }
}

// Test Push Notification
async function testPushNotification() {
    try {
        console.log('Testing push notification...');
        const response = await fetch('/api/test-push-notification', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        const result = await response.json();
        if (result.success) {
            console.log('Test push notification sent');
            if (window.notificationManager) {
                notificationManager.success('Test notification sent! Check your device.', 5000);
            }
        } else {
            console.error('Failed to send test notification:', result.error);
            if (window.notificationManager) {
                notificationManager.error('Failed to send test notification: ' + result.error, 5000);
            }
        }

    } catch (error) {
        console.error('Error sending test notification:', error);
        if (window.notificationManager) {
            notificationManager.error('Error sending test notification. Please try again.', 5000);
        }
    }
}

// Request notification permission
async function requestNotificationPermission() {
    if ('Notification' in window) {
        console.log('Current notification permission:', Notification.permission);

        if (Notification.permission === 'default') {
            console.log('Requesting notification permission...');

            try {
                const permission = await Notification.requestPermission();

                if (permission === 'granted') {
                    console.log('Notification permission granted');
                    if (window.notificationManager) {
                        notificationManager.success('🔔 Notifications enabled! You will receive real-time updates.', 5000);
                    }
                    // Reinitialize push notifications after permission granted
                    if (navigator.serviceWorker.ready) {
                        navigator.serviceWorker.ready.then(registration => {
                            initializePushNotifications(registration);
                        });
                    }
                } else {
                    console.log('Notification permission denied');
                    if (window.notificationManager) {
                        notificationManager.warning('❌ Notifications blocked. Enable them in browser settings for better experience.', 10000);
                    }
                }
            } catch (error) {
                console.error('Error requesting notification permission:', error);
                if (window.notificationManager) {
                    notificationManager.error('Error requesting notification permission. Please enable manually in browser settings.', 8000);
                }
            }
        } else if (Notification.permission === 'granted') {
            console.log('Notification permission already granted');
        } else {
            console.log('Notification permission denied');
            if (window.notificationManager) {
                notificationManager.warning('⚠️ Notifications are blocked. Click on the lock icon in the address bar to enable them.', 12000);
            }
        }
    } else {
        console.warn('This browser does not support notifications');
        if (window.notificationManager) {
            notificationManager.warning('This browser does not support push notifications.', 8000);
        }
    }
}

// Handle incoming notifications with enhanced mobile support
function handleNotification(data) {
    const { type, message, timestamp } = data;

    console.log('Received notification:', data);

    // Show visual notification
    if (window.notificationManager) {
        if (type === 'new_refill' || type === 'delivery_available') {
            notificationManager.info(message, 8000);
        } else if (type === 'refill_accepted' || type === 'refill_ready' || type === 'delivery_complete') {
            notificationManager.success(message, 10000);
        } else if (type === 'delivery_pickup') {
            notificationManager.warning(message, 8000);
        } else {
            notificationManager.info(message, 6000);
        }
    } else {
        console.error('Notification manager not available');
        showMobileFallbackNotification(message, type);
    }

    // Play notification sound
    playNotificationSound(type);

    // Enhanced vibration for mobile devices
    if ('vibrate' in navigator) {
        navigator.vibrate([300, 100, 300, 100, 300]);
    }

    // Additional mobile-specific features
    if (isMobileDevice()) {
        flashScreen();
        showTitleNotification(message);
    }

    // Update page content if needed
    updatePageContent(data);
}

// Detect mobile device
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// Play notification sound
function playNotificationSound(type) {
    const audio = new Audio('/static/notification-sound.mp3');
    audio.volume = 0.5;
    audio.play().catch(e => console.log('Could not play sound:', e));
}

// Flash screen for attention
function flashScreen() {
    const flashDiv = document.createElement('div');
    flashDiv.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(255, 255, 255, 0.8);
        z-index: 9998;
        pointer-events: none;
        animation: flash 0.5s ease-out;
    `;

    if (!document.getElementById('flash-style')) {
        const style = document.createElement('style');
        style.id = 'flash-style';
        style.textContent = `
            @keyframes flash {
                0% { opacity: 0; }
                50% { opacity: 1; }
                100% { opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(flashDiv);
    setTimeout(() => flashDiv.remove(), 500);
}

// Show notification in page title
function showTitleNotification(message) {
    const originalTitle = document.title;
    let blinkCount = 0;
    const maxBlinks = 10;

    const blinkInterval = setInterval(() => {
        if (blinkCount >= maxBlinks) {
            document.title = originalTitle;
            clearInterval(blinkInterval);
            return;
        }

        document.title = blinkCount % 2 === 0 ? '🔔 NEW NOTIFICATION!' : originalTitle;
        blinkCount++;
    }, 800);
}

// Mobile fallback notification
function showMobileFallbackNotification(message, type) {
    console.log('📱 Showing mobile fallback notification');

    const alertDiv = document.createElement('div');
    alertDiv.className = 'mobile-notification-alert';
    alertDiv.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: linear-gradient(135deg, #007bff, #0056b3);
        color: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.6);
        z-index: 10000;
        text-align: center;
        font-size: 18px;
        font-weight: bold;
        max-width: 85%;
        animation: bounceIn 0.5s ease;
        border: 2px solid rgba(255,255,255,0.3);
    `;

    if (!document.getElementById('mobile-notification-style')) {
        const style = document.createElement('style');
        style.id = 'mobile-notification-style';
        style.textContent = `
            @keyframes bounceIn {
                0% { 
                    transform: translate(-50%, -50%) scale(0.3);
                    opacity: 0;
                }
                50% { 
                    transform: translate(-50%, -50%) scale(1.05);
                }
                70% { 
                    transform: translate(-50%, -50%) scale(0.9);
                }
                100% { 
                    transform: translate(-50%, -50%) scale(1);
                    opacity: 1;
                }
            }
            @keyframes pulse {
                0% { transform: translate(-50%, -50%) scale(1); }
                50% { transform: translate(-50%, -50%) scale(1.02); }
                100% { transform: translate(-50%, -50%) scale(1); }
            }
        `;
        document.head.appendChild(style);
    }

    const emoji = type === 'new_refill' ? '🍴' : type === 'refill_ready' ? '✅' : type === 'delivery_pickup' ? '🚛' : '🔔';

    alertDiv.innerHTML = `
        <div style="margin-bottom: 15px; font-size: 32px;">${emoji}</div>
        <div style="line-height: 1.4; margin-bottom: 20px;">${message}</div>
        <button onclick="this.parentElement.remove()" style="
            padding: 12px 24px;
            background: rgba(255,255,255,0.2);
            border: 2px solid rgba(255,255,255,0.4);
            border-radius: 8px;
            color: white;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: all 0.3s ease;
        " onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">
            समझ गया ✓
        </button>
    `;

    document.body.appendChild(alertDiv);

    // Auto-remove after 15 seconds
    setTimeout(() => {
        if (alertDiv.parentElement) {
            alertDiv.style.animation = 'fadeOut 0.5s ease';
            setTimeout(() => alertDiv.remove(), 500);
        }
    }, 15000);
}

// Update page content based on notification
function updatePageContent(data) {
    // Refresh specific page elements based on notification type
    if (data.type === 'new_refill' && window.location.pathname.includes('/kitchen/')) {
        // Refresh kitchen dashboard or refill requests
        setTimeout(() => {
            if (typeof refreshRefillRequests === 'function') {
                refreshRefillRequests();
            }
        }, 1000);
    } else if (data.type === 'refill_ready' && window.location.pathname.includes('/cart/')) {
        // Refresh cart dashboard
        setTimeout(() => {
            if (typeof refreshCartDashboard === 'function') {
                refreshCartDashboard();
            }
        }, 1000);
    }
}

// Initialize other app features
function initializeFeatures() {
    // Initialize any other app-specific features
    console.log('Initializing app features...');

    // Add global keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl+R for refresh (prevent default and show notification)
        if (e.ctrlKey && e.key === 'r') {
            e.preventDefault();
            if (window.notificationManager) {
                notificationManager.info('Use the refresh button or pull to refresh on mobile', 3000);
            }
        }
    });

    // Add pull-to-refresh for mobile
    if (isMobileDevice()) {
        initializePullToRefresh();
    }
}

// Initialize pull-to-refresh for mobile
function initializePullToRefresh() {
    let startY = 0;
    let currentY = 0;
    let pulling = false;

    document.addEventListener('touchstart', function(e) {
        startY = e.touches[0].pageY;
        pulling = window.scrollY === 0;
    });

    document.addEventListener('touchmove', function(e) {
        if (!pulling) return;

        currentY = e.touches[0].pageY;
        const diffY = currentY - startY;

        if (diffY > 100) {
            e.preventDefault();
            // Show pull-to-refresh indicator
            if (!document.querySelector('.pull-refresh-indicator')) {
                const indicator = document.createElement('div');
                indicator.className = 'pull-refresh-indicator';
                indicator.textContent = '↓ Pull to refresh';
                indicator.style.cssText = `
                    position: fixed;
                    top: 10px;
                    left: 50%;
                    transform: translateX(-50%);
                    background: #007bff;
                    color: white;
                    padding: 10px 20px;
                    border-radius: 25px;
                    z-index: 9999;
                    font-size: 14px;
                `;
                document.body.appendChild(indicator);
            }
        }
    });

    document.addEventListener('touchend', function(e) {
        if (!pulling) return;

        const diffY = currentY - startY;
        const indicator = document.querySelector('.pull-refresh-indicator');

        if (indicator) {
            indicator.remove();
        }

        if (diffY > 100) {
            // Trigger refresh
            window.location.reload();
        }

        pulling = false;
    });
}

// Utility functions
function showNotification(message, type = 'info') {
    if (window.notificationManager) {
        notificationManager.show(message, type);
    } else {
        console.log('Notification:', message);
    }
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IN', {
        style: 'currency',
        currency: 'INR'
    }).format(amount);
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('en-IN');
}

// Export for global use
window.showNotification = showNotification;
window.formatCurrency = formatCurrency;
window.formatDate = formatDate;
window.requestNotificationPermission = requestNotificationPermission;
window.testPushNotification = testPushNotification;

// Debug functions for testing
window.debugPushNotifications = function() {
    console.log('=== PUSH NOTIFICATION DEBUG ===');
    console.log('Push Subscription:', pushSubscription);
    console.log('Notification Permission:', Notification.permission);
    console.log('Service Worker Registration:', navigator.serviceWorker);
    console.log('User Agent:', navigator.userAgent);
    console.log('Is Mobile:', isMobileDevice());
    console.log('VAPID Support:', 'PushManager' in window);

    if (navigator.serviceWorker.controller) {
        console.log('Service Worker Controller:', navigator.serviceWorker.controller);
    } else {
        console.log('❌ No Service Worker Controller');
    }

    // Check push subscription status
    if (navigator.serviceWorker.ready) {
        navigator.serviceWorker.ready.then(registration => {
            registration.pushManager.getSubscription().then(subscription => {
                console.log('Current Push Subscription:', subscription);
            });
        });
    }
};

// Add notification enable button for mobile
window.addNotificationButton = function() {
    if (isMobileDevice() && Notification.permission !== 'granted') {
        const button = document.createElement('button');
        button.innerHTML = '🔔 Enable Mobile Notifications';
        button.className = 'btn btn-warning btn-sm';
        button.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            padding: 12px 16px;
            border-radius: 25px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: pulse 2s infinite;
        `;

        button.onclick = async function() {
            await requestNotificationPermission();
            if (Notification.permission === 'granted') {
                button.remove();
            }
        };

        document.body.appendChild(button);

        // Add CSS animation
        const style = document.createElement('style');
        style.innerHTML = `
            @keyframes pulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.05); }
                100% { transform: scale(1); }
            }
        `;
        document.head.appendChild(style);
    }
};

// Initialize Socket.IO connection
function initializeSocketIO() {
    if (window.socket && window.socket.connected) {
        console.log('Socket already connected');
        return;
    }

    window.socket = io();

    window.socket.on('connect', function() {
        console.log('Connected to server');

        // Join kitchen room if user has kitchen
        if (window.userKitchenId) {
            window.socket.emit('join_kitchen', {kitchen_id: window.userKitchenId});
            console.log('Joining kitchen:', window.userKitchenId);
        }
    });
}

// Force enable mobile notifications
function enableMobileNotifications() {
    console.log('📱 Enabling mobile notifications...');

    if ('serviceWorker' in navigator && 'PushManager' in window) {
        if (Notification.permission === 'default') {
            requestNotificationPermission();
        } else if (Notification.permission === 'granted') {
            // Reinitialize push subscription
            navigator.serviceWorker.ready.then(registration => {
                initializePushNotifications(registration);
            });
        }
    }
}

// Handle PWA session restoration
function handlePWASessionRestore() {
    console.log('🔄 Handling PWA session restore...');
    
    // Check if we're on login page but should be authenticated
    if (window.location.pathname === '/login' || window.location.pathname === '/') {
        // Try to access dashboard to check session
        fetch('/dashboard', {
            method: 'GET',
            credentials: 'include',
            redirect: 'manual'
        }).then(response => {
            if (response.ok && response.status === 200) {
                console.log('✅ Session valid, redirecting to dashboard');
                window.location.replace('/dashboard');
            } else {
                console.log('❌ Session invalid, staying on login');
                // Make sure we're on the login page
                if (window.location.pathname !== '/login') {
                    window.location.replace('/login');
                }
            }
        }).catch(error => {
            console.log('🚫 Session check failed, redirecting to login:', error);
            if (window.location.pathname !== '/login') {
                window.location.replace('/login');
            }
        });
    }
}

// Handle PWA lifecycle events
if ('serviceWorker' in navigator) {
    window.addEventListener('beforeunload', function() {
        // Store timestamp when app is being closed
        localStorage.setItem('sadakchef_last_close', Date.now());
    });

    window.addEventListener('load', function() {
        // Check if app was recently closed (within 24 hours)
        const lastClose = localStorage.getItem('sadakchef_last_close');
        if (lastClose) {
            const timeDiff = Date.now() - parseInt(lastClose);
            if (timeDiff < 24 * 60 * 60 * 1000) { // 24 hours
                console.log('🔄 App reopened within 24 hours, checking session...');
                // Session should still be valid
            }
        }
    });
}

console.log('📄 App.js loaded successfully');