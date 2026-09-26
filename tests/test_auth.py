import pytest
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.services.auth_service import AuthService
from app.models.user import User, OTPToken

def test_user_registration(app):
    with app.app_context():
        user = AuthService.register_user(
            username='staff1',
            email='staff1@test.com',
            password='secretpassword',
            full_name='Staff Member',
            role='warehouse_staff'
        )
        assert user.id is not None
        assert user.check_password('secretpassword') is True
        assert user.check_password('wrongpassword') is False
        assert user.role == 'warehouse_staff'
        assert user.is_manager is False

        # Duplicate username must fail
        with pytest.raises(ValueError, match="already registered"):
            AuthService.register_user(
                username='staff1',
                email='different@test.com',
                password='anotherpassword',
                full_name='Another Staff'
            )

        # Duplicate email must fail
        with pytest.raises(ValueError, match="already registered"):
            AuthService.register_user(
                username='distinct_user',
                email='staff1@test.com',
                password='anotherpassword',
                full_name='Another Staff'
            )


def test_user_authentication(app):
    with app.app_context():
        AuthService.register_user(
            username='authuser',
            email='authuser@test.com',
            password='mypassword',
            full_name='Auth User',
            role='inventory_manager'
        )

        # Success with username
        u1 = AuthService.authenticate_user('authuser', 'mypassword')
        assert u1 is not None
        assert u1.is_manager is True

        # Success with email
        u2 = AuthService.authenticate_user('authuser@test.com', 'mypassword')
        assert u2 is not None

        # Fail with wrong password
        u3 = AuthService.authenticate_user('authuser', 'wrong')
        assert u3 is None

        # Fail with non-existent user
        u4 = AuthService.authenticate_user('nonexistent', 'mypassword')
        assert u4 is None


def test_otp_password_reset_and_expiration(app):
    with app.app_context():
        user = AuthService.register_user(
            username='resetuser',
            email='reset@test.com',
            password='oldpassword',
            full_name='Reset User'
        )

        # Request OTP for non-existent email
        bad_ok, bad_msg, _ = AuthService.request_password_reset_otp('unknown@example.com')
        assert bad_ok is False

        # Request valid OTP
        success, msg, otp = AuthService.request_password_reset_otp('reset@test.com')
        assert success is True
        assert otp is not None
        assert len(otp) == 6

        # Test OTP Expiration
        token = OTPToken.query.filter_by(user_id=user.id, otp_code=otp).first()
        assert token.is_valid() is True

        # Simulate expired token
        token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        assert token.is_valid() is False

        expired_ok, expired_msg = AuthService.verify_and_reset_password('reset@test.com', otp, 'newsupersecret')
        assert expired_ok is False
        assert "expired" in expired_msg.lower() or "invalid" in expired_msg.lower()

        # Request fresh OTP
        success2, msg2, fresh_otp = AuthService.request_password_reset_otp('reset@test.com')
        assert success2 is True

        # Reset with correct OTP
        reset_ok, reset_msg = AuthService.verify_and_reset_password('reset@test.com', fresh_otp, 'NewPassword123!')
        assert reset_ok is True

        # Check login with new password
        u = AuthService.authenticate_user('reset@test.com', 'NewPassword123!')
        assert u is not None

        # Re-using OTP should fail
        fail_ok, _ = AuthService.verify_and_reset_password('reset@test.com', fresh_otp, 'AnotherPassword123!')
        assert fail_ok is False


def test_auth_routes_and_role_protection(app, client):
    with app.app_context():
        # Create a manager and a warehouse staff
        manager = AuthService.register_user(
            username='mgr_route',
            email='mgr_route@test.com',
            password='password123',
            full_name='Manager Route',
            role='inventory_manager'
        )
        staff = AuthService.register_user(
            username='staff_route',
            email='staff_route@test.com',
            password='password123',
            full_name='Staff Route',
            role='warehouse_staff'
        )

    # 1. Protected route redirects unauthenticated user to login
    resp = client.get('/', follow_redirects=False)
    assert resp.status_code == 302
    assert '/auth/login' in resp.headers['Location']

    # 2. Login via HTTP POST
    login_resp = client.post('/auth/login', data={
        'identifier': 'staff_route',
        'password': 'password123'
    }, follow_redirects=True)
    assert login_resp.status_code == 200
    assert b'Welcome back, Staff Route' in login_resp.data

    # 3. Warehouse Staff attempting manager-only route (/warehouses/new POST or /products/new GET)
    # /products/new GET requires manager
    prod_new_resp = client.get('/products/new', follow_redirects=True)
    assert b'Access denied' in prod_new_resp.data

    # 4. Logout
    logout_resp = client.get('/auth/logout', follow_redirects=True)
    assert logout_resp.status_code == 200
    assert b'You have been logged out' in logout_resp.data

    # 5. Accessing protected page after logout redirects to login
    resp_after_logout = client.get('/products/', follow_redirects=False)
    assert resp_after_logout.status_code == 302
    assert '/auth/login' in resp_after_logout.headers['Location']

    # 6. Login as manager
    mgr_login = client.post('/auth/login', data={
        'identifier': 'mgr_route',
        'password': 'password123'
    }, follow_redirects=True)
    assert mgr_login.status_code == 200

    # Manager can access manager-only route
    mgr_prod_resp = client.get('/products/new', follow_redirects=True)
    assert mgr_prod_resp.status_code == 200
    assert b'Create New Product' in mgr_prod_resp.data
