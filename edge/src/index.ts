// Edge service for the council news bot.
//
// Serves, from Cloudflare's edge, two read-only views of the posts the bot
// has already published:
//   - Bluesky custom feeds (a feed generator): one feed per group of councils
//     in config/feeds.json.
//   - RSS: every region feed, every council, every state, and all of Australia.
//
// The bot pushes newly posted stories to POST /ingest every few minutes. The
// edge keeps its own copy (D1), so feeds and RSS keep serving if the host
// running the bot is down; they simply stop gaining new items.
import data from "./data.json";
import { SCHEMA } from "./schema";
import {
  type Feed, type Post, STATES, STATE_NAMES, clampLimit, cleanPost, decodeCursor,
  didDocument, encodeCursor, feedIdFromUri, feedUri, renderOpml, renderRss, wantsFeedPage, renderFeedPage, renderManifest, PAGE_CSS,
  classifyClient, hashId, viewerDid, cacheKey,
} from "./lib";
import { ICON_SVG, ICON_180_PNG, ICON_192_PNG, ICON_512_PNG } from "./icons";

type Council = { id: string; name: string; state: string; news_url: string };
type Env = {
  DB: D1Database;
  HOSTNAME: string; // e.g. lgnews.jonathonmarsden.com
  PUBLISHER_DID: string; // DID of the account that publishes the feed records
  INGEST_TOKEN: string; // shared with the bot; secret
  USAGE?: AnalyticsEngineDataset; // anonymous usage counts (see recordUsage)
};

const FEEDS: Feed[] = (data as any).feeds;
const COUNCILS: Record<string, Council> = (data as any).councils;
const FEED_BY_ID = new Map(FEEDS.map((f) => [f.id, f]));
const RSS_ITEMS = 50;
const SKELETON_WINDOW_DAYS = 14;
const RSS_MAX_AGE = 600; // seconds
const SITE = "https://lgnews.jonathonmarsden.com";

const json = (body: unknown, status = 200, extra: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), {
    status, headers: { "content-type": "application/json; charset=utf-8", ...extra },
  });
const xrpcError = (error: string, message: string, status = 400) => json({ error, message }, status);

export default {
  async fetch(req: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;
    try {
      if (path === "/.well-known/did.json") return json(didDocument(env.HOSTNAME));
      if (path === "/xrpc/app.bsky.feed.describeFeedGenerator") {
        return json({
          did: `did:web:${env.HOSTNAME}`,
          feeds: FEEDS.map((f) => ({ uri: feedUri(env.PUBLISHER_DID, f.id) })),
        });
      }
      if (path === "/xrpc/app.bsky.feed.getFeedSkeleton") {
        ctx.waitUntil(recordUsage(req, url, env, "feed"));
        return await cached(req, ctx, false, () => skeleton(url, env));
      }
      if (path === "/ingest") return await ingest(req, env);
      if (path === "/edge/health") return await health(env);
      if (path === "/rss" || path.startsWith("/rss/")) {
        if (req.method !== "GET" && req.method !== "HEAD") return new Response("method not allowed", { status: 405 });
        const icon = iconResponse(path);
        if (icon) return icon;
        if (url.searchParams.get("view") === "manifest") return manifest(url, env);
        const page = wantsFeedPage(req.headers, url.searchParams.get("view"));
        ctx.waitUntil(recordUsage(req, url, env, page ? "page" : "rss"));
        const res = await cached(req, ctx, page, () => rss(url, env, page));
        // Browsers get a readable page, readers get RSS, from the same address.
        const out = new Response(res.body, res);
        out.headers.set("vary", "Sec-Fetch-Dest, Sec-Fetch-Mode");
        return out;
      }
      return new Response("not found", { status: 404 });
    } catch (e: any) {
      console.error(path, e?.stack || e);
      return path.startsWith("/xrpc/") ? xrpcError("InternalServerError", "internal error", 500)
        : new Response("internal error", { status: 500 });
    }
  },
};

