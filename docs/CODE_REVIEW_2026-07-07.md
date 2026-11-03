# Full-Codebase Review — 2026-07-07

> ## Implementation status (updated 2026-07-07, same session)
>
> Fixes were implemented in commits `823591b` (Phase 0), `706f39d` (Phase 1), `01fead8`/`8ea06b7` (Phase 2), `06caf25` (Phase 3), `a5a2534` (Phase 4). All 83 CI tests pass.
>
> **FIXED:** POST-1..4, CORE-1..6, SCRAPE-1..9, DATA-1/2, OPS-1..13 (OPS-13 partial: compose healthcheck + generator tests done), QUAL-1/2/3/4/5/6/8/9/10/12/13/15/16, and SEC-1's code side (paths, untracking, validate.py scrub).
>
> **STILL MANUAL (user action required):**
> 1. **SEC-1**: rotate the VPS root password / disable password auth, then purge `scripts/deployment/deploy_secrets.py` from git history (`git filter-repo --path scripts/deployment/deploy_secrets.py --invert-paths` + force-push). Until then, git history still contains live root credentials.
> 2. **On the VPS after deploy**: install the new crontab — `python3 scripts/deployment/generate_crontab.py` then `crontab crontab_generated.txt` (old crontab backed up at `/root/crontab.backup.*`). The alembic migration (`attempt_count`) runs automatically on container start.
> 3. After CORE-1 deploys, currently-trapped councils will self-probate within 3 days; to clear them immediately run the manual SQL reset once (see project memory).
>
> **DEFERRED (deliberate, with reasons):**
> - **REFACTOR-1** (delete Wanneroo/Perth/Claremont/Bunbury/Joondalup classes → configs): needs live verification against each council site; do alongside backlog repair work.
> - **QUAL-7** (widen URL quote safe-set): changes the dedup identity of URLs — existing DB rows were stored with the old encoding, so changing it risks re-posting old articles as "new". Needs a one-off migration that renormalizes stored URLs in the same change.
> - **QUAL-11** (normalize all datetimes to naive UTC at ingestion): only skews the 7-day boundary by hours; touch with care and test freshness both sides.
> - **QUAL-14** (Stirling endpoint / Kentico userguid / etc. → config): needs config schema additions and live testing.



**Reviewed by:** an automated multi-pass review (five parallel subsystem reviews + independent spot-verification of headline findings).
**Purpose:** hand-off document for a future agent (or human) to implement fixes. Every finding was verified against the actual code at commit `8776603`; several were reproduced empirically (the `record_failure` TypeError, the dateutil `dayfirst` behaviors). Findings the reviewers investigated and found to be *non-issues* are listed at the end so nobody re-chases them.

