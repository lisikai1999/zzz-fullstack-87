from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import static_game, repeated_game, auction
from database import init_db

app = FastAPI(title="Game Theory Simulation Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(static_game.router, prefix="/api/static-game", tags=["Static Game"])
app.include_router(repeated_game.router, prefix="/api/repeated-game", tags=["Repeated Game"])
app.include_router(auction.router, prefix="/api/auction", tags=["Auction"])


@app.on_event("startup")
async def startup():
    await init_db()


@app.get("/api/health")
async def health():
    return {"status": "ok"}
