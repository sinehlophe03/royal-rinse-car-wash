# app.py

import os
from datetime import datetime, date
from functools import wraps # Needed for the admin_required decorator

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

# --- Configuration Class ---
class Config:
    """Application configuration settings."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "royalrinse-secret")
    
    # Get DB URL and correct the prefix for SQLAlchemy if needed
    DB_URL = os.environ.get('DATABASE_URL')
    if DB_URL and DB_URL.startswith("postgres://"):
        DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = DB_URL or 'sqlite:///royalrinse.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Admin Credentials - Load securely from environment
    ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
    ADMIN_PASS = os.environ.get("ADMIN_PASS", "1234")

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
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False) # NOTE: Passwords should be hashed in a real app

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(140), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # ForeignKey restored
    email = db.Column(db.String(200))
    phone = db.Column(db.String(60), nullable=False)
    service = db.Column(db.String(80), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(30), default="pending")  # pending, approved, rejected, completed
    paid = db.Column(db.Boolean, default=False)
    amount = db.Column(db.Float, default=0.0)
    technician = db.Column(db.String(80), nullable=True) # Technician column restored

    def serialize(self):
        # ... (serialization logic unchanged) ...
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
    bookings = Booking.query.filter_by(date=date_obj, status="approved").all()
    taken = {b.time for b in bookings}
    return [s for s in DEFAULT_SLOTS if s not in taken]

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
    contact = {"phone": "76716978", "email": "royalrinse07@gmail.com", "location": "Mbabane, Sdwashini"}
    return {"current_year": datetime.utcnow().year, "contact": contact}

# --- Decorators ---
def admin_required(f):
    """Decorator to protect admin routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin"):
            flash("Not authorized. Please log in.", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

# Index Route
@app.route("/")
def index():
    services = get_service_details()
    return render_template("index.html", services=services)

# User Routes: Register / Login / Logout (Restored from original logic)
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        if not (fullname and email and password):
            flash('Please fill all fields', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'warning')
            return redirect(url_for('register'))
        # NOTE: Passwords should be hashed here (e.g., using Flask-Bcrypt)
        u = User(fullname=fullname, email=email, password=password)
        db.session.add(u); db.session.commit()
        flash('Account created, please login', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Check for Admin login
        if email == app.config['ADMIN_USER'] and password == app.config['ADMIN_PASS']:
            session['admin'] = True
            flash('Admin logged in', 'success')
            return redirect(url_for('admin_dashboard'))
        
        # Check for Regular User login
        user = User.query.filter_by(email=email, password=password).first()
        if user:
            session['user_id'] = user.id
            session['fullname'] = user.fullname
            flash('Logged in', 'success')
            return redirect(url_for('index'))
            
        flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('index'))

@app.route("/book", methods=["GET", "POST"])
def book():
    if 'user_id' not in session:
        flash('Please login to book', 'warning')
        return redirect(url_for('login'))
    # ... (rest of the book route logic is unchanged) ...
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
            user_id=session.get('user_id'), # Link booking to logged-in user
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

    return render_template("book.html", services=get_service_details())

# ... (api_slots, payment, schedule routes are unchanged) ...

@app.route('/my_bookings')
def my_bookings():
    if 'user_id' not in session:
        flash('Please login', 'warning'); return redirect(url_for('login'))
    bookings = Booking.query.filter_by(user_id=session['user_id']).order_by(Booking.date.desc(), Booking.time).all()
    return render_template('my_bookings.html', bookings=bookings)

# Admin Routes
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    # Admin login logic is already included in the /login route, but keeping this separate route 
    # to render the dedicated admin_login.html template.
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
    session.pop("admin", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin_dashboard():
    today = date.today()
    total_today = Booking.query.filter_by(date=today).count()
    approved_today = Booking.query.filter_by(date=today, status='approved').count()
    pending = Booking.query.filter_by(status='pending').count()
    revenue_today = sum([b.amount for b in Booking.query.filter_by(date=today, paid=True).all()])
    
    bookings = Booking.query.order_by(
        Booking.status.asc(), 
        Booking.date.desc(), 
        Booking.time.asc()
    ).all()
    return render_template('admin.html', bookings=bookings, total_today=total_today, approved_today=approved_today, pending=pending, revenue_today=revenue_today)

@app.route("/admin/action/<int:bid>", methods=["POST"])
@admin_required
def admin_action(bid):
    action = request.form.get("action")
    tech = request.form.get("technician") # Technician field restored
    b = Booking.query.get_or_404(bid)

    if action == "approve":
        b.status = "approved"
        if tech:
            b.technician = tech
        db.session.commit()
        flash(f"Booking {bid} approved and assigned to {b.technician or 'N/A'}.", "success")
    # ... (reject/complete logic is unchanged) ...
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
        # Creates database tables ONLY for local development with SQLite
        db.create_all() 
    app.run(debug=True)
