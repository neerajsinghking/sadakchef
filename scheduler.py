from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date
import pytz

# Using get_indian_time from models.py
from app import app, db
from models import InventoryTracker, Kitchen, Ingredient, SupplierPurchase, InventoryAdjustment, get_indian_time
import logging

scheduler = BackgroundScheduler()

def create_daily_inventory_snapshot():
    """Create daily inventory snapshot at midnight"""
    with app.app_context():
        try:
            today = date.today()
            yesterday = date.fromordinal(today.toordinal() - 1)
            
            # Get all kitchens and ingredients
            kitchens = Kitchen.query.filter_by(is_active=True).all()
            ingredients = Ingredient.query.all()
            
            for kitchen in kitchens:
                for ingredient in ingredients:
                    # Check if today's record already exists
                    existing = InventoryTracker.query.filter_by(
                        date=today,
                        kitchen_id=kitchen.id,
                        ingredient_id=ingredient.id
                    ).first()
                    
                    if existing:
                        continue
                    
                    # Get yesterday's closing stock or set to 0
                    yesterday_record = InventoryTracker.query.filter_by(
                        date=yesterday,
                        kitchen_id=kitchen.id,
                        ingredient_id=ingredient.id
                    ).first()
                    
                    opening_stock = yesterday_record.closing_stock if yesterday_record else 0.0
                    
                    # Create new tracker with yesterday's closing stock
                    tracker = InventoryTracker(
                        date=today,
                        kitchen_id=kitchen.id,
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
            logging.info('Daily inventory snapshot created successfully')
            
        except Exception as e:
            logging.error(f'Error creating daily inventory snapshot: {str(e)}')
            db.session.rollback()

# Schedule the daily snapshot at midnight
scheduler.add_job(
    create_daily_inventory_snapshot,
    CronTrigger(hour=0, minute=0),
    id='daily_inventory_snapshot',
    replace_existing=True
)

scheduler.start()

def init_scheduler():
    """Initialize the scheduler with jobs"""
    if not scheduler.running:
        # Run daily at midnight
        scheduler.add_job(
            func=create_daily_inventory_snapshot,
            trigger=CronTrigger(hour=0, minute=0),
            id='daily_inventory_snapshot',
            name='Create daily inventory snapshot',
            replace_existing=True
        )
        
        scheduler.start()
        logging.info("Scheduler initialized and started")

def shutdown_scheduler():
    """Shutdown the scheduler"""
    if scheduler.running:
        scheduler.shutdown()
        logging.info("Scheduler shutdown")
