"""
Real-Time Feedback Service
Sends translated text back to users in real-time
Implements Observer Pattern to monitor translation completion
"""
import logging
import threading
import time
from typing import Dict, Any, List, Optional
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from collections import defaultdict

from config import config
from shared.auth import init_jwt
from shared.rate_limiter import init_rate_limiter, feedback_rate_limit
from shared.message_queue import message_queue
from shared.database import db
from shared.observer_pattern import FeedbackObserver, translation_subject

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

# Store pending translations for real-time delivery
# In production, use Redis or a proper message broker for this
pending_translations: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


class RealTimeFeedbackObserver(FeedbackObserver):
    """
    Custom Feedback Observer that delivers translations in real-time.
    Implements the Observer Pattern.
    """
    
    def __init__(self, name: str = "RealTimeFeedbackObserver"):
        super().__init__(name)
    
    def deliver_feedback(self, data: Dict[str, Any]) -> None:
        """
        Deliver translation feedback to user.
        Stores completed translations for the user to retrieve.
        """
        user_id = data.get('user_id')
        translation_id = data.get('translation_id')
        
        logger.info(f"Delivering feedback for translation {translation_id} to user {user_id}")
        
        # Store the completed translation for the user
        if user_id:
            pending_translations[user_id].append(data)
            
            # Keep only last 100 translations per user
            if len(pending_translations[user_id]) > 100:
                pending_translations[user_id] = pending_translations[user_id][-100:]
        
        # In a production system, you would:
        # - Send via WebSocket to connected clients
        # - Send push notification
        # - Trigger webhook
        # - Emit Server-Sent Event (SSE)


# Create and attach the feedback observer
feedback_observer = RealTimeFeedbackObserver()
translation_subject.attach(feedback_observer)


def start_result_listener():
    """
    Start listening for translation results from message queue.
    Runs in a separate thread.
    """
    def listen():
        logger.info("Feedback service listening for translation results")
        
        def handle_result(data: Dict[str, Any]):
            """Handle translation result from queue"""
            translation_id = data.get('translation_id')
            logger.info(f"Received translation result: {translation_id}")
            
            # Notify the observer (Observer Pattern)
            translation_subject.translation_completed(data)
        
        try:
            message_queue.subscribe_to_results(handle_result)
        except Exception as e:
            logger.error(f"Error in result listener: {str(e)}")
            time.sleep(5)  # Wait before attempting to reconnect
    
    listener_thread = threading.Thread(target=listen)
    listener_thread.daemon = True
    listener_thread.start()
    logger.info("Result listener thread started")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'feedback',
        'timestamp': datetime.utcnow().isoformat(),
        'observers_attached': len(translation_subject._observers)
    }), 200


@app.route('/feedback/<translation_id>', methods=['GET'])
@jwt_required()
@feedback_rate_limit(limiter)
def get_feedback(translation_id):
    """
    Get real-time feedback for a specific translation.
    This endpoint can be polled by clients for updates.
    """
    current_user = get_jwt_identity()
    
    # Check user's pending translations
    user_translations = pending_translations.get(current_user, [])
    
    for translation in user_translations:
        if translation.get('translation_id') == translation_id:
            return jsonify({
                'translation_id': translation_id,
                'status': 'completed',
                'original_text': translation.get('original_text'),
                'translated_text': translation.get('translated_text'),
                'source_language': translation.get('source_language'),
                'target_language': translation.get('target_language'),
                'metadata': translation.get('metadata', {})
            }), 200
    
    # If not in pending, check database
    translation = db.get_translation(translation_id)
    
    if not translation:
        return jsonify({
            'error': 'Not found',
            'message': 'Translation not found'
        }), 404
    
    # Check authorization
    if translation.get('user_id') != current_user:
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Access denied'
        }), 403
    
    status = translation.get('status', 'pending')
    
    response = {
        'translation_id': translation_id,
        'status': status
    }
    
    if status == 'completed':
        response.update({
            'original_text': translation.get('original_text'),
            'translated_text': translation.get('translated_text'),
            'source_language': translation.get('source_language'),
            'target_language': translation.get('target_language')
        })
    elif status == 'failed':
        response['error_message'] = translation.get('error_message')
    
    return jsonify(response), 200


@app.route('/feedback/poll', methods=['GET'])
@jwt_required()
@feedback_rate_limit(limiter)
def poll_all_feedback():
    """
    Poll for all pending translations for the current user.
    Returns all completed translations since last poll.
    """
    current_user = get_jwt_identity()
    
    # Get user's pending translations
    user_translations = pending_translations.get(current_user, [])
    
    if not user_translations:
        return jsonify({
            'translations': [],
            'count': 0,
            'message': 'No pending translations'
        }), 200
    
    # Return and clear pending translations
    translations = user_translations.copy()
    pending_translations[current_user] = []
    
    return jsonify({
        'translations': translations,
        'count': len(translations),
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/feedback/stream/<translation_id>', methods=['GET'])
@jwt_required()
def stream_feedback(translation_id):
    """
    Server-Sent Events (SSE) endpoint for real-time updates.
    Clients can subscribe to this endpoint to receive updates as they happen.
    """
    current_user = get_jwt_identity()
    
    def generate():
        """Generate SSE events"""
        # Send initial connection message
        yield f"data: {{'status': 'connected', 'translation_id': '{translation_id}'}}\n\n"
        
        max_wait = 60  # Maximum wait time in seconds
        elapsed = 0
        
        while elapsed < max_wait:
            # Check if translation is complete
            user_translations = pending_translations.get(current_user, [])
            
            for translation in user_translations:
                if translation.get('translation_id') == translation_id:
                    # Send completion event
                    import json
                    yield f"data: {json.dumps(translation)}\n\n"
                    
                    # Remove from pending
                    user_translations.remove(translation)
                    return
            
            # Check database
            translation = db.get_translation(translation_id)
            if translation and translation.get('status') in ['completed', 'failed']:
                import json
                yield f"data: {json.dumps({'translation_id': translation_id, 'status': translation['status']})}\n\n"
                return
            
            time.sleep(1)
            elapsed += 1
            
            # Send heartbeat every 10 seconds
            if elapsed % 10 == 0:
                yield f"data: {{'status': 'waiting', 'elapsed': {elapsed}}}\n\n"
        
        # Timeout
        yield f"data: {{'status': 'timeout', 'message': 'Translation timed out'}}\n\n"
    
    return app.response_class(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/observer/stats', methods=['GET'])
@jwt_required()
def observer_stats():
    """
    Get statistics about the observer pattern implementation.
    Shows how many observers are attached and translations processed.
    """
    return jsonify({
        'observers_attached': len(translation_subject._observers),
        'observer_names': [obs.name for obs in translation_subject._observers],
        'translations_received': len(feedback_observer.received_translations),
        'recent_translations': feedback_observer.received_translations[-10:] if feedback_observer.received_translations else []
    }), 200


if __name__ == '__main__':
    logger.info(f"Starting Real-Time Feedback Service on port {config.FEEDBACK_SERVICE_PORT}")
    
    # Start the result listener in background
    start_result_listener()
    
    # Start Flask app
    app.run(
        host='0.0.0.0',
        port=config.FEEDBACK_SERVICE_PORT,
        debug=False,
        threaded=True
    )

