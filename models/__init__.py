from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()
login_manager = None

def set_login_manager(lm):
    global login_manager
    login_manager = lm
    
    @lm.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    registration_key = db.Column(db.String(50), unique=True, nullable=False)
    company_userid = db.Column(db.String(50), unique=True)
    company_password = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    users = db.relationship('User', backref='company', lazy=True)
    categories = db.relationship('Category', backref='company', lazy=True)
    suppliers = db.relationship('Supplier', backref='company', lazy=True)
    products = db.relationship('Product', backref='company', lazy=True)
    sales = db.relationship('Sale', backref='company', lazy=True)

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False, default='staff')  # 'admin' or 'staff'
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    theme = db.Column(db.String(10), nullable=False, default='dark')  # 'dark' or 'light'
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active_account = db.Column(db.Boolean, default=True)
    sales = db.relationship('Sale', backref='staff', lazy=True)
    __table_args__ = (db.UniqueConstraint('username', 'company_id', name='unique_username_per_company'),)

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    products = db.relationship('Product', backref='category', lazy=True)
    __table_args__ = (db.UniqueConstraint('name', 'company_id', name='unique_category_per_company'),)

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(20))
    email = db.Column(db.String(100))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    products = db.relationship('Product', backref='supplier', lazy=True)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(30), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    gst_rate = db.Column(db.Float, default=0.0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, default=10)
    unit = db.Column(db.String(20), default='pcs')
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sales = db.relationship('SaleItem', backref='product', lazy=True, cascade='all, delete-orphan')
    __table_args__ = (db.UniqueConstraint('sku', 'company_id', name='unique_sku_per_company'),)

    @property
    def gst_amount(self):
        return round((self.price * self.gst_rate) / 100, 2)

    @property
    def total_price(self):
        return round(self.price + self.gst_amount, 2)

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    @property
    def profit_margin(self):
        if self.price > 0:
            return round(((self.price - self.cost_price) / self.price) * 100, 1)
        return 0

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(20), nullable=False)
    staff_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')
    __table_args__ = (db.UniqueConstraint('invoice_no', 'company_id', name='unique_invoice_per_company'),)

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
