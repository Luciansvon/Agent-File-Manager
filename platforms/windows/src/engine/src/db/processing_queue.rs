//! Restart-safe ingestion queue backed by SQLite.

use anyhow::{Context, Result};
use rusqlite::{params, Connection, OptionalExtension};
use uuid::Uuid;

#[derive(Debug, Clone)]
pub struct NewJob<'a> {
    pub internal_asset_id: Option<&'a str>,
    pub path_text: Option<&'a str>,
    pub job_kind: &'a str,
    pub reason: &'a str,
    pub priority: i64,
    pub content_version: i64,
    pub dedupe_key: Option<&'a str>,
    pub max_attempts: i64,
    pub not_before_at: f64,
    pub created_at: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ClaimedJob {
    pub id: String,
    pub internal_asset_id: Option<String>,
    pub path_text: Option<String>,
    pub job_kind: String,
    pub reason: String,
    pub content_version: i64,
    pub attempts: i64,
    pub max_attempts: i64,
}

pub fn enqueue(conn: &Connection, job: &NewJob<'_>) -> Result<String> {
    anyhow::ensure!(job.internal_asset_id.is_some() || job.path_text.is_some(), "job needs an asset or path");
    anyhow::ensure!(job.content_version >= 1, "content version must be positive");
    anyhow::ensure!(job.max_attempts >= 1, "max attempts must be positive");
    let id = Uuid::new_v4().to_string();
    let inserted = conn.execute(
        "INSERT INTO processing_jobs (\
            id, internal_asset_id, path_text, job_kind, reason, priority, state, \
            content_version, dedupe_key, max_attempts, not_before_at, created_at, updated_at\
         ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, 'pending', ?7, ?8, ?9, ?10, ?11, ?11) \
         ON CONFLICT DO NOTHING",
        params![
            id,
            job.internal_asset_id,
            job.path_text,
            job.job_kind,
            job.reason,
            job.priority,
            job.content_version,
            job.dedupe_key,
            job.max_attempts,
            job.not_before_at,
            job.created_at,
        ],
    )
    .context("enqueueing processing job")?;
    if inserted == 1 {
        return Ok(id);
    }
    if let Some(dedupe_key) = job.dedupe_key {
        return conn
            .query_row(
                "SELECT id FROM processing_jobs WHERE dedupe_key = ?1 \
                 AND state IN ('pending', 'running') LIMIT 1",
                [dedupe_key],
                |row| row.get(0),
            )
            .context("reading existing deduplicated processing job");
    }
    anyhow::bail!("processing job was not inserted")
}

pub fn claim_next(conn: &Connection, now: f64) -> Result<Option<ClaimedJob>> {
    let tx = conn.unchecked_transaction().context("opening processing claim transaction")?;
    let candidate: Option<String> = tx
        .query_row(
            "SELECT id FROM processing_jobs \
             WHERE state = 'pending' AND not_before_at <= ?1 AND attempts < max_attempts \
             ORDER BY priority DESC, created_at ASC LIMIT 1",
            [now],
            |row| row.get(0),
        )
        .optional()
        .context("selecting next processing job")?;
    let Some(id) = candidate else {
        tx.commit().context("committing empty processing claim")?;
        return Ok(None);
    };
    tx.execute(
        "UPDATE processing_jobs SET state = 'running', attempts = attempts + 1, \
         started_at = ?1, updated_at = ?1, finished_at = NULL, last_error = NULL \
         WHERE id = ?2 AND state = 'pending'",
        params![now, id],
    )
    .context("claiming processing job")?;
    let claimed = tx
        .query_row(
            "SELECT id, internal_asset_id, path_text, job_kind, reason, \
             content_version, attempts, max_attempts FROM processing_jobs WHERE id = ?1",
            [&id],
            |row| {
                Ok(ClaimedJob {
                    id: row.get(0)?,
                    internal_asset_id: row.get(1)?,
                    path_text: row.get(2)?,
                    job_kind: row.get(3)?,
                    reason: row.get(4)?,
                    content_version: row.get(5)?,
                    attempts: row.get(6)?,
                    max_attempts: row.get(7)?,
                })
            },
        )
        .context("reading claimed processing job")?;
    tx.commit().context("committing processing claim")?;
    Ok(Some(claimed))
}

