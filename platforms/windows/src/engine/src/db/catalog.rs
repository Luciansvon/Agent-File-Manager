//! Folder Vision lifecycle catalog.
//!
//! Paths are mutable locations. `(volume_serial, file_ref)` is the preferred
//! physical identity on NTFS, while `internal_asset_id` links that physical row
//! to semantic content that survives rename/move and tombstoning.
//!
//! `observe` is also the single-row reference implementation used by lifecycle
//! tests and USN fixtures. Production full scans inline the same transition in
//! `DbWriter` so one batch stays inside one transaction with cached statements.
#![allow(dead_code)]

use std::path::Path;

use anyhow::{Context, Result};
use rusqlite::{params, Connection, OptionalExtension};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct AssetObservation<'a> {
    pub path: &'a Path,
    pub volume_serial: Option<u32>,
    pub file_ref: Option<u64>,
    pub size_bytes: u64,
    pub created_at: Option<f64>,
    pub modified_at: Option<f64>,
    pub content_hash: Option<&'a [u8]>,
    pub last_usn: Option<i64>,
    pub kind: &'a str,
    pub extension: &'a str,
    pub metadata_only: bool,
    pub observed_at: f64,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct AssetUpdate {
    pub file_id: i64,
    pub internal_asset_id: String,
    pub moved: bool,
    pub revived: bool,
    pub content_changed: bool,
    pub content_version: i64,
}

#[derive(Debug)]
struct ExistingAsset {
    file_id: i64,
    internal_asset_id: String,
    path_text: String,
    content_hash: Option<Vec<u8>>,
    lifecycle_status: String,
    content_version: i64,
}

pub fn observe(conn: &Connection, observation: &AssetObservation<'_>) -> Result<AssetUpdate> {
    let path_text = observation.path.to_string_lossy().to_string();
    let path_hash = crate::util::path_safety::stable_path_hash(&path_text);
    let file_ref = observation.file_ref.map(|value| value as i64);
    let volume_serial = observation.volume_serial.map(i64::from);
    let size_bytes = i64::try_from(observation.size_bytes).context("file size exceeds SQLite INTEGER")?;
    let tx = conn.unchecked_transaction().context("opening catalog observation transaction")?;

    let mut existing = find_by_path(&tx, &path_text)?;
    if existing.is_none() {
        if let (Some(volume), Some(reference)) = (volume_serial, file_ref) {
            existing = find_by_physical_identity(&tx, volume, reference)?;
        }
    }
    if existing.is_none() {
        if let (Some(hash), Some(modified_at)) = (observation.content_hash, observation.modified_at) {
            existing = find_tombstone_by_content(&tx, hash, size_bytes, modified_at)?;
        }
    }

    let update = if let Some(existing) = existing {
        let moved = existing.path_text != path_text;
        let revived = existing.lifecycle_status != "active";
        let content_changed = matches!(
            (&existing.content_hash, observation.content_hash),
            (Some(previous), Some(current)) if previous.as_slice() != current
        );
        let content_version = if content_changed {
            existing.content_version.saturating_add(1)
        } else {
            existing.content_version
        };

        tx.execute(
            "UPDATE files SET \
                previous_path_text = CASE WHEN path_text <> ?1 THEN path_text ELSE previous_path_text END, \
                path_text = ?1, path_search = ?1, path_hash = ?2, \
                volume_serial = COALESCE(?3, volume_serial), \
                file_ref = COALESCE(?4, file_ref), size_bytes = ?5, \
                created_at = COALESCE(created_at, ?6), modified_at = ?7, scanned_at = ?8, \
                content_hash = COALESCE(?9, content_hash), last_usn = COALESCE(?10, last_usn), \
                kind = ?11, extension = ?12, metadata_only = ?13, \
                lifecycle_status = 'active', deleted_at = NULL, content_version = ?14 \
              WHERE id = ?15",
            params![
                path_text,
                path_hash,
                volume_serial,
                file_ref,
                size_bytes,
                observation.created_at,
                observation.modified_at,
                observation.observed_at,
                observation.content_hash,
                observation.last_usn,
                observation.kind,
                observation.extension,
                i64::from(observation.metadata_only),
                content_version,
                existing.file_id,
            ],
        )
        .context("updating observed catalog asset")?;

        ensure_semantic_row(
            &tx,
            &existing.internal_asset_id,
            observation.content_hash.or(existing.content_hash.as_deref()),
            content_version,
            observation.observed_at,
        )?;
        if content_changed {
            invalidate_changed_content(
                &tx,
                existing.file_id,
                &existing.internal_asset_id,
                observation.content_hash,
                content_version,
                observation.observed_at,
            )?;
        }

        AssetUpdate {
            file_id: existing.file_id,
            internal_asset_id: existing.internal_asset_id,
            moved,
            revived,
            content_changed,
            content_version,
        }
    } else {
        let internal_asset_id = Uuid::new_v4().to_string();
        tx.execute(
            "INSERT INTO files (\
                internal_asset_id, path_text, path_search, path_hash, volume_serial, file_ref, \
                size_bytes, created_at, modified_at, scanned_at, kind, extension, content_hash, \
                last_usn, lifecycle_status, content_version, metadata_only\
             ) VALUES (?1, ?2, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, 'active', 1, ?14)",
            params![
                internal_asset_id,
                path_text,
                path_hash,
                volume_serial,
                file_ref,
                size_bytes,
                observation.created_at,
                observation.modified_at,
                observation.observed_at,
                observation.kind,
                observation.extension,
                observation.content_hash,
                observation.last_usn,
                i64::from(observation.metadata_only),
            ],
        )
        .context("inserting observed catalog asset")?;
        let file_id = tx.last_insert_rowid();
        ensure_semantic_row(
            &tx,
            &internal_asset_id,
            observation.content_hash,
            1,
            observation.observed_at,
        )?;
        AssetUpdate {
            file_id,
            internal_asset_id,
            moved: false,
            revived: false,
            content_changed: observation.content_hash.is_some(),
            content_version: 1,
        }
    };

    tx.commit().context("committing catalog observation")?;
    Ok(update)
}

