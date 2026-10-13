"""Тесты операций программного интерфейса: код ответа, состав полей, 401, 404, 409, 422."""
from app import config

LOAN_CARD_FIELDS = {"id", "status", "issued_at", "due_date", "returned_at", "fine",
                    "reader", "copy", "book"}


# --- Вход ---

def test_login_returns_token(client):
    response = client.post(
        "/api/login", json={"username": config.APP_USER, "password": config.APP_PASSWORD}
    )
    assert response.status_code == 200
    assert "token" in response.json()


def test_login_with_wrong_password_is_rejected(client):
    response = client.post("/api/login", json={"username": config.APP_USER, "password": "wrong"})
    assert response.status_code == 401


def test_login_without_fields_is_422(client):
    assert client.post("/api/login", json={}).status_code == 422


def test_forged_token_is_rejected(client):
    response = client.get("/api/summary", headers={"Authorization": "Bearer demo:9999999999:fake"})
    assert response.status_code == 401


# --- Без авторизации все операции закрыты ---

def test_operations_require_authorization(client):
    assert client.get("/api/loans").status_code == 401
    assert client.get("/api/loans/1").status_code == 401
    assert client.post("/api/loans", json={"reader_id": 1, "copy_id": 3}).status_code == 401
    assert client.post("/api/loans/1/return").status_code == 401
    assert client.get("/api/summary").status_code == 401


# --- GET /api/loans ---

