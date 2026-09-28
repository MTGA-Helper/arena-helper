import asyncio
from database import AsyncSessionLocal
from models import User, WildcardInventory

async def seed_user():
    async with AsyncSessionLocal() as session:
        user = User(email='test@test.com', hashed_password='fakepassword')
        session.add(user)
        await session.flush()
        wildcards = WildcardInventory(user_id=user.id, common=99, uncommon=99, rare=20, mythic=10)
        session.add(wildcards)
        await session.commit()
        print('[+] Test user and wildcard inventory created successfully!')

if __name__ == "__main__":
    asyncio.run(seed_user())
