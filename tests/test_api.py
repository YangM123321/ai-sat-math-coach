import pytest

from tests.auth_test_helpers import auth_headers, register_and_login


@pytest.fixture
def student(client):
    student_id, token = register_and_login(client, "diag-student@example.com")
    return student_id, auth_headers(token)


def payload(student_id, work='2x = 17 + 5, so 2x = 22 and x = 7'):
    return {'student_id':student_id,'question':{'question_text':'If 2x + 5 = 17, what is x?','correct_answer':'6','official_explanation':'Subtract 5, then divide by 2.','domain':'algebra','skill':'linear_equations','subskill':'inverse_operations','difficulty':'easy'},'student_answer':'7','work_text':work,'student_confidence':4,'time_spent_seconds':95}

def test_create(client,student):
    sid,headers=student
    r=client.post('/api/v1/diagnostics',json=payload(sid),headers=headers); assert r.status_code==201; b=r.json(); assert b['error_category']=='procedural_error'; assert b['error_subcategory']=='inverse_operation_error'; assert not b['requires_human_review']

def test_correct(client,student):
    sid,headers=student
    p=payload(sid,'Subtract 5, then divide by 2.'); p['student_answer']='6'; b=client.post('/api/v1/diagnostics',json=p,headers=headers).json(); assert b['correct'] and b['error_category']=='none'

def test_missing_work_review(client,student):
    sid,headers=student
    b=client.post('/api/v1/diagnostics',json=payload(sid,None),headers=headers).json(); assert b['requires_human_review']; assert b['confidence']<.60

def test_retrieve_history_feedback(client,student):
    sid,headers=student
    b=client.post('/api/v1/diagnostics',json=payload(sid),headers=headers).json(); did=b['diagnostic_id']
    assert client.get('/api/v1/diagnostics/'+did,headers=headers).status_code==200
    assert client.get(f'/api/v1/students/{sid}/diagnostics',headers=headers).json()['total']==1
    feedback=client.post('/api/v1/diagnostics/'+did+'/feedback',json={'is_accurate':True},headers=headers)
    assert feedback.status_code==201

def test_404(client,student):
    sid,headers=student
    r=client.get('/api/v1/diagnostics/diag_missing',headers=headers); assert r.status_code==404; assert r.json()['error']['code']=='DIAGNOSTIC_NOT_FOUND'

def test_ocr_contract(client,student):
    sid,headers=student
    r=client.post('/api/v1/diagnostics/from-image',data={'student_id':sid,'student_answer':'6'},files={'problem_image':('x.txt',b'x','text/plain')},headers=headers); assert r.status_code==415

def test_unauthenticated_request_is_rejected(client):
    r=client.post('/api/v1/diagnostics',json=payload('stu_anonymous'))
    assert r.status_code==401
    assert r.json()['error']['code']=='INVALID_TOKEN'

def test_student_cannot_read_another_students_diagnostic_or_history(client,student):
    sid,headers=student
    b=client.post('/api/v1/diagnostics',json=payload(sid),headers=headers).json(); did=b['diagnostic_id']

    _, other_token = register_and_login(client, "diag-other-student@example.com")
    other_headers = auth_headers(other_token)

    single = client.get('/api/v1/diagnostics/'+did,headers=other_headers)
    assert single.status_code==403
    assert single.json()['error']['code']=='ACCESS_DENIED'

    history = client.get(f'/api/v1/students/{sid}/diagnostics',headers=other_headers)
    assert history.status_code==403
    assert history.json()['error']['code']=='ACCESS_DENIED'

def test_student_cannot_create_diagnostic_for_another_student(client,student):
    sid,headers=student
    r=client.post('/api/v1/diagnostics',json=payload('someone-else'),headers=headers)
    assert r.status_code==403
    assert r.json()['error']['code']=='ACCESS_DENIED'
