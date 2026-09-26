from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
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
            flash('Please provide both username/email/mobile and password.', 'danger')
            return render_template('auth/login.html')

        user = AuthService.authenticate_user(identifier, password)
        if user:
            login_user(user, remember=remember)
            AuditService.log_event(
                action='USER_LOGIN',
                resource_type='auth',
                resource_id=str(user.id),
                details=f"User {user.username} logged in successfully via password."
            )
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            AuditService.log_event(
                action='LOGIN_FAILED',
                resource_type='auth',
                details=f"Failed login attempt for identifier: {identifier}"
            )
            flash('Invalid username/email/mobile or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/login-otp', methods=['GET', 'POST'])
def login_otp():
    """Option B: 6-Digit OTP Login Authentication via Email or Mobile."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    identifier = request.args.get('identifier', '') or request.args.get('mobile_number', '') or request.form.get('identifier', '') or request.form.get('mobile_number', '').strip()

    if request.method == 'POST':
        otp_code = request.form.get('otp_code', '').strip()

        if not identifier or not otp_code:
            flash('Please provide your registered Email/Mobile and 6-digit OTP code.', 'danger')
            return render_template('auth/login_otp.html', identifier=identifier, mobile_number=identifier)

        success, message, user = AuthService.verify_login_otp(identifier, otp_code)
        if success and user:
            login_user(user)
            AuditService.log_event(
                action='USER_LOGIN_OTP',
                resource_type='auth',
                resource_id=str(user.id),
                details=f"User {user.username} logged in via 6-digit OTP verification."
            )
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash(message, 'danger')

    return render_template('auth/login_otp.html', identifier=identifier, mobile_number=identifier)


@auth_bp.route('/otp/send', methods=['POST'])
def send_otp():
    """API endpoint to generate and dispatch 6-Digit Login OTP."""
    identifier = request.form.get('identifier', '').strip() or request.form.get('mobile_number', '').strip() or request.form.get('email', '').strip()
    if not identifier:
        return jsonify({'success': False, 'message': 'Registered Email or Mobile number is required.'}), 400

    success, message, dev_otp = AuthService.request_login_otp(identifier)
    return jsonify({
        'success': success,
        'message': message,
        'dev_otp': dev_otp
    }), 200 if success else 400


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        mobile_number = request.form.get('mobile_number', '').strip() or None
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Public registration defaults strictly to warehouse_staff
        role = 'warehouse_staff'

        if not username or not email or not password or not full_name:
            flash('Full Name, Username, Email, and Password are required.', 'danger')
            return render_template('auth/register.html')

        # Email constraint validation
        is_valid_email, email_msg = AuthService.validate_email_format(email)
        if not is_valid_email:
            flash(email_msg, 'danger')
            return render_template('auth/register.html')

        # Password matching constraint
        if password != confirm_password:
            flash('Password and Confirm Password do not match.', 'danger')
            return render_template('auth/register.html')

        # Password complexity constraint: Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 symbol
        is_valid_pwd, pwd_msg = AuthService.validate_password_complexity(password)
        if not is_valid_pwd:
            flash(pwd_msg, 'danger')
            return render_template('auth/register.html')

        try:
            user = AuthService.register_user(
                username=username,
                email=email,
                mobile_number=mobile_number,
                password=password,
                full_name=full_name,
                role=role
            )
            AuditService.log_event(
                action='USER_REGISTERED',
                resource_type='user',
                resource_id=str(user.id),
                details=f"New user registered: {user.username} ({user.role})"
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

        is_valid_email, email_msg = AuthService.validate_email_format(email)
        if not is_valid_email:
            flash(email_msg, 'danger')
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
            flash('New Password and Confirm Password do not match.', 'danger')
            return render_template('auth/reset_password.html', email=email)

        is_valid, msg = AuthService.validate_password_complexity(new_password)
        if not is_valid:
            flash(msg, 'danger')
            return render_template('auth/reset_password.html', email=email)

        success, message = AuthService.verify_and_reset_password(email, otp_code, new_password)
        if success:
            AuditService.log_event(
                action='PASSWORD_RESET',
                resource_type='auth',
                details=f"Password successfully reset via 6-digit OTP for email {email}"
            )
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
        mobile_number = request.form.get('mobile_number', '').strip() or None
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name:
            flash('Full Name is required.', 'danger')
            return redirect(url_for('auth.profile'))

        current_user.full_name = full_name
        current_user.mobile_number = mobile_number

        if new_password:
            if not current_user.check_password(current_password):
                flash('Current password verification failed.', 'danger')
                return redirect(url_for('auth.profile'))

            if new_password != confirm_password:
                flash('New password and Confirm Password do not match.', 'danger')
                return redirect(url_for('auth.profile'))

            is_valid, msg = AuthService.validate_password_complexity(new_password)
            if not is_valid:
                flash(msg, 'danger')
                return redirect(url_for('auth.profile'))

            current_user.set_password(new_password)
            flash('Password updated successfully.', 'success')

        db.session.commit()
        AuditService.log_event(
            action='PROFILE_UPDATED',
            resource_type='user',
            resource_id=str(current_user.id),
            details=f"User {current_user.username} updated profile details."
        )
        flash('Profile details updated.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')


@auth_bp.route('/logout')
@login_required
def logout():
    AuditService.log_event(
        action='USER_LOGOUT',
        resource_type='auth',
        resource_id=str(current_user.id),
        details=f"User {current_user.username} logged out."
    )
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
