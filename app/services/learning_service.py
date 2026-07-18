from datetime import date, datetime, timedelta, timezone
from app.models.learning import LearningActivity, LearningPlan
from app.schemas.learning import LearningActivityResponse, LearningActivityUpdate, LearningPlanCreate, LearningPlanResponse

ALGORITHM_VERSION = "personalization-v1.0"

class LearningPlanNotFoundError(Exception): pass
class LearningActivityNotFoundError(Exception): pass
class NoSkillCatalogError(Exception): pass

class LearningService:
    def __init__(self, repository): self.repository = repository

    def generate(self, request: LearningPlanCreate) -> LearningPlanResponse:
        skills = self.repository.list_skills()
        if not skills: raise NoSkillCatalogError("No active SAT Math skills are configured")
        masteries = {m.skill_id: m for m in self.repository.list_masteries(request.student_id)}
        relationships = self.repository.list_relationships()
        skill_by_id = {s.id: s for s in skills}
        prerequisite_bonus = {s.id: 0.0 for s in skills}
        for rel in relationships:
            if rel.relationship_type == "prerequisite_of" and rel.source_skill_id in prerequisite_bonus:
                target_mastery = masteries.get(rel.target_skill_id)
                if target_mastery and target_mastery.mastery_score < 0.65:
                    prerequisite_bonus[rel.source_skill_id] = max(prerequisite_bonus[rel.source_skill_id], 0.08 * rel.weight)

        ranked = []
        for skill in skills:
            mastery = masteries.get(skill.id)
            score = mastery.mastery_score if mastery else 0.5
            confidence = mastery.confidence if mastery else 0.0
            unseen = 1.0 if mastery is None else 0.0
            priority = (1-score)*0.70 + (1-confidence)*0.20 + unseen*0.10 + prerequisite_bonus[skill.id]
            ranked.append((round(priority, 4), skill, mastery))
        ranked.sort(key=lambda x: (-x[0], x[1].code))
        focus = ranked[:request.max_focus_skills]

        start = request.start_date or date.today()
        end = start + timedelta(days=request.duration_days - 1)
        snapshot = {
            item[1].code: {
                "mastery_score": item[2].mastery_score if item[2] else None,
                "confidence": item[2].confidence if item[2] else 0.0,
                "priority_score": item[0],
            } for item in ranked
        }
        old = self.repository.active_plan(request.student_id)
        plan = LearningPlan(
            student_id=request.student_id, version=self.repository.next_version(request.student_id), status="active",
            start_date=start, end_date=end, target_score=request.target_score, exam_date=request.exam_date,
            daily_minutes=request.daily_minutes, algorithm_version=ALGORITHM_VERSION, profile_snapshot=snapshot,
            generation_metadata={"duration_days": request.duration_days, "max_focus_skills": request.max_focus_skills},
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
        )
        activities=[]
        for day in range(request.duration_days):
            priority, skill, mastery = focus[day % len(focus)]
            score = mastery.mastery_score if mastery else 0.5
            activity_type, difficulty = self._activity(score, day, request.duration_days)
            minutes = request.daily_minutes
            question_count = max(3, minutes // 5)
            rationale = self._rationale(skill.name, score, mastery.confidence if mastery else 0.0, prerequisite_bonus[skill.id])
            activities.append(LearningActivity(
                plan=plan, skill_id=skill.id, scheduled_date=start+timedelta(days=day), sequence=day+1,
                activity_type=activity_type, difficulty=difficulty, estimated_minutes=minutes,
                question_count=question_count, rationale=rationale, priority_score=priority,
                status="pending", completed_questions=0, correct_questions=0,
                created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
            ))
        saved = self.repository.save_plan(plan, activities, old)
        return self._response(saved)

    def get(self, plan_id):
        plan=self.repository.get_plan(plan_id)
        if not plan: raise LearningPlanNotFoundError(plan_id)
        return self._response(plan)

    def get_active(self, student_id):
        plan=self.repository.active_plan(student_id)
        if not plan: raise LearningPlanNotFoundError(student_id)
        return self._response(plan)

    def get_activity_owner_student_id(self, activity_id):
        """Cheap ownership lookup for the route layer to authorize
        against before performing the full update -- avoids threading
        the authenticated principal through service business logic."""
        activity=self.repository.get_activity(activity_id)
        if not activity: raise LearningActivityNotFoundError(activity_id)
        return activity.plan.student_id

    def update_activity(self, activity_id, request: LearningActivityUpdate):
        activity=self.repository.get_activity(activity_id)
        if not activity: raise LearningActivityNotFoundError(activity_id)
        activity.status=request.status.value
        if request.completed_questions is not None: activity.completed_questions=request.completed_questions
        if request.correct_questions is not None: activity.correct_questions=request.correct_questions
        now=datetime.now(timezone.utc)
        if request.status.value == "in_progress" and not activity.started_at: activity.started_at=now
        if request.status.value == "completed":
            activity.completed_at=now
            if not activity.started_at: activity.started_at=now
        activity.updated_at=now
        self.repository.save_activity(activity)
        return self._activity_response(activity)

    @staticmethod
    def _activity(score, day, duration):
        if day == duration-1: return "checkpoint", "medium"
        if score < 0.4: return "concept_review", "easy"
        if score < 0.65: return "guided_practice", "medium"
        if score < 0.85: return "independent_practice", "medium"
        return "mixed_review", "hard"

    @staticmethod
    def _rationale(name, score, confidence, prereq_bonus):
        reason=f"{name} was selected because current mastery is {score:.0%} and confidence is {confidence:.0%}."
        if prereq_bonus: reason += " It is also a prerequisite for another weak skill."
        return reason

    def _response(self, plan):
        focus=[]
        for activity in plan.activities:
            if activity.skill.code not in focus: focus.append(activity.skill.code)
        return LearningPlanResponse(
            id=plan.id, student_id=plan.student_id, version=plan.version, status=plan.status,
            start_date=plan.start_date, end_date=plan.end_date, target_score=plan.target_score,
            exam_date=plan.exam_date, daily_minutes=plan.daily_minutes, algorithm_version=plan.algorithm_version,
            focus_skills=focus, activities=[self._activity_response(a) for a in plan.activities], created_at=plan.created_at,
        )

    @staticmethod
    def _activity_response(a):
        return LearningActivityResponse(
            id=a.id, skill_code=a.skill.code, skill_name=a.skill.name, scheduled_date=a.scheduled_date,
            sequence=a.sequence, activity_type=a.activity_type, difficulty=a.difficulty,
            estimated_minutes=a.estimated_minutes, question_count=a.question_count, rationale=a.rationale,
            priority_score=a.priority_score, status=a.status, completed_questions=a.completed_questions,
            correct_questions=a.correct_questions,
        )
