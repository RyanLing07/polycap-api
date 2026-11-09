from fastapi import FastAPI
from app import models  # noqa: F401  (registers the tables with Base)
from app.database import Base, engine
from app.routers import kits

# Creates tables if they don't exist yet. Alembic replaces this later.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gundam API", version="0.1.0")
app.include_router(kits.router)

@app.get("/")
def root():
    return {"message": "Gundam API is running"}

@app.get("/v1/health")
def health_check():
    return {"status": "healthy"}