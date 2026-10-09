"""
EVO-COMP — Phase 1 Backend
Adaptive Evolutionary Compiler — Interactive Lexical Analysis Laboratory

Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router as lex_router
from api.pipeline_routes import router as pipeline_router

app = FastAPI(
    title="EVO-COMP Backend",
    description=(
        "EVO-COMP: Source Code -> Lexer -> Parser -> AST -> Semantic Analysis -> IR -> CFG -> "
        "Program DNA -> Evolutionary Optimization -> Digital Twin -> Target Code -> EvoVM -> "
        "Execution -> Final Validation. Every stage is real, non-mocked compiler code."
    ),
    version="2.0.0",
)

# CORS is open for local development of the Vite dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lex_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")


@app.get("/")
def root():
    return {
        "project": "EVO-COMP",
        "phase": "Phase 2+ — Full pipeline (parser through final validation)",
        "pipeline_implemented": [
            "Source", "Lexer", "Parser", "AST", "Semantic Analysis", "IR", "CFG",
            "Program DNA", "Evolutionary Optimization", "Digital Twin",
            "Target Code (EvoVM bytecode)", "EvoVM Execution", "Final Validation",
        ],
        "endpoints": {
            "lex (Phase 1, stateless)": "POST /api/lex",
            "one-shot compile": "POST /api/compile",
            "stage-by-stage": "POST /api/session, POST /api/session/{id}/run/{stage}",
            "pipeline metadata": "GET /api/stages",
        },
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
