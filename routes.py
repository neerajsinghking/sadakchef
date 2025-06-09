from flask import render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_socketio import emit, join_room, leave_room
from werkzeug.security import check_password_hash
from datetime import datetime, date, timedelta
import pytz
from app import app, db, socketio
from models import *
from datetime import date
from forms import *
from werkzeug.security import generate_password_hash
from utils import *
import logging
import json
from pywebpush import webpush, WebPushException

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Push Notification Helper Functions
def send_push_notification(user_id, title, body, data=None):
    """Send push notification to user's subscribed devices"""
    try:
        subscriptions = PushSubscription.query.filter_by(user_id=user_id, is_active=True).all()

        if not subscriptions:
            logger.info(f"No push subscriptions found for user {user_id}")
            return

        payload = {
            'title': title,
            'body': body,
            'icon': '/static/generated-icon.png',
            'badge': '/static/generated-icon.png',
            'data': data or {},
            'vibrate': [300, 100, 300, 100, 300],
            'requireInteraction': True,
            'actions': [
                {
                    'action': 'view',
                    'title': 'View',
                    'icon': '/static/generated-icon.png'
                },
                {
                    'action': 'close',
                    'title': 'Close',
                    'icon': '/static/generated-icon.png'
                }
            ]
        }

        for subscription in subscriptions:
            try:
                webpush(
                    subscription_info=subscription.to_dict(),
                    data=json.dumps(payload),
                    vapid_private_key=app.config['VAPID_PRIVATE_KEY'],
                    vapid_claims=app.config['VAPID_CLAIMS']
                )
                subscription.last_used = datetime.utcnow()
                logger.info(f"Push notification sent successfully to user {user_id}")

            except WebPushException as ex:
                logger.error(f"Push notification failed for user {user_id}: {ex}")
                if ex.response and ex.response.status_code in [404, 410]:
                    # Subscription is no longer valid
                    subscription.is_active = False

        db.session.commit()

    except Exception as e:
        logger.error(f"Error sending push notification to user {user_id}: {str(e)}")

def send_push_to_kitchen(kitchen_id, title, body, data=None):
    """Send push notification to all users in a kitchen"""
    try:
        users = User.query.filter_by(kitchen_id=kitchen_id, is_active=True).all()
        for user in users:
            send_push_notification(user.id, title, body, data)
    except Exception as e:
        logger.error(f"Error sending push to kitchen {kitchen_id}: {str(e)}")

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        logger.info(f"User {current_user.name} connected - joining kitchen_{current_user.kitchen_id} and user_{current_user.id}")
        join_room(f"kitchen_{current_user.kitchen_id}")
        join_room(f"user_{current_user.id}")
        emit('status', {'msg': f'{current_user.name} has connected!'})
    else:
        logger.info("Anonymous user connected")

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        logger.info(f"User {current_user.name} disconnected")
        leave_room(f"kitchen_{current_user.kitchen_id}")
        leave_room(f"user_{current_user.id}")

@socketio.on('join_kitchen')
def handle_join_kitchen(data):
    if current_user.is_authenticated:
        kitchen_id = data.get('kitchen_id', current_user.kitchen_id)
        logger.info(f"User {current_user.name} joining kitchen_{kitchen_id}")
        join_room(f"kitchen_{kitchen_id}")
        emit('status', {'msg': f'{current_user.name} joined kitchen {kitchen_id}!'})

# Notification functions
def send_notification_to_kitchen(kitchen_id, notification_type, message, data=None):
    """Send notification to all users in a kitchen"""
    notification_data = {
        'type': notification_type,
        'message': message,
        'data': data or {},
        'timestamp': get_indian_time().isoformat()
    }
    logger.info(f"Sending kitchen notification to kitchen_{kitchen_id}: {notification_data}")
    socketio.emit('notification', notification_data, room=f"kitchen_{kitchen_id}")

def send_notification_to_user(user_id, notification_type, message, data=None):
    """Send notification to specific user"""
    notification_data = {
        'type': notification_type,
        'message': message,
        'data': data or {},
        'timestamp': get_indian_time().isoformat()
    }
    logger.info(f"Sending user notification to user_{user_id}: {notification_data}")
    socketio.emit('notification', notification_data, room=f"user_{user_id}")

def send_refill_notification(refill_request, action):
    """Send notifications for refill request updates"""
    kitchen_id = refill_request.kitchen_id
    cart_staff_id = refill_request.cart_staff_id

    if action == 'new_request':
        # Notify kitchen manager about new refill request
        message = f"New refill request: {refill_request.sop.recipe_name} ({refill_request.kg_request}kg) from {refill_request.cart_staff.name}"
        send_notification_to_kitchen(kitchen_id, 'new_refill', message)
        send_push_to_kitchen(kitchen_id, 'New Refill Request', message, {
            'type': 'new_refill',
            'refill_id': refill_request.id,
            'url': '/kitchen/refill_requests'
        })

    elif action == 'accepted':
        # Notify cart staff that request was accepted
        message = f"Your refill request for {refill_request.sop.recipe_name} has been accepted by kitchen"
        send_notification_to_user(cart_staff_id, 'refill_accepted', message)
        send_push_notification(cart_staff_id, 'Request Accepted', message, {
            'type': 'refill_accepted',
            'refill_id': refill_request.id,
            'url': '/cart/dashboard'
        })

    elif action == 'prepared':
        # Notify cart staff that food is ready
        message = f"Your {refill_request.sop.recipe_name} refill is ready for pickup!"
        send_notification_to_user(cart_staff_id, 'refill_ready', message)
        send_push_notification(cart_staff_id, 'Food Ready!', message, {
            'type': 'refill_ready',
            'refill_id': refill_request.id,
            'url': '/cart/dashboard'
        })

        # Also notify delivery staff
        delivery_message = f"New delivery available: {refill_request.sop.recipe_name} ({refill_request.kg_request}kg)"
        send_notification_to_kitchen(kitchen_id, 'delivery_available', delivery_message)
        send_push_to_kitchen(kitchen_id, 'New Delivery Available', delivery_message, {
            'type': 'delivery_available',
            'refill_id': refill_request.id,
            'url': '/delivery/dashboard'
        })

    elif action == 'picked_up':
        # Notify cart staff that delivery is on the way
        message = f"Your {refill_request.sop.recipe_name} refill has been picked up for delivery"
        send_notification_to_user(cart_staff_id, 'delivery_pickup', message)
        send_push_notification(cart_staff_id, 'Out for Delivery', message, {
            'type': 'delivery_pickup',
            'refill_id': refill_request.id,
            'url': '/cart/dashboard'
        })

    elif action == 'delivered':
        # Notify cart staff that delivery is complete
        message = f"Your {refill_request.sop.recipe_name} refill has been delivered!"
        send_notification_to_user(cart_staff_id, 'delivery_complete', message)
        send_push_notification(cart_staff_id, 'Delivery Complete', message, {
            'type': 'delivery_complete',
            'refill_id': refill_request.id,
            'url': '/cart/dashboard'
        })

# Make utility functions available in templates
@app.context_processor
def utility_processor():
    return dict(format_indian_time=format_indian_time)

# Utility function to get current Indian time
def get_indian_time():
    indian_tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(indian_tz).replace(tzinfo=None)

# Utility function to convert UTC to Indian time for display
def format_indian_time(utc_time):
    if utc_time is None:
        return None
    if not utc_time.tzinfo:
        utc_time = pytz.utc.localize(utc_time)
    indian_tz = pytz.timezone('Asia/Kolkata')
    indian_time = utc_time.astimezone(indian_tz)
    return indian_time

# Authentication routes
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            # Use permanent session and remember user for PWA
            session.permanent = True
            login_user(user, remember=True, duration=timedelta(days=30), fresh=False)
            # Store additional session data for PWA
            session['user_role'] = user.role
            session['user_kitchen_id'] = user.kitchen_id
            session['user_name'] = user.name
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')

    return render_template('login.html', form=form)

# Handle any undefined routes for PWA
@app.route('/<path:path>')
def catch_all(path):
    # For PWA, redirect unknown routes to login if not authenticated
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    else:
        return redirect(url_for('dashboard'))

