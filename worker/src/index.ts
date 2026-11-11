// Almost: the Worker in front of the Studio's R2 bucket.
//
//   GET /frame/<FRAME_TOKEN>/manifest.txt?battery=NN&ip=A.B.C.D  Frame's nightly check-in (or .json)
//   GET /frame/<FRAME_TOKEN>/<YYYY-MM-DD|charge-me>.png  a Plate
//   GET /preview/<PREVIEW_TOKEN>                         the Preview page (starts a render)
//   GET /preview/<PREVIEW_TOKEN>/manifest.json           for the page to poll
//   GET /preview/<PREVIEW_TOKEN>/<file>.png              a Plate, for the page
//
// Anything else is a bare 404, so the tokens can't be probed.

export interface Env {
  BUCKET: R2Bucket;
  FRAME_TOKEN: string;
  PREVIEW_TOKEN: string;
  GITHUB_TOKEN: string;
  GITHUB_REPO: string;
  GITHUB_WORKFLOW: string;
}

const PLATE = /^(\d{4}-\d{2}-\d{2}(-charged)?|charge-me)\.png$/;
const DISPATCH_GAP_MS = 3 * 60 * 1000;

const notFound = () => new Response("Not found", { status: 404 });

function sameToken(given: string, expected: string): boolean {
  if (!expected || given.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < given.length; i++) diff |= given.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}

async function object(env: Env, key: string, type: string): Promise<Response> {
  const obj = await env.BUCKET.get(key);
  if (!obj) return notFound();
  return new Response(obj.body, {
    headers: { "content-type": type, "cache-control": "no-store", etag: obj.httpEtag },
  });
}

async function recordBattery(env: Env, raw: string | null): Promise<void> {
  const percent = Number(raw);
  if (raw === null || !Number.isInteger(percent) || percent < 0 || percent > 100) return;
  await env.BUCKET.put("state/battery.json", JSON.stringify({ percent, at: new Date().toISOString() }), {
    httpMetadata: { contentType: "application/json" },
  });
}

// The Frame's Wi-Fi address, so it can be reached over SSH once mounted.
async function recordAddress(env: Env, raw: string | null): Promise<void> {
  if (!raw || !/^\d{1,3}(\.\d{1,3}){3}$/.test(raw)) return;
  await env.BUCKET.put("state/frame-ip.json", JSON.stringify({ ip: raw, at: new Date().toISOString() }), {
    httpMetadata: { contentType: "application/json" },
  });
}

