from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import AuthService
from app.extensions import db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not identifier or not password:
            flash('Please provide both username/email and password.', 'danger')
            return render_template('auth/login.html')

        user = AuthService.authenticate_user(identifier, password)
        if user:
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Invalid username/email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'warehouse_staff')

        if not username or not email or not password or not full_name:
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register.html')

        try:
            user = AuthService.register_user(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                role=role
            )
            login_user(user)
            flash('Registration successful! Welcome to StockSense.', 'success')
            return redirect(url_for('dashboard.index'))
        except ValueError as e:
            flash(str(e), 'danger')

    return render_template('auth/register.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not email:
            flash('Please enter your email address.', 'danger')
            return render_template('auth/forgot_password.html')

        success, message, dev_otp = AuthService.request_password_reset_otp(email)
        if success:
            flash(message, 'info')
            return redirect(url_for('auth.reset_password', email=email))
        else:
            flash(message, 'danger')

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    email = request.args.get('email', '') or request.form.get('email', '')

    if request.method == 'POST':
        otp_code = request.form.get('otp_code', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email or not otp_code or not new_password:
            flash('All fields are required.', 'danger')
            return render_template('auth/reset_password.html', email=email)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', email=email)

        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/reset_password.html', email=email)

        success, message = AuthService.verify_and_reset_password(email, otp_code, new_password)
        if success:
            flash(message, 'success')
            return redirect(url_for('auth.login'))
        else:
            flash(message, 'danger')

    return render_template('auth/reset_password.html', email=email)


@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name:
            flash('Full Name is required.', 'danger')
            return redirect(url_for('auth.profile'))

        current_user.full_name = full_name

        if new_password:
            if not current_user.check_password(current_password):
                flash('Current password verification failed.', 'danger')
                return redirect(url_for('auth.profile'))

            if new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
                return redirect(url_for('auth.profile'))

            if len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
                return redirect(url_for('auth.profile'))

            current_user.set_password(new_password)
            flash('Password updated successfully.', 'success')

        db.session.commit()
        flash('Profile details updated.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
