import io

from conftest import auth


def test_export_csv_sales(client, owner_token):
    response = client.get("/api/v1/export.csv?type=sales", headers=auth(owner_token))
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "sales.csv" in response.headers["content-disposition"]
    lines = response.text.strip().splitlines()
    assert lines[0] == "id,created_at,tender,volume_litres,unit_price,amount"


def test_export_csv_collections(client, manager_token):
    response = client.get("/api/v1/export.csv?type=collections", headers=auth(manager_token))
    assert response.status_code == 200
    assert response.text.startswith("date,mode,amount")


def test_import_credit_customers_dry_run_then_commit(client, manager_token):
    csv_content = "account_code,name,credit_limit\nAC-100,Alpha Transport,50000\nAC-101,Beta Agro,75000\nAC-BAD,No Limit,\n"
    upload = io.BytesIO(csv_content.encode())

    dry = client.post(
        "/api/v1/credit/customers/import.csv?validate_only=true",
        headers=auth(manager_token),
        files={"file": ("customers.csv", upload, "text/csv")},
    )
    assert dry.status_code == 200
    body = dry.json()
    assert body["validate_only"] is True
    assert body["created"] == 0
    assert body["summary"]["valid"] == 2
    assert body["summary"]["invalid"] == 1

    # dry run persisted nothing
    listed = client.get("/api/v1/credit/customers", headers=auth(manager_token)).json()
    assert [c["account_code"] for c in listed] == []

    commit = client.post(
        "/api/v1/credit/customers/import.csv?validate_only=false",
        headers=auth(manager_token),
        files={"file": ("customers.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert commit.status_code == 200
    assert commit.json()["created"] == 2

    listed = client.get("/api/v1/credit/customers", headers=auth(manager_token)).json()
    assert sorted(c["account_code"] for c in listed) == ["AC-100", "AC-101"]


def test_import_rejects_wrong_columns(client, manager_token):
    bad = io.BytesIO(b"code,name\nAC-1,Only two cols\n")
    response = client.post(
        "/api/v1/credit/customers/import.csv",
        headers=auth(manager_token),
        files={"file": ("bad.csv", bad, "text/csv")},
    )
    assert response.status_code == 422


def test_import_rejects_duplicates(client, manager_token):
    client.post(
        "/api/v1/credit/customers",
        headers=auth(manager_token),
        json={"account_code": "AC-200", "name": "Existing Co", "credit_limit": "10000"},
    )
    csv_content = "account_code,name,credit_limit\nAC-200,Duplicate Co,99999\n"
    response = client.post(
        "/api/v1/credit/customers/import.csv?validate_only=false",
        headers=auth(manager_token),
        files={"file": ("dup.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert response.json()["summary"]["invalid"] == 1
