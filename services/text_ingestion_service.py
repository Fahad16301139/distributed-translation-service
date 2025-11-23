"""
Text Ingestion Service
Receives incoming text for translation via REST API
"""
import uuid
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime

from config import config
from shared.auth import init_jwt, generate_token, validate_user_credentials, get_current_user
from shared.rate_limiter import init_rate_limiter, translation_rate_limit
from shared.message_queue import message_queue
from shared.database import db

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Initialize JWT authentication
jwt = init_jwt(app)

# Initialize rate limiter
limiter = init_rate_limiter(app)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'text-ingestion',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    """
    User authentication endpoint.
    Returns JWT token for authenticated users.
    """
    data = request.get_json()
    
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({
            'error': 'Missing credentials',
            'message': 'Username and password are required'
        }), 400
    
    username = data['username']
    password = data['password']
    
    if validate_user_credentials(username, password):
        token = generate_token(username)
        logger.info(f"User {username} authenticated successfully")
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user_id': username
        }), 200
    else:
        logger.warning(f"Failed login attempt for user {username}")
        return jsonify({
            'error': 'Invalid credentials',
            'message': 'Username or password is incorrect'
        }), 401


@app.route('/translate', methods=['POST'])
@jwt_required()
@translation_rate_limit(limiter)
def translate_text():
    """
    Main translation endpoint.
    Receives text and publishes translation request to message queue.
    """
    current_user = get_jwt_identity()
    data = request.get_json()
    
    # Validate request
    if not data:
        return jsonify({
            'error': 'Invalid request',
            'message': 'Request body is required'
        }), 400
    
    text = data.get('text')
    source_lang = data.get('source_language', 'en')
    target_lang = data.get('target_language', 'de')
    
    if not text:
        return jsonify({
            'error': 'Missing text',
            'message': 'Text field is required'
        }), 400
    
    if len(text) > config.MAX_LENGTH:
        return jsonify({
            'error': 'Text too long',
            'message': f'Maximum text length is {config.MAX_LENGTH} characters'
        }), 400
    
    # Check cache first
    cached_translation = message_queue.get_cached_translation(text, source_lang, target_lang)
    if cached_translation:
        logger.info(f"Cache hit for user {current_user}")
        return jsonify({
            'translation_id': str(uuid.uuid4()),
            'translated_text': cached_translation,
            'source_language': source_lang,
            'target_language': target_lang,
            'cached': True,
            'status': 'completed'
        }), 200
    
    # Generate unique translation ID
    translation_id = str(uuid.uuid4())
    
    # Publish translation request to message queue
    success = message_queue.publish_translation_request(
        translation_id=translation_id,
        text=text,
        source_lang=source_lang,
        target_lang=target_lang,
        user_id=current_user,
        metadata={
            'request_time': datetime.utcnow().isoformat(),
            'client_ip': request.remote_addr
        }
    )
    
    if not success:
        logger.error(f"Failed to publish translation request {translation_id}")
        return jsonify({
            'error': 'Service unavailable',
            'message': 'Failed to process translation request'
        }), 503
    
    logger.info(f"Translation request {translation_id} published by user {current_user}")
    
    return jsonify({
        'translation_id': translation_id,
        'status': 'pending',
        'message': 'Translation request received',
        'source_language': source_lang,
        'target_language': target_lang
    }), 202


@app.route('/translation/<translation_id>', methods=['GET'])
@jwt_required()
def get_translation_status(translation_id):
    """
    Get translation status and result.
    Allows clients to poll for translation completion.
    """
    current_user = get_jwt_identity()
    
    # Retrieve translation from database
    translation = db.get_translation(translation_id)
    
    if not translation:
        return jsonify({
            'error': 'Not found',
            'message': 'Translation not found'
        }), 404
    
    # Check if user has access to this translation
    if translation.get('user_id') != current_user:
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Access denied'
        }), 403
    
    response_data = {
        'translation_id': translation['translation_id'],
        'status': translation.get('status', 'pending'),
        'source_language': translation.get('source_language'),
        'target_language': translation.get('target_language')
    }
    
    if translation.get('status') == 'completed':
        response_data['original_text'] = translation.get('original_text')
        response_data['translated_text'] = translation.get('translated_text')
    
    if translation.get('error_message'):
        response_data['error_message'] = translation['error_message']
    
    return jsonify(response_data), 200


@app.route('/translations/history', methods=['GET'])
@jwt_required()
def get_translation_history():
    """
    Get user's translation history.
    Supports pagination.
    """
    current_user = get_jwt_identity()
    
    limit = request.args.get('limit', 50, type=int)
    skip = request.args.get('skip', 0, type=int)
    
    translations = db.get_user_translations(current_user, limit=limit, skip=skip)
    
    return jsonify({
        'user_id': current_user,
        'count': len(translations),
        'translations': translations
    }), 200


@app.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    """Get system statistics"""
    stats = db.get_translation_stats()
    
    return jsonify({
        'statistics': stats,
        'timestamp': datetime.utcnow().isoformat()
    }), 200


if __name__ == '__main__':
    logger.info(f"Starting Text Ingestion Service on port {config.TEXT_INGESTION_PORT}")
    app.run(
        host='0.0.0.0',
        port=config.TEXT_INGESTION_PORT,
        debug=False
    )

