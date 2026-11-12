// Run with: npm test (node --test, no Workers runtime needed)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  cleanPost, decodeCursor, didDocument, encodeCursor, feedIdFromUri, itemDate, renderOpml, renderRss, xmlEscape,
  type Post, wantsFeedPage, renderFeedPage, renderManifest, bskyWebUrl, shortName,
  classifyClient, viewerDid, hashId, cacheKey, legacyRedirect,
} from "../src/lib.ts";

const DID = "did:plc:publisher";
const post = (o: Partial<Post> = {}): Post => ({
  url: "https://council.example/news/a", uri: "at://did:plc:bot/app.bsky.feed.post/1",
  council_id: "c1", council_name: "Example Council", state: "vic", title: "Title", excerpt: "Excerpt",
  published_at: "2026-11-05T00:00:00Z", posted_at: "2026-11-05T02:00:00Z", ...o,
});

test("did document points at the hostname", () => {
  const d = didDocument("lgnews.example");
  assert.equal(d.id, "did:web:lgnews.example");
  assert.equal(d.service[0].serviceEndpoint, "https://lgnews.example");
});

test("feed ids come only from this publisher's feed records", () => {
  assert.equal(feedIdFromUri(`at://${DID}/app.bsky.feed.generator/vic-m9`, DID), "vic-m9");
  assert.equal(feedIdFromUri(`at://did:plc:other/app.bsky.feed.generator/vic-m9`, DID), null);
  assert.equal(feedIdFromUri(`at://${DID}/app.bsky.feed.post/vic-m9`, DID), null);
  assert.equal(feedIdFromUri(`at://${DID}/app.bsky.feed.generator/far-too-long-a-feed-id`, DID), null);
});

test("cursors round-trip and reject junk", () => {
  const c = encodeCursor("2026-11-05T02:00:00Z", "at://x/app.bsky.feed.post/1");
  assert.deepEqual(decodeCursor(c), { postedAt: "2026-11-05T02:00:00Z", uri: "at://x/app.bsky.feed.post/1" });
  assert.equal(decodeCursor("nonsense"), null);
  assert.equal(decodeCursor("2026-11-05T02:00:00Z::https://not-an-at-uri"), null);
  assert.equal(decodeCursor(null), null);
});

test("xml escaping covers specials and strips control characters", () => {
  assert.equal(xmlEscape(`a & b <c> "d" 'e'\u0007`), "a &amp; b &lt;c&gt; &quot;d&quot; &apos;e&apos;");
});

test("item date uses the council's date when plausible, else the relay time", () => {
  const now = new Date("2026-11-06T00:00:00Z");
  assert.equal(itemDate(post(), now).toISOString(), "2026-11-05T00:00:00.000Z");
  // future-dated (e.g. a closing date read as the publish date)
  assert.equal(itemDate(post({ published_at: "2026-11-12T00:00:00Z" }), now).toISOString(), "2026-11-05T02:00:00.000Z");
  // far older than when it was relayed
  assert.equal(itemDate(post({ published_at: "2025-01-01T00:00:00Z" }), now).toISOString(), "2026-11-05T02:00:00.000Z");
  assert.equal(itemDate(post({ published_at: null }), now).toISOString(), "2026-11-05T02:00:00.000Z");
});

test("rss is well formed enough: one item per post, escaped, linked to the council", () => {
  const xml = renderRss({ title: "T & U", description: "D", link: "https://site", selfUrl: "https://site/rss/x.xml" },
    [post({ title: "Roads <closed>" }), post({ url: "https://council.example/news/b", excerpt: null })],
    new Date("2026-11-06T00:00:00Z"));
  assert.equal((xml.match(/<item>/g) || []).length, 2);
  assert.ok(xml.includes("<title>T &amp; U</title>"));
  assert.ok(xml.includes("<title>Roads &lt;closed&gt;</title>"));
  assert.ok(xml.includes('<guid isPermaLink="true">https://council.example/news/a</guid>'));
  assert.ok(xml.includes("<dc:creator>Example Council</dc:creator>"));
  assert.ok(xml.startsWith('<?xml version="1.0" encoding="UTF-8"?>'));
});

