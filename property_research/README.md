# Property Research

This folder is the workspace target for the property market research pipeline.

Expected usage:

- keep the canonical property brief in `skills/entities/property_brief.st`
- place raw or intermediate property research artifacts here
- resolve the brief and these artifacts through `property_research.st`
- write consolidated dossiers and notes back into this folder

Suggested structure:

- `property_research/raw/`
  - price paid / land registry artifacts
  - EPC artifacts
  - flood / crime / demographics artifacts
  - rental listing and market research artifacts
- `property_research/`
  - final dossier markdown or JSON summaries
