from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Product, Category, Supplier
from models import db
import secrets

inventory = Blueprint('inventory', __name__)

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated

@inventory.route('/inventory')
@login_required
def index():
    search = request.args.get('search', '')
    category_id = request.args.get('category', '')
    query = Product.query.filter_by(company_id=current_user.company_id, is_deleted=False)
    if search:
        query = query.filter(
            Product.name.ilike(f'%{search}%') |
            Product.sku.ilike(f'%{search}%') |
            Product.id.cast(db.String).ilike(f'%{search}%')
        )
    if category_id:
        query = query.filter_by(category_id=category_id)
    products = query.order_by(Product.name).all()
    categories = Category.query.filter_by(company_id=current_user.company_id).all()
    return render_template('inventory.html', products=products, categories=categories,
                           search=search, selected_cat=category_id)

@inventory.route('/inventory/recycle-bin')
@login_required
@admin_required
def recycle_bin():
    products = Product.query.filter_by(company_id=current_user.company_id, is_deleted=True).order_by(Product.name).all()
    return render_template('recycle_bin.html', products=products)

@inventory.route('/inventory/recycle-bin/restore/<int:id>', methods=['POST'])
@login_required
@admin_required
def restore_product(id):
    p = Product.query.filter_by(id=id, company_id=current_user.company_id, is_deleted=True).first_or_404()
    p.is_deleted = False
    db.session.commit()
    flash(f'Product "{p.name}" restored to inventory.', 'success')
    return redirect(url_for('inventory.recycle_bin'))

@inventory.route('/inventory/recycle-bin/purge/<int:id>', methods=['POST'])
@login_required
@admin_required
def purge_product(id):
    p = Product.query.filter_by(id=id, company_id=current_user.company_id, is_deleted=True).first_or_404()
    db.session.delete(p)
    db.session.commit()
    flash(f'Product "{p.name}" permanently removed.', 'info')
    return redirect(url_for('inventory.recycle_bin'))

