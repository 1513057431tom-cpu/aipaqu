from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )
    assert response.status_code == 200


def test_materials_require_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/materials")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_create_and_filter_materials() -> None:
    client = TestClient(create_app())
    login(client)

    create_response = client.post(
        "/api/v1/materials",
        json={
            "externalCode": "  TEST-RM-1001  ",
            "name": "  基础原料 A  ",
            "specification": "工业级 25kg",
            "category": "原材料",
            "baseUnit": "kg",
            "safetyStockQty": 1200,
            "leadTimeDays": 14,
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["externalCode"] == "TEST-RM-1001"
    assert created["name"] == "基础原料 A"
    assert created["status"] == "ACTIVE"
    assert created["workspaceId"] == "default"

    list_response = client.get("/api/v1/materials", params={"q": "TEST-RM-1001"})

    assert list_response.status_code == 200
    body = list_response.json()
    assert body["pagination"]["totalItems"] == 1
    assert body["data"][0]["id"] == created["id"]


def test_duplicate_material_code_is_rejected() -> None:
    client = TestClient(create_app())
    login(client)
    payload = {
        "externalCode": "TEST-RM-DUPLICATE",
        "name": "测试物料",
        "baseUnit": "kg",
    }

    first_response = client.post("/api/v1/materials", json=payload)
    duplicate_response = client.post("/api/v1/materials", json=payload)

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["error"]["code"] == "MATERIAL_CODE_CONFLICT"


def test_update_material_changes_editable_fields() -> None:
    client = TestClient(create_app())
    login(client)
    created = client.post(
        "/api/v1/materials",
        json={
            "externalCode": "TEST-RM-EDIT-001",
            "name": "编辑前物料",
            "baseUnit": "kg",
            "safetyStockQty": 100,
            "leadTimeDays": 7,
        },
    ).json()

    response = client.patch(
        f"/api/v1/materials/{created['id']}",
        json={
            "externalCode": "TEST-RM-EDIT-002",
            "name": "编辑后物料",
            "specification": "25kg/袋",
            "category": "原材料",
            "baseUnit": "kg",
            "safetyStockQty": 250,
            "leadTimeDays": 12,
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["externalCode"] == "TEST-RM-EDIT-002"
    assert updated["name"] == "编辑后物料"
    assert updated["safetyStockQty"] == 250
    assert updated["leadTimeDays"] == 12
    assert updated["createdAt"] == created["createdAt"]
    assert updated["updatedAt"] >= created["updatedAt"]


def test_update_material_validates_not_found_conflict_and_empty_patch() -> None:
    client = TestClient(create_app())
    login(client)
    first = client.post(
        "/api/v1/materials",
        json={"externalCode": "TEST-RM-EDIT-A", "name": "物料 A", "baseUnit": "kg"},
    ).json()
    client.post(
        "/api/v1/materials",
        json={"externalCode": "TEST-RM-EDIT-B", "name": "物料 B", "baseUnit": "kg"},
    )

    conflict = client.patch(
        f"/api/v1/materials/{first['id']}",
        json={"externalCode": "test-rm-edit-b"},
    )
    missing = client.patch("/api/v1/materials/mat_missing", json={"name": "不存在"})
    empty = client.patch(f"/api/v1/materials/{first['id']}", json={})
    null_value = client.patch(f"/api/v1/materials/{first['id']}", json={"baseUnit": None})

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "MATERIAL_CODE_CONFLICT"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "MATERIAL_NOT_FOUND"
    assert empty.status_code == 422
    assert null_value.status_code == 422


def test_material_groups_form_a_tree_and_filter_materials() -> None:
    client = TestClient(create_app())
    login(client)

    root = client.post(
        "/api/v1/material-groups",
        json={"code": "TEST-RAW", "name": "原材料"},
    )
    assert root.status_code == 201
    child = client.post(
        "/api/v1/material-groups",
        json={
            "code": "TEST-RAW-SOLVENT",
            "name": "溶剂",
            "parentId": root.json()["id"],
        },
    )
    assert child.status_code == 201

    material = client.post(
        "/api/v1/materials",
        json={
            "externalCode": "TEST-GROUP-MAT-001",
            "name": "测试溶剂",
            "baseUnit": "kg",
            "groupId": child.json()["id"],
        },
    )
    assert material.status_code == 201
    assert material.json()["groupId"] == child.json()["id"]

    groups = client.get("/api/v1/material-groups")
    assert groups.status_code == 200
    group_by_id = {item["id"]: item for item in groups.json()["data"]}
    assert group_by_id[root.json()["id"]]["parentId"] is None
    assert group_by_id[child.json()["id"]]["parentId"] == root.json()["id"]
    assert group_by_id[child.json()["id"]]["materialCount"] == 1

    filtered = client.get(
        "/api/v1/materials",
        params={"groupId": child.json()["id"]},
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["data"]] == [material.json()["id"]]


def test_create_and_list_suppliers() -> None:
    client = TestClient(create_app())
    login(client)

    create_response = client.post(
        "/api/v1/suppliers",
        json={
            "externalCode": "TEST-SUP-1001",
            "name": "华东供应商",
            "website": "https://supplier.example.com",
            "country": "CN",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "ACTIVE"

    list_response = client.get("/api/v1/suppliers", params={"q": "华东"})

    assert list_response.status_code == 200
    assert list_response.json()["data"][0]["id"] == created["id"]


def test_csv_import_creates_materials_and_reports_invalid_rows() -> None:
    client = TestClient(create_app())
    login(client)
    csv_content = (
        "externalCode,name,specification,category,baseUnit,safetyStockQty,leadTimeDays\n"
        "TEST-CSV-1001,导入物料 A,25kg,原材料,kg,1000,12\n"
        "TEST-CSV-1002,缺少单位,25kg,原材料,,500,7\n"
    )

    response = client.post(
        "/api/v1/imports",
        data={"entityType": "MATERIAL"},
        files={"file": ("materials.csv", csv_content.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "SUCCEEDED_WITH_ERRORS"
    assert body["totalRows"] == 2
    assert body["createdRows"] == 1
    assert body["failedRows"] == 1
    assert body["errors"][0]["row"] == 3

    list_response = client.get("/api/v1/materials", params={"q": "TEST-CSV-1001"})
    assert list_response.json()["pagination"]["totalItems"] == 1


def test_csv_import_rejects_unsupported_file_type() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.post(
        "/api/v1/imports",
        data={"entityType": "MATERIAL"},
        files={"file": ("materials.txt", b"externalCode,name", "text/plain")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "UNSUPPORTED_IMPORT_TYPE"


def test_supplier_csv_import_allows_blank_optional_fields() -> None:
    client = TestClient(create_app())
    login(client)
    csv_content = (
        "externalCode,name,website,country\n"
        "TEST-CSV-SUP-1001,导入供应商,,CN\n"
    )

    response = client.post(
        "/api/v1/imports",
        data={"entityType": "SUPPLIER"},
        files={"file": ("suppliers.csv", csv_content.encode("utf-8"), "text/csv")},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "SUCCEEDED"
    assert response.json()["createdRows"] == 1


def test_csv_import_rejects_files_without_data_rows() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.post(
        "/api/v1/imports",
        data={"entityType": "MATERIAL"},
        files={
            "file": (
                "materials.csv",
                b"externalCode,name,baseUnit\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "CSV_HAS_NO_DATA_ROWS"
