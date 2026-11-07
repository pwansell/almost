# The Studio renders everything; the Frame only shows Plates

The Frame is an old reMarkable 2 that runs on battery, is recharged about once a week, and wakes once a night. Custom software on the rM2 is fragile, because firmware updates break screen access. Each Event also needs AI-generated Artwork, which the tablet cannot produce. So a cloud Studio does all the work: it reads the Event Calendar, generates and caches Artwork, and renders finished Plates for the next 14 days. The Frame wakes, reports its battery level, downloads the Plates through a secret URL, shows today's Plate, and goes back to sleep.

## Considered Options

- **The Frame does everything**, calling the image API directly with a key stored on the tablet. Rejected: it puts the most code on the most fragile platform, and keeps the tablet awake longest.
- **The Studio makes only the Artwork, and the Frame composes the screen.** Rejected: drawing type and layout on the tablet would still need fragile on-device rendering.

## Consequences

- Getting through a period without Wi‑Fi comes from having Plates for 14 days ahead. The Studio bakes the Offline Mark into Plates 8–14, so the mark appears only after a week of failed fetches, with no extra logic on the Frame.
- The Low Battery Mark is baked in by the Studio, using the battery level reported at each fetch. The Charge Me Plate is the only Plate the Frame stores and chooses to show by itself.
- The Frame depends on a cloud service. If the Studio disappears, the Frame shows its last Plate, which by then carries the Offline Mark.
