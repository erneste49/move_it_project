from datetime import datetime

from flask import Blueprint, flash, render_template, request, redirect, url_for, session, jsonify
from pkg.models import Product, User, State, Localgovernment, Relocation, Contact , ProductCategory
from pkg import db
from werkzeug.security import generate_password_hash, check_password_hash


import secrets


home = Blueprint('home', __name__, template_folder='templates')

@home.route("/login/", methods=["GET", "POST"])
def login():
    if request.method =="POST":
        email = request.form.get('email')
        password = request.form.get('pwd')
        if email == None and password == None:
            return redirect(url_for('home.login'))
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.hashed_password, password) and user.status == 'active':
            session['activeuser'] = user.email
            session['activeuser_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('user.home'))
        else:
            if user and not check_password_hash(user.hashed_password, password):
                flash('Invalid email or password. Please try again.', 'error')
            else:
                flash('Account has been suspended by Admin. Please contact Admin.', 'error')
        return redirect(url_for('home.login'))

    return render_template('/home/login.html')


@home.route("/register/", methods=["GET", "POST"])
def register_user():
    states = State.query.all()
    
    if request.method == "POST":
        fname = request.form.get('first_name')
        lname = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        state = request.form.get('state')
        lga = request.form.get('lga')
        address = request.form.get('address')
        user_password = request.form.get('password')
        confirm_pwd = request.form.get('confirm_pwd')

        if fname == None or lname == None or email == None or phone == None or state == None or lga == None or address == None or user_password == None or confirm_pwd == None:
            return redirect(url_for('home.register_user'))

        selected_lga = Localgovernment.query.filter_by(lga_id=lga, state_id=state).first()
        if selected_lga is None:
            return redirect(url_for('home.register_user'))

        user_exist = User.query.filter_by(email=email).first()
        if user_exist:
            return "<h1> User record already exist </h1>"

        if user_password != confirm_pwd:
            return redirect(url_for('home.register_user'))
        hashed_password = generate_password_hash(user_password)


        new_user = User( first_name=fname, last_name=lname, email=email, phone=phone, state_id=state, lga_id=lga,  address=address,  hashed_password=hashed_password, )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('home.login')) 

    return render_template("home/register.html", states=states)


@home.post("/logout/")
def logout():
    if session.get('activeuser'):
        session.pop('activeuser')
        session.clear()
        return redirect(url_for('home.login'))
    return redirect(url_for('home.login'))

@home.route("/get_lga/<int:state_id>")
def get_lga(state_id):
    lgas = Localgovernment.query.filter_by(state_id=state_id).order_by(Localgovernment.lga_name).all()
    return jsonify([{'id':lga.lga_id, 'name' : lga.lga_name} for lga in lgas])


@home.route("/")
def home_page():
    all_products = Product.query.all()
    if session.get('activeuser_id'):
        return render_template('home/home.html', products=all_products)

    return render_template("home/index.html", products=all_products)

@home.route("/relocate/", methods=["GET", "POST"])
def relocate():
    if session.get('activeuser_id') is None:
        return redirect(url_for('home.register_new_user'))
    user_email = session.get('activeuser')
    user = User.query.filter_by(email=user_email).first()

    if request.method == "POST":
        current_state_id = request.form.get('r_from_state', type=int)
        current_lga_id = request.form.get('r_from_lga', type=int)
        new_state_id = request.form.get('r_to_state', type=int)
        new_lga_id = request.form.get('r_to_lga', type=int)
        current_address = request.form.get('r_from', '').strip()
        new_address = request.form.get('r_to', '').strip()
        scheduled_date_value = request.form.get('r_date', '')
        items_and_properties = request.form.get('r_notes', '').strip()

        if not all(( current_state_id, current_lga_id, new_state_id, new_lga_id, current_address, new_address, scheduled_date_value, )):
            flash('Please complete all required relocation details.', 'error')
            return redirect(url_for('home.relocate'))

        current_lga = Localgovernment.query.filter_by( lga_id=current_lga_id, state_id=current_state_id, ).first()
        new_lga = Localgovernment.query.filter_by( lga_id=new_lga_id, state_id=new_state_id,).first()
        if current_lga is None or new_lga is None:
            flash('Choose a local government that belongs to the selected state.', 'error')
            return redirect(url_for('home.relocate'))

        try:
            scheduled_date = datetime.strptime(scheduled_date_value, '%Y-%m-%d')
        except ValueError:
            flash('Enter a valid preferred move date.', 'error')
            return redirect(url_for('home.relocate'))

        relocation = Relocation( user_id=user.id, current_state_id=current_state_id, current_lga_id=current_lga_id, current_address=current_address, new_state_id=new_state_id, new_lga_id=new_lga_id, new_address=new_address, scheduled_date=scheduled_date, items_and_properties=items_and_properties,)
        db.session.add(relocation)
        db.session.commit()
        flash('Your relocation request has been submitted.', 'success')
        return redirect(url_for('home.relocate'))

    states = State.query.order_by(State.state_name).all()
    return render_template("home/relocate.html", states=states)


