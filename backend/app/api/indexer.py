import os
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from app.models.schemas import IndexRequest, IndexResponse
from app.services.rag_service import rag_service

router = APIRouter()

def bg_index_task(project_name: str, repo_path: str, framework: str, language: str, tags: list):
    try:
        rag_service.index_project_files(
            project_name=project_name,
            repo_path=repo_path,
            framework=framework,
            language=language,
            tags=tags
        )
    except Exception as e:
        print(f"Background indexing task failed: {e}")

@router.post("/index", response_model=IndexResponse)
async def index_project(request: IndexRequest, background_tasks: BackgroundTasks):
    if not os.path.exists(request.repo_path):
        raise HTTPException(
            status_code=400,
            detail=f"Repository path '{request.repo_path}' does not exist on host system."
        )

    # Trigger indexing in the background so API does not timeout for large projects
    background_tasks.add_task(
        bg_index_task,
        request.project_name,
        request.repo_path,
        request.framework,
        request.language,
        request.tags
    )

    return {
        "status": "Indexing job queued in background.",
        "chunks_indexed": 0,  # Processed asynchronously
        "project_name": request.project_name
    }
