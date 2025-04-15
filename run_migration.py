from app import app
from migrations.add_sop_status import upgrade

if __name__ == "__main__":
    with app.app_context():
        print("Running migration to add status columns to SOP table...")
        upgrade()
        print("Migration completed successfully!") 