async function startRender(env: Env): Promise<"started" | "recent" | "failed"> {
  const last = await env.BUCKET.get("state/last-dispatch.json");
  if (last) {
    const { at } = (await last.json()) as { at: string };
    if (Date.now() - Date.parse(at) < DISPATCH_GAP_MS) return "recent";
  }
  const r = await fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/${env.GITHUB_WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${env.GITHUB_TOKEN}`,
        accept: "application/vnd.github+json",
        "x-github-api-version": "2022-11-28",
        "user-agent": "almost-worker",
      },
      body: JSON.stringify({ ref: "main" }),
    },
  );
  if (!r.ok) return "failed";
  await env.BUCKET.put("state/last-dispatch.json", JSON.stringify({ at: new Date().toISOString() }));
  return "started";
}

export default {
  async scheduled(_event: ScheduledController, env: Env): Promise<void> {
    if ((await startRender(env)) === "failed") throw new Error("nightly render dispatch failed");
  },

  async fetch(request: Request, env: Env): Promise<Response> {
    if (request.method !== "GET") return notFound();
    const url = new URL(request.url);
    const [area, token, file, ...rest] = url.pathname.split("/").filter(Boolean);
    if (rest.length) return notFound();

    if (area === "frame" && sameToken(token ?? "", env.FRAME_TOKEN)) {
      if (file === "manifest.json" || file === "manifest.txt") {
        await recordBattery(env, url.searchParams.get("battery"));
        await recordAddress(env, url.searchParams.get("ip"));
        return object(env, `plates/${file}`, file.endsWith(".txt") ? "text/plain" : "application/json");
      }
      if (file && PLATE.test(file)) return object(env, `plates/${file}`, "image/png");
      return notFound();
    }

    if (area === "preview" && sameToken(token ?? "", env.PREVIEW_TOKEN)) {
      if (!file) {
        const status = await startRender(env);
        return new Response(previewPage(status), {
          headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
        });
      }
      if (file === "manifest.json") return object(env, "plates/manifest.json", "application/json");
      if (PLATE.test(file)) return object(env, `plates/${file}`, "image/png");
      return notFound();
    }

    return notFound();
  },
} satisfies ExportedHandler<Env>;

function previewPage(status: "started" | "recent" | "failed"): string {
  const note = {
    started: "Rendering fresh Plates from the calendar. This page updates by itself in a minute or two.",
    recent: "A render started in the last few minutes. This page updates by itself when it finishes.",
    failed: "Couldn't start a fresh render; showing the latest Plates.",
  }[status];
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Almost Preview</title>
<style>
  :root { --bg: #f6f4ef; --fg: #1d1b18; --muted: #6d675e; --card: #fff; --rule: #d9d4ca; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #171614; --fg: #ece8e0; --muted: #a39c90; --card: #222; --rule: #3a3732; }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--fg);
         font: 16px/1.5 "Iowan Old Style", "Palatino Linotype", Georgia, serif; }
  main { max-width: 1100px; margin: 0 auto; padding: 32px 16px 64px; }
  h1 { font-weight: 400; letter-spacing: .2em; text-transform: uppercase; font-size: 1.4rem; margin: 0 0 4px; }
  .note { color: var(--muted); font-style: italic; margin: 0 0 4px; }
  .stamp { color: var(--muted); font-size: .85rem; margin: 0 0 24px; }
  ol { list-style: none; padding: 0; margin: 0; display: grid; gap: 20px;
       grid-template-columns: repeat(auto-fill, minmax(min(100%, 220px), 1fr)); }
  li { background: var(--card); border: 1px solid var(--rule); border-radius: 6px; padding: 10px; }
  li img { display: block; width: 100%; height: auto; aspect-ratio: 1404 / 1872; background: #fff; }
  li span { display: block; text-align: center; margin-top: 8px; font-size: .9rem; color: var(--muted); }
  li:first-child { outline: 2px solid var(--fg); outline-offset: 2px; }
</style>
</head>
<body>
<main>
  <h1>Almost</h1>
  <p class="note">${note}</p>
  <p class="stamp" id="stamp"></p>
  <ol id="plates"></ol>
</main>
<script>
  const base = location.pathname.replace(/\\/$/, "");
  let shown = null;
  const fmt = (iso) => new Date(iso).toLocaleString("en-AU", { dateStyle: "medium", timeStyle: "short" });
  const label = (file) => file === "charge-me.png" ? "Charge Me"
    : new Date(file.slice(0, 10) + "T12:00:00").toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "short" });
  async function refresh() {
    try {
      const r = await fetch(base + "/manifest.json", { cache: "no-store" });
      if (!r.ok) return;
      const m = await r.json();
      if (m.generated_at === shown) return;
      shown = m.generated_at;
      document.getElementById("stamp").textContent = "Rendered " + fmt(m.generated_at);
      // Charged copies differ only by their corner mark; show the first as a sample.
      const charged = m.plates.filter((p) => p.file.endsWith("-charged.png")).slice(0, 1);
      const files = [...m.plates.filter((p) => !p.file.endsWith("-charged.png")), ...charged, m.charge_me].filter(Boolean);
      document.getElementById("plates").replaceChildren(...files.map((p) => {
        const li = document.createElement("li");
        const img = document.createElement("img");
        img.src = base + "/" + p.file + "?v=" + p.sha256.slice(0, 12);
        img.alt = label(p.file);
        img.loading = "lazy";
        const span = document.createElement("span");
        span.textContent = label(p.file);
        li.append(img, span);
        return li;
      }));
    } catch {}
  }
  refresh();
  setInterval(refresh, 15000);
</script>
</body>
</html>`;
}