@home.route("/shop/")
def shop():
    search_word = request.args.get('q', '').strip()
    all_products = Product.query.all()
    searchedProducts = Product.query.filter( (Product.name.contains(search_word)) | (Product.description.contains(search_word)) | ProductCategory.category.contains(search_word) ).all() 
    return render_template('home/shop.html', products=all_products )


@home.route("/register_new/", methods=["GET", "POST"])
def register_new_user():
    states = State.query.all()

    if request.method == "POST":
        fname = request.form.get('first_name')
        lname = request.form.get('last_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        state = request.form.get('state')
        lga = request.form.get('lga')
        address = request.form.get('address')
        user_password = request.form.get('password')
        confirm_pwd = request.form.get('confirm_pwd')

        if fname == None or lname == None or email == None or phone == None or state == None or lga == None or address == None or user_password == None or confirm_pwd == None:
            return redirect(url_for('home.register_user'))
        
        selected_lga = Localgovernment.query.filter_by(lga_id=lga, state_id=state).first()
        if selected_lga is None:
            return redirect(url_for('home.register_user'))

        user_exist = User.query.filter_by(email=email).first()
        if user_exist:
            return "<h1> User record already exist </h1>"

        if user_password != confirm_pwd:
            return redirect(url_for('home.register_user'))
        hashed_password = generate_password_hash(user_password)

        new_user = User(first_name=fname, last_name=lname, email=email, phone=phone, state_id=state, lga_id=lga,
                        address=address, hashed_password=hashed_password, )
        db.session.add(new_user)
        db.session.commit()
        session['activeuser'] = new_user.email
        session['activeuser_id'] = new_user.id
        return redirect(url_for('home.relocate'))

    return render_template("home/relocate_register.html", states=states)


@home.route("/contact_us/", methods=["GET", "POST"])
def contact_us():
    if session.get('activeuser_id') or session.get('activuser_id') or session.get('activeuser_id') is None:
        all_products = Product.query.all()
        if request.method == "POST":
            msg_email = request.form.get('contact_email')
            msg_subject = request.form.get('contact_subject')
            msg_message = request.form.get('contact_message')

            if not msg_email or not msg_message:
                flash('Please provide both your email and message.', 'error')
                return redirect(url_for('home.contact_us'))
            new_message = Contact(email=msg_email, subject=msg_subject, message=msg_message)
            db.session.add(new_message)
            db.session.commit()

            flash('Thank you for reaching out! A member of our team will get in touch with you soon.', 'success')
            return redirect(url_for("home.home_page",  _anchor="contactUs"))
        
    return redirect (url_for("home.home_page",  _anchor="contactUs"))


@home.route("/search/")
def search_word():
    search_word = request.args.get('q', '').strip() 
    if search_word:
        flash(f'Results found for "{search_word}".', 'success')
        searchedProducts = Product.query.filter( (Product.name.contains(search_word)) | (ProductCategory.category.contains(search_word)) | (Product.description.contains(search_word)) ).all()
    elif search_word == "":
        flash('Please enter a search word.', 'error')
        return redirect(url_for('home.shop'))
    else:
        searchedProducts = []  
    return render_template("home/shop.html", products=searchedProducts, search_word=search_word)



@home.errorhandler(404)
def page_not_found(error):
    return render_template("home/404.html") 













