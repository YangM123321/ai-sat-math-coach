"""Seed a minimal SAT Math skill catalog for local development."""
import sys
from pathlib import Path

# Allow running as `python scripts/seed_sat_skills.py` without setting
# PYTHONPATH: only the script's own directory is on sys.path by default,
# not the repository root where the `app` package lives.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import RelationshipCreate, RelationshipType, SkillCreate
from app.schemas.diagnostic import Domain
from app.services.mastery_service import KnowledgeService

SKILLS = [
    SkillCreate(code="linear_equations", name="Linear equations", domain=Domain.algebra),
    SkillCreate(code="inverse_operations", name="Inverse operations", domain=Domain.algebra, parent_code="linear_equations"),
    SkillCreate(code="systems_of_equations", name="Systems of equations", domain=Domain.algebra),
    SkillCreate(code="quadratic_equations", name="Quadratic equations", domain=Domain.advanced_math),
    SkillCreate(code="percentages", name="Percentages", domain=Domain.problem_solving_and_data_analysis),
    SkillCreate(code="circles", name="Circles", domain=Domain.geometry_and_trigonometry),
]

RELATIONSHIPS = [
    RelationshipCreate(
        source_skill_code="inverse_operations",
        target_skill_code="linear_equations",
        relationship_type=RelationshipType.part_of,
        weight=1.0,
    ),
    RelationshipCreate(
        source_skill_code="linear_equations",
        target_skill_code="systems_of_equations",
        relationship_type=RelationshipType.prerequisite_of,
        weight=0.9,
    ),
    RelationshipCreate(
        source_skill_code="linear_equations",
        target_skill_code="quadratic_equations",
        relationship_type=RelationshipType.prerequisite_of,
        weight=0.7,
    ),
]


def main():
    with SessionLocal() as db:
        service = KnowledgeService(KnowledgeRepository(db))
        for skill in SKILLS:
            if not service.repository.get_skill_by_code(skill.code):
                service.create_skill(skill)
        for relationship in RELATIONSHIPS:
            try:
                service.create_relationship(relationship)
            except Exception:
                db.rollback()
        print("SAT Math skill catalog seeded.")


if __name__ == "__main__":
    main()
