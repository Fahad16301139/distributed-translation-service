"""
Translation Service
Uses pre-trained translation models (MarianMT from Hugging Face)
Processes translation requests from the message queue
"""
import logging
import threading
import time
from typing import Dict, Any, Optional
from transformers import MarianMTModel, MarianTokenizer
import torch

from config import config
from shared.message_queue import message_queue
from shared.database import db
from shared.observer_pattern import translation_subject
from shared.circuit_breaker import translation_service_breaker
from shared.ambassador import translation_ambassador, AmbassadorException

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TranslationEngine:
    """
    Translation engine using MarianMT models from Hugging Face.
    Supports multiple language pairs.
    """
    
    def __init__(self):
        self.models: Dict[str, MarianMTModel] = {}
        self.tokenizers: Dict[str, MarianTokenizer] = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Translation engine using device: {self.device}")
    
    def _get_model_name(self, source_lang: str, target_lang: str) -> str:
        """
        Get the appropriate MarianMT model name for language pair.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Model name
        """
        # Map of language pairs to MarianMT models
        model_map = {
            ('en', 'de'): 'Helsinki-NLP/opus-mt-en-de',
            ('en', 'fr'): 'Helsinki-NLP/opus-mt-en-fr',
            ('en', 'es'): 'Helsinki-NLP/opus-mt-en-es',
            ('en', 'it'): 'Helsinki-NLP/opus-mt-en-it',
            ('en', 'pt'): 'Helsinki-NLP/opus-mt-en-pt',
            ('en', 'ru'): 'Helsinki-NLP/opus-mt-en-ru',
            ('en', 'zh'): 'Helsinki-NLP/opus-mt-en-zh',
            ('en', 'ja'): 'Helsinki-NLP/opus-mt-en-jap',
            ('de', 'en'): 'Helsinki-NLP/opus-mt-de-en',
            ('fr', 'en'): 'Helsinki-NLP/opus-mt-fr-en',
            ('es', 'en'): 'Helsinki-NLP/opus-mt-es-en',
            ('it', 'en'): 'Helsinki-NLP/opus-mt-it-en',
        }
        
        return model_map.get((source_lang, target_lang), 'Helsinki-NLP/opus-mt-en-de')
    
    def load_model(self, source_lang: str, target_lang: str) -> bool:
        """
        Load translation model for a language pair.
        
        Args:
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            True if loaded successfully, False otherwise
        """
        model_key = f"{source_lang}-{target_lang}"
        
        if model_key in self.models:
            logger.debug(f"Model {model_key} already loaded")
            return True
        
        try:
            model_name = self._get_model_name(source_lang, target_lang)
            logger.info(f"Loading model: {model_name}")
            
            tokenizer = MarianTokenizer.from_pretrained(model_name)
            model = MarianMTModel.from_pretrained(model_name)
            model.to(self.device)
            model.eval()
            
            self.tokenizers[model_key] = tokenizer
            self.models[model_key] = model
            
            logger.info(f"Model {model_key} loaded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {model_key}: {str(e)}")
            return False
    
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        use_external_api: bool = False
    ) -> Optional[str]:
        """
        Translate text from source to target language.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            use_external_api: Fallback to external API if local fails
            
        Returns:
            Translated text or None if translation fails
        """
        # Try local model first
        try:
            result = translation_service_breaker.call(
                self._translate_local,
                text,
                source_lang,
                target_lang
            )
            
            if result:
                return result
                
        except Exception as e:
            logger.warning(f"Local translation failed: {str(e)}")
        
        # Fallback to external API if configured and local fails
        if use_external_api and config.GOOGLE_TRANSLATE_API_KEY:
            try:
                logger.info("Attempting external API translation")
                result = translation_ambassador.translate(text, source_lang, target_lang)
                return result.get('translated_text')
                
            except AmbassadorException as e:
                logger.error(f"External API translation failed: {str(e)}")
        
        return None
    
    def _translate_local(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Optional[str]:
        """
        Translate using local MarianMT model.
        
        Args:
            text: Text to translate
            source_lang: Source language code
            target_lang: Target language code
            
        Returns:
            Translated text or None
        """
        model_key = f"{source_lang}-{target_lang}"
        
        # Load model if not already loaded
        if model_key not in self.models:
            if not self.load_model(source_lang, target_lang):
                raise Exception(f"Failed to load model for {model_key}")
        
        tokenizer = self.tokenizers[model_key]
        model = self.models[model_key]
        
        try:
            # Tokenize input
            inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate translation
            with torch.no_grad():
                translated = model.generate(**inputs)
            
            # Decode output
            translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)
            
            logger.debug(f"Translated: {text[:50]}... -> {translated_text[:50]}...")
            return translated_text
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            raise


class TranslationWorker:
    """
    Worker that processes translation requests from the message queue.
    """
    
    def __init__(self):
        self.engine = TranslationEngine()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the translation worker"""
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_requests)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        logger.info("Translation worker started")
    
    def stop(self):
        """Stop the translation worker"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Translation worker stopped")
    
    def _process_requests(self):
        """Process translation requests from the message queue"""
        logger.info("Worker thread started, listening for translation requests")
        
        def handle_translation_request(data: Dict[str, Any]):
            """Handle a single translation request"""
            translation_id = data.get('translation_id')
            text = data.get('text')
            source_lang = data.get('source_language')
            target_lang = data.get('target_language')
            user_id = data.get('user_id')
            metadata = data.get('metadata', {})
            
            logger.info(f"Processing translation request {translation_id}")
            
            try:
                # Update status to processing
                db.update_translation_status(translation_id, 'processing')
                
                # Perform translation
                translated_text = self.engine.translate(
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    use_external_api=True  # Enable fallback to external API
                )
                
                if not translated_text:
                    raise Exception("Translation returned empty result")
                
                # Save to database
                db.save_translation(
                    translation_id=translation_id,
                    original_text=text,
                    translated_text=translated_text,
                    source_language=source_lang,
                    target_language=target_lang,
                    user_id=user_id,
                    metadata=metadata
                )
                
                # Cache the translation
                message_queue.cache_translation(
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    translated_text=translated_text
                )
                
                # Notify observers (Observer Pattern)
                translation_data = {
                    'translation_id': translation_id,
                    'original_text': text,
                    'translated_text': translated_text,
                    'source_language': source_lang,
                    'target_language': target_lang,
                    'user_id': user_id,
                    'metadata': metadata
                }
                
                translation_subject.translation_completed(translation_data)
                
                # Publish result to message queue
                message_queue.publish_translation_result(
                    translation_id=translation_id,
                    original_text=text,
                    translated_text=translated_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    user_id=user_id,
                    metadata=metadata
                )
                
                logger.info(f"Translation {translation_id} completed successfully")
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Translation {translation_id} failed: {error_msg}")
                
                # Update status to failed
                db.update_translation_status(translation_id, 'failed', error_msg)
        
        # Subscribe to translation requests
        try:
            message_queue.subscribe_to_requests(handle_translation_request)
        except Exception as e:
            logger.error(f"Worker thread error: {str(e)}")
            time.sleep(5)  # Wait before attempting to reconnect


def main():
    """Main entry point for the translation service"""
    logger.info("Starting Translation Service")
    
    # Create and start translation worker
    worker = TranslationWorker()
    worker.start()
    
    try:
        # Keep the service running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down Translation Service")
        worker.stop()


if __name__ == '__main__':
    main()

