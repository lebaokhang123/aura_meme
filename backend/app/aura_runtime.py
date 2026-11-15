"""Transactional Aura V1. Callers hold the shared mutation gate before User locks."""
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, or_, select, text

from app.aura_v1 import SCHEMA, config, day_window, level_progress, validate_config
from app.models import (AdminAuditLog, AuraLedger, AuraRewardEvent, Category, Comment, DailyCheckin,
    Post, PostReaction, RewardPolicyVersion, Role, User, UserProgress, UserRole)
from app.security import AuthError


def unavailable(message="Aura policy or account state is not ready."):
    raise AuthError(503,"NOT_READY",message)


def active_policy(db,now,required=True):
    day_window(now)
    if db.scalar(text("SELECT to_regclass('public.aura_reward_events')")) is None:
        if required:unavailable()
        return None
    policies=list(db.scalars(select(RewardPolicyVersion).where(RewardPolicyVersion.status=="published",
        RewardPolicyVersion.effective_at<=now,RewardPolicyVersion.config_json["schema"].astext==SCHEMA)))
    if not policies:
        if required:unavailable()
        return None
    if len(policies)!=1:unavailable("Aura policy is ambiguous; preserve data for review.")
    try:validate_config(policies[0].config_json)
    except (ValueError,TypeError):unavailable("Aura policy differs from the reviewed V1 snapshot.")
    return policies[0]


def _streak(db,owner,last_day):
    from app.checkin import streak_length
    return streak_length(db,owner,last_day)


def _state(db,owner,now,initialize=False,locked=False):
    query=select(UserProgress).where(UserProgress.user_id==owner)
    if locked:query=query.with_for_update().execution_options(populate_existing=True)
    state=db.scalar(query)
    earned,bonus,latest=db.execute(select(func.coalesce(func.sum(AuraLedger.base_xp),0),
        func.coalesce(func.sum(AuraLedger.bonus_xp),0),func.max(AuraLedger.occurred_at)).where(AuraLedger.user_id==owner)).one()
    earned,bonus=int(earned),int(bonus)  # PostgreSQL SUM(bigint) returns exact NUMERIC.
    last_day=db.scalar(select(func.max(DailyCheckin.effective_day)).where(DailyCheckin.user_id==owner))
    streak=_streak(db,owner,last_day)
    if earned<0 or bonus<0 or latest is not None and latest>now or last_day is not None and last_day>day_window(now)[0]:unavailable()
    if state is None:
        if not initialize:unavailable()
        state=UserProgress(user_id=owner,aura_xp_earned=earned,aura_xp_bonus=bonus,
            level_cached=level_progress(earned+bonus)["level"],fair_level_cached=level_progress(earned)["level"],
            streak_days=streak,last_checkin_day=last_day,updated_at=now)
        db.add(state);db.flush()
    if (state.aura_xp_earned,state.aura_xp_bonus,state.last_checkin_day,state.streak_days)!=(earned,bonus,last_day,streak):unavailable("Aura ledger/cache mismatch; preserve data for review.")
    return state


def initialize_progress(db,owner,now):
    if active_policy(db,now,False) is None:return None
    return _state(db,owner,now,initialize=True,locked=True)


def progress_payload(db,owner,now):
    active_policy(db,now)
    state=_state(db,owner,now)
    today,_,end=day_window(now)
    last=state.last_checkin_day
    current_streak=state.streak_days if last in (today,today-timedelta(days=1)) else 0
    return {"earned_xp":state.aura_xp_earned,"bonus_xp":state.aura_xp_bonus,"total_xp":state.aura_xp_earned+state.aura_xp_bonus,
        **level_progress(state.aura_xp_earned+state.aura_xp_bonus),"fair_level":level_progress(state.aura_xp_earned)["level"],
        "streak_days":current_streak,"checked_in":last==today,"effective_day":today,"next_reset_at":end,"server_time":now}


def _updated(db,state,base,bonus,now):
    state.aura_xp_earned+=base;state.aura_xp_bonus+=bonus
    if min(state.aura_xp_earned,state.aura_xp_bonus)<0:unavailable()
    state.level_cached=level_progress(state.aura_xp_earned+state.aura_xp_bonus)["level"]
    state.fair_level_cached=level_progress(state.aura_xp_earned)["level"]
    state.updated_at=now
    db.flush()


def _eligible_post(db,post_id):
    return db.scalar(select(Post).join(User,User.id==Post.author_id).join(Category,Category.id==Post.category_id).where(
        Post.id==post_id,Post.status=="published",Post.deleted_at.is_(None),User.status=="active",Category.status=="active"))


