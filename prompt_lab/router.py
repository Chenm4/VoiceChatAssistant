"""FastAPI routes for the interview prompt laboratory."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from prompt_lab.service import (
    create_run,
    get_catalog,
    list_prompt_history,
    list_runs,
    load_run,
    save_background,
    save_prompt,
    update_review,
)


router = APIRouter(prefix="/prompt-lab", tags=["prompt-lab"])


class RunRequest(BaseModel):
    name: Optional[str] = None
    source_name: str
    models: List[str]
    prompt_ids: List[str]
    question_ids: List[str]
    temperature: float = Field(default=0.5, ge=0, le=2)
    top_p: float = Field(default=0.9, ge=0, le=1)
    max_concurrency: int = Field(default=2, ge=1, le=5)


class ReviewRequest(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    note: str = Field(default="", max_length=2000)


class PromptRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(min_length=1, max_length=20000)
    user_prompt_template: str = Field(min_length=1, max_length=20000)


class BackgroundRequest(BaseModel):
    content: str = Field(default="", max_length=50000)


@router.get("/catalog")
async def catalog():
    return get_catalog()


@router.patch("/background")
async def edit_background(request: BackgroundRequest):
    return save_background(request.content)


@router.get("/runs")
async def runs():
    return {"runs": list_runs()}


@router.post("/prompts")
async def create_prompt(request: PromptRequest):
    try:
        return save_prompt(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/prompts/{prompt_id}")
async def edit_prompt(prompt_id: str, request: PromptRequest):
    try:
        return save_prompt(request.model_dump(), prompt_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="提示词不存在") from exc


@router.get("/prompts/{prompt_id}/history")
async def prompt_history(prompt_id: str):
    try:
        return {"versions": list_prompt_history(prompt_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="提示词不存在") from exc


@router.post("/runs")
async def start_run(request: RunRequest):
    try:
        return create_run(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/runs/{run_id}")
async def run_detail(run_id: str):
    try:
        return load_run(run_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="实验不存在") from exc


@router.patch("/runs/{run_id}/items/{item_id}")
async def review_result(run_id: str, item_id: str, request: ReviewRequest):
    try:
        return await update_review(run_id, item_id, request.rating, request.note)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="实验不存在") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="结果不存在") from exc
