import pytest

from tests.auth_test_helpers import auth_headers, register_and_login


@pytest.fixture
def admin(client):
    _, token = register_and_login(client, "learning-admin@example.com", role="admin")
    return auth_headers(token)


def skill(client, headers, code, name):
    return client.post('/api/v1/skills', json={'code':code,'name':name,'domain':'algebra'}, headers=headers)

def evidence(client, headers, student, code, source, correct):
    return client.post('/api/v1/mastery/evidence', json={
        'student_id':student,'skill_code':code,'evidence_type':'practice_attempt','source_id':source,
        'is_correct':correct,'diagnostic_confidence':1.0,'difficulty':'medium'}, headers=headers)

def test_generate_and_retrieve_plan(client, admin):
    skill(client,admin,'linear_equations','Linear equations')
    skill(client,admin,'systems_of_equations','Systems of equations')
    evidence(client,admin,'stu_l3','linear_equations','p1',False)
    response=client.post('/api/v1/learning-plans', json={'student_id':'stu_l3','daily_minutes':30,'duration_days':7}, headers=admin)
    assert response.status_code==201
    body=response.json()
    assert body['version']==1
    assert body['status']=='active'
    assert len(body['activities'])==7
    assert 'linear_equations' in body['focus_skills']
    assert any(a['skill_code']=='linear_equations' for a in body['activities'])
    fetched=client.get(f"/api/v1/learning-plans/{body['id']}", headers=admin)
    assert fetched.status_code==200
    assert fetched.json()['id']==body['id']

def test_new_plan_supersedes_old_plan(client, admin):
    skill(client,admin,'percentages','Percentages')
    first=client.post('/api/v1/learning-plans', json={'student_id':'stu_v','duration_days':2}, headers=admin).json()
    second=client.post('/api/v1/learning-plans', json={'student_id':'stu_v','duration_days':2}, headers=admin).json()
    assert second['version']==2
    assert client.get(f"/api/v1/learning-plans/{first['id']}", headers=admin).json()['status']=='superseded'
    assert client.get('/api/v1/students/stu_v/active-learning-plan', headers=admin).json()['id']==second['id']

def test_update_activity_progress(client, admin):
    skill(client,admin,'quadratic_equations','Quadratic equations')
    plan=client.post('/api/v1/learning-plans', json={'student_id':'stu_progress','duration_days':1}, headers=admin).json()
    activity_id=plan['activities'][0]['id']
    response=client.patch(f'/api/v1/learning-activities/{activity_id}', json={
        'status':'completed','completed_questions':6,'correct_questions':5}, headers=admin)
    assert response.status_code==200
    assert response.json()['status']=='completed'
    assert response.json()['correct_questions']==5

def test_empty_catalog_returns_conflict(client, admin):
    response=client.post('/api/v1/learning-plans', json={'student_id':'stu_empty'}, headers=admin)
    assert response.status_code==409
    assert response.json()['detail']['code']=='SKILL_CATALOG_EMPTY'

def test_invalid_activity_counts_return_422(client, admin):
    response=client.patch('/api/v1/learning-activities/missing', json={
        'status':'completed','completed_questions':3,'correct_questions':4}, headers=admin)
    assert response.status_code==422

def test_student_cannot_create_a_plan_for_another_student(client, admin):
    skill(client,admin,'linear_equations','Linear equations')
    _, token = register_and_login(client, "learning-student@example.com")
    response = client.post('/api/v1/learning-plans', json={'student_id':'someone-else','duration_days':2}, headers=auth_headers(token))
    assert response.status_code==403
    assert response.json()['error']['code']=='ACCESS_DENIED'

def test_student_cannot_read_another_students_plan(client, admin):
    skill(client,admin,'linear_equations','Linear equations')
    victim_id, _ = register_and_login(client, "learning-victim@example.com")
    plan = client.post('/api/v1/learning-plans', json={'student_id':victim_id,'duration_days':1}, headers=admin).json()

    _, attacker_token = register_and_login(client, "learning-attacker@example.com")
    attacker_headers = auth_headers(attacker_token)

    by_id = client.get(f"/api/v1/learning-plans/{plan['id']}", headers=attacker_headers)
    assert by_id.status_code==403
    assert by_id.json()['error']['code']=='ACCESS_DENIED'

    active = client.get(f"/api/v1/students/{victim_id}/active-learning-plan", headers=attacker_headers)
    assert active.status_code==403
    assert active.json()['error']['code']=='ACCESS_DENIED'

def test_teacher_cannot_update_an_assigned_students_activity(client, admin):
    skill(client,admin,'linear_equations','Linear equations')
    student_id, student_token = register_and_login(client, "learning-assigned-student@example.com")
    teacher_id, teacher_token = register_and_login(client, "learning-teacher@example.com", role="teacher")
    grant = client.post('/api/v1/dashboard/access-grants', json={'viewer_id':teacher_id,'student_id':student_id,'role':'teacher'}, headers=admin)
    assert grant.status_code==201

    plan=client.post('/api/v1/learning-plans', json={'student_id':student_id,'duration_days':1}, headers=auth_headers(student_token)).json()
    activity_id=plan['activities'][0]['id']

    # A teacher with an active grant may read but not write (this PR's
    # simplified policy: teachers are read-only, never on-behalf-of-student
    # writers), so the update itself must still be denied.
    response=client.patch(f'/api/v1/learning-activities/{activity_id}', json={
        'status':'completed','completed_questions':1,'correct_questions':1}, headers=auth_headers(teacher_token))
    assert response.status_code==403
    assert response.json()['error']['code']=='ACCESS_DENIED'

    # But the same teacher can read the student's active plan.
    read = client.get(f'/api/v1/students/{student_id}/active-learning-plan', headers=auth_headers(teacher_token))
    assert read.status_code==200
