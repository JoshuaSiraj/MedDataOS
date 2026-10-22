# Citation-judge validation — annotator instructions

For each row, read `claim_text` and `evidence`, then put ONE label in the LABEL
column. Do not look at any judge output — this is a blind check.

If `kind` = **cited** (the claim cited specific findings, shown in `evidence`):
- `faithful`   — the claim's factual content is supported by the cited finding(s),
                 including reasonable clinical interpretation/synthesis of them.
- `overstated` — asserts severity/certainty/magnitude BEYOND what the finding states.
- `fabricated` — asserts a fact absent from, or contradicting, the cited finding(s).

If `kind` = **uncited** (no citation; `evidence` shows demographics + all findings):
- `grounded`     — the fact appears in, or is directly entailed by, any finding or demographics.
- `ungrounded`   — a specific clinical assertion not backed by any finding or demographics.
- `not_a_claim`  — connective/framing text with no checkable clinical fact.

Use NOTES for anything ambiguous. Aim for consistency with the definitions above.