@inventory.route('/inventory/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        temp_sku = f"TMP{secrets.token_hex(6).upper()}"
        p = Product(
            name=request.form['name'], sku=temp_sku,
            category_id=request.form['category_id'],
            supplier_id=request.form.get('supplier_id') or None,
            price=float(request.form['price']),
            cost_price=float(request.form['cost_price']),
            gst_rate=float(request.form.get('gst_rate', 0.0)),
            quantity=int(request.form['quantity']),
            reorder_level=int(request.form['reorder_level']),
            unit=request.form.get('unit', 'pcs'),
            company_id=current_user.company_id
        )
        db.session.add(p)
        db.session.flush()
        p.sku = f"PRD{p.id:04d}"
        db.session.commit()
        flash(f'Product "{p.name}" added successfully!', 'success')
        return redirect(url_for('inventory.index'))
    return render_template('add_product.html',
                           categories=Category.query.filter_by(company_id=current_user.company_id).all(),
                           suppliers=Supplier.query.filter_by(company_id=current_user.company_id).all())

@inventory.route('/inventory/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_product(id):
    p = Product.query.filter_by(id=id, company_id=current_user.company_id, is_deleted=False).first_or_404()
    if request.method == 'POST':
        p.name = request.form['name']
        p.price = float(request.form['price'])
        p.cost_price = float(request.form['cost_price'])
        p.gst_rate = float(request.form.get('gst_rate', 0.0))
        p.quantity = int(request.form['quantity'])
        p.reorder_level = int(request.form['reorder_level'])
        p.unit = request.form.get('unit', 'pcs')
        p.category_id = request.form['category_id']
        p.supplier_id = request.form.get('supplier_id') or None
        db.session.commit()
        flash(f'Product "{p.name}" updated!', 'success')
        return redirect(url_for('inventory.index'))
    return render_template('add_product.html', product=p,
                           categories=Category.query.filter_by(company_id=current_user.company_id).all(),
                           suppliers=Supplier.query.filter_by(company_id=current_user.company_id).all())

@inventory.route('/inventory/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_product(id):
    p = Product.query.filter_by(id=id, company_id=current_user.company_id, is_deleted=False).first_or_404()
    p.is_deleted = True
    db.session.commit()
    flash(f'Product "{p.name}" moved to recycle bin.', 'info')
    return redirect(url_for('inventory.index'))

@inventory.route('/inventory/api/product/<int:id>')
@login_required
def get_product(id):
    p = Product.query.filter_by(id=id, company_id=current_user.company_id, is_deleted=False).first_or_404()
    return jsonify({'id': p.id, 'name': p.name, 'price': p.price, 'quantity': p.quantity, 'unit': p.unit})


# ── Suppliers ────────────────────────────────────────────────────────────────

@inventory.route('/suppliers')
@login_required
@admin_required
def suppliers():
    all_suppliers = Supplier.query.filter_by(company_id=current_user.company_id).order_by(Supplier.name).all()
    return render_template('suppliers.html', suppliers=all_suppliers)

@inventory.route('/suppliers/add', methods=['POST'])
@login_required
@admin_required
def add_supplier():
    name = request.form.get('name', '').strip()
    contact = request.form.get('contact', '').strip()
    email = request.form.get('email', '').strip()
    if not name:
        flash('Supplier name is required.', 'error')
        return redirect(url_for('inventory.suppliers'))
    existing = Supplier.query.filter_by(name=name, company_id=current_user.company_id).first()
    if existing:
        flash(f'Supplier "{name}" already exists.', 'error')
        return redirect(url_for('inventory.suppliers'))
    s = Supplier(name=name, contact=contact, email=email, company_id=current_user.company_id)
    db.session.add(s)
    db.session.commit()
    flash(f'Supplier "{name}" added successfully!', 'success')
    return redirect(url_for('inventory.suppliers'))

@inventory.route('/suppliers/edit/<int:id>', methods=['POST'])
@login_required
@admin_required
def edit_supplier(id):
    s = Supplier.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Supplier name is required.', 'error')
        return redirect(url_for('inventory.suppliers'))
    s.name = name
    s.contact = request.form.get('contact', '').strip()
    s.email = request.form.get('email', '').strip()
    db.session.commit()
    flash(f'Supplier "{s.name}" updated.', 'success')
    return redirect(url_for('inventory.suppliers'))

@inventory.route('/suppliers/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_supplier(id):
    s = Supplier.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()
    if s.products:
        flash(f'Cannot delete "{s.name}" — it has {len(s.products)} product(s) linked.', 'error')
        return redirect(url_for('inventory.suppliers'))
    db.session.delete(s)
    db.session.commit()
    flash(f'Supplier "{s.name}" deleted.', 'info')
    return redirect(url_for('inventory.suppliers'))


# ── Categories ───────────────────────────────────────────────────────────────

@inventory.route('/categories')
@login_required
@admin_required
def categories():
    all_cats = Category.query.filter_by(company_id=current_user.company_id).order_by(Category.name).all()
    return render_template('categories.html', categories=all_cats)

@inventory.route('/categories/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    name = request.form.get('name', '').strip()
    if not name:
        flash('Category name is required.', 'error')
        return redirect(url_for('inventory.categories'))
    existing = Category.query.filter_by(name=name, company_id=current_user.company_id).first()
    if existing:
        flash(f'Category "{name}" already exists.', 'error')
        return redirect(url_for('inventory.categories'))
    c = Category(name=name, company_id=current_user.company_id)
    db.session.add(c)
    db.session.commit()
    flash(f'Category "{name}" created!', 'success')
    return redirect(url_for('inventory.categories'))

@inventory.route('/categories/edit/<int:id>', methods=['POST'])
@login_required
@admin_required
def edit_category(id):
    c = Category.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Category name is required.', 'error')
        return redirect(url_for('inventory.categories'))
    existing = Category.query.filter_by(name=name, company_id=current_user.company_id).first()
    if existing and existing.id != c.id:
        flash(f'Category "{name}" already exists.', 'error')
        return redirect(url_for('inventory.categories'))
    c.name = name
    db.session.commit()
    flash(f'Category renamed to "{name}".', 'success')
    return redirect(url_for('inventory.categories'))

@inventory.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_category(id):
    c = Category.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()
    if c.products:
        flash(f'Cannot delete "{c.name}" — it has {len(c.products)} product(s) linked.', 'error')
        return redirect(url_for('inventory.categories'))
    db.session.delete(c)
    db.session.commit()
    flash(f'Category "{c.name}" deleted.', 'info')
    return redirect(url_for('inventory.categories'))
