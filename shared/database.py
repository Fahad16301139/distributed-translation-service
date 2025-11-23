"""
MongoDB Database Module
Handles storage of translations for high availability and resilience
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pymongo import MongoClient, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure
from config import config

logger = logging.getLogger(__name__)


class TranslationDatabase:
    """
    MongoDB database handler for storing translation records.
    Ensures high availability and data resilience.
    """
    
    def __init__(self, uri: str = None, db_name: str = None):
        """
        Initialize MongoDB connection.
        
        Args:
            uri: MongoDB connection URI
            db_name: Database name
        """
        self.uri = uri or config.MONGODB_URI
        self.db_name = db_name or config.MONGODB_DB_NAME
        self.client: Optional[MongoClient] = None
        self.db = None
        self.translations_collection = None
        
        self.connect()
    
    def connect(self):
        """Establish connection to MongoDB"""
        try:
            self.client = MongoClient(
                self.uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            # Test connection
            self.client.admin.command('ping')
            
            self.db = self.client[self.db_name]
            self.translations_collection = self.db['translations']
            
            # Create indexes for better query performance
            self.translations_collection.create_index([('translation_id', DESCENDING)])
            self.translations_collection.create_index([('user_id', DESCENDING)])
            self.translations_collection.create_index([('created_at', DESCENDING)])
            
            logger.info(f"Connected to MongoDB: {self.db_name}")
            
        except ConnectionFailure as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    def disconnect(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")
    
    def save_translation(
        self,
        translation_id: str,
        original_text: str,
        translated_text: str,
        source_language: str,
        target_language: str,
        user_id: str = None,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Save a translation record to the database.
        
        Args:
            translation_id: Unique translation identifier
            original_text: Original text
            translated_text: Translated text
            source_language: Source language code
            target_language: Target language code
            user_id: User who requested the translation
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        document = {
            'translation_id': translation_id,
            'original_text': original_text,
            'translated_text': translated_text,
            'source_language': source_language,
            'target_language': target_language,
            'user_id': user_id,
            'metadata': metadata or {},
            'created_at': datetime.utcnow(),
            'status': 'completed'
        }
        
        try:
            result = self.translations_collection.insert_one(document)
            logger.info(f"Saved translation {translation_id} to database")
            return str(result.inserted_id)
            
        except OperationFailure as e:
            logger.error(f"Failed to save translation: {str(e)}")
            raise
    
    def get_translation(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a translation by ID.
        
        Args:
            translation_id: Translation identifier
            
        Returns:
            Translation document or None if not found
        """
        try:
            document = self.translations_collection.find_one(
                {'translation_id': translation_id}
            )
            
            if document:
                document['_id'] = str(document['_id'])  # Convert ObjectId to string
                logger.debug(f"Retrieved translation {translation_id}")
            else:
                logger.warning(f"Translation {translation_id} not found")
            
            return document
            
        except OperationFailure as e:
            logger.error(f"Failed to retrieve translation: {str(e)}")
            return None
    
    def get_user_translations(
        self,
        user_id: str,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get all translations for a specific user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of results
            skip: Number of results to skip (for pagination)
            
        Returns:
            List of translation documents
        """
        try:
            cursor = self.translations_collection.find(
                {'user_id': user_id}
            ).sort('created_at', DESCENDING).skip(skip).limit(limit)
            
            translations = list(cursor)
            for doc in translations:
                doc['_id'] = str(doc['_id'])
            
            logger.info(f"Retrieved {len(translations)} translations for user {user_id}")
            return translations
            
        except OperationFailure as e:
            logger.error(f"Failed to retrieve user translations: {str(e)}")
            return []
    
    def update_translation_status(
        self,
        translation_id: str,
        status: str,
        error_message: str = None
    ) -> bool:
        """
        Update translation status.
        
        Args:
            translation_id: Translation identifier
            status: New status (pending, processing, completed, failed)
            error_message: Error message if status is failed
            
        Returns:
            True if update successful, False otherwise
        """
        update_data = {
            'status': status,
            'updated_at': datetime.utcnow()
        }
        
        if error_message:
            update_data['error_message'] = error_message
        
        try:
            result = self.translations_collection.update_one(
                {'translation_id': translation_id},
                {'$set': update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"Updated translation {translation_id} status to {status}")
                return True
            else:
                logger.warning(f"No translation found with ID {translation_id}")
                return False
                
        except OperationFailure as e:
            logger.error(f"Failed to update translation status: {str(e)}")
            return False
    
    def get_translation_stats(self) -> Dict[str, Any]:
        """
        Get translation statistics.
        
        Returns:
            Dictionary with statistics
        """
        try:
            total = self.translations_collection.count_documents({})
            completed = self.translations_collection.count_documents({'status': 'completed'})
            failed = self.translations_collection.count_documents({'status': 'failed'})
            
            return {
                'total_translations': total,
                'completed': completed,
                'failed': failed,
                'success_rate': (completed / total * 100) if total > 0 else 0
            }
            
        except OperationFailure as e:
            logger.error(f"Failed to get translation stats: {str(e)}")
            return {}


# Global database instance
db = TranslationDatabase()