pub fn tombstone(
    conn: &Connection,
    volume_serial: Option<u32>,
    file_ref: Option<u64>,
    path: Option<&Path>,
    last_usn: Option<i64>,
    deleted_at: f64,
) -> Result<Option<String>> {
    let volume_serial = volume_serial.map(i64::from);
    let file_ref = file_ref.map(|value| value as i64);
    let path_text = path.map(|value| value.to_string_lossy().to_string());
    let tx = conn.unchecked_transaction().context("opening tombstone transaction")?;

    let existing = if let Some(path_text) = path_text.as_deref() {
        find_by_path(&tx, path_text)?
    } else if let (Some(volume), Some(reference)) = (volume_serial, file_ref) {
        find_by_physical_identity(&tx, volume, reference)?
    } else {
        None
    };

    let Some(existing) = existing else {
        tx.commit().context("committing empty tombstone transaction")?;
        return Ok(None);
    };
    tx.execute(
        "UPDATE files SET lifecycle_status = 'tombstone', deleted_at = ?1, \
         last_usn = COALESCE(?2, last_usn) WHERE id = ?3",
        params![deleted_at, last_usn, existing.file_id],
    )
    .context("marking asset tombstone")?;
    tx.commit().context("committing tombstone")?;
    Ok(Some(existing.internal_asset_id))
}

/// Tombstone one deleted path and, when it represented a directory, every
/// active descendant. The separator-bearing prefix prevents sibling names
/// such as `Downloads-old` from being included.
pub fn tombstone_path_tree(conn: &Connection, path: &Path, deleted_at: f64) -> Result<usize> {
    let path_text = path.to_string_lossy().to_string();
    let prefix = format!(
        "{}{}",
        path_text.trim_end_matches(['\\', '/']),
        std::path::MAIN_SEPARATOR
    );
    conn.execute(
        "UPDATE files SET lifecycle_status = 'tombstone', deleted_at = ?1 \
         WHERE lifecycle_status = 'active' AND (\
             path_text = ?2 COLLATE NOCASE OR \
             substr(path_text, 1, length(?3)) = ?3 COLLATE NOCASE\
         )",
        params![deleted_at, path_text, prefix],
    )
    .context("tombstoning deleted path tree")
}

fn find_by_path(conn: &Connection, path: &str) -> Result<Option<ExistingAsset>> {
    query_existing(
        conn,
        "SELECT id, internal_asset_id, path_text, content_hash, lifecycle_status, content_version \
         FROM files WHERE path_text = ?1 LIMIT 1",
        [path],
    )
}

fn find_by_physical_identity(
    conn: &Connection,
    volume_serial: i64,
    file_ref: i64,
) -> Result<Option<ExistingAsset>> {
    conn.query_row(
        "SELECT id, internal_asset_id, path_text, content_hash, lifecycle_status, content_version \
         FROM files WHERE volume_serial = ?1 AND file_ref = ?2 \
         ORDER BY (lifecycle_status = 'active') DESC, id DESC LIMIT 1",
        params![volume_serial, file_ref],
        map_existing,
    )
    .optional()
    .context("looking up physical asset identity")
}