@app.route('/logout')
@login_required
def logout():
    # Clear all session data
    session.clear()
    # Logout the user
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'kitchen_manager':
        return redirect(url_for('kitchen_dashboard'))
    elif current_user.role == 'cart_staff':
        return redirect(url_for('cart_dashboard'))
    elif current_user.role == 'delivery_staff':
        return redirect(url_for('delivery_dashboard'))
    else:
        flash('Invalid role', 'error')
        return redirect(url_for('login'))

# Admin routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get statistics
    total_kitchens = Kitchen.query.filter_by(is_active=True).count()
    total_users = User.query.filter_by(is_active=True).count()
    total_carts = Cart.query.filter_by(is_active=True).count()

    # Get recent activities
    recent_refills = RefillRequest.query.join(User, RefillRequest.cart_staff_id == User.id).join(SOP, RefillRequest.sop_id == SOP.id).order_by(RefillRequest.request_time.desc()).limit(10).all()
    recent_sales = DailySales.query.order_by(DailySales.created_at.desc()).limit(10).all()

    # Get alerts
    alerts = []
    today = date.today()
    critical_inventory = InventoryTracker.query.filter_by(status='Critical', date=today).all()
    low_inventory = InventoryTracker.query.filter_by(status='Low', date=today).all()

    for item in critical_inventory:
        alerts.append({
            'type': 'critical',
            'message': f'Critical stock: {item.ingredient.name} at {item.kitchen.city}',
            'time': 'Today'
        })

    for item in low_inventory:
        alerts.append({
            'type': 'warning', 
            'message': f'Low stock: {item.ingredient.name} at {item.kitchen.city}',
            'time': 'Today'
        })

    return render_template('admin/dashboard.html', 
                         total_kitchens=total_kitchens,
                         total_users=total_users, 
                         total_carts=total_carts,
                         recent_refills=recent_refills,
                         recent_sales=recent_sales,
                         alerts=alerts)

@app.route('/admin/add_user', methods=['GET', 'POST'])
@login_required
def admin_add_user():
    if current_user.role != 'admin':
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('dashboard'))

    form = UserForm()
    # Get unique cities from kitchens
    cities = db.session.query(Kitchen.city).distinct().filter_by(is_active=True).all()
    form.city.choices = [('', 'Select City')] + [(city[0], city[0]) for city in cities]
    form.kitchen_id.choices = [(k.id, k.kitchen_id) for k in Kitchen.query.filter_by(is_active=True).all()]

    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already exists', 'error')
            return render_template('admin/add_user.html', form=form)

        # Check if email already exists
        if form.email.data:
            existing_email = User.query.filter_by(email=form.email.data).first()
            if existing_email:
                flash('Email already exists', 'error')
                return render_template('admin/add_user.html', form=form)

        # Create new user
        new_user = User(
            username=form.username.data,
            name=form.name.data,
            role=form.role.data,
            kitchen_id=form.kitchen_id.data if form.kitchen_id.data else None,
            location=form.location.data,
            mobile_no=form.mobile_no.data,
            email=form.email.data,
            address=form.address.data,
            salary=form.salary.data,
            incentive=form.incentive.data,
            is_active=True
        )

        # Set password using the model's method
        new_user.set_password(form.password.data)

        try:
            db.session.add(new_user)
            db.session.flush()  # Get the user ID

            # If cart staff, create cart entry
            if form.role.data == 'cart_staff':
                # Generate thela_id: CART + user_id (3 digits)
                thela_id = f"CART{str(new_user.id).zfill(3)}"

                cart = Cart(
                    thela_id=thela_id,
                    cart_staff_id=new_user.id,
                    kitchen_id=new_user.kitchen_id,
                    location=form.location.data
                )
                db.session.add(cart)

            db.session.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding user', 'error')
            return render_template('admin/add_user.html', form=form)

    # Get all users with their kitchen information for display
    all_users = User.query.join(Kitchen, User.kitchen_id == Kitchen.id, isouter=True).all()

    return render_template('admin/add_user.html', form=form, all_users=all_users)

@app.route('/api/users')
@login_required
def api_users():
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    users = User.query.all()
    users_data = []

    for user in users:
        user_data = {
            'id': user.id,
            'name': user.name,
            'username': user.username,
            'role': user.role,
            'city': user.kitchen.city if user.kitchen else 'No Kitchen',
            'kitchen': user.kitchen.kitchen_id if user.kitchen else 'No Kitchen',
            'kitchen_id': user.kitchen.id if user.kitchen else None,
            'mobile_no': user.mobile_no or '',
            'email': user.email or '',
            'is_active': user.is_active,
            'salary': user.salary or 0,
            'incentive': user.incentive or 0
        }
        users_data.append(user_data)

    return jsonify(users_data)

@app.route('/api/kitchens/<city>')
@login_required
def api_kitchens_by_city(city):
    if current_user.role != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    kitchens = Kitchen.query.filter_by(city=city, is_active=True).all()
    kitchens_data = []

    for kitchen in kitchens:
        kitchen_data = {
            'id': kitchen.id,
            'kitchen_id': kitchen.kitchen_id,
            'location': kitchen.location,
            'city': kitchen.city
        }
        kitchens_data.append(kitchen_data)

    return jsonify(kitchens_data)

@app.route('/admin/add_kitchen', methods=['GET', 'POST'])
@login_required
def admin_add_kitchen():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    form = KitchenForm()

    if form.validate_on_submit():
        # Generate kitchen ID in format: City + ID + Location (e.g., Mumbai001Andheri)
        kitchen_count = Kitchen.query.count() + 1
        kitchen_id = f"{form.city.data}{kitchen_count:03d}{form.location.data}"

        kitchen = Kitchen(
            kitchen_id=kitchen_id,
            city=form.city.data,
            location=form.location.data,
            address=form.address.data
        )

        db.session.add(kitchen)
        db.session.commit()

        flash(f'Kitchen added successfully with ID: {kitchen_id}', 'success')
        return redirect(url_for('admin_add_kitchen'))

    # Get all kitchens for display
    kitchens = Kitchen.query.order_by(Kitchen.created_at.desc()).all()

    return render_template('admin/add_kitchen.html', form=form, kitchens=kitchens)

@app.route('/admin/add_ingredient', methods=['GET', 'POST'])
@login_required
def admin_add_ingredient():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    form = IngredientForm()

    if form.validate_on_submit():
        ingredient = Ingredient(
            name=form.name.data,
            category=form.category.data,
            unit=form.unit.data,
            minimum_stock=form.minimum_stock.data
        )

        db.session.add(ingredient)
        db.session.commit()

        flash('Ingredient added successfully', 'success')
        return redirect(url_for('admin_add_ingredient'))

    # Get all ingredients for display
    ingredients = Ingredient.query.order_by(Ingredient.created_at.desc()).all()

    return render_template('admin/add_ingredient.html', form=form, ingredients=ingredients)

