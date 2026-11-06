# AI use in Folio

AI assists research, design comparison, implementation, and review. Siddhant retains responsibility for the product's requirements and accepted engineering decisions.

## Working method

1. Define a user outcome and its acceptance criteria.
2. Discuss the relevant design options and record the chosen boundary.
3. Delegate a bounded vertical slice with explicit exclusions.
4. Write and run a meaningful failing behavior test before implementation.
5. Implement, verify, and request an independent review of the result.
6. Walk through the data flow, failure behavior, and tradeoffs with Siddhant.

Model-assisted software tests and live AI evaluations serve different purposes. Deterministic tests check contracts; live evaluations check the quality of actual retrieval and answers. Both need human-defined expectations.

## Activity record

| Date | AI contribution | Verification and human ownership |
| --- | --- | --- |
| 2026-11-06 | Parallel research into document pipelines, evaluation workflows, and maintained skills; initial requirements and decision drafts | Primary documentation checked. Recommendations remain explicitly proposed. No application correctness or performance results claimed. |
| 2026-11-06 | Installed pinned skills and independently reviewed requirements coverage and public-source contents | Skill integrity checks passed. Review led to removing an irrelevant infrastructure reference and refreshing decision status. General-purpose document examples and environment-file preferences were confirmed by the human owner. |
| 2026-11-06 | Compared current model metadata and reviewed ingestion acceptance examples; clarified model-budget configuration | The human owner selected OpenRouter, text-based PDFs, and one PDF per conversation. Credential authentication was checked without inference. Independent review caught separate route input/output limits missing from the initial budget contract; these were verified and added. Model quality and numerical budgets remain unverified; summaries were separated from the proposed first ingestion slice. |

For later slices, record the task, relevant constraints, agent contribution, checks run, defects caught, and the decision retained by the human owner. Keep entries brief and factual; do not publish raw conversations, secrets, or private document contents.
