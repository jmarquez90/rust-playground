# NLP and Computational Linguistics: A Field Survey

Oct 4, 2026 · @Jeremiah

A map of the field for learning and for spotting where Rust is thin. Each area says what it does, the classic and modern methods, the Python tools people use, how far Rust has got, a small Rust exercise, and how it touches MARE.

## At a glance

Rust is strong at the bottom of the stack (characters, tokens, search, running models) and thin in the middle (parsing, meaning, discourse, corpus analysis). Rust status reflects what I found on 2026-10-04: **Mature** = several maintained crates, **Partial** = some pieces or bindings, **Thin** = little or dormant, **Gap** = nothing found.

| Area | What it does | Python go-to | Rust today | MARE link |
| --- | --- | --- | --- | --- |
| Characters and text | Normalize, segment, repair encodings, correct OCR | ftfy, unicodedata, PyICU | Mature; OCR correction is a gap | Cleanup after extraction (fused words) |
| Words | Tokens, subwords, stems, lemmas, morphology | spaCy, NLTK, HF tokenizers | Mature for tokenizers and stemming; lemmas thin | Indexing and chunking |
| Syntax | Part-of-speech tags, parse trees | spaCy, Stanza, UDPipe | Partial | Structure-aware chunking |
| Word meaning | Senses, lexicons, embeddings | NLTK WordNet, gensim, sentence-transformers | Partial (models run; lexicons thin) | Vector search |
| Information extraction | Entities, linking, relations, coreference | spaCy, GLiNER, Stanza | Partial; coreference a gap | Knowledge graph |
| Sentences and discourse | Semantic roles, discourse, sentiment, stance | transformers, VADER | Thin | Research synthesis |
| Corpus linguistics | Concordance, collocation, keyness | NLTK, quanteda (R), AntConc | Thin | Exploring a corpus |
| Language models | N-grams to LLMs | KenLM, transformers, vLLM | Mature for inference | Local models |
| Speech and sound | Recognition, synthesis, pronunciation, alignment | Whisper, MFA, Parselmouth | Partial to mature | VTT transcripts |
| Many languages | Language ID, transliteration, translation | fastText LID, lingua-py | Mature for language ID | Multilingual sources |
| Search and QA | Retrieval, ranking, answers | Pyserini, bm25s, FAISS | Mature | HybridRAG core |
| Generation | Summaries, simplification, dialogue | transformers, LLM APIs | Through model runtimes | Research reports |
| Specialty fields | Style, history, acquisition, society | faststylometry, PyLangAcq, CLTK | Thin | Electric Sheep material |
| Foundations | Annotation, treebanks, metrics | conllu, sacreBLEU, jiwer | Partial; document-parsing metrics a gap | Extraction metrics (B3) |

## Characters and text

Everything downstream depends on getting characters right: a fused word or a broken encoding poisons search, embeddings and metrics alike.