@app.route('/admin/add_sop', methods=['GET', 'POST'])
@login_required
def admin_add_sop():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    form = SOPForm()

    # Get all ingredients for dropdown
    ingredients_query = Ingredient.query.all()
    ingredients = [{'id': ing.id, 'name': ing.name, 'category': ing.category, 'unit': ing.unit} for ing in ingredients_query]

    if request.method == 'POST' and form.validate_on_submit():
        try:
            # Create new SOP
            sop = SOP(
                recipe_name=form.recipe_name.data,
                base_quantity=form.base_quantity.data,
                recipe_rate=form.recipe_rate.data,
                description=form.description.data
            )

            db.session.add(sop)
            db.session.flush()  # Get the SOP ID

            # Process ingredients from form data
            ingredient_counter = 1
            while True:
                ingredient_id_key = f'ingredient_{ingredient_counter}_id'
                quantity_key = f'ingredient_{ingredient_counter}_quantity'
                note_key = f'ingredient_{ingredient_counter}_note'

                if ingredient_id_key not in request.form:
                    break

                ingredient_id = request.form.get(ingredient_id_key)
                quantity = request.form.get(quantity_key)
                note = request.form.get(note_key, '')

                if ingredient_id and quantity:
                    try:
                        sop_ingredient = SOPIngredient(
                            sop_id=sop.id,
                            ingredient_id=int(ingredient_id),
                            quantity=float(quantity),
                            note=note if note else None
                        )
                        db.session.add(sop_ingredient)
                    except (ValueError, TypeError):
                        continue  # Skip invalid entries

                ingredient_counter += 1

            db.session.commit()
            flash(f'SOP "{form.recipe_name.data}" added successfully with ingredients!', 'success')
            return redirect(url_for('admin_add_sop'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error adding SOP: {str(e)}', 'error')

    # Get all SOPs for display
    sops = SOP.query.all()

    return render_template('admin/add_sop.html', form=form, ingredients=ingredients, sops=sops)

@app.route('/api/calculate_sop/<int:sop_id>/<float:quantity>')
@login_required
def api_calculate_sop(sop_id, quantity):
    """API endpoint to calculate SOP ingredients for given quantity"""
    try:
        print(f"API called with SOP ID: {sop_id}, Quantity: {quantity}")

        # Validate inputs
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400

        sop = SOP.query.get(sop_id)
        if not sop:
            print(f"SOP {sop_id} not found in database")
            return jsonify({'error': 'Recipe not found'}), 404

        print(f"Found SOP: {sop.recipe_name}")

        ingredients_data = calculate_sop_ingredients(sop_id, quantity)

        if not ingredients_data:
            print(f"No ingredients data returned for SOP {sop_id}")
            return jsonify({'error': 'No ingredients found for this recipe. Please add ingredients to this SOP first.'}), 404

        # Format the response for the frontend
        result = []
        for ingredient_data in ingredients_data:
            ingredient = ingredient_data['ingredient']
            result.append({
                'name': ingredient.name,
                'quantity': round(ingredient_data['quantity'], 2),
                'unit': ingredient.unit,
                'note': ingredient_data.get('note', '') or ''
            })

        print(f"Returning {len(result)} ingredients")
        return jsonify(result)

    except Exception as e:
        print(f"Error in API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/recipe_ingredients/<int:sop_id>')
@login_required
def api_recipe_ingredients(sop_id):
    """API endpoint to get recipe ingredients with current stock levels"""
    try:
        # Get requested quantity from query parameter
        requested_kg = float(request.args.get('kg', 1))

        print(f"API called with SOP ID: {sop_id}, Requested KG: {requested_kg}")

        # Validate inputs
        if requested_kg <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400

        sop = SOP.query.get(sop_id)
        if not sop:
            print(f"SOP {sop_id} not found in database")
            return jsonify({'error': 'Recipe not found'}), 404

        print(f"Found SOP: {sop.recipe_name}")

        # Get SOP ingredients
        sop_ingredients = SOPIngredient.query.filter_by(sop_id=sop_id).join(Ingredient).all()

        if not sop_ingredients:
            print(f"No ingredients found for SOP {sop_id}")
            return jsonify({'error': 'No ingredients found for this recipe. Please add ingredients to this SOP first.'}), 404

        # Calculate scaling factor
        scaling_factor = requested_kg / sop.base_quantity

        # Get current stock levels
        today = date.today()
        kitchen_id = current_user.kitchen_id

        result = {
            'ingredients': []
        }

        for sop_ing in sop_ingredients:
            # Calculate required quantity
            required_qty = sop_ing.quantity * scaling_factor

            # Get current stock from inventory tracker
            inventory = InventoryTracker.query.filter_by(
                kitchen_id=kitchen_id,
                ingredient_id=sop_ing.ingredient_id,
                date=today
            ).first()

            available_qty = inventory.closing_stock if inventory else 0.0

            ingredient_data = {
                'name': sop_ing.ingredient.name,
                'required': round(required_qty, 2),
                'available': round(available_qty, 2),
                'unit': sop_ing.ingredient.unit,
                'note': sop_ing.note or ''
            }

            result['ingredients'].append(ingredient_data)

        print(f"Returning {len(result['ingredients'])} ingredients")
        return jsonify(result)

    except Exception as e:
        print(f"Error in API: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/admin/performance')
@login_required
def admin_performance():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    kitchens = Kitchen.query.filter_by(is_active=True).all()
    return render_template('admin/performance.html', kitchens=kitchens)

@app.route('/admin/export_data', methods=['GET', 'POST'])
@login_required
def admin_export_data():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    tables = [
        ('users', 'Users'),
        ('kitchens', 'Kitchens'),
        ('ingredients', 'Ingredients'),
        ('sops', 'SOPs'),
        ('refill_requests', 'Refill Requests'),
        ('daily_sales', 'Daily Sales'),
        ('inventory_tracker', 'Inventory Tracker'),
        ('supplier_purchases', 'Supplier Purchases'),
        ('customer_feedback', 'Customer Feedback'),
        ('inventory_adjustments', 'Inventory Adjustments')
    ]

    if request.method == 'POST':
        table_name = request.form.get('table_name')
        return export_table_to_excel(table_name)

    return render_template('admin/export_data.html', tables=tables)

@app.route('/admin/export/<table_name>')
@login_required
def export_table(table_name):
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    response = export_table_to_excel(table_name)
    if response:
        return response
    else:
        flash('Invalid table name', 'error')
        return redirect(url_for('admin_export_data'))

@app.route('/admin/convert_timestamps', methods=['POST'])
@login_required
def convert_timestamps():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    try:
        convert_utc_to_ist_in_db()
        flash('Successfully converted all timestamps to IST', 'success')
    except Exception as e:
        flash(f'Error converting timestamps: {str(e)}', 'error')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/fix_timestamps', methods=['POST'])
@login_required
def fix_timestamps():
    if current_user.role != 'admin':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    try:
        # Fix RefillRequest timestamps that are showing incorrect values
        indian_tz = pytz.timezone('Asia/Kolkata')

        refill_requests = RefillRequest.query.all()
        for refill in refill_requests:
            # Only fix times that look incorrect (way off from request_time)
            if refill.request_time and refill.taken_by_chef_time:
                time_diff = abs((refill.taken_by_chef_time - refill.request_time).total_seconds())
                if time_diff > 86400:  # More than 1 day difference indicates wrong timezone
                    # Convert from what appears to be UTC to IST
                    if refill.taken_by_chef_time.tzinfo is None:
                        utc_time = pytz.utc.localize(refill.taken_by_chef_time)
                        ist_time = utc_time.astimezone(indian_tz)
                        refill.taken_by_chef_time = ist_time.replace(tzinfo=None)

            if refill.request_time and refill.prepared_time:
                time_diff = abs((refill.prepared_time - refill.request_time).total_seconds())
                if time_diff > 86400:
                    if refill.prepared_time.tzinfo is None:
                        utc_time = pytz.utc.localize(refill.prepared_time)
                        ist_time = utc_time.astimezone(indian_tz)
                        refill.prepared_time = ist_time.replace(tzinfo=None)

            if refill.request_time and refill.pickup_time:
                time_diff = abs((refill.pickup_time - refill.request_time).total_seconds())
                if time_diff > 86400:
                    if refill.pickup_time.tzinfo is None:
                        utc_time = pytz.utc.localize(refill.pickup_time)
                        ist_time = utc_time.astimezone(indian_tz)
                        refill.pickup_time = ist_time.replace(tzinfo=None)

            if refill.request_time and refill.delivered_time:
                time_diff = abs((refill.delivered_time - refill.request_time).total_seconds())
                if time_diff > 86400:
                    if refill.delivered_time.tzinfo is None:
                        utc_time = pytz.utc.localize(refill.delivered_time)
                        ist_time = utc_time.astimezone(indian_tz)
                        refill.delivered_time = ist_time.replace(tzinfo=None)

        db.session.commit()
        flash('Successfully fixed incorrect timestamps', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error fixing timestamps: {str(e)}', 'error')

    return redirect(url_for('admin_dashboard'))

# Push Notification API Routes
@app.route('/api/vapid-public-key')
@login_required
def get_vapid_public_key():
    """Get VAPID public key for push subscription"""
    return jsonify({'public_key': app.config['VAPID_PUBLIC_KEY']})

@app.route('/api/push-subscription', methods=['POST'])
@login_required
def save_push_subscription():
    """Save user's push subscription"""
    try:
        data = request.get_json()

        # Check if subscription already exists
        existing = PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=data['endpoint']
        ).first()

        if existing:
            # Update existing subscription
            existing.p256dh = data['keys']['p256dh']
            existing.auth = data['keys']['auth']
            existing.is_active = True
            existing.last_used = get_indian_time()
        else:
            # Create new subscription
            subscription = PushSubscription(
                user_id=current_user.id,
                endpoint=data['endpoint'],
                p256dh=data['keys']['p256dh'],
                auth=data['keys']['auth']
            )
            db.session.add(subscription)

        db.session.commit()
        logger.info(f"Push subscription saved for user {current_user.id}")

        return jsonify({'success': True, 'message': 'Subscription saved successfully'})

    except Exception as e:
        logger.error(f"Error saving push subscription: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/push-subscription', methods=['DELETE'])
@login_required
def remove_push_subscription():
    """Remove user's push subscription"""
    try:
        data = request.get_json()

        subscription = PushSubscription.query.filter_by(
            user_id=current_user.id,
            endpoint=data['endpoint']
        ).first()

        if subscription:
            subscription.is_active = False
            db.session.commit()
            logger.info(f"Push subscription removed for user {current_user.id}")

        return jsonify({'success': True, 'message': 'Subscription removed successfully'})

    except Exception as e:
        logger.error(f"Error removing push subscription: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500




# Kitchen Manager routes
@app.route('/kitchen/dashboard')
@login_required
def kitchen_dashboard():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Initialize today's inventory if not exists
    today = date.today()
    initialize_daily_inventory_for_kitchen(current_user.kitchen_id, today)

    # Get pending refill requests
    pending_refills = RefillRequest.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        status='requested'
    ).order_by(RefillRequest.request_time).all()

    # Get low stock items
    low_stock = InventoryTracker.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        date=today
    ).filter(InventoryTracker.status.in_(['Low', 'Critical'])).all()

    # Get today's completed refills
    completed_refills = RefillRequest.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        status='taken_by_cart'
    ).filter(db.func.date(RefillRequest.pickup_time) == today).count()

    # Get real staff status
    cart_staff = User.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        role='cart_staff',
        is_active=True
    ).count()

    delivery_staff = User.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        role='delivery_staff',
        is_active=True
    ).count()

    # Get last 7 days sales data
    seven_days_ago = today - timedelta(days=6)  # 6 days ago + today = 7 days
    daily_sales = db.session.query(
        DailySales.date,
        db.func.sum(DailySales.total_revenue).label('revenue')
    ).filter(
        DailySales.kitchen_id == current_user.kitchen_id,
        DailySales.date >= seven_days_ago,
        DailySales.date <= today
    ).group_by(DailySales.date).order_by(DailySales.date).all()

    # Format sales data for chart
    sales_dates = []
    sales_values = []
    current_date = seven_days_ago
    while current_date <= today:
        sales_dates.append(current_date.strftime('%Y-%m-%d'))
        # Find sales for this date
        sale = next((s for s in daily_sales if s.date == current_date), None)
        sales_values.append(float(sale.revenue) if sale else 0)
        current_date += timedelta(days=1)

    return render_template('kitchen/dashboard.html',
                         pending_refills=pending_refills,
                         low_stock=low_stock,
                         completed_refills=completed_refills,
                         cart_staff=cart_staff,
                         delivery_staff=delivery_staff,
                         sales_dates=sales_dates,
                         sales_values=sales_values)

@app.route('/kitchen/analysis')
@login_required
def kitchen_analysis():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get date range from request, default to last 30 days
    end_date = request.args.get('end_date', date.today().strftime('%Y-%m-%d'))
    start_date = request.args.get('start_date', (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=29)).strftime('%Y-%m-%d'))

    # Convert string dates to date objects
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()

    # Get daily sales data
    sales_data = DailySales.query.filter(
        DailySales.kitchen_id == current_user.kitchen_id,
        DailySales.date >= start_date_obj,
        DailySales.date <= end_date_obj
    ).order_by(DailySales.date).all()

    # Prepare data for charts
    revenue_dates = []
    revenue_values = []
    sop_quantities = {}
    payment_modes = {'Cash': 0, 'UPI': 0}

    # Create date range for complete data
    current_date = start_date_obj
    while current_date <= end_date_obj:
        date_str = current_date.strftime('%Y-%m-%d')
        revenue_dates.append(date_str)
        revenue_values.append(0)
        current_date += timedelta(days=1)

    for sale in sales_data:
        # Revenue data
        date_str = sale.date.strftime('%Y-%m-%d')
        if date_str in revenue_dates:
            idx = revenue_dates.index(date_str)
            revenue_values[idx] += float(sale.total_revenue)

        # SOP distribution data
        sop_name = sale.sop.recipe_name if sale.sop else 'Unknown'
        sop_quantities[sop_name] = sop_quantities.get(sop_name, 0) + float(sale.kg_sold)

        # Payment mode split
        payment_modes['Cash'] += float(sale.cash_collected)
        payment_modes['UPI'] += float(sale.upi_collected)

    # Get production data (from refill requests that are delivered)
    production_data = RefillRequest.query.filter(
        RefillRequest.kitchen_id == current_user.kitchen_id,
        db.func.date(RefillRequest.delivered_time) >= start_date_obj,
        db.func.date(RefillRequest.delivered_time) <= end_date_obj,
        RefillRequest.status == 'delivered'
    ).order_by(RefillRequest.delivered_time).all()

    production_dates = []
    production_quantities = []

    # Create date range for production
    current_date = start_date_obj
    while current_date <= end_date_obj:
        date_str = current_date.strftime('%Y-%m-%d')
        production_dates.append(date_str)
        production_quantities.append(0)
        current_date += timedelta(days=1)

    for prod in production_data:
        if prod.delivered_time:
            date_str = prod.delivered_time.date().strftime('%Y-%m-%d')
            if date_str in production_dates:
                idx = production_dates.index(date_str)
                production_quantities[idx] += float(prod.kg_request)

    # Get inventory usage data
    inventory_data = InventoryTracker.query.filter(
        InventoryTracker.kitchen_id == current_user.kitchen_id,
        InventoryTracker.date >= start_date_obj,
        InventoryTracker.date <= end_date_obj
    ).join(Ingredient).all()

    # Group inventory by unit
    inventory_by_unit = {}

    for inv in inventory_data:
        unit = inv.ingredient.unit
        if unit not in inventory_by_unit:
            inventory_by_unit[unit] = {
                'labels': [],
                'datasets': [{
                    'label': 'Usage',
                    'data': []
                }]
            }

        if inv.ingredient.name not in inventory_by_unit[unit]['labels']:
            inventory_by_unit[unit]['labels'].append(inv.ingredient.name)
            inventory_by_unit[unit]['datasets'][0]['data'].append(float(inv.used_qty))
        else:
            idx = inventory_by_unit[unit]['labels'].index(inv.ingredient.name)
            inventory_by_unit[unit]['datasets'][0]['data'][idx] += float(inv.used_qty)

    return render_template('kitchen/analysis.html',
                         start_date=start_date,
                         end_date=end_date,
                         revenue_dates=revenue_dates,
                         revenue_values=revenue_values,
                         sop_names=list(sop_quantities.keys()),
                         sop_quantities=list(sop_quantities.values()),
                         production_dates=production_dates,
                         production_quantities=production_quantities,
                         payment_modes=list(payment_modes.keys()),
                         payment_amounts=list(payment_modes.values()),
                         inventory_by_unit=inventory_by_unit)

