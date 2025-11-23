"""
Observer Pattern Implementation for Real-Time Feedback
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Subject(ABC):
    """
    The Subject interface declares methods for managing subscribers (observers).
    """
    
    @abstractmethod
    def attach(self, observer: 'Observer') -> None:
        """Attach an observer to the subject"""
        pass
    
    @abstractmethod
    def detach(self, observer: 'Observer') -> None:
        """Detach an observer from the subject"""
        pass
    
    @abstractmethod
    def notify(self, data: Dict[str, Any]) -> None:
        """Notify all observers about an event"""
        pass


class Observer(ABC):
    """
    The Observer interface declares the update method used by subjects.
    """
    
    @abstractmethod
    def update(self, data: Dict[str, Any]) -> None:
        """Receive update from subject"""
        pass


class TranslationSubject(Subject):
    """
    Concrete Subject that manages translation completion notifications.
    """
    
    def __init__(self):
        self._observers: List[Observer] = []
        self._state: Dict[str, Any] = {}
    
    def attach(self, observer: Observer) -> None:
        """Attach an observer to receive notifications"""
        if observer not in self._observers:
            self._observers.append(observer)
            logger.info(f"Observer {observer.__class__.__name__} attached")
    
    def detach(self, observer: Observer) -> None:
        """Remove an observer from notifications"""
        try:
            self._observers.remove(observer)
            logger.info(f"Observer {observer.__class__.__name__} detached")
        except ValueError:
            logger.warning(f"Observer {observer.__class__.__name__} not found")
    
    def notify(self, data: Dict[str, Any]) -> None:
        """
        Notify all observers about translation completion.
        Data should contain translation_id, original_text, translated_text, etc.
        """
        logger.info(f"Notifying {len(self._observers)} observers about translation completion")
        for observer in self._observers:
            try:
                observer.update(data)
            except Exception as e:
                logger.error(f"Error notifying observer {observer.__class__.__name__}: {str(e)}")
    
    def translation_completed(self, translation_data: Dict[str, Any]) -> None:
        """
        Called when a translation is completed.
        Triggers notification to all observers.
        """
        self._state = translation_data
        logger.info(f"Translation completed for request {translation_data.get('translation_id')}")
        self.notify(translation_data)


class FeedbackObserver(Observer):
    """
    Concrete Observer that handles real-time feedback delivery.
    """
    
    def __init__(self, name: str = "FeedbackObserver"):
        self.name = name
        self.received_translations: List[Dict[str, Any]] = []
    
    def update(self, data: Dict[str, Any]) -> None:
        """
        Receive notification about completed translation.
        Store the translation and trigger feedback delivery.
        """
        logger.info(f"{self.name} received translation update: {data.get('translation_id')}")
        self.received_translations.append(data)
        self.deliver_feedback(data)
    
    def deliver_feedback(self, data: Dict[str, Any]) -> None:
        """
        Deliver the translated text back to the user.
        This method will be called by the Real-Time Feedback Service.
        """
        logger.info(f"Delivering feedback for translation {data.get('translation_id')}")
        # The actual delivery mechanism (WebSocket, SSE, polling, etc.) 
        # will be implemented in the Feedback Service
    
    def get_received_translations(self) -> List[Dict[str, Any]]:
        """Get all received translations"""
        return self.received_translations


# Global translation subject instance
translation_subject = TranslationSubject()

