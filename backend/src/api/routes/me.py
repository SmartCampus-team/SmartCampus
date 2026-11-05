from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.api.deps import get_current_user
from src.database import get_db
from src.models.user import NotificationChannel, Role, User
from src.services import profile_service
from src.services.common import ServiceError
from src.services.profile_service import ProfileChanges

router = APIRouter(prefix="/api/me", tags=["profile"])

CurrentUser = Annotated[User, Depends(get_current_user)]
Db = Annotated[Session, Depends(get_db)]


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    phone: str | None
    notification_channel: NotificationChannel
    has_photo: bool


class ProfileUpdate(BaseModel):
    """Seuls les champs envoyés sont modifiés ; l'e-mail et le rôle ne font pas partie du profil."""

    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    # Chiffres, espaces, points, tirets et + initial : 06 12 34 56 78, +212 6 12 34 56 78 ; "" l'efface
    phone: str | None = Field(default=None, max_length=20, pattern=r"^\s*(\+?[0-9][0-9 .-]{5,18})?\s*$")
    notification_channel: NotificationChannel | None = None


def to_out(user: User) -> ProfileOut:
    return ProfileOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        phone=user.phone,
        notification_channel=user.notification_channel,
        has_photo=user.photo_type is not None,
    )


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=ProfileOut)
def get_profile(user: CurrentUser) -> ProfileOut:
    return to_out(user)


@router.patch("", response_model=ProfileOut)
def update_profile(body: ProfileUpdate, request: Request, user: CurrentUser, db: Db) -> ProfileOut:
    """Nom, téléphone et préférences de notification ; l'e-mail et le rôle restent en lecture seule."""
    changes = ProfileChanges(**body.model_dump(exclude_unset=True, exclude_none=True))
    profile_service.update_profile(db, user, changes, client_ip(request))
    return to_out(user)


@router.get("/photo")
def get_photo(user: CurrentUser) -> Response:
    """Photo servie seulement à son propriétaire connecté, jamais par une adresse publique."""
    content, media_type = profile_service.get_photo(user)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.put(
    "/photo",
    response_model=ProfileOut,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "image/png": {"schema": {"type": "string", "format": "binary"}},
                "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
            },
        }
    },
)
async def put_photo(request: Request, user: CurrentUser, db: Db) -> ProfileOut:
    """Le corps de la requête est l'image elle-même (PNG ou JPEG, 2 Mo au plus)."""
    # Refus avant lecture si la taille annoncée dépasse déjà la limite
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > profile_service.MAX_PHOTO_BYTES:
        raise ServiceError(413, profile_service.PHOTO_TOO_LARGE)
    content = await request.body()
    profile_service.set_photo(db, user, content, request.headers.get("content-type"), client_ip(request))
    return to_out(user)


@router.delete("/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(request: Request, user: CurrentUser, db: Db) -> Response:
    profile_service.delete_photo(db, user, client_ip(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
