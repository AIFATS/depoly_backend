from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.routes import router  # Importing router from routes.py

# Create a FastAPI instance
app = FastAPI()
print("FastAPI instance created.")
# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this for security in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routes from routes.py
app.include_router(router)

# Run the FastAPI app
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("setup:app", host="0.0.0.0", port=8000, reload=True)
