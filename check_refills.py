from app import app, db
from models import Refill, SOP
from datetime import date
from sqlalchemy import cast, Date
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

def check_refills():
    with app.app_context():
        today = date.today()
        
        # Get today's refills
        today_refills = db.session.query(
            Refill, SOP
        ).join(
            SOP, Refill.recipe_id == SOP.id
        ).filter(
            cast(Refill.request_time, Date) == today
        ).all()
        
        if not today_refills:
            print("\nNo refill requests found for today.")
            return
        
        print("\nToday's Refill Requests:")
        print("------------------------")
        for refill, sop in today_refills:
            print(f"Recipe: {sop.name}")
            print(f"Quantity: {refill.quantity} kg")
            print(f"Status: {refill.status}")
            print(f"Request Time: {refill.request_time}")
            if refill.taken_time:
                print(f"Taken Time: {refill.taken_time}")
            print("------------------------")

if __name__ == "__main__":
    check_refills() 