from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, request, render_template, url_for, session
from jinja2.ext import do
from pkg import db
from pkg.models import User, Admin, Localgovernment, State, ProductCategory, Product, Driver, Relocation, RelocationPayment , Contact 
from werkzeug.security import generate_password_hash, check_password_hash

admin = Blueprint('admin', __name__, template_folder='templates', static_folder='static', url_prefix="/admin")

@admin.route("/")
def admin_home():
    if session.get('activeadmin') == None:
        return redirect(url_for('home.home_page'))
    all_states = State.query.all()
    all_lgas = Localgovernment.query.all()
    all_users = User.query.all()
    all_products = Product.query.all()
    all_drivers = Driver.query.all()
    relocations = Relocation.query.order_by(Relocation.created_at.desc()).all()
    all_messages = Contact.query.order_by(Contact.created_at.desc()).all()

    return render_template( "/admin/admin.html", states=all_states, lgas=all_lgas, users=all_users, products=all_products, drivers=all_drivers, relocations=relocations, senders=all_messages)


@admin.route("/relocations/<int:relocation_id>/manage/", methods=["GET", "POST"])
def manage_relocation(relocation_id):
    if session.get('activeadmin') is None:
        return redirect(url_for('admin.login_admin'))

    relocation = Relocation.query.get_or_404(relocation_id)
    drivers = Driver.query.filter_by(status='active').order_by(Driver.fullname).all()
    if relocation.driver and relocation.driver.status != 'active':
        drivers.append(relocation.driver)

    statuses = ('pending', 'quoted', 'confirmed', 'in_transit', 'completed')
    if request.method == 'POST':
        if any(payment.status == 'pending' for payment in relocation.payments):
            flash('This request cannot be changed while Paystack payment is in progress.', 'error')
            return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))

        driver_id_value = request.form.get('driver_id', '').strip()
        driver = None
        if driver_id_value:
            try:
                driver_id = int(driver_id_value)
            except ValueError:
                flash('Choose a valid driver.', 'error')
                return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))

            driver = Driver.query.filter_by(id=driver_id).first()
            if driver is None or (
                driver.status != 'active' and driver.id != relocation.driver_id
            ):
                flash('Choose an active registered driver.', 'error')
                return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))

        status = request.form.get('status', '')
        if status not in statuses:
            flash('Choose a valid relocation status.', 'error')
            return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))

        try:
            price = Decimal(request.form.get('price', '').strip())
        except InvalidOperation:
            flash('Enter a valid relocation price.', 'error')
            return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))

        if not price.is_finite() or price <= 0 or price > Decimal('9999999999.99'):
            flash('Enter a price greater than zero and no more than 9,999,999,999.99.', 'error')
            return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))
        if price != price.quantize(Decimal('0.01')):
            flash('Relocation price can have at most two decimal places.', 'error')
            return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))
        if (
            any(payment.status == 'paid' for payment in relocation.payments)
            and price != relocation.estimated_cost
        ):
            flash('The relocation price cannot be changed after payment has been received.', 'error')
            return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))

        relocation.driver = driver
        relocation.estimated_cost = price
        relocation.status = status
        db.session.commit()
        flash('Relocation request updated.', 'success')
        return redirect(url_for('admin.admin_home', _anchor='relocations'))

    return render_template(
        'admin/edit_relocation.html',
        relocation=relocation,
        drivers=drivers,
        statuses=statuses,
    )


@admin.post("/relocations/<int:relocation_id>/payments/<int:payment_id>/status")
def update_relocation_payment_status(relocation_id, payment_id):
    if session.get('activeadmin') is None:
        return redirect(url_for('admin.login_admin'))

    relocation = Relocation.query.get_or_404(relocation_id)
    payment = RelocationPayment.query.filter_by(
        id=payment_id,
        relocation_id=relocation.id,
    ).first_or_404()
    new_status = request.form.get('status', '')

    if new_status not in {'paid', 'failed'}:
        flash('Choose a valid payment status.', 'error')
        return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))
    if payment.status == 'paid' and new_status != 'paid':
        flash('A confirmed payment cannot be changed.', 'error')
        return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))
    if new_status == 'paid':
        expected_amount = int(Decimal(relocation.estimated_cost) * 100)
        if (
            relocation.driver_id is None
            or relocation.status == 'cancelled'
        ):
            flash('The relocation request has been cancelled.', 'error')
            return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))
        payment.paid_at = datetime.now(timezone.utc).replace(tzinfo=None)
        relocation.status = 'confirmed'

    payment.status = new_status
    db.session.commit()
    flash('Payment status updated.', 'success')
    return redirect(url_for('admin.manage_relocation', relocation_id=relocation.id))


@admin.route("/ctrl/register/new/admin/", methods=["GET", "POST"])
def register_admin():
    if request.method == "POST":
        firstname = request.form.get("first_name")
        lastname = request.form.get("last_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_pwd")
        if firstname and lastname and email and password and confirm_password:
            if password == confirm_password:
                hashed_password = generate_password_hash(password)
                new_admin = Admin(first_name=firstname, last_name=lastname, email=email, phone=phone, password=hashed_password)
                db.session.add(new_admin)
                #db.session.flush()
                #nw_user = User(first_name=firstname, last_name=lastname, email=email, phone=phone, state_id= 0, lga_id='0', address='admin address',  hashed_password=hashed_password, role='admin')
                #db.session.add(nw_user)
                db.session.commit()
        return redirect(url_for("admin.login_admin"))
    return render_template("/admin/register.html")



