from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import Product, Sale, SaleItem, Category
from models import db
from datetime import datetime, timedelta
from sqlalchemy import func

reports = Blueprint('reports', __name__)


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
        start_date = datetime.combine(
            today - timedelta(days=today.weekday()), datetime.min.time()
        )
    elif range_str == 'this_month':
        start_date = datetime.combine(today.replace(day=1), datetime.min.time())
    elif range_str == 'all':
        start_date = None
        end_date = None

    return start_date, end_date


@reports.route('/reports')
@login_required
def index():
    today = datetime.utcnow().date()

    # ── Monthly sales last 6 months (fixed) ──────────────────────────────
    monthly = []
    for i in range(5, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 28)
        start = d.replace(day=1)
        end = (
            d.replace(year=d.year + 1, month=1, day=1)
            if d.month == 12
            else d.replace(month=d.month + 1, day=1)
        )
        amt = (
            db.session.query(func.sum(Sale.total_amount))
            .filter(
                Sale.company_id == current_user.company_id,
                Sale.sale_date >= start,
                Sale.sale_date < end,
            )
            .scalar()
            or 0
        )
        monthly.append({'month': start.strftime('%b %Y'), 'amount': round(float(amt), 2)})

    # ── Default to this-month for revenue widgets ─────────────────────────
    start_date = datetime.combine(today.replace(day=1), datetime.min.time())

    # Top 10 products by revenue (this month) — explicit joins
    top_products = (
        db.session.query(
            Product.name,
            func.sum(SaleItem.quantity).label('qty'),
            func.sum(SaleItem.subtotal).label('revenue'),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(
            Product.company_id == current_user.company_id,
            Product.is_deleted == False,
            Sale.company_id == current_user.company_id,
            Sale.sale_date >= start_date,
        )
        .group_by(Product.id)
        .order_by(func.sum(SaleItem.subtotal).desc())
        .limit(10)
        .all()
    )

    # Category revenue (this month) — explicit joins
    cat_sales = (
        db.session.query(
            Category.name,
            func.sum(SaleItem.subtotal).label('revenue'),
        )
        .join(Product, Product.category_id == Category.id)
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(
            Category.company_id == current_user.company_id,
            Sale.company_id == current_user.company_id,
            Sale.sale_date >= start_date,
        )
        .group_by(Category.id)
        .order_by(func.sum(SaleItem.subtotal).desc())
        .all()
    )

    # Categories list for AI filter dropdown
    categories = (
        Category.query.filter_by(company_id=current_user.company_id)
        .order_by(Category.name)
        .all()
    )

    # AI predictions (last 30 days training)
    predictions = get_predictions(training_days=30)
    category_predictions = get_category_predictions(training_days=30)

    return render_template(
        'reports.html',
        monthly=monthly,
        top_products=top_products,
        cat_sales=cat_sales,
        categories=categories,
        predictions=predictions,
        category_predictions=category_predictions,
    )


# ── AI helpers ────────────────────────────────────────────────────────────────

def get_predictions(category_id=None, training_days=30):
    """Linear-regression demand forecast per product for next 7 days."""
    try:
        from sklearn.linear_model import LinearRegression
        import numpy as np

        today = datetime.utcnow().date()
        training_days = max(7, int(training_days))
        results = []

        # Exclude soft-deleted products; optionally filter by category
        prod_query = Product.query.filter_by(
            company_id=current_user.company_id, is_deleted=False
        )
        if category_id:
            prod_query = prod_query.filter_by(category_id=int(category_id))
        products = prod_query.all()

        for prod in products:
            daily_sales = []
            for i in range(training_days, 0, -1):
                day = today - timedelta(days=i)
                # Explicit join: SaleItem → Sale only (filter by product_id directly)
                qty = (
                    db.session.query(func.sum(SaleItem.quantity))
                    .join(Sale, Sale.id == SaleItem.sale_id)
                    .filter(
                        SaleItem.product_id == prod.id,
                        Sale.company_id == current_user.company_id,
                        func.date(Sale.sale_date) == day,
                    )
                    .scalar()
                    or 0
                )
                daily_sales.append(float(qty))

            if sum(daily_sales) == 0:
                continue

            X = np.array(range(len(daily_sales))).reshape(-1, 1)
            y = np.array(daily_sales)
            model = LinearRegression()
            model.fit(X, y)

            next_7 = model.predict(
                np.array(range(training_days, training_days + 7)).reshape(-1, 1)
            )
            # Convert numpy types → native Python types for JSON safety
            predicted   = float(max(0.0, round(float(np.sum(next_7)), 1)))
            avg_daily   = float(round(sum(daily_sales) / len(daily_sales), 1))
            trend_coef  = float(model.coef_[0])
            trend = (
                'up'   if trend_coef >  0.05 else
                'down' if trend_coef < -0.05 else
                'stable'
            )
            # Reorder if 7-day demand > stock  OR  stock already ≤ reorder level
            reorder_suggested = bool(
                predicted > float(prod.quantity)
                or prod.quantity <= prod.reorder_level
            )

            results.append({
                'product':           str(prod.name),
                'sku':               str(prod.sku),
                'product_id':        int(prod.id),
                'current_stock':     int(prod.quantity),
                'reorder_level':     int(prod.reorder_level),
                'avg_daily':         avg_daily,
                'predicted_7days':   predicted,
                'reorder_suggested': reorder_suggested,
                'stock_critical':    bool(prod.quantity <= prod.reorder_level),
                'trend':             trend,
            })

        results.sort(key=lambda x: x['predicted_7days'], reverse=True)
        return results[:10]

    except Exception as e:
        print(f'[AI Prediction Error] {e}')
        return []


def get_category_predictions(training_days=30):
    """Linear-regression revenue forecast per category for next 7 days."""
    try:
        from sklearn.linear_model import LinearRegression
        import numpy as np

        today = datetime.utcnow().date()
        training_days = max(7, int(training_days))
        results = []

        categories = Category.query.filter_by(
            company_id=current_user.company_id
        ).all()

        for cat in categories:
            daily_revenue = []
            for i in range(training_days, 0, -1):
                day = today - timedelta(days=i)
                # Explicit joins: SaleItem → Sale  AND  SaleItem → Product
                rev = (
                    db.session.query(func.sum(SaleItem.subtotal))
                    .join(Sale,    Sale.id    == SaleItem.sale_id)
                    .join(Product, Product.id == SaleItem.product_id)
                    .filter(
                        Product.category_id == cat.id,
                        Sale.company_id == current_user.company_id,
                        func.date(Sale.sale_date) == day,
                    )
                    .scalar()
                    or 0
                )
                daily_revenue.append(float(rev))

            if sum(daily_revenue) == 0:
                continue

            X = np.array(range(len(daily_revenue))).reshape(-1, 1)
            y = np.array(daily_revenue)
            model = LinearRegression()
            model.fit(X, y)

            next_7 = model.predict(
                np.array(range(training_days, training_days + 7)).reshape(-1, 1)
            )
            predicted  = float(max(0.0, round(float(np.sum(next_7)), 2)))
            avg_daily  = float(round(sum(daily_revenue) / len(daily_revenue), 2))
            trend_coef = float(model.coef_[0])
            trend = (
                'up'   if trend_coef >  0.05 else
                'down' if trend_coef < -0.05 else
                'stable'
            )

            results.append({
                'category_name':           str(cat.name),
                'avg_daily_revenue':       avg_daily,
                'predicted_7days_revenue': predicted,
                'trend':                   trend,
            })

        results.sort(key=lambda x: x['predicted_7days_revenue'], reverse=True)
        return results

    except Exception as e:
        print(f'[Category AI Prediction Error] {e}')
        return []


# ── AJAX API endpoints ────────────────────────────────────────────────────────

@reports.route('/reports/api/category-revenue')
@login_required
def api_category_revenue():
    range_str = request.args.get('range', 'this_month')
    start_date, end_date = get_date_range(range_str)

    query = (
        db.session.query(
            Category.name,
            func.sum(SaleItem.subtotal).label('revenue'),
        )
        .join(Product,  Product.category_id == Category.id)
        .join(SaleItem, SaleItem.product_id  == Product.id)
        .join(Sale,     Sale.id              == SaleItem.sale_id)
        .filter(
            Category.company_id == current_user.company_id,
            Sale.company_id     == current_user.company_id,
        )
    )
    if start_date:
        query = query.filter(Sale.sale_date >= start_date)
    if end_date:
        query = query.filter(Sale.sale_date <= end_date)

    cat_sales = query.group_by(Category.id).order_by(
        func.sum(SaleItem.subtotal).desc()
    ).all()
    return jsonify(
        [{'name': str(name), 'revenue': round(float(rev), 2)} for name, rev in cat_sales]
    )


@reports.route('/reports/api/top-revenue')
@login_required
def api_top_revenue():
    range_str = request.args.get('range', 'this_month')
    start_date, end_date = get_date_range(range_str)

    query = (
        db.session.query(
            Product.name,
            func.sum(SaleItem.quantity).label('qty'),
            func.sum(SaleItem.subtotal).label('revenue'),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale,     Sale.id             == SaleItem.sale_id)
        .filter(
            Product.company_id == current_user.company_id,
            Product.is_deleted == False,
            Sale.company_id    == current_user.company_id,
        )
    )
    if start_date:
        query = query.filter(Sale.sale_date >= start_date)
    if end_date:
        query = query.filter(Sale.sale_date <= end_date)

    rows = query.group_by(Product.id).order_by(
        func.sum(SaleItem.subtotal).desc()
    ).limit(10).all()
    return jsonify(
        [{'name': str(n), 'qty': int(q), 'revenue': round(float(r), 2)} for n, q, r in rows]
    )


@reports.route('/reports/api/predictions')
@login_required
def api_predictions():
    cat_id_raw    = request.args.get('category_id', '')
    cat_id        = int(cat_id_raw) if cat_id_raw.isdigit() else None
    training_days = int(request.args.get('training_days', '30'))
    return jsonify(get_predictions(category_id=cat_id, training_days=training_days))


@reports.route('/reports/api/category-predictions')
@login_required
def api_category_predictions():
    training_days = int(request.args.get('training_days', '30'))
    return jsonify(get_category_predictions(training_days=training_days))
