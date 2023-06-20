import re
import sys
sys.path.append('../../../src')
from proteusAI.ml_tools.esm_tools import *

data_path = "../ind_chem_tol_ai-master/"
_dest = "../results/01"
if not os.path.exists(_dest):
    os.mkdir(_dest)

data = pd.read_csv(os.path.join(data_path, "aledb_snp_df.csv"))
gene_set = set(data.gene.to_list())
fasta_path = os.path.join(data_path, 'data_tools/fastas')
gene_name_pattern = re.compile(r"GN=([^ ]*)")

names, seqs = fasta.load_all_fastas(fasta_path)
names = [gene_name_pattern.search(n).group(1) for n in names if gene_name_pattern.search(n)]

for name, seq in zip(names, seqs):
    # create a folder for every gene
    dest = os.path.join(_dest, name)
    if not os.path.exists(dest):
        os.mkdir(dest)

    results, batch_lens, batch_labels, alphabet = esm_compute([seq])
    seq_rep = get_seq_rep(results, batch_lens)

    # LLM major computations
    logits, alphabet = get_mutant_logits(seq, batch_size=1)
    _, _, pdbs, _, _ = structure_prediction(seqs=[seq], names=[name])

    # calculations
    p = get_probability_distribution(logits)
    mmp = masked_marginal_probability(p, seq, alphabet)
    entropy = per_position_entropy(p)
    pdb = entropy_to_bfactor(pdbs[0], entropy)

    # save tensors
    #torch.save(p, os.path.join(dest, f"prob_dist.pt"))
    #torch.save(mmp, os.path.join(dest, f"masked_marginal_probability.pt"))
    #torch.save(entropy, os.path.join(dest, f"per_position_entropy.pt"))
    torch.save(results, os.path.join(dest, f"results.pt"))
    torch.save(logits, os.path.join(dest, f"masked_logits.pt"))

    # save visualizations
    prb_dist_path = os.path.join(dest, f"prob_dist.png")
    log_odds_path = os.path.join(dest, f"log_odds.png")
    per_pos_entropy_path = os.path.join(dest, f"per_pos_entropy.png")
    pdb_path = os.path.join(dest, f"{name}.pdb")

    plot_heatmap(p=p, alphabet=alphabet, remove_tokens=True, dest=prb_dist_path, show=False, title=f"{name} probability distribution", color_sheme="b")
    plot_heatmap(p=mmp, alphabet=alphabet, dest=log_odds_path, show=True, title=f"{name} per position log-odds", color_sheme="rwb")
    plot_per_position_entropy(entropy, seq, show=False, dest=per_pos_entropy_path)
    pdb.write(pdb_path)