import sys
sys.path.append('../')
import re
from design import ZeroShot
from analysis import pdb, interactions
import os

ASMT_pdb = '../example_data/structures/ASMT.pdb'
ASMT_seq = pdb.to_fasta(ASMT_pdb).split('\n')[1]

# determine best docking results
pattern = r'rank[1]_'

dock_results_path = '../example_data/docking/'
dock_dirs = [os.path.join(dock_results_path, d) for d in os.listdir('../example_data/docking/') if d.endswith('sdf')]

docked_ligands = []
for d in dock_dirs:
    for f in os.listdir(d):

        if re.search(pattern, f) and f.endswith('sdf'):
            docked_ligands.append(os.path.join(d, f))

educts = [f for f in docked_ligands if ('melatonin' in f or 'SAM' in f) and 'transition' not in f]
products = [f for f in docked_ligands if ('acet' in f or 'SAH' in f)]
transition_states = [f for f in docked_ligands if 'transition' in f]

melatonin = [f for f in educts if 'melatonin' in f and 'rank1' in f][0]
SAM = [f for f in educts if 'SAM' in f and 'rank1' in f][0]
transition_state = [f for f in transition_states if 'transition' in f and 'rank1' in f][0]

contacts = interactions.mol_contacts([melatonin, SAM, transition_state], ASMT_pdb)

# constrain the design to not change the contacts to ligands
ASMT_atms = interactions.get_atom_array(ASMT_pdb)
contact_indices = []
for res_id in contacts:
    res_name = ASMT_atms.res_name[ASMT_atms.res_id == res_id][0]
    contact_indices.append(res_id-1)

# constraints
res_constraints = {'all_atm':contact_indices}

# Design process
outdir = '../example_data/zero_shot/'

if not os.path.exists(outdir):
    os.mkdir(outdir)

Design = ZeroShot.ZeroShot(seq=ASMT_seq,
                           name='ASMT',
                           constraints=res_constraints,
                           outdir=outdir,
                           )

print('constraints on residues')
print(res_constraints)
print(Design)
Design.run()