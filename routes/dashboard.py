from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import Product, Sale, SaleItem, User, Category
from models import db
from datetime import datetime, timedelta
from sqlalchemy import func

dashboard = Blueprint('dashboard', __name__)

def get_date_range(range_str):
    today = datetime.utcnow().date()
    start_date = None
    end_date = datetime.combine(today, datetime.max.time())
    
    if range_str == 'today':
        start_date = datetime.combine(today, datetime.min.time())
    elif range_str == 'yesterday':
        yesterday = today - timedelta(days=1)
        start_date = datetime.combine(yesterday, datetime.min.time())
        end_date = datetime.combine(yesterday, datetime.max.time())
    elif range_str == 'this_week':
        start_date = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
    elif range_str == 'this_month':
        start_date = datetime.combine(today.replace(day=1), datetime.min.time())
    elif range_str == 'all':
        start_date = None
        end_date = None
        
    return start_date, end_date

@dashboard.route('/dashboard')
@login_required
def index():
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)

    total_products = Product.query.filter_by(company_id=current_user.company_id).count()
    low_stock = Product.query.filter(
        Product.company_id == current_user.company_id,
        Product.quantity <= Product.reorder_level
    ).all()
    total_sales_today = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.company_id == current_user.company_id,
        func.date(Sale.sale_date) == today
    ).scalar() or 0
    total_sales_month = db.session.query(func.sum(Sale.total_amount)).filter(
        Sale.company_id == current_user.company_id,
        Sale.sale_date >= month_start
    ).scalar() or 0
    total_staff = User.query.filter_by(role='staff', company_id=current_user.company_id).count()

    # Sales chart: last 7 days (remains fixed as 7-day trend)
    chart_labels, chart_data = [], []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        amt = db.session.query(func.sum(Sale.total_amount)).filter(
            Sale.company_id == current_user.company_id,
            func.date(Sale.sale_date) == day
        ).scalar() or 0
        chart_labels.append(day.strftime('%d %b'))
        chart_data.append(round(float(amt), 2))

    # Initial load data: default to "this_month"
    start_date = datetime.combine(today.replace(day=1), datetime.min.time())

    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_qty')
    ).join(SaleItem).join(Sale).filter(
        Product.company_id == current_user.company_id,
        Sale.company_id == current_user.company_id,
        Sale.sale_date >= start_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()

    category_revenue = db.session.query(
        Category.name,
        func.sum(SaleItem.subtotal).label('revenue')
    ).join(Product, Product.category_id == Category.id).join(SaleItem).join(Sale).filter(
        Category.company_id == current_user.company_id,
        Sale.company_id == current_user.company_id,
        Sale.sale_date >= start_date
    ).group_by(Category.id).order_by(func.sum(SaleItem.subtotal).desc()).all()
    
    category_labels = [name for name, _ in category_revenue]
    category_data = [round(float(rev), 2) for _, rev in category_revenue]

    top_revenue = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('qty'),
        func.sum(SaleItem.subtotal).label('revenue')
    ).join(SaleItem).join(Sale).filter(
        Product.company_id == current_user.company_id,
        Sale.company_id == current_user.company_id,
        Sale.sale_date >= start_date
    ).group_by(Product.id).order_by(func.sum(SaleItem.subtotal).desc()).limit(5).all()

    recent_sales = Sale.query.filter(
        Sale.company_id == current_user.company_id,
        Sale.sale_date >= start_date
    ).order_by(Sale.sale_date.desc()).limit(8).all()

    return render_template('dashboard.html',
        total_products=total_products,
        low_stock=low_stock,
        total_sales_today=round(total_sales_today, 2),
        total_sales_month=round(total_sales_month, 2),
        total_staff=total_staff,
        chart_labels=chart_labels,
        chart_data=chart_data,
        top_products=top_products,
        category_labels=category_labels,
        category_data=category_data,
        top_revenue=top_revenue,
        recent_sales=recent_sales
    )

# --- API Endpoints for AJAX updating ---

@dashboard.route('/dashboard/api/top-products')
@login_required
def api_top_products():
    range_str = request.args.get('range', 'this_month')
    start_date, end_date = get_date_range(range_str)
    
    query = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('total_qty')
    ).join(SaleItem).join(Sale).filter(
        Product.company_id == current_user.company_id,
        Sale.company_id == current_user.company_id
    )
    if start_date:
        query = query.filter(Sale.sale_date >= start_date)
    if end_date:
        query = query.filter(Sale.sale_date <= end_date)
        
    top_products = query.group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()
    return jsonify([{'name': name, 'total_qty': int(qty)} for name, qty in top_products])

@dashboard.route('/dashboard/api/category-revenue')
@login_required
def api_category_revenue():
    range_str = request.args.get('range', 'this_month')
    start_date, end_date = get_date_range(range_str)
    
    query = db.session.query(
        Category.name,
        func.sum(SaleItem.subtotal).label('revenue')
    ).join(Product, Product.category_id == Category.id).join(SaleItem).join(Sale).filter(
        Category.company_id == current_user.company_id,
        Sale.company_id == current_user.company_id
    )
    if start_date:
        query = query.filter(Sale.sale_date >= start_date)
    if end_date:
        query = query.filter(Sale.sale_date <= end_date)
        
    cat_sales = query.group_by(Category.id).order_by(func.sum(SaleItem.subtotal).desc()).all()
    return jsonify([{'name': name, 'revenue': round(float(rev), 2)} for name, rev in cat_sales])

@dashboard.route('/dashboard/api/top-revenue')
@login_required
def api_top_revenue():
    range_str = request.args.get('range', 'this_month')
    start_date, end_date = get_date_range(range_str)
    
    query = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('qty'),
        func.sum(SaleItem.subtotal).label('revenue')
    ).join(SaleItem).join(Sale).filter(
        Product.company_id == current_user.company_id,
        Sale.company_id == current_user.company_id
    )
    if start_date:
        query = query.filter(Sale.sale_date >= start_date)
    if end_date:
        query = query.filter(Sale.sale_date <= end_date)
        
    top_revenue = query.group_by(Product.id).order_by(func.sum(SaleItem.subtotal).desc()).limit(5).all()
    return jsonify([{'name': name, 'qty': int(qty), 'revenue': round(float(rev), 2)} for name, qty, rev in top_revenue])

@dashboard.route('/dashboard/api/sales-history')
@login_required
def api_sales_history():
    range_str = request.args.get('range', 'this_month')
    start_date, end_date = get_date_range(range_str)
    
    query = Sale.query.filter_by(company_id=current_user.company_id)
    if start_date:
        query = query.filter(Sale.sale_date >= start_date)
    if end_date:
        query = query.filter(Sale.sale_date <= end_date)
        
    recent_sales = query.order_by(Sale.sale_date.desc()).limit(8).all()
    return jsonify([{
        'id': sale.id,
        'invoice_no': sale.invoice_no,
        'staff_name': sale.staff.full_name if sale.staff else 'Unknown',
        'total_amount': round(float(sale.total_amount), 2),
        'sale_date': sale.sale_date.strftime('%d %b')
    } for sale in recent_sales])

