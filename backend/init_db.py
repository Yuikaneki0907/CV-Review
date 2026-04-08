"""Create all database tables from SQLAlchemy models."""
import asyncio
from app.infrastructure.database.models import Base
from app.infrastructure.database.session import engine


async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ All tables created successfully!")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init())
