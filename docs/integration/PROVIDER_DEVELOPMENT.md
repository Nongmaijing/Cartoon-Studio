# Provider Development

## Interfaces

`backend/app/providers/base.py` defines:

- `ProviderInfo`
- `ImageProvider`
- `VideoProvider`
- `AudioProvider`
- `EditingProvider`

Each provider declares:

- name and type
- capabilities
- availability
- input/output constraints
- resource estimate
- configuration
- notes

## Registry

`backend/app/providers/registry.py`:

- instantiates configured providers,
- applies defaults from `config.providers`,
- returns `ProviderInfo` status,
- checks live ComfyUI availability for ComfyUI providers,
- raises `ProviderError` when a provider is unavailable.

The production orchestrator and services request providers by type, never by concrete class.

## Adding a provider

1. Implement the appropriate interface.
2. Declare `ProviderInfo`.
3. Register the class in `PROVIDER_CLASSES`.
4. Add a seeded `provider_configs` row or update an existing row.
5. Add availability/config validation.
6. Add a test using a fake job/result.
7. Document capabilities and credentials.

## Cloud providers

- Cloud image provider (`providers/openai_image.py`) is disabled by default.
- It requires `OPENAI_API_KEY` and `ALLOW_CLOUD_GENERATION=true`.
- Private assets are not uploaded automatically.
- Cloud video is not implemented; the interface exists and a missing adapter is reported honestly.
- Never claim a cloud provider is active without credentials and a live test.

## Job model

Providers that submit asynchronous work return a job ID. The orchestrator persists it in `production_tasks.job_id` and polls `get_job_status`. Providers that are synchronous (Kokoro, FFmpeg queue) return a completed/queued status.
