def seed_data():
    from models import db, Company, User, Category, Supplier, Product, Sale, SaleItem
    from app import bcrypt
    from datetime import datetime, timedelta
    import random

    if Company.query.first():
        return

    # Company
    company = Company(
        name='Sri Ganesh Traders',
        email='admin@ganeshtraders.com',
        phone='9876543210',
        address='Market Road, Dharwad, Karnataka',
        registration_key='GNSH2025',
        company_userid='ganesh',
        company_password=bcrypt.generate_password_hash('ganesh123').decode('utf-8')
    )
    db.session.add(company)
    db.session.flush()

    # Admin user
    admin = User(
        username='admin',
        email='admin@ganeshtraders.com',
        password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
        role='admin',
        full_name='Admin User',
        company_id=company.id
    )
    # Staff user
    staff = User(
        username='staff1',
        email='staff@ganeshtraders.com',
        password=bcrypt.generate_password_hash('staff123').decode('utf-8'),
        role='staff',
        full_name='Raju Kumar',
        company_id=company.id
    )
    db.session.add_all([admin, staff])
    db.session.commit()

    # Categories
    cats = ['Groceries', 'Beverages', 'Dairy', 'Snacks', 'Personal Care']
    cat_objs = [Category(name=c, company_id=company.id) for c in cats]
    db.session.add_all(cat_objs)

    # Suppliers
    sup_objs = [
        Supplier(name='Fresh Farms',       contact='9876543210', email='fresh@farms.com',  company_id=company.id),
        Supplier(name='Metro Distributors',contact='9123456780', email='metro@dist.com',   company_id=company.id),
        Supplier(name='Krishna Traders',   contact='9988776655', email='krishna@trade.com',company_id=company.id),
    ]
    db.session.add_all(sup_objs)
    db.session.commit()

    cat_list = Category.query.filter_by(company_id=company.id).all()
    sup_list = Supplier.query.filter_by(company_id=company.id).all()

    # Products
    products_data = [
        ('Rice (5kg)',         'SKU001', 0, 0, 250, 190, 45, 5,  'bag'),
        ('Toor Dal (1kg)',     'SKU002', 0, 1, 120,  95, 30, 5,  'kg'),
        ('Sugar (1kg)',        'SKU003', 0, 0,  45,  36, 60, 10, 'kg'),
        ('Salt (1kg)',         'SKU004', 0, 2,  20,  15,  8,  5, 'kg'),
        ('Sunflower Oil (1L)', 'SKU005', 0, 1, 160, 130, 20,  5, 'bottle'),
        ('Coca Cola (500ml)',  'SKU006', 1, 1,  40,  30, 50, 10, 'bottle'),
        ('Thumbs Up (500ml)',  'SKU007', 1, 1,  40,  30,  3,  5, 'bottle'),
        ('Milk (1L)',          'SKU008', 2, 0,  55,  48, 25, 10, 'litre'),
        ('Curd (500g)',        'SKU009', 2, 0,  35,  28, 18,  5, 'cup'),
        ('Butter (100g)',      'SKU010', 2, 2,  55,  45, 12,  5, 'pack'),
        ('Lays Chips',         'SKU011', 3, 1,  20,  15, 80, 15, 'pcs'),
        ('Biscuits (Parle-G)', 'SKU012', 3, 2,  10,   7,100, 20, 'pcs'),
        ('Shampoo (200ml)',    'SKU013', 4, 1, 150, 110, 22,  5, 'bottle'),
        ('Soap (100g)',        'SKU014', 4, 2,  35,  25, 40, 10, 'pcs'),
        ('Toothpaste (100g)',  'SKU015', 4, 0,  80,  60, 35,  5, 'tube'),
    ]
    prod_objs = []
    for name, sku, ci, si, price, cost, qty, reorder, unit in products_data:
        prod_objs.append(Product(
            name=name, sku=sku,
            category_id=cat_list[ci].id,
            supplier_id=sup_list[si].id,
            company_id=company.id,
            price=price, cost_price=cost,
            quantity=qty, reorder_level=reorder, unit=unit
        ))
    db.session.add_all(prod_objs)
    db.session.commit()

    # Historical Sales - last 60 days
    products = Product.query.filter_by(company_id=company.id).all()
    counter = 1
    for days_ago in range(60, 0, -1):
        sale_date = datetime.utcnow() - timedelta(days=days_ago)
        for _ in range(random.randint(1, 4)):
            sale = Sale(
                invoice_no=f"INV{counter:04d}",
                staff_id=staff.id,
                company_id=company.id,
                sale_date=sale_date,
                total_amount=0
            )
            db.session.add(sale)
            db.session.flush()
            total = 0
            for prod in random.sample(products, random.randint(1, 4)):
                qty = random.randint(1, 5)
                subtotal = qty * prod.price
                db.session.add(SaleItem(
                    sale_id=sale.id, product_id=prod.id,
                    quantity=qty, unit_price=prod.price, subtotal=subtotal
                ))
                total += subtotal
            sale.total_amount = round(total, 2)
            counter += 1
    db.session.commit()