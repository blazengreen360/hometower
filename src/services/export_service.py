"""Export service — assembles full database snapshot for JSON export (HT-012).

This module hides which repositories are called and how results are assembled.
"""
from datetime import datetime, timezone

from sqlmodel import Session

from src.domain.export import EXPORT_VERSION
from src.models.export_schema import (
    ExportSchema,
    ExportedConnection,
    ExportedCustomField,
    ExportedDevice,
    ExportedDeviceNetwork,
    ExportedDeviceTag,
    ExportedDiagramLayout,
    ExportedLocation,
    ExportedNetwork,
    ExportedService,
    ExportedServiceDependency,
    ExportedTag,
    ExportedTopology,
    ExportedUser,
    ExportedWorkspace,
)
from src.repositories import (
    connection_repository,
    custom_field_repository,
    device_repository,
    diagram_repository,
    location_repository,
    network_repository,
    service_repository,
    tag_repository,
    topology_repository,
    user_repository,
    workspace_repository,
)


def build_export_envelope(
    devices: list[ExportedDevice],
    connections: list[ExportedConnection],
    locations: list[ExportedLocation],
    tags: list[ExportedTag],
    device_tags: list[ExportedDeviceTag],
    custom_fields: list[ExportedCustomField],
    diagram_layouts: list[ExportedDiagramLayout],
    users: list[ExportedUser],
    networks: list[ExportedNetwork] | None = None,
    device_networks: list[ExportedDeviceNetwork] | None = None,
    services: list[ExportedService] | None = None,
    service_dependencies: list[ExportedServiceDependency] | None = None,
    workspaces: list[ExportedWorkspace] | None = None,
    topologies: list[ExportedTopology] | None = None,
) -> ExportSchema:
    """Build the canonical export envelope from export-schema models."""
    services_rows = services or []
    dependency_rows = service_dependencies or []
    workspace_rows = workspaces or []
    topology_rows = topologies or []
    network_rows = networks or []
    membership_rows = device_networks or []
    return ExportSchema(
        version=EXPORT_VERSION,
        exported_at=datetime.now(timezone.utc),
        devices=sorted(devices, key=lambda x: (x.created_at, str(x.id))),
        connections=sorted(connections, key=lambda x: (x.created_at, str(x.id))),
        locations=sorted(locations, key=lambda x: (x.created_at, str(x.id))),
        tags=sorted(tags, key=lambda x: (x.created_at, str(x.id))),
        device_tags=sorted(device_tags, key=lambda x: (str(x.device_id), str(x.tag_id))),
        networks=sorted(network_rows, key=lambda x: (x.created_at, str(x.id))),
        device_networks=sorted(
            membership_rows,
            key=lambda x: (str(x.device_id), str(x.network_id)),
        ),
        custom_fields=sorted(custom_fields, key=lambda x: (x.created_at, str(x.id))),
        services=sorted(services_rows, key=lambda x: (x.created_at, str(x.id))),
        service_dependencies=sorted(
            dependency_rows,
            key=lambda x: (str(x.service_id), str(x.depends_on_id)),
        ),
        workspaces=sorted(workspace_rows, key=lambda x: (x.created_at, str(x.id))),
        topologies=sorted(topology_rows, key=lambda x: (x.created_at, str(x.id))),
        diagram_layouts=sorted(diagram_layouts, key=lambda x: (x.created_at, str(x.id))),
        users=sorted(users, key=lambda x: (x.created_at, str(x.id))),
    )


def build_full_export(session: Session) -> ExportSchema:
    """Call get_all on every repository and build the export envelope.

    Returns an ExportSchema ready for serialisation.
    Empty tables yield empty lists — raises nothing.
    """
    devices = [
        ExportedDevice.model_validate(device.model_dump())
        for device in device_repository.get_all_for_export(session)
    ]
    connections = [
        ExportedConnection.model_validate(connection.model_dump())
        for connection in connection_repository.get_all_for_export(session)
    ]
    locations = [
        ExportedLocation.model_validate(location.model_dump())
        for location in location_repository.get_all(session)
    ]
    tags = [
        ExportedTag.model_validate(tag.model_dump())
        for tag in tag_repository.get_all(session)
    ]
    device_tags = [
        ExportedDeviceTag.model_validate(device_tag.model_dump())
        for device_tag in tag_repository.get_all_device_tags(session)
    ]
    networks = [
        ExportedNetwork.model_validate(network.model_dump())
        for network in network_repository.get_all_for_export(session)
    ]
    device_networks = [
        ExportedDeviceNetwork.model_validate(row.model_dump())
        for row in network_repository.get_all_device_networks(session)
    ]
    custom_fields = [
        ExportedCustomField.model_validate(custom_field.model_dump())
        for custom_field in custom_field_repository.get_all(session)
    ]
    services = [
        ExportedService.model_validate(service.model_dump())
        for service, _device_name in service_repository.get_all(session)
    ]
    service_dependencies = [
        ExportedServiceDependency(service_id=service_id, depends_on_id=depends_on_id)
        for service_id, depends_on_id in service_repository.get_all_dependency_edges(session)
    ]
    workspaces = [
        ExportedWorkspace.model_validate(workspace.model_dump())
        for workspace in workspace_repository.get_all_for_export(session)
    ]
    topologies = [
        ExportedTopology.model_validate(topology.model_dump())
        for topology in topology_repository.get_all_for_export(session)
    ]
    diagram_layouts = [
        ExportedDiagramLayout(
            id=layout.id,
            name=layout.name,
            cytoscape_json=layout.cytoscape_json if isinstance(layout.cytoscape_json, dict) else {},
            topology_id=layout.topology_id,
            version=layout.version,
            created_at=layout.created_at,
            updated_at=layout.updated_at,
        )
        for layout in diagram_repository.get_all_for_export(session)
    ]
    users = [
        ExportedUser.model_validate(user.model_dump())
        for user in user_repository.get_all(session)
    ]

    return build_export_envelope(
        devices=devices,
        connections=connections,
        locations=locations,
        tags=tags,
        device_tags=device_tags,
        networks=networks,
        device_networks=device_networks,
        custom_fields=custom_fields,
        diagram_layouts=diagram_layouts,
        users=users,
        services=services,
        service_dependencies=service_dependencies,
        workspaces=workspaces,
        topologies=topologies,
    )
