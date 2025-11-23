import os
from datetime import datetime, date

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from flask_sqlalchemy import SQLAlchemy

# init_db.py
from app import app, db, User, Booking  # Import your app and models

with app.app_context():
    db.create_all()
    print("PostgreSQL tables created successfully.")
import os 
# ... other imports

# The environment variable provided by Render for your Postgres DB
DB_URL = os.environ.get('DATABASE_URL') 

# Fix for Render/Heroku Postgres URL format:
# If the URL starts with 'postgres://', change it to 'postgresql://' for SQLAlchemy
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL or 'sqlite:///royalrinse.db' 
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
        # OPTIONAL: Add an initial admin user here if needed

if __name__ == '__main__':
    # Check if we are running a special command (like creating the DB)
    if os.environ.get('INIT_DB') == 'True':
        create_db_tables()
    else:
        app.run(debug=True)
class Config:
    """Application configuration settings."""
    # Use environment variable for Secret Key, fall back to a dummy one for local dev (but this is insecure)
    SECRET_KEY = os.environ.get("SECRET_KEY", "change_me_to_a_random_string_in_production")
    
    # Database Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///royalrinse.db')
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///royalrinse.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Admin Credentials - Load securely from environment or strictly control access
    ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
    ADMIN_PASS = os.environ.get("ADMIN_PASS", "1234") # WARNING: DO NOT use '1234' in production!

# --- Initialisation ---
app = Flask(__name__)
app.config.from_object(Config)
db = SQLAlchemy(app)

# --- Constants & Helpers ---
DEFAULT_SLOTS = [
    "08:00", "09:00", "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00", "16:00"
]

SERVICE_PRICES = {
    "basic": 15.0,
    "deluxe": 25.0,
    "royal": 50.0
}

# --- Models ---
class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(140), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(60), nullable=False)
    service = db.Column(db.String(80), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # pending, approved, rejected, completed
    status = db.Column(db.String(30), default="pending") 
    paid = db.Column(db.Boolean, default=False)
    amount = db.Column(db.Float, default=0.0)

    def serialize(self):
        """Returns a dictionary representation of the booking for API use."""
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "email": self.email,
            "phone": self.phone,
            "service": self.service,
            "date": self.date.isoformat() if self.date else None,
            "time": self.time,
            "address": self.address,
            "notes": self.notes,
            "status": self.status,
            "paid": self.paid,
            "amount": self.amount
        }
        
    def __repr__(self):
        return f"<Booking {self.id} - {self.customer_name} on {self.date} at {self.time}>"


# --- Helper Functions ---
def available_slots_for(date_obj):
    """Returns available time slots for a given date."""
    # Only check for 'approved' bookings to prevent double-booking on confirmed slots
    bookings = Booking.query.filter_by(date=date_obj, status="approved").all()
    taken = {b.time for b in bookings}
    available = [s for s in DEFAULT_SLOTS if s not in taken]
    return available

def get_service_details():
    """Returns a list of service details with calculated prices."""
    return [
        {"id":"basic","title":"Basic Rinse","price":SERVICE_PRICES["basic"], "desc":"Exterior wash & dry"},
        {"id":"deluxe","title":"Deluxe Rinse","price":SERVICE_PRICES["deluxe"], "desc":"Exterior + interior vacuum"},
        {"id":"royal","title":"Royal Rinse","price":SERVICE_PRICES["royal"], "desc":"Full detail: wax, polish, deep interior clean"}
    ]

# --- Context Processors ---
@app.context_processor
def inject_common():
    """Injects common variables into all templates."""
    contact = {"phone": "76716978", "email": "royalrinse07@gmail.com", "location": "Mbabane, Sdwashini"}
    return {"current_year": datetime.utcnow().year, "contact": contact}

# --- Routes ---
@app.route("/")
def index():
    """Renders the homepage with service details."""
    services = get_service_details()
    return render_template("index.html", services=services)