@admin.route("/login/", methods=["GET", "POST"])
def login_admin():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("pwd")
        admin = Admin.query.filter_by(email=email).first()
        if admin:
            if check_password_hash(admin.password, password):
                session['activeadmin'] = admin.email
                session['activeuser_id'] = admin.id
                return redirect(url_for("admin.admin_home"))
            return redirect(url_for("admin.login_admin"))
        return redirect(url_for("admin.login_admin"))
    return render_template("/admin/login.html")

@admin.post("/user/<int:user_id>/status")
def update_user_status(user_id):
    if session.get('activeadmin') is None:
        return redirect(url_for('admin.login_admin'))

    user = User.query.get(user_id)
    if not user:
        return redirect(url_for('admin.admin_home'))

    new_status = request.form.get('status')
    if new_status not in {'active', 'inactive', 'blocked'}:
        return redirect(url_for('admin.admin_home'))

    user.status = new_status
    db.session.commit()
    return redirect(url_for('admin.admin_home'))




@admin.route("/add/category/")
def add_category():
    cat1 = ProductCategory(category='Furniture')
    cat2 = ProductCategory(category='Electronics')
    cat3 = ProductCategory(category='Appliances')
    cat4 = ProductCategory(category='Kitchen')
    cat5 = ProductCategory(category='Decor')
    cat6 = ProductCategory(category='Others')
    db.session.add(cat1)
    db.session.add(cat2)
    db.session.add(cat3)
    db.session.add(cat4)
    db.session.add(cat5)
    db.session.add(cat6)
    db.session.commit()
    return redirect(url_for('admin.admin_home'))

@admin.route("/add_driver/", methods=["GET", "POST"])
def add_driver():
    if session.get('activeadmin') == None:
        return redirect(url_for('home.home_page'))
    if request.method == "POST":
        fullname = request.form.get("d_name")
        state = request.form.get("d_state")
        lga = request.form.get("d_lga")
        address = request.form.get("d_address")
        phone = request.form.get("d_phone")
        email = request.form.get("d_email")
        licence = request.form.get("d_licence")
        vehicle = request.form.get("d_vehicle")
        plate_number = request.form.get("d_platenum")
        if not (fullname, state, lga, address, phone, email, licence, vehicle, plate_number):
            return redirect(url_for('admin.home_page'))
        driver_exist = Driver.query.filter_by(email=email).first()
        if driver_exist:
            return "<h1> Driver already exist </h1>" #redirect(url_for('admin.admin_home'))
        new_driver = Driver(fullname=fullname, d_state_id =state, d_lga_id = lga, address=address, phone=phone, email=email, licence_number=licence, vehicle=vehicle, plate_number=plate_number)
        db.session.add(new_driver)
        db.session.commit()
        return redirect(url_for('admin.admin_home'))

@admin.route("/edit_driver/<int:id>", methods=["GET", "POST"])
def edit_driver(id):
    driver = Driver.query.get_or_404(id)
    all_states = State.query.all()
    all_lgas = Localgovernment.query.all()

    if request.method == "POST":
        driver.fullname = request.form.get("fullname")
        driver.d_state_id = request.form.get("d_state_id")
        driver.d_lga_id = request.form.get("d_lga_id")
        driver.address = request.form.get("address")
        driver.phone = request.form.get("phone")
        driver.email = request.form.get("email")
        driver.status = request.form.get("status")
        driver.licence_number = request.form.get("licence_number")
        driver.vehicle = request.form.get("vehicle")
        driver.plate_number = request.form.get("plate_number")

        db.session.commit()
        return redirect(url_for('admin.admin_home'))

    return render_template("admin/edit_driver.html",  driver=driver, states=all_states, lgas=all_lgas )


@admin.route("/delete_driver/<int:id>", methods=["POST"])
def delete_driver(id):
    driver = Driver.query.get_or_404(id)
    try:
        db.session.delete(driver)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
    return redirect(url_for('admin.admin_home'))





@admin.post("/product/<int:product_id>/delete")
def delete_product(product_id):
    if session.get('activeadmin') is None:
        return redirect(url_for('admin.admin_login'))

    item_to_delete = Product.query.filter_by( id=product_id ).first_or_404()
    db.session.delete(item_to_delete)
    db.session.commit() 
    return redirect(url_for('user.home'))


@admin.route("/delete_user/<int:id>", methods=["POST"])
def delete_user(id):
    user = User.query.get_or_404(id)
    try:
        db.session.delete(user)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
    return redirect(url_for('admin.admin_home'))


@admin.route("/delete_message/<int:id>", methods=["POST"])
def delete_message(id):
    message = Contact.query.get_or_404(id)
    try:
        db.session.delete(message)
        db.session.commit()
    except Exception as error:
        db.session.rollback()
    return redirect(url_for('admin.admin_home'))
