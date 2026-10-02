use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::Path;

// const k1 = 1.2;
// const b = 0.75;

// tokenize the text
fn tokenize(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(|w| w.to_lowercase())
        .collect()
}

struct Index {
    docs: Vec<String>,                                     // doc id -> file name
    doc_lengths: Vec<usize>,                               // doc id -> word count
    postings: HashMap<String, HashMap<usize, Vec<usize>>>, // word -> (doc id -> positions)
}

impl Index {
    fn build(dir: &Path) -> std::io::Result<Index> {
        let mut index = Index {
            docs: Vec::new(),
            doc_lengths: Vec::new(),
            postings: HashMap::new(),
        };
        for entry in fs::read_dir(dir)? {
            let path = entry?.path();
            if path.extension().and_then(|e| e.to_str()) != Some("txt") {
                continue;
            }
            let text = fs::read_to_string(&path)?;
            let doc_id = index.docs.len();
            let words = tokenize(&text);
            index.doc_lengths.push(words.len());
            index
                .docs
                .push(path.file_name().unwrap().to_string_lossy().into_owned());
            for (pos, word) in words.into_iter().enumerate() {
                index
                    .postings
                    .entry(word)
                    .or_default()
                    .entry(doc_id)
                    .or_default()
                    .push(pos);
            }
        }
        Ok(index)
    }

    // Rank documents with BM25 (k1 = 1.2, b = 0.75).
    fn search(&self, query: &str) -> Vec<(f64, &str)> {
        let n = self.docs.len() as f64;
        let avg_len = self.doc_lengths.iter().sum::<usize>() as f64 / n.max(1.0);
        let mut scores: HashMap<usize, f64> = HashMap::new();

        for term in tokenize(query) {
            let Some(postings) = self.postings.get(&term) else {
                continue;
            };
            let df = postings.len() as f64;
            let idf = ((n - df + 0.5) / (df + 0.5) + 1.0).ln();

            for (&doc_id, positions) in postings {
                let tf = positions.len() as f64;
                let len_norm = 1.0 - 0.75 + 0.75 * self.doc_lengths[doc_id] as f64 / avg_len;
                *scores.entry(doc_id).or_insert(0.0) += idf * tf * 2.2 / (tf + 1.2 * len_norm);
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
            let mut lists: Vec<&[usize]> = Vec::new();
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
fn phrase_count(term_positions: &[&[usize]]) -> usize {
    let Some((start, remainder)) = term_positions.split_first() else {
        return 0;
    };

    let mut count = 0;
    for &p in start.iter() {
        let mut all_found = true;
        for (i, pos) in remainder.iter().enumerate() {
            if !pos.contains(&(p + i + 1)) {
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

fn main() -> std::io::Result<()> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 3 {
        eprintln!("usage: playground <folder> <query words...>");
        std::process::exit(2);
    }
    let index = Index::build(Path::new(&args[1]))?;
    println!(
        "{} documents, {} distinct words",
        index.docs.len(),
        index.postings.len()
    );

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
