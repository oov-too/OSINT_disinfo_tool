# packs/pilot/briefs

| File | What it is |
|---|---|
| slots.toml | the pilot's value for every pack slot of the brief templates (plugin/templates/briefs/); 45 slots, 41 used by the templates, 4 kept for the skills |
| runs/pilot-6b.toml | the run values of the phase 6b intakes (label, purpose, material) |
| runs/pilot-6b.md | the run brief: the ten intakes, their order (earliest telling first), the extra report keys, what is not in the run |

Render: `python3 wip/platform-phase4/render_briefs.py --pack packs/pilot --run packs/pilot/briefs/runs/pilot-6b.toml --out <dir>` (checked 2026-10-22 after the owner's confirmation: 26 briefs, including intake-hearing.md, rendered to wip/platform-phase6b/rendered-briefs, every slot from the pack).
