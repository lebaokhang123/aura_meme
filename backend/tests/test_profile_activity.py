"""Calendar activity reads use rollback-only PostgreSQL and current public visibility."""
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.models import Category, Comment, MediaUpload, Post, Profile, User
from test_auth import ACCOUNT, auth, migrated
from test_blog import blog


@pytest.mark.parametrize('now,start,today', [
    ('2026-12-31T18:00:00+00:00', '2025-12-29', '2027-01-01'),
    ('2024-02-28T18:00:00+00:00', '2023-02-27', '2024-02-29'),
    ('2026-11-08T18:00:00+00:00', '2025-11-10', '2026-11-09'),
    ('2026-11-08T16:59:59+00:00', '2025-11-03', '2026-11-08'),
])
def test_activity_window_is_53_monday_weeks_in_vietnam(now, start, today):
    from app.profile_activity import activity_window
    actual_start, actual_today = activity_window(datetime.fromisoformat(now))
    assert actual_start == date.fromisoformat(start)
    assert actual_today == date.fromisoformat(today)
    assert actual_start.weekday() == 0
    assert (actual_start + timedelta(days=370)).weekday() == 6
    assert 364 <= (actual_today - actual_start).days <= 370


def post_row(c, owner, category, created, **changes):
    ident = uuid4()
    c.execute(Post.__table__.insert().values(id=ident, author_id=owner, category_id=category,
        title='Synthetic activity', content='Public activity fixture', status='published',
        created_at=created, updated_at=created, **changes))
    return ident


def comment_row(c, owner, parent, created, *, status='visible', deleted_at=None):
    ident = uuid4()
    c.execute(Comment.__table__.insert().values(id=ident, author_id=owner, post_id=parent,
        body='Synthetic activity comment', status=status, deleted_at=deleted_at,
        created_at=created, updated_at=created))
    return ident


def public_activity(client, username=ACCOUNT['username']):
    return client.get('/api/v1/users/' + username + '/activity')


@pytest.mark.integration
def test_activity_groups_public_posts_comments_by_vn_day_with_bounded_queries(blog):
    client,c,owner,category,_ = blog
    now = datetime(2026,12,31,18,tzinfo=timezone.utc)
    client.app.state.auth.now = lambda: now
    before_midnight = datetime(2026,12,31,16,59,59,tzinfo=timezone.utc)
    midnight = datetime(2026,12,31,17,tzinfo=timezone.utc)
    start = datetime(2025,12,28,17,tzinfo=timezone.utc)
    parent = post_row(c,owner,category,before_midnight)
    post_row(c,owner,category,midnight)
    post_row(c,owner,category,now)
    post_row(c,owner,category,start)
    post_row(c,owner,category,start-timedelta(microseconds=1))
    post_row(c,owner,category,now+timedelta(microseconds=1))
    post_row(c,owner,category,now+timedelta(days=2))
    comment_row(c,owner,parent,start)
    comment_row(c,owner,parent,start-timedelta(microseconds=1))
    comment_row(c,owner,parent,before_midnight)
    comment_row(c,owner,parent,midnight)
    comment_row(c,owner,parent,midnight)
    comment_row(c,owner,parent,now+timedelta(microseconds=1))
    other=uuid4()
    c.execute(User.__table__.insert().values(id=other,username='activity_other',email='activity-other@example.test',
        password_hash='synthetic',status='active',created_at=now,updated_at=now))
    c.execute(Profile.__table__.insert().values(user_id=other,display_name='Other',updated_at=now))
    foreign_post=post_row(c,other,category,midnight)
    comment_row(c,other,parent,midnight)
    comment_row(c,owner,foreign_post,midnight)
    client.cookies.clear()
    queries=[]
    def record(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT'):queries.append(statement)
    event.listen(c,'before_cursor_execute',record)
    try:response=public_activity(client)
    finally:event.remove(c,'before_cursor_execute',record)
    assert response.status_code==200,response.text
    assert len(queries)==3
    data=response.json()
    assert set(data)=={'timezone','start_date','end_date','days','total'}
    assert data['timezone']=='Asia/Ho_Chi_Minh' and data['start_date']=='2025-12-29' and data['end_date']=='2027-01-01'
    assert len(data['days'])==371 and data['days'][-1]['date']=='2027-01-03'
    days={item['date']:item for item in data['days']}
    assert days['2025-12-29']==dict(date='2025-12-29',posts=1,comments=1,count=2)
    assert days['2026-12-31']==dict(date='2026-12-31',posts=1,comments=1,count=2)
    assert days['2027-01-01']==dict(date='2027-01-01',posts=2,comments=3,count=5)
    assert data['total']==9==sum(day['count'] for day in data['days'])
    assert all(set(day)=={'date','posts','comments','count'} and day['count']==day['posts']+day['comments'] for day in data['days'])
    assert all(day['count']==0 for day in data['days'] if day['date']>data['end_date'])
    assert not any(secret in response.text for secret in [ACCOUNT['email'],'roles','password_hash','activity-other@example.test'])


@pytest.mark.integration
@pytest.mark.parametrize('hidden', ['draft','hidden','deleted','category','media','comment_hidden','comment_deleted','parent_author'])
def test_activity_excludes_nonpublic_records(blog, hidden):
    client,c,owner,category,_=blog
    now=client.app.state.auth.now()
    parent=post_row(c,owner,category,now)
    comment=comment_row(c,owner,parent,now)
    if hidden in ('draft','hidden','deleted'):
        c.execute(Post.__table__.update().where(Post.id==parent).values(status=hidden,deleted_at=now if hidden=='deleted' else None))
    if hidden=='category':c.execute(Category.__table__.update().where(Category.id==category).values(status='hidden'))
    if hidden=='media':
        media=uuid4()
        c.execute(MediaUpload.__table__.insert().values(id=media,owner_id=owner,object_key='test/activity',mime='image/png',size_bytes=1,status='pending',created_at=now,updated_at=now))
        c.execute(Post.__table__.update().where(Post.id==parent).values(media_id=media))
    if hidden.startswith('comment_'):
        c.execute(Comment.__table__.update().where(Comment.id==comment).values(status='hidden' if hidden=='comment_hidden' else 'deleted',deleted_at=now if hidden=='comment_deleted' else None))
    if hidden=='parent_author':
        other=uuid4()
        c.execute(User.__table__.insert().values(id=other,username='inactive_parent',email='inactive-parent@example.test',password_hash='synthetic',status='locked',created_at=now,updated_at=now))
        c.execute(Profile.__table__.insert().values(user_id=other,display_name='Hidden',updated_at=now))
        c.execute(Post.__table__.update().where(Post.id==parent).values(author_id=other))
    client.cookies.clear()
    response=public_activity(client)
    assert response.status_code==200,response.text
    assert response.json()['total']==(1 if hidden.startswith('comment_') else 0)


@pytest.mark.integration
@pytest.mark.parametrize('identity', ['missing','locked','deleted'])
def test_activity_missing_inactive_profiles_are_not_found(blog, identity):
    client,c,owner,*_=blog
    if identity!='missing':c.execute(User.__table__.update().where(User.id==owner).values(status=identity,deleted_at=client.app.state.auth.now() if identity=='deleted' else None))
    client.cookies.clear()
    assert public_activity(client,'unknown_activity' if identity=='missing' else ACCOUNT['username']).status_code==404


@pytest.mark.integration
@pytest.mark.parametrize('username', ['ab','invalid-name','x'*33])
def test_activity_rejects_invalid_username(blog, username):
    assert public_activity(blog[0],username).status_code==422