@app.route('/kitchen/add-staff', methods=['GET', 'POST'])
@login_required
def kitchen_add_staff():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    form = UserForm()
    # Kitchen Manager can only add staff to their own kitchen
    form.city.choices = [(current_user.kitchen.city, current_user.kitchen.city)]
    form.kitchen_id.choices = [(current_user.kitchen_id, current_user.kitchen.kitchen_id)]
    # Kitchen Manager can only add Cart Staff and Delivery Staff
    form.role.choices = [
        ('cart_staff', 'Cart Staff'),
        ('delivery_staff', 'Delivery Staff')
    ]

    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already exists', 'error')
            return render_template('kitchen/add_staff.html', form=form)

        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Email already exists', 'error')
            return render_template('kitchen/add_staff.html', form=form)

        user = User(
            username=form.username.data,
            name=form.name.data,
            role=form.role.data,
            kitchen_id=form.kitchen_id.data,
            location=form.location.data,
            mobile_no=form.mobile_no.data,
            email=form.email.data,
            address=form.address.data,
            salary=form.salary.data,
            incentive=form.incentive.data
        )
        user.set_password(form.password.data)

        try:
            db.session.add(user)
            db.session.flush()  # Get the user ID

            # If cart staff, create cart entry
            if form.role.data == 'cart_staff':
                # Generate thela_id: CART + user_id (3 digits)
                thela_id = f"CART{str(user.id).zfill(3)}"

                cart = Cart(
                    thela_id=thela_id,
                    cart_staff_id=user.id,
                    kitchen_id=user.kitchen_id,
                    location=form.location.data
                )
                db.session.add(cart)

            db.session.commit()
            flash(f'{form.role.data.replace("_", " ").title()} added successfully', 'success')
            return redirect(url_for('kitchen_add_staff'))
        except Exception as e:
            db.session.rollback()
            flash('Error adding staff member', 'error')
            return render_template('kitchen/add_staff.html', form=form)

    return render_template('kitchen/add_staff.html', form=form)