// ---- Bluesky feed skeleton -------------------------------------------------

async function skeleton(url: URL, env: Env): Promise<Response> {
  const feedId = feedIdFromUri(url.searchParams.get("feed") || "", env.PUBLISHER_DID);
  const feed = feedId ? FEED_BY_ID.get(feedId) : undefined;
  if (!feed) return xrpcError("UnknownFeed", "Unknown feed");
  const limit = clampLimit(url.searchParams.get("limit"));
  const rawCursor = url.searchParams.get("cursor");
  const cur = decodeCursor(rawCursor);
  if (rawCursor && !cur) return xrpcError("InvalidRequest", "Malformed cursor");

  // Read only the last SKELETON_WINDOW_DAYS before the cursor (or now) first: a
  // page of a busy feed is almost always in there, and it reads ~5x fewer rows
  // than scanning every member council's history. Quiet feeds that don't fill a
  // page fall back to the unbounded query, which is cheap for them anyway.
  const anchor = cur ? Date.parse(cur.postedAt) : Date.now();
  const since = new Date(anchor - SKELETON_WINDOW_DAYS * 86400e3).toISOString().replace(/\.\d{3}Z$/, "Z");
  const page = (windowed: boolean) => {
    const where = ["uri IS NOT NULL", "council_id IN (SELECT value FROM json_each(?1))"];
    const args: unknown[] = [JSON.stringify(feed.council_ids)];
    if (cur) { where.push(`(posted_at < ?2 OR (posted_at = ?2 AND uri < ?3))`); args.push(cur.postedAt, cur.uri); }
    if (windowed) { where.push(`posted_at >= ?${args.length + 1}`); args.push(since); }
    args.push(limit);
    return env.DB.prepare(`SELECT uri, posted_at FROM posts WHERE ${where.join(" AND ")}
      ORDER BY posted_at DESC, uri DESC LIMIT ?${args.length}`).bind(...args).all<{ uri: string; posted_at: string }>();
  };
  let { results } = await page(true);
  if (results.length < limit) ({ results } = await page(false));

  const last = results.length === limit ? results[results.length - 1] : null;
  return json(
    { feed: results.map((r) => ({ post: r.uri })), ...(last ? { cursor: encodeCursor(last.posted_at, last.uri) } : {}) },
    200, { "cache-control": "public, max-age=60" },
  );
}

// ---- RSS -------------------------------------------------------------------

type Resolved = { ch: { title: string; description: string; link: string }; where: string; arg: string | null };

/** Which feed an /rss/... address names, and how to select its posts. */
function resolveChannel(path: string): Resolved | null {
  let m: RegExpExecArray | null;
  let where = "", arg: string | null = null, ch: { title: string; description: string; link: string } | null = null;
  if (path === "/rss/all.xml") {
    ch = { title: "Australian council news", description: "News from every Australian council the bot follows, relayed from each council's own news page.", link: SITE };
  } else if ((m = /^\/rss\/state\/([a-z]+)\.xml$/.exec(path)) && (STATES as readonly string[]).includes(m[1])) {
    where = "WHERE state = ?1"; arg = m[1];
    ch = { title: `${STATE_NAMES[m[1]]} council news`, description: `News from every council in ${STATE_NAMES[m[1]]}, relayed from each council's own news page.`, link: `${SITE}/${m[1]}` };
  } else if ((m = /^\/rss\/council\/([^/]{1,120})\.xml$/.exec(path)) && Object.hasOwn(COUNCILS, safeDecode(m[1]))) {
    // Ids are slugs, but one contains "&", so links percent-encode the id.
    const c = COUNCILS[safeDecode(m[1])];
    where = "WHERE council_id = ?1"; arg = c.id;
    ch = { title: `${c.name} news`, description: `News from ${c.name}, relayed from its own news page.`, link: c.news_url };
  } else if ((m = /^\/rss\/([a-z0-9-]{1,15})\.xml$/.exec(path)) && FEED_BY_ID.has(m[1])) {
    const f = FEED_BY_ID.get(m[1])!;
    where = "WHERE council_id IN (SELECT value FROM json_each(?1))"; arg = JSON.stringify(f.council_ids);
    ch = { title: `${f.name} council news`, description: f.description, link: SITE };
  }
  return ch ? { ch, where, arg } : null;
}