def _claim(db,policy,kind,post,actor,now,comment=None):
    day=day_window(now)[0]
    key=f"v1:post:{post.id}" if kind=="post" else f"v1:reaction:{post.id}:{actor}" if kind=="reaction" else f"v1:comment:{day}:{post.id}:{actor}"
    if db.scalar(select(AuraRewardEvent.id).where(AuraRewardEvent.event_key==key)) is not None:return None
    event=AuraRewardEvent(id=uuid4(),event_key=key,kind=kind,actor_id=actor,post_id=post.id,
        comment_id=comment.id if comment else None,policy_id=policy.id,effective_day=day,occurred_at=now)
    db.add(event);db.flush()
    return event


def _award(db,policy,event,owner,role,now):
    rule=config()["rewards"][event.kind+"_"+role]
    state=_state(db,owner,now,initialize=True,locked=True)
    _,start,end=day_window(now)
    eligible=(AuraLedger.user_id==owner,AuraLedger.base_xp>0,AuraLedger.occurred_at>=start,AuraLedger.occurred_at<end,AuraLedger.event_key.startswith("v1:"))
    consumed=db.scalar(select(func.count()).select_from(AuraLedger).where(*eligible,AuraLedger.event_key.like(f"v1:{event.kind}:%:{role}")))
    used=db.scalar(select(func.coalesce(func.sum(AuraLedger.base_xp),0)).where(*eligible))
    if consumed>=rule["daily_limit"] or used+rule["xp"]>135:return
    db.add(AuraLedger(id=uuid4(),user_id=owner,event_key=event.event_key+":"+role,event_type=event.kind,
        source_actor_id=event.actor_id,source_post_id=event.post_id,source_comment_id=event.comment_id,policy_id=policy.id,
        base_xp=rule["xp"],bonus_xp=0,tier_at_event="FREE",multiplier_at_event=1,reverses_id=None,occurred_at=now))
    db.flush();_updated(db,state,rule["xp"],0,now)


def award_post(db,post,now):
    policy=active_policy(db,now,False)
    if policy is None or post.created_at<policy.effective_at or _eligible_post(db,post.id) is None:return
    event=_claim(db,policy,"post",post,post.author_id,now)
    if event:_award(db,policy,event,post.author_id,"author",now)


def award_reaction(db,post_id,actor_id,now):
    policy=active_policy(db,now,False)
    if policy is None:return
    post=_eligible_post(db,post_id)
    if post is None or post.author_id==actor_id:return
    actor=db.get(User,actor_id)
    if actor is None or actor.status!="active" or db.get(PostReaction,(post_id,actor_id)) is None:return
    event=_claim(db,policy,"reaction",post,actor_id,now)
    if event:
        for owner,role in sorted([(actor_id,"actor"),(post.author_id,"author")],key=lambda row:row[0]):_award(db,policy,event,owner,role,now)


def award_comment(db,comment,now):
    policy=active_policy(db,now,False)
    if policy is None:return
    post=_eligible_post(db,comment.post_id)
    actor=db.get(User,comment.author_id)
    if post is None or post.author_id==comment.author_id or comment.status!="visible" or comment.deleted_at is not None or actor is None or actor.status!="active":return
    event=_claim(db,policy,"comment",post,comment.author_id,now,comment)
    if event:
        for owner,role in sorted([(comment.author_id,"actor"),(post.author_id,"author")],key=lambda row:row[0]):_award(db,policy,event,owner,role,now)


def _reverse(db,condition,now):
    day_window(now)
    entries=list(db.scalars(select(AuraLedger).where(condition,AuraLedger.base_xp>0,AuraLedger.event_key.startswith("v1:")).order_by(AuraLedger.user_id,AuraLedger.id)))
    for original in entries:
        if db.scalar(select(AuraLedger.id).where(AuraLedger.reverses_id==original.id)) is not None:continue
        state=_state(db,original.user_id,now,initialize=True,locked=True)
        db.add(AuraLedger(id=uuid4(),user_id=original.user_id,event_key="v1:reversal:"+str(original.id),event_type="reversal",
            source_actor_id=original.source_actor_id,source_post_id=original.source_post_id,source_comment_id=original.source_comment_id,
            policy_id=original.policy_id,base_xp=-original.base_xp,bonus_xp=-original.bonus_xp,tier_at_event=original.tier_at_event,
            multiplier_at_event=original.multiplier_at_event,reverses_id=original.id,occurred_at=now))
        db.flush();_updated(db,state,-original.base_xp,-original.bonus_xp,now)


