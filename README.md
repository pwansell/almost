# Almost

An old reMarkable 2 turned into a framed e-ink picture that counts down the days to the next thing worth looking forward to.

Each night the Frame wakes for a moment, fetches the day's **Plate** (a finished picture: AI-generated Artwork, the number of days left and the Event's name), sets it as the tablet's sleep screen and goes back to sleep. It runs for weeks on a charge.

The words in **bold** are defined in [GLOSSARY.md](GLOSSARY.md).

## How it works

```
 Google Calendar ──► GitHub Actions (the Studio) ──► Cloudflare R2 ◄── Worker ◄── reMarkable 2 (the Frame)
  the Event Calendar   nightly: reads Events,          Plates for       secret     wakes 00:05 Melbourne,
                       makes Artwork with Gemini,      the next         URL        fetches, shows today's
                       renders 14 days of Plates       14 days                     Plate, sleeps
```

- **The Studio does all the work** ([ADR 0001](docs/adr/0001-studio-renders-everything.md)). The tablet never draws anything itself. It only shows images it has downloaded, so firmware quirks can't break the layout.
- **Rendering runs on GitHub Actions** ([ADR 0002](docs/adr/0002-studio-renders-on-github-actions.md)). Cloudflare's free plan has too little CPU to render, so it only stores and serves the Plates.
- **The Frame keeps 14 days of Plates.** If Wi-Fi is down it keeps working, and after a week without a fetch the Plates show the **Offline Mark**.
- **Battery:** the Frame reports its battery level at every check-in. The Studio adds a **Low Battery Mark** when it's low. When it's critically low, the Frame shows the **Charge Me Plate**. On the charger, the Frame checks every 30 minutes and shows a small **Charged Mark** once the battery is full.

## Adding Events

Every entry in the dedicated Google Calendar is an **Event**. One-off entries and entries that repeat yearly count. Any other repeat pattern is ignored, so a weekly reminder can't take over the Frame. Events are counted by their day in Melbourne time.

Two optional lines in an Event's description steer its Artwork:

```
art: a big sponge cake with candles and sprinkles, puppies
style: sumi-e
```

- **`art:`** (the **Art Hint**): words added to the image prompt next to the Event's title. If image generation isn't available, each word is also tried as an **Art Library** keyword (for example `beach`, `cruise`, `birthday`).
- **`style:`** (the **Style Request**): the **House Style** to use, either `sumi-e` (ink and wash) or `deco` (Art Deco). The wording can be loose, such as `ink and wash` or `Art Deco`. Without this line, or if it names neither style, the Event gets one at random, and keeps it.

Artwork is generated once per Event and reused every year after that. Changing the title, the `art:` line or the `style:` line makes new Artwork. Generations are capped each month (see [`studio/settings.toml`](studio/settings.toml)). Past the cap, the Art Library is used, and failing that the **Default Artwork**.

## Repository layout

| Path | What it is |
|---|---|
| [`studio/`](studio) | The Studio: Python that reads the calendar, makes Artwork and renders Plates. Settings are in [`settings.toml`](studio/settings.toml). |
| [`worker/`](worker) | The Cloudflare Worker in front of the R2 bucket. It serves Plates to the Frame, records its battery level and Wi-Fi address, and serves the **Preview** page. |
| [`frame/`](frame) | The Frame side: a BusyBox shell script plus systemd units for the tablet, and `install.sh` to copy them over SSH. |
| [`.github/workflows/studio.yml`](.github/workflows/studio.yml) | The nightly render (22:00 Melbourne time, or 21:00 in winter), which can also be run by hand. |
| [`scripts/setup-studio.sh`](scripts/setup-studio.sh) | A step-by-step wizard that sets up every account and secret. |
| [`docs/adr/`](docs/adr) | Architecture decisions. |
| [`prototypes/`](prototypes) | Early experiments with Plate layout. |

## Setting up

You need: a reMarkable 2 with SSH access, a Google account, a Cloudflare account, a GitHub account with the [`gh`](https://cli.github.com) CLI, a Gemini API key, and [`uv`](https://docs.astral.sh/uv/) and Node.js on your computer.

1. **Prepare the tablet.** Turn off automatic updates. The Frame is tested on firmware 3.22.0.64. Install an SSH key on it as `~/.ssh/id_ed25519_almost`.
2. **Run the wizard:**
   ```sh
   scripts/setup-studio.sh
   ```
   It walks you through 10 stages:
   1. The calendar's secret iCal address.
   2. The Gemini key.
   3. Cloudflare login.
   4. The R2 bucket.
   5. An R2 access key for GitHub Actions.
   6. A GitHub token so the Preview can start renders.
   7. Deploying the Worker.
   8. The Art Library (optional).
   9. The first render.
   10. Installing the Frame side on the tablet over USB.

   Values are saved to `.env`, which is git-ignored, and to GitHub Actions secrets. The wizard can be re-run safely.
3. **Optional: Idle Artwork.** Upload an image with no text to `idle/idle.png` in the bucket. The Frame shows it when there are no upcoming Events.

To reinstall the Frame side later: `frame/install.sh [host]`. The host defaults to `10.11.99.1`, the tablet's address over USB.

## Day to day

- **See upcoming Plates:** open the Preview page at `https://<worker>/preview/<PREVIEW_TOKEN>`. It starts a fresh render, and the new Plates appear a minute or two later.
- **Render now, without waiting for the nightly run:** `gh workflow run studio.yml`.
- **Make the Frame fetch now:** connect over SSH (USB, or Wi-Fi once it's mounted), then run `/home/root/almost/almost.sh show`. The Frame records its Wi-Fi address in R2 at `state/frame-ip.json`.
- **Logs:** the Frame logs to `/home/root/almost/almost.log`. The workflow logs are public, so the Studio logs only counts and statuses, never Event names or hints.
- **Test mode:** put a number of seconds in `/home/root/almost/test-interval` on the tablet. The Frame then wakes that often and cycles through every Plate. Delete the file to go back to nightly wakes.

## Development

```sh
cd studio
uv run pytest                                                          # tests
uv run python -m almost_studio render --local dev/out --ics dev/sample.ics   # render Plates locally from a sample calendar
```

`--today YYYY-MM-DD` renders as if it were another day. Without `GEMINI_API_KEY`, a local render uses the Art Library or blank Artwork in place of generated images.

The Worker:

```sh
cd worker
npm install
npx wrangler dev      # run locally
npx wrangler deploy   # deploy
```
