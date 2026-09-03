# Funding Director Core

This local package supplies deterministic funding-case state, product-card
eligibility checks, approval binding, duplicate-submission prevention, and an
MCP surface for Hermes.

It intentionally does not contain credentials, lender endpoints, applicant
documents, or hard-coded approval promises. The checked-in Product Cards are
discovery seeds. A route becomes submit-ready only after an authorized operator
adds current provider evidence and changes its status to `active` in the private
runtime copy.

Runtime paths:

- Code: `~/.hermes/funding-director/core`
- Private configuration: `~/.hermes/funding-director/config`
- Durable state: `~/.hermes/funding-director/state`
- SQLite ledger: `funding-director.sqlite3`
