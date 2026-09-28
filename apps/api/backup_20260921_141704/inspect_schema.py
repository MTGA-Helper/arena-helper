import asyncio
from sqlalchemy import text
from database import AsyncSessionLocal

async def inspect_db():
    print("[*] Inspecting Database Schemas...")
    async with AsyncSessionLocal() as session:
        try:
            # 1. Check users table sample
            users_res = await session.execute(text("SELECT id FROM users LIMIT 1;"))
            user_row = users_res.fetchone()
            print(f"  -> Users Sample ID: {user_row.id if user_row else 'No users found!'} (Type: {type(user_row.id).__name__ if user_row else 'N/A'})")

            # 2. Check wildcard_inventories columns via a limit query or error inspection
            try:
                wc_res = await session.execute(text("SELECT * FROM wildcard_inventories LIMIT 1;"))
                wc_row = wc_res.fetchone()
                if wc_row:
                    print(f"  -> Wildcard Inventories Columns: {list(wc_row._mapping.keys())}")
                else:
                    print("  -> Wildcard Inventories table is empty, but accessible.")
            except Exception as e:
                print(f"  -> Wildcard Inventories inspection note: {e}")

            # 3. Check user_collections table presence
            col_res = await session.execute(text("SELECT COUNT(*) FROM user_collections;"))
            print(f"  -> User Collections Total Rows: {col_res.scalar()}")

        except Exception as e:
            print(f"[!] Inspection error: {e}")

if __name__ == "__main__":
    asyncio.run(inspect_db())