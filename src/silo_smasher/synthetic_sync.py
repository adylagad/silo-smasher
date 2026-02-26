from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from airbyte_api import AirbyteAPI, models
from airbyte_api.api.getjob import GetJobRequest
from airbyte_api.api.getstreamproperties import GetStreamPropertiesRequest
from airbyte_api.api.listconnections import ListConnectionsRequest
from airbyte_api.api.listdestinations import ListDestinationsRequest
from airbyte_api.api.listsources import ListSourcesRequest
from airbyte_api.api.listworkspaces import ListWorkspacesRequest
from dotenv import load_dotenv


@dataclass
class Settings:
    server_url: str
    workspace_id: Optional[str]
    source_definition_id: Optional[str]
    destination_id: Optional[str]
    source_name: str
    source_count: int
    source_seed: int
    run_sync: bool
    wait: bool
    poll_seconds: int
    timeout_seconds: int


def _parse_args() -> Settings:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Create or reuse Airbyte synthetic source and optionally run a sync job."
    )
    parser.add_argument("--source-name", default="synthetic-catalog-source")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--run-sync",
        action="store_true",
        help="Create/reuse a connection and trigger a sync job (requires destination id).",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for sync job completion when --run-sync is set.",
    )
    parser.add_argument("--poll-seconds", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()

    return Settings(
        server_url=os.getenv("AIRBYTE_SERVER_URL", "http://localhost:8000/api/public/v1"),
        workspace_id=os.getenv("AIRBYTE_WORKSPACE_ID"),
        source_definition_id=os.getenv("AIRBYTE_SOURCE_DEFINITION_ID"),
        destination_id=os.getenv("AIRBYTE_DESTINATION_ID"),
        source_name=args.source_name,
        source_count=args.count,
        source_seed=args.seed,
        run_sync=args.run_sync,
        wait=args.wait,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.timeout_seconds,
    )


def _build_client() -> AirbyteAPI:
    server_url = os.getenv("AIRBYTE_SERVER_URL", "http://localhost:8000/api/public/v1")
    bearer_token = os.getenv("AIRBYTE_BEARER_TOKEN")
    username = os.getenv("AIRBYTE_USERNAME")
    password = os.getenv("AIRBYTE_PASSWORD")

    security = None
    if bearer_token:
        security = models.Security(bearer_auth=bearer_token)
    elif username and password:
        security = models.Security(
            basic_auth=models.SchemeBasicAuth(username=username, password=password)
        )

    if security:
        return AirbyteAPI(server_url=server_url, security=security)
    return AirbyteAPI(server_url=server_url)


def _require_ok(status_code: int, operation: str) -> None:
    if status_code >= 400:
        raise RuntimeError(f"{operation} failed with status code {status_code}")


def _pick_workspace_id(client: AirbyteAPI, workspace_id: Optional[str]) -> str:
    if workspace_id:
        return workspace_id
    resp = client.workspaces.list_workspaces(ListWorkspacesRequest(limit=20, offset=0))
    _require_ok(resp.status_code, "List workspaces")
    if not resp.workspaces_response or not resp.workspaces_response.data:
        raise RuntimeError("No Airbyte workspace found. Set AIRBYTE_WORKSPACE_ID explicitly.")
    return resp.workspaces_response.data[0].workspace_id


def _resolve_source_definition_id(source_definition_id: Optional[str]) -> str:
    if source_definition_id:
        return source_definition_id
    raise RuntimeError("AIRBYTE_SOURCE_DEFINITION_ID is required.")


def _list_sources(client: AirbyteAPI, workspace_id: str) -> Iterable[models.SourceResponse]:
    resp = client.sources.list_sources(
        ListSourcesRequest(limit=100, offset=0, workspace_ids=[workspace_id])
    )
    _require_ok(resp.status_code, "List sources")
    return resp.sources_response.data if resp.sources_response else []


def _ensure_source(
    client: AirbyteAPI,
    workspace_id: str,
    source_definition_id: Optional[str],
    source_name: str,
    count: int,
    seed: int,
) -> models.SourceResponse:
    for source in _list_sources(client, workspace_id):
        if source.name == source_name:
            print(f"Reusing existing source: {source.name} ({source.source_id})")
            return source

    resolved_definition_id = _resolve_source_definition_id(source_definition_id)
    source_request = models.SourceCreateRequest(
        name=source_name,
        workspace_id=workspace_id,
        definition_id=resolved_definition_id,
        configuration={
            "count": count,
            "seed": seed,
        },
    )
    create_resp = client.sources.create_source(source_request)
    _require_ok(create_resp.status_code, "Create source")
    if not create_resp.source_response:
        raise RuntimeError("Source creation did not return a source response.")
    print(
        "Created source:",
        f"{create_resp.source_response.name} ({create_resp.source_response.source_id})",
    )
    return create_resp.source_response


def _list_destinations(client: AirbyteAPI, workspace_id: str) -> Iterable[models.DestinationResponse]:
    resp = client.destinations.list_destinations(
        ListDestinationsRequest(limit=100, offset=0, workspace_ids=[workspace_id])
    )
    _require_ok(resp.status_code, "List destinations")
    return resp.destinations_response.data if resp.destinations_response else []


def _choose_sync_mode(
    modes: Optional[list[models.ConnectionSyncModeEnum]],
) -> models.ConnectionSyncModeEnum:
    if not modes:
        return models.ConnectionSyncModeEnum.FULL_REFRESH_APPEND
    preferred = [
        models.ConnectionSyncModeEnum.FULL_REFRESH_APPEND,
        models.ConnectionSyncModeEnum.FULL_REFRESH_OVERWRITE,
        models.ConnectionSyncModeEnum.INCREMENTAL_APPEND,
    ]
    for mode in preferred:
        if mode in modes:
            return mode
    return modes[0]


def _build_stream_configurations(
    client: AirbyteAPI, source_id: str, destination_id: str
) -> models.StreamConfigurationsInput:
    resp = client.streams.get_stream_properties(
        GetStreamPropertiesRequest(source_id=source_id, destination_id=destination_id)
    )
    _require_ok(resp.status_code, "Get stream properties")
    streams = resp.stream_properties_response or []
    if not streams:
        raise RuntimeError("No streams discovered for source/destination pair.")

    configs: list[models.StreamConfiguration] = []
    for stream in streams:
        if not stream.stream_name:
            continue
        configs.append(
            models.StreamConfiguration(
                name=stream.stream_name,
                namespace=stream.streamnamespace,
                sync_mode=_choose_sync_mode(stream.sync_modes),
            )
        )

    if not configs:
        raise RuntimeError("Unable to create stream configurations from discovered streams.")
    return models.StreamConfigurationsInput(streams=configs)


def _list_connections(client: AirbyteAPI, workspace_id: str) -> Iterable[models.ConnectionResponse]:
    resp = client.connections.list_connections(
        ListConnectionsRequest(limit=100, offset=0, workspace_ids=[workspace_id])
    )
    _require_ok(resp.status_code, "List connections")
    return resp.connections_response.data if resp.connections_response else []


def _ensure_connection(
    client: AirbyteAPI,
    workspace_id: str,
    source: models.SourceResponse,
    destination_id: str,
) -> models.ConnectionResponse:
    for connection in _list_connections(client, workspace_id):
        if connection.source_id == source.source_id and connection.destination_id == destination_id:
            print(f"Reusing existing connection: {connection.name} ({connection.connection_id})")
            return connection

    destination_ids = {d.destination_id for d in _list_destinations(client, workspace_id)}
    if destination_id not in destination_ids:
        raise RuntimeError(
            f"Destination id {destination_id} was not found in workspace {workspace_id}."
        )

    stream_configs = _build_stream_configurations(client, source.source_id, destination_id)
    create_request = models.ConnectionCreateRequest(
        destination_id=destination_id,
        source_id=source.source_id,
        configurations=stream_configs,
        name=f"{source.name}-to-destination",
        namespace_definition=models.NamespaceDefinitionEnum.SOURCE,
        schedule=models.AirbyteAPIConnectionSchedule(
            schedule_type=models.ScheduleTypeEnum.MANUAL
        ),
        status=models.ConnectionStatusEnum.ACTIVE,
    )
    resp = client.connections.create_connection(create_request)
    _require_ok(resp.status_code, "Create connection")
    if not resp.connection_response:
        raise RuntimeError("Connection creation did not return a connection response.")
    print(
        "Created connection:",
        f"{resp.connection_response.name} ({resp.connection_response.connection_id})",
    )
    return resp.connection_response


def _trigger_sync(client: AirbyteAPI, connection_id: str) -> models.JobResponse:
    resp = client.jobs.create_job(
        models.JobCreateRequest(
            connection_id=connection_id,
            job_type=models.JobTypeEnum.SYNC,
        )
    )
    _require_ok(resp.status_code, "Create sync job")
    if not resp.job_response:
        raise RuntimeError("Sync job creation did not return a job response.")
    print(f"Started sync job: {resp.job_response.job_id}")
    return resp.job_response


def _wait_for_job(
    client: AirbyteAPI, job_id: int, poll_seconds: int, timeout_seconds: int
) -> models.JobResponse:
    deadline = time.time() + timeout_seconds
    while True:
        resp = client.jobs.get_job(GetJobRequest(job_id=job_id))
        _require_ok(resp.status_code, "Get job")
        if not resp.job_response:
            raise RuntimeError(f"Job {job_id} response is empty.")
        status = resp.job_response.status
        print(f"Job {job_id} status: {status.value}")
        if status in (
            models.JobStatusEnum.SUCCEEDED,
            models.JobStatusEnum.FAILED,
            models.JobStatusEnum.CANCELLED,
            models.JobStatusEnum.INCOMPLETE,
        ):
            return resp.job_response
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for job {job_id}.")
        time.sleep(poll_seconds)


def main() -> None:
    settings = _parse_args()
    client = _build_client()
    workspace_id = _pick_workspace_id(client, settings.workspace_id)
    print(f"Using workspace: {workspace_id}")

    source = _ensure_source(
        client=client,
        workspace_id=workspace_id,
        source_definition_id=settings.source_definition_id,
        source_name=settings.source_name,
        count=settings.source_count,
        seed=settings.source_seed,
    )
    print(
        "Source is ready. Next:",
        "set AIRBYTE_DESTINATION_ID and run with --run-sync to pull data via a sync job.",
    )

    if not settings.run_sync:
        return

    destination_id = settings.destination_id
    if not destination_id:
        raise RuntimeError("AIRBYTE_DESTINATION_ID is required when --run-sync is set.")
    connection = _ensure_connection(
        client=client,
        workspace_id=workspace_id,
        source=source,
        destination_id=destination_id,
    )
    job = _trigger_sync(client, connection.connection_id)

    if settings.wait:
        final_job = _wait_for_job(
            client,
            job_id=job.job_id,
            poll_seconds=settings.poll_seconds,
            timeout_seconds=settings.timeout_seconds,
        )
        print(f"Final status for job {job.job_id}: {final_job.status.value}")


if __name__ == "__main__":
    main()