async function rss(url: URL, env: Env, page = false): Promise<Response> {
  const path = url.pathname.replace(/\/+$/, "");
  const self = `https://${env.HOSTNAME}${path}`;
  if (path === "/rss" ) return index(env);
  if (path === "/rss/feeds.opml") return opml(env);
  const r = resolveChannel(path);
  if (!r) return new Response("not found", { status: 404 });
  const { ch, where, arg } = r;

  const stmt = env.DB.prepare(
    `SELECT url, uri, council_id, council_name, state, title, excerpt, published_at, posted_at
       FROM posts ${where} ORDER BY posted_at DESC LIMIT ${RSS_ITEMS}`,
  );
  const { results } = await (arg === null ? stmt : stmt.bind(arg)).all<Post>();
  if (page) {
    return new Response(renderFeedPage({ ...ch, selfUrl: self }, results.slice(0, 20), SITE), {
      headers: { "content-type": "text/html; charset=utf-8", "cache-control": `public, max-age=${RSS_MAX_AGE}` },
    });
  }
  return new Response(renderRss({ ...ch, selfUrl: self }, results), {
    headers: { "content-type": "application/rss+xml; charset=utf-8", "cache-control": `public, max-age=${RSS_MAX_AGE}` },
  });
}

function opml(env: Env): Response {
  const base = `https://${env.HOSTNAME}/rss`;
  const entries = [
    { title: "All of Australia", xmlUrl: `${base}/all.xml`, group: "Australia" },
    ...STATES.map((s) => ({ title: STATE_NAMES[s], xmlUrl: `${base}/state/${s}.xml`, group: "States and territories" })),
    ...FEEDS.map((f) => ({ title: f.name, xmlUrl: `${base}/${f.id}.xml`, group: `Regions: ${f.state}` })),
    ...Object.values(COUNCILS).sort((a, b) => a.state.localeCompare(b.state) || a.name.localeCompare(b.name))
      .map((c) => ({ title: c.name, xmlUrl: `${base}/council/${encodeURIComponent(c.id)}.xml`, group: `Councils: ${c.state.toUpperCase()}` })),
  ];
  return new Response(renderOpml("Australian council news", entries), {
    headers: { "content-type": "text/x-opml; charset=utf-8", "cache-control": `public, max-age=${RSS_MAX_AGE}` },
  });
}

function index(env: Env): Response {
  const esc = (s: string) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]!));
  const chip = (href: string, text: string, cls = "") => `<li><a${cls ? ` class="${cls}"` : ""} href="${href}">${esc(text)}</a></li>`;
  const byState = (st: string) => FEEDS.filter((f) => f.state.toLowerCase() === st);
  const councils = (st: string) => Object.values(COUNCILS).filter((c) => c.state === st).sort((a, b) => a.name.localeCompare(b.name));
  const sections = STATES.map((st) => `
<section class="st"><h2>${esc(STATE_NAMES[st])}</h2>
  <ul class="chips">${chip(`/rss/state/${st}.xml`, `All of ${STATE_NAMES[st]}`, "all")}${byState(st).map((f) => chip(`/rss/${f.id}.xml`, f.name)).join("")}</ul>
  <details><summary>${st === "act" ? "Each source" : "Each council"} (${councils(st).length})</summary><ul class="cl">${councils(st).map((c) => `<li><a href="/rss/council/${encodeURIComponent(c.id)}.xml">${esc(c.name)}</a></li>`).join("")}</ul></details>
</section>`).join("");
  const html = `<!doctype html><html lang="en-AU"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RSS feeds · Local Government News</title>
<meta name="description" content="RSS feeds for every Australian council, region and state.">
<link rel="icon" href="/rss/icon.svg" type="image/svg+xml">
<style>${PAGE_CSS}</style></head><body><main>
<a class="top" href="${SITE}">Local Government News</a>
<h1>RSS feeds</h1>
<p class="lead">News from every Australian council, relayed from each council's own news page. Every item links to the original story.</p>
<section class="box"><h2>New to RSS?</h2>
<p>Open any feed below: it shows the latest stories and how to get them by email, in Teams or Slack, or in a feed reader. Or subscribe to <a href="/rss/all.xml">all of Australia</a>, or import <a href="/rss/feeds.opml">every feed</a> into your reader at once.</p></section>
${sections}
<footer><a href="${SITE}">Back to the news site</a></footer>
</main></body></html>`;
  return new Response(html, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": `public, max-age=${RSS_MAX_AGE}` } });
}