@app.route("/book", methods=["GET", "POST"])
def book():
    """Handles the booking form submission and display."""
    if request.method == "POST":
        # 1. Get and Validate Input
        form_data = request.form
        required_fields = ["customer_name", "phone", "date", "time", "address"]
        if not all(form_data.get(f) for f in required_fields):
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("book"))

        try:
            date_obj = datetime.strptime(form_data["date"], "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for("book"))
        
        service_id = form_data.get("service") or "basic"

        # 2. Check Slot Availability
        if form_data["time"] not in available_slots_for(date_obj):
            flash("Time slot already booked. Please select another.", "warning")
            return redirect(url_for("book"))

        # 3. Process Booking
        amount = SERVICE_PRICES.get(service_id, SERVICE_PRICES["basic"])

        booking = Booking(
            customer_name=form_data["customer_name"],
            phone=form_data["phone"],
            email=form_data.get("email"),
            service=service_id,
            date=date_obj,
            time=form_data["time"],
            address=form_data["address"],
            notes=form_data.get("notes"),
            amount=amount,
        )
        db.session.add(booking)
        db.session.commit()

        session["pending_booking_id"] = booking.id
        flash("Booking created. Please complete payment to confirm.", "info")
        return redirect(url_for("payment"))

    return render_template("book.html", services=get_service_details()) # Pass services for rendering form

@app.route("/api/slots")
def api_slots():
    """API endpoint to get available slots for a given date."""
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"slots": []}), 400
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": []}), 400
        
    slots = available_slots_for(d)
    return jsonify({"slots": slots})

@app.route("/payment", methods=["GET", "POST"])
def payment():
    """Handles the payment process for a pending booking."""
    booking_id = session.get("pending_booking_id")
    if not booking_id:
        flash("No pending booking found. Please make a booking first.", "warning")
        return redirect(url_for("book"))

    booking = Booking.query.get(booking_id)
    if not booking:
        flash("Booking not found.", "danger")
        session.pop("pending_booking_id", None)
        return redirect(url_for("book"))
        
    # Redirect if already paid (in case user refreshes)
    if booking.paid:
        flash("This booking is already marked as paid.", "info")
        session.pop("pending_booking_id", None)
        return redirect(url_for("index"))

    if request.method == "POST":
        # Simplified card validation for demo purposes
        card_number = request.form.get("card_number", "").strip()
        cvv = request.form.get("cvv", "").strip()

        if len(card_number) < 12 or len(cvv) < 3:
            flash("Invalid card details (demo only).", "danger")
            return redirect(url_for("payment"))

        # In a real app, this is where you'd call a payment gateway (e.g., Stripe)
        
        booking.paid = True
        db.session.commit()

        flash("Payment successful! Await admin approval.", "success")
        session.pop("pending_booking_id", None)
        return redirect(url_for("index"))

    return render_template("payment.html", booking=booking)

@app.route("/schedule")
def schedule():
    """Displays the public schedule of approved and paid bookings for a selected date."""
    date_str = request.args.get("date")
    selected = date.today()

    if date_str:
        try:
            selected = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date parameter. Showing today's schedule.", "warning")
            # selected remains date.today()

    # Only show approved and paid bookings
    bookings = Booking.query.filter_by(
        date=selected, 
        status="approved", 
        paid=True
    ).order_by(Booking.time).all()
    
    return render_template("schedule.html", bookings=bookings, today=selected)

# --- Admin Routes ---
def admin_required(f):
    """Decorator to protect admin routes."""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            flash("Not authorized. Please log in.", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Handles admin login."""
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == app.config["ADMIN_USER"] and pw == app.config["ADMIN_PASS"]:
            session["admin"] = True
            flash("Welcome Admin.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
@admin_required
def admin_logout():
    """Logs the admin out."""
    session.pop("admin", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    """Displays all bookings for the admin."""
    # Order by date (descending) and then time (ascending)
    bookings = Booking.query.order_by(
        Booking.date.desc(), 
        Booking.time.asc()
    ).all()
    return render_template("admin.html", bookings=bookings)

@app.route("/admin/action/<int:bid>", methods=["POST"])
@admin_required
def admin_action(bid):
    """Handles admin actions (approve, reject, complete) on a booking."""
    action = request.form.get("action")
    b = Booking.query.get_or_404(bid)

    if action == "approve":
        b.status = "approved"
        db.session.commit()
        flash(f"Booking {bid} approved.", "success")

    elif action == "reject":
        b.status = "rejected"
        db.session.commit()
        flash(f"Booking {bid} rejected.", "info")

    elif action == "complete":
        b.status = "completed"
        db.session.commit()
        flash(f"Booking {bid} marked as completed.", "success")

    else:
        flash("Unknown action.", "warning")

    return redirect(url_for("admin_dashboard"))

# --- Run Application ---
if __name__ == "__main__":
    with app.app_context():
        # Creates database tables if they don't exist
        db.create_all() 
    app.run(debug=True)

