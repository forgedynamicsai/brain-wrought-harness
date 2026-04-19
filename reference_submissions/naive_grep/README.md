# Naive Grep Baseline

**This is the floor.** Any retrieval system that can't beat this baseline is broken.

## What it is

Pure token-frequency grep over vault `.md` files using ripgrep. No LLM calls, no
embeddings, no reranking. Every query token is searched independently; per-file
match counts are summed to produce a document score. Ties broken alphabetically
by filename for determinism.

## What it is not

- A competitive retrieval system
- A demonstration of anything beyond "can we run a submission end-to-end"
- Something you should cite as a strong baseline

## Build

```bash
docker build -t naive-grep:v1 .
```

Expected image size: < 150 MB (python:3.12-slim + ripgrep only).

## Self-eval

```bash
brain-wrought self-eval --submission naive-grep:v1 --fixtures fixtures/clean/
```

## Expected scores

See `reference_scores.json`.  Rough expected ranges:

| Metric     | Expected range |
|------------|---------------|
| P@10       | 0.15 – 0.30   |
| Recall@10  | 0.20 – 0.40   |
| MRR        | 0.15 – 0.25   |
| nDCG@10    | 0.20 – 0.35   |

Scores above 0.5 on any metric are a red flag — investigate the qrel/vault
alignment before accepting them.

## Why these scores are low

Token matching has no semantic understanding. A query asking about "the meeting
where Alice discussed the project timeline" will only find notes containing the
literal words "Alice", "meeting", "project", "timeline" — and will score a note
equally regardless of whether it directly answers the question or just mentions
those words in passing. Real retrieval systems use embeddings, BM25 with IDF
weighting, or LLM-based reranking to distinguish relevance from co-occurrence.

## Protocol

The container reads a single JSON request from stdin and writes a single JSON
response to stdout:

**Request:**
```json
{"mode": "retrieve", "vault_path": "/vault", "query": "...", "k": 10}
```

**Response:**
```json
{"results": [{"note_id": "alice-chen", "score": 7}], "abstained": false, "elapsed_ms": 12}
```

`abstained: true` is returned when no tokens match any file (query is unanswerable
by this baseline), which mirrors the abstention behaviour expected for the
retrieval axis abstention queries.
