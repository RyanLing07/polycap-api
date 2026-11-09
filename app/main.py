from fastapi import FastAPI
from app.routers import kits

app = FastAPI(title="Gundam API", version="0.1.0")
app.include_router(kits.router)

@app.get("/")
def root():
    return {"message": "Gundam API is running"}

@app.get("/v1/health")
def health_check():
    return {"status": "healthy"}