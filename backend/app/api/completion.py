import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.models.schemas import QueryRequest

router = APIRouter()


@router.post("/generate")
async def generate_completion(request: QueryRequest):

    async def event_generator():

        mock_response = {
            "node": "assistant",
            "data": f"""
Mock AI Response for:

{request.prompt}


def binary_search(arr, target):
    left, right = 0, len(arr)-1

    while left <= right:
        mid = (left + right) // 2

        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1
"""
        }

        yield f"data: {json.dumps(mock_response)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )