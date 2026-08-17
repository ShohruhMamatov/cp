from app.core.config import settings
from app.core.security import create_access_token

CREDS = {"login": "carol", "password": "password123", "password_repeat": "password123"}


async def test_register_returns_user_without_secrets(client):
    resp = await client.post("/auth", json=CREDS)
    assert resp.status_code == 201

    body = resp.json()
    assert body["login"] == "carol"
    assert "password" not in body
    assert "hashed_password" not in body


async def test_duplicate_login_conflicts(client):
    await client.post("/auth", json=CREDS)
    resp = await client.post("/auth", json=CREDS)
    assert resp.status_code == 409


async def test_password_mismatch_is_422(client):
    resp = await client.post(
        "/auth",
        json={"login": "carol", "password": "password123", "password_repeat": "nope"},
    )
    assert resp.status_code == 422


async def test_short_password_is_422(client):
    resp = await client.post(
        "/auth", json={"login": "carol", "password": "short", "password_repeat": "short"}
    )
    assert resp.status_code == 422


async def test_login_returns_one_hour_token(client):
    await client.post("/auth", json=CREDS)
    resp = await client.post("/login", json={"login": "carol", "password": "password123"})

    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["expires_in"] == 3600


async def test_wrong_password_is_401(client):
    await client.post("/auth", json=CREDS)
    resp = await client.post("/login", json={"login": "carol", "password": "wrongpass"})
    assert resp.status_code == 401


async def test_unknown_login_is_401(client):
    resp = await client.post("/login", json={"login": "ghost", "password": "password123"})
    assert resp.status_code == 401


async def test_missing_token_is_rejected(client):
    resp = await client.get("/me")
    assert resp.status_code == 401


async def test_garbage_token_is_401(client):
    resp = await client.get("/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


async def test_expired_token_is_401(client, alice, monkeypatch):
    monkeypatch.setattr(settings, "access_token_expire_minutes", -1)
    expired = create_access_token(user_id=1)

    resp = await client.get("/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


async def test_invite_token_rejected_as_access_token(client, alice):
    # The "typ" claim is what stops a share link being replayed as a login.
    invite = create_access_token(user_id=1, token_type="invite")
    resp = await client.get("/me", headers={"Authorization": f"Bearer {invite}"})
    assert resp.status_code == 401


async def test_password_change_invalidates_old_password(client, alice):
    resp = await client.post(
        "/auth/password",
        json={
            "old_password": "password123",
            "new_password": "newpassword456",
            "new_password_repeat": "newpassword456",
        },
        headers=alice,
    )
    assert resp.status_code == 204

    old = await client.post("/login", json={"login": "alice", "password": "password123"})
    assert old.status_code == 401

    new = await client.post("/login", json={"login": "alice", "password": "newpassword456"})
    assert new.status_code == 200
