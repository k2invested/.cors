{
  "name": "commitment_chain_construction_spec",
  "desc": "Semantic state for the commitment chain construction specification: when planning, write the commitment chain as a semantic tree following the chain construction spec. Each step encodes full gap configuration. Embed existing .st files by placing their hash in a step's content_refs. Embed await_needed after any background trigger. Write new .st embeddings inline as steps with all 7 gap axes specified. Build layers back-to-front: leaf chains first, then mid-level chains that adopt them, then top-level orchestration. The resulting tree is directly extractable to .st via chain_to_st. If refining: hash_edit updates the reasoning chain. If manifesting: compose agent trigger + inject commitment gaps + trailing commit_needed. If judging persistence: articulate whether the semantic update is stable enough to persist and surface reprogramme_needed only when warranted. If heartbeat: emit close/revisit/refine gaps. If reorienting: reconstruct the rejected chain with corrections.",
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
    "authoring_note": "When reason_needed is authoring a semantic_skeleton.v1 action package, this specification is the executable contract. Treat it as the field-by-field meaning of the skeleton, not as loose design guidance."
  },
  "constraints": {
    "must_follow_chain_spec": true,
    "must_embed_existing_st_by_hash": true,
    "must_build_layers_back_to_front": true,
    "must_distinguish_runtime_effective_from_descriptive_fields": true,
    "must_align_transitions_root_and_closure": true
  },
  "scope": "All planning, refinement, manifestation, and persistence flows that require commitment chain construction or semantic tree extraction.",
  "field_semantics": {
    "artifact.kind": "Declares whether the package is entity, action, or hybrid. This determines who owns authoring and persistence. New skills/actions/*.st packages should be authored under reason_needed as action or hybrid, not reprogramme_needed.",
    "trigger": "How the package activates: command:X, on_vocab:X, on_contact:X, or manual. Public trigger vocab belongs to the highest-order completed workflow, not an unfinished lower-order layer. Lower layers should usually stay manual/internal until the final composition exists.",
    "refs": "Named handles for existing foundations. Treat action/codon .st packages and tool scripts as one hash-native action environment: committed .st packages by skill hash, tool files by committed blob hash. Semantic-tree hashes are embeddable compositional units; described-blob hashes are foundational executable/data blocks.",
    "root": "Entry phase id. It must point to a real phase.id. If root does not match a real phase id, the package is structurally incoherent.",
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
    "protocol": "Author exactly one layer per iteration. Validate it. If valid, actualize and commit it before attempting a higher-order layer. Parent layers may only embed already-existing committed child layers or committed tool blob hashes.",
    "level_0_executable_spine": "Start with the smallest valid action flow: name, trigger, artifact.kind, root, one actionable phase, one terminal phase, and closure aligned to that terminal. No nested phases[*].steps. No decorative schema.",
    "level_1_control_semantics": "Add runtime-effective phase configuration only after L0 is coherent: manifestation, generation, allowed_vocab, and transitions. Control flow must be true in transitions, not only in prose.",
    "level_2_capability_expansion": "Add extra phases, clarify branches, verification, deeper branching, or embedding of lower-order committed layers only after L1 is valid and runtime-effective. Foundational Python tools under tools/*.py are lawful lower-order layers and may need to be authored before the .st layer that embeds them.",
    "level_3_descriptive_enrichment": "Only after L0/L1/L2 are coherent should you add input_schema, output_schema, extra tool declarations, or richer descriptive metadata. Enrichment without runtime linkage is validator-worthy drift.",
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
