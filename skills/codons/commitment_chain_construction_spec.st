{
  "name": "commitment_chain_construction_spec",
  "desc": "Semantic state for the commitment chain construction specification: build one chain at a time as a semantic tree. The default authoring move is step_chain_append.v1: append one step with full gap configuration, manifestation, allowed vocab, relevance, post_diff, and optional embedding; then let the builder compile the cumulative chain, validate it against system laws, and re-render the accepted chain as a semantic tree before the next append. Build higher-order layers inside out / back to front: lower-order chains and tool foundations must already exist before they are embedded. Embedding is strategic, not default: use it when a reusable grouped sub-flow is needed, especially post-mutation observation or self-review bundles. Multi-chain systems may still be built, but consecutively, never by manifesting multiple unfinished layers in one pass.",
  "trigger": "manual",
  "author": "agent",
  "refs": {
    "await": "3ed381ca80b9",
    "commit": "7ce6d9001162",
    "hash_edit": "70772dd86cf9",
    "reason": "684dc74c7a74",
    "reprogramme": "63334a75ecba"
  },
  "identity": {
    "purpose": "Defines the canonical structure and rules for constructing commitment chains as semantic trees, ensuring all planning, refinement, manifestation, and persistence steps are composable, auditable, and hash-native.",
    "authoring_note": "When reason_needed is authoring or repairing workflow structure, this specification is the executable contract. Default to step_chain_append.v1 for incremental authoring. Use step_chain.v1 for a complete simple chain and semantic_skeleton.v1 only when explicit manual spine control is truly necessary."
  },
  "constraints": {
    "must_follow_chain_spec": true,
    "must_embed_existing_st_by_hash": true,
    "must_build_layers_back_to_front": true,
    "must_distinguish_runtime_effective_from_descriptive_fields": true,
    "must_align_transitions_root_and_closure": true,
    "must_author_one_step_per_iteration": true
  },
  "scope": "All planning, refinement, manifestation, and persistence flows that require commitment chain construction or semantic tree extraction.",
  "field_semantics": {
    "artifact.kind": "Declares whether the package is entity, action, or hybrid. This determines who owns authoring and persistence. New skills/actions/*.st packages should be authored under reason_needed as action or hybrid, not reprogramme_needed.",
    "trigger": "How the package activates: command:X, on_vocab:X, on_contact:X, or manual. Public trigger vocab belongs to the highest-order completed workflow, not an unfinished lower-order layer. Lower layers should usually stay manual/internal until the final composition exists.",
    "refs": "Named handles for existing foundations. Treat action/codon .st packages and tool scripts as one hash-native action environment: committed .st packages by skill hash, tool files by committed blob hash. Semantic-tree hashes are embeddable compositional units; described-blob hashes are foundational executable/data blocks.",
    "step_chain_append.v1": "Incremental authoring surface. Append one step at a time to the current working chain, validate the compiled cumulative chain, then re-render that accepted chain as a semantic tree before the next iteration.",
    "step_chain.v1": "Default simple chain authoring surface when one ordered chain is enough. The author still supplies real step semantics, but the builder supplies root, default transitions, terminal, and closure.",
    "root": "Entry phase id for the compiled cumulative chain. The builder derives this automatically for step_chain.v1 and step_chain_append.v1.",
    "phases[*].id": "Canonical phase identifier. Transitions and closure point at these ids. They must be unique.",
    "phases[*].kind": "Runtime role of the phase: observe, reason, verify, clarify, await, higher_order, terminal, etc. This affects allowed vocab and manifestation defaults.",
    "phases[*].goal": "What this phase is trying to achieve. This is the semantic obligation represented by the phase.",
    "phases[*].gap_template": "The causal obligation surface. desc is the gap that this phase articulates, and step_refs/content_refs are what ground that obligation.",
    "phases[*].manifestation": "The runtime-effective execution contract for the phase. kernel_class, dispersal, and execution_mode are used by the engine. If execution_mode is wrong, prose elsewhere will not save the package.",
    "phases[*].generation": "How children or follow-on work are generated. Use this for branch/reentry behavior, not prose in desc.",
    "phases[*].allowed_vocab": "The vocab that this phase is actually allowed to emit. If a declared capability is not represented here or in manifestation, it is probably inert.",
    "phases[*].transitions": "Actual control flow. on_done/on_close targets determine where execution goes next. If transitions are linear, the workflow is linear even if desc claims branching.",
    "phases[*].embedding": "Explicit hash-based composition contract. block_ref identifies the existing foundation being embedded. activation_mode=named_default means use the canonical default gap contract for that block. activation_mode=hash_embedded means the enclosing chain may specialize manifestation through embedding.gap_override.",
    "closure.success.requires_terminal": "The success terminal must match the real terminal contract, usually phase_done unless the package intentionally uses another terminal phase.",
    "steps": "Compatibility projection for older action packages. Useful as a lowered view, but action runtime semantics should be authored from root/phases/closure rather than relying on decorative nested steps."
  },
  "linkage_rules": {
    "root_to_phases": "root must equal one of phases[*].id",
    "transitions_to_phases": "every transition target must equal an existing phases[*].id",
    "closure_to_terminal": "closure.success.requires_terminal must match a real terminal phase id",
    "phase_ids_unique": "all phases[*].id values must be unique",
    "action_tree_ownership": "Anything involving skills/actions/*.st belongs to reason_needed. reason may surface reprogramme_needed only for entity-tree persistence.",
    "entity_tree_persistence": "admin.st and skills/entities/*.st are reprogramme_needed territory once judgment has been made.",
    "embedding_override_explicit": "If a block is used by hash and must manifest differently inside the enclosing chain, that specialization must be explicit in phases[*].embedding.gap_override rather than implied by prose."
  },
  "runtime_effective_fields": {
    "effective": [
      "trigger",
      "root",
      "phases[*].id",
      "phases[*].kind",
      "phases[*].gap_template",
      "phases[*].manifestation",
      "phases[*].generation",
      "phases[*].allowed_vocab",
      "phases[*].transitions",
      "closure"
    ],
    "warning": "Nested freeform descriptive structures can be useful documentation, but runtime behavior is governed primarily by the fields above."
  },
  "authoring_levels": {
    "protocol": "Author exactly one step append per iteration by default. Validate the compiled cumulative chain. If valid, keep building or actualize it. If invalid, repair the next append against the current working semantic tree instead of re-authoring the whole workflow.",
    "level_0_executable_spine": "Start with the smallest valid chain that does real work. In incremental mode, the author supplies the meaningful step and the builder supplies root, terminal, closure, and default ordered transitions.",
    "level_1_control_semantics": "Each authored step must still carry runtime-effective semantics: gap_template, manifestation, allowed_vocab, relevance, post_diff, and optional embedding. Runtime behavior must be true in those fields, not only in prose.",
    "level_2_capability_expansion": "Add extra steps, verification, branching, or embedding of lower-order committed layers only after the current cumulative chain is valid. Foundational Python tools under tools/*.py are lawful lower-order layers and may need to be authored before the .st layer that embeds them.",
    "level_3_descriptive_enrichment": "Only after the cumulative chain is coherent should you add extra descriptive metadata. Enrichment without runtime linkage is validator-worthy drift.",
    "inside_out_rule": "Complex workflows must be built inside out / back to front. Foundational lower-order chains, Python tools, or vocab-mapped tools must already exist before a higher-order flow embeds them.",
    "tool_foundations": "If a required tool script does not exist yet, reason_needed should first surface the concrete tool-authoring gap (content_needed for a new tool, script_edit_needed/hash_edit_needed for an existing tool), commit that layer, and only then author the higher-order .st package that references it.",
    "public_trigger_rule": "If a higher-order layer still remains, the current layer should not claim the final public on_vocab trigger. The public trigger is a deterministic activation field attached to the highest-order completed workflow."
  },
  "common_failure_modes": [
    "Schema-valid but runtime-inert package: prose claims behavior that manifestation/allowed_vocab/transitions do not encode.",
    "root points to a non-existent phase id.",
    "closure.success.requires_terminal points to a non-terminal or to a different phase than the real terminal.",
    "Linear transitions described as branching workflow.",
    "Action/workflow repair incorrectly surfaced as reprogramme_needed instead of staying under reason_needed.",
    "Nested phase steps mention tools or branching, but the runtime-effective fields do not actually represent that behavior.",
    "Level-skipping: input_schema/output_schema or tool refs are added before the executable spine and control semantics are coherent.",
    "A lower-order layer claims the final public trigger vocab before the higher-order workflow it belongs to exists.",
    "A workflow references a tool foundation that has not been authored and committed yet, or references it only in prose instead of through refs/content_refs/activation_ref."
  ],
  "examples": {
    "hash_edit.st": {
      "why_it_works": "Minimal valid action package. Observe target via hash_resolve_needed, then compose, then execute via hash_edit_needed. Runtime semantics are simple and aligned.",
      "trigger": "on_vocab:hash_edit_needed",
      "shape": "linear action package using steps compatibility projection"
    },
    "debug.st": {
      "why_it_works": "Observe -> diagnose -> fix -> verify. Declared steps match runtime expectations and post_diff usage is coherent.",
      "trigger": "command:debug",
      "shape": "linear debug loop with explicit verification"
    },
    "bad_research_example": {
      "what_goes_wrong": "A file can validate while still being behaviorally wrong if transitions stay linear, closure points at the wrong terminal, or nested phase steps describe branching that manifestation/allowed_vocab never actually encode."
    }
  },
  "steps": [
    {
      "action": "load_identity",
      "desc": "surface identity context for commitment_chain_construction_spec",
      "resolve": [
        "identity"
      ],
      "post_diff": false
    },
    {
      "action": "load_constraints",
      "desc": "surface constraints context for commitment_chain_construction_spec",
      "resolve": [
        "constraints"
      ],
      "post_diff": false
    },
    {
      "action": "load_scope",
      "desc": "surface scope context for commitment_chain_construction_spec",
      "resolve": [
        "scope"
      ],
      "post_diff": false
    }
  ]
}
