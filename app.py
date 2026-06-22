import os
import json
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'agri_rental_2050_secure_key' 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    contact_info = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False) # 'farmer', 'owner', 'admin', 'courier'
    is_blocked = db.Column(db.Boolean, default=False)

class Equipment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    price_per_day = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    image_file = db.Column(db.String(100), nullable=False, default='default.jpg')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    owner = db.relationship('User', foreign_keys=[owner_id], backref='equipments')
    images = db.relationship('EquipmentImage', backref='equipment', cascade="all, delete-orphan")

class EquipmentImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    image_file = db.Column(db.String(100), nullable=False)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.Integer, db.ForeignKey('equipment.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending') 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    equipment = db.relationship('Equipment', backref='bookings')
    farmer = db.relationship('User', foreign_keys=[farmer_id], backref='bookings')

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=False) 
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=1)
    description = db.Column(db.Text)
    image_file = db.Column(db.String(100), default='product_default.jpg')
    owner = db.relationship('User', foreign_keys=[owner_id], backref='products')

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    qty = db.Column(db.Integer, default=1)
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    courier_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) 
    full_name = db.Column(db.String(100), nullable=False) 
    phone = db.Column(db.String(20), nullable=False)      
    address = db.Column(db.String(200), nullable=False)
    lat = db.Column(db.Float, nullable=True)
    lng = db.Column(db.Float, nullable=True)
    total_amount = db.Column(db.Float, nullable=False)
    
    status = db.Column(db.String(50), default='Processing')
    order_status = db.Column(db.String(50), default='Placed') 
    payment_status = db.Column(db.String(50), default='Pending') 
    delivery_otp = db.Column(db.String(4), nullable=True)
    tracking_history = db.Column(db.Text, nullable=True) 
    date_ordered = db.Column(db.DateTime, default=datetime.utcnow)
    estimated_delivery = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    
    farmer = db.relationship('User', foreign_keys=[farmer_id], backref='orders')
    courier = db.relationship('User', foreign_keys=[courier_id], backref='deliveries')
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer, nullable=False)
    price_at_purchase = db.Column(db.Float, nullable=False)
    product = db.relationship('Product')

class SupportTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), default='Open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref='tickets')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- HELPER LOGIC ---
def log_tracking(order, status_msg):
    history = []
    if order.tracking_history:
        history = json.loads(order.tracking_history)
    history.append({
        "status": status_msg,
        "time": datetime.utcnow().strftime("%d %b %Y, %H:%M")
    })
    order.tracking_history = json.dumps(history)
    order.order_status = status_msg


