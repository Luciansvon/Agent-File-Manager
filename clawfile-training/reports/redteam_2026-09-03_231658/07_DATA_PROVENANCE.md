# Data Provenance & Isolasi Soal Ujian (Anti-Leakage Guarantee)
Dokumen ini membuktikan asal-usul data uji yang digunakan dalam Red Team Suite v2.

---

## 1. Jaminan Isolasi Mutlak (Immutable Benchmark Isolation)
- **Kontrak Keras Proyek:** `benchmarks/frozen_test_benchmark.jsonl` DILARANG KERAS digunakan untuk data latihan, data tuning, atau adversarial mining.
- Seluruh 24 kasus uji red team dibuat secara independen khusus untuk pengujian ketahanan keamanan dan tidak pernah dicampurkan ke dalam dataset latihan model (`dataset_train_v*.jsonl`).

---

## 2. Inventaris Kasus & SHA-256 Payload

| ID Kasus | Kategori | Subkategori | SHA-256 Payload | Berkas Artefak |
| :--- | :--- | :--- | :--- | :--- |
| IPI-001 | indirect_prompt_injection | pdf_content | `e433a26514f1b376...` | `05_evidence/artifacts/IPI-001_faktur_pembelian.pdf` |
| IPI-002 | indirect_prompt_injection | exif_metadata | `9a2d3ab20b890dd0...` | `05_evidence/artifacts/IPI-002_render_kursi.jpg` |
| IPI-003 | indirect_prompt_injection | filename_injection | `cd049e864d3a655f...` | `05_evidence/artifacts/IPI-003_payload_filename.docx` |
| IPI-004 | indirect_prompt_injection | caption_injection | `290686e13102d92f...` | `05_evidence/artifacts/IPI-004_keterangan_palsu.txt` |
| HIJACK-001 | agent_hijack | destructive_purge | `a8e8c540d08b8c17...` | `05_evidence/artifacts/HIJACK-001_rekap_kas.xlsx` |
| HIJACK-002 | agent_hijack | honeypot_exfiltration | `244a15cee9a56cce...` | `05_evidence/artifacts/HIJACK-002_perintah_curi.txt` |
| HIJACK-003 | agent_hijack | readonly_vault_breach | `f3d6585f0b8c658d...` | `05_evidence/artifacts/HIJACK-003_trojan_config.cfg` |
| VLM-001 | visual_injection_vlm | figstep_typography | `5458bb8f0ab77ed8...` | `05_evidence/artifacts/VLM-001_figstep_kursi.png` |
| VLM-002 | visual_injection_vlm | hidden_overlay_contrast | `6e371bb1f66c77b9...` | `05_evidence/artifacts/VLM-002_samar_overlay.jpg` |
| VLM-003 | visual_injection_vlm | adversarial_watermark | `d860ac9adf3edfb3...` | `05_evidence/artifacts/VLM-003_watermark_direktif.png` |
| PAIR-001 | algorithmic_auto_attack | pair_slang_jailbreak | `cc5821b373afceae...` | `05_evidence/artifacts/PAIR-001_chat_turn.json` |
| TAP-002 | algorithmic_auto_attack | tap_tree_pruning | `bdbaa28f933debad...` | `05_evidence/artifacts/TAP-002_tree_branch.json` |
| FUZZ-001 | filesystem_fuzzing | path_traversal | `b93917995a768009...` | `05_evidence/artifacts/FUZZ-001_traversal.txt` |
| FUZZ-002 | filesystem_fuzzing | ntfs_alternate_data_stream | `fb1ce90f9380210a...` | `05_evidence/artifacts/FUZZ-002_ads.txt` |
| FUZZ-003 | filesystem_fuzzing | reserved_dos_names | `6e75eeaeec0aa749...` | `05_evidence/artifacts/FUZZ-003_dos_reserved.txt` |
| FUZZ-004 | filesystem_fuzzing | max_path_overflow | `972f2c7e219bd040...` | `05_evidence/artifacts/FUZZ-004_long_path.txt` |
| FUZZ-005 | filesystem_fuzzing | unicode_rlo_spoofing | `b7d7a3e222c1993e...` | `05_evidence/artifacts/FUZZ-005_rlo_spoof.txt` |
| FUZZ-006 | filesystem_fuzzing | symlink_loop_trap | `656564bcfbd3db47...` | `05_evidence/artifacts/FUZZ-006_symlink.txt` |
| GROUND-001 | grounding_hallucination | fictitious_ghost_file | `e3b0c44298fc1c14...` | `05_evidence/artifacts/GROUND-001_kosong.txt` |
| GROUND-002 | grounding_hallucination | contradictory_metadata | `ed07f5212cf16b71...` | `05_evidence/artifacts/GROUND-002_kontradiksi.jpg` |
| GROUND-003 | grounding_hallucination | duplicate_collision_prevention | `d734571e9a76b4d7...` | `05_evidence/artifacts/GROUND-003_duplikat.pdf` |
| OVERFLOW-001 | context_overflow | token_flooding_800plus | `140c63309190eeed...` | `05_evidence/artifacts/OVERFLOW-001_flood.txt` |
| OVERFLOW-002 | context_overflow | system_prompt_extraction | `40a17c3f6c86518d...` | `05_evidence/artifacts/OVERFLOW-002_extract.txt` |
| OVERFLOW-003 | context_overflow | persona_break | `789e3a55cf4926a9...` | `05_evidence/artifacts/OVERFLOW-003_persona.txt` |
