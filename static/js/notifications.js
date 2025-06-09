// Push Notification Service
class PushNotificationService {
    constructor() {
        this.registration = null;
        this.vapidPublicKey = null;
        this.isSupported = 'serviceWorker' in navigator && 'PushManager' in window;
        this.isSubscribed = false;
    }

    async init() {
        if (!this.isSupported) {
            console.warn('Push notifications not supported');
            return false;
        }

        try {
            // Register service worker
            this.registration = await navigator.serviceWorker.register('/sw.js');
            console.log('Service Worker registered:', this.registration);

            // Get VAPID public key
            const response = await fetch('/api/vapid-public-key');
            const data = await response.json();
            this.vapidPublicKey = data.public_key;
            console.log('VAPID public key loaded');

            // Check existing subscription
            const subscription = await this.registration.pushManager.getSubscription();
            this.isSubscribed = !!subscription;

            return true;
        } catch (error) {
            console.error('Failed to initialize push notifications:', error);
            return false;
        }
    }

    async requestPermission() {
        if (!this.isSupported) {
            throw new Error('Push notifications not supported');
        }

        const permission = await Notification.requestPermission();
        console.log('Notification permission:', permission);

        if (permission === 'granted') {
            await this.subscribe();
            return true;
        }

        return false;
    }

    async subscribe() {
        if (!this.registration || !this.vapidPublicKey) {
            throw new Error('Service not initialized');
        }

        try {
            const subscription = await this.registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: this.urlBase64ToUint8Array(this.vapidPublicKey)
            });

            // Send subscription to server
            const response = await fetch('/api/push-subscription', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(subscription.toJSON())
            });

            if (response.ok) {
                this.isSubscribed = true;
                console.log('Push subscription successful');
                return true;
            } else {
                throw new Error('Failed to save subscription');
            }
        } catch (error) {
            console.error('Push subscription failed:', error);
            throw error;
        }
    }

    async unsubscribe() {
        if (!this.registration) {
            return false;
        }

        try {
            const subscription = await this.registration.pushManager.getSubscription();
            if (subscription) {
                await subscription.unsubscribe();

                // Notify server
                await fetch('/api/push-subscription', {
                    method: 'DELETE',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(subscription.toJSON())
                });
            }

            this.isSubscribed = false;
            console.log('Push unsubscribed');
            return true;
        } catch (error) {
            console.error('Push unsubscribe failed:', error);
            return false;
        }
    }

    async testNotification() {
        try {
            const response = await fetch('/api/test-push-notification', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const result = await response.json();
            return result;
        } catch (error) {
            console.error('Test notification failed:', error);
            throw error;
        }
    }

    urlBase64ToUint8Array(base64String) {
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
}

// Initialize notification service
const pushService = new PushNotificationService();

// Global functions for UI interaction
window.enableNotifications = async function() {
    try {
        const enabled = await pushService.requestPermission();
        if (enabled) {
            showToast('Push notifications enabled!', 'success');
            updateNotificationUI(true);
        } else {
            showToast('Push notifications denied', 'error');
        }
    } catch (error) {
        showToast('Failed to enable notifications: ' + error.message, 'error');
    }
};

window.disableNotifications = async function() {
    try {
        const disabled = await pushService.unsubscribe();
        if (disabled) {
            showToast('Push notifications disabled', 'info');
            updateNotificationUI(false);
        }
    } catch (error) {
        showToast('Failed to disable notifications', 'error');
    }
};

function updateNotificationUI(enabled) {
    const enableBtn = document.getElementById('enableNotifications');
    const disableBtn = document.getElementById('disableNotifications');
    const statusIndicator = document.getElementById('notificationStatus');

    if (enableBtn && disableBtn) {
        enableBtn.style.display = enabled ? 'none' : 'inline-block';
        disableBtn.style.display = enabled ? 'inline-block' : 'none';
    }

    if (statusIndicator) {
        statusIndicator.textContent = enabled ? 'Enabled' : 'Disabled';
        statusIndicator.className = enabled ? 'badge bg-success' : 'badge bg-secondary';
    }
}

function showToast(message, type = 'info') {
    // Create toast if doesn't exist
    let toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'position-fixed top-0 end-0 p-3';
        toastContainer.style.zIndex = '1055';
        document.body.appendChild(toastContainer);
    }

    const toastId = 'toast-' + Date.now();
    const toastHtml = `
        <div id="${toastId}" class="toast" role="alert">
            <div class="toast-header">
                <strong class="me-auto text-${type}">SadakChef</strong>
                <small>${new Date().toLocaleTimeString('en-IN', { 
            timeZone: 'Asia/Kolkata',
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit',
            hour12: true 
        }) + ' IST'}</small>
                <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;

    toastContainer.insertAdjacentHTML('beforeend', toastHtml);

    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement);
    toast.show();

    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toastElement) {
            toastElement.remove();
        }
    }, 5000);
}

// Export for global access
window.pushService = pushService;