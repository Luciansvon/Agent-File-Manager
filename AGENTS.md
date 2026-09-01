# FileID — multi-platform repo

On-device AI file organizer: tag, dedupe, restructure, and rename tens of thousands of files locally — no cloud, no telemetry — on every major desktop OS.

## Layout

```
FileID/
├── platforms/
│   ├── apple/      ← macOS — Swift / SwiftUI / MLX / GRDB
│   ├── windows/    ← Windows — Rust engine ('fileid-engine') + WinUI 3 / .NET 8
│   └── linux/      ← Rust engine + native GTK4 / libadwaita app
├── shared/
│   ├── ipc-schema/ ← canonical IPC contract (JSON Schema → Swift/Rust/C# DTOs)
│   ├── docs/       ← cross-platform docs (see Persistence files)
│   ├── test-corpus/← shared regression corpus + assertions
│   └── scripts/    ← cross-platform helpers (model export/install)
└── README.md
```

All three desktop apps implement six tabs (Library · People · Cleanup · Deep Analyze · Restructure · Settings). macOS remains the **visual + behavioral reference**; the commercial-clean model stack is wired on every platform, with native hardware, packaging, signing, and hosted-CI release gates documented in `shared/docs/NEXT.md` and `shared/docs/SHIP.md`.

## Per-platform dev guides

Read the one for the work in front of you:
- `platforms/windows/CLAUDE.md` — Rust engine, WinUI 3, ONNX Runtime (DirectML/CUDA/…), llama.cpp.
- `platforms/apple/CLAUDE.md` — Swift engine + SwiftUI app, MLX, GRDB.
- `platforms/linux/CLAUDE.md` — Rust engine client, GTK4/libadwaita, and Linux packaging.

## Cross-platform principles (apply everywhere)

- **No telemetry, ever.** No analytics, crash-reporting, update pings, or download instrumentation. The only network egress is user-initiated model downloads from `huggingface.co`. CI scans every shipped binary for telemetry strings as a release blocker. Never propose a feature that violates this.
- **Commercial-clean, Apache-2.0 project.** FileID is Apache-2.0 (root `LICENSE`); the core weight stack is Apache-2.0/MIT, and no non-commercial-only weights may ship. Optional restricted models such as Gemma are commercially usable under separately accepted upstream terms. New models go through `shared/docs/MODELS.md` with the license and acceptance policy vetted.
- **Performance is a feature.** Match or beat the macOS pipeline (≥140 files/s on comparable mid-tier hardware). Use the GPU/NPU when present; degrade gracefully to CPU.
- **The IPC contract is the contract.** Anything new lands in `shared/ipc-schema/ipc.schema.json` first; the per-platform DTOs mirror it. Schema drift = build break.
- **macOS is the visual reference; ports are 1:1.** Same palette (gold `#FFCC00`, lavender `#B19BCE`, cyan `#A0E2EA`, pink `#F2A6C0`), same springs (response 0.35–0.4 / dampingFraction 0.78–0.8), same `LavaLampBackground`. Native primitives per platform — never web tech.
- **No new dependencies without asking.** Locked sets per platform, documented in the platform guide; new crates/packages need a `DECISIONS.md` justification.
- **Default to no comments.** Add one only when the *why* is non-obvious (workaround, invariant, perf pitfall). Don't narrate the code.

## Folder Vision Windows fork direction

`shared/docs/FOLDER_VISION_ARCHITECTURE.md` is the newest Windows architecture authority. The FINAL PRD and MVP still define product scope and milestone order where they do not conflict with it. Preserve the FileID Rust engine, WinUI 3, SQLite, IPC, local-first processing, performance, and no-telemetry rules.

