# Paper Scope Interview

Ask before `paper prepare`. Answers map directly onto `paper_contract.json`
fields; stop interviewing once every field has an answer.

1. **Venue and deadline** — Which venue and year? When is the abstract
   deadline? (maps to `venue`; drives the readiness checklist)
2. **Paper type** — position, survey, or systems? What is the single biggest
   reviewer objection you expect for that framing at this venue?
   (maps to `paper_type`)
3. **Thesis** — State the core claim in one sentence that a reviewer could
   falsify. (maps to `thesis`)
4. **Claims** — List 3-5 claims. For each: what machine-checkable evidence
   would convince a skeptical reviewer, and does it exist today?
   (maps to `claims[].evidence_required`)
5. **Evidence budget** — If evidence is missing, how many additional bounded
   experiment runs are acceptable? (maps to
   `additional_experiment_policy.max_additional_runs`)
6. **Page budget** — Main-text page limit and appendix plan.
   (maps to `venue.page_limit_main_text`)
7. **Anonymization** — Is the repository public? What must be renamed or
   mirrored anonymously before submission? (maps to
   `writing_rules.anonymization`)
8. **Related work anchors** — Which existing systems/protocols must the paper
   position itself against? These become mandatory `[cite:key]` placeholders.
9. **Writer model** — Which model writes the prose?
   (maps to `writer_policy.writer_model`; default `claude-opus-4-8`)
