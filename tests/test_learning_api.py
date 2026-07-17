def skill(client, code, name):
    return client.post('/api/v1/skills', json={'code':code,'name':name,'domain':'algebra'})

def evidence(client, student, code, source, correct):
    return client.post('/api/v1/mastery/evidence', json={
        'student_id':student,'skill_code':code,'evidence_type':'practice_attempt','source_id':source,
        'is_correct':correct,'diagnostic_confidence':1.0,'difficulty':'medium'})

def test_generate_and_retrieve_plan(client):
    skill(client,'linear_equations','Linear equations')
    skill(client,'systems_of_equations','Systems of equations')
    evidence(client,'stu_l3','linear_equations','p1',False)
    response=client.post('/api/v1/learning-plans', json={'student_id':'stu_l3','daily_minutes':30,'duration_days':7})
    assert response.status_code==201
    body=response.json()
    assert body['version']==1
    assert body['status']=='active'
    assert len(body['activities'])==7
    assert 'linear_equations' in body['focus_skills']
    assert any(a['skill_code']=='linear_equations' for a in body['activities'])
    fetched=client.get(f"/api/v1/learning-plans/{body['id']}")
    assert fetched.status_code==200
    assert fetched.json()['id']==body['id']

def test_new_plan_supersedes_old_plan(client):
    skill(client,'percentages','Percentages')
    first=client.post('/api/v1/learning-plans', json={'student_id':'stu_v','duration_days':2}).json()
    second=client.post('/api/v1/learning-plans', json={'student_id':'stu_v','duration_days':2}).json()
    assert second['version']==2
    assert client.get(f"/api/v1/learning-plans/{first['id']}").json()['status']=='superseded'
    assert client.get('/api/v1/students/stu_v/active-learning-plan').json()['id']==second['id']

def test_update_activity_progress(client):
    skill(client,'quadratic_equations','Quadratic equations')
    plan=client.post('/api/v1/learning-plans', json={'student_id':'stu_progress','duration_days':1}).json()
    activity_id=plan['activities'][0]['id']
    response=client.patch(f'/api/v1/learning-activities/{activity_id}', json={
        'status':'completed','completed_questions':6,'correct_questions':5})
    assert response.status_code==200
    assert response.json()['status']=='completed'
    assert response.json()['correct_questions']==5

def test_empty_catalog_returns_conflict(client):
    response=client.post('/api/v1/learning-plans', json={'student_id':'stu_empty'})
    assert response.status_code==409
    assert response.json()['detail']['code']=='SKILL_CATALOG_EMPTY'

def test_invalid_activity_counts_return_422(client):
    response=client.patch('/api/v1/learning-activities/missing', json={
        'status':'completed','completed_questions':3,'correct_questions':4})
    assert response.status_code==422
