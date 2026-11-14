"""Minimal Admin read surfaces preserve DB RBAC and private field allowlists."""
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models import AssetItem, Comment
from test_auth import auth, migrated
from test_blog import admin, blog, create_post, mutation

@pytest.mark.parametrize('path',['/api/v1/admin/comments','/api/v1/admin/assets','/api/v1/admin/posts/00000000-0000-4000-8000-000000000001/media'])
def test_new_admin_reads_require_session_without_opening_database(monkeypatch,path):
    monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://test:unused@127.0.0.1:1/test')
    monkeypatch.setenv('AUTH_SIGNING_KEY','synthetic-signing-key-at-least-thirty-two-bytes')
    with TestClient(app,base_url='https://testserver') as client:
        assert client.get(path).status_code==401
        assert client.app.state.engine.pool.checkedout()==0

@pytest.mark.integration
@pytest.mark.parametrize('path',['/admin/comments','/admin/assets','/admin/posts/00000000-0000-4000-8000-000000000001/media'])
def test_user_and_guest_cannot_read_admin_surfaces(blog,path):
    client,*_=blog
    assert client.get('/api/v1'+path).status_code==403
    client.cookies.clear();assert client.get('/api/v1'+path).status_code==401

@pytest.mark.integration
def test_admin_comments_include_hidden_and_use_safe_author_dto(admin):
    client,c,owner,*_=admin
    post=create_post(admin,status='published').json()['id'];now=client.app.state.auth.now()
    for status in ['visible','hidden']:
        c.execute(Comment.__table__.insert().values(id=uuid4(),post_id=post,author_id=owner,body='Private '+status,status=status,created_at=now,updated_at=now))
    result=client.get('/api/v1/admin/comments?status=hidden&search=Private&page_size=1').json()
    assert result['pagination']['total']==1 and result['items'][0]['status']=='hidden'
    assert set(result['items'][0])=={'id','post_id','author','body','status','created_at'}
    assert not {'email','roles','password_hash'}.intersection(result['items'][0]['author'])
    assert client.get('/api/v1/admin/comments?post_id='+post).json()['pagination']['total']==2
    ident=result['items'][0]['id'];assert mutation(client,'PATCH','/admin/comments/'+ident,{'status':'visible'}).status_code==204
    assert client.get('/api/v1/admin/comments?status=hidden').json()['items']==[]
    assert client.get('/api/v1/admin/comments?search=%25').json()['items']==[]
    assert client.get('/api/v1/admin/comments?status=forged').status_code==422

@pytest.mark.integration
def test_admin_assets_are_status_only_not_private_source_or_storage(admin):
    client,c,*_=admin;now=client.app.state.auth.now()
    for n,(active,review) in enumerate([(False,'pending'),(True,'approved')]):
        c.execute(AssetItem.__table__.insert().values(id=uuid4(),slug='review-'+str(n),kind='avatar',collection='synthetic',rarity='D',media_key='catalog/private-path',source_rights={'review_status':review,'source':'private-source','license':'private-license'},active=active,created_at=now,updated_at=now))
    response=client.get('/api/v1/admin/assets?review_status=pending&search=review')
    assert response.status_code==200;result=response.json();assert result['pagination']['total']==1
    assert set(result['items'][0])=={'id','slug','kind','rarity','active','review_status'}
    assert result['items'][0]['active'] is False
    assert all(s not in response.text for s in ['private-path','private-source','private-license','media_key','source_rights'])
    assert client.get('/api/v1/admin/assets?active=true').json()['pagination']['total']==1
    assert client.get('/api/v1/admin/assets?kind=frame').json()['items']==[]
    assert client.get('/api/v1/admin/assets?review_status=forged').status_code==422

@pytest.mark.integration
def test_admin_reads_hidden_post_image_without_expanding_public_media(admin,tmp_path,monkeypatch):
    from io import BytesIO
    from uuid import UUID
    from PIL import Image,PngImagePlugin
    from sqlalchemy import update
    from app.models import MediaUpload,Post
    from app.storage import LocalObject
    from test_auth import register
    client,c,_,category_id,*_=admin;other=TestClient(app,base_url='https://testserver')
    try:
        response=register(other,username='image_writer',email='image-writer@example.com');assert response.status_code==201;owner=UUID(response.json()['id'])
        root=tmp_path/'private';monkeypatch.setenv('MEDIA_STORAGE_ROOT',str(root));data=BytesIO();metadata=PngImagePlugin.PngInfo();metadata.add_text('private','must-not-deliver');Image.new('RGB',(8,6),'red').save(data,format='PNG',pnginfo=metadata)
        stored=LocalObject(root,'png',data.getvalue());key=stored.key;stored.close();media_id,post_id=uuid4(),uuid4();now=client.app.state.auth.now()
        c.execute(MediaUpload.__table__.insert().values(id=media_id,owner_id=owner,object_key=key,mime='image/png',size_bytes=len(data.getvalue()),status='ready',created_at=now,updated_at=now))
        c.execute(Post.__table__.insert().values(id=post_id,author_id=owner,category_id=category_id,title='Hidden image',content='Private image fixture',media_id=media_id,status='hidden',created_at=now,updated_at=now))
        path='/api/v1/admin/posts/'+str(post_id)+'/media';response=client.get(path)
        assert response.status_code==200 and response.headers['content-type']=='image/png'
        assert response.headers['cache-control']=='no-store' and response.headers['x-content-type-options']=='nosniff'
        assert b'must-not-deliver' not in response.content
        with Image.open(BytesIO(response.content)) as image:assert image.size==(8,6) and not image.info
        assert client.get('/api/v1/media/'+str(media_id)).status_code==404
        assert other.get(path).status_code==401
        c.execute(update(MediaUpload).where(MediaUpload.id==media_id).values(status='rejected'));assert client.get(path).status_code==404
        c.execute(update(MediaUpload).where(MediaUpload.id==media_id).values(status='ready'));c.execute(update(Post).where(Post.id==post_id).values(media_id=None));assert client.get(path).status_code==404
    finally:other.close()
