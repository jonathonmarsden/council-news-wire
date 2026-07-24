# Roadmap

What would take this from "a good public-interest project" to a reference
example of civic technology. Ordered by honest value, not by ease.

Measured baseline (July 2026): 89 tests, **27% statement coverage of `core/`**,
8 of 13 test files reach the live internet, no linter or type-checker
configuration, 534/537 councils collecting.

---

## Tier 1 — Credibility of the code itself

### 1. Raise test coverage where correctness actually matters

Coverage is 27%. The gap is not evenly distributed, and the uncovered parts are
the ones that lose data:

| Module | Coverage | Why it matters |
|---|---|---|
| `core/poster.py` | 12% | Publishing, rate limits, exactly-once claim |
| `core/database.py` | 16% | Dedup, circuit breaker, queue state |
| `core/scrapers/card.py` | 14% | The primary collector, ~200 councils |
| `core/processing.py` | 39% | Freshness, validation, article lifecycle |

Target 80% on `poster`, `database`, `processing`, and `base` — the modules
where a bug means lost or duplicated public information. Collector-specific
files matter less; they fail visibly and are covered by live checks.

**Every historical defect deserves a regression test.** The July review found
~50 bugs; a reader should be able to see the test that proves each one cannot
return. That is the single most persuasive artefact a maintainer can offer.

### 2. Make the test suite hermetic

8 of 13 test files hit real council websites. That makes CI a weather report:
it fails when a council is down, and it cannot run offline or in a fork's CI.
Record fixtures (`responses`/`vcrpy`) for the parsing tests, and keep a
separate, clearly-labelled `--live` suite run on a schedule rather than on
every commit. Contributors can then run the full suite in seconds without
touching anyone's servers — which is also the polite thing to do.

### 3. Adopt standard Python tooling

No `pyproject.toml`, linter config, or type checker. Add:

- `pyproject.toml` as the single source of project metadata and tool config
- `ruff` for linting and formatting (fast, one tool, minimal bikeshedding)
- `mypy` on `core/` — the codebase already uses type hints; enforce them
- `pre-commit` so contributors get the same checks locally as in CI

This is table stakes for a repo people are asked to take seriously.

### 4. Reduce the collector sprawl

`custom.py` is 796 lines and `card.py` is 700. Several "custom" collectors are
configuration in disguise (documented in the code review as REFACTOR-1).
Collapsing them lowers the cost of every future fix and makes the codebase
legible to a newcomer in one sitting.

---

## Tier 2 — Being genuinely useful to others

### 5. Publish the data, not just the posts

The highest-leverage thing this project could do. The database holds a growing
archive of what every Australian council announced and when. Offer it as:

- a **public read-only API** (or nightly JSON/CSV dumps on a static host)
- a **per-council RSS feed** — many councils have none; this project could
  give every council in Australia a working feed
- an **open dataset** with a stable schema and a licence (CC-BY-4.0 suits data)

Researchers, journalists, and councils themselves would use this. It converts
the project from "a bot" into public infrastructure, and costs little because
the data already exists.

### 6. Make it reproducible elsewhere

The architecture is not Australia-specific. A clean separation between the
engine and the `states/*.json` configuration would let others run the same
service for New Zealand, Canada, the UK, or any country with fragmented local
government. Document "how to run this for your country" and the project stops
being one person's bot and becomes a template.

### 7. Accessibility and archival integrity

- Ensure posts carry alt text where images are ever used, and that the site
  meets WCAG AA — a public-good service should be usable by everyone
- Consider submitting collected URLs to the Internet Archive: council pages
  disappear, and this project knows about them while they exist

---

## Tier 3 — Governance and longevity

### 8. Answer "what if the maintainer stops?"

Currently the honest answer is "it degrades." Reduce that risk:

- a documented, tested restore-from-backup path (partly exists)
- a `GOVERNANCE.md` stating who decides, how a successor takes over, and what
  happens to the accounts and domain
- a `CODE_OF_CONDUCT.md` if contributions are genuinely welcome
- consider a lightweight institutional home (a peak body, a university, or a
  civic-tech organisation) as a backstop

### 9. Publish the operational record

The project already produces daily health data. A public status page — uptime,
councils collecting, stories published — would make the reliability claim
self-evidencing, the same way the crawler page makes the politeness claim
self-evidencing.

### 10. Formalise the council relationship

Move from "we scrape you" to "we work with you": a short standing offer that
any council may nominate an RSS feed or API, request removal, or ask for
changes. Some councils may eventually *ask* to be included — which is the
strongest possible position for a project like this.

---

## What "world's best" would actually mean

Not the most features. A civic-tech project earns that description when:

- **its claims are checkable** — code, data, and operational record all public
- **it survives its founder** — documented, governed, reproducible
- **it gives more than it takes** — the data is a public asset, not just a feed
- **the institutions it serves want it to exist** — councils see it as help
- **its failures are visible** — because that is what makes the successes
  believable

Items 1, 2, 5 and 8 move the needle most. The rest is polish.