# --- AUTH ROUTES ---
@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if User.query.filter_by(email=request.form.get('email')).first():
            flash('Email already exists.', 'danger')
            return redirect(url_for('register'))
        
        hashed_pw = generate_password_hash(request.form.get('password'))
        user = User(
            username=request.form.get('username'), 
            email=request.form.get('email'), 
            contact_info=request.form.get('contact_info'), 
            password=hashed_pw, 
            role=request.form.get('role')
        )
        db.session.add(user)
        db.session.commit()
        flash('Network Identity created successfully! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            if user.is_blocked:
                flash('Your account has been blocked by Admin.', 'danger')
                return redirect(url_for('login'))
            login_user(user)
            if user.role == 'admin': return redirect(url_for('admin_dashboard'))
            if user.role == 'owner': return redirect(url_for('owner_dashboard'))
            if user.role == 'courier': return redirect(url_for('courier_dashboard'))
            return redirect(url_for('farmer_dashboard'))
        flash('Invalid credentials. Please verify your email and password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

# --- COURIER AUTHENTICATION (ZERO DB CHANGES) ---
# --- COURIER AUTHENTICATION (ZERO DB CHANGES) ---
@app.route('/courier_register', methods=['GET', 'POST'])
def courier_register():
    if request.method == 'POST':
        delivery_id = request.form.get('delivery_id')
        
        # Check email column as we map Delivery ID to it
        if User.query.filter_by(email=delivery_id).first():
            flash('Delivery ID is already registered.', 'danger')
            return redirect(url_for('courier_register'))
        
        hashed_pw = generate_password_hash(request.form.get('password'))
        name = request.form.get('name')
        phone = request.form.get('phone')
        
        # We append the phone number to the username so it is safely stored
        user = User(
            username=f"{name} ({phone}) [{delivery_id}]", 
            email=delivery_id,                   
            contact_info=request.form.get('location').lower(), 
            password=hashed_pw, 
            role='courier'
        )
        db.session.add(user)
        db.session.commit()
        flash('Courier Profile activated. Please login.', 'success')
        return redirect(url_for('courier_login'))
    return render_template('courier_register.html')

@app.route('/courier_login', methods=['GET', 'POST'])
def courier_login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('delivery_id'), role='courier').first()
        if user and check_password_hash(user.password, request.form.get('password')):
            if user.is_blocked:
                flash('Your account is restricted by Administration.', 'danger')
                return redirect(url_for('courier_login'))
            login_user(user)
            return redirect(url_for('courier_dashboard'))
        flash('Invalid Delivery ID or Password.', 'danger')
    return render_template('courier_login.html')


# --- DASHBOARD & SUPPORT ROUTES ---
@app.route('/farmer/dashboard')
@login_required
def farmer_dashboard():
    if current_user.role != 'farmer': return redirect(url_for('index'))
    equipments = Equipment.query.all()
    locations = sorted(list(set(eq.location for eq in equipments)))
    bookings = Booking.query.filter_by(farmer_id=current_user.id).order_by(Booking.created_at.desc()).all()
    orders = Order.query.filter_by(farmer_id=current_user.id).order_by(Order.date_ordered.desc()).limit(5).all()
    return render_template('farmer_dashboard.html', equipments=equipments, bookings=bookings, orders=orders, locations=locations)

@app.route('/seasonal_crop')
@login_required
def seasonal_crop():
    """Renders the 12-Month Agro-Climatic Matrix"""
    return render_template('Seasonal_Crop.html')

@app.route('/equipment_status')
@login_required
def equipment_status():
    if current_user.role != 'farmer': 
        return redirect(url_for('index'))
    bookings = Booking.query.filter_by(farmer_id=current_user.id).order_by(Booking.created_at.desc()).all()
    return render_template('equipment_status.html', bookings=bookings)

@app.route('/my_orders')
@login_required
def my_orders():
    if current_user.role != 'farmer': return redirect(url_for('index'))
    orders = Order.query.filter_by(farmer_id=current_user.id).order_by(Order.date_ordered.desc()).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/owner/dashboard')
@login_required
def owner_dashboard():
    if current_user.role != 'owner': return redirect(url_for('index'))
    my_eq = Equipment.query.filter_by(owner_id=current_user.id).all()
    eq_ids = [e.id for e in my_eq]
    requests = Booking.query.filter(Booking.equipment_id.in_(eq_ids)).order_by(Booking.created_at.desc()).all()
    products = Product.query.filter_by(owner_id=current_user.id).all()
    prod_ids = [p.id for p in products]
    sold_items = OrderItem.query.filter(OrderItem.product_id.in_(prod_ids)).all()
    total_rev = sum(b.total_price for b in requests if b.status == 'Completed') + sum(i.quantity * i.price_at_purchase for i in sold_items)
    return render_template('owner_dashboard.html', equipments=my_eq, products=products, requests=requests, total_revenue=total_rev, sold_items=sold_items)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin': return redirect(url_for('index'))
    users = User.query.all()
    equipments = Equipment.query.all()
    bookings = Booking.query.all()
    tickets = SupportTicket.query.order_by(SupportTicket.created_at.desc()).all()
    total_revenue = sum(b.total_price for b in bookings if b.status == 'Completed')
    return render_template('admin_dashboard.html', users=users, equipments=equipments, bookings=bookings, tickets=tickets, total_revenue=total_revenue)

@app.route('/admin/ticket/update/<int:ticket_id>/<status>')
@login_required
def update_ticket_status(ticket_id, status):
    if current_user.role != 'admin': return "Unauthorized", 403
    ticket = SupportTicket.query.get_or_404(ticket_id)
    if status in ['Open', 'Investigating', 'Resolved']:
        ticket.status = status
        db.session.commit()
        flash(f'Transmission #{ticket.id} status updated to {status}.', 'success')
    return redirect(request.referrer)

@app.route('/support', methods=['GET', 'POST'])
@login_required
def support():
    if request.method == 'POST':
        new_ticket = SupportTicket(
            user_id=current_user.id,
            subject=request.form.get('subject'),
            category=request.form.get('category'),
            description=request.form.get('description')
        )
        db.session.add(new_ticket)
        db.session.commit()
        flash('Support transmission sent to Mainframe. An operative will review it.', 'success')
        return redirect(url_for('support'))
    my_tickets = SupportTicket.query.filter_by(user_id=current_user.id).order_by(SupportTicket.created_at.desc()).all()
    return render_template('support.html', tickets=my_tickets)

@app.route('/courier/dashboard')
@login_required
def courier_dashboard():
    if current_user.role != 'courier': return redirect(url_for('index'))
    my_deliveries = Order.query.filter_by(courier_id=current_user.id).order_by(Order.date_ordered.desc()).all()
    delivered_count = len([d for d in my_deliveries if d.status == 'Delivered'])
    earnings = delivered_count * 50
    courier_loc = current_user.contact_info 
    available_orders = Order.query.filter(
        Order.courier_id == None, 
        Order.order_status == 'Ready for Shipment',
        Order.address.ilike(f'%{courier_loc}%')
    ).all()
    return render_template('courier_dashboard.html', deliveries=my_deliveries, available_orders=available_orders, earnings=earnings, location=courier_loc)

# --- EQUIPMENT RENTAL LOGIC ---
@app.route('/equipment/add', methods=['POST'])
@login_required
def add_equipment():
    if current_user.role != 'owner': return "Unauthorized", 403
    name = request.form.get('name')
    category = request.form.get('category')
    price = float(request.form.get('price'))
    desc = request.form.get('description')
    location = request.form.get('location')
    
    primary_img = request.files.get('primary_image')
    primary_filename = 'default.jpg'
    if primary_img and primary_img.filename != '':
        primary_filename = secure_filename(primary_img.filename)
        primary_img.save(os.path.join(app.config['UPLOAD_FOLDER'], primary_filename))

    new_eq = Equipment(owner_id=current_user.id, name=name, category=category, price_per_day=price, description=desc, location=location, image_file=primary_filename)
    db.session.add(new_eq)
    db.session.flush() 
    
    for opt in ['opt_image_1', 'opt_image_2', 'opt_image_3']:
        opt_img = request.files.get(opt)
        if opt_img and opt_img.filename != '':
            fname = secure_filename(opt_img.filename)
            opt_img.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            db.session.add(EquipmentImage(equipment_id=new_eq.id, image_file=fname))
            
    db.session.commit()
    flash('Equipment Listed Successfully!', 'success')
    return redirect(url_for('owner_dashboard'))

@app.route('/equipment/edit/<int:id>', methods=['POST'])
@login_required
def edit_equipment(id):
    eq = Equipment.query.get_or_404(id)
    if eq.owner_id != current_user.id: return "Unauthorized", 403
    eq.name = request.form.get('name')
    eq.category = request.form.get('category')
    eq.price_per_day = float(request.form.get('price'))
    eq.location = request.form.get('location')
    eq.description = request.form.get('description')
    
    primary_img = request.files.get('primary_image')
    if primary_img and primary_img.filename != '':
        primary_filename = secure_filename(primary_img.filename)
        primary_img.save(os.path.join(app.config['UPLOAD_FOLDER'], primary_filename))
        eq.image_file = primary_filename
        
    opt_imgs = [request.files.get(opt) for opt in ['opt_image_1', 'opt_image_2', 'opt_image_3']]
    valid_opts = [img for img in opt_imgs if img and img.filename != '']
    if valid_opts:
        EquipmentImage.query.filter_by(equipment_id=eq.id).delete()
        for img in valid_opts:
            fname = secure_filename(img.filename)
            img.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
            db.session.add(EquipmentImage(equipment_id=eq.id, image_file=fname))

    db.session.commit()
    flash('Equipment updated successfully', 'success')
    return redirect(url_for('owner_dashboard'))

@app.route('/equipment/delete/<int:id>')
@login_required
def delete_equipment(id):
    eq = Equipment.query.get_or_404(id)
    if eq.owner_id != current_user.id: return "Unauthorized", 403
    if Booking.query.filter_by(equipment_id=id, status='Approved').first():
        flash('Cannot delete active equipment', 'danger')
        return redirect(url_for('owner_dashboard'))
    
    db.session.delete(eq)
    db.session.commit()
    flash('Equipment deleted.', 'info')
    return redirect(url_for('owner_dashboard'))

@app.route('/booking/create', methods=['POST'])
@login_required
def book_equipment():
    start = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d')
    end = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d')
    eq_id = request.form.get('equipment_id')
    eq = Equipment.query.get(eq_id)
    
    days = (end - start).days
    if days < 1: days = 1
    
    overlap = Booking.query.filter_by(equipment_id=eq_id).filter(
        Booking.status.in_(['Pending', 'Approved']),
        Booking.end_date >= start,
        Booking.start_date <= end
    ).first()

    if overlap:
        flash('Equipment is already booked for these dates.', 'danger')
        return redirect(url_for('farmer_dashboard'))

    booking = Booking(equipment_id=eq.id, farmer_id=current_user.id, start_date=start, end_date=end, total_price=days*eq.price_per_day)
    db.session.add(booking)
    db.session.commit()
    flash('Booking Request Sent!', 'success')
    return redirect(url_for('farmer_dashboard'))

@app.route('/booking/update/<int:booking_id>/<status>')
@login_required
def update_booking(booking_id, status):
    b = Booking.query.get_or_404(booking_id)
    if b.equipment.owner_id != current_user.id and current_user.role != 'admin':
        return "Unauthorized", 403
        
    if status in ['Approved', 'Rejected', 'Completed']:
        b.status = status
        db.session.commit()
        flash(f'Booking marked as {status}.', 'success')
    return redirect(request.referrer)

# --- E-COMMERCE (SHOP) LOGIC ---
@app.route('/shop')
@login_required
def shop():
    products = Product.query.filter(Product.stock > 0).all()
    return render_template('shop.html', products=products)

@app.route('/product/add', methods=['POST'])
@login_required
def add_product():
    if current_user.role != 'owner': return "Unauthorized", 403
    img = request.files.get('image')
    filename = secure_filename(img.filename) if img and img.filename != '' else 'product_default.jpg'
    if img and img.filename != '': 
        img.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
    prod = Product(owner_id=current_user.id, name=request.form.get('name'), category=request.form.get('category'),
                   price=float(request.form.get('price')), stock=int(request.form.get('stock')),
                   description=request.form.get('description'), image_file=filename)
    db.session.add(prod)
    db.session.commit()
    flash('Product Listed!', 'success')
    return redirect(url_for('owner_dashboard'))

@app.route('/cart/add/<int:id>', methods=['GET', 'POST'])
@login_required
def add_to_cart(id):
    product = Product.query.get_or_404(id)
    qty = int(request.form.get('qty', 1)) if request.method == 'POST' else 1
    
    if product.stock < qty:
        flash('Insufficient stock available.', 'danger')
        return redirect(url_for('shop'))
        
    existing_item = CartItem.query.filter_by(user_id=current_user.id, product_id=id).first()
    
    if existing_item:
        if existing_item.qty + qty > product.stock:
            flash('Cannot exceed maximum available stock.', 'danger')
        else:
            existing_item.qty += qty
            db.session.commit()
            flash('Payload updated.', 'success')
    else:
        new_item = CartItem(user_id=current_user.id, product_id=id, qty=qty)
        db.session.add(new_item)
        db.session.commit()
        flash('Added to payload.', 'success')
        
    return redirect(url_for('view_cart'))

@app.route('/cart')
@login_required
def view_cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.product.price * item.qty for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total=total)

