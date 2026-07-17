from datetime import datetime, timezone

def seed_skill(client,code='alg_linear'):
    r=client.post('/api/v1/skills',json={'code':code,'name':'Linear Equations','domain':'algebra','description':'Solve linear equations','parent_code':None})
    assert r.status_code==201

def seed_mastery(client):
    seed_skill(client)
    r=client.post('/api/v1/mastery/evidence',json={'student_id':'stu_dash','skill_code':'alg_linear','evidence_type':'diagnostic_attempt','source_id':'diag_dash_1','is_correct':False,'error_category':'procedural_error','difficulty':'medium','diagnostic_confidence':0.9,'occurred_at':datetime.now(timezone.utc).isoformat()})
    assert r.status_code==201

def grant(client,viewer='teacher_1',role='teacher'):
    r=client.post('/api/v1/dashboard/access-grants',json={'viewer_id':viewer,'student_id':'stu_dash','role':role,'created_by':'admin_1'})
    assert r.status_code==201

def test_teacher_dashboard_aggregates_mastery_and_alerts(client):
    seed_mastery(client); grant(client)
    r=client.get('/api/v1/dashboard/students/stu_dash?viewer_id=teacher_1&role=teacher')
    assert r.status_code==200
    body=r.json(); assert body['student_id']=='stu_dash'; assert body['metrics']['overall_mastery']<0.5
    assert body['weak_skills'][0]['skill_code']=='alg_linear'; assert body['alerts']

def test_unauthorized_viewer_is_rejected(client):
    seed_mastery(client)
    r=client.get('/api/v1/dashboard/students/stu_dash?viewer_id=unknown&role=parent')
    assert r.status_code==403; assert r.json()['error']['code']=='DASHBOARD_ACCESS_DENIED'

def test_overview_snapshot_and_trends(client):
    seed_mastery(client); grant(client)
    overview=client.get('/api/v1/dashboard/viewers/teacher_1/overview?role=teacher')
    assert overview.status_code==200; assert overview.json()['total']==1
    snap=client.post('/api/v1/dashboard/students/stu_dash/snapshots?viewer_id=teacher_1&role=teacher')
    assert snap.status_code==201
    trends=client.get('/api/v1/dashboard/students/stu_dash/trends?viewer_id=teacher_1&role=teacher')
    assert trends.status_code==200; assert len(trends.json()['snapshots'])==1

def test_admin_can_access_without_grant_but_empty_student_is_404(client):
    r=client.get('/api/v1/dashboard/students/missing?viewer_id=admin&role=admin')
    assert r.status_code==404; assert r.json()['error']['code']=='DASHBOARD_STUDENT_DATA_NOT_FOUND'
