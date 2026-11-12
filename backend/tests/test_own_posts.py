"""Owner-approved private reads must never broaden public post visibility."""
from uuid import UUID,uuid4
import pytest
from sqlalchemy import select
from app.models import AuthSession,Category,MediaUpload,Post,Profile,User
from test_auth import auth,migrated
from test_blog import blog,create_post


@pytest.mark.integration
def test_owner_reopens_draft_without_publishing_it(blog):
    client,connection,actor,*_=blog
    created=create_post(blog,status='draft').json();ident=created['id']
    assert client.get('/api/v1/posts/'+ident).status_code==404
    response=client.get('/api/v1/users/me/posts/'+ident)
    assert response.status_code==200,response.text
    assert response.json()['status']=='draft' and response.json()['media_id'] is None
    page=client.get('/api/v1/users/me/posts').json()
    assert [item['id'] for item in page['items']]==[ident]
    assert connection.scalar(select(Post.status))=='draft'


@pytest.mark.integration
@pytest.mark.parametrize('suffix',['','/'+str(uuid4())])
def test_private_post_reads_require_session(auth,suffix):
    client,*_=auth
    assert client.get('/api/v1/users/me/posts'+suffix).status_code==401


@pytest.mark.integration
@pytest.mark.parametrize('status',['draft','published','hidden','deleted'])
def test_foreign_posts_are_never_in_private_list_or_detail(blog,status):
    client,connection,actor,category,*_=blog
    now=client.app.state.auth.now();other=uuid4();ident=uuid4()
    connection.execute(User.__table__.insert().values(id=other,username='foreign_owner',email='foreign@example.com',password_hash='synthetic',status='active',created_at=now,updated_at=now))
    connection.execute(Profile.__table__.insert().values(user_id=other,display_name='Foreign',updated_at=now))
    connection.execute(Post.__table__.insert().values(id=ident,author_id=other,category_id=category,title='Private foreign',content='Synthetic',status=status,deleted_at=now if status=='deleted' else None,created_at=now,updated_at=now))
    assert client.get('/api/v1/users/me/posts').json()['items']==[]
    assert client.get('/api/v1/users/me/posts/'+str(ident)).status_code==404


@pytest.mark.integration
def test_owner_media_metadata_is_private_and_hidden_category_does_not_publish(blog):
    client,connection,actor,category,hidden=blog
    now=client.app.state.auth.now();media=uuid4()
    connection.execute(MediaUpload.__table__.insert().values(id=media,owner_id=actor,object_key='private-synthetic-key.png',mime='image/png',size_bytes=100,status='ready',created_at=now,updated_at=now))
    ident=create_post(blog,status='published',media_id=str(media)).json()['id']
    connection.execute(Post.__table__.update().where(Post.id==UUID(ident)).values(category_id=hidden,status='hidden'))
    response=client.get('/api/v1/users/me/posts/'+ident)
    assert response.status_code==200
    assert response.json()['media_id']==str(media) and response.json()['media_url']=='/api/v1/media/'+str(media)
    assert response.json()['category']['status']=='hidden'
    assert 'object_key' not in response.text and 'private-synthetic-key' not in response.text
    assert 'password_hash' not in response.text and 'email' not in response.json()['author']
    assert client.get('/api/v1/posts/'+ident).status_code==404
    connection.execute(Post.__table__.update().where(Post.id==UUID(ident)).values(status='deleted',deleted_at=now))
    assert client.get('/api/v1/users/me/posts/'+ident).status_code==404
    assert client.get('/api/v1/users/me/posts').json()['items']==[]


@pytest.mark.integration
def test_owner_posts_pagination_filters_and_validation(blog):
    client,connection,actor,category,*_=blog;now=client.app.state.auth.now()
    connection.execute(Post.__table__.insert(),[dict(id=UUID(int=index),author_id=actor,category_id=category,title='Synthetic',content='Body',status='draft' if index%2 else 'published',created_at=now,updated_at=now) for index in range(1,24)])
    response=client.get('/api/v1/users/me/posts').json()
    assert response['pagination']==dict(page=1,page_size=20,total=23,total_pages=2)
    assert [row['id'] for row in response['items']]==[str(UUID(int=index)) for index in range(23,3,-1)]
    assert client.get('/api/v1/users/me/posts?status=draft').json()['pagination']['total']==12
    assert client.get('/api/v1/users/me/posts?page=2').json()['pagination']['total']==23
    assert client.get('/api/v1/users/me/posts?page='+str(10**40)).json()['items']==[]
    for query in ['page=0','page_size=101','status=deleted','status=unknown']:
        assert client.get('/api/v1/users/me/posts?'+query).status_code==422
    assert client.get('/api/v1/users/me/posts/not-uuid').status_code==422
    assert client.get('/api/v1/users/me/posts/'+str(uuid4())).status_code==404


@pytest.mark.integration
@pytest.mark.parametrize('fault',['locked','revoked'])
def test_private_reads_recheck_account_and_session(blog,fault):
    client,connection,actor,*_=blog
    if fault=='locked':connection.execute(User.__table__.update().where(User.id==actor).values(status='locked'))
    else:connection.execute(AuthSession.__table__.update().values(revoked_at=client.app.state.auth.now()))
    assert client.get('/api/v1/users/me/posts').status_code==401


def test_private_post_contract_matches_owner_approval():
    from app.main import app
    runtime=app.openapi()
    for path in ['/api/v1/users/me/posts','/api/v1/users/me/posts/{post_id}']:
        assert runtime['paths'][path]['get']['security']
    assert not runtime['paths']['/api/v1/posts/{post_id}']['get'].get('security')
    assert 'media_id' not in runtime['components']['schemas']['PostResponse']['properties']
    assert 'media_id' in runtime['components']['schemas']['OwnPost']['required']
    assert set(runtime['components']['schemas']['OwnPost']['properties'])==set(runtime['components']['schemas']['PostResponse']['properties'])|{'media_id'}
