# Instruction Layers and Precedence

Every durable instruction must have one declared ownership layer. Classification
prevents template updates from erasing project knowledge and prevents temporary
work decisions from silently becoming permanent policy.

## Layers

1. **Common** — Root `.instructions/*.md` files supplied by the project
   template. They define invariants and operational rules shared by every
   downstream project. The template owns and may update these files.
2. **Kind** — `.instructions/kind/`. The fork owns its repository-kind
   classification and guidance shared by repositories of that kind, such as an
   application, tool, platform, library, driver, runtime, trial, or another
   explicitly named kind. The template supplies only the classification slot.
3. **Local** — `.instructions/local/`. The fork owns durable instructions unique
   to this project, including its product boundaries, subsystem responsibilities,
   user-interface rules, domain constraints, and project-specific verification.
4. **Task-scoped** — Authorized records in `20_ops/`. They govern one bounded
   change, experiment, investigation, or release operation and expire with that
   scope unless deliberately promoted and reclassified.

The examples above are descriptive, not a closed global taxonomy. A fork must
state its chosen kind and rationale instead of inferring it from a repository
name, umbrella category, or source layout.

## Precedence and conflict

- Governing specifications, explicit external contracts, and license boundaries
  retain their own authority and cannot be weakened by repository instructions.
- Common invariants apply to every fork. Kind instructions may narrow them for a
  declared repository class; local instructions may narrow them for one project.
- A more specific layer may add constraints or choose among options explicitly
  left open by a broader layer. It may not contradict or weaken the broader
  invariant.
- Task-scoped records authorize bounded work; they do not override durable
  common, kind, or local rules merely because they are newer.
- When two instructions conflict or their ownership is unclear, stop, record the
  conflict, and change the owning layer through an authorized decision. Do not
  resolve the conflict by accidental file order or duplication.

## Placement and promotion

- Keep `AGENTS.md` concise: state core invariants and route readers to the owned
  instruction indexes. Put detailed project-specific guidance in `local/`.
- Put a durable rule in the narrowest layer that fully owns it. Do not copy the
  same rule into several layers.
- Promote task-scoped learning only after review establishes that it is durable,
  identifies its owner, and updates the correct kind or local index.
- Preserve rationale in the owning instruction or its linked decision record;
  do not preserve obsolete generations as permanent guidance.

## Template synchronization boundary

Template synchronization may add or update common files and the common routing
section of `AGENTS.md`. It must treat `.instructions/kind/` and
`.instructions/local/` as downstream-owned: never overwrite, delete, reset, or
silently reclassify their contents. Report a conflict for human resolution.
