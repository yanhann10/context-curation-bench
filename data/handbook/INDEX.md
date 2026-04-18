# GitLab Handbook Corpus Index

Extracted 2026-04-18 for the context curation benchmark. All files are cleaned markdown derived from the public GitLab Handbook (source: `https://gitlab.com/gitlab-com/content-sites/handbook`).

| File | Title | Source URL | Approx Words |
|---|---|---|---|
| `expenses-and-reimbursement.md` | Spending Company Money (Expenses & Reimbursement) | `https://handbook.gitlab.com/handbook/finance/spending-company-money/` | 648 |
| `travel-policy.md` | Travel Safety, Security, and Insurance | `https://handbook.gitlab.com/handbook/finance/travel/` | 803 |
| `procurement.md` | Procurement & Vendor Management | `https://handbook.gitlab.com/handbook/finance/procurement/` | 850 |
| `individual-software-purchases.md` | Individual Use Software Purchases | `https://handbook.gitlab.com/handbook/finance/procurement/individual-use-software/` | 446 |
| `corporate-card-policy.md` | Navan Purchasing Card Policy (Corporate Credit Card) | `https://handbook.gitlab.com/handbook/finance/accounts-payable/corp-credit-cards/` | 771 |
| `flexible-pto-and-time-off.md` | Flexible PTO, Public Holidays, Sick Time, Bereavement, Jury Duty | `https://handbook.gitlab.com/handbook/people-group/time-off-and-absence/time-off-types/` | 1174 |
| `parental-and-other-leave.md` | Parental Leave, Emergency Leave, Military Leave, Equity Vesting During Leave | `https://handbook.gitlab.com/handbook/people-group/time-off-and-absence/leave-types/` | 1198 |
| `general-onboarding.md` | General Onboarding (New Hire Checklist) | `https://handbook.gitlab.com/handbook/people-group/general-onboarding/` | 862 |
| `us-benefits-overview.md` | GitLab Inc (US) Benefits Overview | `https://handbook.gitlab.com/handbook/total-rewards/benefits/general-and-entity-benefits/inc-benefits-us/` | 1092 |
| `total-rewards-compensation.md` | Total Rewards: Compensation, Bonuses, Equity | `https://handbook.gitlab.com/handbook/total-rewards/compensation/` + `.../stock-options/` | 917 |
| `all-remote-work.md` | All-Remote Work: Async, Handbook-First, Non-Linear Workday | `https://handbook.gitlab.com/handbook/company/culture/all-remote/` (+ subpages) | 861 |

**Total: 11 content files + this index. Approximately 9,622 words / ~12-13k tokens combined.**

## Notes on skipped sections

- **Dedicated IT onboarding page (laptop / MFA / Okta)** — The `https://handbook.gitlab.com/handbook/it/` public page now only redirects to `https://handbook.gitlab.com/handbook/security/corporate/end-user-services/` (CorpSec team page). Most IT onboarding details (Okta, JAMF, 1Password specifics, hardware provisioning) have moved to the **internal handbook** and are no longer public. Okta is still referenced throughout the public handbook as the access hub (`https://gitlab.okta.com/app/UserHome`), and `#it_help` Slack channel is the public-facing support route. This content is surfaced inside `general-onboarding.md` (Day 2 access request, Slack channels) and `procurement.md` (Okta / Zip access).
- **Home office / equipment stipend specifics** — The public `/handbook/finance/procurement/office-equipment-supplies/` page is now a 3-line stub that redirects to the internal handbook's Expenses page "Equipment" section for dollar-amount policy. Public references point to `expenses@gitlab.com` for questions.
- **Global Travel and Expense Policy (exact per-diem / meal / lodging limits)** — Moved entirely to `https://internal.gitlab.com/handbook/finance/expenses/` in March 2026. Only the meta-page and Navan card limits ($5k/transaction, $100/person meals, $125 gifts, $50 receipt threshold) remain in the public handbook — captured in `corporate-card-policy.md`.
- **Payroll details** — Public `/handbook/finance/payroll/` redirects to internal handbook.

## Source repository

All raw markdown was fetched from `https://gitlab.com/gitlab-com/content-sites/handbook/-/raw/main/content/handbook/...`. File provenance is preserved via the "Source" header in each individual file.
