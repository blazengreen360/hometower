"""Unit tests for enrichment behavior in src/services/device_service.py."""

import uuid
from unittest.mock import patch

from sqlmodel import Session

from src.models.custom_field import CustomField
from src.models.device import Device
from src.models.device_network import DeviceNetwork
from src.models.network import Network
from src.models.service import Service
from src.models.tag import DeviceTag, Tag
from src.models.types import DeviceType
from src.repositories import (
    custom_field_repository,
    network_repository,
    service_repository,
    tag_repository,
)
from src.services import device_service


class TestDeviceServiceEnrichment:
    def test_get_all_enriched_uses_batch_fetches_for_include_collections(
        self, session: Session
    ) -> None:
        suffix = str(uuid.uuid4())[:8]
        device = Device(name=f"batch-dev-{suffix}", type=DeviceType.Server)
        session.add(device)
        session.commit()
        session.refresh(device)

        tag = Tag(name=f"batch-tag-{suffix}", color="#123abc")
        session.add(tag)
        session.commit()
        session.refresh(tag)

        session.add(DeviceTag(device_id=device.id, tag_id=tag.id))
        session.add(CustomField(device_id=device.id, key="owner", value="qa"))
        session.add(Service(device_id=device.id, name="batch-svc"))
        session.commit()

        network = Network(
            name=f"batch-net-{suffix}",
            vlan_id=10,
            cidr="10.0.10.0/24",
            gateway="10.0.10.1",
            color="#3b82f6",
        )
        session.add(network)
        session.commit()
        session.refresh(network)

        session.add(
            DeviceNetwork(
                device_id=device.id,
                network_id=network.id,
                ip_address="10.0.10.10",
            )
        )
        session.commit()

        include = {"tags", "custom_fields", "services", "networks"}
        with patch.object(
            tag_repository,
            "get_by_device",
            side_effect=AssertionError("N+1 tag fetch should not be used"),
        ), patch.object(
            custom_field_repository,
            "get_by_device",
            side_effect=AssertionError("N+1 custom field fetch should not be used"),
        ), patch.object(
            service_repository,
            "get_by_device",
            side_effect=AssertionError("N+1 service fetch should not be used"),
        ), patch.object(
            network_repository,
            "get_by_device",
            side_effect=AssertionError("N+1 network fetch should not be used"),
        ):
            items, _ = device_service.get_all_enriched(
                session=session,
                page=1,
                limit=1000,
                include=include,
            )

        target = next((item for item in items if item.id == device.id), None)
        assert target is not None
        assert [t.name for t in target.tags] == [tag.name]
        assert [cf.key for cf in target.custom_fields] == ["owner"]
        assert [svc.name for svc in target.services] == ["batch-svc"]
        assert [net.name for net in target.networks] == [network.name]
        assert [net.ip_address for net in target.networks] == ["10.0.10.10"]
