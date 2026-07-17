from fastapi import APIRouter, Depends, Query, status
from app.api.dependencies import get_evaluation_service
from app.schemas.evaluation import *
from app.services.evaluation_service import EvaluationService

router=APIRouter(prefix="/api/v1/evaluation",tags=["evaluation"])

@router.post("/runs",response_model=EvaluationRunResponse,status_code=status.HTTP_201_CREATED)
def create_run(request:EvaluationRunCreate,service:EvaluationService=Depends(get_evaluation_service)):
    return service.create_run(request)

@router.get("/runs/{run_id}",response_model=EvaluationRunResponse)
def get_run(run_id:str,service:EvaluationService=Depends(get_evaluation_service)):
    return service.get_run(run_id)

@router.get("/runs",response_model=list[EvaluationRunResponse])
def list_runs(component:EvaluationComponent|None=None,limit:int=Query(20,ge=1,le=100),service:EvaluationService=Depends(get_evaluation_service)):
    return service.list_runs(component,limit)

@router.post("/metrics",response_model=MetricSnapshotResponse,status_code=status.HTTP_201_CREATED)
def create_metric(request:MetricSnapshotCreate,service:EvaluationService=Depends(get_evaluation_service)):
    return service.save_metric(request)

@router.get("/metrics/{component}",response_model=list[MetricSnapshotResponse])
def metric_history(component:EvaluationComponent,metric_name:str|None=None,limit:int=Query(100,ge=1,le=500),service:EvaluationService=Depends(get_evaluation_service)):
    return service.metric_history(component,metric_name,limit)

@router.post("/experiments",response_model=ExperimentResponse,status_code=status.HTTP_201_CREATED)
def create_experiment(request:ExperimentCreate,service:EvaluationService=Depends(get_evaluation_service)):
    return service.create_experiment(request)

@router.post("/experiments/{experiment_id}/complete",response_model=ExperimentResponse)
def complete_experiment(experiment_id:str,request:ExperimentResultUpdate,service:EvaluationService=Depends(get_evaluation_service)):
    return service.complete_experiment(experiment_id,request)