- **Tasks:** Unicode normalization (NFC, NFKC), case folding, splitting into graphemes, words and sentences, fixing mojibake, de-hyphenating line breaks, correcting OCR errors.
- **Methods:** rules and Unicode tables (UAX #29 for boundaries); dictionary and frequency-based repair; modern OCR post-correction uses sequence-to-sequence models or LLMs.
- **Python:** `unicodedata`, PyICU, ftfy, wordninja and SymSpell for splitting fused words.
- **Rust:** mature. `unicode-segmentation` and `unicode-normalization`, ICU4X, `plsfix` (an ftfy port with Python bindings), `charabia` (Meilisearch's normalizer). OCR post-correction: nothing found.
- **Try in Rust:** a fused-word splitter. Learn word frequencies from the 21 books, then split "thewhale" into "the whale" with dynamic programming (Viterbi over word costs).
- **MARE:** this is where its fused-word finding lives. A repair step after extraction is candidate 2 for the parallel project.

## Words: tokens, stems, lemmas, morphology

Deciding what counts as a word is the first real linguistic decision, and Rust is strongest here.

- **Tasks:** tokenization; subword tokenization for models (BPE, WordPiece, Unigram); stemming ("running" → "run" by rule); lemmatization ("better" → "good" by dictionary); morphological analysis ("unhappiness" = un + happy + ness); segmenting languages written without spaces (Chinese, Japanese, Thai).
- **Methods:** rules and finite-state transducers; dictionaries; statistical segmenters (Viterbi over a lattice); neural models.
- **Python:** spaCy, NLTK, HF `tokenizers`, `tiktoken`, SentencePiece, jieba, SudachiPy.
- **Rust:** mature for tokenizers. HF `tokenizers` is Rust underneath, plus `tiktoken-rs`, `bpe`, `rust-stemmers` (Snowball), `jieba-rs`, `lindera`, `vibrato`, `vaporetto`, `rustfst` (finite-state transducers). Lemmatization is thin.
- **Try in Rust:** add Snowball stemming to your BM25 engine behind a Cargo feature, then measure recall and speed. Or train a tiny BPE tokenizer on the 21 books.
- **MARE:** the tokenizer decides what the lexical index can match. Stemming trades precision for recall.

## Syntax: tags and parse trees

Syntax labels each word's role and how words attach to each other, and Rust has pieces but no complete parser of its own.

- **Tasks:** part-of-speech tagging; chunking (noun phrases, verb groups); dependency parsing (which word governs which); constituency parsing (nested phrases).
- **Methods:** hidden Markov models and averaged perceptrons for tagging; transition-based and graph-based dependency parsers; today, transformer encoders under a small parsing head. Universal Dependencies gives one annotation scheme for 100+ languages.
- **Python:** spaCy, Stanza, UDPipe, Trankit, benepar (constituency).
- **Rust:** partial. `rustling` has a perceptron tagger and HMMs. `udpipe-rs` binds UDPipe. `SpaRs` runs spaCy's English models natively but is experimental. `rust-bert` covers POS through transformer models.
- **Try in Rust:** an averaged perceptron POS tagger trained on a Universal Dependencies treebank (CoNLL-U files). It's about 200 lines and teaches structs, traits and hash maps.
- **MARE:** noun phrases make good index terms and graph nodes; parse trees help split long sentences into propositions.

## Word meaning: senses, lexicons, embeddings

Meaning comes either from hand-built lexicons or from where words occur ("you shall know a word by the company it keeps"). Rust can run the models, but the lexicon side is thin.

- **Tasks:** word sense disambiguation (bank: river or money); lexical relations (synonyms, hypernyms); word and sentence embeddings; semantic similarity.
- **Methods:** WordNet and FrameNet; counts and PMI matrices, then LSA; word2vec, GloVe and fastText; contextual embeddings from transformers; static distilled embeddings (Model2Vec) for speed.
- **Python:** NLTK's WordNet, gensim, sentence-transformers, Model2Vec.
- **Rust:** partial. Models run through `candle` (which ships BERT, E5 and GTE embedding models), `ort` and `rust-bert`. The embedding-format crates `finalfusion` and `finalfrontier` are dormant. WordNet access in Rust is thin.
- **Try in Rust:** build a PMI co-occurrence matrix from the 21 books and list each word's nearest neighbours. It's distributional semantics with nothing but hash maps.
- **MARE:** this is the vector half of HybridRAG (B2 and B6).

## Information extraction: entities, relations, coreference

Extraction turns text into structured facts: who, what, where, and how they connect. It's the raw material for a knowledge graph.

- **Tasks:** named entity recognition (people, organizations, places, dates); entity linking (which "Washington" is meant, tied to a knowledge base); relation extraction (X founded Y); coreference ("she" = Dr. Lee); event extraction; keyword and keyphrase extraction.
- **Methods:** gazetteers and rules; CRFs; fine-tuned transformers; zero-shot extractors such as GLiNER; LLMs prompted to emit triples.
- **Python:** spaCy, Stanza, GLiNER, Flair, REBEL for relations, fastcoref, KeyBERT and YAKE for keyphrases.
- **Rust:** partial. `rust-bert` has NER pipelines, and any ONNX model runs through `ort`. LeNLP's FlashText does fast dictionary matching. Coreference and entity linking: nothing found.
- **Try in Rust:** a gazetteer NER with an Aho-Corasick automaton (the `aho-corasick` crate) over a list of names from the books. Then measure it against spaCy.
- **MARE:** the semantic knowledge graph in B6 is built from this. The LLM extraction step dominates its cost.

## Sentences and discourse: roles, structure, sentiment, stance

Above the sentence, the questions become who did what to whom, how ideas connect, and what the writer thinks. LLMs now handle much of this, so dedicated tools are fading in Python too.

- **Tasks:** semantic role labeling (agent, patient, instrument); discourse parsing (cause, contrast, elaboration between clauses, as in Rhetorical Structure Theory); argument mining (claims and evidence); sentiment and emotion; stance (for or against a target); hedging and certainty; pragmatics (implicature, speech acts, dialogue acts).
- **Methods:** lexicons (VADER for sentiment); feature-based classifiers; fine-tuned transformers; LLM prompting.
- **Python:** transformers pipelines, VADER, NLTK's sentiment tools. AllenNLP, the former home of SRL models, is archived.
- **Rust:** thin. `vader_sentiment` is dormant; `rust-bert` has sentiment classification; anything else means running a model through `ort` or `candle`.
- **Try in Rust:** port VADER's lexicon and rules (a few hundred lines) and check it gives the same scores as Python on a test set.
- **MARE:** claim, evidence and hedging detection fit a research engine that has to weigh sources.

## Corpus linguistics: patterns across many texts

Corpus linguistics counts and compares language at scale. It's mostly statistics over big indexes, which suits Rust, yet Rust barely has it.

- **Tasks:**
  - concordance, or keyword in context (KWIC): every use of a word, with its neighbours;
  - collocation: words that occur together more than chance, such as "strong tea";
  - keyness: words over-used in one corpus compared with another;
  - dispersion: whether a word appears evenly or in bursts;
  - n-gram and lexical bundle counts;
  - register and genre analysis.
- **Methods:** association measures (PMI, log-likelihood, t-score, Dice); suffix arrays for fast n-gram and phrase lookup; multidimensional analysis (Biber).
- **Python and others:** NLTK collocations, corpus-toolkit, spaCy plus pandas. Outside Python: quanteda (R) and AntConc and Sketch Engine (desktop and web).
- **Rust:** thin. `rustling` counts n-grams; the rest is a gap.
- **Try in Rust:** your index already holds word positions, so a KWIC concordance and PMI collocations are small additions to the playground engine.
- **MARE:** keyness can tell a researcher what's distinctive about one source compared with the rest of a corpus.

## Language models: n-grams to LLMs

A language model assigns probabilities to text. Running neural models is now a strength of Rust; classic n-gram models are only partly covered.

- **Tasks:** scoring how likely text is (perplexity); predicting the next word; generation; filtering data by quality; constrained decoding (forcing output into a schema).
- **Methods:** n-gram models with smoothing (Kneser-Ney); RNNs; transformers; quantized local inference; speculative decoding.
- **Python:** KenLM's Python module (the library itself is C++), transformers, vLLM, llama-cpp-python.
- **Rust:** mature for inference. `llama-cpp-2` (the most used), `mistralrs` (pure Rust, on `candle`), `candle-transformers` and `burn`. `llguidance` handles constrained decoding inside vLLM, SGLang and llama.cpp, so Rust already sits underneath the Python stack. For n-grams, `rustling` has language models and `kenlm-rs` binds KenLM.
- **Try in Rust:** a Kneser-Ney trigram model over the 21 books. Then use its perplexity to spot garbled text, such as a bad extraction.
- **MARE:** local models for research agents. A cheap n-gram "does this look like language" score could flag extraction failures.

## Speech and sound

Speech is where computational linguistics meets signal processing. Rust is surprisingly strong at running speech models, but thin on phonetic analysis.

- **Tasks:** speech recognition (ASR) and synthesis (TTS); converting spelling to pronunciation (grapheme-to-phoneme, G2P); forced alignment (timing each word and sound); voice activity detection; speaker diarization (who spoke when); phonetic measurement (pitch, formants); phonological analysis (sound patterns, syllables).
- **Methods:** HMM-GMM systems and finite-state transducers; neural end-to-end models (Whisper, Parakeet); Praat-style acoustic analysis.
- **Python:** Whisper, faster-whisper, Montreal Forced Aligner, Parselmouth (Praat), Epitran and phonemizer for G2P, pyannote for diarization. WikiPron (by rustling's author) is a large G2P dataset.
- **Rust:**
  - Running models is partial to mature: `whisper-rs`, `sherpa-onnx` (recognition, TTS, diarization), `parakeet-rs`, `piper-rs`, a pure-Rust `espeak-ng` port, and `earshot` for voice activity detection.
  - Audio plumbing is mature: `symphonia`, `rustfft`, `rubato`.
  - Phonetic analysis and forced alignment are thin. `rustling` reads TextGrid and ELAN files.
- **Try in Rust:** a syllable counter, or a G2P lookup built from WikiPron data.
- **MARE:** VTT transcripts are already an input format, and diarization would attribute quotes to speakers.

## Many languages: identification, transliteration, translation

Most NLP tools assume English. Multilingual work starts with knowing which language you have, and that's one place where Rust leads.

- **Tasks:** language identification (including short and mixed-language text); script detection; transliteration (Москва → Moskva); machine translation; cross-lingual embeddings and search; low-resource and endangered languages.
- **Methods:** character n-gram profiles; fastText classifiers; neural translation (MarianMT, NLLB); multilingual encoders (XLM-R, LaBSE).
- **Python:** fastText's language ID model, `lingua-py` (which now runs on the Rust `lingua`), langdetect, CTranslate2, transformers.
- **Rust:** mature for language ID. `lingua` is accurate on short text and `whatlang` is fast and light. `charabia` detects scripts. Translation runs through model runtimes (`candle`, `ort`, `rust-bert`'s translation pipelines). Transliteration is thin.
- **Try in Rust:** a character-trigram language identifier (Cavnar-Trenkle profiles), then compare it with `whatlang` for accuracy and speed.
- **MARE:** route documents to the right tokenizer and stemmer, and decide whether a source needs translation before indexing.

## Search and question answering

Information retrieval is NLP's most-used application, and the one your playground already builds. The full set of search types and their chunking is in the ideas doc (series B6).

- **Tasks:** lexical search (BM25); dense vector search; learned sparse search (SPLADE); late interaction (ColBERT, ColPali); hybrid fusion and reranking; query expansion and spelling correction; extractive and generative question answering; chunking.
- **Methods:** inverted indexes and BM25; approximate nearest-neighbour graphs (HNSW); cross-encoder rerankers; retrieval-augmented generation.
- **Python:** Pyserini, `bm25s`, `rank_bm25`, FAISS, sentence-transformers, tantivy-py.
- **Rust:** mature. `tantivy`, Meilisearch, Qdrant, LanceDB, `text-splitter` for chunking, plus `bm25` and `tokenizers`.
- **Try in Rust:** already underway: your engine, then Series 3 against tantivy, then chunking the books (idea C10).
- **MARE:** HybridRAG's core.

## Generation: summaries, simplification, dialogue

Generation is now mostly LLM work. What's left for computational linguistics is controlling it and measuring it.

- **Tasks:** summarization (extractive and abstractive); simplification and readability; paraphrase; data-to-text; dialogue systems; checking that output is faithful to its source (hallucination detection).
- **Methods:** extractive ranking (TextRank, LexRank); sequence-to-sequence models; LLM prompting with constrained decoding. Measured by ROUGE, BERTScore, readability formulas (Flesch-Kincaid), and fact-checking with natural language inference (NLI) models.
- **Python:** transformers, LLM SDKs, sumy (extractive), `textstat` (readability), `rouge-score`, `bert-score`.
- **Rust:** generation itself runs through the inference crates (`llama-cpp-2`, `mistralrs`). Evaluation metrics and readability are thin.
- **Try in Rust:** an extractive TextRank summarizer: sentence similarity plus PageRank over a graph, perhaps with `petgraph`.
- **MARE:** research reports are generation. Faithfulness checks against cited passages tie back to the "one document, many chunkings" offsets idea.

## Specialty fields

These are where computational linguistics answers questions about people and history rather than building products. Most of their tools are small Python or R packages, and Rust has almost none.

| Field | Questions it asks | Typical tools |
| --- | --- | --- |
| Stylometry and authorship | Who wrote this? Has the style changed? Is it machine-written? | Burrows's Delta, function-word profiles; faststylometry, stylo (R) |
| Historical linguistics | How did words and meanings change? Which languages are related? | Semantic change from embeddings over time, cognate detection; CLTK, LingPy |
| Language acquisition | How do children learn language? | CHILDES/TalkBank transcripts; PyLangAcq, rustling (CHAT files) |
| Sociolinguistics | How does language vary by group, place, platform? | Variation models, dialect maps |
| Psycholinguistics | What makes text hard to process? | Surprisal from language models, reading-time corpora |
| Domain NLP | Legal, clinical, financial, scientific text | scispaCy, domain models, citation parsing (GROBID) |

**Rust:** thin across all of them. `rustling` is the main exception, for acquisition data.

**Try in Rust:** a Burrows's Delta authorship test over the 21 books. Can it tell your authors apart from 5,000-word samples?

**Your work:** stylometry and machine-text detection would make natural Electric Sheep pieces, and scientific-document parsing is MARE's world.

## Foundations: annotation, data and evaluation

Every area above stands on annotated data and agreed metrics. This is the least glamorous part of the field and the one that decides whether results mean anything.

- **Annotation:** guidelines; tools (Label Studio, INCEpTION, brat); agreement between annotators (Cohen's and Fleiss' kappa, Krippendorff's alpha).
- **Data formats and resources:** CoNLL-U and Universal Dependencies treebanks, Penn Treebank, OntoNotes, CHAT (CHILDES), TextGrid, and benchmarks such as GLUE, BEIR and OmniDocBench.
- **Metrics:**
  - Classification: precision, recall, F1.
  - Text output: WER and CER for speech and OCR; BLEU, chrF and COMET for translation; ROUGE and BERTScore for summaries.
  - Search: nDCG and recall@k.
  - Document parsing: edit distance, TEDS for tables, reading order.
  - Statistics: significance tests and bootstrap confidence intervals (as in your benchmarks).
- **Python:** `conllu`, sacreBLEU, jiwer, `ranx` and `ir_measures`, `krippendorff`, `evaluate`.
- **Rust:** partial. `werx` and `rwer` compute WER; `rustling` reads CoNLL-U and CHAT. For document-parsing metrics and agreement statistics, nothing found.
- **Try in Rust:** Krippendorff's alpha, or TEDS. Both are well defined and have Python reference outputs to match.
- **MARE:** this is series B3, and candidate 1 for the parallel project.

## Where Rust has gaps

The gaps cluster in the middle of the stack (analysis, metrics, linguistics proper), not at the bottom (tokens, search, model runtimes). The ones nearest your work are document-parsing evaluation and text repair.

| Gap | Who needs it | Fits | Effort |
| --- | --- | --- | --- |
| Document-parsing metrics (TEDS, reading order, fused words) | Anyone building document AI or RAG ingestion | Parallel project candidate 1; series B3 | Medium |
| Repairing text after extraction and OCR | Every RAG pipeline | Candidate 2 | Medium |
| Corpus linguistics (KWIC, collocation, keyness, dispersion) | Linguists, digital humanities, researchers | Candidate 4, or contribute to rustling | Small to medium |
| Agreement statistics (kappa, Krippendorff's alpha) | Anyone annotating data | A small crate, or part of candidate 1 | Small |
| Readability and generation metrics (Flesch, ROUGE, BERTScore) | Evaluation pipelines | A small crate | Small |
| Lemmatization and a full native parser | General NLP users | Candidate 5 (spaCy-style) | Large |
| Coreference and entity linking | Knowledge-graph builders | Model runtimes plus glue | Large |
| Stylometry | Digital humanities, machine-text detection | A small crate; an Electric Sheep story | Small |

The pattern for a visible project is the same in every row: a Rust core, Python bindings on PyPI, and benchmarks against the Python incumbent. The "Try in Rust" exercises above double as prototypes for the small rows.

## Sources

The Rust status column draws on the pages below, opened 2026-10-04. Python tools and method histories are general knowledge of the field, not separately sourced. "Nothing found" means a search came up empty, not that nothing exists.

- [Are We Learning Yet: Modalities & Domains](https://www.arewelearningyet.com/modalities) (text, tokenization and speech crates, with status)
- [Are We Learning Yet: LLMs & Foundation Models](https://www.arewelearningyet.com/llms)
- [rustling](https://github.com/jacksonllee/rustling) and [its docs](https://docs.rustling.io)
- [SpaRs](https://github.com/jotx19/SpaRs)
- [udpipe-rs](https://docs.rs/udpipe-rs)
- [plsfix](https://docs.rs/crate/plsfix/latest)
- [werx](https://pypi.org/project/werx/) and [rwer](https://docs.rs/crate/rwer/0.2.2)
- [LeNLP](https://github.com/raphaelsty/LeNLP)
- [OmniDocBench](https://arxiv.org/html/2412.07626v2)
- [wtpsplit](https://github.com/bminixhofer/wtpsplit)
- Companion: the project doc `claude/rust-playground-series-ideas.md` (series B3, B6, B7 and section H)