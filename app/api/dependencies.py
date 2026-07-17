from fastapi import Depends
from app.db.session import get_db
from app.core.config import get_settings
from app.repositories.diagnostic_repository import Repository
from app.services.grading_service import GradingService
from app.services.llm_service import RuleBasedProvider
from app.services.confidence_service import ConfidenceService
from app.services.diagnostic_service import DiagnosticService

def get_service(db=Depends(get_db)):
    s=get_settings()
    if s.diagnostic_provider!='rule_based': raise RuntimeError('Only rule_based is implemented in V1')
    return DiagnosticService(Repository(db),GradingService(),RuleBasedProvider(),ConfidenceService(s.human_review_threshold))

from app.repositories.knowledge_repository import KnowledgeRepository
from app.services.mastery_service import KnowledgeService

def get_knowledge_service(db=Depends(get_db)):
    return KnowledgeService(KnowledgeRepository(db))

from app.repositories.learning_repository import LearningRepository
from app.services.learning_service import LearningService

def get_learning_service(db=Depends(get_db)):
    return LearningService(LearningRepository(db))

from app.repositories.tutor_repository import TutorRepository
from app.services.tutor_service import TutorService

def get_tutor_service(db=Depends(get_db)):
    return TutorService(TutorRepository(db))

from app.repositories.dashboard_repository import DashboardRepository
from app.services.dashboard_service import DashboardService

def get_dashboard_service(db=Depends(get_db)):
    return DashboardService(DashboardRepository(db))

from app.repositories.evaluation_repository import EvaluationRepository
from app.services.evaluation_service import EvaluationService

def get_evaluation_service(db=Depends(get_db)):
    return EvaluationService(EvaluationRepository(db))
