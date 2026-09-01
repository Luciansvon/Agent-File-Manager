//! Canonical text preparation and the optional shadow-Markdown cache.
//!
//! SQLite (`semantic_assets` + `content_chunks`) is authoritative. Shadow files
//! are deterministic, content-addressed derivatives that may be deleted and
//! regenerated without losing indexed content.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

const MAX_CHUNK_BYTES: usize = 1_600;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ContentChunk {
    pub ordinal: usize,
    pub heading: Option<String>,
    pub byte_offset: usize,
    pub text: String,
}

#[derive(Debug, Clone)]
pub struct PreparedSemanticContent {
    pub cache_key: String,
    pub canonical_text: String,
    pub markdown: String,
    pub chunks: Vec<ContentChunk>,
}

pub fn prepare(kind: &str, content_hash: &[u8; 32], text: &str) -> Option<PreparedSemanticContent> {
    let canonical_text = normalize_text(text);
    if canonical_text.is_empty() {
        return None;
    }

    let cache_key = hash_hex(content_hash);
    let markdown = format!(
        "---\ncontent_hash: {cache_key}\nkind: {}\n---\n\n{}\n",
        yaml_scalar(kind),
        canonical_text
    );
    let chunks = chunk_text(&canonical_text);
    Some(PreparedSemanticContent {
        cache_key,
        canonical_text,
        markdown,
        chunks,
    })
}

/// Persist a derived shadow file atomically. Existing content-addressed files
/// are immutable and therefore need no rewrite on rename/move or repeat scans.
pub fn write_shadow(cache_key: &str, markdown: &str) -> Result<PathBuf> {
    let root = crate::paths::semantic_cache_dir()?;
    let prefix = cache_key.get(..2).unwrap_or("00");
    let dir = root.join(prefix);
    std::fs::create_dir_all(&dir)
        .with_context(|| format!("creating semantic cache directory {}", dir.display()))?;

    let destination = dir.join(format!("{cache_key}.md"));
    if destination.exists() {
        return Ok(destination);
    }

    let temporary = temporary_path(&destination);
    std::fs::write(&temporary, markdown.as_bytes())
        .with_context(|| format!("writing semantic cache temporary file {}", temporary.display()))?;
    match std::fs::rename(&temporary, &destination) {
        Ok(()) => Ok(destination),
        Err(_) if destination.exists() => {
            let _ = std::fs::remove_file(&temporary);
            Ok(destination)
        }
        Err(error) => {
            let _ = std::fs::remove_file(&temporary);
            Err(error).with_context(|| {
                format!("publishing semantic cache file {}", destination.display())
            })
        }
    }
}

fn temporary_path(destination: &Path) -> PathBuf {
    let file_name = destination
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or("semantic.md");
    destination.with_file_name(format!(".{file_name}.{}.tmp", std::process::id()))
}

fn normalize_text(text: &str) -> String {
    text.replace("\r\n", "\n")
        .replace('\r', "\n")
        .trim()
        .to_string()
}

fn yaml_scalar(value: &str) -> String {
    format!("\"{}\"", value.replace('\\', "\\\\").replace('"', "\\\""))
}

fn hash_hex(hash: &[u8; 32]) -> String {
    let mut output = String::with_capacity(hash.len() * 2);
    for byte in hash {
        use std::fmt::Write as _;
        let _ = write!(output, "{byte:02x}");
    }
    output
}

fn chunk_text(text: &str) -> Vec<ContentChunk> {
    let mut sections: Vec<(Option<String>, usize, usize)> = Vec::new();
    let mut heading: Option<String> = None;
    let mut body_start = 0usize;
    let mut offset = 0usize;

    for line in text.split_inclusive('\n') {
        if let Some(next_heading) = markdown_heading(line) {
            push_section(&mut sections, heading.take(), body_start, offset, text);
            heading = Some(next_heading);
            body_start = offset + line.len();
        }
        offset += line.len();
    }
    push_section(&mut sections, heading, body_start, text.len(), text);

    let mut chunks = Vec::new();
    for (heading, start, end) in sections {
        split_section(text, heading, start, end, &mut chunks);
    }
    if chunks.is_empty() && !text.trim().is_empty() {
        split_section(text, None, 0, text.len(), &mut chunks);
    }
    for (ordinal, chunk) in chunks.iter_mut().enumerate() {
        chunk.ordinal = ordinal;
    }
    chunks
}

