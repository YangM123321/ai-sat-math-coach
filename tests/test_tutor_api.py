def seed_skill(client):
    response=client.post('/api/v1/skills',json={'code':'alg_linear','name':'Linear Equations','domain':'algebra','description':'Solve linear equations','parent_code':None})
    assert response.status_code==201

def payload():
    return {'student_id':'stu_tutor','skill_code':'alg_linear','problem_text':'If 2x + 5 = 17, what is x?','correct_answer':'6','student_answer':'7','student_work':'2x = 17 + 5, so x = 7'}

def test_create_and_continue_socratic_session(client):
    seed_skill(client)
    created=client.post('/api/v1/tutor/sessions',json=payload())
    assert created.status_code==201
    body=created.json(); assert body['status']=='active'; assert body['policy_version']=='socratic-v1.0'
    assert body['messages'][-1]['strategy']=='socratic'
    response=client.post(f"/api/v1/tutor/sessions/{body['id']}/messages",json={'content':"I'm stuck"})
    assert response.status_code==200
    updated=response.json(); assert updated['hints_used']==1; assert updated['messages'][-1]['strategy']=='hint'

def test_session_can_complete_and_reject_more_messages(client):
    seed_skill(client)
    sid=client.post('/api/v1/tutor/sessions',json=payload()).json()['id']
    completed=client.post(f'/api/v1/tutor/sessions/{sid}/complete',json={'reflection':'I should subtract 5 first.'})
    assert completed.status_code==200; assert completed.json()['status']=='completed'
    closed=client.post(f'/api/v1/tutor/sessions/{sid}/messages',json={'content':'another question'})
    assert closed.status_code==409; assert closed.json()['error']['code']=='TUTOR_SESSION_CLOSED'

def test_feedback_and_missing_skill(client):
    missing=client.post('/api/v1/tutor/sessions',json=payload())
    assert missing.status_code==404; assert missing.json()['error']['code']=='TUTOR_SKILL_NOT_FOUND'
    seed_skill(client)
    sid=client.post('/api/v1/tutor/sessions',json=payload()).json()['id']
    feedback=client.post(f'/api/v1/tutor/sessions/{sid}/feedback',json={'helpful':True,'rating':5,'comment':'Useful prompts'})
    assert feedback.status_code==201; assert feedback.json()['accepted'] is True
