import os

from dotenv import load_dotenv
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()
_ = load_dotenv()


class ModelInfoResponse(BaseModel):
    model: str


@router.get("/model", response_model=ModelInfoResponse)
async def get_model_info() -> ModelInfoResponse:
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")
    return ModelInfoResponse(model=model_name)
