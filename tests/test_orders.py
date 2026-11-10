"""Tests for manual orders and isolation between users.

Owns the checks on stored values and status, every 422 for bad values and paging, PATCH and DELETE,
and that another user's order is invisible on every endpoint.
"""

import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db import engine

Headers = dict[str, str]

VALID_ORDER = {
    "patient_first_name": "Ada",
    "patient_last_name": "Lovelace",
    "patient_dob": "1985-12-10",
    "provider_name": "Grace Hopper",
    "provider_npi": "1234567893",
}


def create(client: TestClient, headers: Headers, values: dict[str, Any] = VALID_ORDER) -> dict:
    """Create an order for these headers, assert a 201 and return its JSON."""
    response = client.post("/orders", json=values, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_order_with_all_fields_is_complete(client: TestClient, alice: Headers) -> None:
    """Expect status complete, source manual and the values as sent."""
    order = create(client, alice)

    assert order["status"] == "complete"
    assert order["source"] == "manual"
    assert {field: order[field] for field in VALID_ORDER} == VALID_ORDER


def test_order_with_missing_fields_needs_review(client: TestClient, alice: Headers) -> None:
    """Expect needs_review, with the status the client sent ignored."""
    order = create(client, alice, {"patient_first_name": "Ada", "status": "complete"})

    assert order["status"] == "needs_review"
    assert order["provider_npi"] is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_npi", "1234567890"),
        ("provider_npi", "12345abcde"),
        ("provider_npi", "12345678931"),
        ("patient_dob", "2999-01-01"),
        ("patient_dob", "1850-01-01"),
        ("patient_dob", "2023-02-30"),
        ("patient_dob", 0),
        ("patient_dob", 503020800),
        ("patient_dob", "1985-12-10T00:00:00"),
        ("patient_dob", "12/10/1985"),
        ("patient_first_name", "Ada2"),
        ("patient_last_name", "Unknown"),
        ("patient_first_name", "A" * 101),
        ("provider_name", "B" * 201),
        ("provider_name", "   "),
    ],
)
def test_invalid_value_is_rejected_and_nothing_saved(
    client: TestClient, alice: Headers, field: str, value: object
) -> None:
    """Expect a 422 naming the field for each bad value, and no order saved."""
    response = client.post("/orders", json={**VALID_ORDER, field: value}, headers=alice)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", field]
    assert client.get("/orders", headers=alice).json() == []


def test_rejection_gives_the_reason_without_the_value(client: TestClient, alice: Headers) -> None:
    """Expect the check-digit reason in the 422, but neither the NPI nor a long name."""
    marker = "MARKER" * 20
    bad_npi = client.post(
        "/orders", json={**VALID_ORDER, "provider_npi": "1234567890"}, headers=alice
    )
    long_name = client.post("/orders", json={"patient_first_name": marker}, headers=alice)

    assert "check digit" in bad_npi.json()["detail"][0]["msg"]
    assert "1234567890" not in bad_npi.text
    assert marker not in long_name.text


def test_list_returns_own_orders_newest_first(client: TestClient, alice: Headers) -> None:
    """Expect the newer order first."""
    first = create(client, alice)
    second = create(client, alice, {"patient_first_name": "Ada"})

    listed = client.get("/orders", headers=alice).json()

    assert [order["id"] for order in listed] == [second["id"], first["id"]]


def test_list_filters_by_status_and_pages(client: TestClient, alice: Headers) -> None:
    """Expect the status filter, limit and offset to pick the right orders."""
    complete = create(client, alice)
    create(client, alice, {"patient_first_name": "Ada"})
    create(client, alice, {"patient_first_name": "Ada"})

    filtered = client.get("/orders", params={"status": "complete"}, headers=alice).json()
    page = client.get("/orders", params={"limit": 2, "offset": 2}, headers=alice).json()

    assert [order["id"] for order in filtered] == [complete["id"]]
    assert [order["id"] for order in page] == [complete["id"]]


@pytest.mark.parametrize(
    "params",
    [{"limit": 101}, {"limit": 0}, {"offset": -1}, {"offset": 10**30}, {"status": "done"}],
)
def test_list_rejects_out_of_range_paging(
    client: TestClient, alice: Headers, params: dict[str, Any]
) -> None:
    """Expect a 422 for limits outside 1-100, bad offsets and unknown statuses."""
    assert client.get("/orders", params=params, headers=alice).status_code == 422


