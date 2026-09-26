from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login', next=request.url))
        if not current_user.is_manager:
            flash('Access denied: This action requires Inventory Manager privileges.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    return decorated_function