@app.route('/kitchen/refill_requests')
@login_required
def kitchen_refill_requests():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Show 10 refills per page

    # Get all refill requests for this kitchen with pagination
    refill_requests_query = RefillRequest.query.filter_by(
        kitchen_id=current_user.kitchen_id
    ).order_by(RefillRequest.request_time.desc())

    refill_requests = refill_requests_query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )

    # Get today's refill requests
    today = date.today()
    today_refills = RefillRequest.query.filter_by(
        kitchen_id=current_user.kitchen_id
    ).filter(
        db.func.date(RefillRequest.request_time) == today
    ).order_by(RefillRequest.request_time.desc()).all()

    # Get counts for status cards
    status_counts = {
        'pending': RefillRequest.query.filter_by(
            kitchen_id=current_user.kitchen_id,
            status='requested'
        ).count(),
        'in_progress': RefillRequest.query.filter_by(
            kitchen_id=current_user.kitchen_id,
            status='taken_by_chef'
        ).count(),
        'prepared': RefillRequest.query.filter_by(
            kitchen_id=current_user.kitchen_id,
            status='prepared'
        ).count(),
        'completed': RefillRequest.query.filter_by(
            kitchen_id=current_user.kitchen_id,
            status='taken_by_cart'
        ).count()
    }

    return render_template('kitchen/refill_requests.html', 
                         refill_requests=refill_requests,
                         today_refills=today_refills,
                         status_counts=status_counts)

@app.route('/kitchen/accept_refill/<int:refill_id>')
@login_required
def kitchen_accept_refill(refill_id):
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    refill = RefillRequest.query.get_or_404(refill_id)

    if refill.kitchen_id != current_user.kitchen_id:
        flash('Access denied', 'error')
        return redirect(url_for('kitchen_refill_requests'))

    if refill.status == 'requested':
        refill.status = 'taken_by_chef'
        refill.taken_by_chef_time = get_indian_time()
        db.session.commit()

        # Send notification to cart staff
        send_refill_notification(refill, 'accepted')

        flash('Refill request accepted', 'success')

    return redirect(url_for('kitchen_refill_requests'))

@app.route('/kitchen/mark_prepared/<int:refill_id>', methods=['POST'])
@login_required
def kitchen_mark_prepared(refill_id):
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    refill = RefillRequest.query.get_or_404(refill_id)

    if refill.kitchen_id != current_user.kitchen_id:
        flash('Access denied', 'error')
        return redirect(url_for('kitchen_refill_requests'))

    quality_status = request.form.get('quality_status', 'verified')
    quality_notes = request.form.get('quality_notes', '')

    if refill.status == 'taken_by_chef':
        refill.status = 'prepared'
        refill.prepared_time = get_indian_time()
        refill.quality_status = quality_status
        refill.quality_notes = quality_notes

        # Update inventory based on SOP
        update_inventory_after_cooking(refill.sop_id, refill.kg_request, refill.kitchen_id)

        db.session.commit()

        # Send notification to cart staff and delivery team
        send_refill_notification(refill, 'prepared')

        flash('Refill marked as prepared', 'success')

    return redirect(url_for('kitchen_refill_requests'))

@app.route('/kitchen/inventory')
@login_required
def kitchen_inventory():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    today = date.today()

    # Auto-initialize today's inventory if not exists
    ingredients = Ingredient.query.all()
    for ingredient in ingredients:
        existing = InventoryTracker.query.filter_by(
            date=today,
            kitchen_id=current_user.kitchen_id,
            ingredient_id=ingredient.id
        ).first()

        if not existing:
            # Get yesterday's closing stock
            yesterday = date.fromordinal(today.toordinal() - 1)
            yesterday_tracker = InventoryTracker.query.filter_by(
                date=yesterday,
                kitchen_id=current_user.kitchen_id,
                ingredient_id=ingredient.id
            ).first()

            opening_stock = yesterday_tracker.closing_stock if yesterday_tracker else 0.0

            # Create today's tracker
            tracker = InventoryTracker(
                date=today,
                kitchen_id=current_user.kitchen_id,
                ingredient_id=ingredient.id,
                opening_stock=opening_stock,
                purchase_qty=0.0,
                used_qty=0.0,
                loss_qty=0.0,
                closing_stock=opening_stock,
                min_threshold=ingredient.minimum_stock,
                status='Critical' if opening_stock <= 0 else 'Low' if opening_stock <= ingredient.minimum_stock else 'OK'
            )
            db.session.add(tracker)

    db.session.commit()

    # Now get all inventory items
    inventory_items = InventoryTracker.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        date=today
    ).join(Ingredient).all()

    return render_template('kitchen/inventory.html', inventory_items=inventory_items)

@app.route('/kitchen/supplier_purchase', methods=['GET', 'POST'])
@login_required
def kitchen_supplier_purchase():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    form = SupplierPurchaseForm()
    form.ingredient_id.choices = [(i.id, f"{i.name} ({i.unit})") for i in Ingredient.query.all()]

    if form.validate_on_submit():
        total_amount = form.quantity.data * form.rate_per_unit.data
        balance_amount = total_amount - form.payment_made.data

        purchase = SupplierPurchase(
            kitchen_id=current_user.kitchen_id,
            ingredient_id=form.ingredient_id.data,
            vendor_name=form.vendor_name.data,
            quantity=form.quantity.data,
            rate_per_unit=form.rate_per_unit.data,
            total_amount=total_amount,
            payment_made=form.payment_made.data,
            payment_mode=form.payment_mode.data,
            balance_amount=balance_amount
        )

        db.session.add(purchase)

        # Automatically create/update inventory tracker
        today = date.today()
        ingredient = Ingredient.query.get(form.ingredient_id.data)

        # Get or create today's tracker
        tracker = InventoryTracker.query.filter_by(
            date=today,
            kitchen_id=current_user.kitchen_id,
            ingredient_id=form.ingredient_id.data
        ).first()

        if not tracker:
            # Auto-create tracker - get yesterday's closing stock
            yesterday = date.fromordinal(today.toordinal() - 1)
            yesterday_tracker = InventoryTracker.query.filter_by(
                date=yesterday,
                kitchen_id=current_user.kitchen_id,
                ingredient_id=form.ingredient_id.data
            ).first()

            opening_stock = yesterday_tracker.closing_stock if yesterday_tracker else 0.0

            tracker = InventoryTracker(
                date=today,
                kitchen_id=current_user.kitchen_id,
                ingredient_id=form.ingredient_id.data,
                opening_stock=opening_stock,
                purchase_qty=0.0,
                used_qty=0.0,
                loss_qty=0.0,
                closing_stock=opening_stock,
                min_threshold=ingredient.minimum_stock,
                status='Critical' if opening_stock <= 0 else 'Low' if opening_stock <= ingredient.minimum_stock else 'OK'
            )
            db.session.add(tracker)

        # Add purchase quantity
        tracker.purchase_qty += form.quantity.data
        tracker.closing_stock = tracker.opening_stock + tracker.purchase_qty - tracker.used_qty - tracker.loss_qty

        # Update status based on current stock
        if tracker.closing_stock <= 0:
            tracker.status = 'Critical'
        elif tracker.closing_stock <= tracker.min_threshold:
            tracker.status = 'Low'
        else:
            tracker.status = 'OK'

        db.session.commit()
        flash('Purchase recorded successfully', 'success')
        return redirect(url_for('kitchen_supplier_purchase'))

    # Get recent purchases
    recent_purchases = SupplierPurchase.query.filter_by(
        kitchen_id=current_user.kitchen_id
    ).order_by(SupplierPurchase.created_at.desc()).limit(10).all()

    return render_template('kitchen/supplier_purchase.html', form=form, recent_purchases=recent_purchases)

