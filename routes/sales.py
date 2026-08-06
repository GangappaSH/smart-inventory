from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Sale, SaleItem, Product
from models import db
from datetime import datetime
import random, string

sales = Blueprint('sales', __name__)

def generate_invoice():
    return 'INV' + ''.join(random.choices(string.digits, k=6))

@sales.route('/sales')
@login_required
def index():
    all_sales = Sale.query.filter_by(company_id=current_user.company_id).order_by(Sale.sale_date.desc()).limit(50).all()
    return render_template('sales.html', sales=all_sales)

@sales.route('/sales/new', methods=['GET', 'POST'])
@login_required
def new_sale():
    if request.method == 'POST':
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        if not product_ids:
            flash('Add at least one product.', 'error')
            return redirect(url_for('sales.new_sale'))
        invoice = generate_invoice()
        sale = Sale(invoice_no=invoice, staff_id=current_user.id, company_id=current_user.company_id, total_amount=0)
        db.session.add(sale)
        db.session.flush()
        total = 0
        for pid, qty_str in zip(product_ids, quantities):
            qty = int(qty_str)
            product = Product.query.filter_by(id=int(pid), company_id=current_user.company_id).first()
            if not product or product.quantity < qty:
                flash(f'Insufficient stock for {product.name if product else "product"}.', 'error')
                db.session.rollback()
                return redirect(url_for('sales.new_sale'))
            subtotal = qty * product.price
            item = SaleItem(sale_id=sale.id, product_id=product.id,
                            quantity=qty, unit_price=product.price, subtotal=subtotal)
            product.quantity -= qty
            db.session.add(item)
            total += subtotal
        sale.total_amount = round(total, 2)
        db.session.commit()
        flash(f'Sale {invoice} recorded! Total: ₹{sale.total_amount}', 'success')
        return redirect(url_for('sales.index'))
    products = Product.query.filter(
        Product.company_id == current_user.company_id,
        Product.quantity > 0
    ).order_by(Product.name).all()
    return render_template('new_sale.html', products=products)

@sales.route('/sales/<int:id>')
@login_required
def view_sale(id):
    sale = Sale.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()
    return render_template('view_sale.html', sale=sale)
