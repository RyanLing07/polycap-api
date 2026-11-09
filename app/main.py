from fastapi import FastAPI
from app import models  # noqa: F401  (registers the tables with Base)
from app.database import Base, engine
from app.routers import kits

# Creates tables if they don't exist yet. Alembic replaces this later.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Polycap API",
    description="Catalog API for Gundam model kits (Gunpla).",
    version="0.1.0",
)
app.include_router(kits.router)

@app.get("/")
def root():
    return {"message": "Polycap API is running"}

@app.get("/v1/health")
def health_check():
    return {"status": "healthy"}