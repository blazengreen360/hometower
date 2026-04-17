"""IPAM router — read-only derived views over Network + DeviceNetwork."""
import uuid

from fastapi import APIRouter, Depends
from sqlmodel import Session

from src.api.dependencies.rbac import require_role
from src.models.ipam import IpamNetworkDetailResponse, IpamNetworkListResponse
from src.models.types import Role
from src.services import ipam_service
from src.utils.db import get_session

router = APIRouter(prefix="/ipam", tags=["ipam"])


@router.get(
    "/networks",
    response_model=IpamNetworkListResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def list_ipam_networks(
    session: Session = Depends(get_session),
) -> IpamNetworkListResponse:
    """List IPAM summaries for all networks."""
    return ipam_service.list_networks(session)


@router.get(
    "/networks/{network_id}",
    response_model=IpamNetworkDetailResponse,
    dependencies=[Depends(require_role(Role.Reader))],
)
def get_ipam_network_detail(
    network_id: uuid.UUID,
    session: Session = Depends(get_session),
) -> IpamNetworkDetailResponse:
    """Return one network's detailed IPAM rendering payload."""
    return ipam_service.get_network_detail(network_id, session)
