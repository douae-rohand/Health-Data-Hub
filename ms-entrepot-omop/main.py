from fastapi import FastAPI

from app.routes_ingest import router as ingest_router

app = FastAPI(title="ms-entrepot-omop")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ms-entrepot-omop"}


# Chaque dev ajoute ses routes dans son propre APIRouter
# puis une ligne app.include_router(...) ici.
app.include_router(ingest_router)   # Dev 3 : POST /ingest/fhir
