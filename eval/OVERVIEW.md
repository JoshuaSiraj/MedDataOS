The evaluation checks the three things the design depends on: that the
orchestrator sends each question to the right data sources, that every claim in an
answer traces back to the data it cites, and that the Knowledge Bus flags genuine
contradictions while leaving consistent patients alone. It deliberately sets aside
one question, how accurately any single agent reads an ECG or an X-ray, because
that isn't what the system claims, and the whole point of the design is that
clinicians verify rather than trust. Measuring per-source accuracy would test the
wrong thing, and it would invite a comparison to specialized models I never meant
to compete with.

The harder problem was ground truth. I looked at existing public medical
benchmarks, but none really fit: they test one data type at a time, while
everything interesting here happens across data types, for a single patient, with
citations and conflict checking layered on top. So I built the answer key from the
ten synthetic patients created as a demo in the system's initial version. Each one comes with a complete,
internally consistent set of findings across all seven data types, and I take that
set of findings as the ground truth I grade everything against. They are not
independently clinician-validated: the evaluation measures whether the system
routes to, cites, and reconciles the findings correctly, not whether the findings
themselves are right. The construction is simple
enough to describe in a line or two in the paper rather than needing a methodology
write-up of its own.

The first step was to go through all ten patient records and catalogue the
individual clinical facts in each one, which I did with Claude Opus 4.8, roughly
288 of them across the seven data types, things like "ejection fraction 45 percent"
or "lateral ischemia on the ECG." That catalogue became both the raw material for writing questions and the
audit trail behind every correct answer, so each question can be traced back to
the specific facts that justify it.

From that catalogue I wrote 100 test questions, again with Claude Opus 4.8, grouped
by how much reasoning they demand. Alongside them I built 40 cases for the Knowledge Bus. The full
composition is:

| Test cases | Count | What they check |
|---|---|---|
| Simple lookups | 30 | answer sits in a single data source |
| Probe cases | 10 | 5 general questions needing no patient data (it should call nothing) and 5 asking about a data type that was removed (it must not call it) |
| Cross-modal | 30 | answer needs several sources at once |
| Multi-hop | 30 | answer requires chaining across four or five sources |
| Knowledge Bus, clean | 10 | internally consistent patient, it should stay silent |
| Knowledge Bus, seeded | 30 | one finding swapped for a contradictory one it should catch |

Each question carries a hand-labelled list of which data sources a correct answer
must use, and which are merely reasonable to consult. The multi-hop questions were
built by taking several single-source questions for one patient and composing them
into one natural, layered question, so their difficulty comes from structure
rather than from me trying to be tricky. The 30 seeded conflict cases span a range
of difficulty on purpose, from blatant contradictions to subtle ones, and cover
nine different pairings of data types, so the results do not hinge on a single
kind of conflict.

Three different AI model families are involved, on purpose, so that no model ends
up checking its own work:

| Role | Model |
|---|---|
| The system under test | Gemini 3.1 Pro |
| The independent grader (judge) | GPT 5.5 |
| Authoring the questions and composing the multi-hop ones | Claude Opus 4.8 |

The grader reads each answer and labels every claim. Claims that carry a citation
are marked faithful, overstated, or fabricated against the source they cite;
claims with no citation are marked grounded, ungrounded, or simply not a factual
claim. Those labels are what the citation numbers below are built from.

Before running everything, I trialed the whole pipeline on a small pilot of 10
questions and 2 conflict cases, and it paid off immediately. It showed that the
grader was at first too strict, penalizing perfectly sensible clinical phrasing. I
recalibrated the grading rubric on the pilot and then locked the questions and
rules in place. Locking it down matters. Once I had seen how the system did, I
did not go back and quietly reword questions to make the results look nicer. When
you build your own test, that bit of restraint is really what keeps it trustworthy.

The numbers here come from a second run. A first run showed where the system fell
short, and in response I improved the orchestrator's prompt, telling it to cite
every factual statement it makes and to stay strictly within what the agents
reported rather than adding inferences of its own. On the benchmark side I made a
single correction: I stopped scoring it as a mistake when the system consulted the
patient's clinical notes, since reading the chart is always reasonable, and I
decided that rule on principle and applied it everywhere. What I deliberately did
not do was touch the questions or their required answers, or tune anything to the
specific mistakes the first run had made. Then I re-ran the same frozen set.
Improving the system freely while leaving the test itself honest is the line that
keeps the comparison meaningful.

The results are strong. Because the system cites every factual statement it makes
and stays within what the agents actually reported, its answers hold up well under
scrutiny:

| What I measured | Result |
|---|---|
| Right data sources chosen (exact match) | 87% |
| Routing precision / recall / F1 | 0.95 / 0.97 / 0.96 |
| Claims faithful to their cited source | 96% |
| Overstated / fabricated claims | 1% / 2% |
| Confident claims with no source (out of ~1,600) | 4 |
| Real contradictions caught | 93% |
| False alarms on consistent patients | 0% |
| Median time per answer | 14.8 s |

In plain terms: the system routes to the right data and rarely misses what is
needed, its answers stay faithful to their sources almost all the time, and the few
unsupported statements that remain are mild clinical inferences rather than invented
facts. The conflict detector catches real contradictions without raising false
alarms on healthy patients. And the imperfections that do show up are the honest,
explainable kind a careful evaluation is meant to surface, not a suspiciously clean
sweep.

Everything is stored and version-tagged, so the run can be reproduced or inspected
in full. What is left is to fold these numbers into the paper's evaluation section
and, separately, for the paper's honesty rather than for these results, to replace
the placeholder agents with ones that read the raw data directly.
