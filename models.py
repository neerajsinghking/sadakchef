from app import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, chef, cart
    staff_id = db.Column(db.String(20), unique=True)  # Thela ID or Chef ID
    mobile = db.Column(db.String(15))
    salary = db.Column(db.Float)
    location = db.Column(db.String(100))  # For cart staff only
    incentive_per_kg = db.Column(db.Float, default=0)  # For cart staff only

    # Relationships
    refill_requests = db.relationship('Refill', foreign_keys='Refill.staff_id', backref='staff', lazy=True)
    chef_refill_requests = db.relationship('Refill', foreign_keys='Refill.chef_id', backref='chef', lazy=True)
    kitchen_productions = db.relationship('KitchenProduction', backref='chef', lazy=True)
    sales = db.relationship('Sales', backref='staff', lazy=True)
    attendances = db.relationship('Attendance', foreign_keys='Attendance.staff_id', backref='staff', lazy=True)
    approved_attendances = db.relationship('Attendance', foreign_keys='Attendance.approved_by', backref='approver', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Ingredient(db.Model):
    __tablename__ = 'ingredients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    unit = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    sop_ingredients = db.relationship('SOPIngredient', backref='ingredient', lazy=True)
    inventory_records = db.relationship('Inventory', backref='ingredient', lazy=True)
    supplier_purchases = db.relationship('SupplierPurchase', backref='ingredient', lazy=True)

    def __repr__(self):
        return f'<Ingredient {self.name}>'

class SOP(db.Model):
    __tablename__ = 'sops'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    base_quantity = db.Column(db.Float, nullable=False)  # in kg
    selling_price = db.Column(db.Float, nullable=False)  # per kg
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    discontinued_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    ingredients = db.relationship('SOPIngredient', backref='sop', lazy=True)
    refill_requests = db.relationship('Refill', backref='recipe', lazy=True)
    kitchen_productions = db.relationship('KitchenProduction', backref='recipe', lazy=True)
    sales = db.relationship('Sales', backref='recipe', lazy=True)

    def __repr__(self):
        return f'<SOP {self.name}>'

class SOPIngredient(db.Model):
    __tablename__ = 'sop_ingredients'

    id = db.Column(db.Integer, primary_key=True)
    sop_id = db.Column(db.Integer, db.ForeignKey('sops.id'), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255))

    def __repr__(self):
        return f'<SOPIngredient {self.sop_id}-{self.ingredient_id}>'

class Staff(db.Model):
    __tablename__ = 'staff'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    role = db.Column(db.String(20), nullable=False)  # chef, cart
    active = db.Column(db.Boolean, default=True)

    # For cart staff
    thela_id = db.Column(db.String(20), unique=True)
    location = db.Column(db.String(100))
    incentive_per_kg = db.Column(db.Float, default=0)

    # Common fields
    salary = db.Column(db.Float)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('staff_details', uselist=False))

    def __repr__(self):
        return f'<Staff {self.id}-{self.role}>'

class Inventory(db.Model):
    __tablename__ = 'inventory'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    opening_stock = db.Column(db.Float, nullable=False)
    purchased = db.Column(db.Float, default=0)
    used = db.Column(db.Float, default=0)
    closing_stock = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Inventory {self.date}-{self.ingredient_id}>'

class Refill(db.Model):
    __tablename__ = 'refills'

    id = db.Column(db.Integer, primary_key=True)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('sops.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # in kg

    request_date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    request_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Status tracking
    status = db.Column(db.String(50), default='requested')  # requested, accepted, prepared, taken
    accepted_time = db.Column(db.DateTime)
    prepared_time = db.Column(db.DateTime)
    taken_time = db.Column(db.DateTime)

    # Chef who processed the refill
    chef_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __repr__(self):
        return f'<Refill {self.id} - {self.status}>'

class KitchenProduction(db.Model):
    __tablename__ = 'kitchen_production'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    batch_no = db.Column(db.String(100), nullable=False, unique=True)
    chef_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('sops.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # in kg

    time_started = db.Column(db.DateTime, nullable=False)
    time_completed = db.Column(db.DateTime)

    # Link to refill request
    refill_id = db.Column(db.Integer, db.ForeignKey('refills.id'))
    refill = db.relationship('Refill', backref=db.backref('production', uselist=False))

    def __repr__(self):
        return f'<KitchenProduction {self.batch_no}>'

class Sales(db.Model):
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipe_id = db.Column(db.Integer, db.ForeignKey('sops.id'), nullable=False)

    kg_taken = db.Column(db.Float, nullable=False)
    kg_unsold = db.Column(db.Float, nullable=False)
    kg_sold = db.Column(db.Float, nullable=False)

    cash_collected = db.Column(db.Float, nullable=False)
    upi_collected = db.Column(db.Float, nullable=False)
    total_revenue = db.Column(db.Float, nullable=False)

    incentive_per_kg = db.Column(db.Float)
    total_incentive = db.Column(db.Float)

    def __repr__(self):
        return f'<Sales {self.date}-{self.staff_id}>'

class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    present = db.Column(db.Boolean, default=False)
    approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    def __repr__(self):
        return f'<Attendance {self.date}-{self.staff_id}>'

class SupplierPurchase(db.Model):
    __tablename__ = 'supplier_purchases'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    vendor_name = db.Column(db.String(100), nullable=False)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    rate_per_unit = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_made = db.Column(db.Float, nullable=False)
    payment_mode = db.Column(db.String(50), nullable=False)
    balance_amount = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<SupplierPurchase {self.id}-{self.vendor_name}>'

class Feedback(db.Model):
    __tablename__ = 'feedback'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    thela_id = db.Column(db.String(20), nullable=False)
    feedback_type = db.Column(db.String(50), nullable=False)
    comments = db.Column(db.Text, nullable=False)
    action_taken = db.Column(db.Text)

    def __repr__(self):
        return f'<Feedback {self.id}-{self.thela_id}>'