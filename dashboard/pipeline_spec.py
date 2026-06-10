"""
dashboard/pipeline_spec.py — minimal spine SPEC for the trail-of-record system.

Defines the stable edge-id space (E-*) for the PRD→slice→PR→review→merge
workflow pipeline. Each edge carries:
  - id        : stable E-* identifier (never changes after assignment)
  - from_node : source node kind/id
  - to_node   : target node kind/id
  - evidence  : 'github' | 'runtime' | 'unmeasurable'
                github = authoritative; evaluated in comparison engine
                runtime = live enrichment only; never compared against trail
                unmeasurable = in-conversation; rendered as context only
  - required  : 'always' | 'conditional'
                always     = every run must traverse this edge
                conditional = only triggered under certain conditions
                              (e.g., BLOCK loop, trivial-lane skip)
  - predicate : human-readable name for what confirms the edge

ADR-0053 D1/D2: artifact trail is the system of record; one evidence-annotated
SPEC is the single declared topology.

This is the SPINE SPEC (slice 1 walking skeleton). The full ontology
(replacing PIPELINE __edges__ + children[]) ships in slice 2.
"""

# ---------------------------------------------------------------------------
# Nodes — kinds only in this walking-skeleton spec.
# Stable node id-space uses hyphen-separated names matching skill/agent dirs.
# ---------------------------------------------------------------------------
NODES = {
    # --- artifacts ---
    "prd-issue":     {"kind": "artifact", "label": "PRD issue"},
    "slice-issue":   {"kind": "artifact", "label": "Slice issue"},
    "pr":            {"kind": "artifact", "label": "Pull Request"},
    "merge":         {"kind": "artifact", "label": "Merge"},
    "closed-prd":    {"kind": "artifact", "label": "Closed PRD"},
    # --- actors (orchestrator / skills / agents) ---
    "human":         {"kind": "human",        "label": "Human"},
    "orchestrator":  {"kind": "orchestrator",  "label": "Orchestrator"},
    "implementer":   {"kind": "agent",         "label": "implementer"},
    "reviewer":      {"kind": "agent",         "label": "reviewer"},
}

# ---------------------------------------------------------------------------
# Spine edges — the ~8 edges covering the PRD→slice→PR→review→merge region.
# These are the github-tier edges evaluated by the comparison engine.
# ---------------------------------------------------------------------------
SPINE_EDGES = [
    {
        "id": "E-PRD-SLICE",
        "from_node": "prd-issue",
        "to_node": "slice-issue",
        "evidence": "github",
        "required": "always",
        "predicate": "prd_has_sub_issue",
        "description": "PRD issue has ≥1 native sub-issue (slice)",
    },
    {
        "id": "E-SLICE-PR",
        "from_node": "slice-issue",
        "to_node": "pr",
        "evidence": "github",
        "required": "always",
        "predicate": "slice_closed_by_pr",
        "description": "Slice is closed by a PR via closingIssuesReferences",
    },
    {
        "id": "E-PR-REVIEW",
        "from_node": "pr",
        "to_node": "reviewer",
        "evidence": "github",
        "required": "always",
        "predicate": "pr_has_verdict_comment",
        "description": "PR has ≥1 reviewer verdict comment (VERDICT: APPROVE|BLOCK)",
    },
    {
        "id": "E-REVIEW-MERGE",
        "from_node": "reviewer",
        "to_node": "merge",
        "evidence": "github",
        "required": "always",
        "predicate": "pr_merged_after_approve",
        "description": "PR merged; last verdict before merge was APPROVE",
    },
    {
        "id": "E-MERGE-CLOSE-PRD",
        "from_node": "merge",
        "to_node": "closed-prd",
        "evidence": "github",
        "required": "always",
        "predicate": "all_slices_merged_prd_closed",
        "description": "All slices merged; PRD issue closed",
    },
    # Conditional: BLOCK loop (reviewer blocks implementer; multiple rounds)
    {
        "id": "E-REVIEW-BLOCK",
        "from_node": "reviewer",
        "to_node": "implementer",
        "evidence": "github",
        "required": "conditional",
        "predicate": "pr_has_block_verdict",
        "description": "Reviewer posted BLOCK — implementer revised and re-pushed",
    },
    # Conditional: trivial-lane (PR ≤10 LoC, trivial label, no slice ceremony)
    {
        "id": "E-TRIVIAL-LANE",
        "from_node": "pr",
        "to_node": "merge",
        "evidence": "github",
        "required": "conditional",
        "predicate": "pr_has_trivial_label",
        "description": "PR is trivial-lane (≤10 LoC, trivial label, no reviewer required)",
    },
]


def get_spec() -> dict:
    """Return the full spine spec as a JSON-serializable dict.

    Shape:
        {
          "nodes": {id: {kind, label}, ...},
          "edges": [{id, from_node, to_node, evidence, required, predicate, description}, ...],
          "version": "spine-v1"
        }
    """
    return {
        "version": "spine-v1",
        "nodes": NODES,
        "edges": SPINE_EDGES,
    }
