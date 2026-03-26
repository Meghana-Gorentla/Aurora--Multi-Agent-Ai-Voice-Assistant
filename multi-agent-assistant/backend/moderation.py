# backend/moderation.py
"""
Content Moderation Layer using ToxicChat T5 Model
Integrates with the multi-personality AI assistant to filter toxic content
"""

from typing import Dict, Literal
import logging

logger = logging.getLogger(__name__)

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False


class ToxicChatModerator:
    """
    Content moderation using ToxicChat T5 model.
    Detects policy-violating toxic content in user messages and agent responses.
    """
    
    def __init__(self):
        """Initialize the ToxicChat model and tokenizer."""
        if not HAS_TRANSFORMERS:
            logger.warning("Transformers not installed. Moderation disabled (all content allowed).")
            self.tokenizer = None
            self.model = None
            return
        try:
            logger.info("Loading ToxicChat moderation model...")
            # Use t5-large tokenizer as the model repo doesn't include tokenizer files
            self.tokenizer = AutoTokenizer.from_pretrained("t5-large")
            self.model = AutoModelForSeq2SeqLM.from_pretrained("lmsys/toxicchat-t5-large-v1.0")
            logger.info("✓ ToxicChat moderation model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load ToxicChat model: {e}")
            raise
    
    def check_toxicity(self, text: str) -> Dict[str, any]:
        """
        Check if the given text contains toxic content.
        
        Args:
            text: The text to analyze
            
        Returns:
            Dictionary containing:
                - is_toxic (bool): Whether content is toxic
                - confidence (str): Model's raw output
                - action (str): Recommended action ('allow', 'flag', 'block')
        """
        if self.model is None:
            return {'is_toxic': False, 'confidence': 'disabled', 'action': 'allow', 'text_preview': text[:100] + '...' if len(text) > 100 else text}
        try:
            # Format input with required prefix
            prefix = "ToxicChat: "
            inputs = self.tokenizer.encode(prefix + text, return_tensors="pt")
            
            # Generate prediction
            outputs = self.model.generate(inputs, max_length=10)
            result = self.tokenizer.decode(outputs[0], skip_special_tokens=True).strip().lower()
            
            # Interpret result: 'positive' = toxic, 'negative' = non-toxic
            is_toxic = 'positive' in result
            
            # Determine action based on toxicity
            if is_toxic:
                action = 'block'  # Block toxic content
            else:
                action = 'allow'  # Allow non-toxic content
            
            return {
                'is_toxic': is_toxic,
                'confidence': result,
                'action': action,
                'text_preview': text[:100] + '...' if len(text) > 100 else text
            }
            
        except Exception as e:
            logger.error(f"Error checking toxicity: {e}")
            # Fail-safe: allow content if moderation fails (prevent blocking legitimate content)
            return {
                'is_toxic': False,
                'confidence': 'error',
                'action': 'allow',
                'error': str(e)
            }
    
    def moderate_conversation(self, user_message: str, agent_response: str = None) -> Dict[str, any]:
        """
        Moderate both user input and agent response.
        
        Args:
            user_message: The user's message to check
            agent_response: Optional agent response to check
            
        Returns:
            Dictionary containing moderation results for both
        """
        results = {
            'user_input': self.check_toxicity(user_message),
            'agent_response': None
        }
        
        if agent_response:
            results['agent_response'] = self.check_toxicity(agent_response)
        
        # Determine overall action
        if results['user_input']['action'] == 'block':
            results['overall_action'] = 'block_user_input'
            results['message'] = "Your message contains content that violates our content policy. Please rephrase your request."
        elif agent_response and results['agent_response']['action'] == 'block':
            results['overall_action'] = 'block_agent_response'
            results['message'] = "I apologize, but I cannot provide a response to that request as it may contain inappropriate content."
        else:
            results['overall_action'] = 'allow'
            results['message'] = None
        
        return results


# Initialize global moderator instance
_moderator_instance = None

def get_moderator() -> ToxicChatModerator:
    """Get or create the global moderator instance."""
    global _moderator_instance
    if _moderator_instance is None:
        _moderator_instance = ToxicChatModerator()
    return _moderator_instance