- Build an always-on `FolderVision.Core` process that owns the Rust engine, indexing state, watchers, queues, models, automation, and tray. Closing `FolderVision.UI` must not stop Core.
- The primary UI is chat-first. MVP navigation is **Chat**, **Inbox**, **Library**, **Activity**, and **Settings**. Rename and organize are review/activity workflows, not mandatory top-level workspaces.
- There is no primary select-one-folder flow. Build whole-disk metadata awareness from MFT + USN on NTFS; `FileSystemWatcher` is fallback only. Classify content eligibility as Auto-manage, Index-only, or Protected. Auto-manage means eligible for background enrichment, never permission to mutate files.
- Separate physical identity (volume serial, Windows FileId, path history, hash, lifecycle) from semantic identity. Rename/move must not create a new asset; cross-volume correlation uses hash + size + timestamps; delete creates a tombstone excluded from active results.
- Search uses persistent FTS/vector/metadata indexes only and must never trigger a full scan, OCR pass, or embedding rebuild.
- New/changed files enter a persistent bounded queue after a settle check. Process only the affected file; unchanged files are skipped and pending work resumes after restart.
- Use the cheapest native/light document parser first and OCR/specialist parsing only when extracted content is unusable. SQLite is canonical; shadow Markdown is one compressed content-addressed artifact per content hash, while chunks live in DB.
- Search baseline is BM25/FTS plus `multilingual-e5-small`. Translation is not a dependency. Fusion and rerankers are production-eligible only after lexical/dense/hybrid/reranked benchmarks on real Indonesian queries.
- Vision enriches an image once on creation and reruns only after content-hash/pixel change. Rename/move updates physical identity only; search never invokes vision.
- Heavy embedder, OCR, vision, reranker, and LLM workloads must not remain loaded together. Idle means no heavy model in RAM/VRAM; queue vision for idle/charger conditions.
- AI only proposes rename/move/organize. Every mutation uses preview + explicit approval + Windows `IFileOperation`, then USN reconciles the DB. Delete always requires explicit confirmation.
- OneDrive cloud-only placeholders are metadata-only and never hydrated automatically. Background startup performs no silent model/runtime downloads; installed local models may be warmed without network access.
- Implement milestones in MVP order and keep proof distinct: M0 baseline, M1 background core, M2 ingestion, M3 retrieval, M4 incremental automation, M5 intelligence, M6 safe actions, M7 chat, M8 hardening, M9 release candidate.

## How we work

- **Verify, don't assume.** The Windows engine + app compile, lint, and test headlessly in the dev env — self-verify every change (`cargo clippy --all-targets -D warnings`, `cargo test`; `dotnet build`/`test`/`format --verify-no-changes`). `cargo check` passing is not proof of correctness; the WinUI runtime/GPU path and all macOS Swift need the user's hardware.
- **On-hardware checks** run on the dev RTX 2060 against the `G:\TrueNAS` corpus via `platforms/windows/build/iterate.ps1` (+ `scan_assertions.py`). Tune ML thresholds against real data, not by guess.
- **Land work on a branch, then merge to `main` and confirm GitHub CI is green** (engine + app workflows). Commit/push when asked.
- **Keep the record current:** newest entry on top of `STATE.md`; update `NEXT.md`; append non-obvious calls to `DECISIONS.md`; record actual work in `WORKLOG.md` and resolved errors in `ERROR_SOLUTIONS.md`.
- Preserve the user's signature touches: `LavaLampBackground` (and its Win2D port), the gold palette, springs-everywhere motion.

## Persistence files

- `shared/docs/README.md` — documentation hub and reading order.
- `shared/docs/STATE.md` — session log (newest first).
- `shared/docs/NEXT.md` — next-session priorities + acceptance criteria.
- `shared/docs/WORKLOG.md` — chronological work record with actual validation.
- `shared/docs/DECISIONS.md` — append-only rationale (cross-platform).
- `shared/docs/ERROR_SOLUTIONS.md` — resolved error root causes and evidence; open bugs stay in `BUGS.md`.
- `shared/docs/MODELS.md` — canonical model registry + licenses.
- `shared/docs/ARCHITECTURE.md` — two-binary IPC design, scan pipeline, ML stack.
- `shared/docs/RESTRUCTURE.md` — butler-grade restructure design + phased build.
- `shared/docs/SHIP.md` — v1.0 release-readiness inventory.
- `~/.Codex/projects/<project-key>/memory/MEMORY.md` — auto-memory index.