def test_list_has_expected_shape(client, auth):
    response = client.get("/api/loans", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert len(body["items"]) == 5
    assert set(body["items"][0]) == {
        "id", "status", "reader_name", "book_title", "inventory_number",
        "issued_at", "due_date", "returned_at", "fine",
    }


def test_list_is_paginated(client, auth):
    first = client.get("/api/loans?page=1&size=2", headers=auth).json()
    second = client.get("/api/loans?page=2&size=2", headers=auth).json()
    assert len(first["items"]) == 2
    assert len(second["items"]) == 2
    assert first["total"] == 5
    ids = {item["id"] for item in first["items"]} | {item["id"] for item in second["items"]}
    assert len(ids) == 4   # страницы не пересекаются


def test_list_filter_overdue(client, auth):
    body = client.get("/api/loans?status=overdue", headers=auth).json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == 1
    assert body["items"][0]["status"] == "overdue"


def test_list_filter_returned(client, auth):
    body = client.get("/api/loans?status=returned", headers=auth).json()
    assert body["total"] == 3
    assert all(item["status"] == "returned" for item in body["items"])


def test_list_filter_by_reader(client, auth):
    body = client.get("/api/loans?reader_id=3", headers=auth).json()
    assert body["total"] == 3


def test_list_rejects_bad_parameters(client, auth):
    assert client.get("/api/loans?page=0", headers=auth).status_code == 422
    assert client.get("/api/loans?size=1000", headers=auth).status_code == 422
    assert client.get("/api/loans?status=unknown", headers=auth).status_code == 422
    assert client.get("/api/loans?page=abc", headers=auth).status_code == 422


# --- GET /api/loans/{id} ---

def test_card_has_related_entities(client, auth):
    response = client.get("/api/loans/1", headers=auth)
    assert response.status_code == 200
    card = response.json()
    assert set(card) == LOAN_CARD_FIELDS
    assert card["status"] == "overdue"
    assert card["reader"]["full_name"] == "Петров Пётр"
    assert card["copy"]["inventory_number"] == "INV-2"
    assert card["book"]["title"] == "Книга А"


def test_card_of_overdue_loan_shows_accrued_fine(client, auth):
    assert client.get("/api/loans/1", headers=auth).json()["fine"] == 170


def test_card_of_loan_in_time_has_no_fine(client, auth):
    assert client.get("/api/loans/4", headers=auth).json()["fine"] == 0


def test_list_shows_accrued_fine_for_overdue_loan(client, auth):
    item = client.get("/api/loans?status=overdue", headers=auth).json()["items"][0]
    assert item["fine"] == 170


def test_card_of_unknown_loan_is_404(client, auth):
    assert client.get("/api/loans/999", headers=auth).status_code == 404


def test_card_with_bad_id_is_422(client, auth):
    assert client.get("/api/loans/abc", headers=auth).status_code == 422


# --- POST /api/loans (выдача) ---

def test_issue_free_copy_creates_loan(client, auth):
    response = client.post("/api/loans", json={"reader_id": 3, "copy_id": 3}, headers=auth)
    assert response.status_code == 201
    card = response.json()
    assert set(card) == LOAN_CARD_FIELDS
    assert card["status"] == "on_hands"
    assert card["issued_at"] == "2026-09-01"
    assert card["due_date"] == "2026-09-15"      
    assert card["returned_at"] is None


def test_issue_copy_that_is_on_hands_is_409(client, auth):
    response = client.post("/api/loans", json={"reader_id": 3, "copy_id": 1}, headers=auth)
    assert response.status_code == 409


def test_issue_to_reader_with_overdue_is_409(client, auth):
    response = client.post("/api/loans", json={"reader_id": 2, "copy_id": 3}, headers=auth)
    assert response.status_code == 409


def test_issue_to_unknown_reader_is_404(client, auth):
    response = client.post("/api/loans", json={"reader_id": 999, "copy_id": 3}, headers=auth)
    assert response.status_code == 404


def test_issue_unknown_copy_is_404(client, auth):
    response = client.post("/api/loans", json={"reader_id": 3, "copy_id": 999}, headers=auth)
    assert response.status_code == 404


def test_issue_with_bad_body_is_422(client, auth):
    assert client.post("/api/loans", json={"reader_id": 3}, headers=auth).status_code == 422
    assert client.post("/api/loans", json={"reader_id": "x", "copy_id": 3}, headers=auth).status_code == 422
    assert client.post("/api/loans", json={"reader_id": 0, "copy_id": 3}, headers=auth).status_code == 422


def test_second_issue_of_same_copy_is_rejected(client, auth):
    assert client.post("/api/loans", json={"reader_id": 3, "copy_id": 3}, headers=auth).status_code == 201
    assert client.post("/api/loans", json={"reader_id": 1, "copy_id": 3}, headers=auth).status_code == 409


# --- POST /api/loans/{id}/return (возврат) ---

def test_return_in_time_has_no_fine(client, auth):
    response = client.post("/api/loans/4/return", headers=auth)  
    assert response.status_code == 200
    card = response.json()
    assert card["status"] == "returned"
    assert card["returned_at"] == "2026-09-01"
    assert card["fine"] == 0


def test_return_overdue_charges_fine(client, auth):
    response = client.post("/api/loans/1/return", headers=auth)   
    assert response.status_code == 200
    assert response.json()["fine"] == 170


def test_return_frees_the_copy(client, auth):
    assert client.post("/api/loans/1/return", headers=auth).status_code == 200
    response = client.post("/api/loans", json={"reader_id": 2, "copy_id": 2}, headers=auth)
    assert response.status_code == 201  


def test_return_twice_is_409(client, auth):
    assert client.post("/api/loans/2/return", headers=auth).status_code == 409


def test_return_unknown_loan_is_404(client, auth):
    assert client.post("/api/loans/999/return", headers=auth).status_code == 404


# --- GET /api/summary ---

def test_summary_counts_all_data(client, auth):
    response = client.get("/api/summary", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"on_hands", "overdue", "top_books"}
    assert body["on_hands"] == 2      
    assert body["overdue"] == 1      
    top = body["top_books"]
    assert set(top[0]) == {"book_id", "title", "author", "loans_count"}
    assert top[0]["title"] == "Книга А"  
    assert top[0]["loans_count"] == 3
    assert top[1]["loans_count"] == 2


# --- Служебные заголовки со статистикой запросов к БД ---

def test_response_reports_db_query_count(client, auth):
    response = client.get("/api/summary", headers=auth)
    assert response.headers["X-DB-Queries"] == "2"
    assert float(response.headers["X-DB-Time-Ms"]) >= 0
