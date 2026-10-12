from fastapi import APIRouter

from app.api.document_types.router import document_type_router
from app.api.issuers.router import issuer_router
from app.api.manufacturers.router import manufacturer_router
from app.api.products.router import product_router
from app.api.variants.router import variant_router

api_router = APIRouter()


@api_router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


api_router.include_router(manufacturer_router)
api_router.include_router(product_router)
api_router.include_router(variant_router)
api_router.include_router(document_type_router)
api_router.include_router(issuer_router)