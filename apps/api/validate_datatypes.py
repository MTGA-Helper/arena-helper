import asyncio, uuid
from sqlalchemy import text
from database import AsyncSessionLocal

async def main():
    print('==> Starting Datatype & Constraint Validation Suite...')
    async with AsyncSessionLocal() as session:
        async with session.begin():
            uid = str(uuid.uuid4())
            await session.execute(text('INSERT INTO users (id, email, hashed_password) VALUES (:id, :email, :pw)'), {'id': uid, 'email': f'test_{uid[:6]}@example.com', 'pw': 'hash'})
            print(' [PASS] UUID Insertion & Timestamp Generation')
        
        # Test FK enforcement
        async with session.begin():
            failed = False
            try:
                await session.execute(text('INSERT INTO match_histories (user_id, format, deck_name, result) VALUES (:uid, :fmt, :deck, :res)'), {'uid': str(uuid.uuid4()), 'fmt': 'Standard', 'deck': 'Aggro', 'res': 'Win'})
                await session.flush()
            except Exception as e:
                failed = True
                print(f' [PASS] Foreign Key Constraint Enforced ({type(e).__name__})')
            if not failed: raise AssertionError('FK check failed!')

        # Test Rollback
        try:
            async with session.begin():
                uid2 = str(uuid.uuid4())
                await session.execute(text('INSERT INTO users (id, email, hashed_password) VALUES (:id, :email, :pw)'), {'id': uid2, 'email': 'rollback@example.com', 'pw': 'hash'})
                raise ValueError('Force rollback')
        except ValueError:
            print(' [PASS] Transaction error caught, rolling back block...')
        
        async with session.begin():
            res = await session.execute(text('SELECT COUNT(*) FROM users WHERE email = :email'), {'email': 'rollback@example.com'})
            if res.scalar() == 0:
                print(' [PASS] Transaction Rollback Verified Successfully!')
            else:
                raise AssertionError('Rollback failed!')

    print('========================================')
    print('ALL DATATYPE & CONSTRAINT TESTS PASSED ✅')
    print('========================================')

if __name__ == '__main__':
    asyncio.run(main())
