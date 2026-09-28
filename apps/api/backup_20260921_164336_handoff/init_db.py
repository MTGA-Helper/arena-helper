import asyncio
from database import engine, Base
from models import *

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[+] All database tables created successfully!")

if __name__ == "__main__":
    asyncio.run(main())
