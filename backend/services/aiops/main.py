from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import services, hosts, datamart, security, ops, aiops, users

app = FastAPI(title="CloudRealm Backend API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(services.router, prefix="/api", tags=["Services"])
app.include_router(hosts.router, prefix="/api", tags=["Hosts"])
app.include_router(datamart.router, prefix="/api", tags=["DataMart"])
app.include_router(security.router, prefix="/api", tags=["Security"])
app.include_router(ops.router, prefix="/api", tags=["Ops"])
app.include_router(aiops.router, prefix="/api", tags=["AIOps"])
app.include_router(users.router, prefix="/api", tags=["Users"])

@app.get("/")
async def root():
    return {"message": "Welcome to CloudRealm API"}

if __name__ == "__main__":
    import uvicorn
    # Reload is enabled for dev environment
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
