# Code review checklist

## Correctness
- Does the code satisfy the acceptance scenarios?
- Are lifecycle transitions validated at the domain boundary?
- Are duplicates, retries, and rollback actions safe and idempotent?

## Design
- Are responsibilities separated between API, domain, and persistence?
- Are DTOs and domain models clearly defined?
- Is the solution extensible for future model scale and new environments?

## Quality
- Are tests deterministic and isolated?
- Are public interfaces documented and consistent?
- Are API error cases surfaced with clear details?

## Operations
- Does the change include relevant logging and health checks?
- Are packaging and deployment steps clear for the repo?
- Are any new dependencies or config values documented?
