import pytest

from tests.auth_test_helpers import auth_headers, register_and_login


@pytest.fixture
def admin(client):
    _, token = register_and_login(client, "tutor-admin@example.com", role="admin")
    return auth_headers(token)


@pytest.fixture
def student(client):
    student_id, token = register_and_login(client, "tutor-student@example.com")
    return student_id, auth_headers(token)


def seed_skill(client, headers):
    response=client.post('/api/v1/skills',json={'code':'alg_linear','name':'Linear Equations','domain':'algebra','description':'Solve linear equations','parent_code':None},headers=headers)
    assert response.status_code==201

def payload(student_id):
    return {'student_id':student_id,'skill_code':'alg_linear','problem_text':'If 2x + 5 = 17, what is x?','correct_answer':'6','student_answer':'7','student_work':'2x = 17 + 5, so x = 7'}

def test_create_and_continue_socratic_session(client, admin, student):
    sid,headers=student
    seed_skill(client,admin)
    created=client.post('/api/v1/tutor/sessions',json=payload(sid),headers=headers)
    assert created.status_code==201
    body=created.json(); assert body['status']=='active'; assert body['policy_version']=='socratic-v1.0'
    assert body['messages'][-1]['strategy']=='socratic'
    response=client.post(f"/api/v1/tutor/sessions/{body['id']}/messages",json={'content':"I'm stuck"},headers=headers)
    assert response.status_code==200
    updated=response.json(); assert updated['hints_used']==1; assert updated['messages'][-1]['strategy']=='hint'

def test_session_can_complete_and_reject_more_messages(client, admin, student):
    sid,headers=student
    seed_skill(client,admin)
    session_id=client.post('/api/v1/tutor/sessions',json=payload(sid),headers=headers).json()['id']
    completed=client.post(f'/api/v1/tutor/sessions/{session_id}/complete',json={'reflection':'I should subtract 5 first.'},headers=headers)
    assert completed.status_code==200; assert completed.json()['status']=='completed'
    closed=client.post(f'/api/v1/tutor/sessions/{session_id}/messages',json={'content':'another question'},headers=headers)
    assert closed.status_code==409; assert closed.json()['error']['code']=='TUTOR_SESSION_CLOSED'

def test_feedback_and_missing_skill(client, admin, student):
    sid,headers=student
    missing=client.post('/api/v1/tutor/sessions',json=payload(sid),headers=headers)
    assert missing.status_code==404; assert missing.json()['error']['code']=='TUTOR_SKILL_NOT_FOUND'
    seed_skill(client,admin)
    session_id=client.post('/api/v1/tutor/sessions',json=payload(sid),headers=headers).json()['id']
    feedback=client.post(f'/api/v1/tutor/sessions/{session_id}/feedback',json={'helpful':True,'rating':5,'comment':'Useful prompts'},headers=headers)
    assert feedback.status_code==201; assert feedback.json()['accepted'] is True

def test_another_student_cannot_read_or_send_messages(client, admin, student):
    sid,headers=student
    seed_skill(client,admin)
    session_id=client.post('/api/v1/tutor/sessions',json=payload(sid),headers=headers).json()['id']

    _, other_token = register_and_login(client, "tutor-other-student@example.com")
    other_headers = auth_headers(other_token)

    read = client.get(f'/api/v1/tutor/sessions/{session_id}',headers=other_headers)
    assert read.status_code==403
    assert read.json()['error']['code']=='ACCESS_DENIED'

    send = client.post(f'/api/v1/tutor/sessions/{session_id}/messages',json={'content':'hi'},headers=other_headers)
    assert send.status_code==403
    assert send.json()['error']['code']=='ACCESS_DENIED'

def test_teacher_can_read_but_not_send_messages(client, admin, student):
    sid,headers=student
    seed_skill(client,admin)
    session_id=client.post('/api/v1/tutor/sessions',json=payload(sid),headers=headers).json()['id']

    teacher_id, teacher_token = register_and_login(client, "tutor-teacher@example.com", role="teacher")
    grant = client.post('/api/v1/dashboard/access-grants', json={'viewer_id':teacher_id,'student_id':sid,'role':'teacher'}, headers=admin)
    assert grant.status_code==201
    teacher_headers = auth_headers(teacher_token)

    read = client.get(f'/api/v1/tutor/sessions/{session_id}',headers=teacher_headers)
    assert read.status_code==200

    send = client.post(f'/api/v1/tutor/sessions/{session_id}/messages',json={'content':'hi'},headers=teacher_headers)
    assert send.status_code==403
    assert send.json()['error']['code']=='ACCESS_DENIED'