@app.route('/kitchen/sales')
@login_required
def kitchen_sales():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get date filter from request
    selected_date = request.args.get('date')
    if selected_date:
        try:
            filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            filter_date = date.today()
    else:
        filter_date = date.today()

    # Get sales data for the selected date
    sales_data = DailySales.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        date=filter_date
    ).join(User).join(SOP).all()

    # Calculate totals
    total_revenue = sum(sale.total_revenue for sale in sales_data)
    total_kg_sold = sum(sale.kg_sold for sale in sales_data)
    total_incentive = sum(sale.total_incentive for sale in sales_data)

    # Get active cart staff count
    active_carts = User.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        role='cart_staff',
        is_active=True
    ).count()

    # Get weekly summary if viewing today
    weekly_summary = None
    is_today = filter_date == date.today()
    if is_today:
        # Get last 7 days summary by cart staff
        week_ago = filter_date - timedelta(days=7)
        weekly_data = db.session.query(
            User.name,
            db.func.sum(DailySales.total_revenue).label('total_revenue'),
            db.func.sum(DailySales.kg_sold).label('total_kg_sold'),
            db.func.sum(DailySales.total_incentive).label('total_incentive'),
            db.func.avg(DailySales.total_revenue).label('avg_daily_sales')
        ).join(DailySales).filter(
            DailySales.kitchen_id == current_user.kitchen_id,
            DailySales.date >= week_ago,
            DailySales.date <= filter_date
        ).group_by(User.id, User.name).all()

        weekly_summary = [{
            'name': item.name,
            'total_revenue': int(item.total_revenue or 0),
            'total_kg_sold': int(item.total_kg_sold or 0),
            'total_incentive': int(item.total_incentive or 0),
            'avg_daily_sales': int(item.avg_daily_sales or 0)
        } for item in weekly_data]

    return render_template('kitchen/sales.html',
                         sales_data=sales_data,
                         selected_date=selected_date,
                         selected_date_display=filter_date.strftime('%d %B %Y'),
                         today=date.today().strftime('%Y-%m-%d'),
                         total_revenue=int(total_revenue),
                         total_kg_sold=int(total_kg_sold),
                         total_incentive=int(total_incentive),
                         active_carts=active_carts,
                         weekly_summary=weekly_summary,
                         is_today=is_today)

@app.route('/kitchen/feedback')
@login_required
def kitchen_feedback():
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get feedback for this kitchen
    feedbacks = CustomerFeedback.query.filter_by(
        kitchen_id=current_user.kitchen_id
    ).order_by(CustomerFeedback.created_at.desc()).all()

    # Generate QR code for feedback form
    feedback_url = url_for('customer_feedback', kitchen_id=current_user.kitchen_id, _external=True)
    qr_code = generate_qr_code(feedback_url)

    return render_template('kitchen/feedback.html', feedbacks=feedbacks, qr_code=qr_code)

# Cart Staff routes
@app.route('/cart/dashboard')
@login_required
def cart_dashboard():
    if current_user.role != 'cart_staff':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get all current refill requests
    current_refills = RefillRequest.query.filter_by(
        cart_staff_id=current_user.id
    ).filter(RefillRequest.status.in_(['requested', 'taken_by_chef', 'prepared', 'picked_up'])).all()

    # Get today's sales entry status
    today = date.today()
    sales_entered = DailySales.query.filter_by(
        cart_staff_id=current_user.id,
        date=today
    ).first()

    # Get incentive summary
    this_month = date.today().replace(day=1)
    monthly_incentive = db.session.query(db.func.sum(DailySales.total_incentive)).filter(
        DailySales.cart_staff_id == current_user.id,
        DailySales.date >= this_month
    ).scalar() or 0

    # Get sales entries for today
    sales_entries = DailySales.query.filter_by(
        cart_staff_id=current_user.id,
        date=today
    ).join(SOP).all()

    # Get delivered refills for today
    delivered_refills = RefillRequest.query.filter_by(
        cart_staff_id=current_user.id,
        status='delivered'
    ).filter(db.func.date(RefillRequest.delivered_time) == today).all()

    # Get unique SOPs from delivered refills
    delivered_sops = set(refill.sop_id for refill in delivered_refills)

    # Get SOPs with sales entries
    sales_sops = set(sale.sop_id for sale in sales_entries)

    # Check if all delivered recipes have sales entries
    sales_completed = len(delivered_sops) > 0 and delivered_sops == sales_sops

    # Calculate overall sales summary (aggregate all entries)
    total_revenue = sum(sale.total_revenue for sale in sales_entries)
    total_kg_sold = sum(sale.kg_sold for sale in sales_entries)
    total_incentive = sum(sale.total_incentive for sale in sales_entries)
    total_kg_unsold = sum(sale.kg_unsold for sale in sales_entries)
    total_kg_taken = sum(sale.kg_taken for sale in sales_entries)

    return render_template('cart/dashboard.html',
                         current_refills=current_refills,
                         sales_entered=sales_entered,
                         monthly_incentive=monthly_incentive,
                         sales_entries=sales_entries,
                         sales_completed=sales_completed,
                         total_revenue=total_revenue,
                         total_kg_sold=total_kg_sold,
                         total_incentive=total_incentive,
                         total_kg_unsold=total_kg_unsold,
                         total_kg_taken=total_kg_taken)

@app.route('/cart/refill_request', methods=['GET', 'POST'])
@login_required
def cart_refill_request():
    if current_user.role != 'cart_staff':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    form = RefillRequestForm()
    form.sop_id.choices = [(s.id, s.recipe_name) for s in SOP.query.filter_by(is_active=True).all()]

    if form.validate_on_submit():
        today = date.today()

        # Check if sales already submitted for today
        sales_today = DailySales.query.filter_by(
            cart_staff_id=current_user.id,
            date=today
        ).first()

        if sales_today:
            flash('Cannot request refills after submitting sales for today', 'error')
            return render_template('cart/refill_request.html', form=form)

        # Check if there's already a pending request for this recipe
        pending_request = RefillRequest.query.filter_by(
            cart_staff_id=current_user.id,
            sop_id=form.sop_id.data
        ).filter(RefillRequest.status.in_(['requested', 'taken_by_chef', 'prepared'])).first()

        if pending_request:
            flash(f'You already have a pending refill request for {pending_request.sop.recipe_name}', 'error')
            return render_template('cart/refill_request.html', form=form)

        # Create new refill request
        refill_request = RefillRequest(
            cart_staff_id=current_user.id,
            kitchen_id=current_user.kitchen_id,
            sop_id=form.sop_id.data,
            kg_request=form.kg_request.data
        )

        db.session.add(refill_request)
        db.session.commit()

        # Send notification to kitchen immediately
        logger.info(f"Sending new refill notification for request {refill_request.id}")
        send_refill_notification(refill_request, 'new_request')

        # Also send direct notification to kitchen room
        socketio.emit('notification', {
            'type': 'new_refill',
            'message': f"New refill request: {refill_request.sop.recipe_name} ({refill_request.kg_request}kg) from {current_user.name}",
            'data': {
                'refill_id': refill_request.id,
                'cart_staff': current_user.name,
                'recipe': refill_request.sop.recipe_name,
                'quantity': refill_request.kg_request
            },
            'timestamp': get_indian_time().isoformat()
        }, room=f"kitchen_{current_user.kitchen_id}")

        flash('Refill request submitted successfully', 'success')

        # Ask if user wants to request another recipe
        if 'add_another' in request.form:
            return redirect(url_for('cart_refill_request'))
        return redirect(url_for('cart_dashboard'))

    # Get all pending refill requests for today
    today = date.today()
    pending_refills = RefillRequest.query.filter(
        RefillRequest.cart_staff_id == current_user.id,
        db.func.date(RefillRequest.request_time) == today
    ).filter(RefillRequest.status.in_(['requested', 'taken_by_chef', 'prepared'])).all()

    return render_template('cart/refill_request.html', form=form, pending_refills=pending_refills)

