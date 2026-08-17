from pathlib import Path

from app.core.config import settings

PDF = b"%PDF-1.4\nfake pdf content for testing\n"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def pdf(name: str = "report.pdf", content: bytes = PDF):
    return {"files": (name, content, "application/pdf")}


async def upload(client, headers, project_id: int, files=None):
    return await client.post(
        f"/project/{project_id}/documents", files=files or pdf(), headers=headers
    )


async def test_upload_updates_size_counter(client, alice, project):
    resp = await upload(client, alice, project["id"])
    assert resp.status_code == 201

    body = resp.json()
    assert len(body) == 1
    assert body[0]["size_bytes"] == len(PDF)
    assert body[0]["filename"] == "report.pdf"

    info = await client.get(f"/project/{project['id']}/info", headers=alice)
    assert info.json()["total_size_bytes"] == len(PDF)


async def test_storage_key_is_never_exposed(client, alice, project):
    resp = await upload(client, alice, project["id"])
    assert "storage_key" not in resp.json()[0]
    assert "s3_key" not in resp.json()[0]


async def test_stored_filename_is_not_client_controlled(client, alice, project, tmp_path):
    await upload(client, alice, project["id"], files=pdf("../../evil.pdf"))

    written = list(Path(tmp_path).rglob("*.pdf"))
    assert len(written) == 1
    assert "evil" not in written[0].name  # UUID on disk, real name only in the DB


async def test_multiple_files_in_one_request(client, alice, project):
    files = [
        ("files", ("a.pdf", PDF, "application/pdf")),
        ("files", ("b.docx", b"fake docx", DOCX_TYPE)),
    ]
    resp = await upload(client, alice, project["id"], files=files)

    assert resp.status_code == 201
    assert len(resp.json()) == 2

    info = await client.get(f"/project/{project['id']}/info", headers=alice)
    assert info.json()["total_size_bytes"] == len(PDF) + len(b"fake docx")


async def test_wrong_content_type_is_415(client, alice, project):
    resp = await upload(
        client, alice, project["id"], files={"files": ("n.txt", b"hi", "text/plain")}
    )
    assert resp.status_code == 415


async def test_batch_rejected_entirely_if_one_file_is_bad(client, alice, project):
    files = [
        ("files", ("good.pdf", PDF, "application/pdf")),
        ("files", ("bad.txt", b"hi", "text/plain")),
    ]
    resp = await upload(client, alice, project["id"], files=files)
    assert resp.status_code == 415

    listing = await client.get(f"/project/{project['id']}/documents", headers=alice)
    assert listing.json() == []  # nothing written, not a half-applied batch


async def test_oversized_file_is_413(client, alice, project, monkeypatch):
    monkeypatch.setattr(settings, "max_file_bytes", 10)
    resp = await upload(client, alice, project["id"])
    assert resp.status_code == 413


async def test_project_quota_is_enforced(client, alice, project, monkeypatch):
    monkeypatch.setattr(settings, "max_project_bytes", len(PDF) + 5)

    first = await upload(client, alice, project["id"])
    assert first.status_code == 201

    second = await upload(client, alice, project["id"])
    assert second.status_code == 413


async def test_download_returns_original_bytes(client, alice, project):
    doc_id = (await upload(client, alice, project["id"])).json()[0]["id"]

    resp = await client.get(f"/document/{doc_id}", headers=alice)
    assert resp.status_code == 200
    assert resp.content == PDF


async def test_non_member_cannot_download(client, alice, bob, project):
    doc_id = (await upload(client, alice, project["id"])).json()[0]["id"]

    resp = await client.get(f"/document/{doc_id}", headers=bob)
    assert resp.status_code == 404


async def test_update_replaces_content_and_adjusts_counter(client, alice, project):
    doc_id = (await upload(client, alice, project["id"])).json()[0]["id"]
    replacement = b"%PDF-1.4\nlonger replacement content here\n"

    resp = await client.put(
        f"/document/{doc_id}",
        files={"file": ("new.pdf", replacement, "application/pdf")},
        headers=alice,
    )
    assert resp.status_code == 200
    assert resp.json()["size_bytes"] == len(replacement)

    info = await client.get(f"/project/{project['id']}/info", headers=alice)
    assert info.json()["total_size_bytes"] == len(replacement)

    fetched = await client.get(f"/document/{doc_id}", headers=alice)
    assert fetched.content == replacement


async def test_delete_removes_row_file_and_counter(client, alice, project, tmp_path):
    doc_id = (await upload(client, alice, project["id"])).json()[0]["id"]

    resp = await client.delete(f"/document/{doc_id}", headers=alice)
    assert resp.status_code == 204

    info = await client.get(f"/project/{project['id']}/info", headers=alice)
    assert info.json()["total_size_bytes"] == 0
    assert list(Path(tmp_path).rglob("*.pdf")) == []


async def test_deleting_project_removes_its_files(client, alice, project, tmp_path):
    await upload(client, alice, project["id"])
    assert len(list(Path(tmp_path).rglob("*.pdf"))) == 1

    await client.delete(f"/project/{project['id']}", headers=alice)
    assert list(Path(tmp_path).rglob("*.pdf")) == []