test("opml groups outlines", () => {
  const x = renderOpml("All", [{ title: "A", xmlUrl: "https://s/a.xml", group: "G1" }, { title: "B", xmlUrl: "https://s/b.xml", group: "G1" }]);
  assert.equal((x.match(/type="rss"/g) || []).length, 2);
  assert.equal((x.match(/<outline text="G1"/g) || []).length, 1);
});

test("ingest accepts a well-formed post and refuses bad ones", () => {
  const ok = cleanPost({ ...post(), state: "VIC" });
  assert.equal(ok?.state, "vic");
  assert.equal(cleanPost({ ...post(), url: "javascript:alert(1)" }), null);
  assert.equal(cleanPost({ ...post(), state: "xx" }), null);
  assert.equal(cleanPost({ ...post(), posted_at: "yesterday" }), null);
  assert.equal(cleanPost({ ...post(), uri: "not-at" })?.uri, null);
  assert.equal(cleanPost(null), null);
});

test("feed page only for browser navigations", () => {
  const h = (o: Record<string, string>) => ({ get: (k: string) => o[k] ?? null });
  assert.equal(wantsFeedPage(h({ "sec-fetch-dest": "document", "sec-fetch-mode": "navigate" }), null), true);
  assert.equal(wantsFeedPage(h({ accept: "text/html,application/xhtml+xml" }), null), false); // reader faking a browser Accept
  assert.equal(wantsFeedPage(h({ "sec-fetch-dest": "empty", "sec-fetch-mode": "cors" }), null), false);
  assert.equal(wantsFeedPage(h({}), "html"), true);
  assert.equal(wantsFeedPage(h({ "sec-fetch-dest": "document", "sec-fetch-mode": "navigate" }), "rss"), false);
});

test("feed page escapes content and links readers to the feed", () => {
  const html = renderFeedPage({ title: "A & B news", description: "d", link: "https://x", selfUrl: "https://h/rss/a.xml" },
    [{ url: "https://c/1?a=1&b=2", uri: null, council_id: "c", council_name: "C <Council>", state: "vic", title: "<b>hi</b>",
       excerpt: null, published_at: null, posted_at: "2026-11-01T00:00:00Z" }], "https://site");
  assert.ok(html.includes("A &amp; B news") && html.includes("&lt;b&gt;hi&lt;/b&gt;") && html.includes("C &lt;Council&gt;"));
  assert.ok(html.includes("add_feed=https%3A%2F%2Fh%2Frss%2Fa.xml"));
  // Email routes for people who live in their inbox: Microsoft 365 at work, any mailbox at home.
  assert.ok(html.includes("make.powerautomate.com/templates/details/"));
  assert.ok(html.includes("feedrabbit.com/subscriptions/new?url=https%3A%2F%2Fh%2Frss%2Fa.xml"));
  assert.ok(!html.includes("<b>hi</b>"));
});

test("feed page shows each story as a card with its council, links and state colour", () => {
  const html = renderFeedPage({ title: "Greater Sydney council news", description: "d", link: "https://x", selfUrl: "https://h/rss/nsw-sydney.xml" },
    [post({ state: "nsw", url: "https://www.council.example/news/a", uri: "at://did:plc:bot/app.bsky.feed.post/3abc" })], "https://site");
  assert.ok(html.includes('class="card" style="--sc:#2a6b98"'));
  assert.ok(html.includes('data-at="2026-11-05T02:00:00Z"'));
  assert.ok(html.includes("Read on council.example"));
  assert.ok(html.includes("https://bsky.app/profile/did:plc:bot/post/3abc"));
  // Home-screen support: a manifest for this feed, an icon and a name that fits under it.
  assert.ok(html.includes('rel="manifest" href="https://h/rss/nsw-sydney.xml?view=manifest"'));
  assert.ok(html.includes('rel="apple-touch-icon" href="/rss/icon-180.png"'));
  assert.ok(html.includes('content="Greater Sydney"'));
});

