from fastapi import FastAPI
from routers.quality import router as quality_router

app = FastAPI(title="ms-entrepot-omop")
app.include_router(quality_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ms-entrepot-omop"}

# Chaque dev ajoute ses routes dans son propre APIRouter
# puis une ligne app.include_router(...) ici.
