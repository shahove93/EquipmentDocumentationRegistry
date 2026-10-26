from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.batches.schemas import BatchCreate, BatchRead, BatchUpdate
from app.database.connection import get_db
from app.services.batch_service import DEFAULT_LIMIT, BatchService, VariantNotFoundError

batch_router = APIRouter(prefix="/batches", tags=["batches"])


@batch_router.post(
    "", response_model=BatchRead, status_code=status.HTTP_201_CREATED,
    summary="Create a batch",
)
def create_batch(
    data: BatchCreate, response: Response, request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> BatchRead:
    try:
        batch = BatchService.create(db, data)
    except VariantNotFoundError as error:
        raise HTTPException(404, detail=f"Variant {error.variant_id} not found") from error
    response.headers["Location"] = str(request.url_for("get_batch", batch_id=batch.id))
    return BatchRead.model_validate(batch)


@batch_router.get(
    "/{batch_id}", response_model=BatchRead, summary="Get a batch by id",
)
def get_batch(batch_id: int, db: Annotated[Session, Depends(get_db)]) -> BatchRead:
    batch = BatchService.get_by_id(db, batch_id)
    if batch is None:
        raise HTTPException(404, detail=f"Batch {batch_id} not found")
    return BatchRead.model_validate(batch)


@batch_router.get("", response_model=list[BatchRead], summary="List batches")
def list_batches(
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BatchRead]:
    return [BatchRead.model_validate(item) for item in BatchService.list(db, limit, offset)]


@batch_router.patch(
    "/{batch_id}", response_model=BatchRead, summary="Update a batch",
)
def update_batch(
    batch_id: int, data: BatchUpdate, db: Annotated[Session, Depends(get_db)],
) -> BatchRead:
    try:
        batch = BatchService.update(db, batch_id, data)
    except VariantNotFoundError as error:
        raise HTTPException(404, detail=f"Variant {error.variant_id} not found") from error
    if batch is None:
        raise HTTPException(404, detail=f"Batch {batch_id} not found")
    return BatchRead.model_validate(batch)
