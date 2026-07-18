import pytest

from tests.auth_test_helpers import auth_headers, register_and_login


@pytest.fixture
def admin(client):
    _, token = register_and_login(client, "knowledge-admin@example.com", role="admin")
    return auth_headers(token)


def create_skill(client, headers, code, name, domain="algebra", parent_code=None):
    payload = {"code": code, "name": name, "domain": domain}
    if parent_code:
        payload["parent_code"] = parent_code
    return client.post("/api/v1/skills", json=payload, headers=headers)


def test_skill_catalog_and_relationship(client, admin):
    assert create_skill(client, admin, "linear_equations", "Linear equations").status_code == 201
    assert create_skill(client, admin, "systems_of_equations", "Systems of equations").status_code == 201

    relationship = client.post(
        "/api/v1/skill-relationships",
        json={
            "source_skill_code": "linear_equations",
            "target_skill_code": "systems_of_equations",
            "relationship_type": "prerequisite_of",
            "weight": 0.9,
        },
        headers=admin,
    )
    assert relationship.status_code == 201
    assert relationship.json()["weight"] == 0.9


def test_non_admin_cannot_create_skills(client):
    _, token = register_and_login(client, "knowledge-student@example.com")
    r = client.post("/api/v1/skills", json={"code": "x", "name": "X", "domain": "algebra"}, headers=auth_headers(token))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ACCESS_DENIED"


def test_evidence_updates_mastery_and_is_idempotent(client, admin):
    create_skill(client, admin, "linear_equations", "Linear equations")
    evidence = {
        "student_id": "stu_001",
        "skill_code": "linear_equations",
        "evidence_type": "diagnostic_attempt",
        "source_id": "diag_001",
        "is_correct": False,
        "diagnostic_confidence": 0.95,
        "difficulty": "medium",
        "error_category": "procedural_error",
    }
    first = client.post("/api/v1/mastery/evidence", json=evidence, headers=admin)
    second = client.post("/api/v1/mastery/evidence", json=evidence, headers=admin)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["event_id"] == second.json()["event_id"]
    assert first.json()["new_score"] < 0.5

    profile = client.get("/api/v1/students/stu_001/knowledge-profile", headers=admin)
    assert profile.status_code == 200
    body = profile.json()
    assert len(body["skills"]) == 1
    assert body["skills"][0]["attempt_count"] == 1
    assert body["weakest_skills"][0]["skill_code"] == "linear_equations"


def test_correct_evidence_increases_mastery(client, admin):
    create_skill(client, admin, "percentages", "Percentages", "problem_solving_and_data_analysis")
    response = client.post(
        "/api/v1/mastery/evidence",
        json={
            "student_id": "stu_002",
            "skill_code": "percentages",
            "evidence_type": "practice_attempt",
            "source_id": "practice_001",
            "is_correct": True,
            "diagnostic_confidence": 1.0,
            "difficulty": "hard",
        },
        headers=admin,
    )
    assert response.status_code == 201
    assert response.json()["new_score"] > 0.5


def test_knowledge_graph_contains_nodes_edges_and_mastery(client, admin):
    create_skill(client, admin, "linear_equations", "Linear equations")
    create_skill(client, admin, "systems_of_equations", "Systems of equations")
    client.post(
        "/api/v1/skill-relationships",
        json={
            "source_skill_code": "linear_equations",
            "target_skill_code": "systems_of_equations",
            "relationship_type": "prerequisite_of",
            "weight": 0.9,
        },
        headers=admin,
    )
    client.post(
        "/api/v1/mastery/evidence",
        json={
            "student_id": "stu_003",
            "skill_code": "linear_equations",
            "evidence_type": "diagnostic_attempt",
            "source_id": "diag_003",
            "is_correct": True,
            "difficulty": "medium",
        },
        headers=admin,
    )
    graph = client.get("/api/v1/students/stu_003/knowledge-graph", headers=admin)
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) == 2
    assert len(graph.json()["edges"]) == 1
    mastered_node = next(node for node in graph.json()["nodes"] if node["code"] == "linear_equations")
    assert mastered_node["mastery_score"] is not None


def test_unknown_skill_returns_404(client, admin):
    response = client.post(
        "/api/v1/mastery/evidence",
        json={
            "student_id": "stu_001",
            "skill_code": "missing_skill",
            "evidence_type": "diagnostic_attempt",
            "source_id": "diag_404",
            "is_correct": False,
            "difficulty": "medium",
        },
        headers=admin,
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SKILL_NOT_FOUND"


def test_student_cannot_submit_mastery_evidence_for_another_student(client, admin):
    student_id, token = register_and_login(client, "knowledge-victim@example.com")
    create_skill(client, admin, "linear_equations", "Linear equations")
    response = client.post(
        "/api/v1/mastery/evidence",
        json={
            "student_id": "someone-else",
            "skill_code": "linear_equations",
            "evidence_type": "diagnostic_attempt",
            "source_id": "diag_999",
            "is_correct": True,
            "difficulty": "medium",
        },
        headers=auth_headers(token),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "ACCESS_DENIED"


def test_student_cannot_read_another_students_knowledge_profile_or_graph(client, admin):
    victim_id, _ = register_and_login(client, "knowledge-victim-2@example.com")
    create_skill(client, admin, "linear_equations", "Linear equations")
    client.post(
        "/api/v1/mastery/evidence",
        json={
            "student_id": victim_id,
            "skill_code": "linear_equations",
            "evidence_type": "diagnostic_attempt",
            "source_id": "diag_998",
            "is_correct": True,
            "difficulty": "medium",
        },
        headers=admin,
    )
    _, attacker_token = register_and_login(client, "knowledge-attacker@example.com")
    attacker_headers = auth_headers(attacker_token)

    profile = client.get(f"/api/v1/students/{victim_id}/knowledge-profile", headers=attacker_headers)
    assert profile.status_code == 403
    assert profile.json()["error"]["code"] == "ACCESS_DENIED"

    graph = client.get(f"/api/v1/students/{victim_id}/knowledge-graph", headers=attacker_headers)
    assert graph.status_code == 403
    assert graph.json()["error"]["code"] == "ACCESS_DENIED"
