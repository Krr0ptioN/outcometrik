import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client


@pytest.mark.django_db
def test_seed_credentials_and_existing_administrator_can_view_demo_dashboard(tmp_path, settings):
    settings.DEBUG = True
    operator = get_user_model().objects.create_user(username="operator", password="operator-pass")
    credentials = tmp_path / "credentials.json"
    call_command(
        "seed_acibadem", credentials_file=str(credentials), administrator=operator.username
    )
    data = json.loads(credentials.read_text())
    client = Client()
    demo = data["accounts"]["administrators"][0]
    assert client.login(username=demo["username"], password=demo["password"])
    scope = data["institution"]["scope_id"]
    response = client.get("/api/access/dashboard/", {"scope": scope})
    assert response.status_code == 200
    assert response.json()["counts"]["users"] > 1
    client.logout()
    assert client.login(username="operator", password="operator-pass")
    assert client.get("/api/access/dashboard/", {"scope": scope}).status_code == 200
    call_command(
        "seed_acibadem", credentials_file=str(credentials), administrator=operator.username
    )
    assert client.get("/api/access/dashboard/", {"scope": scope}).status_code == 200