fn find_tombstone_by_content(
    conn: &Connection,
    content_hash: &[u8],
    size_bytes: i64,
    modified_at: f64,
) -> Result<Option<ExistingAsset>> {
    conn.query_row(
        "SELECT id, internal_asset_id, path_text, content_hash, lifecycle_status, content_version \
         FROM files WHERE lifecycle_status = 'tombstone' AND content_hash = ?1 \
           AND size_bytes = ?2 AND ABS(modified_at - ?3) <= 2.0 \
         ORDER BY deleted_at DESC, id DESC LIMIT 1",
        params![content_hash, size_bytes, modified_at],
        map_existing,
    )
    .optional()
    .context("looking up conservative cross-volume tombstone match")
}

fn query_existing<P>(conn: &Connection, sql: &str, params: P) -> Result<Option<ExistingAsset>>
where
    P: rusqlite::Params,
{
    conn.query_row(sql, params, map_existing)
        .optional()
        .context("looking up catalog asset")
}

fn map_existing(row: &rusqlite::Row<'_>) -> rusqlite::Result<ExistingAsset> {
    Ok(ExistingAsset {
        file_id: row.get(0)?,
        internal_asset_id: row.get(1)?,
        path_text: row.get(2)?,
        content_hash: row.get(3)?,
        lifecycle_status: row.get(4)?,
        content_version: row.get(5)?,
    })
}

fn ensure_semantic_row(
    conn: &Connection,
    internal_asset_id: &str,
    content_hash: Option<&[u8]>,
    content_version: i64,
    now: f64,
) -> Result<()> {
    conn.execute(
        "INSERT INTO semantic_assets \
         (internal_asset_id, content_hash, content_version, created_at, updated_at) \
         VALUES (?1, ?2, ?3, ?4, ?4) \
         ON CONFLICT(internal_asset_id) DO UPDATE SET \
           content_hash = COALESCE(excluded.content_hash, content_hash), \
           content_version = excluded.content_version, updated_at = excluded.updated_at",
        params![internal_asset_id, content_hash, content_version, now],
    )
    .context("ensuring semantic asset row")?;
    Ok(())
}