@app.route('/cart/update/<int:id>', methods=['POST'])
@login_required
def update_cart(id):
    action = request.form.get('action')
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=id).first()
    if cart_item:
        if action == 'increase' and cart_item.qty < cart_item.product.stock:
            cart_item.qty += 1
        elif action == 'decrease':
            cart_item.qty -= 1
            if cart_item.qty <= 0:
                db.session.delete(cart_item)
        db.session.commit()
    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<int:id>')
@login_required
def remove_from_cart(id):
    cart_item = CartItem.query.filter_by(user_id=current_user.id, product_id=id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        flash('Item purged from payload.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Your payload is empty.', 'warning')
        return redirect(url_for('shop'))
    total = sum(item.product.price * item.qty for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total=total)

@app.route('/process_checkout', methods=['POST'])
@login_required
def process_checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items: return redirect(url_for('shop'))
    total_amount = sum(item.product.price * item.qty for item in cart_items)
    
    order_lat = 11.6643 + random.uniform(-0.1, 0.1)
    order_lng = 78.1460 + random.uniform(-0.1, 0.1)
    otp_code = str(random.randint(1000, 9999))
    eta = datetime.utcnow() + timedelta(days=2) 
    
    new_order = Order(
        farmer_id=current_user.id, full_name=request.form.get('full_name'),
        phone=request.form.get('phone'), address=request.form.get('address'),
        total_amount=total_amount, lat=order_lat, lng=order_lng,
        payment_status='Completed', delivery_otp=otp_code, estimated_delivery=eta
    )
    
    log_tracking(new_order, "Placed")
    db.session.add(new_order)
    db.session.flush() 
    
    for item in cart_items:
        if item.product.stock < item.qty:
            db.session.rollback()
            flash(f'Stock anomaly for {item.product.name}.', 'danger')
            return redirect(url_for('view_cart'))
            
        db.session.add(OrderItem(order_id=new_order.id, product_id=item.product_id, quantity=item.qty, price_at_purchase=item.product.price))
        item.product.stock -= item.qty
        db.session.delete(item)
        
    db.session.commit()
    return redirect(url_for('order_success', order_id=new_order.id))

@app.route('/order_success/<int:order_id>')
@login_required
def order_success(order_id):
    order = Order.query.filter_by(id=order_id, farmer_id=current_user.id).first_or_404()
    return render_template('order_success.html', order=order)

# --- TRACKING & COURIER LOGIC ---
@app.route('/order/<int:order_id>/tracking')
@login_required
def order_tracking(order_id):
    order = Order.query.get_or_404(order_id)
    if order.farmer_id != current_user.id and current_user.role not in ['admin', 'owner', 'courier']:
        return "Unauthorized", 403
    history = json.loads(order.tracking_history) if order.tracking_history else []
    return render_template('tracking.html', order=order, history=history)

@app.route('/order/update/<int:order_id>/<status>')
@login_required
def update_order_status(order_id, status):
    order = Order.query.get_or_404(order_id)
    has_permission = False
    if current_user.role == 'admin': has_permission = True
    elif current_user.role == 'owner':
        for item in order.items:
            if item.product.owner_id == current_user.id:
                has_permission = True
                break
    if not has_permission: return "Unauthorized", 403

    valid_statuses = ['Confirmed', 'Packed', 'Ready for Shipment', 'Dispatched']
    if status in valid_statuses:
        log_tracking(order, status)
        if status == 'Dispatched' or status == 'Ready for Shipment':
            order.status = 'Dispatched'
            order.order_status = 'Ready for Shipment'
        db.session.commit()
        flash(f'Order marked as {status}', 'success')
    return redirect(request.referrer)

@app.route('/product/restock/<int:product_id>', methods=['POST'])
@login_required
def restock_product(product_id):
    product = Product.query.get_or_404(product_id)
    if product.owner_id != current_user.id: return "Unauthorized", 403
    added_qty = int(request.form.get('added_stock', 0))
    if added_qty > 0:
        product.stock += added_qty
        db.session.commit()
        flash(f'Inventory replenished. New stock: {product.stock}', 'success')
    return redirect(request.referrer)

@app.route('/api/orders/nearby')
@login_required
def get_nearby_orders():
    if current_user.role != 'courier': return jsonify({'error': 'Unauthorized'}), 403
    available_orders = Order.query.filter(Order.courier_id == None, Order.order_status == 'Ready for Shipment').all()
    return jsonify([{'id': o.id, 'address': o.address, 'lat': o.lat, 'lng': o.lng} for o in available_orders])

@app.route('/order/assign/<int:order_id>', methods=['POST'])
@login_required
def assign_order(order_id):
    if current_user.role != 'courier': return "Unauthorized", 403
    order = Order.query.get_or_404(order_id)
    if order.courier_id is None:
        order.courier_id = current_user.id
        log_tracking(order, 'Out for Delivery')
        order.status = 'In Transit' 
        db.session.commit()
        flash('Logistics target acquired.', 'success')
    return redirect(url_for('courier_dashboard'))

@app.route('/api/verify_delivery/<int:order_id>', methods=['POST'])
@login_required
def verify_delivery(order_id):
    if current_user.role != 'courier': return "Unauthorized", 403
    order = Order.query.get_or_404(order_id)
    otp_attempt = request.form.get('otp')
    if otp_attempt == order.delivery_otp:
        log_tracking(order, 'Delivered')
        order.status = 'Delivered' 
        order.delivered_at = datetime.utcnow()
        db.session.commit()
        flash('OTP Verified! Delivery successful.', 'success')
    else:
        flash('Invalid OTP. Do not handover the payload.', 'danger')
    return redirect(request.referrer)

@app.route('/order/request_return/<int:order_id>')
@login_required
def request_return(order_id):
    order = Order.query.filter_by(id=order_id, farmer_id=current_user.id).first_or_404()
    if order.order_status == 'Delivered':
        log_tracking(order, 'Return Requested')
        db.session.commit()
        flash('Return Request transmitted to Mainframe.', 'info')
    return redirect(request.referrer)

# --- API & UTILS ---
@app.route('/admin/user/toggle/<int:user_id>')
@login_required
def toggle_user(user_id):
    if current_user.role != 'admin': return "Unauthorized", 403
    u = User.query.get(user_id); u.is_blocked = not u.is_blocked; db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/api/owner/calendar')
@login_required
def get_calendar_data():
    if current_user.role != 'owner': return jsonify([])
    my_equipments = Equipment.query.filter_by(owner_id=current_user.id).all()
    eq_ids = [e.id for e in my_equipments]
    bookings = Booking.query.filter(Booking.equipment_id.in_(eq_ids)).all()
    events = []
    for b in bookings:
        color = '#ff9800' 
        if b.status == 'Approved': color = '#2196f3' 
        if b.status == 'Completed': color = '#4caf50' 
        if b.status == 'Rejected': color = '#f44336' 
        events.append({'title': f"{b.equipment.name} ({b.status})", 'start': b.start_date.strftime('%Y-%m-%d'), 'end': b.end_date.strftime('%Y-%m-%d'), 'color': color})
    return jsonify(events)

@app.route('/api/equipment/<int:id>/availability')
def get_availability(id):
    bookings = Booking.query.filter_by(equipment_id=id).filter(Booking.status.in_(['Pending', 'Approved'])).all()
    return jsonify([{'from': b.start_date.strftime('%Y-%m-%d'), 'to': b.end_date.strftime('%Y-%m-%d')} for b in bookings])

@app.route('/api/iot/<int:booking_id>')
@login_required
def get_iot_data(booking_id):
    return jsonify({
        'battery': random.randint(45, 100),
        'gps': f"{random.uniform(10.5, 11.5):.4f}° N, {random.uniform(76.5, 77.5):.4f}° E",
        'status': random.choice(['Active', 'Autonomous Mode', 'Scanning Field', 'Idle']),
        'efficiency': random.randint(85, 99)
    })

if __name__ == '__main__':
    with app.app_context():
        # IMPORTANT: If you get an "OperationalError" (no such column), 
        # stop the server, delete your "database.db" file, and restart.
        db.create_all()
        
        if not User.query.filter_by(role='admin').first():
            db.session.add(User(username='Admin', email='admin@agri.com', contact_info='0000000000', password=generate_password_hash('admin123'), role='admin'))
            db.session.commit()
    app.run(debug=True)