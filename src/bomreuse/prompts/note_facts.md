You read a free-text engineering note attached to a railway component. The note may be in French
or English. Extract only these facts about the component {{ref}}:
- "superseded_by": the component is replaced by another reference (give it as "target"). When the
  note names a replacement reference, the fact is "superseded_by", even if it also says the old
  reference must no longer be ordered;
- "obsolete": the component is no longer produced or must no longer be ordered, with no
  replacement named;
- "equivalent_to": another reference can be used interchangeably (give it as "target");
- "withdrawn": the note cancels an earlier replacement or obsolescence statement about {{ref}}.
Negations count: "not obsolete" is not an obsolete fact. A note that only mentions another
reference, or gives assembly instructions, has no fact.

Note on {{ref}}: "{{text}}"

Answer only with JSON, no prose around it:
{"facts": [{"kind": "...", "target": "<reference or null>"}]}
