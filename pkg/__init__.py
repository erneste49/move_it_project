import os 
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy 
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv



db = SQLAlchemy()
migrate = Migrate ()
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__, static_folder='static')
    
    load_dotenv()
    from pkg.config import DevelopmentConfig

    
    app.config.from_object(DevelopmentConfig)
    app.secret_key = os.getenv('SECRET_KEY')
    
    db.init_app(app) 
    migrate.init_app(app, db)   
    csrf.init_app(app) 

    from pkg.home.routes import home 
    from pkg.users.routes import user
    from pkg.admin.routes import admin

    
    app.register_blueprint(home)
    app.register_blueprint(user)
    app.register_blueprint(admin)
    
    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("home/404.html"), 404
    
    
    return app
app = create_app()
