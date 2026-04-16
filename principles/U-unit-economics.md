# U — Unit Economics & UX

> **Axiom:** AI computation always consumes resources — computational, time, financial, energetic. An unjustified call is an architectural defect.

---

## The Problem This Solves

AI APIs are priced per token. Every call costs money, takes time, and consumes energy. Unlike a database query or a local function call, the cost of an AI call is:

- **Variable** — scales with input and output length
- **Significant** — frontier models cost $5–$60 per million tokens
- **Compounding** — 10,000 requests/day × bad token hygiene = thousands of dollars/month wasted
- **Invisible** — costs don't show up until the invoice

The Unit Economics principle says: **you must be intentional about every AI call, or the cost will be unpleasant.**

---

## The Four Levers

### 1. Model Routing

Not all tasks require the same model. Using GPT-4o for a binary classification is like taking a taxi to pick up a newspaper from your front porch.

```
Task type                    Appropriate tier
─────────────────────────────────────────────────────────
Intent classification        Small (local 8B or mini API model)
Slot filling / extraction    Small-to-medium
Summarization                Medium
Structured reasoning         Medium-to-large frontier
Multi-step agentic chains    Large frontier
Open-ended creative gen      Large frontier
```

**Cost difference:** GPT-4o vs GPT-4o-mini on the same task = ~20x price difference for often identical quality on simpler tasks.

Routing doesn't require a sophisticated router. A hardcoded `model = "gpt-4o-mini"` for your classification endpoint *is* routing — explicit and deliberate.

### 2. Semantic Caching

Many AI calls are semantically equivalent even if not textually identical:
- "What's your return policy?" and "how do returns work?" mean the same thing

Semantic caching uses embeddings to find near-duplicate queries and serve cached responses.

```
Typical cache hit rates for FAQ/support scenarios: 40–70%
Cost reduction from 60% hit rate: 60% savings
```

Implementation sketch:
1. Embed the incoming query
2. Check vector store for similar queries above threshold (e.g. 0.92 cosine)
3. If found, return cached response — no AI call
4. If not found, call AI, cache result with embedding

### 3. Context Window Hygiene

Input tokens are money. Every unnecessary token in your prompt is a cost you pay on every single call.

**Common offenders:**
- Dumping entire documents when only a section is relevant → use retrieval
- Repeating instructions in every turn of a multi-turn conversation → use system prompt + summary
- Including full conversation history for a task that only needs the last message → truncate
- Verbose system prompts with redundant phrasing → edit ruthlessly

**Rule of thumb:** for every 1,000 tokens you remove from your average prompt, at 10k calls/day at GPT-4o prices, you save ~$18/month. Multiply by scale.

### 4. Output Bounding

`max_tokens` is not a safety valve — it's a budget. Set it to what the task actually needs.

| Task | Reasonable max_tokens |
|---|---|
| Binary classification | 5–10 |
| Slot extraction (5 fields) | 100–200 |
| Summarization (paragraph) | 200–400 |
| Long-form generation | 1000–2000 |
| Open-ended chat | 500–1000 |

---

## Multimodal Cost Control: Vision & Audio

In 2026, models routinely ingest video frames and audio streams alongside text. Vision and audio carry distinct pricing models that don't map to text-token intuitions — and they scale differently under load.

### Vision: How Images Are Priced

Most providers price image inputs via a **tile-based model**:

- A full-resolution image is split into N×N tiles (typically 512×512 px each)
- Each tile is charged as a flat token cost (~85–170 tokens per tile, depending on provider)
- A 1024×1024 image → 4 tiles; a 2048×2160 image → 16 tiles

**Cost cliff:** A 4K frame (3840×2160) can consume 1 000+ vision tokens — more than most text prompts. Resolution directly controls cost.

**Levers:**

| Lever | What it does | Guidance |
|---|---|---|
| Resize before sending | Reduces tile count | Downscale to task-minimum resolution (e.g. 512 px wide for UI classification) |
| `detail="low"` mode | Forces a single low-res tile (~85 tokens) | Use when spatial precision is not required |
| Explicit `detail` parameter | Prevents unintended full-resolution sends | Always set `detail="low"` or `detail="high"` explicitly — never rely on `"auto"` in production |

**Rule of thumb:** Every 2× increase in image resolution quadruples vision-token cost.

### Video: Frame Sampling Strategy

Video is not a first-class input type — providers receive individual frames. Every frame sent is a full image charge. Naive extraction of all frames produces catastrophic cost.

**Correct practice: sample frames at the minimum rate that answers the task.**

```
Task type                           Recommended sampling rate
──────────────────────────────────────────────────────────────
Static content / single image       1 frame (keyframe only)
Slow-changing slides / screencasts  1 FPS
Human activity recognition          1–2 FPS
Fast motion, sports, gestures       3–5 FPS
Real-time continuous analysis       Never send raw — batch and summarise instead
```

