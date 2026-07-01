# Models

This directory stores placement instructions for model assets used by local
experiments. Large model files should not be committed to Git.

Recommended usage:

- Keep model weights on the local machine, under a documented path.
- Share large artifacts through Git LFS, GitHub Releases, or an external model
  download location when needed.
- Commit only lightweight metadata, README files, and placeholders.

For RAIR-RAG downstream generation experiments, see `models/llm/README.md`.
