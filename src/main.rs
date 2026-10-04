// use std::collections::HashMap;
use std::env;
use std::fs;
use std::io::{BufWriter, Write};
use std::path::Path;
use std::time::{Duration, Instant};
use rayon::prelude::*;
use mimalloc::MiMalloc;

#[cfg(not(any(feature = "ahash", feature = "rustc-hash")))]
type HashBuilder = std::hash::RandomState;
#[cfg(feature = "ahash")]
type HashBuilder = ahash::RandomState;
#[cfg(feature = "rustc-hash")]
type HashBuilder = rustc_hash::FxBuildHasher;

type HashMap<K, V> = std::collections::HashMap<K, V, HashBuilder>;
#[global_allocator]
static GLOBAL: MiMalloc = MiMalloc;

// BM25 parameters
const K1: f64 = 1.2; // how quickly repeated words stop adding to the score
const B: f64 = 0.75; // how much long documents are penalized

// Queries for timing search speed, run when QUERY_BENCH=<repetitions> is set.
// No phrases of very common words ("of the"): phrase_count's linear scan makes those take milliseconds.
const BENCH_SEARCHES: [&str; 6] = ["whale", "harpoon", "the", "elizabeth darcy", "white whale harpoon", "sea ship captain boat"];
const BENCH_PHRASES: [&str; 3] = ["white whale", "captain ahab", "mr darcy"];




fn words(lowercased: &str) -> impl Iterator<Item = &str> {
    lowercased.split(|c: char| !c.is_alphanumeric()).filter(|w| !w.is_empty())
}


// tokenize: split a query into lowercase words, exactly as the index does.
fn tokenize(text: &str) -> Vec<String> {
    words(&text.to_lowercase()).map(|w| w.to_string()).collect()
}


struct DocIndex {
    name: String,
    len: usize,
    postings: HashMap<String, Vec<u32>>,
}


fn index_file(path: &Path) -> std::io::Result<DocIndex> {
    let text = fs::read_to_string(path)?.to_lowercase();
    let mut len = 0;
    // About one distinct word per 64 bytes of text in this corpus (measured: 37 to 124).
    let mut local: HashMap<&str, Vec<u32>> = HashMap::with_capacity_and_hasher(text.len() / 64, HashBuilder::default());
    
    for (pos, word) in words(&text).enumerate() {
        local.entry(word).or_default().push(u32::try_from(pos).expect("over 4 billion words in one file"));
        len = pos + 1;
    }
    let name = path.file_name().unwrap().to_string_lossy().into_owned();
    let postings: HashMap<String, Vec<u32>> =
        local.into_iter().map(|(word, positions)| (word.to_string(), positions)).collect();
    Ok(DocIndex { name, len, postings })
}



struct Index {
    docs: Vec<String>,                                     // doc id -> file name
    doc_lengths: Vec<usize>,                               // doc id -> word count
    postings: HashMap<String, HashMap<usize, Vec<u32>>>, // word -> (doc id -> positions)
}

impl Index {

    // Builds the index in parallel
    fn build(dir: &Path) -> std::io::Result<Index> {
        // 1. Collect the .txt files.
        let mut paths = Vec::new();
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            if path.extension().and_then(|e| e.to_str()) == Some("txt") {
                paths.push(path);
            }
        }

        // 2. Index each file on its own. Step 2 makes this run in parallel.
        let t = Instant::now();
        let doc_indexes = paths
            .par_iter()                         // was .iter()
            .map(|path| index_file(path))
            .collect::<std::io::Result<Vec<DocIndex>>>()?;
        eprintln!("  per-file indexing: {:?}", t.elapsed());

        // 3. Merge the per-file indices into one.
        let t = Instant::now();
        // Distinct words overall: at least the largest file's count, at most the sum. Guess twice the largest.
        let largest = doc_indexes.iter().map(|d| d.postings.len()).max().unwrap_or(0);
        let mut index = Index {
            docs: Vec::with_capacity(doc_indexes.len()),
            doc_lengths: Vec::with_capacity(doc_indexes.len()),
            postings: HashMap::with_capacity_and_hasher(largest * 2, HashBuilder::default()),
        };
        for (doc_id, doc) in doc_indexes.into_iter().enumerate() {
            index.docs.push(doc.name);
            index.doc_lengths.push(doc.len);
            for (word, positions) in doc.postings {
                let inner_map = index.postings.entry(word).or_default();
                inner_map.insert(doc_id, positions);
            }
        }
        eprintln!("  merge: {:?}", t.elapsed());
        Ok(index)
    }

    // Rank documents with BM25 (k1 = 1.2, b = 0.75).
    fn search(&self, query: &str) -> Vec<(f64, &str)> {
        let n = self.docs.len() as f64;
        let avg_len = self.doc_lengths.iter().sum::<usize>() as f64 / n.max(1.0);
        let mut scores: HashMap<usize, f64> = HashMap::default();

        for term in tokenize(query) {
            let Some(postings) = self.postings.get(&term) else {
                continue;
            };
            let df = postings.len() as f64;
            let idf = ((n - df + 0.5) / (df + 0.5) + 1.0).ln();

            for (&doc_id, positions) in postings {
                let tf = positions.len() as f64;
                let len_norm = 1.0 - B + B * self.doc_lengths[doc_id] as f64 / avg_len;
                *scores.entry(doc_id).or_insert(0.0) += idf * tf * (K1 + 1.0) / (tf + K1 * len_norm);
            }
        }
        let mut ranked: Vec<(f64, &str)> = scores
            .into_iter()
            .map(|(id, s)| (s, self.docs[id].as_str()))
            .collect();
        ranked.sort_by(|a, b| b.0.total_cmp(&a.0));
        ranked
    }

    // Documents containing the exact phrase, with how many times it occurs, most first.
    fn phrase_search(&self, phrase: &str) -> Vec<(usize, &str)> {
        // 1. Look up every word's postings. If any word isn't indexed, nothing can match.
        let mut term_postings = Vec::new();
        for term in tokenize(phrase) {
            let Some(postings) = self.postings.get(&term) else {
                return Vec::new();
            };
            term_postings.push(postings);
        }
        let Some(first) = term_postings.first() else {
            return Vec::new(); // empty phrase
        };

        // 2. For each document containing the first word, count the phrase there.
        let mut results: Vec<(usize, &str)> = Vec::new();
        'docs: for &doc_id in first.keys() {
            let mut lists: Vec<&[u32]> = Vec::new();
            for postings in &term_postings {
                let Some(positions) = postings.get(&doc_id) else {
                    continue 'docs;
                };
                lists.push(positions); // (b) &Vec<usize> becomes &[usize] automatically
            }
            let count = phrase_count(&lists); // (c)
            if count > 0 {
                results.push((count, self.docs[doc_id].as_str()));
            }
        }
        results.sort_by_key(|r| std::cmp::Reverse(r.0));
        results
    }
}

