"""Real-PostgreSQL, rollback-only tests of Vault Exp (no demo DB)."""
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event, text

from test_vault_v1_runtime import runtime_vault, opening, counts
from test_auth import auth, migrated, register, login
from app.aura_v1 import day_window
from app.vault_exp_award import reward_amount, VAULT_KEY_PREFIX


def test_exp_cap_pure_function():
    assert reward_amount(0) == 2
    assert reward_amount(99) == 2
    assert reward_amount(100) == 0
    assert reward_amount(101) == 0
    for bad in (-1, 1.2, True):
        with pytest.raises(ValueError):
            reward_amount(bad)


def test_exp_day_boundary_uses_0700_vietnam():
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    before = datetime(2026, 11, 15, 6, 59, 59, tzinfo=tz)
    after = datetime(2026, 11, 15, 7, 0, 0, tzinfo=tz)
    assert day_window(before)[0].isoformat() == "2026-11-14"
    assert day_window(after)[0].isoformat() == "2026-11-15"
    assert day_window(before)[2] == day_window(after)[1]


@pytest.mark.integration
def test_vault_open_awards_without_separate_aura_policy(runtime_vault):
    client, c, owner, cases, vault_policy, _, _ = runtime_vault
    assert c.scalar(text("SELECT count(*) FROM reward_policy_versions WHERE config_json->>'schema' = 'aurameme-aura-v1'")) == 0
    result = opening(client, cases['avatar'])
    assert result.status_code == 200, result.text
    rows = c.execute(text("SELECT event_key,event_type,base_xp,bonus_xp,policy_id "
                          "FROM aura_ledger WHERE user_id=:uid"), {"uid": owner}).all()
    assert len(rows) == 1
    assert rows[0].event_key == VAULT_KEY_PREFIX + result.json()['open_id']
    assert (rows[0].event_type, rows[0].base_xp, rows[0].bonus_xp, rows[0].policy_id) == (
        'adjustment', 2, 0, vault_policy)
    cached = c.execute(text("SELECT aura_xp_earned,aura_xp_bonus,level_cached FROM user_progress WHERE user_id=:uid"),
                       {"uid": owner}).one()
    assert cached == (2, 0, 1)
    assert counts(c)['wallet_transactions'] == 0
    # Aura progress *reads* may remain unavailable until its own policy is
    # published; the valid Vault opening must not return HTTP 503.


@pytest.mark.integration
def test_both_case_types_retry_and_different_users(runtime_vault):
    client, c, owner, cases, _, _, _ = runtime_vault
    first = opening(client, cases['avatar'], 'vault-exp-avatar-once')
    assert first.status_code == 200, first.text
    retry = opening(client, cases['avatar'], 'vault-exp-avatar-once')
    assert retry.status_code == 200 and retry.json()['already_processed']
    assert c.scalar(text('SELECT count(*) FROM aura_ledger WHERE user_id=:u'), {'u': owner}) == 1
    now = client.app.state.auth.now() + timedelta(seconds=2)
    client.app.state.auth.now = lambda: now
    second = opening(client, cases['background'], 'vault-exp-background')
    assert second.status_code == 200, second.text
    assert c.scalar(text('SELECT sum(base_xp) FROM aura_ledger WHERE user_id=:u'), {'u': owner}) == 4

    client.cookies.clear()
    created = register(client, username='vault_exp_second', email='vault-exp-second@example.com')
    assert created.status_code == 201, created.text
    other = UUID(created.json()['id'])
    assert login(client, email='vault-exp-second@example.com').status_code == 200
    if hasattr(client, '_vault_token'):
        del client._vault_token
    third = opening(client, cases['background'], 'vault-exp-other-user')
    assert third.status_code == 200, third.text
    assert c.scalar(text('SELECT sum(base_xp) FROM aura_ledger WHERE user_id=:u'), {'u': other}) == 2
    assert c.scalar(text('SELECT sum(base_xp) FROM aura_ledger WHERE user_id=:u'), {'u': owner}) == 4


@pytest.mark.integration
def test_first_100_openings_reward_but_101st_still_grants_item(runtime_vault):
    client, c, owner, cases, _, _, _ = runtime_vault
    now = client.app.state.auth.now()
    for i in range(1, 102):
        instant = now
        client.app.state.auth.now = lambda instant=instant: instant
        case = cases['avatar' if i % 2 else 'background']
        result = opening(client, case, f'vault-exp-boundary-{i:03}')
        assert result.status_code == 200, f'open {i}: {result.text}'
        now += timedelta(seconds=5 if i % 10 == 0 else 2)
    assert c.scalar(text('SELECT count(*) FROM case_opens')) == 101
    assert c.scalar(text('SELECT count(*) FROM inventory_grants')) == 101
    assert c.scalar(text('SELECT sum(quantity) FROM user_inventory')) == 101
    assert c.scalar(text('SELECT count(*) FROM aura_ledger WHERE user_id=:uid AND event_key LIKE :prefix'),
                    {'uid': owner, 'prefix': VAULT_KEY_PREFIX + '%'}) == 100
    assert c.scalar(text('SELECT sum(base_xp) FROM aura_ledger WHERE user_id=:uid'), {'uid': owner}) == 200
    assert c.scalar(text('SELECT aura_xp_earned FROM user_progress WHERE user_id=:uid'), {'uid': owner}) == 200
    assert counts(c)['wallet_transactions'] == 0


@pytest.mark.integration
def test_exp_insert_failure_rolls_back_receipt_and_inventory(runtime_vault):
    client, c, owner, cases, _, _, _ = runtime_vault

    def refuse_ledger(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith('INSERT INTO aura_ledger'):
            raise RuntimeError('synthetic aura ledger insertion failure')

    event.listen(c, 'before_cursor_execute', refuse_ledger)
    try:
        with pytest.raises(RuntimeError, match='synthetic aura ledger'):
            opening(client, cases['avatar'], 'vault-exp-rollback')
    finally:
        event.remove(c, 'before_cursor_execute', refuse_ledger)

    assert counts(c)['case_opens'] == 0
    assert counts(c)['inventory_grants'] == 0
    assert counts(c)['user_inventory'] == 0
    assert counts(c)['aura_ledger'] == 0
    assert counts(c)['user_progress'] == 0
    okay = opening(client, cases['avatar'], 'vault-exp-rollback')
    assert okay.status_code == 200, okay.text
    assert counts(c)['aura_ledger'] == 1
