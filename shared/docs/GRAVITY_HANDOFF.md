# Gravity Handoff — Folder Vision AI MVP

Date: 2026-09-01
Branch: `codex/folder-vision-shell`
Repository: `C:\Users\shint\Documents\FolderVisionAI-FileID`

## User outcome

The intended workflow is:

```text
download image/document into Downloads
  -> detect automatically after the file settles
  -> parse/OCR or local vision
  -> propose a contextual filename
  -> recommend an existing destination folder
  -> one explicit Rename + Move approval
  -> journal + Undo
```

Do not download models, NuGet packages, or other large artifacts without explicit approval. The user is on metered data and has already had OneDrive hydration surprise them.

## Verified in the current worktree

- Rust engine builds at `platforms\windows\src\engine\target\debug\FileIDEngine.exe`.
- Core Release publish builds at `platforms\windows\src\FolderVision.Core\bin\x64\Release\net8.0-windows10.0.19041.0\win-x64\publish\FolderVision.Core.exe`.
- Both binaries were copied to the app output and SHA-256 compared equal.
- `FileID.App` Debug build passed with 0 warnings and 0 errors after the latest IPC change.
- A real image copied into `C:\Users\shint\Downloads` was detected by the background watcher without pressing Scan, scanned as a single file, analyzed by local `qwen3-vl:2b-instruct` in about 11 seconds, and persisted with `vlm_description` plus `vlm_proposed_name`.
- Persistent lexical search returned that image from its AI description without a new full scan.
- Isolated Rename + Move + Undo smoke passed: `Apply 1/1`, `Undo 1/1`, extension preserved, contextual name generated.
- Runtime delete smoke passed after the tombstone fix: new file became `active`, deletion changed it to `tombstone` within 20 seconds, and the physical file was gone.
- OneDrive placeholder smoke passed safely: an offline candidate was skipped with `totalFiles=0`, its `Offline` attribute remained set, and no content was opened. This proves no hydration, not metadata-row indexing.
- Core startup registration exists at `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\FolderVisionCore` and points to the staged `FolderVision.Core.exe`.
- Desktop shortcut exists at `C:\Users\shint\OneDrive\Desktop\Folder Vision AI.lnk` and targets the staged `FileID.exe`.

## Important implementation changes

- `FolderVision.Core` watches only `AutoManage` zones. Current default is Downloads; Desktop/Documents/OneDrive are IndexOnly.
- A watcher event settles the file, sends a single-file scan, then runs local Qwen vision for image/video/PDF inbox candidates.
- OneDrive cloud-only checks are metadata-only in Rust and C#, including thumbnail and VLM paths.
- `markPathDeleted` IPC was added so watcher delete/rename events tombstone exact paths or descendants without waiting for a full scan.
- Restructure planning is constrained to the selected library root and uses `vlm_proposed_name` while preserving the extension.
- AI rename remains review/approval-gated; do not reintroduce silent filesystem mutation.

## Remaining work — continue in this order

1. Launch the staged app and run a UI acceptance pass: Inbox shows the real Downloads test result, checkbox approval applies Rename + Move, Activity/history is visible, and Undo restores it. Do not apply a plan to the whole user library.
2. Complete OneDrive UX. Manual selection of a locally mounted OneDrive root must list local files while skipping online-only files; decide and implement whether skipped placeholders should get `metadata_only=1` catalog rows. Never hydrate them.
3. Run isolated document fixtures end-to-end for PDF/DOCX/XLSX/PPTX plus scanned PDF/JPG OCR, and verify `semantic.cache` canonical Markdown and chunk FTS persistence.
4. Finish or explicitly scope the AI workspace: current production surface is AI Search/Inbox, while the chat-first Ask Files/RAG flow with source filename, exact path, and page/sheet citation is still incomplete.
5. Semantic vector search is not active in the current install: `clip_embeddings=0` and `text_embeddings=0` because optional model packs are absent. Benchmark lexical first; request approval before any model download.
6. Prove UI-close/Core-lifecycle and Windows-login auto-start with exactly one Core and one engine. Current Run registration points to a Debug project path, so release packaging must install/update that path rather than preserve a dev-only registration.
7. Run the full solution/test gates only if package assets are already available. The app test project previously lacked `project.assets.json`; do not restore on metered data without approval.
8. Add the remaining scale proof: 100k-style corpus, backlog throughput, MFT initial enumeration/journal-gap reconciliation, and installer/release candidate. USN parser/poller is source-wired but not a complete stress proof.

## Commands

```powershell
cd C:\Users\shint\Documents\FolderVisionAI-FileID\platforms\windows
dotnet build src\FileID.App\FileID.App.csproj -c Debug -p:Platform=x64 --no-restore
dotnet publish src\FolderVision.Core\FolderVision.Core.csproj -c Release -r win-x64 -p:Platform=x64 --no-restore
```

For the isolated rename/move proof:

```powershell
cd C:\Users\shint\Documents\FolderVisionAI-FileID
& .\platforms\windows\build\mvp-inbox-smoke.ps1 `
  -SourceImage C:\Users\shint\AppData\Local\Temp\codex-clipboard-2a7caeba-1ab6-4131-b0b8-61be7af070bb.png `
  -EngineExe .\platforms\windows\src\engine\target\debug\FileIDEngine.exe
```

## Safety boundaries

- Preserve all existing dirty changes; do not reset or clean the worktree broadly.
- Do not scan `C:\Users\shint` automatically again.
- Do not read or hydrate OneDrive online-only content.
- Do not delete user files. Filesystem changes require preview and explicit approval; delete requires a separate confirmation and Recycle Bin behavior.
- Do not claim MVP complete from source inspection alone. Keep build, runtime, UI, installer, and scale evidence separate.