def reverse_post(db,post_id,now):_reverse(db,AuraLedger.source_post_id==post_id,now)
def reverse_reaction(db,post_id,actor_id,now):_reverse(db,(AuraLedger.source_post_id==post_id)&(AuraLedger.source_actor_id==actor_id)&(AuraLedger.event_type=="reaction"),now)
def reverse_comment(db,comment_id,now):_reverse(db,AuraLedger.source_comment_id==comment_id,now)
def reverse_user(db,user_id,now):_reverse(db,or_(AuraLedger.source_actor_id==user_id,AuraLedger.source_post_id.in_(select(Post.id).where(Post.author_id==user_id))),now)


def claim_checkin(db,owner,now):
    policy=active_policy(db,now)
    state=_state(db,owner,now,initialize=True,locked=True)
    day,_,end=day_window(now)
    receipt=db.get(DailyCheckin,(owner,day))
    if receipt is not None:
        entry=db.get(AuraLedger,receipt.aura_ledger_id)
        if entry is None or entry.user_id!=owner or entry.event_type!="checkin" or entry.occurred_at!=receipt.claimed_at:unavailable()
        if receipt.reward_mode=="aura_v1" and (entry.base_xp!=15 or entry.bonus_xp!=0 or receipt.wallet_transaction_id is not None):unavailable()
        return {"effective_day":day,"already_checked_in":True,"earned_xp_delta":0,"bonus_xp_delta":0,"khi_van_delta":0,"streak_days":state.streak_days}
    used=db.scalar(select(func.coalesce(func.sum(AuraLedger.base_xp),0)).where(AuraLedger.user_id==owner,AuraLedger.base_xp>0,
        AuraLedger.event_key.startswith("v1:"),AuraLedger.occurred_at>=end-timedelta(days=1),AuraLedger.occurred_at<end))
    if used+15>135:unavailable("Aura quota/cache is inconsistent; preserve data for review.")
    streak=state.streak_days+1 if state.last_checkin_day==day-timedelta(days=1) else 1
    entry=AuraLedger(id=uuid4(),user_id=owner,event_key="v1:checkin:"+day.isoformat(),event_type="checkin",source_actor_id=None,
        source_post_id=None,source_comment_id=None,policy_id=policy.id,base_xp=15,bonus_xp=0,tier_at_event="FREE",multiplier_at_event=1,reverses_id=None,occurred_at=now)
    db.add(entry);db.flush();_updated(db,state,15,0,now)
    state.streak_days=streak;state.last_checkin_day=day
    db.add(DailyCheckin(user_id=owner,effective_day=day,aura_ledger_id=entry.id,wallet_transaction_id=None,reward_mode="aura_v1",claimed_at=now));db.flush()
    return {"effective_day":day,"already_checked_in":False,"earned_xp_delta":15,"bonus_xp_delta":0,"khi_van_delta":0,"streak_days":streak}


def publish_v1(db,actor_id,now):
    """Operator-only publication: fixed approved bytes, existing DB ADMIN, no grants."""
    from app.aura_lock import lock_aura_mutation
    lock_aura_mutation(db)
    if db.scalar(select(User.id).join(UserRole,UserRole.user_id==User.id).join(Role,Role.id==UserRole.role_id).where(
        User.id==actor_id,User.status=="active",Role.code=="ADMIN")) is None:raise ValueError("An active database administrator is required.")
    policy=active_policy(db,now,False)
    if policy is None:
        version=(db.scalar(select(func.max(RewardPolicyVersion.version))) or 0)+1
        policy=RewardPolicyVersion(id=uuid4(),version=version,config_json=config(),status="published",effective_at=now,created_by=actor_id,created_at=now)
        db.add(policy);db.flush()
        # Baseline real existing sources as consumed, with zero awards; never retroactively farm them.
        sources=[("post",row,row.author_id,row.created_at,None) for row in db.scalars(select(Post))]
        sources += [("reaction",db.get(Post,row.post_id),row.user_id,row.created_at,None) for row in db.scalars(select(PostReaction))]
        sources += [("comment",db.get(Post,row.post_id),row.author_id,row.created_at,row) for row in db.scalars(select(Comment))]
        for kind,post,actor,occurred,comment in sources:
            event=_claim(db,policy,kind,post,actor,occurred,comment)
        initialized=0
        for user_id in db.scalars(select(User.id).order_by(User.id)):
            state=_state(db,user_id,now,initialize=True,locked=True)
            state.level_cached=level_progress(state.aura_xp_earned+state.aura_xp_bonus)["level"]
            state.fair_level_cached=level_progress(state.aura_xp_earned)["level"];initialized+=1
        db.add(AdminAuditLog(id=uuid4(),actor_id=actor_id,action="aura.policy.publish",target_type="reward_policy",target_id=str(policy.id),
            before_json=None,after_json={"schema":SCHEMA,"version":policy.version,"initialized":initialized},created_at=now));db.flush()
    return policy
