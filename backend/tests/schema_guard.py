"""Allow only reviewed immutable-ledger/policy triggers; never ignore unknown SQL."""
import hashlib
from sqlalchemy import text

FUNCTION_HASHES = {'aurameme_immutable_ledger': '16133b0d1c38d3a566921db341effef89e3f9692e716bd5038350dd91cd66c8a', 'aurameme_immutable_policy': 'b067b4a3b866faefeff3d6218e0be4fb250ba22b65916858ee6a548f869e56d5'}


def assert_auxiliary_objects(connection):
    revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
    expected_functions = dict(FUNCTION_HASHES)
    if revision == '0007_inventory':
        expected_functions['aurameme_equipment_guard'] = '3857f5f969ff012cee8d521c930cc4ef43b8b3593388dc16e14a2430a5b8f264'
    functions = connection.execute(text("SELECT p.proname,p.prosrc,p.prosecdef,p.pronargs,p.prorettype::regtype::text,l.lanname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname='public'")).all()
    assert len(functions) == len(expected_functions), "Unknown or missing public functions"
    for name, body, security_definer, arguments, result, language in functions:
        assert name in expected_functions and not security_definer and arguments == 0 and result == 'trigger' and language == 'plpgsql'
        assert hashlib.sha256(' '.join(body.split()).encode()).hexdigest() == expected_functions[name], "Changed immutable function body"
    triggers = connection.execute(text("SELECT t.tgname,c.relname,p.proname,t.tgtype,t.tgenabled,t.tgqual IS NULL,t.tgnargs,t.tgconstraint FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='public' AND NOT t.tgisinternal")).all()
    expected = {
        ('aura_ledger_no_truncate','aura_ledger','aurameme_immutable_ledger',34,'O',True,0,0),
        ('reward_policy_no_truncate','reward_policy_versions','aurameme_immutable_ledger',34,'O',True,0,0),
        ('aura_ledger_immutable','aura_ledger','aurameme_immutable_ledger',27,'O',True,0,0),
        ('reward_policy_immutable','reward_policy_versions','aurameme_immutable_policy',27,'O',True,0,0),
    }
    revision = connection.scalar(text('SELECT version_num FROM alembic_version'))
    assert revision in {'0003_aura_draft','0004_wallet_read','0005_checkin','0006_catalog','0007_inventory'}, "Unknown schema revision"
    if revision in {'0005_checkin','0006_catalog','0007_inventory'}:
        for table in ['wallet_transactions','daily_checkins']:
            expected.add((table+'_immutable',table,'aurameme_immutable_ledger',27,'O',True,0,0))
            expected.add((table+'_no_truncate',table,'aurameme_immutable_ledger',34,'O',True,0,0))
    if revision == '0007_inventory':
        for table,kind in [('user_equipment',23),('user_inventory',27),('asset_items',27)]:
            expected.add((table+'_guard',table,'aurameme_equipment_guard',kind,'O',True,0,0))
    assert set(triggers) == expected, "Unknown, changed or disabled triggers"
