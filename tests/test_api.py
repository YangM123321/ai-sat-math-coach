def payload(work='2x = 17 + 5, so 2x = 22 and x = 7'):
    return {'student_id':'stu_001','question':{'question_text':'If 2x + 5 = 17, what is x?','correct_answer':'6','official_explanation':'Subtract 5, then divide by 2.','domain':'algebra','skill':'linear_equations','subskill':'inverse_operations','difficulty':'easy'},'student_answer':'7','work_text':work,'student_confidence':4,'time_spent_seconds':95}
def test_create(client):
    r=client.post('/api/v1/diagnostics',json=payload()); assert r.status_code==201; b=r.json(); assert b['error_category']=='procedural_error'; assert b['error_subcategory']=='inverse_operation_error'; assert not b['requires_human_review']
def test_correct(client):
    p=payload('Subtract 5, then divide by 2.'); p['student_answer']='6'; b=client.post('/api/v1/diagnostics',json=p).json(); assert b['correct'] and b['error_category']=='none'
def test_missing_work_review(client):
    b=client.post('/api/v1/diagnostics',json=payload(None)).json(); assert b['requires_human_review']; assert b['confidence']<.60
def test_retrieve_history_feedback(client):
    b=client.post('/api/v1/diagnostics',json=payload()).json(); did=b['diagnostic_id']; assert client.get('/api/v1/diagnostics/'+did).status_code==200; assert client.get('/api/v1/students/stu_001/diagnostics').json()['total']==1; assert client.post('/api/v1/diagnostics/'+did+'/feedback',json={'reviewer_id':'teacher_1','reviewer_type':'teacher','is_accurate':True}).status_code==201
def test_404(client):
    r=client.get('/api/v1/diagnostics/diag_missing'); assert r.status_code==404; assert r.json()['error']['code']=='DIAGNOSTIC_NOT_FOUND'
def test_ocr_contract(client):
    r=client.post('/api/v1/diagnostics/from-image',data={'student_id':'s','student_answer':'6'},files={'problem_image':('x.txt',b'x','text/plain')}); assert r.status_code==415