@app.route('/cart/daily_sales', methods=['GET', 'POST'])
@login_required
def cart_daily_sales():
    if current_user.role != 'cart_staff':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    form = DailySalesForm()
    today = date.today()

    # Get recipes from delivered refill requests for today
    fulfilled_refills = RefillRequest.query.filter(
        RefillRequest.cart_staff_id == current_user.id,
        RefillRequest.status == 'delivered',
        db.func.date(RefillRequest.pickup_time) == today  # Use pickup_time instead of fulfilled_time
    ).all()

    # Only allow recipes that have been delivered today
    available_sops = [(refill.sop_id, refill.sop.recipe_name) for refill in fulfilled_refills]
    if not available_sops:
        flash('No refills received today. Please request and receive refills before submitting sales.', 'warning')
        return redirect(url_for('cart_dashboard'))

    form.sop_id.choices = available_sops

    if form.validate_on_submit():
        # Check if sales already entered for this recipe today
        existing_sales = DailySales.query.filter_by(
            cart_staff_id=current_user.id,
            sop_id=form.sop_id.data,
            date=today
        ).first()

        if existing_sales:
            flash('Sales already entered for this recipe today', 'error')
            return render_template('cart/daily_sales.html', form=form)

        # Get the refill request for this recipe
        refill = next((r for r in fulfilled_refills if r.sop_id == form.sop_id.data), None)
        if not refill:
            flash('No valid refill found for this recipe today', 'error')
            return render_template('cart/daily_sales.html', form=form)

        # Handle None values and convert to 0
        kg_unsold = float(form.kg_unsold.data) if form.kg_unsold.data is not None else 0.0
        cash_collected = float(form.cash_collected.data) if form.cash_collected.data is not None else 0.0

        # Validate that unsold quantity doesn't exceed refilled quantity
        if kg_unsold > refill.kg_request:
            flash(f'Unsold quantity cannot be more than refilled quantity ({refill.kg_request} kg)', 'error')
            return render_template('cart/daily_sales.html', form=form)

        sop = SOP.query.get(form.sop_id.data)
        totals = calculate_daily_sales_totals({
            'kg_unsold': kg_unsold,
            'cash_collected': cash_collected
        }, current_user, sop)

        daily_sales = DailySales(
            cart_staff_id=current_user.id,
            kitchen_id=current_user.kitchen_id,
            sop_id=form.sop_id.data,
            date=today,
            kg_taken=refill.kg_request,
            kg_unsold=kg_unsold,
            kg_sold=totals['kg_sold'],
            cash_collected=cash_collected,
            upi_collected=totals['upi_collected'],
            total_revenue=totals['total_revenue'],
            recipe_rate=totals['recipe_rate'],
            incentive_per_kg=totals['incentive_per_kg'],
            total_incentive=totals['total_incentive']
        )

        db.session.add(daily_sales)
        db.session.commit()

        flash('Daily sales recorded successfully', 'success')
        return redirect(url_for('cart_dashboard'))

    return render_template('cart/daily_sales.html', form=form)

@app.route('/cart/mark_received/<int:refill_id>')
@login_required
def cart_mark_received(refill_id):
    if current_user.role != 'cart_staff':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    refill = RefillRequest.query.get_or_404(refill_id)

    if refill.cart_staff_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('cart_dashboard'))

    if refill.status == 'picked_up':
        refill.status = 'delivered'
        refill.delivered_time = get_indian_time()
        db.session.commit()
        flash('Refill marked as received', 'success')

    return redirect(url_for('cart_dashboard'))

@app.route('/api/refill_data/<int:sop_id>')
@login_required
def api_refill_data(sop_id):
    if current_user.role != 'cart_staff':
        return jsonify({'error': 'Access denied'}), 403

    today = date.today()
    fulfilled_refill = RefillRequest.query.filter(
        RefillRequest.cart_staff_id == current_user.id,
        RefillRequest.sop_id == sop_id,
        RefillRequest.status == 'delivered',
        db.func.date(RefillRequest.pickup_time) == today
    ).first()

    if fulfilled_refill:
        return jsonify({'kg_taken': fulfilled_refill.kg_request})
    else:
        return jsonify({'kg_taken': 0})

@app.route('/api/recipe_rate/<int:sop_id>')
@login_required
def api_recipe_rate(sop_id):
    if current_user.role != 'cart_staff':
        return jsonify({'error': 'Access denied'}), 403

    sop = SOP.query.get(sop_id)
    if sop:
        return jsonify({'recipe_rate': sop.recipe_rate})
    else:
        return jsonify({'recipe_rate': 0})

