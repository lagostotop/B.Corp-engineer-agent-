import redis
import json
from typing import Any, Optional

class RedisCache:
    def __init__(self, url=os.getenv("REDIS_URL", "redis://localhost:6379")):
        self.client = redis.from_url(url)
        self.default_ttl = 3600  # 1 hour
        
    def get(self, key: str) -> Optional[Any]:
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None
        
    def set(self, key: str, value: Any, ttl: int = None):
        self.client.setex(
            key,
            ttl or self.default_ttl,
            json.dumps(value)
        )
        
    def invalidate(self, pattern: str):
        keys = self.client.keys(pattern)
        if keys:
            self.client.delete(*keys)
