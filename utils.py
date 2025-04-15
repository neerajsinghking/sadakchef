from datetime import datetime
import qrcode
import io
import base64
from flask import url_for
from sqlalchemy import func
from app import db
from models import Inventory

def update_inventory(ingredient_id, quantity, operation):
    """
    Update inventory for an ingredient
    
    Args:
        ingredient_id (int): ID of the ingredient
        quantity (float): Quantity to add or subtract
        operation (str): 'add' or 'subtract'
    """
    today = datetime.utcnow().date()
    
    # Get latest inventory record for this ingredient
    inventory = Inventory.query.filter_by(
        ingredient_id=ingredient_id,
        date=today
    ).first()
    
    if not inventory:
        # Get the most recent inventory record
        latest_inventory = Inventory.query.filter_by(
            ingredient_id=ingredient_id
        ).order_by(Inventory.date.desc()).first()
        
        # Create a new inventory record for today
        if latest_inventory:
            opening_stock = latest_inventory.closing_stock
        else:
            opening_stock = 0
        
        inventory = Inventory(
            ingredient_id=ingredient_id,
            date=today,
            opening_stock=opening_stock,
            purchased=0,
            used=0,
            closing_stock=opening_stock
        )
        db.session.add(inventory)
    
    # Update the inventory
    if operation == 'add':
        inventory.purchased += quantity
        inventory.closing_stock += quantity
    elif operation == 'subtract':
        inventory.used += quantity
        inventory.closing_stock -= quantity
    
    db.session.commit()

def calculate_sales(staff_id, recipe_id, kg_unsold, cash_collected):
    """
    Calculate sales data based on inputs
    
    Args:
        staff_id (int): ID of the cart staff
        recipe_id (int): ID of the recipe
        kg_unsold (float): Quantity unsold
        cash_collected (float): Cash collected
        
    Returns:
        dict: Calculated sales data
    """
    from models import Refill, SOP, User
    
    # Get today's refills for this user and recipe
    today = datetime.utcnow().date()
    
    # Calculate kg_taken
    kg_taken_query = db.session.query(
        func.sum(Refill.quantity)
    ).filter(
        Refill.staff_id == staff_id,
        Refill.recipe_id == recipe_id,
        Refill.status == 'taken',
        func.date(Refill.taken_time) == today
    ).scalar()
    
    kg_taken = float(kg_taken_query) if kg_taken_query else 0
    
    # Calculate kg_sold
    kg_sold = max(0, kg_taken - kg_unsold)
    
    # Get selling price
    sop = SOP.query.get(recipe_id)
    selling_price = sop.selling_price if sop else 0
    
    # Calculate revenue
    total_revenue = kg_sold * selling_price
    
    # Validate cash_collected
    if cash_collected > total_revenue:
        cash_collected = total_revenue
    
    upi_collected = total_revenue - cash_collected
    
    # Get incentive
    user = User.query.get(staff_id)
    incentive_per_kg = user.incentive_per_kg if user else 0
    total_incentive = kg_sold * incentive_per_kg
    
    return {
        'kg_taken': kg_taken,
        'kg_unsold': kg_unsold,
        'kg_sold': kg_sold,
        'cash_collected': cash_collected,
        'upi_collected': upi_collected,
        'total_revenue': total_revenue,
        'incentive_per_kg': incentive_per_kg,
        'total_incentive': total_incentive
    }

def generate_batch_number():
    """Generate a unique batch number for kitchen production"""
    now = datetime.utcnow()
    date_part = now.strftime('%Y%m%d')
    time_part = now.strftime('%H%M%S')
    return f"BATCH-{date_part}-{time_part}"

def generate_qr_code(data):
    """Generate a QR code image as base64 string"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffered = io.BytesIO()
        img.save(buffered)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    except Exception as e:
        # Return a placeholder or default QR code if there's an error
        print(f"Error generating QR code: {e}")
        return ""
