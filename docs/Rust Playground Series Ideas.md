# rust-playground: every idea in one place

*Last updated 2026-10-04. Companion to `claude/rust-playground-handoff.md`. This is the complete list: every idea raised so far, by Jeremiah, by Claude, or in the README's "Ideas for next exercises". Nothing is ranked here, and no order is decided. Who raised each idea is in brackets.*

## Through-line: where Rust and Python divide in MARE Pro [Jeremiah]
- Every experiment should help decide where to draw the line between Rust and Python in MARE Pro.
- **Starting hypothesis:** the target-state language map in `claude/mare-hotwash-and-p1-inputs.md` [Claude, 10-02]. Each series tests one or more of its rows.
- **"For MARE Pro" verdict** at the end of each series: confirmed, changed, or not enough evidence [Claude].
- **Measure what Rust costs, not just its speed:** build time, lines of code, dependencies, time to write, and whether Codex can write it and Claude can review it [Claude].
- **Open question:** where the verdict table lives. The README Benchmarks section, or MARE as input to the hotwash.

## A. Already agreed, in order
1. **Close Series 2: the overview run.** It's running (`20261004-233633_overview`).
   - Configurations: python/seq, python3.14t/thread, rust baseline, s9-safe and s9-speed (rayon).
   - Then: a closing section in the README, and a backup of `~/bench-bins` to `data/bench-bins-backup/`.
2. **New full-series run.** Step 9 joins the main table, and "(in progress)" comes off the Series 2 heading.
3. **Series 3: his engine against tantivy.**
   - Both sides use the same BM25 settings (k1 1.2, b 0.75); tantivy keeps everything in RAM and indexes text only.
   - Correctness is checked by result counts and the top results. Note that tantivy drops words over 40 bytes.
   - The comparison code is a small binary under `src/bin/`.
   - It also reports how many segments tantivy builds.
   - Snapshots included: s9-segments/s9-safe and s9-dashmap.

## B. New series ideas [Jeremiah, 2026-10-04], with Claude's notes

### B1. Extraction of other file types, against Python
- PDF first, then the formats MARE sees: HTML, DOCX, VTT.
- **Python side:** pdfplumber with x-tolerance, run both sequentially and as parallel processes. Processes made Python 1.8× faster in Series 1.
- **Library choice:**
  - PDFium (`pdfium-render`): Chrome's engine, strong on hard PDFs, but C++, so it needs the pdfium library in the Dockerfile.
  - Pure-Rust parsers (`lopdf`, `pdf-extract`): no C++, weaker on hard PDFs.
- **B1a. A small PDFium parity test** [Claude]. Does PDFium space characters the same way pdfminer does? Tested on PDFs outside the MARE corpus. This is the main risk of hotwash option 2 (porting the x-tolerance algorithm to Rust).
- **Scored with B3's metrics.**

### B2. Embeddings, against Python
- **Expected lesson:** the model math runs in C++ either way. Rust against Python mostly changes text splitting, batching, startup time and memory.
- **Fair comparison:** the same ONNX model through Python `onnxruntime` and Rust `ort`.
- **Other candidates:** `fastembed` (it exists in both languages), sentence-transformers, and TEI as a server.
- **Correctness:** both implementations produce the same vectors (cosine ≈ 1.0).
- **CPU against GPU** is a separate axis.

