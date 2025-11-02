from contextlib import asynccontextmanager, AsyncExitStack
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.chat_api import router as chat_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        yield


app = FastAPI(
    title="Neuro Ma API",
    description="API for Neuro Ma LangGraph-based agent workflow",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint to verify service is running.
    
    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "Neuro Ma API"
    }
