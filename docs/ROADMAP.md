# Roadmap 2026

## 🎯 Strategic Goal
**Mission**: Achieve **95% Active Health** (>513 active councils) and **Zero Silent Failures**.

## 📊 Current Status (Jan 23, 2026)
- **Health Score**: ~87.9% (Estimate post-SparkCMS remediation).
- **Recent Wins**: 
    - Full remediation of Tasmania (OpenCities).
    - Identification of "SparkCMS" / Generic ASP pattern fixing 76% of NT and key WA councils (Esperance, Albany).
    - "Catalyst" consolidation in WA.

## 🛠 Active Workstreams

### W1. The "SparkCMS" Rollout (NT/WA)
**Objective**: Capitalize on the discovery of the `.module-list .row` platform.
- [x] **Discovery**: Identified platform via cookies and structure.
- [x] **NT Fix**: Remedied Katherine, MacDonnell, Tiwi Islands.
- [x] **WA Fix**: Remedied Esperance, Albany + **Reactivated 13 Disabled Councils** (Jan 23).
- [x] **Scan**: Full WA scan complete. Identified ~70 matches.

### W2. "Risky Selectors" Remediation
**Objective**: Fix fragile generic selectors (`.col-12`, `.row`) identified in the audit.
*Ref: [reports/RISKY_SELECTORS_REPORT.md](reports/RISKY_SELECTORS_REPORT.md)*
- [x] **WA**: Albany & Bridgetown-Greenbushes.
- [x] **NT**: Katherine/MacDonnell (Solved via SparkCMS migration).
- [ ] **TAS**: Hobart, Launceston, Burnie (OpenCities).
- [ ] **VIC**: Whitehorse, Wodonga, Greater Dandenong.

### W3. Hard Targets (The "Too Hard" Basket)
- [ ] **City of Armadale (WA)**: Uses React Server Components (Next.js) with content loaded via protected API. Current status: Disabled. Requires Playwright/Browser or API key extraction.
- [ ] **NSW/QLD Strict WAFs**: 16 councils in NSW failing due to strict WAF. Action: Test `impersonate: safari15_5`.

## 🟡 Infrastructure & Stability
- [ ] **Continuous Monitoring**: Cron job for `scripts/comprehensive_health_check.py`.
- [ ] **Database**: Plan migration from SQLite to PostgreSQL.
- [ ] **Dashboard**: Static HTML report generator.

## 🟢 Maintenance
- [x] **Global Health Check**: Jan 23, 2026.
- [ ] **Dependency Lock**: Freeze `requirements.txt`.
