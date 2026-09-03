# Funding Director Demonstration Runbook

This runbook demonstrates the system without customer data, real submissions,
credit pulls, or provider credentials.

## Before the session

- Use a fresh test workspace and synthetic applicant only.
- Confirm `./scripts/verify.sh` passes on the default branch.
- Keep every provider Product Card in `draft`; the test suite supplies its own
  temporary active fixtures.
- Never screen-share a token, private training page, customer file, or browser
  profile.

## Demonstration sequence

1. Deploy from `https://github.com/jbellsolutions/funding-director-agent` using
   `START-HERE.md`.
2. Prove the agent answers through one authorized messaging channel.
3. Open the Funding Director status and show that external writes begin behind
   one-time approval and that the emergency stop is clear.
4. Create a synthetic case, move it through completeness and underwriting, and
   run product routing. Explain why the public discovery catalog makes no live
   provider claim.
5. Add a temporary synthetic Product Card and destination in a throwaway test
   directory, prepare a submission, and display its frozen digest.
6. Approve that exact synthetic action, record a fake receipt, and show that the
   approval cannot be reused.
7. Record two synthetic offers, compare known finance cost and estimated
   monthly debt service, and show that unknown terms remain unknown.
8. Trigger the emergency stop and prove both submission and GoHighLevel writes
   are blocked while underwriting still works.
9. If private integrations are available, perform read-only Funding Machine and
   GoHighLevel tests. Do not write to a live contact during a demonstration.

## Definition of done

The installation is healthy; all repository tests pass; a real authorized
message works; synthetic case, routing, approval, receipt, deduplication, offer
comparison, and emergency-stop behavior are proven; no production record or
paid training content was exposed.
