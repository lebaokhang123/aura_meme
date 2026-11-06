"""Real committed races and deferred COMMIT failures for equipment ownership."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID,uuid4
import pytest
from sqlalchemy import event,text
from sqlalchemy.exc import IntegrityError
from test_auth import migrated,csrf
from test_blog import mutation
from test_comments_concurrency import race_comments,wait_for_lock


@pytest.fixture
def equipment_race(race_comments):
    client,_,engine,_,tag=race_comments
    owner=UUID(client.get('/api/v1/users/me').json()['id']);ids=[uuid4(),uuid4()]
    with engine.begin() as c:
        for index,asset in enumerate(ids):
            c.execute(text("INSERT INTO asset_items VALUES (:id,:slug,'icon','synthetic','D',:key,CAST(:rights AS jsonb),true,now(),now())"),
                      {'id':asset,'slug':'fixture-'+asset.hex,'key':'catalog/'+'0'*64+'.png','rights':'{"review_status":"approved","source":"synthetic fixture"}'})
            c.execute(text('INSERT INTO user_inventory VALUES (:owner,:asset,1,now(),now())'),{'owner':owner,'asset':asset})
    try:yield client,owner,ids,engine,tag
    finally:
        with engine.begin() as c:
            assert all(row.asset_id in ids for row in c.execute(text('SELECT asset_id FROM user_equipment WHERE user_id=:owner'),{'owner':owner}))
            assert all(row.asset_id in ids for row in c.execute(text('SELECT asset_id FROM user_inventory WHERE user_id=:owner'),{'owner':owner}))
            c.execute(text('DELETE FROM user_equipment WHERE user_id=:owner'),{'owner':owner})
            c.execute(text('DELETE FROM user_inventory WHERE user_id=:owner AND asset_id=ANY(:ids)'),{'owner':owner,'ids':ids})
            c.execute(text('DELETE FROM asset_items WHERE id=ANY(:ids)'),{'ids':ids})


@pytest.mark.integration
@pytest.mark.parametrize('second_action',['equip','reduce'])
def test_competing_equipment_changes_preserve_one_valid_slot(equipment_race,second_action):
    client,owner,ids,engine,tag=equipment_race;token=csrf(client)
    locked,release=Event(),Event()
    def pause(conn,cursor,statement,parameters,context,executemany):
        if 'FROM user_inventory' in statement and 'FOR UPDATE' in statement and not locked.is_set():
            locked.set();assert release.wait(7)
    def put(asset):return mutation(client,'PUT','/inventory/equipment/icon',{'asset_id':str(asset)},token)
    def reduce():
        with pytest.raises(IntegrityError),engine.begin() as c:
            c.execute(text('UPDATE user_inventory SET quantity=0 WHERE user_id=:owner AND asset_id=:id'),{'owner':owner,'id':ids[0]})
        return None
    event.listen(engine,'after_cursor_execute',pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(put,ids[0])
            try:
                assert locked.wait(5)
                second=pool.submit(put,ids[1]) if second_action=='equip' else pool.submit(reduce)
                wait_for_lock(engine,tag)
            finally:release.set()
            assert first.result(timeout=15).status_code==200
            result=second.result(timeout=15)
            if result is not None:assert result.status_code==200
        with engine.connect() as c:
            assert c.scalar(text('SELECT count(*) FROM user_equipment WHERE user_id=:owner'),{'owner':owner})==1
            assert c.scalar(text('SELECT asset_id FROM user_equipment WHERE user_id=:owner'),{'owner':owner})==ids[1 if second_action=='equip' else 0]
            assert c.scalar(text('SELECT min(quantity) FROM user_inventory WHERE user_id=:owner'),{'owner':owner})==1
    finally:release.set();event.remove(engine,'after_cursor_execute',pause)


@pytest.mark.integration
def test_equip_commit_failure_returns500_without_persisting_slot(equipment_race):
    client,owner,ids,engine,_=equipment_race
    try:
        with engine.begin() as c:
            c.exec_driver_sql("CREATE FUNCTION equipment_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic commit failure'; END $$")
            c.exec_driver_sql('CREATE CONSTRAINT TRIGGER equipment_fail AFTER INSERT ON user_equipment DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION equipment_fail()')
        response=mutation(client,'PUT','/inventory/equipment/icon',{'asset_id':str(ids[0])})
        assert response.status_code==500
        with engine.connect() as c:assert c.scalar(text('SELECT count(*) FROM user_equipment WHERE user_id=:owner'),{'owner':owner})==0
    finally:
        with engine.begin() as c:
            c.exec_driver_sql('DROP TRIGGER equipment_fail ON user_equipment')
            c.exec_driver_sql('DROP FUNCTION equipment_fail()')