test("posts never sent to Bluesky get no Bluesky link", () => {
  const html = renderFeedPage({ title: "t", description: "d", link: "https://x", selfUrl: "https://h/rss/a.xml" }, [post({ uri: null })], "https://site");
  assert.ok(!html.includes("View on Bluesky"));
  assert.equal(bskyWebUrl("at://did:plc:x/app.bsky.feed.like/1"), null);
  assert.equal(bskyWebUrl("javascript:alert(1)"), null);
});

test("manifest opens the feed page it was added from", () => {
  const m = JSON.parse(renderManifest({ title: "Hunter & Central Coast council news", description: "d", link: "https://x", selfUrl: "https://h/rss/nsw-hunter.xml" }));
  assert.equal(m.start_url, "/rss/nsw-hunter.xml?view=html");
  assert.equal(m.scope, "/rss/nsw-hunter.xml");
  assert.equal(m.short_name, "Hunter & Central Coast");
  assert.equal(m.display, "standalone");
  assert.ok(m.icons.some((i: any) => i.sizes === "512x512"));
  assert.equal(shortName("Wollongong City Council news"), "Wollongong City Council");
});

test("clients are classed coarsely, with reader subscriber counts", () => {
  assert.deepEqual(classifyClient("Feedly/1.0 (+http://www.feedly.com/fetcher.html; 12 subscribers)"), { client: "reader:feedly", subscribers: 12 });
  assert.deepEqual(classifyClient("Inoreader/1.0 (+http://www.inoreader.com/feed-fetcher; 1 subscribers; )"), { client: "reader:inoreader", subscribers: 1 });
  assert.equal(classifyClient("NetNewsWire (RSS Reader; https://netnewswire.com/)").client, "reader:netnewswire");
  assert.equal(classifyClient("BskyAppView").client, "bsky-appview");
  assert.equal(classifyClient("Protoverse/1.0 (+https://protoverse.app/about)").client, "indexer");
  assert.equal(classifyClient("Mozilla/5.0 (compatible; ElevenlabsCrawler/1.0; +https://elevenlabs.io/docs/bots)").client, "bot");
  assert.equal(classifyClient("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36 (compatible; meta-webindexer/1.1)").client, "bot");
  assert.equal(classifyClient("facebookexternalhit/1.1").client, "bot");
  assert.equal(classifyClient("curl/8.7.1").client, "bot");
  assert.equal(classifyClient("Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 Version/27.2 Mobile Safari/604.1").client, "browser");
  assert.equal(classifyClient("lgnews-livetest").client, "test");
  assert.equal(classifyClient("").client, "blank");
  assert.equal(classifyClient(null).client, "blank");
});

test("viewer DID comes from the service token's issuer, or nothing", () => {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const jwt = (o: object) => `Bearer ${b64({ alg: "ES256K" })}.${b64(o)}.c2ln`;
  assert.equal(viewerDid(jwt({ iss: "did:plc:abc123", aud: "did:web:h" })), "did:plc:abc123");
  assert.equal(viewerDid(jwt({ iss: "did:plc:abc123#atproto" })), "did:plc:abc123");
  assert.equal(viewerDid(jwt({ iss: "https://evil" })), null);
  assert.equal(viewerDid(jwt({})), null);
  assert.equal(viewerDid("Bearer not-a-jwt"), null);
  assert.equal(viewerDid(null), null);
});

test("hash ids are stable per key and differ across keys", async () => {
  const a = await hashId("k1", "did:plc:abc");
  assert.match(a, /^[0-9a-f]{16}$/);
  assert.equal(a, await hashId("k1", "did:plc:abc"));
  assert.notEqual(a, await hashId("k2", "did:plc:abc"));
  assert.notEqual(a, await hashId("k1", "did:plc:abd"));
});

