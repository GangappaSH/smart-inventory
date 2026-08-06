from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app import bcrypt
from models import db, User, Company
import secrets
from sqlalchemy import func

auth = Blueprint('auth', __name__)

@auth.route('/')
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        action = request.form.get('action', 'company')
        
        if action == 'company':
            company_userid = request.form.get('company_userid', '').strip()
            company_password = request.form.get('company_password', '')

            company = Company.query.filter(func.lower(Company.company_userid) == company_userid.lower()).first()
            if not company:
                company = Company.query.filter(func.lower(Company.name) == company_userid.lower()).first()
            if company and company.company_password and bcrypt.check_password_hash(company.company_password, company_password):
                session['company_id'] = company.id
                session['company_name'] = company.name
                flash(f'Company "{company.name}" selected. Please enter your credentials.', 'info')
                return redirect(url_for('auth.login'))
            flash('Invalid company user ID or password.', 'error')
        
        elif action == 'user' and 'company_id' in session:
            # User login with role-based access
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            company_id = session.get('company_id')
            
            user = User.query.filter(
                User.company_id == company_id,
                func.lower(User.username) == username.lower()
            ).first()

            # Backward-compatible alias for seeded demo account.
            if not user and username.lower() == 'staff':
                user = User.query.filter(
                    User.company_id == company_id,
                    func.lower(User.username) == 'staff1'
                ).first()
            if user and user.is_active_account and bcrypt.check_password_hash(user.password, password):
                login_user(user)
                flash(f'Welcome back, {user.full_name}! ({user.role})', 'success')
                return redirect(url_for('dashboard.index'))
            flash('Invalid username or password for this company.', 'error')
    
    company_id = session.get('company_id')
    company_name = session.get('company_name')
    return render_template('login.html', company_id=company_id, company_name=company_name)

@auth.route('/clear-company')
def clear_company():
    session.pop('company_id', None)
    session.pop('company_name', None)
    return redirect(url_for('auth.login'))

@auth.route('/register-company', methods=['GET', 'POST'])
def register_company():
    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        company_email = request.form.get('company_email', '').strip()
        company_phone = request.form.get('company_phone', '').strip()
        company_address = request.form.get('company_address', '').strip()
        company_userid = request.form.get('company_userid', '').strip()
        company_password = request.form.get('company_password', '')
        company_confirm_password = request.form.get('company_confirm_password', '')
        admin_name = request.form.get('admin_name', '').strip()
        admin_username = request.form.get('admin_username', '').strip()
        admin_password = request.form.get('admin_password', '')
        confirm_password = request.form.get('confirm_password', '')
        staff_name = request.form.get('staff_name', '').strip()
        staff_username = request.form.get('staff_username', '').strip()
        staff_password = request.form.get('staff_password', '')
        staff_confirm_password = request.form.get('staff_confirm_password', '')

        if not company_name or not company_email or not company_userid or not company_password.strip() or not admin_name or not admin_username or not admin_password.strip():
            flash('All fields are required.', 'error')
            return render_template('register_company.html')
        
        if company_password != company_confirm_password:
            flash('Company password and confirm password do not match.', 'error')
            return render_template('register_company.html')

        if admin_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register_company.html')

        existing_company_name = Company.query.filter(
            func.lower(Company.name) == company_name.lower()
        ).first()
        if existing_company_name:
            flash('Company name already exists.', 'error')
            return render_template('register_company.html')

        existing_company_userid = Company.query.filter(
            func.lower(Company.company_userid) == company_userid.lower()
        ).first()
        if existing_company_userid:
            flash('Company user ID already exists.', 'error')
            return render_template('register_company.html')

        existing_company_name_as_userid = Company.query.filter(
            func.lower(Company.name) == company_userid.lower()
        ).first()
        if existing_company_name_as_userid:
            flash('Company user ID conflicts with an existing company name.', 'error')
            return render_template('register_company.html')
        
        # Usernames are unique per-company (not globally). Since this is a brand-new
        # company being created, no users exist for it yet, so no username collision
        # is possible at registration time. We only need to ensure admin != staff.

        has_any_staff_field = bool(staff_name or staff_username or staff_password or staff_confirm_password)
        if has_any_staff_field:
            if not staff_name or not staff_username or not staff_password.strip() or not staff_confirm_password.strip():
                flash('To create staff account, fill all staff fields.', 'error')
                return render_template('register_company.html')
            if staff_password != staff_confirm_password:
                flash('Staff password and confirm password do not match.', 'error')
                return render_template('register_company.html')
            if admin_username.lower() == staff_username.lower():
                flash('Admin and staff username must be different.', 'error')
                return render_template('register_company.html')
        
        # Create company
        registration_key = secrets.token_urlsafe(12)
        company = Company(
            name=company_name,
            email=company_email,
            phone=company_phone,
            address=company_address,
            registration_key=registration_key,
            company_userid=company_userid,
            company_password=bcrypt.generate_password_hash(company_password).decode('utf-8')
        )
        db.session.add(company)
        db.session.flush()
        
        # Create admin user
        admin = User(
            username=admin_username,
            email=company_email,
            password=bcrypt.generate_password_hash(admin_password).decode('utf-8'),
            role='admin',
            full_name=admin_name,
            theme='dark',
            company_id=company.id,
            is_active_account=True
        )
        db.session.add(admin)

        if has_any_staff_field:
            staff = User(
                username=staff_username,
                email=company_email,
                password=bcrypt.generate_password_hash(staff_password).decode('utf-8'),
                role='staff',
                full_name=staff_name,
                theme='dark',
                company_id=company.id,
                is_active_account=True
            )
            db.session.add(staff)

        db.session.commit()
        
        flash('Company registered successfully. Login using company user ID and password.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register_company.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/theme/<theme>')
