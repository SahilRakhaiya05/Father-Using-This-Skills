# Contributing

Thanks for helping. This collection holds agent skills: a folder with a `SKILL.md` (instructions) plus optional `scripts/`, `references/` and `assets/`.

## Ground rules

- Your own skills go in `user/<skill-name>/`. `private/`, `organization/` and `plugins/` are generated copies — do not edit them by hand.
- Do not change anything in `examples/`, `public/` or `plugin-files/`; those belong to their original authors.
- Contributions to `user/` are accepted under the MIT License (see `LICENSE`). Only submit work you wrote or have the right to license this way. Do not paste text or code from paid or closed-source skills.
- No secrets, API keys, personal data or machine-specific paths.

## A good skill

- `SKILL.md` starts with YAML frontmatter: `name` (lowercase, hyphens), `description` (what it does **and when to use it**), `license`.
- Keep `SKILL.md` under about 500 lines; move detail to `references/` and link each file from `SKILL.md` with a note on when to read it.
- Scripts do the repeatable work, print clear errors, and never leave half-written output files.
- Every claim in the instructions is something you have checked by running it.

## Before you open a pull request

1. Try your skill end to end on real sample files, and run each script it ships at least once.
2. Copy `user/<skill>` to the three mirror folders and rebuild `user/<skill>.skill` with `examples/skill-creator/scripts/package_skill.py`.
3. Add a line to `CHANGELOG.md` and the skill to its category in `README.md`.

## Reporting a problem

Open an issue with: the skill name, what you asked for, what happened, what you expected, and your OS plus tool versions (`python --version`, `ffmpeg -version`).
