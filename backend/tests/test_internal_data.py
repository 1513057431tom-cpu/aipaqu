from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )
    assert response.status_code == 200


def create_material(client: TestClient, external_code: str) -> dict:
    response = client.post(
        "/api/v1/materials",
        json={
            "externalCode": external_code,
            "name": f"Material {external_code}",
            "baseUnit": "kg",
        },
    )
    assert response.status_code == 201
    return response.json()


def import_csv(
    client: TestClient,
    *,
    data_type: str,
    content: str,
    idempotency_key: str,
    source_system: str = "ERP",
):
    return client.post(
        "/api/v1/internal-data/imports",
        data={"dataType": data_type, "sourceSystem": source_system},
        files={"file": (f"{data_type.lower()}.csv", content.encode("utf-8"), "text/csv")},
        headers={"Idempotency-Key": idempotency_key},
    )


def test_internal_data_requires_authentication() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/inventory-snapshots")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_inventory_import_maps_material_and_reports_unknown_rows() -> None:
    client = TestClient(create_app())
    login(client)
    material = create_material(client, "OPS-INV-1001")
    csv_content = (
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,"
        "reservedQty,qualityHoldQty,unit,sourceRecordRef\n"
        "OPS-INV-1001,WH-A,2026-08-13T08:00:00+08:00,1200,900,200,100,kg,inv-1001\n"
        "OPS-UNKNOWN,WH-A,2026-08-13T08:00:00+08:00,10,10,0,0,kg,inv-1002\n"
    )

    response = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-import-1001",
    )

    assert response.status_code == 202
    result = response.json()
    assert result["status"] == "SUCCEEDED_WITH_ERRORS"
    assert result["createdRows"] == 1
    assert result["failedRows"] == 1
    assert result["errors"][0]["code"] == "MATERIAL_NOT_MAPPED"

    list_response = client.get(
        "/api/v1/inventory-snapshots",
        params={"materialId": material["id"]},
    )
    assert list_response.status_code == 200
    body = list_response.json()
    assert body["pagination"]["totalItems"] == 1
    assert body["data"][0]["availableQty"] == 900
    assert body["data"][0]["sourceSystem"] == "ERP"
    assert body["data"][0]["material"]["externalCode"] == "OPS-INV-1001"


def test_internal_data_import_is_idempotent_by_request_key() -> None:
    client = TestClient(create_app())
    login(client)
    create_material(client, "OPS-IDEMPOTENT-1001")
    csv_content = (
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "OPS-IDEMPOTENT-1001,WH-A,2026-08-13T09:00:00+08:00,20,18,kg,idem-1001\n"
    )

    first = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-idempotent-1001",
    )
    replay = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-idempotent-1001",
    )

    assert first.status_code == 202
    assert replay.status_code == 202
    assert replay.json()["jobId"] == first.json()["jobId"]
    assert replay.json()["replayed"] is True

    snapshots = client.get(
        "/api/v1/inventory-snapshots",
        params={"materialExternalCode": "OPS-IDEMPOTENT-1001"},
    ).json()
    assert snapshots["pagination"]["totalItems"] == 1


def test_idempotency_key_cannot_be_reused_for_another_source() -> None:
    client = TestClient(create_app())
    login(client)
    create_material(client, "OPS-IDEMPOTENT-SOURCE")
    csv_content = (
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "OPS-IDEMPOTENT-SOURCE,WH-A,2026-08-13T09:00:00+08:00,20,18,kg,idem-source\n"
    )

    first = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-source-conflict",
        source_system="ERP",
    )
    conflict = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-source-conflict",
        source_system="WMS",
    )

    assert first.status_code == 202
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_CONFLICT"


def test_consumption_demand_and_open_supply_imports_are_queryable() -> None:
    client = TestClient(create_app())
    login(client)
    material = create_material(client, "OPS-FLOW-1001")

    consumption = import_csv(
        client,
        data_type="CONSUMPTION",
        idempotency_key="consumption-1001",
        source_system="MES",
        content=(
            "materialExternalCode,bucketDate,actualQty,plannedQty,unit,sourceRecordRef\n"
            "OPS-FLOW-1001,2026-08-12,35,30,kg,cons-1001\n"
        ),
    )
    demand = import_csv(
        client,
        data_type="DEMAND",
        idempotency_key="demand-1001",
        source_system="MES",
        content=(
            "materialExternalCode,requiredAt,requiredQty,unit,sourceType,sourceRecordRef\n"
            "OPS-FLOW-1001,2026-08-20T08:00:00+08:00,500,kg,PRODUCTION_PLAN,dem-1001\n"
        ),
    )
    supply = import_csv(
        client,
        data_type="OPEN_SUPPLY",
        idempotency_key="supply-1001",
        content=(
            "materialExternalCode,orderNo,orderLineNo,orderedQty,receivedQty,openQty,"
            "unit,expectedAt,status,sourceRecordRef\n"
            "OPS-FLOW-1001,PO-1001,10,800,200,600,kg,2026-08-18T08:00:00+08:00,OPEN,po-1001-10\n"
        ),
    )

    assert consumption.json()["createdRows"] == 1
    assert demand.json()["createdRows"] == 1
    assert supply.json()["createdRows"] == 1

    endpoints = [
        "/api/v1/consumption-snapshots",
        "/api/v1/material-demands",
        "/api/v1/open-supply-snapshots",
    ]
    for endpoint in endpoints:
        response = client.get(endpoint, params={"materialId": material["id"]})
        assert response.status_code == 200
        assert response.json()["pagination"]["totalItems"] == 1


def test_inventory_import_rejects_impossible_available_quantity() -> None:
    client = TestClient(create_app())
    login(client)
    create_material(client, "OPS-INVALID-1001")
    csv_content = (
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "OPS-INVALID-1001,WH-A,2026-08-13T08:00:00+08:00,10,11,kg,invalid-1001\n"
    )

    response = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-invalid-1001",
    )

    assert response.status_code == 202
    assert response.json()["status"] == "FAILED"
    assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"


def test_internal_data_import_requires_a_unit_mapping() -> None:
    client = TestClient(create_app())
    login(client)
    create_material(client, "OPS-UNIT-1001")
    csv_content = (
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "OPS-UNIT-1001,WH-A,2026-08-13T08:00:00+08:00,10,9,ton,unit-1001\n"
    )

    response = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-unit-1001",
    )

    assert response.status_code == 202
    assert response.json()["status"] == "FAILED"
    assert response.json()["errors"][0]["code"] == "UNIT_MAPPING_REQUIRED"


def test_inventory_business_time_requires_timezone() -> None:
    client = TestClient(create_app())
    login(client)
    create_material(client, "OPS-TIMEZONE-1001")
    csv_content = (
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "OPS-TIMEZONE-1001,WH-A,2026-08-13T08:00:00,10,9,kg,timezone-1001\n"
    )

    response = import_csv(
        client,
        data_type="INVENTORY",
        content=csv_content,
        idempotency_key="inventory-timezone-1001",
    )

    assert response.status_code == 202
    assert response.json()["status"] == "FAILED"
    assert response.json()["errors"][0]["code"] == "VALIDATION_ERROR"
