from flask import Flask
from flask_bcrypt import Bcrypt
from models import db, set_login_manager
from sqlalchemy import text

bcrypt = Bcrypt()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'smartinventory_secret_2025'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    from flask_login import LoginManager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    set_login_manager(login_manager)

    with app.app_context():
        from models import User, Category, Supplier, Product, Sale, SaleItem, Company
        db.create_all()
        ensure_company_auth_columns()

        from utils.seed import seed_data
        seed_data( )

        from routes.auth import auth
        from routes.dashboard import dashboard
        from routes.inventory import inventory
        from routes.sales import sales
        from routes.reports import reports

        app.register_blueprint(auth)
        app.register_blueprint(dashboard)
        app.register_blueprint(inventory)
        app.register_blueprint(sales)
        app.register_blueprint(reports)

    return app

def ensure_company_auth_columns():
    conn = db.session.connection()
    rows = conn.execute(text("PRAGMA table_info(companies)")).fetchall()
    existing_cols = {row[1] for row in rows}

    if 'company_userid' not in existing_cols:
        conn.execute(text("ALTER TABLE companies ADD COLUMN company_userid VARCHAR(50)"))
        conn.commit()
    if 'company_password' not in existing_cols:
        conn.execute(text("ALTER TABLE companies ADD COLUMN company_password VARCHAR(200)"))
        conn.commit()

    # User table additions
    user_rows = conn.execute(text("PRAGMA table_info(users)")).fetchall()
    user_cols = {row[1] for row in user_rows}
    if 'phone' not in user_cols:
        conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(20)"))
        conn.commit()

    # Product table additions
    prod_rows = conn.execute(text("PRAGMA table_info(products)")).fetchall()
    prod_cols = {row[1] for row in prod_rows}
    if 'gst_rate' not in prod_cols:
        conn.execute(text("ALTER TABLE products ADD COLUMN gst_rate FLOAT DEFAULT 0.0"))
        conn.commit()
    if 'is_deleted' not in prod_cols:
        conn.execute(text("ALTER TABLE products ADD COLUMN is_deleted BOOLEAN DEFAULT 0"))
        conn.commit()

    from models import Company
    companies_without_userid = Company.query.filter(Company.company_userid.is_(None)).all()
    for company in companies_without_userid:
        safe_name = ''.join(ch.lower() for ch in company.name if ch.isalnum())[:12] or f"company{company.id}"
        fallback_userid = safe_name
        suffix = 1
        while Company.query.filter(Company.company_userid == fallback_userid, Company.id != company.id).first():
            suffix += 1
            fallback_userid = f"{safe_name}{suffix}"
        company.company_userid = fallback_userid

    companies_without_password = Company.query.filter(Company.company_password.is_(None)).all()
    for company in companies_without_password:
        company.company_password = bcrypt.generate_password_hash('company123').decode('utf-8')

    # Backward compatibility for seeded default company login.
    seeded_company = Company.query.filter_by(name='Sri Ganesh Traders').first()
    if seeded_company:
        seeded_company.company_userid = 'ganeshtraders'
        seeded_company.company_password = bcrypt.generate_password_hash('ganesh123').decode('utf-8')

    db.session.commit()

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)