# Privacy / PII review (BITE-07)

## Standing rule

Real workloads remain **blocked** until a human decides retention, PII handling, and publication boundaries.

## Exclusion rules (draft for human lock)

- No private conversations as fixtures
- No credentials, phone numbers, emails, or government IDs in bundled artifacts
- No undisclosed scraping of personal accounts
- Synthetic fixtures must not encode real person names

## Adapter enforcement

- `allow_network_fetch()` defaults to `False`
- Real adapter IDs are absent from the runtime registry until approval
- Config flags `allow_network` / `allow_paid_api` stay false (see `configs/default.toml`)

## Human decisions still open

- Whether any real log dumps may be stored under `seeds/`
- Redaction SOP for borderline fields
- Retention window and deletion owner