pub fn complete(conn: &Connection, id: &str, now: f64) -> Result<bool> {
    let updated = conn.execute(
        "UPDATE processing_jobs SET state = 'completed', updated_at = ?1, finished_at = ?1 \
         WHERE id = ?2 AND state = 'running'",
        params![now, id],
    )?;
    Ok(updated == 1)
}

pub fn fail(conn: &Connection, id: &str, error: &str, retry_at: f64, now: f64) -> Result<bool> {
    let updated = conn.execute(
        "UPDATE processing_jobs SET \
           state = CASE WHEN attempts < max_attempts THEN 'pending' ELSE 'failed' END, \
           not_before_at = CASE WHEN attempts < max_attempts THEN ?1 ELSE not_before_at END, \
           updated_at = ?2, finished_at = CASE WHEN attempts < max_attempts THEN NULL ELSE ?2 END, \
           last_error = ?3 \
         WHERE id = ?4 AND state = 'running'",
        params![retry_at, now, error, id],
    )?;
    Ok(updated == 1)
}

pub fn recover_interrupted(conn: &Connection, now: f64) -> Result<usize> {
    conn.execute(
        "UPDATE processing_jobs SET state = 'pending', started_at = NULL, updated_at = ?1, \
         not_before_at = MIN(not_before_at, ?1), last_error = 'engine_interrupted' \
         WHERE state = 'running'",
        [now],
    )
    .context("recovering interrupted processing jobs")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn db() -> Connection {
        let conn = Connection::open_in_memory().unwrap();
        crate::db::migrations::apply(&conn).unwrap();
        conn
    }

    fn job<'a>(dedupe_key: &'a str, priority: i64) -> NewJob<'a> {
        NewJob {
            internal_asset_id: None,
            path_text: Some(r"C:\\Inbox\\referensi.jpg"),
            job_kind: "vision",
            reason: "created",
            priority,
            content_version: 1,
            dedupe_key: Some(dedupe_key),
            max_attempts: 2,
            not_before_at: 0.0,
            created_at: 1.0,
        }
    }

    #[test]
    fn duplicate_active_job_returns_existing_id() {
        let conn = db();
        let first = enqueue(&conn, &job("vision:asset:1", 0)).unwrap();
        let second = enqueue(&conn, &job("vision:asset:1", 99)).unwrap();
        assert_eq!(first, second);
        let count: i64 = conn.query_row("SELECT COUNT(*) FROM processing_jobs", [], |row| row.get(0)).unwrap();
        assert_eq!(count, 1);
    }

    #[test]
    fn claim_uses_priority_then_creation_order() {
        let conn = db();
        let low = enqueue(&conn, &job("low", 1)).unwrap();
        let high = enqueue(&conn, &job("high", 10)).unwrap();
        let claimed = claim_next(&conn, 2.0).unwrap().unwrap();
        assert_eq!(claimed.id, high);
        assert_ne!(claimed.id, low);
        assert_eq!(claimed.attempts, 1);
    }

    #[test]
    fn failed_job_retries_then_becomes_terminal() {
        let conn = db();
        let id = enqueue(&conn, &job("retry", 0)).unwrap();
        assert_eq!(claim_next(&conn, 2.0).unwrap().unwrap().id, id);
        assert!(fail(&conn, &id, "temporary", 3.0, 2.5).unwrap());
        assert!(claim_next(&conn, 2.9).unwrap().is_none());
        assert_eq!(claim_next(&conn, 3.0).unwrap().unwrap().attempts, 2);
        assert!(fail(&conn, &id, "permanent", 4.0, 3.5).unwrap());
        let state: String = conn
            .query_row("SELECT state FROM processing_jobs WHERE id = ?1", [&id], |row| row.get(0))
            .unwrap();
        assert_eq!(state, "failed");
    }

    #[test]
    fn interrupted_running_job_returns_to_pending() {
        let conn = db();
        enqueue(&conn, &job("resume", 0)).unwrap();
        claim_next(&conn, 2.0).unwrap().unwrap();
        assert_eq!(recover_interrupted(&conn, 3.0).unwrap(), 1);
        assert!(claim_next(&conn, 3.0).unwrap().is_some());
    }
}
