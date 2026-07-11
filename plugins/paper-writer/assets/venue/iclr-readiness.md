# ICLR Readiness Checklist

Every item below reflects historically stable ICLR practice and MUST be
re-verified against the current year's Call For Papers before submission.

## Format

- Official ICLR LaTeX template for the target year (`iclr<year>.sty`).
- Main text within the page limit (9 pages in recent years; confirm on the
  CFP). References and appendix are not counted.
- Abstract deadline precedes the full-paper deadline; both go through
  OpenReview.

## Anonymity

- Double-blind: no author names, affiliations, acknowledgments, or grant
  numbers in the submission.
- No public repository URLs; use an anonymized mirror (for example
  anonymous.4open.science).
- Rewrite self-citations so they do not identify the authors.

## Statements

- Reproducibility Statement after the main text (does not count toward the
  limit): where the spec, conformance suite, and experiment ledger live and
  how to re-run them.
- Ethics Statement if applicable (up to one page, not counted).
- LLM usage disclosure per the current CFP policy; human authors remain fully
  responsible for all content.

## Fit and fallback

- The ICLR main track rewards technical contributions with empirical or
  formal grounding. A pure position/survey framing is high-risk: anchor the
  paper on (a) a formal contract model and (b) machine-checked conformance
  results, and treat the survey material as Related Work.
- Identify a fallback: a relevant ICLR workshop, or a systems venue if
  reviewers judge the ML relevance too thin.
- Dual submission policy: check any arXiv preprint or workshop overlap
  against the current rules.