// How many times do the terms appear consecutively? term_positions[i] holds the
// sorted positions of the i-th query word in one document.
fn phrase_count(term_positions: &[&[u32]]) -> usize {
    let Some((start, remainder)) = term_positions.split_first() else {
        return 0;
    };

    let mut count = 0;
    for &p in start.iter() {
        let mut all_found = true;
        for (i, pos) in remainder.iter().enumerate() {
            if !pos.contains(&(p + i as u32 + 1)) {
                all_found = false;
                break;
            }
        }
        if all_found {
            count += 1;
        }
    }
    count
}

// Dumps each word in the index and what document they're linked to using a BTreeMap
// https://doc.rust-lang.org/std/collections/struct.BTreeMap.html
fn write_dump(index: &Index, path: &str) -> std::io::Result<()> {

    // Open the file, buffered
    let mut out = BufWriter::new(fs::File::create(path)?);

    // 1. Collect the words and sort them.
    let mut words: Vec<&String> = index.postings.keys().collect();
    words.sort();

    // 2. For each word, collect its doc ids and sort them by file name.
    for word in words {
        let by_doc = &index.postings[word];
        let mut doc_ids: Vec<usize> = by_doc.keys().copied().collect();
        doc_ids.sort_by(|a, b| index.docs[*a].cmp(&index.docs[*b]));

        // 3. Write one line per (word, doc).
        // write: word, index.docs[doc_id], and by_doc[&doc_id] as space-separated numbers
        for doc_id in doc_ids {
            let text = by_doc[&doc_id].iter().map(|p| p.to_string()).collect::<Vec<_>>().join(" ");
            writeln!(out, "{}\t{}\t{}", word, index.docs[doc_id], text)?;
        }
    }
    Ok(())
}


fn time_queries(index: &Index, reps: u32) -> (Duration, usize) {
    let run_all = || {
        let mut hits = 0;
        for q in BENCH_SEARCHES {
            hits += index.search(q).len();
        }
        for p in BENCH_PHRASES {
            hits += index.phrase_search(p).len();
        }
        hits
    };
    run_all(); // warmp-up, not timed
    let start = Instant:: now();
    let mut hits = 0;
    for _ in 0..reps {
        hits += run_all();
    }
    let queries = (BENCH_SEARCHES.len() + BENCH_PHRASES.len()) as u32;
    (start.elapsed() / (reps * queries), hits)
}


fn main() -> std::io::Result<()> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 3 {
        eprintln!("usage: playground <folder> <query words...>");
        std::process::exit(2);
    }
    // timeing the build
    let start = Instant::now();

    // building the index
    let index = Index::build(Path::new(&args[1]))?;
    println!(
        "{} documents, {} distinct words, indexed in {:?}",
        index.docs.len(),
        index.postings.len(),
        start.elapsed(),
    );

    // write dump
    if let Ok(path) = env::var("INDEX_DUMP") {
        write_dump(&index, &path)?;
    }

    // query benchmarking
    if let Ok(reps) = env::var("QUERY_BENCH") {
        let reps: u32 = reps.parse().expect("QUERY_BENCH must be a whole numberr");
        let (per_query, hits) = time_queries(&index, reps);
        eprintln!("  query: {per_query:?} per query({hits} results)");
    }

    if args[2] == "--phrase" {
        let phrase = args[3..].join(" ");
        for (count, name) in index.phrase_search(&phrase).iter().take(5) {
            println!("{count:8} {name}");
        }
    } else {
        let query = args[2..].join(" ");
        for (score, name) in index.search(&query).iter().take(5) {
            println!("{score:8.3} {name}");
        }
    }
    Ok(())
}


#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokenize_lowercases_and_splits() {
        assert_eq!(tokenize("Hello, World! 42x"), vec!["hello", "world", "42x"]);
    }

    #[test]
    fn phrase_count_finds_adjacent_words() {
        // "white" at 3 and 10, "whale" at 4 and 20: one "white whale", at 3.
        assert_eq!(phrase_count(&[&[3, 10], &[4, 20]]), 1);
    }

    #[test]
    fn phrase_count_respects_word_order() {
        assert_eq!(phrase_count(&[&[4, 20], &[3, 10]]), 0);
    }

    #[test]
    fn phrase_count_handles_three_words() {
        assert_eq!(phrase_count(&[&[1, 7, 40], &[2, 8], &[3, 9, 50]]), 2);
    }

    #[test]
    fn phrase_count_edge_cases() {
        assert_eq!(phrase_count(&[&[1, 5, 9]]), 3);
        assert_eq!(phrase_count(&[]), 0);
    }
}