fn markdown_heading(line: &str) -> Option<String> {
    let trimmed = line.trim();
    let content = trimmed.strip_prefix('#')?.trim_start_matches('#').trim();
    (!content.is_empty()).then(|| content.to_string())
}

fn push_section(
    sections: &mut Vec<(Option<String>, usize, usize)>,
    heading: Option<String>,
    start: usize,
    end: usize,
    text: &str,
) {
    let (start, end) = trim_span(text, start, end);
    if start < end {
        sections.push((heading, start, end));
    }
}

fn split_section(
    text: &str,
    heading: Option<String>,
    mut start: usize,
    end: usize,
    chunks: &mut Vec<ContentChunk>,
) {
    while start < end {
        let mut boundary = (start + MAX_CHUNK_BYTES).min(end);
        while boundary > start && !text.is_char_boundary(boundary) {
            boundary -= 1;
        }
        if boundary < end {
            let candidate = &text[start..boundary];
            if let Some(relative) = candidate.rfind("\n\n") {
                boundary = start + relative + 2;
            } else if let Some((relative, whitespace)) =
                candidate.char_indices().rfind(|(_, ch)| ch.is_whitespace())
            {
                boundary = start + relative + whitespace.len_utf8();
            }
        }

        let (trimmed_start, trimmed_end) = trim_span(text, start, boundary);
        if trimmed_start < trimmed_end {
            chunks.push(ContentChunk {
                ordinal: 0,
                heading: heading.clone(),
                byte_offset: trimmed_start,
                text: text[trimmed_start..trimmed_end].to_string(),
            });
        }
        start = boundary.max(start + 1);
        while start < end {
            let next = text[start..].chars().next().expect("valid UTF-8 boundary");
            if !next.is_whitespace() {
                break;
            }
            start += next.len_utf8();
        }
    }
}

fn trim_span(text: &str, mut start: usize, mut end: usize) -> (usize, usize) {
    while start < end {
        let ch = text[start..end].chars().next().expect("valid UTF-8 boundary");
        if !ch.is_whitespace() {
            break;
        }
        start += ch.len_utf8();
    }
    while end > start {
        let ch = text[start..end].chars().next_back().expect("valid UTF-8 boundary");
        if !ch.is_whitespace() {
            break;
        }
        end -= ch.len_utf8();
    }
    (start, end)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn headings_are_preserved_as_chunk_context() {
        let chunks = chunk_text("Pembuka\n\n# Material\nKayu jati solid\n\n# Ukuran\n80 x 60 cm");
        assert_eq!(chunks.len(), 3);
        assert_eq!(chunks[1].heading.as_deref(), Some("Material"));
        assert_eq!(chunks[1].text, "Kayu jati solid");
        assert_eq!(chunks[2].heading.as_deref(), Some("Ukuran"));
        assert!(chunks.windows(2).all(|pair| pair[0].ordinal < pair[1].ordinal));
    }

    #[test]
    fn same_content_hash_has_stable_cache_key() {
        let hash = [0xabu8; 32];
        let first = prepare("document", &hash, "isi dokumen").unwrap();
        let second = prepare("document", &hash, "isi dokumen").unwrap();
        assert_eq!(first.cache_key, second.cache_key);
        assert_eq!(first.markdown, second.markdown);
        assert_eq!(first.cache_key.len(), 64);
    }

    #[test]
    fn oversized_unicode_text_splits_on_valid_boundaries() {
        let text = "kursi rotan ".repeat(400);
        let chunks = chunk_text(&text);
        assert!(chunks.len() > 1);
        assert!(chunks.iter().all(|chunk| chunk.text.len() <= MAX_CHUNK_BYTES));
        assert!(chunks.iter().all(|chunk| text.is_char_boundary(chunk.byte_offset)));
    }
}