@app.route('/api/recipe_details/<int:sop_id>')
@login_required
def api_recipe_details(sop_id):
    """API endpoint to get recipe details"""
    try:
        sop = SOP.query.get(sop_id)
        if not sop:
            return jsonify({'error': 'Recipe not found'}), 404

        # Get SOP ingredients
        sop_ingredients = SOPIngredient.query.filter_by(sop_id=sop_id).join(Ingredient).all()

        ingredients = []
        for sop_ing in sop_ingredients:
            ingredients.append({
                'name': sop_ing.ingredient.name,
                'quantity': sop_ing.quantity,
                'unit': sop_ing.ingredient.unit,
                'note': sop_ing.note or ''
            })

        recipe_data = {
            'id': sop.id,
            'recipe_name': sop.recipe_name,
            'base_quantity': sop.base_quantity,
            'recipe_rate': sop.recipe_rate,
            'description': sop.description or '',
            'ingredients': ingredients
        }

        return jsonify(recipe_data)

    except Exception as e:
        logger.error(f"Error in recipe details API: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/api/kitchen-carts/<int:kitchen_id>')
def api_kitchen_carts(kitchen_id):
    """API endpoint to get all carts for a specific kitchen"""
    try:
        kitchen = Kitchen.query.get(kitchen_id)
        if not kitchen:
            return jsonify({'error': 'Kitchen not found'}), 404

        # Get cart staff users for this kitchen
        cart_staff = User.query.filter_by(
            kitchen_id=kitchen_id,
            role='cart_staff',
            is_active=True
        ).all()
        
        carts_data = []
        for staff in cart_staff:
            # Generate thela_id based on user ID
            thela_id = f"CART{str(staff.id).zfill(3)}"
            carts_data.append({
                'thela_id': thela_id,
                'location': staff.location or 'Unknown Location',
                'cart_staff_name': staff.name
            })

        return jsonify(carts_data)

    except Exception as e:
        logger.error(f"Error in kitchen carts API: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

# Delivery Staff routes
@app.route('/delivery/dashboard')
@login_required
def delivery_dashboard():
    if current_user.role != 'delivery_staff':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Show 10 deliveries per page

    # Get available deliveries (prepared food ready for pickup)
    available_deliveries = RefillRequest.query.filter_by(
        kitchen_id=current_user.kitchen_id,
        status='prepared'
    ).filter(RefillRequest.delivery_staff_id.is_(None)).order_by(RefillRequest.prepared_time).all()

    # Get today's deliveries (all deliveries completed today)
    today = date.today()
    my_deliveries = RefillRequest.query.filter_by(
        delivery_staff_id=current_user.id,
        status='delivered'
    ).filter(db.func.date(RefillRequest.delivered_time) == today).all()

    # Calculate overall statistics
    total_deliveries = RefillRequest.query.filter_by(
        delivery_staff_id=current_user.id,
        status='delivered'
    ).count()

    # Calculate total kg delivered (overall)
    total_kg_delivered = db.session.query(db.func.sum(RefillRequest.kg_request)).filter_by(
        delivery_staff_id=current_user.id,
        status='delivered'
    ).scalar() or 0.0

    # Calculate average preparation time (in minutes)
    prep_time_data = db.session.query(
        db.func.avg(
            db.func.extract('epoch', RefillRequest.pickup_time - RefillRequest.prepared_time) / 60
        )
    ).filter_by(
        delivery_staff_id=current_user.id,
        status='delivered'
    ).filter(
        RefillRequest.pickup_time.isnot(None),
        RefillRequest.prepared_time.isnot(None)
    ).scalar()

    avg_prep_time = round(prep_time_data) if prep_time_data else 0

    # Calculate average delivery time (in minutes)
    delivery_time_data = db.session.query(
        db.func.avg(
            db.func.extract('epoch', RefillRequest.delivered_time - RefillRequest.pickup_time) / 60
        )
    ).filter_by(
        delivery_staff_id=current_user.id,
        status='delivered'
    ).filter(
        RefillRequest.delivered_time.isnot(None),
        RefillRequest.pickup_time.isnot(None)
    ).scalar()

    avg_delivery_time = round(delivery_time_data) if delivery_time_data else 0

    # Get all completed deliveries with pagination
    completed_deliveries_query = RefillRequest.query.filter_by(
        delivery_staff_id=current_user.id,
        status='delivered'
    ).order_by(RefillRequest.delivered_time.desc())

    completed_deliveries = completed_deliveries_query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )

    return render_template('delivery/dashboard.html',
                         available_deliveries=available_deliveries,
                         my_deliveries=my_deliveries,
                         total_deliveries=total_deliveries,
                         total_kg_delivered=total_kg_delivered,
                         avg_prep_time=avg_prep_time,
                         avg_delivery_time=avg_delivery_time,
                         completed_deliveries=completed_deliveries)

@app.route('/delivery/pickup/<int:refill_id>')
@login_required
def delivery_pickup(refill_id):
    if current_user.role != 'delivery_staff':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    refill = RefillRequest.query.get_or_404(refill_id)

    if refill.kitchen_id != current_user.kitchen_id:
        flash('Access denied', 'error')
        return redirect(url_for('delivery_dashboard'))

    if refill.status == 'prepared' and not refill.delivery_staff_id:
        refill.delivery_staff_id = current_user.id
        refill.status = 'picked_up'
        refill.pickup_time = get_indian_time()
        db.session.commit()

        # Send notification to cart staff
        send_refill_notification(refill, 'picked_up')

        flash('Delivery picked up successfully', 'success')

    return redirect(url_for('delivery_dashboard'))

@app.route('/delivery/mark_delivered/<int:refill_id>', methods=['POST'])
@login_required
def delivery_mark_delivered(refill_id):
    if current_user.role != 'delivery_staff':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    refill = RefillRequest.query.get_or_404(refill_id)

    if refill.delivery_staff_id != current_user.id:
        flash('Access denied', 'error')
        return redirect(url_for('delivery_dashboard'))

    if refill.status == 'picked_up':
        refill.status = 'delivered'
        refill.delivered_time = get_indian_time()
        db.session.commit()

        # Send notification to cart staff
        send_refill_notification(refill, 'delivered')

        return jsonify({'success': True, 'message': 'Delivery marked as completed'})
    else:
        return jsonify({'success': False, 'message': 'Invalid delivery status'}), 400

# Settings and other routes
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    profile_form = ProfileForm(obj=current_user)
    password_form = ChangePasswordForm()

    if request.method == 'POST':
        if 'profile_submit' in request.form and profile_form.validate():
            current_user.name = profile_form.name.data
            current_user.mobile_no = profile_form.mobile_no.data
            current_user.email = profile_form.email.data
            current_user.address = profile_form.address.data

            db.session.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('settings'))

        elif 'password_submit' in request.form and password_form.validate():
            if current_user.check_password(password_form.old_password.data):
                current_user.set_password(password_form.new_password.data)
                db.session.commit()
                flash('Password changed successfully', 'success')
                return redirect(url_for('settings'))
            else:
                flash('Old password is incorrect', 'error')

    return render_template('settings.html', profile_form=profile_form, password_form=password_form)

@app.route('/kitchen/inventory_adjustment', methods=['POST'])
@login_required
def kitchen_inventory_adjustment():
    if current_user.role != 'kitchen_manager':
        return jsonify({'error': 'Access denied'}), 403

    try:
        ingredient_id = request.form.get('ingredient_id')
        quantity = float(request.form.get('quantity', 0))
        reason = request.form.get('reason')
        notes = request.form.get('notes', '')

        # Create inventory adjustment record
        adjustment = InventoryAdjustment(
            kitchen_id=current_user.kitchen_id,
            ingredient_id=ingredient_id,
            quantity=quantity,
            reason=reason,
            notes=notes,
            adjusted_by=current_user.id
        )
        db.session.add(adjustment)

        # Auto-create/update inventory tracker
        today = date.today()
        tracker = auto_create_inventory_tracker(current_user.kitchen_id, ingredient_id, today)

        if tracker:
            tracker.loss_qty += quantity
            tracker.closing_stock = tracker.opening_stock + tracker.purchase_qty - tracker.used_qty - tracker.loss_qty

            # Prevent negative stock
            if tracker.closing_stock < 0:
                tracker.closing_stock = 0

            # Update status
            if tracker.closing_stock <= 0:
                tracker.status = 'Critical'
            elif tracker.closing_stock <= tracker.min_threshold:
                tracker.status = 'Low'
            else:
                tracker.status = 'OK'

        db.session.commit()
        flash('Inventory adjustment recorded successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error recording adjustment: {str(e)}', 'error')

    return redirect(url_for('kitchen_inventory'))

@app.route('/feedback/<int:kitchen_id>', methods=['GET', 'POST'])
def customer_feedback(kitchen_id):
    kitchen = Kitchen.query.get_or_404(kitchen_id)
    form = CustomerFeedbackForm(kitchen_id=kitchen_id)

    if request.method == 'POST' and form.validate_on_submit():
        feedback = CustomerFeedback(
            date=date.today(),
            city=kitchen.city,  # Use kitchen's city instead of form data
            thela_id=form.thela_id.data,
            feedback_type=form.feedback_type.data,
            comments=form.comments.data,
            kitchen_id=kitchen_id
        )
        db.session.add(feedback)
        db.session.commit()
        flash('Thank you for your feedback!', 'success')
        return redirect(url_for('customer_feedback', kitchen_id=kitchen_id))

    return render_template('feedback_form.html', form=form, kitchen=kitchen)

@app.route('/kitchen/feedback/<int:feedback_id>/action', methods=['POST'])
@login_required
def kitchen_feedback_action(feedback_id):
    if current_user.role != 'kitchen_manager':
        flash('Access denied', 'error')
        return redirect(url_for('dashboard'))

    feedback = CustomerFeedback.query.get_or_404(feedback_id)

    if feedback.kitchen_id != current_user.kitchen_id:
        flash('Access denied', 'error')
        return redirect(url_for('kitchen_feedback'))

    action_taken = request.form.get('action_taken')
    if action_taken:
        feedback.action_taken = action_taken
        db.session.commit()
        flash('Action recorded successfully', 'success')

    return redirect(url_for('kitchen_feedback'))

# Initialize demo data on first run
@app.before_request
def initialize_data():
    if not hasattr(app, 'initialized'):
        create_demo_data()
        app.initialized = True

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# This code automatically creates a Cart entry when a cart staff user is added via the admin interface.