test("cache keys ignore made-up parameters, so they cannot force database reads", () => {
  const u = (s: string) => new URL(`https://h.example${s}`);
  const base = cacheKey(u("/rss/vic-m9.xml"), false);
  assert.equal(cacheKey(u("/rss/vic-m9.xml?x=1"), false), base);
  assert.equal(cacheKey(u("/rss/vic-m9.xml?x=2&y=3"), false), base);
  assert.equal(cacheKey(u("/rss/vic-m9.xml/"), false), base);
  assert.notEqual(cacheKey(u("/rss/vic-m9.xml"), true), base); // readable page kept apart
  assert.equal(cacheKey(u("/rss/vic-m9.xml?view=html"), true), cacheKey(u("/rss/vic-m9.xml"), true));
  const sk = "/xrpc/app.bsky.feed.getFeedSkeleton?feed=at://did:plc:p/app.bsky.feed.generator/vic-m9";
  assert.equal(cacheKey(u(sk + "&junk=1"), false), cacheKey(u(sk), false));
  assert.equal(cacheKey(u(sk + "&limit=500"), false), cacheKey(u(sk + "&limit=100"), false)); // clamped
  assert.equal(cacheKey(u(sk + "&limit=0"), false), cacheKey(u(sk), false)); // default 30
  assert.notEqual(cacheKey(u(sk + "&cursor=abc"), false), cacheKey(u(sk), false)); // pages differ
});

test("hostile story content cannot inject markup or scripts into feed pages or RSS", () => {
  assert.equal(cleanPost({ ...post({}), url: "javascript:alert(1)" }), null);
  assert.equal(cleanPost({ ...post({}), url: "data:text/html,<script>alert(1)</script>" }), null);
  assert.equal(cleanPost({ ...post({}), url: " https://x" }), null);
  const evil = post({
    title: `<script>alert(1)</script>"><img src=x onerror=alert(2)>`,
    excerpt: `</p><script>alert(3)</script>`,
    council_name: `<b onmouseover=alert(4)>Council</b>`,
    url: `https://council.example/a?q="><script>alert(5)</script>`,
    uri: `javascript:alert(6)`,
  });
  const html = renderFeedPage({ title: "t", description: "d", link: "https://x", selfUrl: "https://h/rss/a.xml" }, [evil], "https://site");
  const body = html.slice(0, html.lastIndexOf("<script>"));
  // Live tags or script links would be dangerous; the same words as escaped text are not.
  assert.ok(!/<script>alert|<img|<b onmouseover|href="\s*javascript:/i.test(body), "feed page body contains live markup");
  assert.ok(body.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
  const xml = renderRss({ title: "t", description: "d", link: "https://x", selfUrl: "https://h/rss/a.xml" }, [evil]);
  assert.ok(!/<script>|<img|<b onmouseover/i.test(xml), "RSS contains live markup");
});

test("legacyRedirect: nothing moves while the hosts are the same", () => {
  const u = new URL("https://lgnews.jonathonmarsden.com/rss/state/vic.xml");
  assert.equal(legacyRedirect(u, "GET", "lgnews.jonathonmarsden.com", "lgnews.jonathonmarsden.com"), null);
});

test("legacyRedirect: site and RSS move, path and query intact", () => {
  const F = "lgnews.jonathonmarsden.com", P = "councilnewswire.au";
  assert.equal(legacyRedirect(new URL(`https://${F}/rss/state/vic.xml?x=1`), "GET", F, P), `https://${P}/rss/state/vic.xml?x=1`);
  assert.equal(legacyRedirect(new URL(`https://${F}/`), "HEAD", F, P), `https://${P}/`);
  assert.equal(legacyRedirect(new URL(`https://${F}/vic`), "GET", F, P), `https://${P}/vic`);
});

test("legacyRedirect: the feed service, ingest, health and POSTs stay put", () => {
  const F = "lgnews.jonathonmarsden.com", P = "councilnewswire.au";
  for (const path of ["/.well-known/did.json", "/xrpc/app.bsky.feed.getFeedSkeleton", "/ingest", "/edge/health"]) {
    assert.equal(legacyRedirect(new URL(`https://${F}${path}`), "GET", F, P), null, path);
  }
  assert.equal(legacyRedirect(new URL(`https://${F}/rss`), "POST", F, P), null);
  assert.equal(legacyRedirect(new URL(`https://${P}/rss`), "GET", F, P), null); // already on the new host
});
