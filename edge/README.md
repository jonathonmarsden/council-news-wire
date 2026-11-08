# Edge service: Bluesky custom feeds and RSS

A small Cloudflare Worker that serves two read-only views of the stories the
bot has already published:

- **Bluesky custom feeds**, one per group of councils in
  [`config/feeds.json`](../config/feeds.json) (for example "M9 inner
  Melbourne", "Hunter", "Pilbara"). The Worker is the feed generator: Bluesky
  asks it which posts belong in a feed, and it answers with posts the state
  accounts have already made. It adds no new posts.
- **RSS** for every region feed, every council, every state and all of
  Australia, plus an OPML file to subscribe to many at once. Each item links
  straight to the council's own story.

The bot sends newly posted stories to the Worker every ten minutes
(`scripts/cron/sync_edge.py`). The Worker keeps its own copy in D1, so feeds
and RSS keep serving if the bot's host is down; they simply stop gaining items
until it is back.

## Paths

All on `lgnews.jonathonmarsden.com`; every other path on that host is the
static site.

| Path | What |
|---|---|
| `/rss/` | Human index of every RSS feed |
| `/rss/all.xml` | Every council |
| `/rss/state/<state>.xml` | One state or territory (`nsw`, `vic`, …) |
| `/rss/<feed-id>.xml` | One region feed, e.g. `/rss/vic-m9.xml` |
| `/rss/council/<council-id>.xml` | One council, e.g. `/rss/council/brisbane.xml` |
| `/rss/feeds.opml` | All of the above, for importing into a reader |
| `/.well-known/did.json` | The feed generator's `did:web` document |
| `/xrpc/app.bsky.feed.describeFeedGenerator` | The feeds this service offers |
| `/xrpc/app.bsky.feed.getFeedSkeleton` | A feed's posts (called by Bluesky) |
| `/ingest` | Where the bot sends new stories (bearer token) |
| `/edge/health` | Row count and newest story, for monitoring |

## Usage counts

Each feed and RSS request writes one anonymous data point to the Analytics
Engine dataset `council_news_edge_usage`, so we can see which feeds people
read. It is written after the response and never delays or fails a request.

Stored per request: which feed, a coarse client class (Bluesky, a named feed
reader, browser, bot), the subscriber count a reader reports, whether it was
the first page, and a keyed hash. For Bluesky the hash is of the signed-in
account asking for the feed, so readers can be counted over time without
being identified. For RSS it is of address, user agent and day, so visitors
can be counted per day but not followed across days. No IP address, account
or user agent string is stored. Analytics Engine keeps data for three months.

Query it with the [SQL API](https://developers.cloudflare.com/analytics/analytics-engine/sql-api/)
using a token with Account Analytics Read; `recordUsage` in `src/index.ts`
lists the fields.

## Data

`src/data.json` is a snapshot of the feeds and the enabled councils, because
the Worker cannot read the repository at run time. Regenerate it after
changing either, then redeploy:

```sh
python3 scripts/deployment/build_edge_data.py
```

`tests/test_edge_data.py` fails while the snapshot is stale.

The D1 table is created by the Worker on the first ingest (`src/schema.ts`),
so a new database needs no migration step.

## Develop and test

Requires Node.js 22.18 or later and the [`cf` CLI](https://developers.cloudflare.com/cf/).

```sh
cd edge
npm install
npm test                                   # logic tests, no Workers runtime
echo INGEST_TOKEN=local > .dev.vars
PUBLISHER_DID=did:plc:example cf dev       # http://localhost:5173 with a local D1
```

## Deploy

1. Sign in: `cf auth login`.
2. Create the database once: `cf d1 create --name council-news-edge`.
3. Publish the feed records from the account that will offer the feeds
   (`scripts/feeds/publish_feed_records.py --write`, with `FEEDS_HANDLE` and
   `FEEDS_APP_PASSWORD`). It prints the account's DID.
4. Deploy with that DID and a random ingest token:

   ```sh
   echo "INGEST_TOKEN=$(openssl rand -hex 24)" > secrets.env
   PUBLISHER_DID=did:plc:... cf deploy --secrets-file secrets.env
   ```

5. Give the bot the same token as `EDGE_INGEST_TOKEN` in its environment and
   install the crontab, which runs the sync every ten minutes. The first sync
   sends the last 90 days.

Feed records only need publishing again when a feed's name or description
changes, or a feed is added or retired (`--prune`).
