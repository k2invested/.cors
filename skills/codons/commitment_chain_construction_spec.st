{
  "name": "commitment_chain_construction_spec",
  "desc": "Protected planning specification for future chain construction. This package is no longer injected into live reason-needed turns. It remains as an immutable reference for the later chain_needed path, where workflow composition will be handled separately from judgment, tool writing, and semantic persistence.",
  "trigger": "manual",
  "author": "agent",
  "identity": {
    "purpose": "Describe the future chain construction discipline without letting the live runtime confuse that planning contract with ordinary reason_needed behavior.",
    "status": "dormant_reference"
  },
  "constraints": {
    "activation_owned_by_reason": true,
    "tool_creation_owned_by_tool_needed": true,
    "entity_persistence_owned_by_reprogramme_needed": true,
    "chain_building_owned_by_chain_needed": true,
    "public_tools_only": true,
    "hash_internal_handlers_not_public": true
  },
  "scope": "Future chain_needed workflow composition and package authoring.",
  "field_semantics": {
    "activation": "reason_needed decides when chain construction should begin.",
    "tool_refs": "Chains should reference public tools or public tool blob hashes, not internal handlers behind hash_resolve/hash_manifest.",
    "post_observe": "Mutation steps should rely on post-observation rather than direct gap explosion.",
    "public_trigger_rule": "Final public trigger assignment belongs to the completed top-level workflow."
  },
  "authoring_levels": {
    "level_0": "compose a minimal lawful chain that does real work",
    "level_1": "surface missing lower-order tools through tool_needed",
    "level_2": "compose higher-order workflow structure from existing public tools or chains",
    "level_3": "promote or map vocab only when the public semantic surface is truly needed"
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