def test_patch_updates_sent_fields_and_recomputes_status(
    client: TestClient, alice: Headers
) -> None:
    """Expect only the fields sent to change, and the status to follow."""
    order = create(client, alice, {"patient_first_name": "Ada"})
    url = f"/orders/{order['id']}"

    filled = client.patch(
        url, json={k: v for k, v in VALID_ORDER.items() if k != "patient_first_name"}, headers=alice
    )
    cleared = client.patch(url, json={"provider_npi": None}, headers=alice)

    assert filled.json()["status"] == "complete"
    assert filled.json()["patient_first_name"] == "Ada"
    assert cleared.json()["status"] == "needs_review"
    assert cleared.json()["provider_npi"] is None
    assert cleared.json()["provider_name"] == "Grace Hopper"


def test_patch_with_invalid_value_changes_nothing(client: TestClient, alice: Headers) -> None:
    """Expect a 422 and the stored value unchanged."""
    order = create(client, alice)
    url = f"/orders/{order['id']}"

    response = client.patch(url, json={"provider_npi": "1234567890"}, headers=alice)

    assert response.status_code == 422
    assert client.get(url, headers=alice).json()["provider_npi"] == VALID_ORDER["provider_npi"]


def test_delete_removes_order(client: TestClient, alice: Headers) -> None:
    """Expect a 204 and then a 404."""
    url = f"/orders/{create(client, alice)['id']}"

    assert client.delete(url, headers=alice).status_code == 204
    assert client.get(url, headers=alice).status_code == 404


def test_other_users_order_is_not_found_on_read_update_delete(
    client: TestClient, alice: Headers, bob: Headers
) -> None:
    """Expect another user's order to answer 404 like an unknown id, and stay untouched."""
    url = f"/orders/{create(client, alice)['id']}"
    unknown_url = f"/orders/{uuid.uuid4()}"

    read = client.get(url, headers=bob)
    update = client.patch(url, json={"patient_first_name": "Mallory"}, headers=bob)
    delete = client.delete(url, headers=bob)

    for response in (read, update, delete):
        assert response.status_code == 404
        assert response.json() == client.get(unknown_url, headers=bob).json()
    still_there = client.get(url, headers=alice)
    assert still_there.status_code == 200
    assert still_there.json()["patient_first_name"] == "Ada"


def test_list_shows_only_own_orders(client: TestClient, alice: Headers, bob: Headers) -> None:
    """Expect each user's list to hold only their own orders."""
    alice_ids = {create(client, alice)["id"], create(client, alice)["id"]}
    bob_ids = {create(client, bob)["id"]}

    assert {order["id"] for order in client.get("/orders", headers=alice).json()} == alice_ids
    assert {order["id"] for order in client.get("/orders", headers=bob).json()} == bob_ids


def test_every_orders_endpoint_requires_a_valid_token(client: TestClient, alice: Headers) -> None:
    """Expect a 401 on every orders endpoint without a token or with a bad one."""
    url = f"/orders/{create(client, alice)['id']}"
    requests = [
        ("POST", "/orders"),
        ("GET", "/orders"),
        ("GET", url),
        ("PATCH", url),
        ("DELETE", url),
    ]

    for method, path in requests:
        for headers in ({}, {"Authorization": "Bearer not-a-token"}):
            response = client.request(method, path, json={}, headers=headers)
            assert response.status_code == 401, (method, path)


def test_malformed_order_id_is_422(client: TestClient, alice: Headers) -> None:
    """Expect a 422 for an order id that is not a UUID."""
    assert client.get("/orders/not-a-uuid", headers=alice).status_code == 422


def test_failed_database_write_keeps_values_out_of_the_error(
    client: TestClient, alice: Headers
) -> None:
    """Expect a failed INSERT's error, which the server logs, to hold no field value."""
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE orders"))

    with pytest.raises(OperationalError) as failed:
        client.post("/orders", json={**VALID_ORDER, "patient_first_name": "Zebedee"}, headers=alice)

    message = str(failed.value)
    assert "INSERT INTO orders" in message
    for value in ["Zebedee", *VALID_ORDER.values()]:
        assert value not in message
