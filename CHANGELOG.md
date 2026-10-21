# Changelog

This file records user-visible changes. Versions are not considered released until a tagged distribution has passed the checks in `QUALITY_GATES.md`.

## Unreleased

- Show a path-and-size manifest for the exact project snapshot before a user confirms sandbox execution.
- Exclude Windows filesystem reparse points as well as symlinks from sandbox snapshots.
- Show raw untrusted model output and the separately filtered CLI response during evaluation review.
- Record the completed historical 50-case human evaluation and its failed release gate.
- Add explicit Docker/Podman runtime selection and a dedicated Podman sandbox CI job.
