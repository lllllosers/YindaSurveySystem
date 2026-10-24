"""Real PostgreSQL DDL regression in a disposable, separately named database.

Run with APP_ENV=test and a test-cluster role with CREATEDB permission.
"""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from app.core.config import settings


def test_media_uid_upgrade_preserves_data_and_downgrade_refuses_long_uid():
    if settings.app_env != "test":
        pytest.skip("Requires APP_ENV=test and a disposable PostgreSQL cluster with CREATEDB permission")
    database = "yinda_media_migration_test_" + uuid4().hex[:12]
    connection_args = dict(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                           password=settings.db_password)
    environment = {**os.environ, "DB_NAME": database}
    backend = Path(__file__).resolve().parents[1]

    def migrate(*args, success=True):
        result = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend,
                                env=environment, capture_output=True, text=True)
        if success:
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            assert result.returncode != 0, result.stdout + result.stderr
        return result

    def workflow_script(source, *args):
        result = subprocess.run([sys.executable, "-c", source, *args], cwd=backend,
                                env=environment, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        return result.stdout.strip()

    def media_rows():
        with psycopg.connect(dbname=database, **connection_args) as db:
            return db.execute("SELECT * FROM central_survey_media ORDER BY id").fetchall()

    def schema_state():
        with psycopg.connect(dbname=database, **connection_args) as db:
            length = db.execute("SELECT character_maximum_length FROM information_schema.columns "
                                "WHERE table_name='central_survey_media' AND column_name='media_uid'").fetchone()[0]
            version = db.execute("SELECT version_num FROM alembic_version").fetchone()[0]
            indexes = db.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename='central_survey_media' "
                                 "ORDER BY indexname").fetchall()
            return length, version, indexes

    old_uid, long_uid = uuid4().hex, str(uuid4())
    insert = ("INSERT INTO central_survey_media "
              "(media_uid, survey_record_uid, package_path, file_sha256, file_size, payload_json, current_submission_uid) "
              "VALUES (%s, %s, %s, %s, %s, %s, %s)")
    record_uid, submission_uid = uuid4().hex, uuid4().hex
    old_values = (old_uid, record_uid, f"media/{old_uid}.jpg", "a" * 64, 123, '{"legacy":true}', submission_uid)
    new_values = (long_uid, record_uid, f"media/{long_uid}.jpg", "b" * 64, 456, '{"uuid":true}', submission_uid)
    with psycopg.connect(dbname="postgres", autocommit=True, **connection_args) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        try:
            migrate("upgrade", "20260927_0213")
            assert schema_state()[:2] == (32, "20260927_0213")
            with psycopg.connect(dbname=database, **connection_args) as db:
                db.execute(insert, old_values)
            old_rows = media_rows()
            old_indexes = schema_state()[2]
            with pytest.raises(psycopg.errors.StringDataRightTruncation):
                with psycopg.connect(dbname=database, **connection_args) as db:
                    db.execute(insert, new_values)
            # Exercise the exact reported failure through ZIP inspection,
            # preflight, review and API commit against the old real schema.
            submission = workflow_script('''
from fastapi.testclient import TestClient
from app.main import app
from tests.auth_helpers import create_test_user, login_client
from tests.test_result_workflow_api import create_project_batch_and_task, make_formal_result_package, accept_formal, assert_formal_counts
from uuid import uuid4
client = TestClient(app)
admin = create_test_user("admin")
csrf = login_client(client, admin.username)
project, batch, task, scope = create_project_batch_and_task(client, csrf, uuid4().hex[:8], department=True)
package, _, _ = make_formal_result_package(project_uid=project, batch_uid=batch, task_uid=task["task_uid"], scope=scope, record_count=10, media_count=25)
uploaded = client.post("/api/v1/result-submissions/upload", headers={"X-CSRF-Token": csrf}, files={"file": ("migration.ydresult", package, "application/octet-stream")})
assert uploaded.status_code == 201, uploaded.text
uid = uploaded.json()["submission_uid"]
accept_formal(client, csrf, uid)
failed = client.post(f"/api/v1/result-submissions/{uid}/import", headers={"X-CSRF-Token": csrf})
assert failed.status_code == 500, failed.text
assert_formal_counts(uid, (0, 0, 0, 0))
assert client.get(f"/api/v1/result-submissions/{uid}").json()["status"] == "accepted"
assert client.get(f"/api/v1/survey-tasks/{task['task_uid']}").json()["status"] == "result_received"
print(uid)
''')
            assert media_rows() == old_rows
            migrate("upgrade", "head")
            assert schema_state() == (36, "20261024_0214", old_indexes)
            assert media_rows() == old_rows
            workflow_script('''
import sys
from fastapi.testclient import TestClient
from app.main import app
from tests.auth_helpers import create_test_user, login_client
from tests.test_result_workflow_api import assert_formal_counts
uid = sys.argv[1]
client = TestClient(app)
csrf = login_client(client, create_test_user("admin").username)
headers = {"X-CSRF-Token": csrf}
response = client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers)
assert response.status_code == 200, response.text
assert response.json()["status"] == "imported"
assert_formal_counts(uid, (10, 10, 10, 25))
assert client.post(f"/api/v1/result-submissions/{uid}/import", headers=headers).status_code == 409
''', submission)
            with psycopg.connect(dbname=database, **connection_args) as db:
                db.execute(insert, new_values)
            upgraded_rows = media_rows()
            rejected = migrate("downgrade", "20260927_0213", success=False)
            assert "Cannot downgrade" in rejected.stderr
            assert media_rows() == upgraded_rows
            assert schema_state() == (36, "20261024_0214", old_indexes)
            with psycopg.connect(dbname=database, **connection_args) as db:
                db.execute("DELETE FROM central_survey_media WHERE length(media_uid)>32")
            migrate("downgrade", "20260927_0213")
            assert schema_state() == (32, "20260927_0213", old_indexes)
            assert media_rows() == old_rows
            migrate("upgrade", "head")
            assert media_rows() == old_rows
        finally:
            # The name is generated above, never read from application config.
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
