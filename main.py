from app import app, socketio
from flask import send_from_directory, jsonify, request
from routes import send_push_notification
from flask_login import current_user

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js')

@app.route('/api/test-push-notification', methods=['POST'])
def test_push_notification():
    try:
        # Send a test notification to the current user
        if not current_user.is_authenticated:
            return jsonify({"success": False, "error": "User not authenticated"}), 401
        # Always send a dict payload, not a string
        send_push_notification(
            user_id=current_user.id,
            title="Test Notification",
            body="This is a test push notification from SadakChef!",
            data={"url": "/kitchen/dashboard"}
        )
        return jsonify({"success": True, "message": "Test push notification sent!"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
