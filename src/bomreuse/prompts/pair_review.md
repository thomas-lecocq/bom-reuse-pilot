You review a possible duplicate in a railway Bill of Materials. Two component references were
flagged as similar by string matching. Descriptions may be in French or English; supplier names
may be written differently; similar references are often genuinely different parts (other size,
material, generation, motor vs trailer version).

Component A: {{a}}
Component B: {{b}}

Are A and B the same physical part recorded under two references (a data-entry duplicate)?
Answer only with JSON, no prose around it:
{"same_part": true or false, "reason": "<one sentence, English>"}
