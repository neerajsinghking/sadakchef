from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, FloatField, TextAreaField, BooleanField, DateField, SubmitField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange, ValidationError
from datetime import datetime

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    role = SelectField('Role', choices=[('chef', 'Chef'), ('cart', 'Cart Staff')], validators=[DataRequired()])
    mobile = StringField('Mobile Number', validators=[DataRequired(), Length(min=10, max=15)])
    salary = FloatField('Salary', validators=[DataRequired(), NumberRange(min=0)])
    location = StringField('Location', validators=[Optional(), Length(max=100)])
    incentive_per_kg = FloatField('Incentive per KG', validators=[Optional(), NumberRange(min=0)])
    submit = SubmitField('Add User')

class IngredientForm(FlaskForm):
    name = StringField('Ingredient Name', validators=[DataRequired(), Length(min=2, max=100)])
    category = StringField('Category', validators=[DataRequired(), Length(min=2, max=50)])
    unit = StringField('Unit', validators=[DataRequired(), Length(min=1, max=20)])
    submit = SubmitField('Add Ingredient')

class SOPForm(FlaskForm):
    name = StringField('Recipe Name', validators=[DataRequired(), Length(min=2, max=100)])
    base_quantity = FloatField('Base Quantity (kg)', validators=[DataRequired(), NumberRange(min=0.1)])
    selling_price = FloatField('Selling Price per kg', validators=[DataRequired(), NumberRange(min=1)])
    description = TextAreaField('Description', validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Save Recipe')

class SOPIngredientForm(FlaskForm):
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0.001)])
    note = StringField('Note', validators=[Optional(), Length(max=255)])
    submit = SubmitField('Add Ingredient')

class RefillRequestForm(FlaskForm):
    recipe_id = SelectField('Recipe', coerce=int, validators=[DataRequired()])
    quantity = FloatField('Quantity (kg)', validators=[DataRequired(), NumberRange(min=0.1)])
    submit = SubmitField('Request Refill')

class UpdateRefillStatusForm(FlaskForm):
    refill_id = HiddenField('Refill ID', validators=[DataRequired()])
    action = HiddenField('Action', validators=[DataRequired()])
    submit = SubmitField('Update Status')

class SalesForm(FlaskForm):
    recipe_id = SelectField('Recipe', coerce=int, validators=[DataRequired()])
    kg_unsold = FloatField('Unsold Quantity (kg)', validators=[DataRequired(), NumberRange(min=0)])
    cash_collected = FloatField('Cash Collected (₹)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Submit Sales')

class AttendanceForm(FlaskForm):
    present = BooleanField('Present')
    submit = SubmitField('Submit Attendance')

class ApproveAttendanceForm(FlaskForm):
    attendance_id = HiddenField('Attendance ID', validators=[DataRequired()])
    approve = HiddenField('Approve', validators=[DataRequired()])
    submit = SubmitField('Update')

class SupplierPurchaseForm(FlaskForm):
    vendor_name = StringField('Vendor Name', validators=[DataRequired(), Length(min=2, max=100)])
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0.001)])
    rate_per_unit = FloatField('Rate per Unit (₹)', validators=[DataRequired(), NumberRange(min=0.01)])
    payment_made = FloatField('Payment Made (₹)', validators=[DataRequired(), NumberRange(min=0)])
    payment_mode = SelectField('Payment Mode', choices=[
        ('cash', 'Cash'), 
        ('upi', 'UPI'), 
        ('bank_transfer', 'Bank Transfer'),
        ('credit', 'Credit')
    ], validators=[DataRequired()])
    submit = SubmitField('Add Purchase')

class FeedbackForm(FlaskForm):
    thela_id = StringField('Thela ID', validators=[DataRequired()])
    feedback_type = SelectField('Feedback Type', choices=[
        ('complaint', 'Complaint'), 
        ('suggestion', 'Suggestion'), 
        ('appreciation', 'Appreciation')
    ], validators=[DataRequired()])
    comments = TextAreaField('Comments', validators=[DataRequired(), Length(min=5, max=1000)])
    submit = SubmitField('Submit Feedback')

class UpdateFeedbackForm(FlaskForm):
    feedback_id = HiddenField('Feedback ID', validators=[DataRequired()])
    action_taken = TextAreaField('Action Taken', validators=[DataRequired(), Length(min=5, max=1000)])
    submit = SubmitField('Update Feedback')

class ExportForm(FlaskForm):
    table = SelectField('Select Table', choices=[
        ('users', 'Users'),
        ('ingredients', 'Ingredients'),
        ('sops', 'SOPs'),
        ('inventory', 'Inventory'),
        ('refills', 'Refill Requests'),
        ('kitchen_production', 'Kitchen Production'),
        ('sales', 'Sales'),
        ('attendance', 'Attendance'),
        ('supplier_purchases', 'Supplier Purchases'),
        ('feedback', 'Feedback')
    ], validators=[DataRequired()])
    submit = SubmitField('Export to Excel')
