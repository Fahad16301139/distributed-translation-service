"""
JWT Authentication Module
Secures API access and ensures authorized requests
"""
import logging
from datetime import timedelta
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    verify_jwt_in_request
)
from config import config

logger = logging.getLogger(__name__)


def init_jwt(app):
    """Initialize JWT manager with Flask app"""
    app.config['JWT_SECRET_KEY'] = config.JWT_SECRET_KEY
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(seconds=config.JWT_ACCESS_TOKEN_EXPIRES)
    jwt = JWTManager(app)
    
    @jwt.unauthorized_loader
    def unauthorized_callback(callback):
        return jsonify({
            'error': 'Missing or invalid authentication token',
            'message': 'Please provide a valid JWT token'
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(callback):
        return jsonify({
            'error': 'Invalid authentication token',
            'message': 'The token is invalid or expired'
        }), 401
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': 'Token has expired',
            'message': 'Please request a new token'
        }), 401
    
    return jwt


def generate_token(user_id: str, additional_claims: dict = None) -> str:
    """
    Generate JWT access token for a user.
    
    Args:
        user_id: Unique user identifier
        additional_claims: Additional data to include in token
        
    Returns:
        JWT token string
    """
    claims = additional_claims or {}
    token = create_access_token(identity=user_id, additional_claims=claims)
    logger.info(f"Generated token for user: {user_id}")
    return token


def jwt_required_custom(fn):
    """
    Custom decorator for JWT authentication.
    Validates JWT token and extracts user identity.
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            current_user = get_jwt_identity()
            logger.debug(f"Authenticated request from user: {current_user}")
            return fn(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Authentication failed: {str(e)}")
            return jsonify({
                'error': 'Authentication required',
                'message': str(e)
            }), 401
    
    return wrapper


def get_current_user() -> str:
    """
    Get the current authenticated user's identity.
    
    Returns:
        User ID from JWT token
    """
    try:
        verify_jwt_in_request()
        return get_jwt_identity()
    except Exception as e:
        logger.warning(f"Failed to get current user: {str(e)}")
        return None


# Simple user validation (in production, use a proper user database)
DEMO_USERS = {
    'demo_user': 'demo_password',
    'test_user': 'test_password',
    'admin': 'admin_password'
}


def validate_user_credentials(username: str, password: str) -> bool:
    """
    Validate user credentials.
    
    Args:
        username: Username
        password: Password
        
    Returns:
        True if credentials are valid, False otherwise
    """
    return DEMO_USERS.get(username) == password

