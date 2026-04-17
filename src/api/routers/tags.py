"""Tags router — CRUD endpoints for the Tag entity (HT-006)."""
import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.tag import TagCreate, TagResponse, TagUpdate, TagWithCountResponse
from src.models.types import Role
from src.services import tag_service
from src.utils.db import get_session

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get(
    "/",
    response_model=list[TagWithCountResponse],
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_tags(
    session: Session = Depends(get_session),
) -> list[TagWithCountResponse]:
    """Return all tags with device counts. Requires Reader role."""
    return tag_service.get_all(session)


@router.post(
    "/",
    status_code=201,
    response_model=TagResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def create_tag(
    data: TagCreate,
    session: Session = Depends(get_session),
) -> TagResponse:
    """Create a new tag. Requires Contributor role. Returns 409 on duplicate name."""
    tag = tag_service.create(data, session)
    return TagResponse.model_validate(tag.model_dump())


@router.get(
    "/{tag_id}",
    response_model=TagResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_tag(
    tag_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> TagResponse:
    """Get a tag by ID. Requires Reader role."""
    tag = tag_service.get_by_id(tag_id, session)
    return TagResponse.model_validate(tag.model_dump())


@router.patch(
    "/{tag_id}",
    response_model=TagResponse,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def update_tag(
    tag_id: uuid.UUID,
    data: TagUpdate,
    session: Session = Depends(get_session),
) -> TagResponse:
    """Partially update a tag. Requires Contributor role. Returns 409 on duplicate name."""
    tag = tag_service.update(tag_id, data, session)
    return TagResponse.model_validate(tag.model_dump())


@router.delete(
    "/{tag_id}",
    status_code=204,
    dependencies=[Depends(require_role(Role.Contributor))],
)
def delete_tag(
    tag_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> None:
    """Delete a tag. Requires Contributor role. DB CASCADE removes all device associations."""
    tag_service.delete(tag_id, session)
