"""Register only the dedicated test server in the existing local pgAdmin profile."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess

root = Path(__file__).resolve().parent.parent
private = root / '.qa-test-db'
admin = Path('C:/Program Files/PostgreSQL/18/pgAdmin 4')
database = Path(os.environ['APPDATA']) / 'pgAdmin/pgadmin4.db'
password = (private / 'application-password.txt').read_text(encoding='utf-8').strip()
passfile = private / 'pgpass.conf'
passfile.write_text('127.0.0.1:5433:qa_test_data:qa_data:' + password.replace('\\', '\\\\').replace(':', '\\:') + '\n', encoding='utf-8')
name = 'QA Framework - Test Data (5433)'
document = {'Servers': {'1': {'Name': name, 'Group': 'QA Framework',
    'Host': '127.0.0.1', 'Port': 5433, 'MaintenanceDB': 'qa_test_data',
    'Username': 'qa_data', 'SSLMode': 'prefer', 'PassFile': str(passfile)}}}
server_file = private / 'pgadmin-servers.json'
server_file.write_text(json.dumps(document, indent=2), encoding='utf-8')
if not database.exists():
    raise SystemExit('Open pgAdmin once, then rerun this command. Import file is ready in .qa-test-db.')
with sqlite3.connect(database) as connection:
    users = connection.execute('SELECT id,email FROM user ORDER BY id').fetchall()
    if len(users) != 1:
        raise SystemExit('Several pgAdmin profiles found; import .qa-test-db/pgadmin-servers.json in the intended profile.')
    user_id, email = users[0]
    exists = connection.execute('SELECT count(*) FROM server WHERE user_id=? AND name=?', (user_id, name)).fetchone()[0]
    if not exists:
        with sqlite3.connect(private / 'pgadmin-before-registration.db') as backup:
            connection.backup(backup)
if not exists:
    env = os.environ.copy()
    env['PGADMIN_CONFIG_SERVER_MODE'] = 'False'
    result = subprocess.run([str(admin / 'python/python.exe'), str(admin / 'web/setup.py'),
        'load-servers', str(server_file), '--user', email, '--sqlite-path', str(database)],
        cwd=admin / 'web', env=env, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise SystemExit('pgAdmin registration failed; use its Import/Export Servers dialog with the generated file.')
with sqlite3.connect(database) as connection:
    found = connection.execute('SELECT count(*) FROM server WHERE user_id=? AND name=?', (user_id, name)).fetchone()[0]
if not found:
    raise SystemExit('Registration not confirmed; import .qa-test-db/pgadmin-servers.json manually.')
print('Dedicated test-data connection registered in pgAdmin; credentials are in a local passfile, not in the JSON import.')