async function cached(req: Request, ctx: ExecutionContext, page: boolean, make: () => Promise<Response> | Response): Promise<Response> {
  const cache = (caches as any).default as Cache;
  // Only the parameters that change the answer go into the key (see cacheKey):
  // the readable page and the RSS share a URL, so the page gets its own key.
  const key = new Request(cacheKey(new URL(req.url), page), { method: "GET" });
  const hit = await cache.match(key);
  if (hit) return hit;
  const res = await make();
  if (res.ok) ctx.waitUntil(cache.put(key, res.clone()));
  return res;
}

// ---- Usage counts ----------------------------------------------------------
// One Analytics Engine data point per feed or RSS request, written after the
// response so it never slows or breaks one. Recorded before the cache, so cached
// answers are counted too. Fields (query with the Analytics Engine SQL API):
//   index1  kind: feed (Bluesky), rss (reader), page (browser view of a feed)
//   blob1   which feed: a feed id, or an /rss/... path; "unknown" for anything else
//   blob2   client class (classifyClient): bsky-appview, reader:feedly, bot, ...
//   blob3   viewer id: for Bluesky, a keyed hash of the signed-in account, stable
//           over time; for RSS, a keyed hash of address + user agent + UTC day,
//           so it counts distinct visitors per day but cannot follow anyone
//           across days. Empty when there is nothing to hash.
//   blob4   "1" for the first page of a feed (an open), "0" for a scroll
//   double1 subscriber count the reader reports, e.g. Feedly's "12 subscribers"

async function recordUsage(req: Request, url: URL, env: Env, kind: "feed" | "rss" | "page"): Promise<void> {
  if (!env.USAGE) return;
  try {
    const ua = req.headers.get("user-agent");
    const { client, subscribers } = classifyClient(ua);
    const key = env.INGEST_TOKEN ? `usage:${env.INGEST_TOKEN}` : "";
    let target = "unknown", viewer = "", first = "1";
    if (kind === "feed") {
      target = feedIdFromUri(url.searchParams.get("feed") || "", env.PUBLISHER_DID) ?? "unknown";
      if (!FEED_BY_ID.has(target)) target = "unknown";
      const did = viewerDid(req.headers.get("authorization"));
      if (did && key) viewer = await hashId(key, `did|${did}`);
      first = url.searchParams.get("cursor") ? "0" : "1";
    } else {
      const path = url.pathname.replace(/\/+$/, "") || "/rss";
      if (path === "/rss" || path === "/rss/feeds.opml" || resolveChannel(path)) target = path;
      const ip = req.headers.get("cf-connecting-ip") || "";
      const day = new Date().toISOString().slice(0, 10);
      if (ip && key) viewer = await hashId(key, `rss|${day}|${ip}|${ua || ""}`);
    }
    env.USAGE.writeDataPoint({ indexes: [kind], blobs: [target, client, viewer, first], doubles: [subscribers] });
  } catch (e: any) {
    console.error("usage", e?.stack || e);
  }
}