@login_required
def change_theme(theme):
    if theme not in ['dark', 'light']:
        theme = 'dark'
    current_user.theme = theme
    db.session.commit()
    flash(f'Theme changed to {theme}!', 'success')
    return redirect(request.referrer or url_for('dashboard.index'))

@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Personal details (All users)
        current_user.full_name = request.form.get('full_name', '').strip()
        current_user.email = request.form.get('email', '').strip()
        current_user.phone = request.form.get('phone', '').strip()

        # Company details (Admin only)
        if current_user.role == 'admin':
            current_user.company.name = request.form.get('company_name', '').strip()
            current_user.company.email = request.form.get('company_email', '').strip()

        # Security updates (Requires current password if changing passwords or company credentials)
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        company_new_userid = request.form.get('company_userid', '').strip()
        company_new_password = request.form.get('company_password', '')

        security_change = bool(new_password or company_new_userid != current_user.company.company_userid or company_new_password)
        
        if security_change:
            if not bcrypt.check_password_hash(current_user.password, current_password):
                flash('Current user password is required and must be correct for security changes.', 'error')
                return render_template('profile.html')

            if new_password:
                if new_password != confirm_password:
                    flash('New password and confirm password do not match.', 'error')
                    return render_template('profile.html')
                
                # Strong password validation
                import re
                if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', new_password):
                    flash('Password must be at least 8 chars, with uppercase, lowercase, number, and special symbol.', 'error')
                    return render_template('profile.html')
                    
                current_user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')

            if company_new_userid and company_new_userid != current_user.company.company_userid:
                existing = Company.query.filter(
                    func.lower(Company.company_userid) == company_new_userid.lower(),
                    Company.id != current_user.company_id
                ).first()
                if existing:
                    flash('Company user ID already in use.', 'error')
                    return render_template('profile.html')
                current_user.company.company_userid = company_new_userid

            if company_new_password:
                current_user.company.company_password = bcrypt.generate_password_hash(company_new_password).decode('utf-8')

        db.session.commit()
        flash('Profile and details updated successfully.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('profile.html')


# ── Staff Management (admin only) ────────────────────────────────────────────

@auth.route('/staff')
@login_required
def staff_list():
    if current_user.role != 'admin':
        flash('Access denied. Admins only.', 'error')
        return redirect(url_for('dashboard.index'))
    staff_members = User.query.filter_by(company_id=current_user.company_id).order_by(User.role, User.full_name).all()
    return render_template('staff.html', staff_members=staff_members)


@auth.route('/staff/add', methods=['GET', 'POST'])
@login_required
def add_staff():
    if current_user.role != 'admin':
        flash('Access denied. Admins only.', 'error')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', 'staff')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name or not username or not email or not password:
            flash('All fields marked with * are required.', 'error')
            return render_template('add_staff.html')

        # Strong password validation
        import re
        if not re.match(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$', password):
            flash('Password must be at least 8 chars, with uppercase, lowercase, number, and special symbol.', 'error')
            return render_template('add_staff.html')

        if role not in ('admin', 'staff'):
            flash('Invalid role selected.', 'error')
            return render_template('add_staff.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('add_staff.html')

        existing = User.query.filter(
            User.company_id == current_user.company_id,
            func.lower(User.username) == username.lower()
        ).first()
        if existing:
            flash('Username already exists in your company.', 'error')
            return render_template('add_staff.html')

        new_user = User(
            username=username,
            email=email,
            phone=phone,
            password=bcrypt.generate_password_hash(password).decode('utf-8'),
            role=role,
            full_name=full_name,
            theme='dark',
            company_id=current_user.company_id,
            is_active_account=True
        )
        db.session.add(new_user)
        db.session.commit()
        flash(f'Staff member "{full_name}" added successfully.', 'success')
        return redirect(url_for('auth.staff_list'))

    return render_template('add_staff.html')


@auth.route('/staff/<int:user_id>/toggle', methods=['POST'])
@login_required
def toggle_staff(user_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))
    user = User.query.filter_by(id=user_id, company_id=current_user.company_id).first_or_404()
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'error')
        return redirect(url_for('auth.staff_list'))
    user.is_active_account = not user.is_active_account
    db.session.commit()
    state = 'activated' if user.is_active_account else 'deactivated'
    flash(f'Account for "{user.full_name}" {state}.', 'success')
    return redirect(url_for('auth.staff_list'))


@auth.route('/staff/<int:user_id>/reset-password', methods=['POST'])
@login_required
def reset_staff_password(user_id):
    if current_user.role != 'admin':
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.index'))
    user = User.query.filter_by(id=user_id, company_id=current_user.company_id).first_or_404()
    new_password = request.form.get('new_password', '')
    if len(new_password) < 4:
        flash('Password must be at least 4 characters.', 'error')
        return redirect(url_for('auth.staff_list'))
    user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')
    db.session.commit()
    flash(f'Password reset for "{user.full_name}".', 'success')
    return redirect(url_for('auth.staff_list'))
