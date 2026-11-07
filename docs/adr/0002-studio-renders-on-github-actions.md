---
status: accepted
---

# The Studio renders on GitHub Actions; Cloudflare only stores and serves

ADR 0001 put the whole Studio on Cloudflare, but the free Workers plan allows only 10 ms of CPU per request or cron run. That is far too little to decode Artwork, typeset, dither and encode a Plate, and the paid plan costs US$5 a month. So rendering runs in a GitHub Actions workflow, nightly and on demand. The workflow uses the Python renderer already proven on the Frame's screen, and writes the Plates to a private Cloudflare R2 bucket. A tiny free Worker sits in front of the bucket: it serves Plates to the Frame through its secret URL, records the battery level the Frame reports, and serves the Preview.

## Consequences

- The Preview is no longer instant. Opening it starts a workflow run, and fresh Plates appear 1–2 minutes later.
- The repository is public, so the workflow's logs are too. The Studio must never log Event names, Art Hints, the calendar URL or anything else private, only counts and statuses.
- Rendering depends on GitHub as well as Cloudflare. If GitHub is down, the Frame keeps showing the Plates already in R2, and the Offline Mark appears on schedule.
