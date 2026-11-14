"""Inventory and approved catalog delivery use synthetic bytes and rollback-only identities."""
from hashlib import sha256
from io import BytesIO
import json
from uuid import UUID,uuid4
import pytest
from PIL import Image,PngImagePlugin
from sqlalchemy import text
from test_auth import auth,migrated,register,login,csrf
from test_blog import mutation


@pytest.fixture
def inventory(auth,tmp_path,monkeypatch):
    client,c=auth
    owner=UUID(register(client).json()['id'])
    other=UUID(register(client,username='other_inv',email='other-inv@example.com').json()['id'])
    assert login(client).status_code==200
    monkeypatch.setenv('CATALOG_STORAGE_ROOT',str(tmp_path))
    ids=[uuid4() for _ in range(4)];files=[]
    for index,asset in enumerate(ids):
        image=Image.new('RGBA',(8,8),(index,30,80,255));out=BytesIO()
        info=PngImagePlugin.PngInfo();info.add_text('private-fixture','must-not-survive')
        image.save(out,format='PNG',pnginfo=info);data=out.getvalue();digest=sha256(data).hexdigest()
        file=tmp_path/(digest+'.png');file.write_bytes(data);files.append(file)
        rights={'review_status':'approved','source':'synthetic test fixture only','author':'test','license':'CC0-1.0','attribution':'not released','sha256':digest,'mime':'image/png'}
        c.execute(text("INSERT INTO asset_items VALUES (:id,:slug,:kind,'synthetic','D',:key,CAST(:rights AS jsonb),true,:now,:now)"),
                  dict(id=asset,slug='fixture-'+str(index),kind='frame' if index==1 else 'icon',key='catalog/'+file.name,rights=json.dumps(rights),now=client.app.state.auth.now()))
        c.execute(text('INSERT INTO user_inventory VALUES (:user,:asset,:quantity,:now,:now)'),dict(user=other if index==2 else owner,asset=asset,quantity=0 if index==3 else 1,now=client.app.state.auth.now()))
    return client,c,owner,other,ids,files


@pytest.mark.integration
def test_inventory_filters_owner_and_zero_quantity_with_stable_pagination(inventory):
    client,c,owner,other,ids,_=inventory
    response=client.get('/api/v1/inventory/me?page_size=1')
    assert response.status_code==200,response.text
    body=response.json();assert body['pagination']['total']==2 and len(body['items'])==1
    second=client.get('/api/v1/inventory/me?page=2&page_size=1').json()
    assert {body['items'][0]['asset']['id'],second['items'][0]['asset']['id']}=={str(ids[0]),str(ids[1])}
    assert all(set(x['asset'])=={'id','slug','kind','rarity','media_url'} and not x['equipped'] for x in body['items'])
    assert client.get('/api/v1/inventory/me?page=9999999999999999999').json()['items']==[]
    assert str(other) not in response.text and 'source_rights' not in response.text


@pytest.mark.integration
def test_equip_retry_unequip_and_client_cannot_override_owner(inventory):
    client,c,owner,other,ids,_=inventory
    for _ in range(2):
        r=mutation(client,'PUT','/inventory/equipment/icon',{'asset_id':str(ids[0]),'user_id':str(other)})
        assert r.status_code==200 and r.json()=={'slot_kind':'icon','asset_id':str(ids[0])}
    assert c.scalar(text('SELECT count(*) FROM user_equipment'))==1
    assert c.scalar(text('SELECT user_id FROM user_equipment'))==owner
    assert any(x['equipped'] for x in client.get('/api/v1/inventory/me').json()['items'])
    for _ in range(2):assert mutation(client,'PUT','/inventory/equipment/icon',{'asset_id':None}).status_code==200
    assert c.scalar(text('SELECT count(*) FROM user_equipment'))==0


@pytest.mark.integration
@pytest.mark.parametrize('index,slot,code',[(2,'icon',404),(3,'icon',404),(1,'icon',409),(0,'generator',422)])
def test_equip_rejects_idor_zero_quantity_and_wrong_slot(inventory,index,slot,code):
    client,c,_,_,ids,_=inventory
    assert mutation(client,'PUT','/inventory/equipment/'+slot,{'asset_id':str(ids[index])}).status_code==code
    assert c.scalar(text('SELECT count(*) FROM user_equipment'))==0


@pytest.mark.integration
def test_catalog_public_read_only_returns_normalized_png_without_metadata(inventory):
    client,c,_,_,ids,_=inventory;client.cookies.clear()
    r=client.get('/api/v1/catalog/assets/'+str(ids[0]))
    assert r.status_code==200 and r.headers['content-type']=='image/png'
    assert r.headers['cache-control']=='no-store' and r.headers['x-content-type-options']=='nosniff'
    with Image.open(BytesIO(r.content)) as image:assert image.size==(8,8) and 'private-fixture' not in image.info
    assert b'must-not-survive' not in r.content


