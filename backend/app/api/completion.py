import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.models.schemas import QueryRequest
from app.services.agent_graph import agent_orchestrator

router = APIRouter()

@router.post("/generate")
async def generate_completion(request: QueryRequest):
    """
    Triggers the multi-agent graph loop, streaming agent state actions and
    the code suggestions back to the VSCode client using Server-Sent Events (SSE).
    """
    
    async def event_generator():
        # Context extraction and formatting helper
        workspace = request.workspace_context.model_dump() if request.workspace_context else None
        
        try:
            async for step in agent_orchestrator.execute(
                query=request.prompt,
                workspace_context=workspace,
                project_filter=request.project_filter,
                use_peft=request.use_peft
            ):
                # Yield SSE chunk
                yield f"data: {json.dumps(step)}\n\n"
        except Exception as e:
            err_msg = {"node": "error", "data": f"Internal execution exception: {str(e)}"}
            yield f"data: {json.dumps(err_msg)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
