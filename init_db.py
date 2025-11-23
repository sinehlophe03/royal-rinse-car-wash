# init_db.py
import os
from app import app, db, User, Booking # Import app, db, and all models

with app.app_context():
    db.create_all()
    print("PostgreSQL tables created successfully.")
