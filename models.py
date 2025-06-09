from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import pytz

def get_indian_time():
    """Get current time in IST timezone"""
    indian_tz = pytz.timezone('Asia/Kolkata')
    return datetime.now(indian_tz).replace(tzinfo=None)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, kitchen_manager, cart_staff, delivery_staff
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=True)
    location = db.Column(db.String(100), nullable=False)
    mobile_no = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    address = db.Column(db.Text)
    salary = db.Column(db.Float, default=0.0)
    incentive = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=get_indian_time)
    is_active = db.Column(db.Boolean, default=True)

    kitchen = db.relationship('Kitchen', backref='users')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Kitchen(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kitchen_id = db.Column(db.String(50), unique=True, nullable=False)
    city = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(50), nullable=False)
    address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=get_indian_time)
    is_active = db.Column(db.Boolean, default=True)

class Ingredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    minimum_stock = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=get_indian_time)

class SOP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipe_name = db.Column(db.String(100), nullable=False)
    base_quantity = db.Column(db.Float, nullable=False)  # Base quantity in kg
    recipe_rate = db.Column(db.Float, nullable=False)  # Rate per kg
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_indian_time)
    is_active = db.Column(db.Boolean, default=True)

    # Relationship to SOPIngredient
    ingredients = db.relationship('SOPIngredient', backref='sop_recipe', lazy='dynamic')

class SOPIngredient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sop_id = db.Column(db.Integer, db.ForeignKey('sop.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Quantity for base_quantity
    note = db.Column(db.Text)

    # Relationships
    ingredient = db.relationship('Ingredient', backref='sop_usages')

class RefillRequest(db.Model):
    __tablename__ = 'refill_request'
    id = db.Column(db.Integer, primary_key=True)
    cart_staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=False)
    sop_id = db.Column(db.Integer, db.ForeignKey('sop.id'), nullable=False)
    kg_request = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='requested')
    request_time = db.Column(db.DateTime, nullable=False, default=get_indian_time)
    taken_by_chef_time = db.Column(db.DateTime)
    prepared_time = db.Column(db.DateTime)
    pickup_time = db.Column(db.DateTime)  # When delivery staff picks up
    delivered_time = db.Column(db.DateTime)
    delivery_staff_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    quality_status = db.Column(db.String(20))
    quality_notes = db.Column(db.Text)

    # Relationships
    cart_staff = db.relationship('User', foreign_keys=[cart_staff_id])
    kitchen = db.relationship('Kitchen')
    sop = db.relationship('SOP')
    delivery_staff = db.relationship('User', foreign_keys=[delivery_staff_id])

class DailySales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cart_staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=False)
    sop_id = db.Column(db.Integer, db.ForeignKey('sop.id'), nullable=False)
    date = db.Column(db.Date, default=lambda: get_indian_time().date())
    kg_taken = db.Column(db.Float, nullable=False)  # Sum of day's refill requests
    kg_unsold = db.Column(db.Float, nullable=False)
    kg_sold = db.Column(db.Float, nullable=False)  # Calculated: taken - unsold
    cash_collected = db.Column(db.Float, nullable=False)
    upi_collected = db.Column(db.Float, nullable=False)  # Calculated
    total_revenue = db.Column(db.Float, nullable=False)  # Calculated
    recipe_rate = db.Column(db.Float, nullable=False)  # From SOP
    incentive_per_kg = db.Column(db.Float, nullable=False)  # From user
    total_incentive = db.Column(db.Float, nullable=False)  # Calculated
    created_at = db.Column(db.DateTime, default=get_indian_time)

    cart_staff = db.relationship('User', backref='daily_sales')
    kitchen = db.relationship('Kitchen', backref='daily_sales')
    sop = db.relationship('SOP', backref='daily_sales')

class InventoryTracker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=lambda: get_indian_time().date())
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    opening_stock = db.Column(db.Float, nullable=False)
    purchase_qty = db.Column(db.Float, default=0.0)
    used_qty = db.Column(db.Float, default=0.0)
    loss_qty = db.Column(db.Float, default=0.0)
    closing_stock = db.Column(db.Float, nullable=False)
    min_threshold = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='OK')  # OK, Low, Critical

    kitchen = db.relationship('Kitchen', backref='inventory_trackers')
    ingredient = db.relationship('Ingredient', backref='inventory_trackers')

class SupplierPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=lambda: get_indian_time().date())
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    vendor_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    rate_per_unit = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_made = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(20), nullable=False)
    balance_amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=get_indian_time)

    kitchen = db.relationship('Kitchen', backref='supplier_purchases')
    ingredient = db.relationship('Ingredient', backref='supplier_purchases')

class CustomerFeedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=lambda: get_indian_time().date())
    city = db.Column(db.String(50), nullable=False)
    thela_id = db.Column(db.String(20), nullable=False)
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=False)
    feedback_type = db.Column(db.String(50), nullable=False)
    comments = db.Column(db.Text)
    action_taken = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=get_indian_time)

    kitchen = db.relationship('Kitchen', backref='customer_feedbacks')

class InventoryAdjustment(db.Model):
    __tablename__ = 'inventory_adjustments'

    id = db.Column(db.Integer, primary_key=True)
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredient.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Negative for loss, positive for found
    reason = db.Column(db.String(50), nullable=False)  # 'wastage', 'loss', 'found', 'correction'
    notes = db.Column(db.Text)
    adjusted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, default=lambda: get_indian_time().date())
    created_at = db.Column(db.DateTime, default=get_indian_time)

    kitchen = db.relationship('Kitchen', backref='inventory_adjustments')
    ingredient = db.relationship('Ingredient', backref='inventory_adjustments')
    user = db.relationship('User', backref='inventory_adjustments')

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    thela_id = db.Column(db.String(20), unique=True, nullable=False)
    cart_staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    kitchen_id = db.Column(db.Integer, db.ForeignKey('kitchen.id'), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_indian_time)

    cart_staff = db.relationship('User', backref='cart')
    kitchen = db.relationship('Kitchen', backref='carts')

class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.Text, nullable=False)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=get_indian_time)
    last_used = db.Column(db.DateTime, default=get_indian_time)

    # Relationships
    user = db.relationship('User', backref='push_subscriptions')

    def to_dict(self):
        return {
            'endpoint': self.endpoint,
            'keys': {
                'p256dh': self.p256dh,
                'auth': self.auth
            }
        }

    @property
    def p256dh_key(self):
        return self.p256dh
    
    @property
    def auth_key(self):
        return self.auth