### B3. Metrics: which best measure text-extraction success
- **Candidates:**
  - correct words over total words (MARE's main metric);
  - word precision;
  - fused words per 1,000;
  - character and word error rates (edit distance);
  - reading order;
  - table structure (TEDS);
  - retrieval recall@k.
- **What makes a metric good:**
  - it agrees with Jeremiah's own judgments;
  - it separates extractors from each other;
  - it gives stable results;
  - it's cheap to compute.
- **Where ground truth comes from:**
  - Render the 21 Gutenberg books to PDF, so the exact text is known. Clean, but easier than real PDFs.
  - MARE's stored bake-off outputs plus his P0 judging. Real PDFs, but that's MARE work under its harness rules.
- **Bonus:** edit distance over millions of words is CPU-bound, so the metric code itself is a Rust/Python candidate.

### B4. SvelteKit playground: MARE Pro's front end
- The folder `GitHub/sveltekit-playground` exists. It's empty and not yet a git repo.
- It works as a learning track on its own, and becomes the client for B5.
- **Framework comparison:**
  - Measure his workload, since public benchmarks already cover raw rendering: a live event log, a large sortable table, and a search box.
  - Candidates: SvelteKit, React, SolidJS, htmx served by the backend, and Leptos (Rust in the browser).
- **Also check:** whether Codex writes correct Svelte 5 (its newer "runes" syntax).
- **Earlier design notes (10-03, in the hotwash doc):**
  - SPA mode (`adapter-static`, SSR off).
  - The UI talks only to the backend API.
  - Delivery: a browser tab served by the backend first; a thin Tauri window later as an option.

### B5. Rust microservices
- **The question it tests:** Rust inside the Python program, or Rust in separate services (the hotwash doc's "in-process or services" fork). B7 covers the in-process side in depth; this series covers services.
- **The search engine, exposed four ways:**
  - as a PyO3 module called from Python (reuse B7's module);
  - as an axum HTTP service;
  - possibly over gRPC (tonic);
  - with FastAPI as the Python side.
- **Measures:**
  - the cost of each call;
  - p50/p95/p99 latency under load;
  - what survives when a worker crashes.
- **What he'd learn:** async Rust (tokio).
- **Possible extra:** Arrow for passing bulk data between Rust and Python.

### B6. Search types and the chunking each one needs [Jeremiah, 2026-10-04]
Each type of search needs its own chunking strategy, and we may have to experiment with them.

**Design idea that ties the types together [Claude]:** one document, many chunkings. Each index uses its own unit (passage, chunk, section node, triple), but every unit points back to the same source character offsets. Fusion, deduplication and citations then work across indexes, and B1's extraction output becomes the single source of truth.

**What research says about chunking:**
- **Zhou et al., Feb 2026** (arXiv 2602.16974): the best chunking depends on the task.
  - Simple structure-based chunking (paragraph, sentence, fixed size) beat LLM-guided chunking when searching across a corpus.
  - LumberChunker was best when searching within one document.
  - "Contextualized" chunking (embed the whole document first, then split) helped corpus-wide search by about 6–7% but hurt search within a document.
- **Merola & Singh, 2025** (arXiv 2504.19754):
  - Contextual retrieval (an LLM writes context for each chunk) keeps more meaning, but costs more compute.
  - Late chunking is cheaper, but loses some relevance and completeness.

**The types:**
1. **Lexical / BM25: Elasticsearch, OpenSearch, tantivy, his own engine.**
   - Chunk unit: passages or sections; fields such as title and heading can be boosted.
   - BM25's length normalization (b) interacts with chunk size. His engine indexes whole books today, so chunking them is a natural first experiment.
   - Elasticsearch is a JVM server, while tantivy is a Rust library. Elasticsearch also offers dense kNN and learned-sparse search (ELSER), so one engine can cover several types.
   - Fits with A3.
2. **Vector (dense).**
   - Chunk size is bounded by the embedding model's context length.
   - Strategies to compare:
     - fixed size or recursive splitting;
     - semantic splitting (break where adjacent-sentence similarity drops);
     - propositions (LLM-written atomic facts);
     - late chunking;
     - contextual retrieval;
     - parent–child, or small-to-big: search small chunks, return the larger parent.
   - Matryoshka embeddings let you trade vector size against cost.
   - Stores: LanceDB or Qdrant (from the language map).
   - Fits with B2.
3. **Structural graph.**
   - The document's own structure: sections, headings, tables, figures, pages, citations.
   - Chunks are nodes in the document tree, and search can walk to a node's parent, siblings or cited sources.
   - Page-level chunking suits layout-heavy PDFs.
   - Depends on MARE's structure layer (hotwash #41), so B1's quality limits it.
4. **Semantic knowledge graph.**
   - Entities and relationships pulled out of the text, each pointing back to the passage it came from.
   - Variants:
     - GraphRAG: community summaries, for global "what are the themes" questions;
     - LightRAG: keywords at two levels, with incremental updates;
     - HippoRAG: Personalized PageRank over the graph;
     - NodeRAG: a mixed-node hierarchy.
   - Indexing cost is dominated by the LLM doing the extraction; Rust helps with traversal and storage, not with that step.
   - Jeremiah's existing graph-vector database is a reference point.
5. **Other approaches from research [Claude]:**
   - **Learned sparse (SPLADE, ELSER):** a model adds related terms, but the index is still inverted lists, so it's close to his engine and tantivy.
   - **Late interaction (ColBERT for text; ColPali for page images):** many vectors per document and heavy storage. ColPali skips text extraction entirely, which matters for MARE; it would have to run locally (E7).
   - **Hierarchical summary trees (RAPTOR):** search over cluster summaries at several levels.
   - **Hybrid fusion (RRF) plus cross-encoder reranking:** this is HybridRAG itself. In the language map, reranking usually dominates query latency.
   - **Query-side techniques:** HyDE (embed a drafted answer), query decomposition, step-back prompting.
   - **Agentic and corrective retrieval:** an agent picks indexes and tools; CRAG and Self-RAG check what came back.
   - **Baselines with little or no retrieval:** long-context prompting, and order-preserving RAG (OP-RAG, which keeps chunks in document order). Useful as control conditions.

**Ground truth for retrieval** (extends B3): retrieval metrics need queries with known relevant passages. Options:
- public benchmarks: BEIR for text, ViDoRe for visual documents;
- MARE's corpus with his judgments;
- questions an LLM writes for each chunk. Cheap, but biased toward the chunking that generated them.

**Rust/Python line:** chunking and tokenizing are CPU-bound (Rust on the map). Embedding and graph extraction are model-bound, so the language matters little there. Searching an index and walking a graph run in the store, so the store's language matters.

**Natural pairings, not an order:** lexical chunking with A3, vector chunking with B2, the structural graph after B1, the knowledge graph later.

### B7. Plain Python vs plain Rust vs PyO3 (Rust inside Python) [Jeremiah, 2026-10-04]
- **His analogy:** LeNLP (github.com/raphaelsty/LeNLP; MIT, about 72 stars), a Python toolbox with a Rust backend built with PyO3 and maturin. It has CountVectorizer, TfidfVectorizer and BM25Vectorizer that fit into scikit-learn, plus FlashText keyword extraction, and it reports beating scikit-learn. Note: its BM25 produces a sparse matrix of term weights; it isn't a search engine like his.
- **The question it answers:** is Rust as a Python extension close to plain Rust in speed? If so, MARE Pro can keep Python as its outer layer and move only the hot paths into Rust. This tests the "Rust as a wheel inside Python" option, and the "one Rust core with thin shells" idea from the language map.
- **Configurations [Claude]:**
  1. Plain Python: `bench/index_bench.py`, already measured.
  2. Python with C-backed libraries: `bm25s`, which scores with NumPy and SciPy sparse matrices. This is what a Python developer would actually reach for.
  3. Python calling ready-made Rust: LeNLP, and also tantivy-py (itself a PyO3 binding; ties to D2).
  4. Python calling his own engine through PyO3, built with maturin.
  5. Plain Rust: his binary, already measured.
- **What to vary [Claude]:**
  - **How often the code crosses between Python and Rust:** one call for the whole corpus, one per file, or one per word. Each crossing has a cost, and fine-grained calls could even be slower than plain Python.
  - **What crosses:** strings going into Rust are copied and checked as UTF-8. Turning a large result into Python objects is expensive, so keep the index in Rust and return only the top results.
  - **The GIL:** release it while Rust works, so rayon can use all the cores while Python waits. Also check the extension on free-threaded 3.14t.
  - **Also measure:** import and startup time, and build and packaging (maturin builds a wheel that uv installs; ENG-02's two-lockfile note applies if it lives inside MARE's package).
- **Correctness:** the same index hash and the same search results as the existing output check.
- **Rust lessons:** PyO3's `#[pyfunction]` and `#[pyclass]`; who owns data across the boundary (Python owns its strings); turning `Result` errors into Python exceptions.
- **Links:** B5 reuses the PyO3 module; D2 (tantivy-py) gets measured here first.

## C. Smaller experiments and exercises (open)
1. **Option C: a timer per file in `index_file`** [Claude, recommended]. Does moby.txt alone set the build's wall time? Undecided.
2. **Segment merging** [Jeremiah, deferred]. A possible bridge into Series 3.
3. **Give each word's `Vec<u32>` its starting size up front** [Claude, from the flamegraph]. Growing these lists is about half of push's 17%.
4. **Stop turning keys into `String`s** [Claude, from the flamegraph]. That costs 10% (the collect re-hashes every key). Alternative: let each segment borrow the book's text, which would be a lifetimes lesson.
5. **Lowercasing (12%) and splitting into words (~12%)** [flamegraph]. These are the remaining big slices; no specific idea yet.
6. **Fix the `phrase_count` slowdown** [Claude]. `Vec::contains` checks the list item by item, so phrases of common words take milliseconds; `binary_search` fixes it.
7. **Command-line options with `clap`** [README list]: number of results, folder, case folding.
8. **Save the index to disk and load it** [README list]. Would add a "load against rebuild" benchmark, and is useful before B5, since a service loads its index at startup.
9. **Corpus scaling: 21 → ~200 → ~2,000 files** [Claude, 10-02]. Not done yet.
10. **Chunk the books for BM25** [Claude, from B6]: index paragraphs or fixed windows instead of whole books, then sweep the chunk size and b. It's a small first step into B6.

## D. Later
1. **A Python tuning series** [Claude]: the same treatment Rust got. B7's configuration 2 (`bm25s`) is a first taste.
2. **tantivy-py for the lexical side of MARE's HybridRAG** [Claude]. Measured in B7.

## E. Order options (raised, not decided; ranking set aside for now)
- **(a)** Keep the agreed order, tantivy first.
- **(b)** Extraction work first.
- **(c)** The B1a parity test, then tantivy [Claude's recommendation].
- **Draft order under (c):** A1–A2 → B1a → A3 → B3 → B1 → B2 → B5. B4 runs alongside throughout. C7 and C8 come before B5. B6 and B7 were added after this draft and aren't placed yet; B7 would naturally come before B5.

## F. Housekeeping
- Add `__pycache__/` to `.gitignore` (his file).
- README "What's here", `Cargo.toml` row: mention the features; `dashmap` is no longer a dependency (his section).
- Delete `~/prof/perf.data` (348 MB), if he hasn't already.
- **README: add this list eventually** [Jeremiah, 10-04]. It's outside the Benchmarks section, so it's his to approve. It could replace "Ideas for next exercises".

## G. Done: earlier ideas already covered
- **From the README list:**
  - rayon (Series 1);
  - phrase queries (exercise 2);
  - timing against Python (Series 1);
  - tantivy is Series 3 (A3).
- **From the 10-02 suggestions:**
  - free-threaded 3.14t;
  - peak memory including child processes;
  - Rust phase timings;
  - `&str` slices and lowercasing each file once (s3);
  - u32 word IDs (s5, reverted);
  - faster hashers (s7);
  - a hash of the full index from each language (the run's output check);
  - CPU time.
- **From 10-03:**
  - segments and a sharded merge (s9; segments adopted);
  - query time as a metric (s8).
- **Profiling:** the flamegraph (456afa6).