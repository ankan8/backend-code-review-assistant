from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles 
from .db import init_db
from .routes.reviews import router as reviews_router
from .routes.llm import router as llm_router



app = FastAPI(title="Code Review Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/app", StaticFiles(directory="app/static", html=True), name="static") 

@app.on_event("startup")
def on_startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(reviews_router)
app.include_router(llm_router)
