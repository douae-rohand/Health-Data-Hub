from fastapi import FastAPI

app = FastAPI(title="ms-entrepot-omop")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ms-entrepot-omop"}

# Chaque dev ajoute ses routes dans son propre APIRouter
# puis une ligne app.include_router(...) ici.