**How to use this doc:** work through the phases in [Fix Order](#fix-order) — they're sequenced so each phase de-risks the next. Each finding has an ID for cross-referencing. Line numbers are accurate as of commit `8776603`; re-locate by the quoted code if the file has drifted.

---

## The one-paragraph diagnosis

The June 2026 incident (85 councils silently disabled) was not a fluke — it is the system's default failure mode, and the mechanism is still fully in place: **no scraper ever raises `ScrapeError`**, so network/WAF/proxy failures are recorded as "successful runs with 0 articles"; the empty-run breaker then disables councils one-way with **no re-enable path in code**; and `record_failure` — the other breaker — **crashes with a TypeError** for any council without an existing health row, so the 5-failure path is doubly dead. On the output side, a transient BlueSky outage **permanently destroys** every queued article attempted during it, and two uncoordinated posting processes (scrape-run posting + the 10-min queue processor, no locks, no atomic claim) can double-post and blow the rate budget. Plus one P0 that isn't a code bug at all: real VPS root credentials are committed to git because `.gitignore` excludes the wrong path.

---

## P0 — fix immediately

### SEC-1: Real VPS root credentials committed to git
- **Where:** `scripts/deployment/deploy_secrets.py` (tracked — confirmed via `git ls-files`); contains `HOST = "vps.example.com"`, `USER = "root"`, and a real password. Root cause: `.gitignore:47` excludes `scripts/deploy_secrets.py` but the file lives at `scripts/deployment/deploy_secrets.py`. The same wrong path is used in the rsync `--exclude` in both `.github/workflows/deploy.yml:44` and `rollback.yml:56`.
- **Failure scenario:** anyone with repo access (or any leaked clone) has root SSH to production.
- **Fix (in order):**
  1. Rotate the VPS root password and/or disable password auth in `sshd_config` (deploy already uses `VPS_SSH_KEY`, so key-only auth should be safe).
  2. Remove the file from HEAD **and history** (`git filter-repo --path scripts/deployment/deploy_secrets.py --invert-paths`), force-push, invalidate old clones as far as practical.
  3. Fix the path in `.gitignore` and in both workflow excludes to `scripts/deployment/deploy_secrets.py`.
  4. `scripts/deployment/validate.py:132` embeds fragments of previous real passwords as "suspicious patterns" — delete those literals too.

### POST-1: Transient BlueSky failure permanently destroys queued articles
- **Where:** `core/processing.py:214-216` + `core/poster.py:160-167`.
- **Defect:** `poster.post_article()` returns `None` for *every* failure — validation rejection, but also `send_post` raising on 429/5xx/timeout/expired session (blanket `except Exception` at poster.py:165). The caller can't distinguish, and its `else` branch runs `db.mark_as_posted(article['url'], "REJECTED_POSTER_VALIDATION")`, setting `posted_at` so the article is never retried.
- **Failure scenario:** a 10-minute BlueSky outage during a queue run → every article attempted in the window is silently, permanently dropped; the loop also keeps hammering the API on 429.
- **Fix:** make `post_article` tri-state — return URI on success; raise (or return) a distinct `TransientPostError` for network/HTTP/auth exceptions (treat 408/429/5xx/network as transient, 4xx-invalid-record as permanent); return `None` only for validation rejection. In `post_articles`, on transient error leave the row untouched and `break` the batch (next cron tick retries). Add an `attempt_count` column (alembic migration) incremented per try, with a dead-letter cap (`status='failed'` after ~5 attempts) so poison articles can't loop forever.

---

## P1 — will bite (several already are)

### SCRAPE-1 (systemic): No scraper ever raises `ScrapeError` — the failure breaker is dead code and network failures masquerade as empty runs
- **Where:** all of `core/scrapers/` — verified zero `raise` statements across base.py, card.py, rss.py, json.py, browser.py, custom.py, wa_custom.py, alyka.py, catalyst.py, spark_json.py. `fetch_page()` returns `None` on total failure; every scraper converts that to `[]` (e.g. card.py:123-125, custom.py:183/308/382, wa_custom.py:24/88/157/452, catalyst.py:37) or swallows via blanket `except Exception: return []` (custom.py:91, wa_custom.py:323/432, alyka.py:114/250, spark_json.py:90).
- **Consequence:** `main.py:175` records fetch failures as `record_success(articles_found=0)` → `consecutive_empty_runs++`. The `except ScrapeError → record_failure` path (main.py:184) is unreachable. A dead proxy/WAF block for ~20 runs disables councils via the empty-run path with no CRITICAL alert — **this is the exact mechanism of the June mass-disable.**
- **Fix:** add `fetch_page_or_raise(url)` to `BaseScraper` that raises `ScrapeError(f"fetch failed: {url}")` when all fetch attempts return `None`; use it for each scraper's top-level listing fetch. In API scrapers, narrow the blanket `except Exception` so network/HTTP/JSON-decode errors re-raise as `ScrapeError` and only per-item parse errors `continue`. Reserve the empty-run counter strictly for "HTTP 200, parsed OK, 0 items matched".

### CORE-1: Circuit breaker is a one-way trap — no auto-re-enable exists anywhere
- **Where:** `main.py:149-152` + `core/database.py:297-306`. The only re-enable logic (`record_success` clears `is_disabled` on ≥1 article, database.py:300-303) is dead code because `scrape_single_council` returns before scraping any disabled council. Confirmed by repo-wide grep; maintenance scripts only *report*.
- **Failure scenario:** transient WAF block → disabled forever until manual SQL (exactly the June incident).
- **Fix (probation pattern):** include `disabled_at` in the dict returned by `Database.get_council_health` (database.py:256-272); in the main.py:150 skip, allow one probation attempt when `disabled_at` is older than N days (suggest 3). Critically, on a *failed* probation re-stamp `disabled_at = func.now()` in both `record_failure` and the empty-run branch of `record_success` — currently `disabled_at` is stamped only at the disable transition, so without re-stamping, probation would fire every run once expired. A successful probation re-enables via the existing database.py:300-303 branch.

### CORE-2: `record_failure` crashes with TypeError for any council without a health row
- **Where:** `core/database.py:316`. A freshly constructed `CouncilHealth` has `consecutive_failures = None` pre-flush (`default=0` applies at INSERT), so `obj.consecutive_failures += 1` is `None += 1`. **Empirically reproduced.** The TypeError escapes the `except ScrapeError` block in main.py, skipping `log_scraper_run` and Discord logging; a council that has never succeeded can never trip the 5-failure breaker and never gets health/stats rows.
- **Fix:** `obj.consecutive_failures = (obj.consecutive_failures or 0) + 1`, or construct with explicit `consecutive_failures=0, consecutive_empty_runs=0, is_disabled=False`. (Audit `record_success` for the same pre-flush pattern.)

### POST-2: Two uncoordinated posting processes — duplicate posts and rate blowout
- **Where:** `scripts/deployment/generate_crontab.py:97-103` and `:235` emit scrape jobs **without `--scrape-only`**, so `main.py:432-436` posts after every scrape (up to the 50 rows `get_unposted_articles` returns). The queue processor independently posts every 10 min. No `flock` anywhere in the repo; `mark_as_posted` happens only *after* `send_post` (processing.py:200-201) with no claim-before-send.
- **Failure scenario:** scrape run and queue tick fetch overlapping unposted lists → same URL posted twice; a scrape run can burst ~50 posts, obliterating the 18/hr budget.
- **Fix (three parts):** (a) add `--scrape-only` to the staggered scrape cron lines so all posting flows through the paced queue; (b) atomic claim: `UPDATE articles SET posted_at=now(), posted_to_handle=:handle WHERE url=:url AND posted_at IS NULL RETURNING id` — skip the post if 0 rows; (c) `flock -n` (or `pg_try_advisory_lock`) around every posting entrypoint.

### POST-3: Posted-then-killed window + overlapping queue processors
- **Where:** `scripts/cron/process_global_queue.py:56-61` — `subprocess.run(timeout=120)` SIGKILLs the child, possibly between `send_post` and `mark_as_posted` → repost next tick. Worst case 8 states × 120s = 960s > the 600s cron period → two processor instances overlap (no lock), doubling the "18/hr" rate.
- **Fix:** wrap the processor in `flock -n` (single lock file); SIGTERM with grace before SIGKILL (`Popen` + `terminate()` then `kill()`). The atomic claim from POST-2(b) makes the kill window harmless.

### OPS-1: `--staggered` crontab output still omits all infra lines (known trap, confirmed unfixed)
- **Where:** `scripts/deployment/generate_crontab.py:278-280` — the staggered branch prints scrape jobs and returns: no `SHELL/PATH` header, no queue processor, no feed_watchdog, no alert_check, no daily digest, no cleanup.
- **Failure scenario:** any crontab rebuild from this output silently kills posting and all monitoring.
- **Fix:** make the `args.staggered` branch emit a complete crontab (env header + staggered jobs + `get_queue_processor_line()` et al.) and write `crontab_generated.txt` like the legacy path. Add a CI test asserting the staggered output contains `process_global_queue.py`, `feed_watchdog.py`, `alert_check.py` (see OPS-11).

### OPS-2: No missed-run detection (confirmed absent)
- **Where:** `scripts/monitoring/alert_check.py` checks breaker trips, zero-post states (12h floor), infra log events, empty runs — nothing checks scrape jobs actually ran. A wedged cron/docker or a bad crontab paste (OPS-1) produces zero alerts while backlog drains.
- **Fix:** add check #5 to alert_check.py: `SELECT state, count(*) FROM run_summaries WHERE started_at >= now() - interval '24 hours' GROUP BY state` (model at core/models.py:63) — alert if any state has 0 runs (expected 6 slots/day), escalate if all states have 0. Also alert if `max(articles.posted_at)` is >2h old (queue-processor death, distinct from scrape death).

### OPS-3: Nobody watches the watchmen
- **Where:** (a) `feed_watchdog.py:129` — `check()` uncaught; an exception tracebacks to an unread log and no alert is ever sent again. (b) alert_check.py requires the DB — a down DB (exactly when you want an alert) crashes it silently. (c) `discord_logger.py:_send_webhook` prints-and-returns on delivery failure. (d) If docker/cron is dead, nothing runs at all.
- **Fix:** wrap each monitor's `main()` in try/except that sends a "monitor crashed" embed (DB-independent for alert_check); make `_send_webhook` return success/failure and log CRITICAL on failure; **run feed_watchdog on the GitHub runner too** via `.github/workflows/ops_monitoring.yml` — it only needs the public BlueSky API + repo JSON, giving a true off-VPS dead-man that also covers (d) and OPS-2.

### SCRAPE-2: Fuzzy date-parse fallback fabricates near-now dates
- **Where:** `core/scrapers/base.py:360-367` — `date_parser.parse(date_str, dayfirst=True, fuzzy=True)` fills missing components from *today*: `"3 min read"` → day 3 of the current month; `"2026"` → today. Combined with the 7-day freshness check, a `date_selector` that grabs a "N min read" badge makes old articles perpetually "fresh".
- **Fix:** remove the fuzzy fallback, or use `fuzzy_with_tokens=True` and require the matched text to contain a full day+month pattern first (e.g. `re.search(r'\d{1,2}[\s/.-]+[A-Za-z0-9]+[\s/.-]+\d{2,4}', date_str)`); add explicit handling for `today`/`yesterday`/`N days ago`.

### SCRAPE-3: Day/month swap family — 8 call sites parse Australian dates month-first
- **Where (verified: `parse('12/06/2026')` → Dec 6; `parse('2026-06-05', dayfirst=True)` → May 6):**
  - `custom.py:770-772` (Drupal): parses ISO `datetime=` attributes **with** `dayfirst=True` → swaps ISO dates. Worst of the family.
  - `core/scrapers/json.py:122`: raw `date_parser.parse` without `dayfirst` → swaps dd/mm.
  - `wa_custom.py:56` (Wanneroo), `:121` (Perth), `:189` (Claremont); `custom.py:227,275` (OpenCities); `:420` (AspNet): no `dayfirst`.
  - `rss.py:58`: low risk (RFC-822 has month names) but inconsistent.
- **Fix (one pattern everywhere):** replace every raw `date_parser.parse` call with the inherited `self.parse_date(text)` — base.py:351-358 already handles ISO-vs-dayfirst correctly and strips "Published/Posted" prefixes.

### SCRAPE-4: Proxy configuration silently ignored by 5 scraper families (+ IP-burning per-item sessions)
- **Where:** `json.py:44-56` (module-level `requests.get`/`crequests.get`, hardcoded UA/impersonation, ignores `self.proxy`/`self.impersonate`/`self.verify_ssl`); `browser.py:44` (`p.chromium.launch()` never passes `proxy={"server": self.proxy}` — 26 browser_scraper councils); `custom.py:43` (WordPressScraper `self.session.get` — session proxies only set in `fetch_page`, never called); `spark_json.py:50` (bare `requests.get`); `wa_custom.py:372` (Belmont). Also `custom.py:456-501` (LGASA): a **new** curl_cffi Session per item, no proxy, no cap — ~800 direct redirect-resolution fetches per run.
- **Fix:** route through `self.fetch_page()` where possible; otherwise pass `proxies={'http': self.proxy, 'https': self.proxy} if self.proxy else None` (copy the correct pattern from alyka.py:98/222, wa_custom.py:262). Browser: pass `proxy={"server": self.proxy}` to `launch()` when set. LGASA: one reusable Session outside the loop + slice `items[:self.limit or 10]` before resolving. *Note: the de-proxy plan (project memory) may moot the proxy half — but the invariant "if configured, use it" should hold until the proxy is actually dropped, and the LGASA cap matters regardless.*

### SCRAPE-5: Hang risk — Belmont has no timeout; no per-council wall-clock bound anywhere
- **Where:** `wa_custom.py:372` — `self.session.get(...)` with no `timeout` (requests waits forever; one wedged connection eats a ThreadPoolExecutor worker for the whole run). Systemically: `fetch_page` retry stack ≈ 96s worst case, and `CardScraper.scrape` fetches up to 10 detail pages through it (card.py:163) ≈ 17.6 min in one thread; `main.py:227` calls `future.result()` with no timeout — only the outer cron container `timeout 1200` saves the run. Also: `_fetch_with_curl` gets zero retries while deterministic WAF blocks get 3 useless retries.
- **Fix:** `timeout=30` at wa_custom.py:372. Add a per-council deadline (`self.deadline = time.monotonic() + N` set in `scrape()`, checked in `fetch_page` and detail loops). Don't `_retry` detected WAF blocks (return a "blocked" sentinel distinct from "transient").

### SCRAPE-6: `full_content_selector` miss sets excerpt to the literal string `"None"`
- **Where:** `core/scrapers/card.py:225-229` — the else-branch (element not found) is a copy-paste of the success branch: `clean_text(str(None))` → `"None"` → truthy → posted to BlueSky. Latent today (no config uses `full_content_selector` — grep over `states/*/councils.json` = 0 hits) but fires the moment anyone uses the documented option.
- **Fix:** delete lines 227-229 (keep the debug print if wanted).

---

## P2 — should fix soon

### DATA-1: Mojibake root cause — wrong charset at ingest; downstream scripts only repair symptoms
- **Where:** `core/scrapers/base.py:208,219,246` return `response.text`; when a server omits `charset`, requests/cloudscraper decode as ISO-8859-1 (UTF-8 `'` → `â€™`) while curl_cffi defaults to UTF-8 — same site, different text depending on `use_curl`. The subprocess-curl fallback (base.py:297-302, `text=True`) decodes with the *locale* encoding and can raise `UnicodeDecodeError` (swallowed → None). This is what `fix_mojibake_posts.py` and the replacement table in `clean_text` (base.py:384-399) paper over.
- **Fix:** in `_fetch_with_requests`/`_fetch_with_cloudscraper`: `if 'charset' not in response.headers.get('content-type','').lower(): response.encoding = response.apparent_encoding or 'utf-8'`. Subprocess curl: `capture_output=True` without `text=True`, decode with `errors='replace'`. Belt-and-braces: reject the `â€` signature in `validate_post` so corrupted text can never reach BlueSky again.

### DATA-2: `date=None` articles are silently archived — a broken date selector stops a council posting while every health signal stays green
- **Where:** `core/processing.py:66-80` — dateless articles go to `add_articles_bulk(status='archived')`, which `get_unposted_articles` excludes; but the scrape returned N>0 so `record_success(N)` resets the empty-run counter. Broken `date_selector` (the most common breakage mode) = council never posts again, invisible to breaker, watchdog thresholds, and alerts. Inconsistent with `get_unposted_articles`, which *keeps* undated articles (database.py:203-215). Easy to hit: card.py only detail-fetches dates for the first 10 items, `browser.py:90` returns None date when selector absent, RSS items without pubDate.
- **Fix:** treat `date=None` as fresh in `process_articles` (freshness falls back to `first_seen_at` semantics, matching the queue side) **and** add a `dateless_count` to `scraper_stats` telemetry with an alert_check rule for councils 100%-dateless across N runs.

### CORE-3: Only `ScrapeError` triggers failure bookkeeping; all other exceptions bypass health tracking
- **Where:** `main.py:184` + `main.py:260` — an `AttributeError`/`UnicodeDecodeError`/unwrapped requests exception lands in the generic handler in `scrape_councils` where `record_failure`/`log_scraper_run` never run. (This is also where the CORE-2 TypeError lands invisibly.)
- **Fix:** add a second `except Exception` branch in `scrape_single_council` doing the same `record_failure` + `log_scraper_run(status='error')` bookkeeping. Complements SCRAPE-1.

### CORE-4: `--force-fresh` is a documented no-op
- **Where:** `main.py:426` omits `force_fresh=args.force_fresh` from the `process_articles` call (only tests pass it). Two-part fix: (1) pass the flag; (2) `get_unposted_articles` (database.py:199-220) auto-suppresses >7-day articles at read time (`status='suppressed_too_old'`), so also thread a `suppress_stale: bool = True` param through and pass `not force_fresh`.

### CORE-5: `add_articles_bulk` select-then-insert race loses the whole batch
- **Where:** `core/database.py:150-168` — concurrent duplicate URL (manual run overlapping cron) → `IntegrityError` on the unique index at commit → all articles from the run rolled back, exception propagates, run dies before posting.
- **Fix:** per-row `pg_upsert(...).on_conflict_do_nothing(index_elements=['url'])` (module already imports `pg_upsert`), count inserts via rowcount.

### CORE-6: Disabled councils spam a perpetual "Silent Failure" alert loop
- **Where:** `main.py:240-257` — the disabled-skip returns `[]`, so every run fires the silent-failure warning for every disabled council (frozen `consecutive_empty_runs` ≥ 20 ≥ threshold 3), inflating `warnings_count` and burying real alerts.
- **Fix:** return a sentinel (e.g. `None`) from the disabled-skip path and skip `log_council_result` + the alert branch for it.

### POST-4: Queue processor's log filter hides every failure mode
- **Where:** `scripts/cron/process_global_queue.py:64-66` relays only lines containing `"Posted"`/`"Error"`; actual failure strings ("Failed to post:", "Skipping post: Validation failed", "Authentication failed:", "Failed to authenticate with BlueSky") match neither. An hours-long auth outage is invisible.
- **Fix:** log all non-empty child output (post-only runs are small), and call `discord_logger.log_error` from `post_articles` on auth failure so it lands in `log_events` (which alert_check reads).

### OPS-4: Default (legacy) generator output is broken and dangerous — and still the default
- **Where:** `generate_crontab.py` no-flags emits `--concurrency $(dynamic)` (line 62 — cron executes it as command substitution → argparse failure, every scrape fails) and the old twice-daily burst schedule, overwriting `crontab_generated.txt`. This is exactly what the docs/DEVELOPER_GUIDE.md "regenerate after DST" instruction produces.
- **Fix:** make `--staggered` the default; delete the legacy path or gate behind `--legacy-burst` with a loud warning. (If legacy survives: the group stagger is also a silent no-op — `timezone_utils.py:135-139` adds the offset to the *date*, but `get_utc_time` reads only Y/M/D, so NSW/VIC/ACT all fire at the identical UTC minute; `tests/test_cron_schedule.py:35-55` asserts nothing real.)

### OPS-5: Deploy/rollback race with cron jobs
- **Where:** `deploy.yml`/`rollback.yml` run `docker compose down && up -d --build` with zero coordination — `down` kills Postgres under mid-run one-offs; during the multi-minute Playwright build every cron `docker compose run` fails; `rsync --delete` swaps code under running containers. With 48 scrape slots + queue every 10 min, collision is near-certain.
- **Fix:** `docker compose build && docker compose up -d` (build while old stack serves), plus a shared `flock /opt/council-news-bot/.ops.lock` taken by deploy and by generated cron lines (`flock -w 300 ...` in `generate_staggered_crontab` and `get_queue_processor_line`).

### OPS-6: Backups — success-reporting broken, single-disk, restore undocumented
- **Where:** `ops_monitoring.yml` backup step: `pg_dump | gzip > file` without `set -o pipefail` → pg_dump failure still reports "Database backed up" with an empty `.gz`. Backups live only on the VPS disk (14-day retention). No restore procedure exists (`docs/operations/RUNBOOK.md:315` documents dump only). `deploy.sh:254-270` still "backs up" the long-gone SQLite `council_news.db` — false comfort; delete.
- **Fix:** `set -o pipefail` + minimum-size check; copy off-box (upload-artifact from the workflow, or rclone to object storage); write and *test* a RESTORE.md (`gunzip -c … | docker compose exec -T db psql -U councilbot council_news`).

### OPS-7: Top-of-hour resource pile-up on the 4GB box
- **Where:** queue (`*/10` → :00), feed_watchdog (`0 */4`), alert_check (`0 */6`), and the NSW scrape slot all fire simultaneously at 00:00/12:00 UTC — four one-off containers (each *allowed* 3072M) + idle bot + Postgres → OOM-killer roulette where the victim may be Postgres. Related: `browser.py` launches a full Chromium per scrape and NSW has 13 browser_scraper councils — the shuffled pool can co-schedule 4-5 Chromium launches (~1.5GB+).
- **Fix:** de-align infra minutes (queue `3-53/10`, watchdog `17 */4`, alert `43 */6`, digest `11 21`); serialize browser scrapes with a module-level `threading.Semaphore(1-2)` around the `sync_playwright()` block; also move browser.py's `new_context`/`new_page` inside the `try` with `finally: browser.close()` (currently lines 52-61 sit before the try — leak on exception).

### OPS-8: Unbounded host log files
- **Where:** every cron line appends to `/var/log/council_bot_*.log`; no logrotate config exists anywhere. 48 jobs/day (including card.py's per-item `prettify()[:1000]` prints — see P3 QUAL-6) will fill the disk, killing Postgres and cron together.
- **Fix:** ship `/etc/logrotate.d/council-news-bot` (weekly, rotate 4, compress, copytruncate), installed by `setup_vps.sh` and deploy.

### OPS-9: `daily_briefing` window is Sydney-vs-UTC skewed; mixed-timezone `posted_at`
- **Where:** `daily_briefing.py:29` uses naive `datetime.now()` (Sydney, per container TZ) against UTC DB timestamps → "Last 24 Hours" is really ~13-14h. Related: `database.py:220` writes `posted_at = datetime.now()` (Sydney) for suppressed articles while line 175 writes UTC via `func.now()`.
- **Fix:** `utcnow` in both. (alert_check.py already correct; its state-casing bug is confirmed fixed.)

### SCRAPE-7: Selector-miss fallback replaces the "0 articles" signal with plausible garbage
- **Where:** `card.py:145-149` — if `item_selector` matches 0 items, `_scrape_links_directly` sweeps **every** `<a>` on the page for `/news/`-ish hrefs (nav, footer, teasers), no date requirement, title = link text. A markup change never produces the empty-run signal; the council "works" while posting nav-link titles.
- **Fix:** only run `_scrape_links_directly` when no selectors were configured; for configured councils return `[]` so the breaker and silent-failure alert actually fire.

### SCRAPE-8: Over-broad WAF-block detection discards legitimate pages
- **Where:** `base.py:253-263` — `"please wait..."` / `"ray id:"` matched anywhere in the body flags legit pages as blocked → None → empty run. Subprocess-curl variant worse (base.py:306): bare `"cloudflare"` anywhere (a `cdnjs.cloudflare.com` script tag) rejects the page.
- **Fix:** require title-level indicators (`<title>just a moment...`, `<title>attention required`) or co-occurrence of ≥2 indicators; align the subprocess branch with the curl_cffi logic.

### SCRAPE-9: Custom-scraper hygiene batch (verified individually)
- `custom.py:43` (WordPress): hardcoded `verify=False` — use `verify=self.verify_ssl`.
- `custom.py:601` (CatalystBrowser): Playwright import outside the try — import failure escapes to the no-bookkeeping handler (CORE-3); Melville/Rockingham/Kwinana/Murray/Laverton fail invisibly.
- `custom.py:387-430` (AspNet): (a) `section_links[:3]` can be 3 copies of one URL — dedupe with `dict.fromkeys` first; (b) line 412 assigns `section_url` to every linkless item — with the URL-unique constraint, one arbitrary title wins; `continue` instead; (c) ignores `self.selectors` and `self.limit`; bare `except:` at 421.
- Direct `NewsArticle(...)` construction bypassing `create_article` sanitization (`clean_text`, mojibake fixes): `wa_custom.py:60,130,196,311,420,482`, `catalyst.py:102`, `spark_json.py:80` — replace with `self.create_article(...)`.
- `custom.py:214` (OpenCities): `item_data.get('image', {}).get('imageAlt')` crashes on explicit `"image": null` → `(item_data.get('image') or {}).get('imageAlt')`.

### REFACTOR-1: Four custom classes are configs in disguise (consolidation plan)
- **Wanneroo/Perth/Claremont → `card_scraper`/`curl_scraper` config entries** in `states/wa/councils.json`. Exact selector mappings (verified against CardScraper's configured path, card.py:332-406):
  - Wanneroo: `{item: 'a.item-list__article', link: 'self', title: '.box-header, h2, h3', date: '.subtext'}`
  - Perth: `{item: '.card-list__item', title: '.card-list__title', link: 'a.card-list__whole-link', date: '.card-list__date', excerpt: '.card-list__synopsis', use_curl: true}` (note wa_custom.py:84 currently force-overrides `impersonate="chrome110"`, discarding config — the config route removes that trap)
  - Claremont: `{item: '.page-card', title: 'h3', link: 'self', date: '.news-card-details strong', use_curl: true}`
- **Joondalup → `alyka_scraper` config** (wa_custom.py:220-262 is a hand-rolled copy of `AlykaScraper.scrape_html_result`); Alyka needs two small additions: extra `PR` entries from config, and date-from-item-attribute (`data-datetime`) support.
- **Bunbury → WordPressScraper + `"api_url"` in config**; the class (custom.py:96-105) is just URL injection.
- Keep registry keys as aliases during migration to avoid a config flag-day. Also extract the triplicated "fetch detail page to recover date" loop (card.py:177, custom.py:135, custom.py:709) into a `BaseScraper` helper.

---

## P3 — cleanup / hardening

- **QUAL-1** `core/validator.py:70-113`: no total-post-length check — add `len(text) > 300` and UTF-8 byte-length guards to `validate_post` (Python `len()` over-counts vs graphemes, so it's safely conservative). Via POST-1, an over-long post currently means permanent article loss.
- **QUAL-2** `core/poster.py:368-384`: `#` in a *title* creates a Tag facet overlapping the title's Link facet (excerpts are checked for `#`, titles aren't) — only facet matches at/after the hashtags-string byte offset.
- **QUAL-3** `core/poster.py:331,346-350`: truncation slices mid-word/mid-grapheme (can split emoji ZWJ sequences) — cut at last space; use `regex.findall(r'\X', …)` if emoji fidelity matters.
- **QUAL-4** `core/database.py:171-179`: `mark_as_posted` never sets `status` (stays `'new'` forever, contradicting the documented lifecycle), and rejections recorded as `posted_to_handle='REJECTED_*'` pollute any `posted_at IS NOT NULL` stats. Add `status='posted'`; separate `mark_as_rejected` with `status='rejected'`, `posted_at` NULL, and exclude `'rejected'` in `get_unposted_articles`.
- **QUAL-5** `core/database.py:192`: LIFO within each council queue (`first_seen_at.desc()`) + 7-day auto-suppression = sustained backlog silently expires oldest items unposted. Order ascending within council (round-robin across councils is correct).
- **QUAL-6** `card.py:134,143,161,326` etc.: `print()` in the hot path incl. `item.prettify()[:1000]` per card — megabytes of thread-interleaved stdout per run burying real signals (feeds OPS-8). Replace all scraper `print()` with `logger.debug`.
- **QUAL-7** `base.py:54-63`: `quote(url, safe=":/?#=&%")` percent-encodes `+ @ , ! $ ;` — changes URL semantics and dedup identity (encoded vs raw forms = two rows = double post). Widen safe set to `":/?#[]@!$&'()*+,;=%"`; strip fragments before dedup.
- **QUAL-8** `factory.py:83-93` vs `json.py:14-26`: nested `"selectors"` style silently doesn't reach `JsonScraper` (falls back to defaults → 0 articles, no config error). Read `kwargs.get('selectors')` in `JsonScraper.__init__`. Also json.py:131-138 builds `NewsArticle` directly — route through `create_article` (gets `make_absolute_url` + `clean_text`).
- **QUAL-9** `rss.py:24-31`: the `html.parser` fallback is entirely non-functional (lowercased tags, `<link>` void element → 0 articles) — fail loudly if lxml-xml unavailable; also handle Atom `<entry>`/`<link href>`.
- **QUAL-10** `main.py:339,360,377` vs `main.py:109`: config loaders raise `ValueError` but call sites catch `ConfigurationError` — `--state typo` = raw traceback; one malformed `councils.json` breaks the cross-state `--council` search. Raise `ConfigurationError` from loaders; catch `(ConfigurationError, ValueError, IOError)`.
- **QUAL-11** `processing.py:56-57` + `database.py:200,210` + `base.py:77`: mixed naive-local/naive-UTC/aware datetimes → up to ~11h skew at the 7-day boundary. Normalize to naive UTC at ingestion (`dt.astimezone(timezone.utc).replace(tzinfo=None)` in `to_dict`) and compare against `utcnow` everywhere.
- **QUAL-12** `database.py:36`: `Base.metadata.create_all` in `Database.__init__` fights alembic (fresh DB gets tables without a version stamp; masks missing migrations). Remove; rely on the container's `alembic upgrade head`; keep behind an explicit flag for sqlite tests.
- **QUAL-13** `main.py:411`: `args.slot % args.slots` silently wraps an out-of-range `--slot` (a `--slot 6 --slots 6` typo double-scrapes slot 0 while the intended councils never run). Hard `parser.error` on out-of-range. Also validate in `generate_staggered_crontab` that `slots` divides 24 (`--slots 25` → `hours_per_slot=0`, all slots stack).
- **QUAL-14** Hardcoding rot: `wa_custom.py:478` (Dumbleyung) pins year-less dates to `datetime(2025,1,1)` forever-stale; `wa_custom.py:301` posts literal `"No Title"`; `wa_custom.py:356` bakes in a Kentico `userguid` that rots on index rebuild; `alyka.py:36-38` embeds the Stirling endpoint behind `if 'stirling' in council_id` — move all to config.
- **QUAL-15** `core/poster.py:64-72` + docs/DEVELOPER_GUIDE.md: state detection is regex-coupled to the `roundupnewsbot` handle prefix. **Verified this works today** (production `.env` uses `roundupnewsbot*`; docs/DEVELOPER_GUIDE.md's `lgnews*` is stale documentation — fix docs/DEVELOPER_GUIDE.md). But a rebrand silently degrades every account to `'NAT'`/`#ALGA` with zero errors — pass `state_code` explicitly into `BlueSkyPoster.__init__` from `main.py:393` and keep the regex as fallback.
- **QUAL-16** `discord_logger.py:69-70,93-94`: `log_warning`/`log_error` early-return (drop events) if `start_run()` was never called — lazily create `Database()` so maintenance scripts' events persist.
- **OPS-10** Duplicate daily briefing: both the generated crontab (`generate_crontab.py:181`) and `ops_monitoring.yml` (cron `0 21 * * *`) run it — keep the GH one (has failure alerting), drop the crontab line.
- **OPS-11** Watchdog alert fatigue: one 24h stale threshold for all 8 states + no cooldown → NT/ACT/TAS lulls re-alert every 4h, retraining channel-blindness. Per-state `stale_hours` (48h for TAS/NT/ACT) + a hash-of-problems cooldown file.
- **OPS-12** Post-deploy health gate is decorative: `health_check.py` always exits 0 and writes its report inside the ephemeral container. Exit non-zero past thresholds, or gate on `alert_check.py` + a `SELECT 1` probe.
- **OPS-13** Compose/CI hygiene: no `db` healthcheck / no `condition: service_healthy` (alembic races Postgres on boot); `POSTGRES_PASSWORD: securepassword` hardcoded in the committed compose file → `.env`; CI tests py3.9 while prod is 3.10; several tests besides the excluded TAS ones hit live sites; nothing in CI executes `generate_crontab.py --staggered` — add a test asserting the staggered output contains the infra lines (locks in OPS-1), each state emits exactly `slots` lines, and no two same-state jobs are within 20 min.

---

## Fix Order

**Phase 0 — today, mostly manual (SEC-1):** rotate VPS password / disable password auth → purge `deploy_secrets.py` from history → fix the three wrong paths → scrub `validate.py`.

**Phase 1 — pipeline integrity (stops silent data loss and the next mass-disable):**
POST-1 (tri-state post result + attempt cap) → POST-2/POST-3 (atomic claim + flock + `--scrape-only` cron lines) → CORE-2 (TypeError one-liner) → SCRAPE-1 (raise ScrapeError on fetch failure) → CORE-3 (bookkeep generic exceptions) → CORE-1 (breaker probation). Order matters: fix CORE-2 before SCRAPE-1, otherwise newly-raised ScrapeErrors hit the TypeError. After CORE-1, run the manual SQL reset once more to clear currently-trapped councils.

**Phase 2 — ops safety net (makes the next failure visible):**
OPS-1 (complete staggered crontab; regenerate + reinstall on VPS, diff against `/root/crontab.backup.*`) → OPS-2 (missed-run check) → OPS-3 (watchman wrapping + off-VPS watchdog) → OPS-4 (staggered default) → OPS-6 (backups+restore) → OPS-5 (deploy lock) → OPS-7/OPS-8 (pile-up + logrotate).

**Phase 3 — data quality:** DATA-1 (charset at ingest) → SCRAPE-3 (dayfirst family) → SCRAPE-2 (fuzzy dates) → DATA-2 (dateless telemetry) → SCRAPE-7/SCRAPE-8 → CORE-4/CORE-5/CORE-6 → SCRAPE-4/SCRAPE-5/SCRAPE-6 → POST-4 → OPS-9.

**Phase 4 — cleanup:** REFACTOR-1 consolidation, SCRAPE-9 batch, the QUAL-* list, OPS-10..13. Each is independent; good "small PR" fodder.

**Verification after Phases 1-2:** deploy, run one state with a deliberately-broken council config and a deliberately-unreachable URL; confirm the unreachable one records a *failure* (not empty), the broken-selector one records *empty*, a disabled council gets a probation attempt after N days, and `feed_watchdog`/`alert_check` fire on a simulated missed slot. The existing triage flow (`scripts/maintenance/triage_coverage.py`, `docs/SCRAPER_REPAIR_PLAYBOOK.md`) proves end-to-end recovery.

---

## Verified non-issues (don't re-chase)

- ISO-8601 dates vs `dayfirst` in **base.py** `parse_date` — correctly exempted (base.py:354-358). The bug is only in the call sites that *bypass* it (SCRAPE-3).
- Missing dates defaulting to `now()` — doesn't happen; dateless articles are archived (that's DATA-2, a different problem).
- Garbage/generic title filtering — handled downstream in `validator.is_valid_article` via constants.py.
- Unknown scraper type — rejected at config-load (main.py:83-86); factory's CardScraper fallback unreachable for validated configs.
- `use_curl` + `use_cloudscraper` both set — cloudscraper wins deterministically, degrades gracefully if uninstalled.
- Protocol-relative `//host/path` URLs — `urljoin` resolves correctly.
- Staggered slot math — `md5(id) % slots` partitions every council into exactly one slot; state-pair hour collisions are separated by 28 min > the 20-min container timeout.
- Naive-vs-aware datetime *crashes* — database.py:209-210 strips tzinfo before comparing (skew is QUAL-11, but no crash).
- `feed_watchdog`'s hardcoded `roundupnewsbot*` handles — correct; docs/DEVELOPER_GUIDE.md's `lgnews*` is the stale side. Network failure to BlueSky is correctly treated as a problem, not as healthy.
- Alembic heads (`d99b9970035d` → `2f3a0c8b2b9d` → `e4a1c3f7b8d2`) match `core/models.py` — no drift beyond QUAL-12.
- Page-1-only pagination — correct for newest-first feeds scraped daily.
- `_detect_state` regex — works today (see QUAL-15).
