import os

os.environ["SWITCHBOARD_ENV"] = "dev"
os.environ["SWITCHBOARD_DEV_WEBHOOK_BYPASS"] = "0"
os.environ["SWITCHBOARD_INTERNAL_TOKEN"] = "test-internal-token"
os.environ["SWITCHBOARD_CORS_ORIGINS"] = "http://localhost:5173"
os.environ["MEDIA_GATEWAY_PUBLIC_WS"] = "ws://localhost:8001/v1/streams"
os.environ["DATABASE_URL"] = "postgresql://switchboard:switchboard@localhost:5432/switchboard"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
