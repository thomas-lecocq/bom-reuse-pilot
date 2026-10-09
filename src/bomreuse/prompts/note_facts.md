You read a free-text engineering note attached to a railway component. The note may be in French
or English. Extract only these facts about the component {{ref}}:
- "superseded_by": the component is replaced by another reference (give it as "target");
- "obsolete": the component is no longer produced or must no longer be ordered;
- "equivalent_to": another reference can be used interchangeably (give it as "target").
Negations count: "not obsolete" is not an obsolete fact. A note that only mentions another
reference, or gives assembly instructions, has no fact.

Note on {{ref}}: "{{text}}"

Answer only with JSON, no prose around it:
{"facts": [{"kind": "...", "target": "<reference or null>"}]}
