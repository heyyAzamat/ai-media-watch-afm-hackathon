# ML Model Contract — for the ML teammate

This is the **entire** handshake between the backend and your model. Implement
this one class and the backend wires it in with a single config change. You
never touch the API, the downloader, or the frontend.

## What you implement

Create `src/aimw/services/scam_model/ml_model.py` with a class named
`MlScamModel` that satisfies this contract:

```python
from .base import ScamVerdict


class MlScamModel:
    name = "ml-embedding-model"          # any short label

    def __init__(self) -> None:
        # load weights / the embedding model + classifier here, once
        ...

    def analyze(self, video_path: str) -> ScamVerdict:
        # video_path is a local .mp4 the backend already downloaded for you.
        # Do your own frame/audio extraction + embedding + classification.
        return ScamVerdict(
            risk_score=87,                 # int 0-100
            category="illegal_gambling",   # see categories below, or "none"
            confidence=0.91,               # float 0.0-1.0
            explanation="casino UI + 'guaranteed win' voiceover",  # optional, 1 line
            model=self.name,
        )
```

That's it. `analyze` is **synchronous** (the backend runs it in a worker thread,
so blocking inference is fine). Input is a **local file path**; output is a
`ScamVerdict`.

## `ScamVerdict` fields (defined in `scam_model/base.py`)

| field | type | notes |
|-------|------|-------|
| `risk_score` | int 0–100 | higher = more likely a scam |
| `category` | str | one of the categories below, or `"none"` |
| `confidence` | float 0.0–1.0 | optional, defaults to 0.0 |
| `explanation` | str | optional, one human-readable line (great for the demo) |
| `model` | str | set it to your `name` |

## Suggested `category` values

`illegal_gambling`, `casino_advertising`, `sports_betting`, `pyramid_scheme`,
`ponzi_scheme`, `guaranteed_income`, `referral_scam`, `fake_investment`,
`financial_manipulation`, `hidden_advertising`, `none`.

(Free-form strings are accepted, but matching these keeps the frontend labels
consistent.)

## How to turn your model on

Once `ml_model.py` exists, the backend switches to it with one env var:

```
AIMW_SCAM_MODEL_PROVIDER=ml
```

(Default is `orchestrator` — the existing Whisper pipeline, so the product works
even before your model is ready. `mock` returns a fixed placeholder for UI work.)

## Notes

- Heavy deps (torch, transformers, …) go in `requirements-ml.txt`, not the base
  requirements, so the API image stays light.
- If loading the model is slow, do it in `__init__` (built once at startup), not
  per-request.
- Talk to the backend dev if your model needs something other than a file path —
  the contract can grow, but keep it minimal.
