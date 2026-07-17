from datetime import datetime, timezone
from app.models.tutor import TutorFeedback, TutorMessage, TutorSession
from app.prompts.tutor_prompt import TUTOR_POLICY_VERSION
from app.schemas.tutor import *

class TutorSessionNotFoundError(Exception): pass
class TutorSkillNotFoundError(Exception): pass
class TutorSessionClosedError(Exception): pass

class RuleBasedTutorProvider:
    name='rule_based_socratic'
    def opening(self,request):
        if request.student_work:
            return ('socratic', 'Let’s inspect your work first. What was the goal of your first step, and which operation did you use to keep the equation balanced?')
        return ('socratic', 'Before calculating, what quantity is the problem asking you to find, and what information connects to it?')
    def reply(self,session,student_message):
        text=student_message.lower().strip()
        if any(p in text for p in ['just tell me','give me the answer','show answer']):
            if session.hints_used < session.max_hints:
                return ('hint','Try isolating the unknown one operation at a time. What inverse operation would undo the constant term?')
            return ('explanation', self._explanation(session))
        if any(p in text for p in ["don't know",'not sure','stuck']):
            return ('hint','Start by naming the operation closest to the variable. What opposite operation would remove it while keeping both sides equal?')
        if any(p in text for p in ['because','so ','therefore','=']):
            return ('reflection','Good—now verify that the same operation was applied to both sides. What should the next simplified equation be?')
        return ('socratic','What mathematical rule supports that step, and how can you check it against the original problem?')
    @staticmethod
    def _explanation(session):
        if session.correct_answer:
            return f'Work backward using inverse operations, checking both sides after each step. The expected final answer is {session.correct_answer}. Now explain which step changes the original equation first.'
        return 'Work one transformation at a time, apply the same operation to both sides, and substitute your result back into the original problem to verify it.'

class TutorService:
    def __init__(self,repository,provider=None): self.repository=repository; self.provider=provider or RuleBasedTutorProvider()
    def create(self,request:TutorSessionCreate):
        skill=self.repository.skill_by_code(request.skill_code)
        if not skill: raise TutorSkillNotFoundError(request.skill_code)
        strategy,content=self.provider.opening(request)
        session=TutorSession(student_id=request.student_id,skill_id=skill.id,learning_activity_id=request.learning_activity_id,status='active',problem_text=request.problem_text,correct_answer=request.correct_answer,student_answer=request.student_answer,student_work=request.student_work,current_step=0,max_hints=3,hints_used=0,provider=self.provider.name,policy_version=TUTOR_POLICY_VERSION)
        messages=[]
        if request.student_work: messages.append(TutorMessage(session=session,role='student',content=request.student_work,strategy=None,sequence=1))
        messages.append(TutorMessage(session=session,role='tutor',content=content,strategy=strategy,sequence=len(messages)+1))
        return self._response(self.repository.save_session(session,messages))
    def get(self,session_id):
        session=self.repository.get_session(session_id)
        if not session: raise TutorSessionNotFoundError(session_id)
        return self._response(session)
    def send(self,session_id,request:TutorMessageCreate):
        session=self.repository.get_session(session_id)
        if not session: raise TutorSessionNotFoundError(session_id)
        if session.status!='active': raise TutorSessionClosedError(session_id)
        sequence=self.repository.next_sequence(session_id)
        student=TutorMessage(session=session,role='student',content=request.content,strategy=None,sequence=sequence)
        strategy,content=self.provider.reply(session,request.content)
        if strategy=='hint': session.hints_used+=1
        session.current_step+=1; session.updated_at=datetime.now(timezone.utc)
        tutor=TutorMessage(session=session,role='tutor',content=content,strategy=strategy,sequence=sequence+1)
        return self._response(self.repository.save_messages(session,[student,tutor]))
    def complete(self,session_id,request:TutorSessionComplete):
        session=self.repository.get_session(session_id)
        if not session: raise TutorSessionNotFoundError(session_id)
        if request.reflection:
            seq=self.repository.next_sequence(session_id)
            self.repository.save_messages(session,[TutorMessage(session=session,role='student',content=request.reflection,strategy='reflection',sequence=seq)])
        session.status='completed'; session.completed_at=datetime.now(timezone.utc); session.updated_at=session.completed_at
        return self._response(self.repository.save_messages(session,[]))
    def feedback(self,session_id,request:TutorFeedbackCreate):
        session=self.repository.get_session(session_id)
        if not session: raise TutorSessionNotFoundError(session_id)
        item=TutorFeedback(session_id=session_id,helpful=request.helpful,rating=request.rating,comment=request.comment)
        saved=self.repository.save_feedback(item); return {'feedback_id':saved.id,'session_id':session_id,'accepted':True}
    @staticmethod
    def _response(s):
        return TutorSessionResponse(id=s.id,student_id=s.student_id,skill_code=s.skill.code,status=s.status,problem_text=s.problem_text,current_step=s.current_step,max_hints=s.max_hints,hints_used=s.hints_used,provider=s.provider,policy_version=s.policy_version,messages=[TutorMessageResponse(id=m.id,role=m.role,content=m.content,strategy=m.strategy,sequence=m.sequence,created_at=m.created_at) for m in s.messages],created_at=s.created_at,updated_at=s.updated_at)
