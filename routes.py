import os
import logging
import pandas as pd
import qrcode
from io import BytesIO
import base64
from werkzeug.security import check_password_hash, generate_password_hash
from flask import render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta, date
from sqlalchemy import func, cast, Date

from app import app, db
from models import User, Ingredient, SOP, SOPIngredient, Staff, Inventory, Refill, KitchenProduction, Sales, Attendance, SupplierPurchase, Feedback
from forms import (LoginForm, UserForm, IngredientForm, SOPForm, SOPIngredientForm, 
                   RefillRequestForm, UpdateRefillStatusForm, SalesForm, AttendanceForm, 
                   ApproveAttendanceForm, SupplierPurchaseForm, FeedbackForm, 
                   UpdateFeedbackForm, ExportForm)
from utils import update_inventory, calculate_sales, generate_batch_number, generate_qr_code

# ===== Authentication Routes =====
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'chef':
            return redirect(url_for('chef_dashboard'))
        elif current_user.role == 'cart':
            return redirect(url_for('cart_dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password_hash, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'chef':
                return redirect(url_for('chef_dashboard'))
            elif user.role == 'cart':
                return redirect(url_for('cart_dashboard'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ===== Admin Routes =====
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get counts for dashboard
    staff_count = User.query.filter(User.role != 'admin').count()
    chef_count = User.query.filter_by(role='chef').count()
    cart_count = User.query.filter_by(role='cart').count()
    
    # Get active refill requests
    active_refills = Refill.query.filter(Refill.status != 'taken').all()
    
    # Get today's sales
    today = date.today()
    today_sales = Sales.query.filter_by(date=today).all()
    total_revenue_today = sum(sale.total_revenue for sale in today_sales)
    
    # Get low stock items - converting to dictionary for easier access in template
    inventory_query = db.session.query(
        Ingredient.name,
        Inventory.closing_stock,
        Ingredient.unit
    ).join(Ingredient).order_by(Inventory.closing_stock).limit(5).all()
    
    # Create objects with attributes for easy template access
    inventory_items = []
    for item in inventory_query:
        inventory_items.append({
            'name': item.name,
            'closing_stock': item.closing_stock,
            'unit': item.unit
        })
    
    # Get recent feedbacks
    recent_feedbacks = Feedback.query.order_by(Feedback.date.desc()).limit(5).all()
    
    # Get daily sales for the past week for chart
    past_week = datetime.now().date() - timedelta(days=7)
    daily_sales = db.session.query(
        cast(Sales.date, Date).label('sale_date'),
        func.sum(Sales.total_revenue).label('total')
    ).filter(Sales.date >= past_week).group_by('sale_date').all()
    
    # Format for chart
    dates = [str(s.sale_date) for s in daily_sales]
    revenues = [float(s.total) for s in daily_sales]
    
    return render_template(
        'admin/dashboard.html',
        staff_count=staff_count,
        chef_count=chef_count,
        cart_count=cart_count,
        active_refills=active_refills,
        total_revenue_today=total_revenue_today,
        inventory_items=inventory_items,
        recent_feedbacks=recent_feedbacks,
        dates=dates,
        revenues=revenues
    )

@app.route('/admin/sop', methods=['GET', 'POST'])
@login_required
def admin_sop():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    show_inactive = request.args.get('show_inactive', '0') == '1'
    
    sop_form = SOPForm()
    ingredient_form = SOPIngredientForm()
    
    # Populate the ingredient select field
    ingredient_form.ingredient_id.choices = [(i.id, f"{i.name} ({i.unit})") for i in Ingredient.query.all()]
    
    if request.method == 'POST':
        if 'name' in request.form and sop_form.validate_on_submit():
            # Creating a new SOP
            sop = SOP(
                name=sop_form.name.data,
                base_quantity=sop_form.base_quantity.data,
                selling_price=sop_form.selling_price.data,
                description=sop_form.description.data,
                is_active=True
            )
            db.session.add(sop)
            db.session.commit()
            flash(f'SOP for {sop.name} created successfully!', 'success')
            return redirect(url_for('admin_sop'))
        
        elif 'ingredient_id' in request.form and ingredient_form.validate_on_submit():
            # Adding ingredient to an existing SOP
            sop_id = request.form.get('sop_id')
            
            # Validate sop_id
            if not sop_id:
                flash('Invalid SOP selected.', 'danger')
                return redirect(url_for('admin_sop'))
            
            try:
                sop_id = int(sop_id)
                sop = SOP.query.get(sop_id)
            except (ValueError, TypeError):
                flash('Invalid SOP ID format.', 'danger')
                return redirect(url_for('admin_sop'))
            
            if sop:
                sop_ingredient = SOPIngredient(
                    sop_id=sop_id,
                    ingredient_id=ingredient_form.ingredient_id.data,
                    quantity=ingredient_form.quantity.data,
                    note=ingredient_form.note.data
                )
                db.session.add(sop_ingredient)
                db.session.commit()
                flash('Ingredient added to SOP successfully!', 'success')
            else:
                flash('SOP not found.', 'danger')
            
            return redirect(url_for('admin_sop'))
    
    # Get all SOPs with filter
    sops_query = SOP.query
    if not show_inactive:
        sops_query = sops_query.filter_by(is_active=True)
    sops = sops_query.order_by(SOP.name).all()
    
    # Get ingredients for each SOP
    sop_ingredients = {}
    for sop in sops:
        ingredients = db.session.query(SOPIngredient, Ingredient) \
            .join(Ingredient, SOPIngredient.ingredient_id == Ingredient.id) \
            .filter(SOPIngredient.sop_id == sop.id).all()
        sop_ingredients[sop.id] = ingredients
    
    return render_template(
        'admin/sop.html',
        sop_form=sop_form,
        ingredient_form=ingredient_form,
        sops=sops,
        sop_ingredients=sop_ingredients,
        show_inactive=show_inactive
    )

@app.route('/admin/sop/<int:sop_id>/toggle-status', methods=['POST'])
@login_required
def toggle_sop_status(sop_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    try:
        sop = SOP.query.get_or_404(sop_id)
        
        # Toggle status
        sop.is_active = not sop.is_active
        if not sop.is_active:
            sop.discontinued_at = datetime.utcnow()
        else:
            sop.discontinued_at = None
        
        db.session.commit()
        
        status = "activated" if sop.is_active else "discontinued"
        flash(f'Recipe "{sop.name}" has been {status}. Historical data is preserved.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating recipe status: {str(e)}', 'danger')
        
    return redirect(url_for('admin_sop', show_inactive='1' if not sop.is_active else '0'))

@app.route('/admin/sop/<int:sop_id>/delete', methods=['POST'])
@login_required
def delete_sop(sop_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    try:
        sop = SOP.query.get_or_404(sop_id)
        
        # First delete all related refills
        Refill.query.filter_by(recipe_id=sop_id).delete()
        
        # Delete related kitchen productions
        KitchenProduction.query.filter_by(recipe_id=sop_id).delete()
        
        # Delete related sales records
        Sales.query.filter_by(recipe_id=sop_id).delete()
        
        # Delete all ingredients related to this SOP
        SOPIngredient.query.filter_by(sop_id=sop_id).delete()
        
        # Finally delete the SOP
        db.session.delete(sop)
        db.session.commit()
        
        flash(f'SOP for {sop.name} has been deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting SOP: {str(e)}', 'danger')
        
    return redirect(url_for('admin_sop'))

@app.route('/admin/sop/ingredient/<int:sop_ingredient_id>/delete', methods=['POST'])
@login_required
def delete_sop_ingredient(sop_ingredient_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    sop_ingredient = SOPIngredient.query.get_or_404(sop_ingredient_id)
    sop_id = sop_ingredient.sop_id
    
    db.session.delete(sop_ingredient)
    db.session.commit()
    
    flash('Ingredient removed from SOP successfully.', 'success')
    return redirect(url_for('admin_sop'))

@app.route('/admin/staff', methods=['GET', 'POST'])
@login_required
def admin_staff():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = UserForm()
    if form.validate_on_submit():
        # Generate staff_id based on role
        if form.role.data == 'chef':
            last_chef = User.query.filter_by(role='chef').order_by(User.id.desc()).first()
            if last_chef and last_chef.staff_id and last_chef.staff_id.startswith('CHEF'):
                chef_num = int(last_chef.staff_id[4:]) + 1
            else:
                chef_num = 1
            staff_id = f'CHEF{chef_num:03d}'
            location = 'Kitchen'
            incentive_per_kg = 0
        else:  # cart staff
            last_cart = User.query.filter_by(role='cart').order_by(User.id.desc()).first()
            if last_cart and last_cart.staff_id and last_cart.staff_id.startswith('CART'):
                cart_num = int(last_cart.staff_id[4:]) + 1
            else:
                cart_num = 1
            staff_id = f'CART{cart_num:03d}'
            location = form.location.data
            incentive_per_kg = form.incentive_per_kg.data or 0
        
        # Create user
        user = User(
            username=form.username.data,
            password_hash=generate_password_hash(form.password.data),
            name=form.name.data,
            role=form.role.data,
            staff_id=staff_id,
            mobile=form.mobile.data,
            salary=form.salary.data,
            location=location,
            incentive_per_kg=incentive_per_kg
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Also create Staff record
        staff = Staff(
            user_id=user.id,
            role=form.role.data,
            thela_id=staff_id if form.role.data == 'cart' else None,
            location=location if form.role.data == 'cart' else None,
            incentive_per_kg=incentive_per_kg if form.role.data == 'cart' else 0,
            salary=form.salary.data
        )
        
        db.session.add(staff)
        db.session.commit()
        
        flash(f'{form.role.data.capitalize()} {form.name.data} added successfully!', 'success')
        return redirect(url_for('admin_staff'))
    
    # Get all staff members
    chefs = User.query.filter_by(role='chef').all()
    cart_staff = User.query.filter_by(role='cart').all()
    
    return render_template(
        'admin/staff.html',
        form=form,
        chefs=chefs,
        cart_staff=cart_staff
    )

@app.route('/admin/staff/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_staff(user_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(user_id)
    
    if user.role == 'admin':
        flash('Cannot delete admin user.', 'danger')
        return redirect(url_for('admin_staff'))
    
    # Delete the staff record first
    staff = Staff.query.filter_by(user_id=user_id).first()
    if staff:
        db.session.delete(staff)
    
    # Delete the user
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Staff member {user.name} has been deleted.', 'success')
    return redirect(url_for('admin_staff'))

@app.route('/admin/ingredients', methods=['GET', 'POST'])
@login_required
def admin_ingredients():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = IngredientForm()
    if form.validate_on_submit():
        ingredient = Ingredient(
            name=form.name.data,
            category=form.category.data,
            unit=form.unit.data
        )
        
        db.session.add(ingredient)
        db.session.commit()
        
        # Initialize inventory for this ingredient
        inventory = Inventory(
            ingredient_id=ingredient.id,
            opening_stock=0,
            purchased=0,
            used=0,
            closing_stock=0
        )
        
        db.session.add(inventory)
        db.session.commit()
        
        flash(f'Ingredient {form.name.data} added successfully!', 'success')
        return redirect(url_for('admin_ingredients'))
    
    # Get all ingredients
    ingredients = Ingredient.query.all()
    
    return render_template(
        'admin/ingredients.html',
        form=form,
        ingredients=ingredients
    )

@app.route('/admin/ingredients/<int:ingredient_id>/delete', methods=['POST'])
@login_required
def delete_ingredient(ingredient_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    ingredient = Ingredient.query.get_or_404(ingredient_id)
    
    # Check if ingredient is used in any SOP
    sop_ingredients = SOPIngredient.query.filter_by(ingredient_id=ingredient_id).first()
    if sop_ingredients:
        flash(f'Cannot delete {ingredient.name} as it is used in SOPs.', 'danger')
        return redirect(url_for('admin_ingredients'))
    
    # Delete inventory records
    Inventory.query.filter_by(ingredient_id=ingredient_id).delete()
    
    # Delete supplier purchase records
    SupplierPurchase.query.filter_by(ingredient_id=ingredient_id).delete()
    
    # Delete the ingredient
    db.session.delete(ingredient)
    db.session.commit()
    
    flash(f'Ingredient {ingredient.name} has been deleted.', 'success')
    return redirect(url_for('admin_ingredients'))

@app.route('/admin/inventory')
@login_required
def admin_inventory():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get the latest inventory for each ingredient
    today = date.today()
    
    # Get all ingredients with their current inventory
    inventory_items = db.session.query(
        Ingredient,
        Inventory
    ).join(
        Inventory, 
        Inventory.ingredient_id == Ingredient.id
    ).filter(
        Inventory.date == today
    ).all()
    
    # If no inventory for today, show the most recent
    if not inventory_items:
        latest_date = db.session.query(func.max(Inventory.date)).scalar()
        if latest_date:
            inventory_items = db.session.query(
                Ingredient,
                Inventory
            ).join(
                Inventory, 
                Inventory.ingredient_id == Ingredient.id
            ).filter(
                Inventory.date == latest_date
            ).all()
    
    return render_template(
        'admin/inventory.html',
        inventory_items=inventory_items,
        today=today
    )

@app.route('/admin/kitchen')
@login_required
def admin_kitchen():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get active refill requests
    refill_requests = db.session.query(
        Refill,
        User,
        SOP
    ).join(
        User, Refill.staff_id == User.id
    ).join(
        SOP, Refill.recipe_id == SOP.id
    ).order_by(Refill.request_time.desc()).all()
    
    # Get kitchen production data
    productions = db.session.query(
        KitchenProduction,
        User,
        SOP
    ).join(
        User, KitchenProduction.chef_id == User.id
    ).join(
        SOP, KitchenProduction.recipe_id == SOP.id
    ).order_by(KitchenProduction.time_started.desc()).all()
    
    return render_template(
        'admin/kitchen.html',
        refill_requests=refill_requests,
        productions=productions
    )

@app.route('/admin/purchases', methods=['GET', 'POST'])
@login_required
def admin_purchases():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = SupplierPurchaseForm()
    form.ingredient_id.choices = [(i.id, f"{i.name} ({i.unit})") for i in Ingredient.query.all()]
    
    if form.validate_on_submit():
        try:
            # Validate and convert form data
            quantity = float(form.quantity.data) if form.quantity.data is not None else 0.0
            rate_per_unit = float(form.rate_per_unit.data) if form.rate_per_unit.data is not None else 0.0
            payment_made = float(form.payment_made.data) if form.payment_made.data is not None else 0.0
            
            # Calculate total amount
            total_amount = quantity * rate_per_unit
            balance_amount = total_amount - payment_made
            
            # Validate ingredient_id
            ingredient_id = form.ingredient_id.data
            if not ingredient_id or not Ingredient.query.get(ingredient_id):
                flash('Please select a valid ingredient.', 'danger')
                return redirect(url_for('admin_purchases'))
        except (ValueError, TypeError) as e:
            flash(f'Invalid numeric input: {str(e)}', 'danger')
            return redirect(url_for('admin_purchases'))
        
        purchase = SupplierPurchase(
            vendor_name=form.vendor_name.data,
            ingredient_id=ingredient_id,
            quantity=quantity,
            rate_per_unit=rate_per_unit,
            total_amount=total_amount,
            payment_made=payment_made,
            payment_mode=form.payment_mode.data,
            balance_amount=balance_amount
        )
        
        db.session.add(purchase)
        db.session.commit()
        
        # Update inventory
        update_inventory(ingredient_id, quantity, 'add')
        
        flash('Purchase added successfully!', 'success')
        return redirect(url_for('admin_purchases'))
    
    # Get all purchases
    purchases = db.session.query(
        SupplierPurchase,
        Ingredient
    ).join(
        Ingredient, SupplierPurchase.ingredient_id == Ingredient.id
    ).order_by(SupplierPurchase.date.desc()).all()
    
    return render_template(
        'admin/purchases.html',
        form=form,
        purchases=purchases
    )

@app.route('/admin/attendance')
@login_required
def admin_attendance():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get pending attendance records
    pending_attendance = Attendance.query.filter_by(approved=False).all()
    
    return render_template('admin/attendance.html', pending_attendance=pending_attendance)

@app.route('/admin/attendance/<int:attendance_id>/approve', methods=['POST'])
@login_required
def approve_attendance(attendance_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    attendance = Attendance.query.get_or_404(attendance_id)
    attendance.approved = True
    attendance.approved_by = current_user.id
    db.session.commit()
    
    flash('Attendance approved successfully!', 'success')
    return redirect(url_for('admin_attendance'))

@app.route('/admin/attendance/<int:attendance_id>/reject', methods=['POST'])
@login_required
def reject_attendance(attendance_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    attendance = Attendance.query.get_or_404(attendance_id)
    db.session.delete(attendance)
    db.session.commit()
    
    flash('Attendance rejected successfully!', 'success')
    return redirect(url_for('admin_attendance'))

@app.route('/admin/feedback')
@login_required
def admin_feedback():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get feedback data
    feedbacks = Feedback.query.order_by(Feedback.date.desc()).all()
    
    # Generate QR code for feedback form
    feedback_url = url_for('customer_feedback', _external=True)
    qr_code = generate_qr_code(feedback_url)
    
    return render_template(
        'admin/feedback.html',
        feedbacks=feedbacks,
        qr_code=qr_code
    )

@app.route('/admin/feedback/<int:feedback_id>/update', methods=['POST'])
@login_required
def update_feedback(feedback_id):
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    # Check if feedback_id is valid
    if not feedback_id:
        flash('Invalid feedback ID.', 'danger')
        return redirect(url_for('admin_feedback'))
    
    form = UpdateFeedbackForm()
    if form.validate_on_submit():
        try:
            feedback = Feedback.query.get_or_404(feedback_id)
            feedback.action_taken = form.action_taken.data
            db.session.commit()
            flash('Feedback updated successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating feedback: {str(e)}', 'danger')
    
    return redirect(url_for('admin_feedback'))

@app.route('/admin/export', methods=['GET', 'POST'])
@login_required
def admin_export():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = ExportForm()
    
    if form.validate_on_submit():
        table_name = form.table.data
        
        # Define the table object based on selection
        table_mapping = {
            'users': User,
            'ingredients': Ingredient,
            'sops': SOP,
            'inventory': Inventory,
            'refills': Refill,
            'kitchen_production': KitchenProduction,
            'sales': Sales,
            'attendance': Attendance,
            'supplier_purchases': SupplierPurchase,
            'feedback': Feedback
        }
        
        if table_name in table_mapping:
            # Get all records from the selected table
            records = table_mapping[table_name].query.all()
            
            # Convert to DataFrame
            data = []
            for record in records:
                data.append({c.name: getattr(record, c.name) for c in record.__table__.columns})
            
            df = pd.DataFrame(data)
            
            # Create Excel file
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            output.seek(0)
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{table_name}_{timestamp}.xlsx"
            
            return send_file(
                output,
                as_attachment=True,
                download_name=filename,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
    
    return render_template('admin/export.html', form=form)

# ===== Chef Routes =====
@app.route('/chef/dashboard')
@login_required
def chef_dashboard():
    if current_user.role != 'chef':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get active refill requests
    active_refills = db.session.query(
        Refill,
        User,
        SOP
    ).join(
        User, Refill.staff_id == User.id
    ).join(
        SOP, Refill.recipe_id == SOP.id
    ).filter(
        Refill.status.in_(['requested', 'accepted'])
    ).order_by(Refill.request_time.desc()).all()
    
    # Get recent production data
    recent_productions = db.session.query(
        KitchenProduction,
        SOP
    ).join(
        SOP, KitchenProduction.recipe_id == SOP.id
    ).filter(
        KitchenProduction.chef_id == current_user.id
    ).order_by(KitchenProduction.time_started.desc()).limit(5).all()
    
    # Check if attendance for today is submitted
    today = date.today()
    attendance_submitted = Attendance.query.filter_by(
        staff_id=current_user.id,
        date=today
    ).first() is not None
    
    # Get all SOPs for the calculator
    sops = SOP.query.order_by(SOP.name).all()
    
    return render_template(
        'chef/dashboard.html',
        active_refills=active_refills,
        recent_productions=recent_productions,
        attendance_submitted=attendance_submitted,
        sops=sops
    )

@app.route('/chef/refill')
@login_required
def chef_refill():
    if current_user.role != 'chef':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get all refill requests
    refill_requests = db.session.query(
        Refill,
        User,
        SOP
    ).join(
        User, Refill.staff_id == User.id
    ).join(
        SOP, Refill.recipe_id == SOP.id
    ).order_by(Refill.request_time.desc()).all()
    
    status_form = UpdateRefillStatusForm()
    
    return render_template(
        'chef/refill.html',
        refill_requests=refill_requests,
        status_form=status_form
    )

@app.route('/chef/refill/update', methods=['POST'])
@login_required
def update_refill():
    if current_user.role != 'chef':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    form = UpdateRefillStatusForm()
    if form.validate_on_submit():
        refill_id = form.refill_id.data
        action = form.action.data
        
        refill = Refill.query.get_or_404(refill_id)
        
        if action == 'accept' and refill.status == 'requested':
            refill.status = 'accepted'
            refill.chef_id = current_user.id
            refill.accepted_time = datetime.utcnow()
            
            # Create kitchen production record
            batch_no = generate_batch_number()
            
            production = KitchenProduction(
                batch_no=batch_no,
                chef_id=current_user.id,
                recipe_id=refill.recipe_id,
                quantity=refill.quantity,
                time_started=datetime.utcnow(),
                refill_id=refill.id
            )
            
            db.session.add(production)
            flash('Refill request accepted!', 'success')
            
        elif action == 'prepare' and refill.status == 'accepted':
            refill.status = 'prepared'
            refill.prepared_time = datetime.utcnow()
            
            # Update production record
            production = KitchenProduction.query.filter_by(refill_id=refill.id).first()
            if production:
                production.time_completed = datetime.utcnow()
            
            # Update inventory based on SOP
            sop = SOP.query.get(refill.recipe_id)
            if sop:
                # Scale the ingredients based on the requested quantity
                scale_factor = float(refill.quantity) / float(sop.base_quantity) if sop.base_quantity else 0
                
                # Get all ingredients for this SOP
                sop_ingredients = SOPIngredient.query.filter_by(sop_id=sop.id).all()
                
                # Update inventory for each ingredient
                for sop_ingredient in sop_ingredients:
                    used_quantity = float(sop_ingredient.quantity or 0) * scale_factor
                    update_inventory(sop_ingredient.ingredient_id, used_quantity, 'subtract')
            
            flash('Refill prepared and inventory updated!', 'success')
        
        db.session.commit()
        
        return redirect(url_for('chef_refill'))
    
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('chef_refill'))

@app.route('/chef/inventory')
@login_required
def chef_inventory():
    if current_user.role != 'chef':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get the current inventory
    today = date.today()
    
    inventory_items = db.session.query(
        Ingredient,
        Inventory
    ).join(
        Inventory, 
        Inventory.ingredient_id == Ingredient.id
    ).filter(
        Inventory.date == today
    ).all()
    
    # If no inventory for today, show the most recent
    if not inventory_items:
        latest_date = db.session.query(func.max(Inventory.date)).scalar()
        if latest_date:
            inventory_items = db.session.query(
                Ingredient,
                Inventory
            ).join(
                Inventory, 
                Inventory.ingredient_id == Ingredient.id
            ).filter(
                Inventory.date == latest_date
            ).all()
    
    return render_template(
        'chef/inventory.html',
        inventory_items=inventory_items,
        today=today
    )

@app.route('/chef/sop')
@login_required
def chef_sop():
    if current_user.role != 'chef':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get all SOPs with their ingredients
    sops = SOP.query.all()
    sop_ingredients = {}
    
    for sop in sops:
        ingredients = db.session.query(SOPIngredient, Ingredient) \
            .join(Ingredient, SOPIngredient.ingredient_id == Ingredient.id) \
            .filter(SOPIngredient.sop_id == sop.id).all()
        
        sop_ingredients[sop.id] = ingredients
    
    return render_template(
        'chef/sop.html',
        sops=sops,
        sop_ingredients=sop_ingredients
    )

@app.route('/chef/attendance', methods=['GET', 'POST'])
@login_required
def chef_attendance():
    if current_user.role != 'chef':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = AttendanceForm()
    today = date.today()
    
    # Check if attendance already submitted for today
    existing_attendance = Attendance.query.filter_by(
        staff_id=current_user.id,
        date=today
    ).first()
    
    if existing_attendance:
        flash('Attendance already submitted for today.', 'info')
        attendance_submitted = True
    else:
        attendance_submitted = False
        
        if form.validate_on_submit():
            attendance = Attendance(
                staff_id=current_user.id,
                date=today,
                present=form.present.data
            )
            
            db.session.add(attendance)
            db.session.commit()
            
            flash('Attendance submitted successfully!', 'success')
            attendance_submitted = True
    
    # Get past week attendance
    past_week = today - timedelta(days=7)
    attendance_records = Attendance.query.filter(
        Attendance.staff_id == current_user.id,
        Attendance.date >= past_week,
        Attendance.date <= today
    ).order_by(Attendance.date.desc()).all()
    
    return render_template(
        'chef/attendance.html',
        form=form,
        attendance_submitted=attendance_submitted,
        attendance_records=attendance_records,
        today=today
    )

# ===== Cart Staff Routes =====
@app.route('/cart/dashboard')
@login_required
def cart_dashboard():
    if current_user.role != 'cart':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    # Get refill status
    refill_status = db.session.query(
        Refill,
        SOP
    ).join(
        SOP, Refill.recipe_id == SOP.id
    ).filter(
        Refill.staff_id == current_user.id
    ).order_by(Refill.request_time.desc()).limit(5).all()
    
    # Check if sales for today is submitted
    today = date.today()
    sales_submitted = Sales.query.filter_by(
        staff_id=current_user.id,
        date=today
    ).first() is not None
    
    # Check if attendance for today is submitted
    attendance_submitted = Attendance.query.filter_by(
        staff_id=current_user.id,
        date=today
    ).first() is not None
    
    # Get today's refill data
    today_refills = db.session.query(
        Refill,
        SOP
    ).join(
        SOP, Refill.recipe_id == SOP.id
    ).filter(
        Refill.staff_id == current_user.id,
        cast(Refill.request_time, Date) == today
    ).all()
    
    # Calculate total kg taken today
    kg_taken = sum(refill.quantity for refill, _ in today_refills)
    
    return render_template(
        'cart/dashboard.html',
        refill_status=refill_status,
        sales_submitted=sales_submitted,
        attendance_submitted=attendance_submitted,
        kg_taken=kg_taken
    )

@app.route('/cart/refill', methods=['GET', 'POST'])
@login_required
def cart_refill():
    if current_user.role != 'cart':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = RefillRequestForm()
    form.recipe_id.choices = [(sop.id, sop.name) for sop in SOP.query.all()]
    
    if form.validate_on_submit():
        refill = Refill(
            staff_id=current_user.id,
            recipe_id=form.recipe_id.data,
            quantity=form.quantity.data,
            status='requested'
        )
        
        db.session.add(refill)
        db.session.commit()
        
        flash('Refill request submitted successfully!', 'success')
        return redirect(url_for('cart_refill'))
    
    # Get all refill requests for this cart
    refill_requests = db.session.query(
        Refill,
        SOP
    ).join(
        SOP, Refill.recipe_id == SOP.id
    ).filter(
        Refill.staff_id == current_user.id
    ).order_by(Refill.request_time.desc()).all()
    
    status_form = UpdateRefillStatusForm()
    
    return render_template(
        'cart/refill.html',
        form=form,
        refill_requests=refill_requests,
        status_form=status_form
    )

@app.route('/cart/refill/update', methods=['POST'])
@login_required
def cart_update_refill():
    if current_user.role != 'cart':
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('login'))
    
    form = UpdateRefillStatusForm()
    if form.validate_on_submit():
        refill_id = form.refill_id.data
        action = form.action.data
        
        refill = Refill.query.get_or_404(refill_id)
        
        # Ensure the refill belongs to this cart
        if refill.staff_id != current_user.id:
            flash('You do not have permission to update this refill.', 'danger')
            return redirect(url_for('cart_refill'))
        
        if action == 'take' and refill.status == 'prepared':
            refill.status = 'taken'
            refill.taken_time = datetime.utcnow()
            
            db.session.commit()
            flash('Refill marked as taken!', 'success')
        
        return redirect(url_for('cart_refill'))
    
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('cart_refill'))

@app.route('/cart/sales', methods=['GET', 'POST'])
@login_required
def cart_sales():
    if current_user.role != 'cart':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = SalesForm()
    form.recipe_id.choices = [(sop.id, sop.name) for sop in SOP.query.all()]
    
    today = date.today()
    
    # Check if sales already submitted for today
    existing_sales = Sales.query.filter_by(
        staff_id=current_user.id,
        date=today
    ).first()
    
    if existing_sales:
        flash('Sales already submitted for today.', 'info')
        sales_submitted = True
    else:
        sales_submitted = False
        
        if form.validate_on_submit():
            # Get all taken refills for today - using taken_time for validation
            today_refills = db.session.query(
                func.sum(Refill.quantity)
            ).filter(
                Refill.staff_id == current_user.id,
                Refill.status == 'taken',
                cast(Refill.taken_time, Date) == today,  # Changed back to taken_time
                Refill.recipe_id == form.recipe_id.data
            ).scalar() or 0
            
            kg_taken = float(today_refills)
            kg_unsold = float(form.kg_unsold.data) if form.kg_unsold.data is not None else 0.0
            
            # Debug log
            app.logger.info(f"Recipe ID: {form.recipe_id.data}")
            app.logger.info(f"Today's date: {today}")
            app.logger.info(f"KG Taken: {kg_taken}")
            
            # Validate unsold quantity
            if kg_taken == 0:
                # Get refill status for debugging
                refill_status = db.session.query(
                    Refill
                ).filter(
                    Refill.staff_id == current_user.id,
                    Refill.recipe_id == form.recipe_id.data,
                    cast(Refill.request_time, Date) == today
                ).all()
                
                status_info = []
                for refill in refill_status:
                    status_info.append(f"Status: {refill.status}, Taken time: {refill.taken_time}")
                
                app.logger.info(f"Refill status for today: {status_info}")
                flash('No refills taken today for this recipe. Cannot submit sales.', 'danger')
                return redirect(url_for('cart_sales'))
                
            if kg_unsold > kg_taken:
                flash('Unsold quantity cannot be greater than taken quantity.', 'danger')
                return redirect(url_for('cart_sales'))
            
            # Calculate other fields
            kg_sold = kg_taken - kg_unsold
            
            # Get selling price
            sop = SOP.query.get(form.recipe_id.data)
            selling_price = float(sop.selling_price) if sop and sop.selling_price else 0.0
            
            # Calculate revenue
            total_revenue = kg_sold * selling_price
            cash_collected = float(form.cash_collected.data) if form.cash_collected.data is not None else 0.0
            
            # Validate cash collected
            if cash_collected > total_revenue:
                flash('Cash collected cannot be greater than total revenue.', 'danger')
                return redirect(url_for('cart_sales'))
            
            upi_collected = float(total_revenue - cash_collected)
            
            # Get incentive
            incentive_per_kg = float(current_user.incentive_per_kg or 0)
            total_incentive = float(kg_sold * incentive_per_kg)
            
            sales = Sales(
                staff_id=current_user.id,
                recipe_id=form.recipe_id.data,
                kg_taken=kg_taken,
                kg_unsold=kg_unsold,
                kg_sold=kg_sold,
                cash_collected=cash_collected,
                upi_collected=upi_collected,
                total_revenue=total_revenue,
                incentive_per_kg=incentive_per_kg,
                total_incentive=total_incentive
            )
            
            db.session.add(sales)
            db.session.commit()
            
            flash('Sales submitted successfully!', 'success')
            sales_submitted = True
    
    # Get past week sales
    past_week = today - timedelta(days=7)
    sales_records = db.session.query(
        Sales,
        SOP
    ).join(
        SOP, Sales.recipe_id == SOP.id
    ).filter(
        Sales.staff_id == current_user.id,
        Sales.date >= past_week,
        Sales.date <= today
    ).order_by(Sales.date.desc()).all()
    
    # Get today's refill data for dropdown help
    today_refills = db.session.query(
        SOP.id,
        SOP.name,
        func.sum(Refill.quantity).label('total_quantity')
    ).join(
        Refill, Refill.recipe_id == SOP.id
    ).filter(
        Refill.staff_id == current_user.id,
        Refill.status == 'taken',
        cast(Refill.taken_time, Date) == today
    ).group_by(SOP.id, SOP.name).all()
    
    return render_template(
        'cart/sales.html',
        form=form,
        sales_submitted=sales_submitted,
        sales_records=sales_records,
        today_refills=today_refills
    )

@app.route('/cart/attendance', methods=['GET', 'POST'])
@login_required
def cart_attendance():
    if current_user.role != 'cart':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('login'))
    
    form = AttendanceForm()
    today = date.today()
    
    # Check if attendance already submitted for today
    existing_attendance = Attendance.query.filter_by(
        staff_id=current_user.id,
        date=today
    ).first()
    
    if existing_attendance:
        flash('Attendance already submitted for today.', 'info')
        attendance_submitted = True
    else:
        attendance_submitted = False
        
        if form.validate_on_submit():
            attendance = Attendance(
                staff_id=current_user.id,
                date=today,
                present=form.present.data
            )
            
            db.session.add(attendance)
            db.session.commit()
            
            flash('Attendance submitted successfully!', 'success')
            attendance_submitted = True
    
    # Get past week attendance
    past_week = today - timedelta(days=7)
    attendance_records = Attendance.query.filter(
        Attendance.staff_id == current_user.id,
        Attendance.date >= past_week,
        Attendance.date <= today
    ).order_by(Attendance.date.desc()).all()
    
    return render_template(
        'cart/attendance.html',
        form=form,
        attendance_submitted=attendance_submitted,
        attendance_records=attendance_records,
        today=today
    )

# ===== Public Routes =====
@app.route('/feedback', methods=['GET', 'POST'])
def customer_feedback():
    form = FeedbackForm()
    if form.validate_on_submit():
        feedback = Feedback(
            thela_id=form.thela_id.data,
            feedback_type=form.feedback_type.data,
            comments=form.comments.data
        )
        
        db.session.add(feedback)
        db.session.commit()
        
        flash('Thank you for your feedback!', 'success')
        return redirect(url_for('customer_feedback'))
    
    return render_template('feedback.html', form=form)

# ===== API Routes for AJAX calls =====

@app.route('/api/calculate_sop/<sop_id>/<quantity>')
@login_required
def calculate_sop(sop_id, quantity):
    try:
        # Convert parameters to proper types
        try:
            sop_id = int(sop_id)
            quantity = float(quantity)
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid SOP ID or quantity format'}), 400

        # Get SOP details
        sop = SOP.query.get(sop_id)
        if not sop:
            return jsonify({'error': 'SOP not found'}), 404
            
        # Validate quantity
        if quantity <= 0:
            return jsonify({'error': 'Quantity must be greater than 0'}), 400
            
        # Calculate scale factor
        try:
            scale_factor = quantity / float(sop.base_quantity) if sop.base_quantity else 0
            if scale_factor == 0:
                return jsonify({'error': 'Invalid base quantity in SOP'}), 400
        except (ValueError, ZeroDivisionError):
            return jsonify({'error': 'Invalid quantity or base quantity'}), 400
        
        # Get ingredients with their details
        ingredients = db.session.query(
            SOPIngredient,
            Ingredient
        ).join(
            Ingredient, SOPIngredient.ingredient_id == Ingredient.id
        ).filter(
            SOPIngredient.sop_id == sop_id
        ).all()
        
        if not ingredients:
            return jsonify({'error': 'No ingredients found for this SOP'}), 404
        
        # Format ingredients data
        ingredients_data = []
        for sop_ing, ing in ingredients:
            try:
                quantity_value = float(sop_ing.quantity or 0)
                scaled_quantity = quantity_value * scale_factor
                ingredients_data.append({
                    'name': ing.name,
                    'original_quantity': quantity_value,
                    'scaled_quantity': scaled_quantity,
                    'unit': ing.unit,
                    'note': sop_ing.note or ''
                })
            except ValueError:
                continue  # Skip invalid quantities
        
        response_data = {
            'sop_name': sop.name,
            'original_quantity': float(sop.base_quantity),
            'requested_quantity': float(quantity),
            'scale_factor': float(scale_factor),
            'ingredients': ingredients_data
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Error in calculate_sop: {str(e)}")
        return jsonify({'error': 'An error occurred while calculating ingredients'}), 500

@app.route('/api/get_sop_details/<int:sop_id>')
@login_required
def get_sop_details(sop_id):
    # Validate sop_id to ensure it's not empty
    if not sop_id:
        return jsonify({'error': 'Invalid SOP ID'}), 400
        
    sop = SOP.query.get_or_404(sop_id)
    
    ingredients = db.session.query(
        SOPIngredient,
        Ingredient
    ).join(
        Ingredient, SOPIngredient.ingredient_id == Ingredient.id
    ).filter(
        SOPIngredient.sop_id == sop_id
    ).all()
    
    ingredients_data = []
    for sop_ing, ing in ingredients:
        ingredients_data.append({
            'name': ing.name or '',
            'quantity': float(sop_ing.quantity or 0),
            'unit': ing.unit or '',
            'note': sop_ing.note or ''
        })
    
    return jsonify({
        'id': sop.id,
        'name': sop.name,
        'base_quantity': sop.base_quantity,
        'selling_price': sop.selling_price,
        'description': sop.description,
        'ingredients': ingredients_data
    })


