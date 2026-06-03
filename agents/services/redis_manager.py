import os
import json
import redis
from datetime import datetime

def _clean_none(value):
    """Convert None to empty string for Redis compatibility"""
    if value is None:
        return ""
    return value

class PromptStateManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', 6379)),
            db=0,
            decode_responses=True
        )
    
    def create_prompt_state(self, prompt_id, user_input, thread_id):
        state = {
            'id': str(prompt_id),
            'user_input': str(user_input),
            'thread_id': str(thread_id),
            'status': 'PENDING',
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'response': '',
            'is_pending': 'false',
            'error': ''
        }
        self.redis_client.hset(f"prompt:{prompt_id}", mapping=state)
        self.redis_client.expire(f"prompt:{prompt_id}", 3600)
        return state
    
    def get_prompt_state(self, prompt_id):
        return self.redis_client.hgetall(f"prompt:{prompt_id}")
    
    def update_prompt_state(self, prompt_id, **kwargs):
        kwargs['updated_at'] = datetime.utcnow().isoformat()
        for key, value in kwargs.items():
            if value is None:
                kwargs[key] = ''
            elif isinstance(value, bool):
                kwargs[key] = 'true' if value else 'false'
            else:
                kwargs[key] = str(value)
        self.redis_client.hset(f"prompt:{prompt_id}", mapping=kwargs)
    
    def set_status(self, prompt_id, status):
        self.update_prompt_state(prompt_id, status=status)
    
    def set_response(self, prompt_id, response, is_pending=False):
        self.update_prompt_state(
            prompt_id, 
            response=str(response) if response else '',
            is_pending='true' if is_pending else 'false',
            status='COMPLETED' if not is_pending else 'PENDING_APPROVAL'
        )
    
    def set_error(self, prompt_id, error):
        self.update_prompt_state(
            prompt_id,
            error=str(error) if error else '',
            status='ERROR'
        )
    
    def append_stream(self, prompt_id, chunk):
        self.redis_client.rpush(f"prompt:{prompt_id}:stream", str(chunk))
        self.redis_client.expire(f"prompt:{prompt_id}:stream", 3600)
    
    def get_stream(self, prompt_id):
        return self.redis_client.lrange(f"prompt:{prompt_id}:stream", 0, -1)
    
    def clear_stream(self, prompt_id):
        self.redis_client.delete(f"prompt:{prompt_id}:stream")
    
    def delete_prompt_state(self, prompt_id):
        self.redis_client.delete(f"prompt:{prompt_id}")
        self.redis_client.delete(f"prompt:{prompt_id}:stream")
    
    def get_thread_prompts(self, thread_id):
        keys = self.redis_client.keys(f"prompt:*")
        prompts = []
        for key in keys:
            state = self.redis_client.hgetall(key)
            if state.get('thread_id') == thread_id:
                prompts.append(state)
        return prompts

prompt_state_manager = PromptStateManager()