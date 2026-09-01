//! NTFS USN journal reader and durable cursor handling.
//!
//! This layer reads metadata changes only; it never opens file content and
//! therefore cannot hydrate OneDrive placeholders.
#![allow(dead_code)]

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use rusqlite::{params, Connection, OptionalExtension};

const REASON_DATA_OVERWRITE: u32 = 0x0000_0001;
const REASON_DATA_EXTEND: u32 = 0x0000_0002;
const REASON_DATA_TRUNCATION: u32 = 0x0000_0004;
const REASON_NAMED_DATA_OVERWRITE: u32 = 0x0000_0010;
const REASON_NAMED_DATA_EXTEND: u32 = 0x0000_0020;
const REASON_NAMED_DATA_TRUNCATION: u32 = 0x0000_0040;
const REASON_FILE_CREATE: u32 = 0x0000_0100;
const REASON_FILE_DELETE: u32 = 0x0000_0200;
const REASON_RENAME_OLD_NAME: u32 = 0x0000_1000;
const REASON_RENAME_NEW_NAME: u32 = 0x0000_2000;
const REASON_CLOSE: u32 = 0x8000_0000;
const CONTENT_REASON_MASK: u32 = REASON_DATA_OVERWRITE
    | REASON_DATA_EXTEND
    | REASON_DATA_TRUNCATION
    | REASON_NAMED_DATA_OVERWRITE
    | REASON_NAMED_DATA_EXTEND
    | REASON_NAMED_DATA_TRUNCATION;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct JournalInfo {
    pub journal_id: u64,
    pub first_usn: i64,
    pub next_usn: i64,
    pub max_size: u64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct UsnRecord {
    pub file_ref: u64,
    pub parent_file_ref: u64,
    pub usn: i64,
    pub reason: u32,
    pub file_attributes: u32,
    pub name: String,
}

impl UsnRecord {
    pub fn is_create(&self) -> bool {
        self.reason & REASON_FILE_CREATE != 0
    }

    pub fn is_delete(&self) -> bool {
        self.reason & REASON_FILE_DELETE != 0
    }

    pub fn is_rename_old(&self) -> bool {
        self.reason & REASON_RENAME_OLD_NAME != 0
    }

    pub fn is_rename_new(&self) -> bool {
        self.reason & REASON_RENAME_NEW_NAME != 0
    }

    pub fn content_changed(&self) -> bool {
        self.reason & CONTENT_REASON_MASK != 0
    }

    pub fn is_close(&self) -> bool {
        self.reason & REASON_CLOSE != 0
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct JournalBatch {
    pub next_usn: i64,
    pub records: Vec<UsnRecord>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct ChangeIntent {
    pub file_ref: u64,
    pub last_usn: i64,
    pub deleted: bool,
    pub needs_reconcile: bool,
    pub content_changed: bool,
    pub renamed: bool,
    pub is_directory: bool,
}

/// Collapse the noisy per-write journal stream into one idempotent decision per
/// physical file. A delete wins over create/edit in the same batch. Replaying a
/// batch after a crash is safe because tombstones are stable and queue dedupe is
/// keyed by volume + FileId.
pub(crate) fn coalesce_records(records: &[UsnRecord]) -> Vec<ChangeIntent> {
    const FILE_ATTRIBUTE_DIRECTORY: u32 = 0x10;
    let mut changes = BTreeMap::<u64, ChangeIntent>::new();
    for record in records {
        let item = changes.entry(record.file_ref).or_insert(ChangeIntent {
            file_ref: record.file_ref,
            last_usn: record.usn,
            deleted: false,
            needs_reconcile: false,
            content_changed: false,
            renamed: false,
            is_directory: record.file_attributes & FILE_ATTRIBUTE_DIRECTORY != 0,
        });
        item.last_usn = item.last_usn.max(record.usn);
        item.deleted |= record.is_delete();
        item.content_changed |= record.content_changed();
        item.renamed |= record.is_rename_old() || record.is_rename_new();
        item.needs_reconcile |=
            record.is_create() || record.is_rename_new() || record.content_changed();
        item.is_directory |= record.file_attributes & FILE_ATTRIBUTE_DIRECTORY != 0;
    }
    for item in changes.values_mut() {
        if item.deleted {
            item.needs_reconcile = false;
        }
    }
    changes.into_values().collect()
}

pub(crate) trait FileIdResolver {
    fn resolve(&self, file_ref: u64) -> Result<Option<PathBuf>>;
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub(crate) struct DispatchSummary {
    pub tombstoned: usize,
    pub queued: usize,
    pub skipped: usize,
    pub unresolved: usize,
}

pub(crate) fn dispatch_batch<R: FileIdResolver>(
    conn: &Connection,
    resolver: &R,
    monitored_roots: &[PathBuf],
    volume_serial: u32,
    batch: &JournalBatch,
    now: f64,
) -> Result<DispatchSummary> {
    let mut summary = DispatchSummary::default();
    for change in coalesce_records(&batch.records) {
        if change.is_directory {
            summary.skipped += 1;
            continue;
        }
        if change.deleted {
            if crate::db::catalog::tombstone(
                conn,
                Some(volume_serial),
                Some(change.file_ref),
                None,
                Some(change.last_usn),
                now,
            )?
            .is_some()
            {
                summary.tombstoned += 1;
            } else {
                summary.skipped += 1;
            }
            continue;
        }
        if !change.needs_reconcile {
            summary.skipped += 1;
            continue;
        }
        let Some(path) = resolver.resolve(change.file_ref)? else {
            summary.unresolved += 1;
            continue;
        };
        if !is_eligible_changed_path(&path, monitored_roots) {
            summary.skipped += 1;
            continue;
        }
        let reason = if change.renamed {
            "renamed"
        } else if change.content_changed {
            "content_changed"
        } else {
            "created"
        };
        let path_text = path.to_string_lossy().to_string();
        let dedupe_key = format!("reconcile:{volume_serial:08x}:{:016x}", change.file_ref);
        crate::db::processing_queue::enqueue(
            conn,
            &crate::db::processing_queue::NewJob {
                internal_asset_id: None,
                path_text: Some(&path_text),
                job_kind: "reconcile_path",
                reason,
                priority: if change.content_changed { 20 } else { 10 },
                content_version: 1,
                dedupe_key: Some(&dedupe_key),
                max_attempts: 3,
                not_before_at: now,
                created_at: now,
            },
        )?;
        summary.queued += 1;
    }
    Ok(summary)
}

fn is_eligible_changed_path(path: &Path, monitored_roots: &[PathBuf]) -> bool {
    let Some(relative_path) = monitored_roots
        .iter()
        .filter_map(|root| path.strip_prefix(root).ok())
        .min_by_key(|relative| relative.components().count())
    else {
        return false;
    };
    if std::fs::symlink_metadata(path)
        .map(|metadata| !metadata.is_file())
        .unwrap_or(true)
    {
        return false;
    }
    const EXCLUDED_COMPONENTS: &[&str] = &[
        "$recycle.bin",
        "system volume information",
        "windows",
        "program files",
        "program files (x86)",
        "programdata",
        "node_modules",
        ".git",
        ".venv",
        "__pycache__",
        "appdata",
    ];
    if relative_path.components().any(|component| {
        let value = component.as_os_str().to_string_lossy();
        value.starts_with('.')
            || EXCLUDED_COMPONENTS
                .iter()
                .any(|excluded| value.eq_ignore_ascii_case(excluded))
    }) {
        return false;
    }
    let extension = path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    matches!(
        extension.as_str(),
        "jpg"
            | "jpeg"
            | "png"
            | "gif"
            | "webp"
            | "bmp"
            | "tif"
            | "tiff"
            | "heic"
            | "heif"
            | "raw"
            | "arw"
            | "cr2"
            | "nef"
            | "dng"
            | "pdf"
            | "docx"
            | "doc"
            | "odt"
            | "rtf"
            | "txt"
            | "md"
            | "xls"
            | "xlsx"
            | "pptx"
            | "csv"
            | "json"
            | "html"
            | "htm"
            | "mp4"
            | "mov"
            | "m4v"
            | "avi"
            | "mkv"
            | "webm"
            | "mp3"
            | "wav"
            | "flac"
            | "ogg"
            | "m4a"
            | "aac"
            | "opus"
    )
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct PersistedCursor {
    pub journal_id: u64,
    pub next_usn: i64,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum CursorDecision {
    ResumeAt(i64),
    FullReconcile,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum PollOutcome {
    FullReconcileRequired,
    Idle,
    Applied(DispatchSummary),
}

/// Cursor captured immediately before a full filesystem reconciliation.  It is
/// committed only after that reconciliation succeeds, so writes that happen
/// while the scan is running remain visible to the next USN poll.
#[cfg(windows)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) struct ReconcileSeed {
    volume_serial: u32,
    journal_id: u64,
    next_usn: i64,
}

#[cfg(windows)]
pub(crate) fn capture_reconcile_seed(
    conn: &Connection,
    scan_root: &Path,
) -> Result<Option<ReconcileSeed>> {
    if !scan_root.is_dir() {
        return Ok(None);
    }
    let volume_root = scan_root.ancestors().last().unwrap_or(scan_root);
    let info = query_journal(volume_root)?;
    let volume_serial = crate::platform::physical_file_identity(volume_root)
        .and_then(|identity| identity.volume_serial)
        .context("volume root has no Windows volume serial")?;
    let persisted = load_cursor(conn, &format!("{volume_serial:08x}"))?;
    if cursor_decision(info, persisted) != CursorDecision::FullReconcile {
        return Ok(None);
    }
    Ok(Some(ReconcileSeed {
        volume_serial,
        journal_id: info.journal_id,
        next_usn: info.next_usn,
    }))
}

#[cfg(windows)]
pub(crate) fn commit_reconcile_seed(
    conn: &Connection,
    seed: ReconcileSeed,
    completed_at: f64,
) -> Result<()> {
    save_cursor(
        conn,
        &format!("{:08x}", seed.volume_serial),
        seed.journal_id,
        seed.next_usn,
        completed_at,
    )
}

pub(crate) fn cursor_decision(
    info: JournalInfo,
    persisted: Option<PersistedCursor>,
) -> CursorDecision {
    match persisted {
        Some(cursor)
            if cursor.journal_id == info.journal_id
                && cursor.next_usn >= info.first_usn
                && cursor.next_usn <= info.next_usn =>
        {
            CursorDecision::ResumeAt(cursor.next_usn)
        }
        _ => CursorDecision::FullReconcile,
    }
}

pub(crate) fn load_cursor(conn: &Connection, volume_id: &str) -> Result<Option<PersistedCursor>> {
    conn.query_row(
        "SELECT journal_id, next_usn FROM usn_state WHERE volume_id = ?1",
        [volume_id],
        |row| {
            Ok(PersistedCursor {
                journal_id: row.get::<_, i64>(0)? as u64,
                next_usn: row.get(1)?,
            })
        },
    )
    .optional()
    .context("loading USN cursor")
}

pub(crate) fn save_cursor(
    conn: &Connection,
    volume_id: &str,
    journal_id: u64,
    next_usn: i64,
    polled_at: f64,
) -> Result<()> {
    conn.execute(
        "INSERT INTO usn_state (volume_id, journal_id, next_usn, last_polled_at) \
         VALUES (?1, ?2, ?3, ?4) \
         ON CONFLICT(volume_id) DO UPDATE SET journal_id = excluded.journal_id, \
           next_usn = excluded.next_usn, last_polled_at = excluded.last_polled_at",
        params![volume_id, journal_id as i64, next_usn, polled_at],
    )
    .context("saving USN cursor")?;
    Ok(())
}

#[cfg(windows)]
pub(crate) fn seed_cursor_after_full_reconcile(
    conn: &Connection,
    volume_root: &Path,
    polled_at: f64,
) -> Result<()> {
    let info = query_journal(volume_root)?;
    let volume_serial = crate::platform::physical_file_identity(volume_root)
        .and_then(|identity| identity.volume_serial)
        .context("volume root has no Windows volume serial")?;
    save_cursor(
        conn,
        &format!("{volume_serial:08x}"),
        info.journal_id,
        info.next_usn,
        polled_at,
    )
}

#[cfg(windows)]
pub(crate) fn poll_once(
    conn: &Connection,
    volume_root: &Path,
    monitored_roots: &[PathBuf],
    now: f64,
    max_records: usize,
) -> Result<PollOutcome> {
    let info = query_journal(volume_root)?;
    let volume_serial = crate::platform::physical_file_identity(volume_root)
        .and_then(|identity| identity.volume_serial)
        .context("volume root has no Windows volume serial")?;
    let volume_id = format!("{volume_serial:08x}");
    let persisted = load_cursor(conn, &volume_id)?;
    let start_usn = match cursor_decision(info, persisted) {
        CursorDecision::FullReconcile => return Ok(PollOutcome::FullReconcileRequired),
        CursorDecision::ResumeAt(cursor) => cursor,
    };
    if start_usn == info.next_usn {
        return Ok(PollOutcome::Idle);
    }
    let batch = read_journal(volume_root, start_usn, info.journal_id, max_records)?;
    let resolver = VolumeFileIdResolver::open(volume_root)?;
    let summary = dispatch_batch(
        conn,
        &resolver,
        monitored_roots,
        volume_serial,
        &batch,
        now,
    )?;
    save_cursor(conn, &volume_id, info.journal_id, batch.next_usn, now)?;
    Ok(PollOutcome::Applied(summary))
}

#[cfg(windows)]
fn open_volume(volume_root: &Path, desired_access: u32) -> Result<windows::Win32::Foundation::HANDLE> {
    use windows::core::PCWSTR;
    use windows::Win32::Storage::FileSystem::{
        CreateFileW, FILE_ATTRIBUTE_NORMAL, FILE_FLAG_BACKUP_SEMANTICS, FILE_SHARE_DELETE,
        FILE_SHARE_READ, FILE_SHARE_WRITE, OPEN_EXISTING,
    };

    let root = volume_root
        .ancestors()
        .last()
        .unwrap_or(volume_root)
        .to_string_lossy();
    let device = format!(r"\\.\{}", root.trim_end_matches(['\\', '/']));
    let mut wide: Vec<u16> = device.encode_utf16().collect();
    wide.push(0);
    let handle = unsafe {
        CreateFileW(
            PCWSTR(wide.as_ptr()),
            desired_access,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_ATTRIBUTE_NORMAL,
            None,
        )
        .context("opening NTFS volume")?
    };
    anyhow::ensure!(!handle.is_invalid(), "opening NTFS volume returned invalid handle");
    Ok(handle)
}

#[cfg(windows)]
#[repr(C)]
struct RawFileIdDescriptor {
    size: u32,
    kind: i32,
    file_id: i64,
    // FILE_ID_DESCRIPTOR's union is 16 bytes; FileId occupies its first 8.
    union_tail: i64,
}

#[cfg(windows)]
#[link(name = "kernel32")]
extern "system" {
    fn OpenFileById(
        volume: windows::Win32::Foundation::HANDLE,
        descriptor: *const RawFileIdDescriptor,
        desired_access: u32,
        share_mode: u32,
        security_attributes: *const std::ffi::c_void,
        flags_and_attributes: u32,
    ) -> windows::Win32::Foundation::HANDLE;
    fn GetFinalPathNameByHandleW(
        file: windows::Win32::Foundation::HANDLE,
        path: *mut u16,
        path_chars: u32,
        flags: u32,
    ) -> u32;
}

#[cfg(windows)]
pub(crate) struct VolumeFileIdResolver {
    handle: windows::Win32::Foundation::HANDLE,
}

#[cfg(windows)]
impl VolumeFileIdResolver {
    pub fn open(volume_root: &Path) -> Result<Self> {
        Ok(Self {
            // OpenFileById only needs a hint handle on the target volume; the
            // file itself is opened with desired access 0 (metadata query).
            handle: open_volume(volume_root, 0)?,
        })
    }
}

#[cfg(windows)]
impl FileIdResolver for VolumeFileIdResolver {
    fn resolve(&self, file_ref: u64) -> Result<Option<PathBuf>> {
        use windows::Win32::Foundation::CloseHandle;

        const FILE_ID_TYPE: i32 = 0;
        const FILE_SHARE_ALL: u32 = 0x1 | 0x2 | 0x4;
        const FILE_FLAG_BACKUP_SEMANTICS: u32 = 0x0200_0000;
        let descriptor = RawFileIdDescriptor {
            size: std::mem::size_of::<RawFileIdDescriptor>() as u32,
            kind: FILE_ID_TYPE,
            file_id: file_ref as i64,
            union_tail: 0,
        };
        let file = unsafe {
            OpenFileById(
                self.handle,
                &descriptor,
                0,
                FILE_SHARE_ALL,
                std::ptr::null(),
                FILE_FLAG_BACKUP_SEMANTICS,
            )
        };
        if file.is_invalid() {
            // Deletion/race is expected between journal read and resolution.
            return Ok(None);
        }

        let result = (|| -> Result<PathBuf> {
            let mut buffer = vec![0_u16; 512];
            let mut written = unsafe {
                GetFinalPathNameByHandleW(file, buffer.as_mut_ptr(), buffer.len() as u32, 0)
            };
            anyhow::ensure!(written != 0, "GetFinalPathNameByHandleW failed");
            if written as usize >= buffer.len() {
                buffer.resize(written as usize + 1, 0);
                written = unsafe {
                    GetFinalPathNameByHandleW(file, buffer.as_mut_ptr(), buffer.len() as u32, 0)
                };
                anyhow::ensure!(
                    written != 0 && (written as usize) < buffer.len(),
                    "GetFinalPathNameByHandleW returned unstable size"
                );
            }
            buffer.truncate(written as usize);
            let raw = String::from_utf16(&buffer).context("resolved path is invalid UTF-16")?;
            let normalized = if let Some(rest) = raw.strip_prefix(r"\\?\UNC\") {
                format!(r"\\{rest}")
            } else {
                raw.strip_prefix(r"\\?\").unwrap_or(&raw).to_string()
            };
            Ok(PathBuf::from(normalized))
        })();
        unsafe {
            let _ = CloseHandle(file);
        }
        result.map(Some)
    }
}

#[cfg(windows)]
impl Drop for VolumeFileIdResolver {
    fn drop(&mut self) {
        unsafe {
            let _ = windows::Win32::Foundation::CloseHandle(self.handle);
        }
    }
}

#[cfg(windows)]
pub(crate) fn query_journal(volume_root: &Path) -> Result<JournalInfo> {
    use windows::Win32::Foundation::CloseHandle;
    use windows::Win32::System::Ioctl::{FSCTL_QUERY_USN_JOURNAL, USN_JOURNAL_DATA_V0};
    use windows::Win32::System::IO::DeviceIoControl;

    let handle = open_volume(volume_root, 0)?;
    let mut data = USN_JOURNAL_DATA_V0::default();
    let mut returned = 0_u32;
    let result = unsafe {
        DeviceIoControl(
            handle,
            FSCTL_QUERY_USN_JOURNAL,
            None,
            0,
            Some((&mut data as *mut USN_JOURNAL_DATA_V0).cast()),
            std::mem::size_of::<USN_JOURNAL_DATA_V0>() as u32,
            Some(&mut returned),
            None,
        )
    };
    unsafe {
        let _ = CloseHandle(handle);
    }
    result.context("FSCTL_QUERY_USN_JOURNAL")?;
    anyhow::ensure!(
        returned as usize >= std::mem::size_of::<USN_JOURNAL_DATA_V0>(),
        "short USN journal query response"
    );
    Ok(JournalInfo {
        journal_id: data.UsnJournalID,
        first_usn: data.FirstUsn,
        next_usn: data.NextUsn,
        max_size: data.MaximumSize,
    })
}

#[repr(C)]
#[cfg(windows)]
struct ReadUsnJournalDataV0 {
    start_usn: i64,
    reason_mask: u32,
    return_only_on_close: u32,
    timeout: u64,
    bytes_to_wait_for: u64,
    journal_id: u64,
}

#[cfg(windows)]
pub(crate) fn read_journal(
    volume_root: &Path,
    start_usn: i64,
    journal_id: u64,
    max_records: usize,
) -> Result<JournalBatch> {
    use windows::Win32::Foundation::CloseHandle;
    use windows::Win32::System::Ioctl::FSCTL_READ_USN_JOURNAL;
    use windows::Win32::System::IO::DeviceIoControl;

    const GENERIC_READ: u32 = 0x8000_0000;
    let handle = open_volume(volume_root, GENERIC_READ)?;
    let input = ReadUsnJournalDataV0 {
        start_usn,
        reason_mask: u32::MAX,
        return_only_on_close: 0,
        timeout: 0,
        bytes_to_wait_for: 0,
        journal_id,
    };
    let mut buffer = vec![0_u8; 1024 * 1024];
    let mut returned = 0_u32;
    let result = unsafe {
        DeviceIoControl(
            handle,
            FSCTL_READ_USN_JOURNAL,
            Some((&input as *const ReadUsnJournalDataV0).cast()),
            std::mem::size_of::<ReadUsnJournalDataV0>() as u32,
            Some(buffer.as_mut_ptr().cast()),
            buffer.len() as u32,
            Some(&mut returned),
            None,
        )
    };
    unsafe {
        let _ = CloseHandle(handle);
    }
    result.context("FSCTL_READ_USN_JOURNAL")?;
    buffer.truncate(returned as usize);
    parse_journal_buffer(&buffer, max_records)
}

#[cfg(not(windows))]
pub(crate) fn query_journal(_volume_root: &Path) -> Result<JournalInfo> {
    anyhow::bail!("USN journal is only available on Windows / NTFS")
}

#[cfg(not(windows))]
pub(crate) fn read_journal(
    _volume_root: &Path,
    _start_usn: i64,
    _journal_id: u64,
    _max_records: usize,
) -> Result<JournalBatch> {
    anyhow::bail!("USN journal is only available on Windows / NTFS")
}

fn parse_journal_buffer(buffer: &[u8], max_records: usize) -> Result<JournalBatch> {
    anyhow::ensure!(buffer.len() >= 8, "USN response is shorter than its cursor");
    anyhow::ensure!(max_records > 0, "USN parser record limit must be positive");
    let system_next_usn = read_i64(buffer, 0)?;
    let mut offset = 8_usize;
    let mut records = Vec::new();
    while offset < buffer.len() && records.len() < max_records {
        anyhow::ensure!(buffer.len() - offset >= 60, "truncated USN_RECORD_V2 header");
        let record_length = read_u32(buffer, offset)? as usize;
        anyhow::ensure!(record_length >= 60, "invalid USN record length {record_length}");
        let end = offset.checked_add(record_length).context("USN record length overflow")?;
        anyhow::ensure!(end <= buffer.len(), "USN record exceeds response buffer");
        if read_u16(buffer, offset + 4)? == 2 {
            let name_len = read_u16(buffer, offset + 56)? as usize;
            let name_offset = read_u16(buffer, offset + 58)? as usize;
            anyhow::ensure!(name_len % 2 == 0, "odd UTF-16 filename length");
            let name_start = offset.checked_add(name_offset).context("name offset overflow")?;
            let name_end = name_start.checked_add(name_len).context("name length overflow")?;
            anyhow::ensure!(name_start >= offset + 60 && name_end <= end, "filename exceeds USN record");
            let utf16: Vec<u16> = buffer[name_start..name_end]
                .chunks_exact(2)
                .map(|pair| u16::from_le_bytes([pair[0], pair[1]]))
                .collect();
            records.push(UsnRecord {
                file_ref: read_u64(buffer, offset + 8)?,
                parent_file_ref: read_u64(buffer, offset + 16)?,
                usn: read_i64(buffer, offset + 24)?,
                reason: read_u32(buffer, offset + 40)?,
                file_attributes: read_u32(buffer, offset + 52)?,
                name: String::from_utf16_lossy(&utf16),
            });
        }
        offset = end;
    }
    // If the caller's bound cut a valid buffer short, resume from the final
    // processed record rather than advancing to Windows' end-of-buffer cursor
    // and silently skipping records. Re-reading the final record is harmless:
    // dispatch is idempotent and the durable queue has an active dedupe key.
    let next_usn = if offset >= buffer.len() {
        system_next_usn
    } else {
        records
            .last()
            .map(|record| record.usn)
            .context("USN record limit stopped before any record")?
    };
    Ok(JournalBatch { next_usn, records })
}

fn read_u16(buffer: &[u8], offset: usize) -> Result<u16> {
    let bytes = buffer.get(offset..offset + 2).context("short USN u16")?;
    Ok(u16::from_le_bytes(bytes.try_into().unwrap_or_default()))
}

fn read_u32(buffer: &[u8], offset: usize) -> Result<u32> {
    let bytes = buffer.get(offset..offset + 4).context("short USN u32")?;
    Ok(u32::from_le_bytes(bytes.try_into().unwrap_or_default()))
}

fn read_u64(buffer: &[u8], offset: usize) -> Result<u64> {
    let bytes = buffer.get(offset..offset + 8).context("short USN u64")?;
    Ok(u64::from_le_bytes(bytes.try_into().unwrap_or_default()))
}

fn read_i64(buffer: &[u8], offset: usize) -> Result<i64> {
    let bytes = buffer.get(offset..offset + 8).context("short USN i64")?;
    Ok(i64::from_le_bytes(bytes.try_into().unwrap_or_default()))
}

#[cfg(test)]
mod tests {
    use super::*;

    struct FakeResolver(BTreeMap<u64, PathBuf>);

    impl FileIdResolver for FakeResolver {
        fn resolve(&self, file_ref: u64) -> Result<Option<PathBuf>> {
            Ok(self.0.get(&file_ref).cloned())
        }
    }

    fn record(file_ref: u64, reason: u32, name: &str) -> Vec<u8> {
        let name_utf16: Vec<u16> = name.encode_utf16().collect();
        let length = 60 + name_utf16.len() * 2;
        let mut out = vec![0_u8; length];
        out[0..4].copy_from_slice(&(length as u32).to_le_bytes());
        out[4..6].copy_from_slice(&2_u16.to_le_bytes());
        out[8..16].copy_from_slice(&file_ref.to_le_bytes());
        out[16..24].copy_from_slice(&7_u64.to_le_bytes());
        out[24..32].copy_from_slice(&899_i64.to_le_bytes());
        out[40..44].copy_from_slice(&reason.to_le_bytes());
        out[52..56].copy_from_slice(&0x20_u32.to_le_bytes());
        out[56..58].copy_from_slice(&((name_utf16.len() * 2) as u16).to_le_bytes());
        out[58..60].copy_from_slice(&60_u16.to_le_bytes());
        for (index, unit) in name_utf16.into_iter().enumerate() {
            let start = 60 + index * 2;
            out[start..start + 2].copy_from_slice(&unit.to_le_bytes());
        }
        out
    }

    #[test]
    fn parses_v2_record_and_flags() {
        let mut buffer = 900_i64.to_le_bytes().to_vec();
        buffer.extend(record(42, REASON_RENAME_NEW_NAME | REASON_CLOSE, "Kursi.jpg"));
        let batch = parse_journal_buffer(&buffer, 100).unwrap();
        assert_eq!(batch.next_usn, 900);
        assert_eq!(batch.records[0].name, "Kursi.jpg");
        assert!(batch.records[0].is_rename_new());
        assert!(batch.records[0].is_close());
    }

    #[test]
    fn bounded_parser_does_not_skip_unprocessed_records() {
        let mut buffer = 1000_i64.to_le_bytes().to_vec();
        buffer.extend(record(41, REASON_FILE_CREATE, "a.jpg"));
        buffer.extend(record(42, REASON_FILE_CREATE, "b.jpg"));
        let batch = parse_journal_buffer(&buffer, 1).unwrap();
        assert_eq!(batch.records.len(), 1);
        assert_eq!(batch.next_usn, 899);
        assert_ne!(batch.next_usn, 1000);
    }

    #[test]
    fn coalesces_write_noise_and_delete_wins() {
        let records = vec![
            UsnRecord {
                file_ref: 9,
                parent_file_ref: 1,
                usn: 10,
                reason: REASON_DATA_EXTEND,
                file_attributes: 0x20,
                name: "a.jpg".into(),
            },
            UsnRecord {
                file_ref: 9,
                parent_file_ref: 1,
                usn: 11,
                reason: REASON_CLOSE,
                file_attributes: 0x20,
                name: "a.jpg".into(),
            },
            UsnRecord {
                file_ref: 9,
                parent_file_ref: 1,
                usn: 12,
                reason: REASON_FILE_DELETE,
                file_attributes: 0x20,
                name: "a.jpg".into(),
            },
        ];
        let changes = coalesce_records(&records);
        assert_eq!(changes.len(), 1);
        assert!(changes[0].deleted);
        assert!(changes[0].content_changed);
        assert!(!changes[0].needs_reconcile);
        assert_eq!(changes[0].last_usn, 12);
    }

    #[test]
    fn dispatches_delete_to_tombstone_and_create_to_durable_queue() {
        let dir = std::env::temp_dir().join(format!(
            "foldervision-usn-dispatch-{}-{:?}",
            std::process::id(),
            std::thread::current().id()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let old_path = dir.join("old.jpg");
        let new_path = dir.join("new.pdf");
        std::fs::write(&old_path, b"old").unwrap();
        std::fs::write(&new_path, b"new").unwrap();

        let conn = Connection::open_in_memory().unwrap();
        crate::db::migrations::apply(&conn).unwrap();
        let old_hash = [1_u8; 32];
        crate::db::catalog::observe(
            &conn,
            &crate::db::catalog::AssetObservation {
                path: &old_path,
                volume_serial: Some(77),
                file_ref: Some(42),
                size_bytes: 3,
                created_at: Some(1.0),
                modified_at: Some(1.0),
                content_hash: Some(&old_hash),
                last_usn: Some(1),
                kind: "image",
                extension: "jpg",
                metadata_only: false,
                observed_at: 1.0,
            },
        )
        .unwrap();

        let observed: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM files WHERE volume_serial = 77 AND file_ref = 42",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(observed, 1);

        let resolver = FakeResolver(BTreeMap::from([(43, new_path.clone())]));
        let batch = JournalBatch {
            next_usn: 100,
            records: vec![
                UsnRecord {
                    file_ref: 42,
                    parent_file_ref: 1,
                    usn: 90,
                    reason: REASON_FILE_DELETE,
                    file_attributes: 0x20,
                    name: "old.jpg".into(),
                },
                UsnRecord {
                    file_ref: 43,
                    parent_file_ref: 1,
                    usn: 91,
                    reason: REASON_FILE_CREATE | REASON_CLOSE,
                    file_attributes: 0x20,
                    name: "new.pdf".into(),
                },
            ],
        };
        let summary = dispatch_batch(&conn, &resolver, std::slice::from_ref(&dir), 77, &batch, 2.0)
            .unwrap();
        assert_eq!(summary.tombstoned, 1);
        assert_eq!(summary.queued, 1);
        let lifecycle: String = conn
            .query_row(
                "SELECT lifecycle_status FROM files WHERE file_ref = 42",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(lifecycle, "tombstone");
        let queued: i64 = conn
            .query_row("SELECT COUNT(*) FROM processing_jobs WHERE state = 'pending'", [], |row| {
                row.get(0)
            })
            .unwrap();
        assert_eq!(queued, 1);

        let _ = std::fs::remove_file(old_path);
        let _ = std::fs::remove_file(new_path);
        let _ = std::fs::remove_dir(dir);
    }

    #[test]
    fn rejects_malformed_record() {
        let mut buffer = 10_i64.to_le_bytes().to_vec();
        buffer.extend([0_u8; 60]);
        buffer[8..12].copy_from_slice(&999_u32.to_le_bytes());
        assert!(parse_journal_buffer(&buffer, 10).is_err());
    }

    #[test]
    fn cursor_requires_same_live_journal() {
        let info = JournalInfo { journal_id: 5, first_usn: 100, next_usn: 500, max_size: 1 };
        assert_eq!(
            cursor_decision(info, Some(PersistedCursor { journal_id: 5, next_usn: 250 })),
            CursorDecision::ResumeAt(250)
        );
        assert_eq!(
            cursor_decision(info, Some(PersistedCursor { journal_id: 4, next_usn: 250 })),
            CursorDecision::FullReconcile
        );
        assert_eq!(
            cursor_decision(info, Some(PersistedCursor { journal_id: 5, next_usn: 99 })),
            CursorDecision::FullReconcile
        );
    }

    #[test]
    fn cursor_round_trips_sqlite() {
        let conn = Connection::open_in_memory().unwrap();
        crate::db::migrations::apply(&conn).unwrap();
        save_cursor(&conn, "C:00112233", u64::MAX - 3, 456, 1.0).unwrap();
        assert_eq!(
            load_cursor(&conn, "C:00112233").unwrap(),
            Some(PersistedCursor { journal_id: u64::MAX - 3, next_usn: 456 })
        );
    }

    #[test]
    #[cfg(windows)]
    fn query_journal_returns_without_panicking() {
        let _ = query_journal(Path::new(r"C:\"));
    }
}
