async def test_creator_becomes_owner(client, alice, project):
    resp = await client.get("/projects", headers=alice)
    assert resp.status_code == 200

    body = resp.json()
    assert len(body) == 1
    assert body[0]["role"] == "owner"
    assert body[0]["total_size_bytes"] == 0


async def test_projects_list_is_scoped_to_user(client, bob, project):
    resp = await client.get("/projects", headers=bob)
    assert resp.json() == []


async def test_partial_update_preserves_other_fields(client, alice, project):
    resp = await client.put(
        f"/project/{project['id']}/info", json={"name": "Renamed"}, headers=alice
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renamed"
    assert resp.json()["description"] == "hello"  # not wiped by the partial PUT


async def test_non_member_gets_404_not_403(client, bob, project):
    # 403 would confirm the project exists to someone with no right to know.
    resp = await client.get(f"/project/{project['id']}/info", headers=bob)
    assert resp.status_code == 404


async def test_nonexistent_project_is_404(client, alice):
    resp = await client.get("/project/9999/info", headers=alice)
    assert resp.status_code == 404


async def test_invite_grants_read_access(client, alice, bob, project):
    resp = await client.post(f"/project/{project['id']}/invite?user=bob", headers=alice)
    assert resp.status_code == 204

    info = await client.get(f"/project/{project['id']}/info", headers=bob)
    assert info.status_code == 200

    listing = await client.get("/projects", headers=bob)
    assert listing.json()[0]["role"] == "participant"


async def test_participant_can_update(client, alice, bob, project):
    await client.post(f"/project/{project['id']}/invite?user=bob", headers=alice)
    resp = await client.put(f"/project/{project['id']}/info", json={"name": "Edited"}, headers=bob)
    assert resp.status_code == 200


async def test_participant_cannot_delete(client, alice, bob, project):
    await client.post(f"/project/{project['id']}/invite?user=bob", headers=alice)
    resp = await client.delete(f"/project/{project['id']}", headers=bob)
    assert resp.status_code == 403


async def test_participant_cannot_invite(client, alice, bob, project):
    await client.post(f"/project/{project['id']}/invite?user=bob", headers=alice)
    resp = await client.post(f"/project/{project['id']}/invite?user=alice", headers=bob)
    assert resp.status_code == 403


async def test_owner_can_delete(client, alice, project):
    resp = await client.delete(f"/project/{project['id']}", headers=alice)
    assert resp.status_code == 204

    gone = await client.get(f"/project/{project['id']}/info", headers=alice)
    assert gone.status_code == 404


async def test_invite_unknown_user_is_404(client, alice, project):
    resp = await client.post(f"/project/{project['id']}/invite?user=nobody", headers=alice)
    assert resp.status_code == 404


async def test_duplicate_invite_is_409(client, alice, bob, project):
    await client.post(f"/project/{project['id']}/invite?user=bob", headers=alice)
    resp = await client.post(f"/project/{project['id']}/invite?user=bob", headers=alice)
    assert resp.status_code == 409
