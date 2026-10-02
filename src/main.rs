use std::collections::HashMap;
use std::env;
use std::fs;
use std::path::Path;

// tokenize the text
fn tokenize(text: &str) -> Vec<String> {
    text.split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .map(|w| w.to_lowercase())
        .collect()
}

struct Index {
    docs: Vec<String>,                                // doc id -> file name
    doc_lengths: Vec<usize>,                          // doc id -> word count
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
}

fn main() -> std::io::Result<()> {
    let args: Vec<String> = env::args().collect();

    if args.len() < 3 {
        eprintln!("usage: playground <folder> <query words...>");
        std::process::exit(2);
    }
    let index = Index::build(Path::new(&args[1]))?;
    let query = args[2..].join(" ");
    println!(
        "{} documents, {} distinct words",
        index.docs.len(),
        index.postings.len()
    );
    for (score, name) in index.search(&query).iter().take(5) {
        println!("{score:8.3} {name}");
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
}
