import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import asyncio
from .services.redis_manager import prompt_state_manager

class AgentConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.prompt_id = None
        await self.accept()
    
    async def disconnect(self, close_code):
        if self.prompt_id:
            await self.leave_group(self.prompt_id)
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'init':
            self.prompt_id = data.get('prompt_id')
            await self.join_group(self.prompt_id)
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'prompt_id': self.prompt_id
            }))
        
        elif message_type == 'poll':
            prompt_id = data.get('prompt_id')
            state = await self.get_prompt_state(prompt_id)
            await self.send(text_data=json.dumps({
                'type': 'state_update',
                'state': state
            }))
        
        elif message_type == 'action':
            await self.handle_action(data)
    
    async def handle_action(self, data):
        from .views import process_action
        prompt_id = data.get('prompt_id')
        action = data.get('action')
        user_input = data.get('user_input', '')
        
        state = await self.get_prompt_state(prompt_id)
        if not state:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Prompt not found'
            }))
            return
        
        result = await process_action(prompt_id, user_input, action)
        await self.send(text_data=json.dumps({
            'type': 'response',
            'response': result.get('response'),
            'is_pending': result.get('is_pending', False)
        }))
    
    @database_sync_to_async
    def get_prompt_state(self, prompt_id):
        return prompt_state_manager.get_prompt_state(prompt_id)
    
    async def join_group(self, prompt_id):
        await self.channel_layer.group_add(
            f"prompt_{prompt_id}",
            self.channel_name
        )
    
    async def leave_group(self, prompt_id):
        await self.channel_layer.group_discard(
            f"prompt_{prompt_id}",
            self.channel_name
        )
    
    async def prompt_update(self, event):
        await self.send(text_data=json.dumps(event['data']))
    
    async def stream_chunk(self, event):
        await self.send(text_data=json.dumps({
            'type': 'stream',
            'chunk': event['chunk']
        }))