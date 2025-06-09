import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash
from datetime import datetime, date, timedelta
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from pywebpush import webpush, WebPushException
import json

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Initialize Flask-Login
login_manager = LoginManager()

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "sadakchef_secret_key_2024")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure session settings for better persistence
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = False  # Allow JavaScript access for PWA
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 * 30  # 30 days
app.config['SESSION_COOKIE_NAME'] = 'sadakchef_session'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_USE_SIGNER'] = True

# Configure the database to use Neon
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True
}

# VAPID Keys for Web Push
app.config['VAPID_PRIVATE_KEY'] = os.environ.get('VAPID_PRIVATE_KEY')
app.config['VAPID_PUBLIC_KEY'] = os.environ.get('VAPID_PUBLIC_KEY')
app.config['VAPID_CLAIMS'] = json.loads(os.environ.get('VAPID_CLAIMS', '{"sub": "mailto:admin@sadakchef.com"}'))

# Log VAPID key status for debugging
if app.config['VAPID_PRIVATE_KEY'] and app.config['VAPID_PUBLIC_KEY']:
    print("✅ VAPID keys loaded successfully from environment")
    print(f"Public Key: {app.config['VAPID_PUBLIC_KEY']}")
else:
    print("❌ VAPID keys not found in environment variables")
    print("Please add VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to .env file")

# Initialize extensions
db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = 'basic'  # Use basic instead of strong
login_manager.remember_cookie_duration = timedelta(days=30)
login_manager.remember_cookie_secure = False  # Set to True in production with HTTPS
login_manager.remember_cookie_httponly = True

# Add custom template filters
@app.template_filter('strftime')
def strftime_filter(date_str, fmt='%d/%m/%Y'):
    if date_str == 'today':
        return date.today().strftime(fmt)
    return date_str

login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

with app.app_context():
    # Import models to ensure tables are created
    import models
    import routes
    import scheduler

    # Create all tables
    db.create_all()

    # Initialize scheduler
    scheduler.init_scheduler()