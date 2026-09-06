import redis
from config import config

# Global Redis client instance
redis_client = redis.Redis.from_url(config.redis_url, decode_responses=True)
