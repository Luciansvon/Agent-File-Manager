//! Loopback-only Ollama client for the small local vision model.
//!
//! No model is pulled here. The user installs the model explicitly; this client
//! only probes and invokes an already-running local Ollama service.

use std::path::Path;
use std::time::Duration;

use anyhow::{bail, Context, Result};
use base64::Engine as _;
use serde::Deserialize;

pub const MODEL_KIND: &str = "qwen3_vl_2b_ollama";
pub const MODEL_NAME: &str = "qwen3-vl:2b-instruct";
const BASE_URL: &str = "http://127.0.0.1:11434";

#[derive(Clone)]
pub struct OllamaVisionClient {
    client: reqwest::Client,
}

#[derive(Deserialize)]
struct GenerateResponse {
    response: String,
}

impl OllamaVisionClient {
    pub fn new() -> Result<Self> {
        let client = reqwest::Client::builder()
            .no_proxy()
            .connect_timeout(Duration::from_secs(3))
            .timeout(Duration::from_secs(180))
            .build()
            .context("building loopback Ollama client")?;
        Ok(Self { client })
    }

    pub async fn require_installed(&self) -> Result<()> {
        let response = self
            .client
            .get(format!("{BASE_URL}/api/tags"))
            .send()
            .await
            .context("Ollama is not reachable on 127.0.0.1:11434")?;
        if !response.status().is_success() {
            bail!("Ollama model probe failed with HTTP {}", response.status());
        }
        let body: serde_json::Value = serde_json::from_slice(&response.bytes().await?)?;
        let installed = body
            .get("models")
            .and_then(serde_json::Value::as_array)
            .into_iter()
            .flatten()
            .filter_map(|model| {
                model
                    .get("name")
                    .or_else(|| model.get("model"))
                    .and_then(serde_json::Value::as_str)
            })
            .any(|name| name == MODEL_NAME);
        if !installed {
            bail!(
                "Local model {MODEL_NAME} is not installed. Folder Vision never pulls it automatically."
            );
        }
        Ok(())
    }

    pub async fn generate_json(
        &self,
        image_path: &Path,
        prompt: &str,
        keep_alive: &str,
    ) -> Result<String> {
        let bytes = tokio::fs::read(image_path)
            .await
            .with_context(|| format!("reading vision input {}", image_path.display()))?;
        let image = base64::engine::general_purpose::STANDARD.encode(bytes);
        let request = serde_json::json!({
            "model": MODEL_NAME,
            "prompt": prompt,
            "images": [image],
            "format": "json",
            "stream": false,
            "keep_alive": keep_alive,
            "options": {
                "temperature": 0,
                "num_predict": 180
            }
        });
        let response = self
            .client
            .post(format!("{BASE_URL}/api/generate"))
            .header(reqwest::header::CONTENT_TYPE, "application/json")
            .body(serde_json::to_vec(&request)?)
            .send()
            .await
            .context("calling local Ollama vision model")?;
        let status = response.status();
        let body = response.bytes().await?;
        if !status.is_success() {
            let detail = String::from_utf8_lossy(&body);
            bail!("Ollama vision request failed with HTTP {status}: {detail}");
        }
        let envelope: GenerateResponse =
            serde_json::from_slice(&body).context("decoding Ollama response envelope")?;
        Ok(envelope.response)
    }

    /// Release model RAM/VRAM after a visible batch. Best-effort at call sites:
    /// failure to unload must not invalidate already-persisted results.
    pub async fn unload(&self) -> Result<()> {
        let request = serde_json::json!({
            "model": MODEL_NAME,
            "keep_alive": 0,
            "stream": false
        });
        let response = self
            .client
            .post(format!("{BASE_URL}/api/generate"))
            .header(reqwest::header::CONTENT_TYPE, "application/json")
            .body(serde_json::to_vec(&request)?)
            .send()
            .await
            .context("requesting Ollama model unload")?;
        if !response.status().is_success() {
            bail!("Ollama unload failed with HTTP {}", response.status());
        }
        Ok(())
    }
}
