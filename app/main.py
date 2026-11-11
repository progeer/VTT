import os
import shutil
import uuid
import json
import random
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from jose import JWTError, jwt
from passlib.context import CryptContext

from .database import engine, Base, get_db
from .routers import rooms, ws
from . import models

SECRET_KEY = "super_secret_vtt_key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ БАЗЫ ДАННЫХ ---
Base.metadata.create_all(bind=engine)
with engine.connect() as conn:
    try:
        conn.execute(text("SELECT avatar_url FROM characters LIMIT 1"))
    except Exception:
        conn.execute(text("ALTER TABLE characters ADD COLUMN avatar_url VARCHAR DEFAULT ''"))
        conn.commit()

app = FastAPI(title="VTT App")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(rooms.router)
app.include_router(ws.router)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None: raise credentials_exception
    return user


@app.post("/register")
def register_user(username: str, password: str, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    if user: raise HTTPException(status_code=400, detail="Username already registered")
    new_user = models.User(username=username, hashed_password=get_password_hash(password))
    db.add(new_user);
    db.commit();
    db.refresh(new_user)
    return {"message": "User created successfully"}


@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": create_access_token(data={"sub": user.username}), "token_type": "bearer"}


# --- УПРАВЛЕНИЕ ПЕРСОНАЖАМИ ---
@app.get("/api/characters")
def get_my_characters(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    chars = db.query(models.Character).filter(models.Character.user_id == current_user.id).all()
    return [
        {"id": c.id, "name": c.name or "Безымянный", "occupation": c.occupation or "", "avatar_url": c.avatar_url or ""}
        for c in chars]


@app.get("/api/characters/{char_id}")
def get_character(char_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    char = db.query(models.Character).filter(models.Character.id == char_id,
                                             models.Character.user_id == current_user.id).first()
    if not char: raise HTTPException(status_code=404, detail="Character not found")
    return {
        "id": char.id, "name": char.name, "age": char.age, "occupation": char.occupation, "birthplace": char.birthplace,
        "avatar_url": char.avatar_url,
        "str_val": char.str_val, "con_val": char.con_val, "pow_val": char.pow_val, "dex_val": char.dex_val,
        "app_val": char.app_val, "siz_val": char.siz_val, "int_val": char.int_val, "edu_val": char.edu_val,
        "hp_current": char.hp_current, "sanity_current": char.sanity_current, "mp_current": char.mp_current,
        "luck": char.luck,
        "skills": json.loads(char.skills_json or "{}"),
        "ideology": char.ideology, "significant_people": char.significant_people,
        "meaningful_locations": char.meaningful_locations, "treasured_possessions": char.treasured_possessions,
        "traits": char.traits, "phobias": char.phobias, "mythos": char.mythos
    }


@app.post("/api/characters")
def create_character(char_data: dict, current_user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    new_char = models.Character(user_id=current_user.id)
    new_char.name = str(char_data.get("name", "Новый персонаж"))
    db.add(new_char)
    db.commit()
    db.refresh(new_char)
    return {"id": new_char.id, "message": "Created"}


@app.put("/api/characters/{char_id}")
def update_character(char_id: int, char_data: dict, current_user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    char = db.query(models.Character).filter(models.Character.id == char_id,
                                             models.Character.user_id == current_user.id).first()
    if not char: raise HTTPException(status_code=404, detail="Character not found")

    char.name = str(char_data.get("name", ""))
    char.age = int(char_data.get("age", 30))
    char.occupation = str(char_data.get("occupation", ""))
    char.birthplace = str(char_data.get("birthplace", ""))
    char.avatar_url = str(char_data.get("avatar_url", ""))

    char.str_val = int(char_data.get("str_val", 50))
    char.con_val = int(char_data.get("con_val", 50))
    char.pow_val = int(char_data.get("pow_val", 50))
    char.dex_val = int(char_data.get("dex_val", 50))
    char.app_val = int(char_data.get("app_val", 50))
    char.siz_val = int(char_data.get("siz_val", 50))
    char.int_val = int(char_data.get("int_val", 50))
    char.edu_val = int(char_data.get("edu_val", 50))

    char.hp_current = int(char_data.get("hp_current", 10))
    char.sanity_current = int(char_data.get("sanity_current", 50))
    char.mp_current = int(char_data.get("mp_current", 10))
    char.luck = int(char_data.get("luck", 50))

    char.skills_json = json.dumps(char_data.get("skills", {}), ensure_ascii=False)

    char.ideology = str(char_data.get("ideology", ""))
    char.significant_people = str(char_data.get("significant_people", ""))
    char.meaningful_locations = str(char_data.get("meaningful_locations", ""))
    char.treasured_possessions = str(char_data.get("treasured_possessions", ""))
    char.traits = str(char_data.get("traits", ""))
    char.phobias = str(char_data.get("phobias", ""))
    char.mythos = str(char_data.get("mythos", ""))

    db.commit()
    return {"message": "Updated"}


@app.delete("/api/characters/{char_id}")
def delete_character(char_id: int, current_user: models.User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    char = db.query(models.Character).filter(models.Character.id == char_id,
                                             models.Character.user_id == current_user.id).first()
    if not char: raise HTTPException(status_code=404, detail="Character not found")
    db.delete(char)
    db.commit()
    return {"message": "Deleted"}


# --- УПРАВЛЕНИЕ КОМНАТАМИ ---
@app.post("/api/rooms")
def create_room(data: dict, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    while True:
        room_code = random.randint(100000, 999999)
        existing = db.query(models.Room).filter(models.Room.id == room_code).first()
        if not existing: break

    new_room = models.Room(id=room_code, name=data.get("name", "Новая комната"), master_id=current_user.id)
    db.add(new_room)
    db.commit()
    return {"room_id": new_room.id, "name": new_room.name}


@app.get("/api/rooms/my")
def get_my_rooms(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    rooms = db.query(models.Room).filter(models.Room.master_id == current_user.id).all()
    return [{"id": r.id, "name": r.name} for r in rooms]


@app.delete("/api/rooms/{room_id}")
def delete_room(room_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    room = db.query(models.Room).filter(models.Room.id == room_id, models.Room.master_id == current_user.id).first()
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    db.delete(room)
    db.commit()
    return {"message": "Room deleted"}


@app.get("/api/rooms/check/{room_id}")
def check_room(room_id: int, db: Session = Depends(get_db)):
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room: raise HTTPException(status_code=404, detail="Room not found")
    return {"id": room.id, "name": room.name}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    UPLOAD_DIR = "static/uploads"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = file.filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_location = f"{UPLOAD_DIR}/{filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": f"/static/uploads/{filename}"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)