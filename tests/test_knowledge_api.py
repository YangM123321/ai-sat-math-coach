def create_skill(client, code, name, domain="algebra", parent_code=None):
    payload = {"code": code, "name": name, "domain": domain}
    if parent_code:
        payload["parent_code"] = parent_code
    return client.post("/api/v1/skills", json=payload)


def test_skill_catalog_and_relationship(client):
    assert create_skill(client, "linear_equations", "Linear equations").status_code == 201
    assert create_skill(client, "systems_of_equations", "Systems of equations").status_code == 201

    relationship = client.post(
        "/api/v1/skill-relationships",
        json={
            "source_skill_code": "linear_equations",
            "target_skill_code": "systems_of_equations",
            "relationship_type": "prerequisite_of",
            "weight": 0.9,
        },
    )
    assert relationship.status_code == 201
    assert relationship.json()["weight"] == 0.9


def test_evidence_updates_mastery_and_is_idempotent(client):
    create_skill(client, "linear_equations", "Linear equations")
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
    first = client.post("/api/v1/mastery/evidence", json=evidence)
    second = client.post("/api/v1/mastery/evidence", json=evidence)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["event_id"] == second.json()["event_id"]
    assert first.json()["new_score"] < 0.5

    profile = client.get("/api/v1/students/stu_001/knowledge-profile")
    assert profile.status_code == 200
    body = profile.json()
    assert len(body["skills"]) == 1
    assert body["skills"][0]["attempt_count"] == 1
    assert body["weakest_skills"][0]["skill_code"] == "linear_equations"


def test_correct_evidence_increases_mastery(client):
    create_skill(client, "percentages", "Percentages", "problem_solving_and_data_analysis")
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
    )
    assert response.status_code == 201
    assert response.json()["new_score"] > 0.5


def test_knowledge_graph_contains_nodes_edges_and_mastery(client):
    create_skill(client, "linear_equations", "Linear equations")
    create_skill(client, "systems_of_equations", "Systems of equations")
    client.post(
        "/api/v1/skill-relationships",
        json={
            "source_skill_code": "linear_equations",
            "target_skill_code": "systems_of_equations",
            "relationship_type": "prerequisite_of",
            "weight": 0.9,
        },
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
    )
    graph = client.get("/api/v1/students/stu_003/knowledge-graph")
    assert graph.status_code == 200
    assert len(graph.json()["nodes"]) == 2
    assert len(graph.json()["edges"]) == 1
    mastered_node = next(node for node in graph.json()["nodes"] if node["code"] == "linear_equations")
    assert mastered_node["mastery_score"] is not None


def test_unknown_skill_returns_404(client):
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
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SKILL_NOT_FOUND"
