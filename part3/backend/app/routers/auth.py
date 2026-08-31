from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app import crud, schemas, auth, models

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post(
    "/login",
    response_model=schemas.Token,
    responses={
        200: {"description": "Successful authentication with JWT bearer token"},
        400: {"description": "Missing or empty username / password"},
        401: {"description": "Incorrect username or password"}
    }
)
def login(login_req: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with username and password, returning JWT access token and profile info."""
    username = (login_req.username or "").strip()
    password = (login_req.password or "").strip()

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password cannot be empty."
        )

    user = crud.get_user_by_username(db, username)
    if not user or not auth.verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password. Please verify your credentials or register a new patient account."
        )
    
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    
    full_name = user.username
    if user.patient_id:
        p = crud.get_patient(db, user.patient_id)
        if p:
            full_name = p.name
    elif user.doctor_id:
        doc = db.query(models.Doctor).filter(models.Doctor.doctor_id == user.doctor_id).first()
        if doc:
            full_name = doc.name

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "full_name": full_name,
        "patient_id": user.patient_id,
        "doctor_id": user.doctor_id,
        "pharmacist_id": user.pharmacist_id
    }
