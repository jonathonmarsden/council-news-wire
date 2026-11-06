// Run with: npm test (node --test, no Workers runtime needed)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  cleanPost, decodeCursor, didDocument, encodeCursor, feedIdFromUri, itemDate, renderOpml, renderRss, xmlEscape,
  type Post, wantsFeedPage, renderFeedPage,
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
  assert.ok(!html.includes("<b>hi</b>"));
});
