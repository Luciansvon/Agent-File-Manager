# Folder Vision — Canonical Windows Architecture

> Authority: user architecture revision dated 2026-08-30. This document supersedes conflicting model, lifecycle, watcher, search, and action decisions in earlier Folder Vision drafts.

## System loop

```text
Windows storage
  -> MFT + USN Change Journal
  -> File Catalog Service
  -> SQLite metadata/lifecycle DB
  -> eligibility rules
  -> parser/OCR/vision enrichment
  -> canonical content + semantic identity
  -> lexical search + multilingual vector search
  -> fusion only if benchmarked better
  -> reranker only if benchmarked better
  -> live filesystem verification
  -> LLM/chat/action proposal
  -> preview + user approval
  -> Windows IFileOperation
  -> USN observes the resulting change
```

## Filesystem truth and identity

- Windows is the source of truth for whether a file currently exists.
- On NTFS, MFT identity plus the USN Change Journal is primary for create, edit, rename, move, delete, and restore. `FileSystemWatcher` is fallback/supplementary only.
- Every catalog row carries at least `internal_asset_id`, volume serial, Windows FileId, current path, previous path, size, mtime, content hash, last USN, and lifecycle status.
- Rename and same-volume move update physical location without creating a new asset.
- Cross-volume moves may appear as delete plus create; correlate conservatively using content hash, size, and timestamps.
- Deleted assets become tombstones and leave active search. Historical semantic identity may remain. Restore reuses prior identity when FileId/hash evidence supports it.

## Whole-disk awareness and eligibility

- Catalog storage metadata broadly; run content intelligence only on eligible user content.
- Exclude system/application internals such as Windows files, DLLs, caches, temp, browser caches, `node_modules`, `.git`, and virtual environments.
- OneDrive online-only placeholders are metadata-only: filename, path, extension, and timestamps may be indexed, but content read, OCR, embeddings, and hydration are forbidden until local or explicitly requested.

## Document pipeline

```text
detect type -> cheapest native/light parser -> content usable?
  yes: canonicalize
  no: OCR or specialist fallback
```

- TXT, Markdown, and code: direct read.
- DOCX, PPTX, XLSX: native/light parser.
- Text PDF: PDF parser.
- Scanned PDF: OCR fallback.
- Image: image pipeline.
- SQLite is the source of truth. Shadow Markdown is derived and content-addressed, for example `cache/<content-hash>.md.zst`.
- Do not create one Markdown file per chunk. Store chunk identity, asset identity, heading, offset, and text in SQLite.

## Search

- Baseline: original canonical content into both lexical/BM25 and multilingual dense retrieval.
- Baseline embedding candidate: `multilingual-e5-small`; Indonesian-to-English translation is not a core dependency.
- BM25 remains important for filenames, project codes, SKUs, dimensions, materials, and revisions.
- Benchmark lexical-only, dense-only, and hybrid on real queries. Keep fusion only if it improves agreed metrics.
- Candidate rerankers include `BAAI/bge-reranker-v2-m3` and Jina reranker v3.5, but neither enters production without improving Hit@1, Recall, and MRR on the representative query set.
- Before returning an active file, verify its current filesystem state.

## Image semantic identity

- Run vision once on eligible image creation, then persist caption, objects, materials, colors, style, features, OCR, tags, and visual embedding.
- Rename or move changes physical identity fields only; do not rerun vision.
- Edit compares content hash; rerun vision only when pixels/content changed.
- Delete tombstones the physical asset and removes it from active results. Restore may reuse semantic identity.
- Physical identity and semantic identity are separate but linked by `internal_asset_id`.

## Device model budget

Target: RTX 3050 Laptop 4 GB VRAM and 24 GB RAM.

- Idle means no heavy model loaded.
- Ingestion loads only the parser/embedder/OCR required for the current job, then unloads it.
- Vision is queued and preferably runs while idle/on charger.
- Query loads query embedding and only an experimentally justified reranker.
- LLM is remote through an explicitly configured provider such as OpenRouter, or runs as a separate local model lifecycle.
- Embedding, OCR, vision, reranker, and LLM must not occupy VRAM simultaneously by default.

## Action boundary

- AI may propose rename, move, and organization actions.
- Every filesystem mutation requires preview and explicit user approval.
- Execute approved actions through Windows `IFileOperation`, journal the proposal/result, then let USN reconcile the catalog.
- Delete always requires explicit approval.