// ---- Home-screen support for feed pages -----------------------------------

function manifest(url: URL, env: Env): Response {
  const path = url.pathname.replace(/\/+$/, "");
  const r = resolveChannel(path);
  if (!r) return new Response("not found", { status: 404 });
  return new Response(renderManifest({ ...r.ch, selfUrl: `https://${env.HOSTNAME}${path}` }), {
    headers: { "content-type": "application/manifest+json; charset=utf-8", "cache-control": "public, max-age=86400" },
  });
}

const PNG: Record<string, string> = {
  "/rss/icon-180.png": ICON_180_PNG, "/rss/icon-192.png": ICON_192_PNG, "/rss/icon-512.png": ICON_512_PNG,
};

function iconResponse(path: string): Response | null {
  const headers = { "cache-control": "public, max-age=604800" };
  if (path === "/rss/icon.svg") return new Response(ICON_SVG, { headers: { ...headers, "content-type": "image/svg+xml" } });
  const b64 = PNG[path];
  if (!b64) return null;
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Response(bytes, { headers: { ...headers, "content-type": "image/png" } });
}

// ---- Ingest (from the bot) ------------------------------------------------

function sameToken(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

async function ingest(req: Request, env: Env): Promise<Response> {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });
  const auth = req.headers.get("authorization") || "";
  if (!sameToken(auth, `Bearer ${env.INGEST_TOKEN || ""}`)) return new Response("forbidden", { status: 403 });
  let body: any;
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }
  const raw: any[] = Array.isArray(body?.posts) ? body.posts : [];
  if (raw.length > 500) return json({ error: "at most 500 posts per request" }, 413);
  const posts = raw.map(cleanPost).filter((p): p is Post => p !== null);

  const stmts = SCHEMA.map((sql) => env.DB.prepare(sql));
  stmts.push(...posts.map((p) => env.DB.prepare(
    `INSERT INTO posts (url, uri, council_id, council_name, state, title, excerpt, published_at, posted_at)
     VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)
     ON CONFLICT(url) DO UPDATE SET
       uri = COALESCE(excluded.uri, posts.uri), council_id = excluded.council_id,
       council_name = excluded.council_name, state = excluded.state, title = excluded.title,
       excerpt = excluded.excerpt, published_at = excluded.published_at, posted_at = excluded.posted_at`,
  ).bind(p.url, p.uri, p.council_id, p.council_name, p.state, p.title, p.excerpt, p.published_at, p.posted_at)));
  let pruned = 0;
  if (typeof body?.prune_before === "string" && /^\d{4}-\d{2}-\d{2}T/.test(body.prune_before)) {
    stmts.push(env.DB.prepare("DELETE FROM posts WHERE posted_at < ?1").bind(body.prune_before));
  }
  {
    const out = await env.DB.batch(stmts);
    if (body?.prune_before) pruned = out[out.length - 1]?.meta?.changes ?? 0;
  }
  return json({ accepted: posts.length, rejected: raw.length - posts.length, pruned });
}

async function health(env: Env): Promise<Response> {
  // Polled by the off-host watchdog, so it must stay cheap: the newest row comes
  // straight off the posted_at index and MAX(rowid) is O(1). A COUNT(*) would read
  // every row on every poll. `posts` is the highest row id, an upper bound on rows.
  const row = await env.DB.prepare(
    "SELECT (SELECT posted_at FROM posts ORDER BY posted_at DESC LIMIT 1) AS newest, (SELECT MAX(rowid) FROM posts) AS posts",
  ).first<{ posts: number | null; newest: string | null }>();
  return json({ posts: row?.posts ?? 0, newest: row?.newest ?? null, feeds: FEEDS.length, councils: Object.keys(COUNCILS).length },
    200, { "cache-control": "no-store" });
}

function safeDecode(s: string): string {
  try { return decodeURIComponent(s); } catch { return ""; }
}
