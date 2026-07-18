from datetime import datetime, timezone

import pytest

from tests.auth_test_helpers import auth_headers, register_and_login


@pytest.fixture
def admin(client):
    _, token = register_and_login(client, "dashboard-admin@example.com", role="admin")
    return auth_headers(token)


def seed_skill(client,headers,code='alg_linear'):
    r=client.post('/api/v1/skills',json={'code':code,'name':'Linear Equations','domain':'algebra','description':'Solve linear equations','parent_code':None},headers=headers)
    assert r.status_code==201

def seed_mastery(client,headers,student_id):
    seed_skill(client,headers)
    r=client.post('/api/v1/mastery/evidence',json={'student_id':student_id,'skill_code':'alg_linear','evidence_type':'diagnostic_attempt','source_id':'diag_dash_1','is_correct':False,'error_category':'procedural_error','difficulty':'medium','diagnostic_confidence':0.9,'occurred_at':datetime.now(timezone.utc).isoformat()},headers=headers)
    assert r.status_code==201

def grant(client,headers,viewer_id,student_id,role='teacher'):
    r=client.post('/api/v1/dashboard/access-grants',json={'viewer_id':viewer_id,'student_id':student_id,'role':role},headers=headers)
    assert r.status_code==201

def test_teacher_dashboard_aggregates_mastery_and_alerts(client, admin):
    student_id,_=register_and_login(client,"dashboard-student-1@example.com")
    teacher_id,teacher_token=register_and_login(client,"dashboard-teacher-1@example.com",role="teacher")
    seed_mastery(client,admin,student_id); grant(client,admin,teacher_id,student_id)
    r=client.get(f'/api/v1/dashboard/students/{student_id}',headers=auth_headers(teacher_token))
    assert r.status_code==200
    body=r.json(); assert body['student_id']==student_id; assert body['metrics']['overall_mastery']<0.5
    assert body['weak_skills'][0]['skill_code']=='alg_linear'; assert body['alerts']

def test_unauthorized_viewer_is_rejected(client, admin):
    student_id,_=register_and_login(client,"dashboard-student-2@example.com")
    seed_mastery(client,admin,student_id)
    _,other_token=register_and_login(client,"dashboard-unrelated-teacher@example.com",role="teacher")
    r=client.get(f'/api/v1/dashboard/students/{student_id}',headers=auth_headers(other_token))
    assert r.status_code==403; assert r.json()['error']['code']=='ACCESS_DENIED'

def test_grant_access_requires_admin(client):
    student_id,_=register_and_login(client,"dashboard-student-3@example.com")
    teacher_id,teacher_token=register_and_login(client,"dashboard-teacher-3@example.com",role="teacher")
    r=client.post('/api/v1/dashboard/access-grants',json={'viewer_id':teacher_id,'student_id':student_id,'role':'teacher'},headers=auth_headers(teacher_token))
    assert r.status_code==403; assert r.json()['error']['code']=='ACCESS_DENIED'

def test_grant_access_rejects_unknown_users(client, admin):
    r=client.post('/api/v1/dashboard/access-grants',json={'viewer_id':'nonexistent-viewer','student_id':'nonexistent-student','role':'teacher'},headers=admin)
    assert r.status_code==404; assert r.json()['error']['code']=='USER_NOT_FOUND'

def test_overview_snapshot_and_trends(client, admin):
    student_id,_=register_and_login(client,"dashboard-student-4@example.com")
    teacher_id,teacher_token=register_and_login(client,"dashboard-teacher-4@example.com",role="teacher")
    seed_mastery(client,admin,student_id); grant(client,admin,teacher_id,student_id)
    teacher_headers=auth_headers(teacher_token)
    overview=client.get(f'/api/v1/dashboard/viewers/{teacher_id}/overview?role=teacher',headers=teacher_headers)
    assert overview.status_code==200; assert overview.json()['total']==1
    # Snapshot creation is a write on student-owned data -- this PR's
    # simplified policy keeps teachers read-only, so only self/admin may
    # trigger one.
    snap=client.post(f'/api/v1/dashboard/students/{student_id}/snapshots',headers=admin)
    assert snap.status_code==201
    trends=client.get(f'/api/v1/dashboard/students/{student_id}/trends',headers=teacher_headers)
    assert trends.status_code==200; assert len(trends.json()['snapshots'])==1

def test_teacher_cannot_create_snapshot_for_assigned_student(client, admin):
    student_id,_=register_and_login(client,"dashboard-student-5@example.com")
    teacher_id,teacher_token=register_and_login(client,"dashboard-teacher-5@example.com",role="teacher")
    seed_mastery(client,admin,student_id); grant(client,admin,teacher_id,student_id)
    snap=client.post(f'/api/v1/dashboard/students/{student_id}/snapshots',headers=auth_headers(teacher_token))
    assert snap.status_code==403; assert snap.json()['error']['code']=='ACCESS_DENIED'

def test_viewer_overview_rejects_mismatched_viewer_id(client, admin):
    teacher_id,teacher_token=register_and_login(client,"dashboard-teacher-6@example.com",role="teacher")
    _,other_teacher_token=register_and_login(client,"dashboard-teacher-7@example.com",role="teacher")
    r=client.get(f'/api/v1/dashboard/viewers/{teacher_id}/overview',headers=auth_headers(other_teacher_token))
    assert r.status_code==403; assert r.json()['error']['code']=='ACCESS_DENIED'

def test_admin_can_access_without_grant_but_empty_student_is_404(client, admin):
    r=client.get('/api/v1/dashboard/students/missing',headers=admin)
    assert r.status_code==404; assert r.json()['error']['code']=='DASHBOARD_STUDENT_DATA_NOT_FOUND'

def test_student_can_view_own_dashboard(client, admin):
    student_id,student_token=register_and_login(client,"dashboard-student-8@example.com")
    seed_mastery(client,admin,student_id)
    r=client.get(f'/api/v1/dashboard/students/{student_id}',headers=auth_headers(student_token))
    assert r.status_code==200
    assert r.json()['student_id']==student_id
