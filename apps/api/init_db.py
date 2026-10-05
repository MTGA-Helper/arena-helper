import asyncio
from apps.api.database import engine, Base
from apps.api.models import *

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] All database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(main())