@pytest.mark.integration
@pytest.mark.parametrize('mode',['inactive','pending','missing','hash','traversal','mime','html','hardlink'])
def test_catalog_never_serves_unready_or_unverified_bytes(inventory,mode):
    import os
    client,c,_,_,ids,files=inventory
    if mode=='inactive':c.execute(text('UPDATE asset_items SET active=false WHERE id=:id'),{'id':ids[0]})
    elif mode=='pending':c.execute(text("UPDATE asset_items SET active=false,source_rights=jsonb_set(source_rights,'{review_status}','\"pending\"') WHERE id=:id"),{'id':ids[0]})
    elif mode=='missing':files[0].unlink()
    elif mode=='hash':files[0].write_bytes(b'changed')
    elif mode=='traversal':c.execute(text("UPDATE asset_items SET media_key='../'||media_key WHERE id=:id"),{'id':ids[0]})
    elif mode=='mime':c.execute(text("UPDATE asset_items SET source_rights=jsonb_set(source_rights,'{mime}','\"image/jpeg\"') WHERE id=:id"),{'id':ids[0]})
    elif mode=='html':
        files[0].write_bytes(b'<html>bad</html>')
        digest=sha256(files[0].read_bytes()).hexdigest();files[0].rename(files[0].parent/(digest+'.png'))
        c.execute(text("UPDATE asset_items SET media_key=:key,source_rights=jsonb_set(source_rights,'{sha256}',to_jsonb(CAST(:digest AS text))) WHERE id=:id"),{'id':ids[0],'key':'catalog/'+digest+'.png','digest':digest})
    else:os.link(files[0],files[0].parent/'linked.png')
    assert client.get('/api/v1/catalog/assets/'+str(ids[0])).status_code==404


@pytest.mark.integration
def test_equipment_database_guards_quantity_and_active_asset(inventory):
    from sqlalchemy.exc import IntegrityError
    client,c,_,_,ids,_=inventory
    assert mutation(client,'PUT','/inventory/equipment/icon',{'asset_id':str(ids[0])}).status_code==200
    for statement in ["UPDATE user_inventory SET quantity=0 WHERE asset_id=:id", "UPDATE asset_items SET active=false WHERE id=:id", "UPDATE asset_items SET kind='frame' WHERE id=:id", "UPDATE asset_items SET rarity='C' WHERE id=:id"]:
        with pytest.raises(IntegrityError),c.begin_nested():c.execute(text(statement),{'id':ids[0]})
    assert c.scalar(text('SELECT count(*) FROM user_equipment'))==1


@pytest.mark.integration
def test_inventory_auth_csrf_origin_and_revoked_session_before_write(inventory):
    client,c,_,_,ids,_=inventory;path='/api/v1/inventory/equipment/icon';body={'asset_id':str(ids[0])}
    assert client.put(path,json=body).status_code==403
    assert client.put(path,json=body,headers={'Origin':'https://evil.test','X-CSRF-Token':csrf(client)}).status_code==403
    c.execute(text('UPDATE auth_sessions SET revoked_at=:now'),{'now':client.app.state.auth.now()})
    assert mutation(client,'PUT','/inventory/equipment/icon',body).status_code==401
    client.cookies.clear();assert client.get('/api/v1/inventory/me').status_code==401
    assert c.scalar(text('SELECT count(*) FROM user_equipment'))==0


@pytest.mark.integration
def test_inventory_anonymous_requires_session(auth):
    assert auth[0].get('/api/v1/inventory/me').status_code==401


def add_avatar_fixture(client, c, owner, template, *, active=True, approved=True, quantity=1, kind='avatar'):
    asset=uuid4()
    c.execute(text("INSERT INTO asset_items SELECT :asset,:slug,:kind,collection,rarity,media_key,source_rights || CAST(:rights AS jsonb),:active,created_at,updated_at FROM asset_items WHERE id=:template"),
        dict(asset=asset,slug='avatar-'+asset.hex,kind=kind,rights=json.dumps({'review_status':'approved' if approved else 'pending'}),active=active,template=template))
    c.execute(text('INSERT INTO user_inventory VALUES (:owner,:asset,:quantity,:now,:now)'),dict(owner=owner,asset=asset,quantity=quantity,now=client.app.state.auth.now()))
    return asset


@pytest.mark.integration
def test_equipped_avatar_identity_and_unequip_fallback(inventory):
    from test_auth import ACCOUNT, post
    client,c,owner,other,ids,_=inventory
    asset=add_avatar_fixture(client,c,owner,ids[0])
    assert client.get('/api/v1/users/me').json()['avatar_url'] is None
    response=mutation(client,'PUT','/inventory/equipment/avatar',{'asset_id':str(asset)})
    assert response.status_code==200,response.text
    expected='/api/v1/catalog/assets/'+str(asset)
    assert client.get('/api/v1/users/me').json()['avatar_url']==expected
    assert client.get('/api/v1/users/'+ACCOUNT['username']).json()['avatar_url']==expected
    assert post(client,'logout').status_code==204
    assert login(client).status_code==200
    assert client.get('/api/v1/users/me').json()['avatar_url']==expected
    assert mutation(client,'PUT','/inventory/equipment/avatar',{'asset_id':None}).status_code==200
    assert client.get('/api/v1/users/me').json()['avatar_url'] is None
    assert client.get('/api/v1/users/'+ACCOUNT['username']).json()['avatar_url'] is None


@pytest.mark.integration
@pytest.mark.parametrize('invalid', ['inactive', 'unapproved', 'unowned', 'zero', 'wrong_kind'])
def test_avatar_equip_rejects_invalid_inventory(inventory, invalid):
    client,c,owner,other,ids,_=inventory
    asset=add_avatar_fixture(client,c,other if invalid=='unowned' else owner,ids[0],
        active=invalid not in ('inactive','unapproved'),approved=invalid!='unapproved',quantity=0 if invalid=='zero' else 1,
        kind='icon' if invalid=='wrong_kind' else 'avatar')
    assert mutation(client,'PUT','/inventory/equipment/avatar',{'asset_id':str(asset)}).status_code==(409 if invalid=='wrong_kind' else 404)