**1 FPS as a default cap:** For most video understanding tasks, 1 frame per second is sufficient and reduces frame volume by 24–30× compared to extracting every frame from a standard 30 FPS source.

**Implementation pattern:**
```python
import cv2

def sample_frames(video_path: str, target_fps: float = 1.0) -> list:
    cap = cv2.VideoCapture(video_path)
    source_fps = cap.get(cv2.CAP_PROP_FPS)
    interval = max(1, int(source_fps / target_fps))  # e.g. 30 FPS source, 1 FPS target → every 30th frame
    frames, i = [], 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if i % interval == 0:
            frames.append(frame)
        i += 1
    cap.release()
    return frames
```

**Pre-estimate cost before sending.** Treat the estimate as a gate: if projected cost exceeds budget, reduce resolution or sampling rate before dispatching.

```python
import math

def estimate_vision_cost(
    frame_count: int,
    resolution: tuple[int, int],
    tile_px: int = 512,
    tokens_per_tile: int = 170,
    price_per_1m_tokens: float = 1.50,
) -> float:
    """Returns estimated USD cost for a batch of frames at given resolution."""
    tiles_per_frame = math.ceil(resolution[0] / tile_px) * math.ceil(resolution[1] / tile_px)
    total_tokens = frame_count * tiles_per_frame * tokens_per_tile
    return total_tokens / 1_000_000 * price_per_1m_tokens
```

### Audio: Cost Model

Audio inputs are priced per **second of audio** or per **character of transcript**, depending on whether the model receives raw audio or pre-transcribed text.

| Mode | Cost driver | Approximate pricing (Q2 2026) |
|---|---|---|
| Raw audio → frontier model | Seconds of audio + output tokens | $0.06–$0.10 / min input + text-token output |
| ASR transcription (Whisper-class) | Seconds of audio | ~$0.003–$0.006 / min |
| Transcript text → frontier model | Text tokens | Standard text-token pricing |

**Transcribe-then-reason** is the default cost-control pattern: use a cheap ASR model to produce text, then pass the transcript to the frontier model. Send raw audio to a frontier model only when the task requires tone, emotion, or speaker diarisation that a transcript cannot convey.

**Levers:**

| Lever | What it does |
|---|---|
| Transcribe first, reason on text | Avoids raw-audio pricing on the reasoning step |
| Trim silence | Strip leading/trailing silence and long pauses before sending |
| VAD (Voice Activity Detection) | Detect and discard non-speech segments — only send speech windows |
| Chunk long recordings | Process in windows rather than full recordings; enables early stopping when the answer is found |

### Business Math for Multimodal

Extend the Business Math checklist with four additional questions before shipping any Vision or Audio feature:

6. **How many frames per request?** (from video or image sequences)
7. **What is the average image resolution?** (determines tile count per frame)
8. **What is the audio duration per request?** (seconds or minutes)
9. **Is raw audio required, or can you transcribe first?**

Run `estimate_vision_cost()` on a representative sample before the feature goes to staging. A result that surprises you at staging will be ten times more unpleasant in production.

---

## The UX Dimension: Latency

300ms and 3 seconds are different products. AI latency has two components:

**TTFT — Time to First Token**
The delay before any text appears. This is the UX-critical metric. Users perceive a blank screen as "broken." Streaming responses solve TTFT: the user sees text flowing within 200–500ms even if the full response takes 4 seconds.

**Total generation time**
Scales with output token count. Controllable via `max_tokens`.

**Rules:**
- Use streaming for any response > ~2 seconds of total generation
- Optimize TTFT first — it has the biggest perceived impact
- Show a loading state or partial response, never a blank screen

---

## Cost Visibility

You cannot optimize what you cannot measure.

**Minimum viable cost logging:**
```json
{
  "request_id": "...",
  "model": "gpt-4o-mini",
  "input_tokens": 312,
  "output_tokens": 87,
  "estimated_cost_usd": 0.0000756
}
```

**Alerts to configure:**
- Hourly spend > 2x baseline → runaway loop or unexpected traffic spike
- Average input tokens > expected baseline → context stuffing regression
- Cache hit rate drops suddenly → caching layer issue

---

## The Business Math

Before shipping an AI feature, answer these questions:

1. **What is the expected call volume at scale?** (requests/day)
2. **What is the average token count?** (input + output, from test runs)
3. **What model will be used?** (with its pricing per 1M tokens)
4. **What is the projected monthly cost?**
5. **Is this cost justified by the value the feature delivers?**

If you cannot answer these questions before shipping, the answer to question 5 is "we don't know" — which is not acceptable for a production feature.

---

## Further Reading

- [`code-review/unit-economics-checklist.md`](../code-review/unit-economics-checklist.md)
- [`examples/unit-economics/`](../examples/unit-economics/)
