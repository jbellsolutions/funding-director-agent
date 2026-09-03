# Operational underwriting and product routing

Use this skill when the file has enough verified information to compare funding
structures. This is operational pre-underwriting, not a lender decision.

1. Separate verified facts, unknowns, and assumptions.
2. Review relevant credit summaries, cash flow, existing debt, collateral,
   invoices, property, requested use, and time constraints.
3. Load only current active Product Cards backed by provider-controlled rules.
4. Test requirements and exclusions explicitly; do not infer around a failure.
5. Compare viable structures without optimizing for commission.
6. If no verified route exists, return `NO_VERIFIED_ACTIVE_ROUTE` and name the
   evidence or provider review required.

Validate rule effective dates, source authority, state coverage, required
documents, credit-pull type, guarantees, collateral, pricing method, and
destination. Public sites and training may identify a product family but cannot
activate it.

Return: fact table, risks, viable structures, eliminated structures with
reasons, missing evidence, and next safe action.

