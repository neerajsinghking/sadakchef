from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SelectField, TextAreaField, PasswordField, DateField, IntegerField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, Length, NumberRange, EqualTo, ValidationError
from models import Kitchen, Ingredient, SOP, User
from wtforms import DecimalField

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class UserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=64)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', 
                                   validators=[DataRequired(), EqualTo('password')])
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    role = SelectField('Role', choices=[
        ('admin', 'Admin'),
        ('kitchen_manager', 'Kitchen Manager'),
        ('cart_staff', 'Cart Staff'),
        ('delivery_staff', 'Delivery Staff')
    ], validators=[DataRequired()])
    city = SelectField('City', choices=[], validators=[DataRequired()])
    kitchen_id = SelectField('Kitchen', coerce=int, validators=[DataRequired()])
    location = StringField('Location', validators=[DataRequired(), Length(max=100)])
    mobile_no = StringField('Mobile Number', validators=[DataRequired(), Length(max=15)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    address = TextAreaField('Address')
    salary = FloatField('Salary', validators=[NumberRange(min=0)], default=0.0)
    incentive = FloatField('Incentive per Kg', validators=[NumberRange(min=0)], default=0.0)

class KitchenForm(FlaskForm):
    city = StringField('City', validators=[DataRequired(), Length(max=50)])
    location = StringField('Location', validators=[DataRequired(), Length(max=50)])
    address = TextAreaField('Address', validators=[DataRequired()])

class IngredientForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    category = StringField('Category', validators=[DataRequired(), Length(max=50)])
    unit = StringField('Unit', validators=[DataRequired(), Length(max=20)])
    minimum_stock = FloatField('Minimum Stock', validators=[DataRequired(), NumberRange(min=0)])

class SOPForm(FlaskForm):
    recipe_name = StringField('Recipe Name', validators=[DataRequired(), Length(max=100)])
    base_quantity = FloatField('Base Quantity (kg)', validators=[DataRequired(), NumberRange(min=0)])
    recipe_rate = FloatField('Recipe Rate (per kg)', validators=[DataRequired(), NumberRange(min=0)])
    description = TextAreaField('Description')

class RefillRequestForm(FlaskForm):
    sop_id = SelectField('Recipe', coerce=int, validators=[DataRequired()])
    kg_request = FloatField('Kg Request', validators=[DataRequired(), NumberRange(min=0)])

class DailySalesForm(FlaskForm):
    sop_id = SelectField('Recipe', coerce=int, validators=[DataRequired()])
    kg_unsold = DecimalField('Kg Unsold', validators=[NumberRange(min=0)], places=2, default=0)
    cash_collected = DecimalField('Cash Collected (₹)', validators=[NumberRange(min=0)], places=2, default=0)
    submit = SubmitField('Submit Sales Data')

    def validate_kg_unsold(self, field):
        if field.data is None:
            field.data = 0
        if field.data < 0:
            raise ValidationError('Kg Unsold cannot be negative')

    def validate_cash_collected(self, field):
        if field.data is None:
            field.data = 0
        if field.data < 0:
            raise ValidationError('Cash Collected cannot be negative')

class SupplierPurchaseForm(FlaskForm):
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()])
    vendor_name = StringField('Vendor Name', validators=[DataRequired(), Length(max=100)])
    quantity = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    rate_per_unit = FloatField('Rate per Unit', validators=[DataRequired(), NumberRange(min=0)])
    payment_made = FloatField('Payment Made', validators=[DataRequired(), NumberRange(min=0)])
    payment_mode = SelectField('Payment Mode', choices=[
        ('cash', 'Cash'),
        ('upi', 'UPI'),
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque')
    ], validators=[DataRequired()])

class CustomerFeedbackForm(FlaskForm):
    city = HiddenField('City')  # Hidden field, will be set automatically from kitchen
    thela_id = SelectField('Thela ID', choices=[('', 'Select Thela ID')], validators=[DataRequired()], validate_choice=False)
    feedback_type = SelectField('Feedback Type', choices=[
        ('quality_issue', 'Quality Issue'),
        ('taste_complaint', 'Taste Complaint'),
        ('service_complaint', 'Service Complaint'),
        ('appreciation', 'Appreciation'),
        ('suggestion', 'Suggestion'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    comments = TextAreaField('Comments', validators=[DataRequired()])
    submit = SubmitField('Submit Feedback')

    def __init__(self, kitchen_id=None, *args, **kwargs):
        super(CustomerFeedbackForm, self).__init__(*args, **kwargs)
        
        # If kitchen_id is provided, populate thela choices
        if kitchen_id:
            from models import User
            cart_staff = User.query.filter_by(
                kitchen_id=kitchen_id,
                role='cart_staff',
                is_active=True
            ).all()
            
            self.thela_id.choices = [('', 'Select Thela ID')] + [
                (f'CART{str(u.id).zfill(3)}', f'CART{str(u.id).zfill(3)} - {u.name}') 
                for u in cart_staff
            ]

class InventoryAdjustmentForm(FlaskForm):
    ingredient_id = SelectField('Ingredient', coerce=int, validators=[DataRequired()])
    quantity = FloatField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    reason = SelectField('Reason', choices=[
        ('burnt', 'Burnt'),
        ('spillage', 'Spillage'),
        ('theft', 'Theft'),
        ('expired', 'Expired'),
        ('damaged', 'Damaged'),
        ('other', 'Other')
    ], validators=[DataRequired()])
    notes = TextAreaField('Notes')

class ChangePasswordForm(FlaskForm):
    old_password = PasswordField('Old Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', 
                                   validators=[DataRequired(), EqualTo('new_password')])

class ProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    mobile_no = StringField('Mobile Number', validators=[DataRequired(), Length(max=15)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    address = TextAreaField('Address')

class AnalysisForm(FlaskForm):
    start_date = DateField('Start Date', validators=[DataRequired()])
    end_date = DateField('End Date', validators=[DataRequired()])
    submit = SubmitField('Apply Filter')

class DateRangeForm(FlaskForm):
    start_date = DateField('Start Date', format='%Y-%m-%d', validators=[DataRequired()])
    end_date = DateField('End Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Update')