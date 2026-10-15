# Technical specification: AI Workflow Studio

## Goal
Visual-first content production: Brief → LLM-generated per-model prompts → Image Lab → selected reference → Video Lab → Audio Lab → asset library. Two UIs: linear studio and node canvas, backed by the same project state.

## Entities
Project, Scene, Shot, Character (immutable identity traits), ModelProfile (prompt overrides and reference sets), StyleBible (world-wide palette/lighting/material/camera locks), Asset (real/approved/rejected/model-specific), PromptVersion, GenerationJob, AgentRun, AudioClip.

## Model registry and validation
Each adapter documents `provider`, `model`, `task_type`, accepted media inputs, valid settings, duration/resolution constraints, reference ceilings, price disclaimer, capabilities version, official docs and output parser. Model parameters validated on the backend, not freely LLM-generated. Failed generations are kept separate from positive reference packs.

## AI agents
Director decomposes user briefs; Continuity checks identity and style rules; Prompt specialist writes model-specific instructions. Start in approval mode: LLM runs allowed, any paid media generation must be explicitly triggered. Store job events, estimates vs actual spending, errors and audit trail. Human approval for canonical asset updates.

## Audio
Local import of licensed files, FFmpeg extraction, segment suggestions by silence, human clip selection, WAV export and consent acknowledgement. Future: transcription, diarization, voice activity detection, quality ranking, review, ElevenLabs/Fish Audio provider adapters. No unauthorized voice cloning.

## Deployment milestones
MVP local: project DB, prompt flow, verified adapters, image-to-video selection, character folders, basic audio. V2: comprehensive style bible editor and consistency review; complete model-specific schemas; cloud queue and provider credential vault. V3: agents with durable jobs, batch scene generation, human-review gates, audio providers, timeline.

## Acceptance checks
- `GET /api/health` responds; project persists across reload; model-specific prompt changes do not overwrite other prompts.
- A stored character profile is isolated per model; an approved image can serve as the next video reference.
- Unsupported model settings rejected before upstream call; any Cloudflare 1010 explains no retry.
- Paid image/video submission only after manual click and authorized API key.
- WAV audio cut requires user attestation of rights and FFmpeg.