pub(crate) fn invalidate_changed_content(
    conn: &Connection,
    file_id: i64,
    internal_asset_id: &str,
    content_hash: Option<&[u8]>,
    content_version: i64,
    now: f64,
) -> Result<()> {
    conn.execute("DELETE FROM content_chunks WHERE internal_asset_id = ?1", [internal_asset_id])?;
    for table in ["ocr_text", "doc_text", "clip_embeddings", "text_embeddings", "face_prints"] {
        conn.execute(&format!("DELETE FROM {table} WHERE file_id = ?1"), [file_id])?;
    }
    conn.execute(
        "DELETE FROM tags WHERE file_id = ?1 AND source IN ('auto', 'vlm')",
        [file_id],
    )?;
    conn.execute(
        "UPDATE semantic_assets SET content_hash = ?1, content_version = ?2, \
           canonical_text = NULL, shadow_cache_key = NULL, caption = NULL, \
           objects_json = NULL, materials_json = NULL, colors_json = NULL, \
           style_json = NULL, features_json = NULL, visual_embedding = NULL, \
           vision_model = NULL, vision_analyzed_hash = NULL, updated_at = ?3 \
         WHERE internal_asset_id = ?4",
        params![content_hash, content_version, now, internal_asset_id],
    )?;
    conn.execute(
        "UPDATE files SET phash = NULL, aesthetic = NULL, has_faces = 0, has_text = 0, \
           vlm_description = NULL, vlm_proposed_name = NULL, vlm_model = NULL, \
           vlm_analyzed_at = NULL WHERE id = ?1",
        [file_id],
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn db() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        crate::db::migrations::apply(&conn).unwrap();
        conn
    }

    fn observation<'a>(path: &'a Path, hash: &'a [u8]) -> AssetObservation<'a> {
        AssetObservation {
            path,
            volume_serial: Some(99),
            file_ref: Some(1234),
            size_bytes: 100,
            created_at: Some(10.0),
            modified_at: Some(20.0),
            content_hash: Some(hash),
            last_usn: Some(7),
            kind: "image",
            extension: "jpg",
            metadata_only: false,
            observed_at: 30.0,
        }
    }

    #[test]
    fn rename_preserves_asset_and_semantics() {
        let conn = db();
        let hash = [1_u8; 32];
        let first = observe(&conn, &observation(Path::new(r"C:\\old.jpg"), &hash)).unwrap();
        conn.execute(
            "UPDATE semantic_assets SET caption = 'kursi kayu' WHERE internal_asset_id = ?1",
            [&first.internal_asset_id],
        )
        .unwrap();

        let moved = observe(&conn, &observation(Path::new(r"C:\\baru.jpg"), &hash)).unwrap();
        assert_eq!(moved.file_id, first.file_id);
        assert_eq!(moved.internal_asset_id, first.internal_asset_id);
        assert!(moved.moved);
        assert!(!moved.content_changed);
        let (previous, caption): (String, String) = conn
            .query_row(
                "SELECT f.previous_path_text, s.caption FROM files f \
                 JOIN semantic_assets s USING (internal_asset_id) WHERE f.id = ?1",
                [first.file_id],
                |row| Ok((row.get(0)?, row.get(1)?)),
            )
            .unwrap();
        assert_eq!(previous, r"C:\\old.jpg");
        assert_eq!(caption, "kursi kayu");
    }

    #[test]
    fn content_edit_bumps_version_and_invalidates_vision() {
        let conn = db();
        let old_hash = [2_u8; 32];
        let first = observe(&conn, &observation(Path::new(r"C:\\edit.jpg"), &old_hash)).unwrap();
        conn.execute(
            "UPDATE semantic_assets SET caption = 'lama', vision_analyzed_hash = ?1 \
             WHERE internal_asset_id = ?2",
            params![old_hash.as_slice(), first.internal_asset_id],
        )
        .unwrap();

        let new_hash = [3_u8; 32];
        let changed = observe(&conn, &observation(Path::new(r"C:\\edit.jpg"), &new_hash)).unwrap();
        assert!(changed.content_changed);
        assert_eq!(changed.content_version, 2);
        let stale: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM semantic_assets \
                 WHERE internal_asset_id = ?1 AND (caption IS NOT NULL OR vision_analyzed_hash IS NOT NULL)",
                [&changed.internal_asset_id],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(stale, 0);
    }

    #[test]
    fn tombstone_restore_reuses_identity() {
        let conn = db();
        let hash = [4_u8; 32];
        let first = observe(&conn, &observation(Path::new(r"C:\\gone.pdf"), &hash)).unwrap();
        let deleted = tombstone(
            &conn,
            Some(99),
            Some(1234),
            Some(Path::new(r"C:\\gone.pdf")),
            Some(8),
            40.0,
        )
        .unwrap();
        assert_eq!(deleted.as_deref(), Some(first.internal_asset_id.as_str()));

        let restored = observe(&conn, &observation(Path::new(r"C:\\restored.pdf"), &hash)).unwrap();
        assert_eq!(restored.internal_asset_id, first.internal_asset_id);
        assert!(restored.revived);
        assert!(restored.moved);
    }

    #[test]
    fn tombstone_path_tree_removes_exact_path_and_descendants_only() {
        let conn = db();
        for (index, path) in [
            r"C:\Downloads\gone.txt",
            r"C:\Downloads\Folder\child.txt",
            r"C:\Downloads\Folder-old\keep.txt",
        ]
        .into_iter()
        .enumerate()
        {
            let hash = [7_u8 + index as u8; 32];
            let mut item = observation(Path::new(path), &hash);
            item.file_ref = Some(1234 + index as u64);
            observe(&conn, &item).unwrap();
        }

        assert_eq!(
            tombstone_path_tree(&conn, Path::new(r"C:\Downloads\gone.txt"), 50.0).unwrap(),
            1
        );
        assert_eq!(
            tombstone_path_tree(&conn, Path::new(r"C:\Downloads\Folder"), 51.0).unwrap(),
            1
        );
        let active: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM files WHERE lifecycle_status = 'active'",
                [],
                |row| row.get(0),
            )
            .unwrap();
        assert_eq!(active, 1);
    }

    #[test]
    fn one_drive_placeholder_is_metadata_only() {
        let conn = db();
        let mut placeholder = observation(Path::new(r"C:\\OneDrive\\cloud.docx"), &[5_u8; 32]);
        placeholder.content_hash = None;
        placeholder.metadata_only = true;
        let inserted = observe(&conn, &placeholder).unwrap();
        let metadata_only: i64 = conn
            .query_row("SELECT metadata_only FROM files WHERE id = ?1", [inserted.file_id], |row| row.get(0))
            .unwrap();
        assert_eq!(metadata_only, 1);
    }
}
