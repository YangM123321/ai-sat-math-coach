from datetime import datetime, timezone

from app.models.knowledge import MasteryEvent, StudentSkillMastery
from app.schemas.knowledge import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeGraphResponse,
    KnowledgeProfileResponse,
    MasteryEventResponse,
    MasteryEvidenceInput,
    MasteryStatus,
    RelationshipCreate,
    RelationshipResponse,
    SkillCreate,
    SkillMasteryResponse,
    SkillResponse,
)


class SkillNotFoundError(ValueError):
    pass


class KnowledgeService:
    DIFFICULTY_WEIGHT = {"easy": 0.8, "medium": 1.0, "hard": 1.2}

    def __init__(self, repository):
        self.repository = repository

    def create_skill(self, request: SkillCreate) -> SkillResponse:
        if self.repository.get_skill_by_code(request.code):
            raise ValueError(f"Skill code already exists: {request.code}")
        parent = None
        if request.parent_code:
            parent = self.repository.get_skill_by_code(request.parent_code)
            if not parent:
                raise SkillNotFoundError(request.parent_code)
        skill = self.repository.create_skill(
            code=request.code,
            name=request.name,
            domain=request.domain.value,
            description=request.description,
            parent_id=parent.id if parent else None,
            active=request.active,
        )
        return self._skill_response(skill, request.parent_code)

    def list_skills(self) -> list[SkillResponse]:
        skills = self.repository.list_skills()
        code_by_id = {skill.id: skill.code for skill in skills}
        return [self._skill_response(skill, code_by_id.get(skill.parent_id)) for skill in skills]

    def create_relationship(self, request: RelationshipCreate) -> RelationshipResponse:
        source = self.repository.get_skill_by_code(request.source_skill_code)
        target = self.repository.get_skill_by_code(request.target_skill_code)
        if not source:
            raise SkillNotFoundError(request.source_skill_code)
        if not target:
            raise SkillNotFoundError(request.target_skill_code)
        relationship = self.repository.create_relationship(source, target, request.relationship_type.value, request.weight)
        return RelationshipResponse(
            id=relationship.id,
            source_skill_code=source.code,
            target_skill_code=target.code,
            relationship_type=relationship.relationship_type,
            weight=relationship.weight,
            created_at=relationship.created_at,
        )

    def apply_evidence(self, request: MasteryEvidenceInput) -> MasteryEventResponse:
        skill = self.repository.get_skill_by_code(request.skill_code)
        if not skill:
            raise SkillNotFoundError(request.skill_code)
        existing = self.repository.get_event(request.evidence_type.value, request.source_id, skill.id)
        if existing:
            return self._event_response(existing, skill.code)

        mastery = self.repository.get_mastery(request.student_id, skill.id)
        if not mastery:
            mastery = StudentSkillMastery(
                student_id=request.student_id,
                skill_id=skill.id,
                mastery_score=0.5,
                confidence=0.0,
                attempt_count=0,
                correct_count=0,
                updated_at=datetime.now(timezone.utc),
            )

        previous = mastery.mastery_score
        evidence_weight = self._evidence_weight(request)
        target = 1.0 if request.is_correct else 0.0
        delta = (target - previous) * evidence_weight
        new_score = round(max(0.0, min(1.0, previous + delta)), 4)
        occurred_at = request.occurred_at or datetime.now(timezone.utc)

        mastery.mastery_score = new_score
        mastery.attempt_count += 1
        mastery.correct_count += int(request.is_correct)
        mastery.confidence = round(1 - (0.75 ** mastery.attempt_count), 4)
        mastery.last_evidence_at = occurred_at
        mastery.updated_at = datetime.now(timezone.utc)

        event = MasteryEvent(
            student_id=request.student_id,
            skill_id=skill.id,
            evidence_type=request.evidence_type.value,
            source_id=request.source_id,
            is_correct=request.is_correct,
            error_category=request.error_category,
            difficulty=request.difficulty,
            evidence_weight=evidence_weight,
            previous_score=previous,
            score_delta=round(delta, 4),
            new_score=new_score,
            occurred_at=occurred_at,
        )
        saved = self.repository.save_evidence(mastery, event)
        if saved is None:
            existing = self.repository.get_event(request.evidence_type.value, request.source_id, skill.id)
            return self._event_response(existing, skill.code)
        return self._event_response(saved, skill.code)

    def get_profile(self, student_id: str) -> KnowledgeProfileResponse:
        masteries = self.repository.list_student_masteries(student_id)
        items = [self._mastery_response(mastery) for mastery in masteries]
        overall = round(sum(item.mastery_score for item in items) / len(items), 4) if items else 0.0
        return KnowledgeProfileResponse(
            student_id=student_id,
            overall_mastery=overall,
            weakest_skills=items[:3],
            strongest_skills=list(reversed(items[-3:])),
            skills=items,
            generated_at=datetime.now(timezone.utc),
        )

    def get_graph(self, student_id: str) -> KnowledgeGraphResponse:
        skills = self.repository.list_skills()
        masteries = {m.skill_id: m for m in self.repository.list_student_masteries(student_id)}
        nodes = []
        for skill in skills:
            mastery = masteries.get(skill.id)
            nodes.append(
                KnowledgeGraphNode(
                    code=skill.code,
                    name=skill.name,
                    domain=skill.domain,
                    mastery_score=mastery.mastery_score if mastery else None,
                    status=self._status(mastery.mastery_score) if mastery else None,
                )
            )
        edges = [
            KnowledgeGraphEdge(
                source=relationship.source_skill.code,
                target=relationship.target_skill.code,
                relationship_type=relationship.relationship_type,
                weight=relationship.weight,
            )
            for relationship in self.repository.list_relationships()
        ]
        return KnowledgeGraphResponse(student_id=student_id, nodes=nodes, edges=edges)

    def _evidence_weight(self, request: MasteryEvidenceInput) -> float:
        base = 0.18 if request.is_correct else 0.24
        confidence_factor = 0.5 + (0.5 * request.diagnostic_confidence)
        difficulty_factor = self.DIFFICULTY_WEIGHT[request.difficulty]
        if request.error_category == "insufficient_evidence":
            confidence_factor *= 0.5
        return round(min(0.35, base * confidence_factor * difficulty_factor), 4)

    @staticmethod
    def _status(score: float) -> MasteryStatus:
        if score < 0.2:
            return MasteryStatus.not_started
        if score < 0.4:
            return MasteryStatus.emerging
        if score < 0.65:
            return MasteryStatus.developing
        if score < 0.85:
            return MasteryStatus.proficient
        return MasteryStatus.mastered

    def _mastery_response(self, mastery) -> SkillMasteryResponse:
        return SkillMasteryResponse(
            skill_code=mastery.skill.code,
            skill_name=mastery.skill.name,
            domain=mastery.skill.domain,
            mastery_score=mastery.mastery_score,
            status=self._status(mastery.mastery_score),
            confidence=mastery.confidence,
            attempt_count=mastery.attempt_count,
            correct_count=mastery.correct_count,
            last_evidence_at=mastery.last_evidence_at,
            updated_at=mastery.updated_at,
        )

    @staticmethod
    def _skill_response(skill, parent_code):
        return SkillResponse(
            id=skill.id,
            code=skill.code,
            name=skill.name,
            domain=skill.domain,
            description=skill.description,
            parent_code=parent_code,
            active=skill.active,
            created_at=skill.created_at,
        )

    @staticmethod
    def _event_response(event, skill_code):
        return MasteryEventResponse(
            event_id=event.id,
            student_id=event.student_id,
            skill_code=skill_code,
            previous_score=event.previous_score,
            score_delta=event.score_delta,
            new_score=event.new_score,
            evidence_weight=event.evidence_weight,
            created_at=event.created_at,
        )
