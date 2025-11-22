
# -------------------- Config --------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "royalrinse-secret")

# SQLite DB (file in project root)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///royalrinse.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Admin credentials
ADMIN_USER = "admin"
ADMIN_PASS = "1234"

db = SQLAlchemy(app)

# -------------------- Models --------------------
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
    status = db.Column(db.String(30), default="pending")  # pending, approved, rejected, completed
    paid = db.Column(db.Boolean, default=False)
    amount = db.Column(db.Float, default=0.0)

    def serialize(self):
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "email": self.email,
            "phone": self.phone,
            "service": self.service,
            "date": self.date.isoformat(),
            "time": self.time,
            "address": self.address,
            "notes": self.notes,
            "status": self.status,
            "paid": self.paid,
            "amount": self.amount
        }

# -------------------- Helpers --------------------
DEFAULT_SLOTS = [
    "08:00", "09:00", "10:00", "11:00", "12:00",
    "13:00", "14:00", "15:00", "16:00"
]

SERVICE_PRICES = {
    "basic": 15.0,
    "deluxe": 25.0,
    "royal": 50.0
}

def available_slots_for(date_obj):
    """Return available slots that are not yet approved."""
    bookings = Booking.query.filter_by(date=date_obj, status="approved").all()
    taken = [b.time for b in bookings]
    available = [s for s in DEFAULT_SLOTS if s not in taken]
    return available

# -------------------- Context --------------------
@app.context_processor
def inject_common():
    contact = {"phone": "76716978", "email": "royalrinse07@gmail.com", "location": "Mbabane, Sdwashini"}
    return {"current_year": datetime.utcnow().year, "contact": contact}

# -------------------- Routes --------------------
@app.route("/")
def index():
    services = [
        {"id":"basic","title":"Basic Rinse","price":SERVICE_PRICES["basic"], "desc":"Exterior wash & dry"},
        {"id":"deluxe","title":"Deluxe Rinse","price":SERVICE_PRICES["deluxe"], "desc":"Exterior + interior vacuum"},
        {"id":"royal","title":"Royal Rinse","price":SERVICE_PRICES["royal"], "desc":"Full detail: wax, polish, deep interior clean"}
    ]
    return render_template("index.html", services=services)

@app.route("/book", methods=["GET", "POST"])
def book():
    if request.method == "POST":
        name = request.form.get("customer_name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        service = request.form.get("service") or "basic"
        date_str = request.form.get("date")
        time_slot = request.form.get("time")
        address = request.form.get("address")
        notes = request.form.get("notes")

        if not (name and phone and date_str and time_slot and address):
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("book"))

        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for("book"))

        if time_slot not in available_slots_for(d):
            flash("Time slot already booked. Please select another.", "warning")
            return redirect(url_for("book"))

        amount = SERVICE_PRICES.get(service, SERVICE_PRICES["basic"])

        booking = Booking(
            customer_name=name,
            phone=phone,
            email=email,
            service=service,
            date=d,
            time=time_slot,
            address=address,
            notes=notes,
            amount=amount,
            paid=False,
            status="pending"
        )
        db.session.add(booking)
        db.session.commit()

        session["pending_booking_id"] = booking.id
        flash("Booking created. Please complete payment to confirm.", "info")
        return redirect(url_for("payment"))

    return render_template("book.html")

@app.route("/api/slots")
def api_slots():
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"slots": []})
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"slots": []})
    slots = available_slots_for(d)
    return jsonify({"slots": slots})

@app.route("/payment", methods=["GET", "POST"])
def payment():
    booking_id = session.get("pending_booking_id")
    if not booking_id:
        flash("No booking found. Please make a booking first.", "warning")
        return redirect(url_for("book"))

    booking = Booking.query.get(booking_id)
    if not booking:
        flash("Booking not found.", "danger")
        return redirect(url_for("book"))

    if request.method == "POST":
        card_number = request.form.get("card_number", "").strip()
        exp = request.form.get("exp", "").strip()
        cvv = request.form.get("cvv", "").strip()

        if len(card_number) < 12 or len(cvv) < 3:
            flash("Invalid card details (demo only).", "danger")
            return redirect(url_for("payment"))

        booking.paid = True
        db.session.commit()

        flash("Payment successful! Await admin approval.", "success")
        session.pop("pending_booking_id", None)
        return redirect(url_for("index"))

    return render_template("payment.html", booking=booking)

@app.route("/schedule")
def schedule():
    date_str = request.args.get("date")
    if date_str:
        try:
            selected = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            selected = date.today()
    else:
        selected = date.today()

    bookings = Booking.query.filter_by(date=selected, status="approved", paid=True).order_by(Booking.time).all()
    return render_template("schedule.html", bookings=bookings, today=selected)

# -------------------- Admin --------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session["admin"] = True
            flash("Welcome Admin.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials.", "danger")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

@app.route("/admin")
def admin_dashboard():
    if not session.get("admin"):
        return redirect(url_for("admin_login"))
...     bookings = Booking.query.order_by(
...         Booking.status.asc(), Booking.date.desc(), Booking.time
...     ).all()
...     return render_template("admin.html", bookings=bookings)
... 
... @app.route("/admin/action/<int:bid>", methods=["POST"])
... def admin_action(bid):
...     if not session.get("admin"):
...         flash("Not authorized.", "danger")
...         return redirect(url_for("admin_login"))
... 
...     action = request.form.get("action")
...     b = Booking.query.get_or_404(bid)
... 
...     if action == "approve":
...         b.status = "approved"
...         db.session.commit()
...         flash("Booking approved.", "success")
... 
...     elif action == "reject":
...         b.status = "rejected"
...         db.session.commit()
...         flash("Booking rejected.", "info")
... 
...     elif action == "complete":
...         b.status = "completed"
...         db.session.commit()
...         flash("Booking marked as completed.", "success")
... 
...     else:
...         flash("Unknown action.", "warning")
... 
...     return redirect(url_for("admin_dashboard"))
... 
... # -------------------- Run --------------------
... if __name__ == "__main__":
...     with app.app_context():
...         db.create_all()
...     app.run(debug=True)
