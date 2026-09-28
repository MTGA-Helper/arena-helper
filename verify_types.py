import asyncio
import uuid
from sqlalchemy import text
from database import AsyncSessionLocal

async def validate_types():
    print('==> Starting Type-Safe Datatype Validation...')
    async with AsyncSessionLocal() as session:
        async with session.begin():
            # 1. Test JSONB via deck_analyses or direct query cast
            print('\n--- [1] JSONB Operation Test ---')
            jsonb_query = text("SELECT ('{\"archetype\": \"Aggro\", \"metrics\": {\"win_rate\": 0.68}}'::jsonb)->'metrics'->>'win_rate' AS win_rate")
            json_res = await session.execute(jsonb_query)
            json_row = json_res.fetchone()
            print(f' [PASS] JSONB Query & Extraction: win_rate -> {json_row.win_rate}')
            assert float(json_row.win_rate) == 0.68, 'JSONB extraction mismatch!'

            # 2. Test PostgreSQL Native ARRAY via direct expression query
            print('\n--- [2] PostgreSQL Native ARRAY Test ---')
            array_query = text("SELECT ARRAY['Standard', 'Historic', 'Brawl']::VARCHAR[] AS formats, ARRAY[3, 4, 3, 2]::INTEGER[] AS mana_curve")
            arr_res = await session.execute(array_query)
            arr_row = arr_res.fetchone()
            print(f' [PASS] ARRAY Select: formats -> {arr_row.formats}, mana_curve -> {arr_row.mana_curve}')
            assert arr_row.formats == ['Standard', 'Historic', 'Brawl'], 'Array formats mismatch!'
            assert sum(arr_row.mana_curve) == 12, 'Array curve mismatch!'

    print('\n==================================================')
    print('JSONB & ARRAY EXPLICIT VERIFICATION PASSED ✅')
    print('==================================================')

if __name__ == '__main__':
    asyncio.run(validate_types())
