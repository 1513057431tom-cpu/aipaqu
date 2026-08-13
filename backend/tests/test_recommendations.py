from fastapi.testclient import TestClient

from app.main import create_app


def login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "change-me-now"},
    )
    assert response.status_code == 200


def import_csv(
    client: TestClient,
    data_type: str,
    content: str,
    key: str,
) -> None:
    response = client.post(
        "/api/v1/internal-data/imports",
        data={"dataType": data_type, "sourceSystem": "ERP"},
        files={"file": (f"{data_type}.csv", content.encode(), "text/csv")},
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 202
    assert response.json()["failedRows"] == 0


def test_generate_recommendation_is_deterministic_and_reviewable() -> None:
    client = TestClient(create_app())
    login(client)
    material_response = client.post(
        "/api/v1/materials",
        json={
            "externalCode": "REC-MVP-001",
            "name": "Recommendation sample",
            "baseUnit": "kg",
            "safetyStockQty": 100,
            "leadTimeDays": 7,
        },
    )
    assert material_response.status_code == 201
    import_csv(
        client,
        "INVENTORY",
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "REC-MVP-001,WH-A,2026-08-13T08:00:00+08:00,220,200,kg,rec-inv-001\n",
        "rec-inventory-001",
    )
    import_csv(
        client,
        "DEMAND",
        "materialExternalCode,requiredAt,requiredQty,unit,sourceType,sourceRecordRef\n"
        "REC-MVP-001,2026-08-20T08:00:00+08:00,1000,kg,PLAN,rec-dem-001\n",
        "rec-demand-001",
    )
    import_csv(
        client,
        "OPEN_SUPPLY",
        "materialExternalCode,orderNo,orderLineNo,orderedQty,receivedQty,openQty,unit,expectedAt,status,sourceRecordRef\n"
        "REC-MVP-001,PO-REC,10,300,0,300,kg,2026-08-18T08:00:00+08:00,OPEN,rec-supply-001\n",
        "rec-supply-001",
    )

    first = client.post(
        "/api/v1/procurement-recommendations/generate",
        json={"asOfDate": "2026-08-13", "horizonDays": 30},
    )
    replay = client.post(
        "/api/v1/procurement-recommendations/generate",
        json={"asOfDate": "2026-08-13", "horizonDays": 30},
    )

    assert first.status_code == 201
    recommendation = first.json()["recommendations"][0]
    assert recommendation["recommendedQty"] == 600
    assert recommendation["calculation"] == {
        "availableQty": 200.0,
        "demandQty": 1000.0,
        "openSupplyQty": 300.0,
        "safetyStockQty": 100.0,
        "consumptionDailyQty": 0.0,
        "leadTimeDays": 7,
        "projectedBalanceQty": -500.0,
    }
    assert recommendation["algorithm"] == {
        "key": "deterministic-reorder-point",
        "version": "1.0.0",
    }
    assert recommendation["inputDigest"].startswith("sha256:")
    assert recommendation["status"] == "PROPOSED"
    assert len(recommendation["evidenceRefs"]) == 3
    assert replay.status_code == 200
    assert replay.json()["replayed"] is True
    assert replay.json()["recommendations"][0]["id"] == recommendation["id"]

    approved = client.post(
        f"/api/v1/procurement-recommendations/{recommendation['id']}/decisions",
        headers={"If-Match": '"1"'},
        json={"decision": "APPROVE", "reason": "数据已复核"},
    )
    stale = client.post(
        f"/api/v1/procurement-recommendations/{recommendation['id']}/decisions",
        headers={"If-Match": '"1"'},
        json={"decision": "REJECT", "reason": "并发旧请求"},
    )

    assert approved.status_code == 201
    assert approved.json()["recommendation"]["status"] == "APPROVED"
    assert approved.json()["recommendation"]["version"] == 2
    assert approved.json()["decision"]["actorId"]
    history = client.get(
        f"/api/v1/procurement-recommendations/{recommendation['id']}/decisions"
    )
    assert history.status_code == 200
    assert history.json()["data"][0]["reason"] == "数据已复核"
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"

    unchanged = client.post(
        f"/api/v1/procurement-recommendations/{recommendation['id']}/decisions",
        headers={"If-Match": '"2"'},
        json={
            "decision": "ADJUST",
            "adjustedQty": recommendation["recommendedQty"],
            "reason": "没有实际变化",
        },
    )
    assert unchanged.status_code == 422
    assert unchanged.json()["error"]["code"] == "ADJUSTMENT_UNCHANGED"


def test_adjustment_requires_a_changed_value_and_reason() -> None:
    client = TestClient(create_app())
    login(client)

    response = client.post(
        "/api/v1/procurement-recommendations/missing/decisions",
        headers={"If-Match": '"1"'},
        json={"decision": "ADJUST", "reason": ""},
    )

    assert response.status_code == 422


def test_recommendation_decision_cors_allows_if_match_header() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/api/v1/procurement-recommendations/rec-1/decisions",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,if-match",
        },
    )

    assert response.status_code == 200
    assert "if-match" in response.headers["access-control-allow-headers"].lower()


