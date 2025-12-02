# Tasmania (TAS) Council Configuration

## Status
- **Total Councils**: 29
- **Implemented**: 10 (Initial Batch)
- **Coverage**: ~35%

## Councils

| Council | Status | Scraper | Notes |
|---------|--------|---------|-------|
| Hobart | 🔴 403 | Card | Needs WAF bypass or specific selectors |
| Launceston | 🔴 403 | Card | Needs WAF bypass |
| Clarence | 🔴 0 items | Card | Needs selectors |
| Glenorchy | 🔴 0 items | Card | Needs selectors |
| Burnie | 🔴 403 | Card | Needs WAF bypass |
| Devonport | 🔴 0 items | Card | Needs selectors |
| Kingborough | 🔴 0 items | Card | Needs selectors |
| Huon Valley | 🔴 0 items | Card | Needs selectors |
| West Tamar | 🔴 0 items | Card | Needs selectors |
| Meander Valley | 🟢 Working | Card | Found 268 articles (Generic selectors worked) |

## Next Steps
1. Fix 403 errors (Try `use_curl: true` in `councils.json`).
2. Identify CSS selectors for the "0 items" councils.
3. Add the remaining 19 councils.
