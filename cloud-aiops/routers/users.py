from fastapi import APIRouter
from typing import List
from models import User

router = APIRouter()

users_db = [
    User(username="admin", role="Super Admin", status="Active", last_login="Just now"),
    User(username="data_eng_01", role="Editor", status="Active", last_login="2h ago"),
    User(username="sec_auditor", role="Viewer", status="Inactive", last_login="3d ago"),
]

@router.get("/users", response_model=List[User])
async def get_users():
    return users_db