def test_generation_skips_material_without_inventory_snapshot() -> None:
    client = TestClient(create_app())
    login(client)
    material = client.post(
        "/api/v1/materials",
        json={"externalCode": "REC-NO-INVENTORY", "name": "No inventory", "baseUnit": "kg"},
    ).json()
    import_csv(
        client,
        "DEMAND",
        "materialExternalCode,requiredAt,requiredQty,unit,sourceType,sourceRecordRef\n"
        "REC-NO-INVENTORY,2026-08-20T08:00:00+08:00,10,kg,PLAN,no-inv-demand\n",
        "rec-no-inventory",
    )

    response = client.post(
        "/api/v1/procurement-recommendations/generate",
        json={"asOfDate": "2026-08-13", "horizonDays": 30},
    )

    assert response.status_code in {200, 201}
    assert all(
        item["materialId"] != material["id"]
        for item in response.json()["recommendations"]
    )
    assert {"materialId": material["id"], "reason": "INVENTORY_MISSING"} in response.json()["skipped"]


def test_late_open_supply_does_not_hide_an_earlier_shortage() -> None:
    client = TestClient(create_app())
    login(client)
    client.post(
        "/api/v1/materials",
        json={
            "externalCode": "REC-LATE-SUPPLY",
            "name": "Late supply",
            "baseUnit": "kg",
            "safetyStockQty": 0,
            "leadTimeDays": 2,
        },
    )
    import_csv(
        client,
        "INVENTORY",
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "REC-LATE-SUPPLY,WH-A,2026-08-13T08:00:00+08:00,100,100,kg,late-inv\n",
        "rec-late-inventory",
    )
    import_csv(
        client,
        "DEMAND",
        "materialExternalCode,requiredAt,requiredQty,unit,sourceType,sourceRecordRef\n"
        "REC-LATE-SUPPLY,2026-08-15T08:00:00+08:00,500,kg,PLAN,late-demand\n",
        "rec-late-demand",
    )
    import_csv(
        client,
        "OPEN_SUPPLY",
        "materialExternalCode,orderNo,orderLineNo,orderedQty,receivedQty,openQty,unit,expectedAt,status,sourceRecordRef\n"
        "REC-LATE-SUPPLY,PO-LATE,10,500,0,500,kg,2026-08-20T08:00:00+08:00,OPEN,late-supply\n",
        "rec-late-supply",
    )

    body = client.post(
        "/api/v1/procurement-recommendations/generate",
        json={"asOfDate": "2026-08-13", "horizonDays": 30},
    ).json()
    recommendation = next(
        item for item in body["recommendations"]
        if item["recommendedQty"] == 400 and item["calculation"]["openSupplyQty"] == 500
    )

    assert recommendation["latestOrderDate"] == "2026-08-13"
    assert recommendation["calculation"]["projectedBalanceQty"] == -400


def test_stale_inventory_blocks_formal_recommendation() -> None:
    client = TestClient(create_app())
    login(client)
    material = client.post(
        "/api/v1/materials",
        json={"externalCode": "REC-STALE", "name": "Stale inventory", "baseUnit": "kg"},
    ).json()
    import_csv(
        client,
        "INVENTORY",
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "REC-STALE,WH-A,2026-07-01T08:00:00+08:00,0,0,kg,stale-inv\n",
        "rec-stale-inventory",
    )
    import_csv(
        client,
        "DEMAND",
        "materialExternalCode,requiredAt,requiredQty,unit,sourceType,sourceRecordRef\n"
        "REC-STALE,2026-08-20T08:00:00+08:00,10,kg,PLAN,stale-demand\n",
        "rec-stale-demand",
    )

    body = client.post(
        "/api/v1/procurement-recommendations/generate",
        json={"asOfDate": "2026-08-13", "horizonDays": 30},
    ).json()

    assert {"materialId": material["id"], "reason": "INVENTORY_STALE"} in body["skipped"]


def test_latest_order_date_uses_first_safety_stock_breach() -> None:
    client = TestClient(create_app())
    login(client)
    material = client.post(
        "/api/v1/materials",
        json={
            "externalCode": "REC-FIRST-BREACH",
            "name": "First breach",
            "baseUnit": "kg",
            "safetyStockQty": 800,
            "leadTimeDays": 1,
        },
    ).json()
    import_csv(
        client,
        "INVENTORY",
        "materialExternalCode,locationCode,snapshotAt,onHandQty,availableQty,unit,sourceRecordRef\n"
        "REC-FIRST-BREACH,WH-A,2026-08-13T08:00:00+08:00,1000,1000,kg,breach-inv\n",
        "rec-breach-inventory",
    )
    import_csv(
        client,
        "DEMAND",
        "materialExternalCode,requiredAt,requiredQty,unit,sourceType,sourceRecordRef\n"
        "REC-FIRST-BREACH,2026-08-15T08:00:00+08:00,300,kg,PLAN,breach-demand-1\n"
        "REC-FIRST-BREACH,2026-08-25T08:00:00+08:00,700,kg,PLAN,breach-demand-2\n",
        "rec-breach-demand",
    )

    body = client.post(
        "/api/v1/procurement-recommendations/generate",
        json={"asOfDate": "2026-08-13", "horizonDays": 30},
    ).json()
    recommendation = next(
        item for item in body["recommendations"]
        if item["materialId"] == material["id"]
    )

    assert recommendation["recommendedQty"] == 800
    assert recommendation["latestOrderDate"] == "2026-08-14"
