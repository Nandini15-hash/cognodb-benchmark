# Dataset attribution

This benchmark uses the MUSAE-GitHub social network dataset:

Rozemberczki, B., Allen, C., & Sarkar, R. (2021). Multi-scale Attributed
Node Embedding. *Journal of Complex Networks*, 9(2).
Source repository: https://github.com/benedekrozemberczki/MUSAE
(GNU GPLv3 — a freely redistributable public research dataset)

The raw edge list (`data/musae_git_edges.csv`) is redistributed unmodified
under that license. `data/nodes.csv` and `data/edges.csv` are derived
files produced by `data/prepare_dataset.py`, which also adds two synthetic
benchmark-fixture properties (`dev_type`, `login`) documented in
`README.md` and `data/prepare_dataset.py`.
