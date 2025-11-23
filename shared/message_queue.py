"""
Redis Message Queue Module
Asynchronous communication between services
"""
import json
import logging
import uuid
from typing import Dict, Any, Callable, Optional
import redis
from config import config
from shared.circuit_breaker import message_queue_breaker

logger = logging.getLogger(__name__)


class MessageQueue:
    """
    Redis-based message queue for asynchronous service communication.
    Supports pub/sub and task queue patterns.
    """
    
    def __init__(self, redis_url: str = None):
        """
        Initialize Redis message queue.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url or config.REDIS_URL
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        
        self.connect()
    
    def connect(self):
        """Establish connection to Redis"""
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis message queue")
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            raise
    
    def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            self.redis_client.close()
            logger.info("Disconnected from Redis")
    
    def publish_translation_request(
        self,
        translation_id: str,
        text: str,
        source_lang: str,
        target_lang: str,
        user_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Publish a translation request to the queue.
        
        Args:
            translation_id: Unique translation identifier
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            user_id: User requesting the translation
            metadata: Additional metadata
            
        Returns:
            True if published successfully, False otherwise
        """
        message = {
            'translation_id': translation_id,
            'text': text,
            'source_language': source_lang,
            'target_language': target_lang,
            'user_id': user_id,
            'metadata': metadata or {}
        }
        
        try:
            # Use circuit breaker to protect against Redis failures
            result = message_queue_breaker.call(
                self._publish_message,
                channel='translation_requests',
                message=message
            )
            
            logger.info(f"Published translation request {translation_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to publish translation request: {str(e)}")
            return False
    
    def _publish_message(self, channel: str, message: Dict[str, Any]) -> bool:
        """Internal method to publish message to Redis channel"""
        message_json = json.dumps(message)
        subscribers = self.redis_client.publish(channel, message_json)
        logger.debug(f"Message published to {channel}, {subscribers} subscribers")
        return True
    
    def publish_translation_result(
        self,
        translation_id: str,
        original_text: str,
        translated_text: str,
        source_lang: str,
        target_lang: str,
        user_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Publish a translation result to the feedback channel.
        
        Args:
            translation_id: Translation identifier
            original_text: Original text
            translated_text: Translated text
            source_lang: Source language code
            target_lang: Target language code
            user_id: User ID
            metadata: Additional metadata
            
        Returns:
            True if published successfully, False otherwise
        """
        message = {
            'translation_id': translation_id,
            'original_text': original_text,
            'translated_text': translated_text,
            'source_language': source_lang,
            'target_language': target_lang,
            'user_id': user_id,
            'metadata': metadata or {},
            'status': 'completed'
        }
        
        try:
            result = message_queue_breaker.call(
                self._publish_message,
                channel='translation_results',
                message=message
            )
            
            logger.info(f"Published translation result {translation_id}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to publish translation result: {str(e)}")
            return False
    
    def subscribe_to_requests(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to translation requests channel.
        
        Args:
            callback: Function to call when a message is received
        """
        self._subscribe_to_channel('translation_requests', callback)
    
    def subscribe_to_results(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Subscribe to translation results channel.
        
        Args:
            callback: Function to call when a message is received
        """
        self._subscribe_to_channel('translation_results', callback)
    
    def _subscribe_to_channel(self, channel: str, callback: Callable[[Dict[str, Any]], None]):
        """
        Internal method to subscribe to a Redis channel.
        
        Args:
            channel: Channel name
            callback: Callback function
        """
        try:
            self.pubsub = self.redis_client.pubsub()
            self.pubsub.subscribe(channel)
            
            logger.info(f"Subscribed to channel: {channel}")
            
            for message in self.pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        logger.debug(f"Received message from {channel}: {data.get('translation_id')}")
                        callback(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode message: {str(e)}")
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        
        except Exception as e:
            logger.error(f"Subscription error: {str(e)}")
            raise
    
    def push_to_queue(self, queue_name: str, data: Dict[str, Any]) -> bool:
        """
        Push data to a Redis list (queue).
        
        Args:
            queue_name: Queue name
            data: Data to push
            
        Returns:
            True if successful, False otherwise
        """
        try:
            message_json = json.dumps(data)
            result = message_queue_breaker.call(
                self.redis_client.rpush,
                queue_name,
                message_json
            )
            logger.debug(f"Pushed to queue {queue_name}: {result}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to push to queue: {str(e)}")
            return False
    
    def pop_from_queue(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """
        Pop data from a Redis list (queue).
        
        Args:
            queue_name: Queue name
            timeout: Blocking timeout in seconds (0 = blocking)
            
        Returns:
            Data dictionary or None
        """
        try:
            result = self.redis_client.blpop(queue_name, timeout=timeout)
            
            if result:
                _, message_json = result
                data = json.loads(message_json)
                logger.debug(f"Popped from queue {queue_name}")
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to pop from queue: {str(e)}")
            return None
    
    def get_queue_length(self, queue_name: str) -> int:
        """
        Get the length of a queue.
        
        Args:
            queue_name: Queue name
            
        Returns:
            Queue length
        """
        try:
            return self.redis_client.llen(queue_name)
        except Exception as e:
            logger.error(f"Failed to get queue length: {str(e)}")
            return 0
    
    def cache_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        translated_text: str,
        ttl: int = 3600
    ) -> bool:
        """
        Cache a translation result for quick lookup.
        
        Args:
            text: Original text
            source_lang: Source language
            target_lang: Target language
            translated_text: Translated text
            ttl: Time to live in seconds
            
        Returns:
            True if cached successfully, False otherwise
        """
        cache_key = f"translation:{source_lang}:{target_lang}:{hash(text)}"
        
        try:
            self.redis_client.setex(
                cache_key,
                ttl,
                translated_text
            )
            logger.debug(f"Cached translation: {cache_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache translation: {str(e)}")
            return False
    
    def get_cached_translation(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[str]:
        """
        Get a cached translation if available.
        
        Args:
            text: Original text
            source_lang: Source language
            target_lang: Target language
            
        Returns:
            Cached translated text or None
        """
        cache_key = f"translation:{source_lang}:{target_lang}:{hash(text)}"
        
        try:
            result = self.redis_client.get(cache_key)
            
            if result:
                logger.debug(f"Cache hit: {cache_key}")
                return result
            else:
                logger.debug(f"Cache miss: {cache_key}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get cached translation: {str(e)}")
            return None


# Global message queue instance
message_queue = MessageQueue()

