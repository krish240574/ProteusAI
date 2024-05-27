# This source code is part of the proteusAI package and is distributed
# under the MIT License.

__name__ = "proteusAI"
__author__ = "Jonathan Funk"

from typing import Union
import inspect
import os
import warnings
import sys
current_path = os.path.dirname(os.path.abspath(__file__))
root_path = os.path.join(current_path, '..')
sys.path.append(root_path)
from proteusAI.ml_tools.esm_tools import *
from proteusAI.struc import *
import hashlib

model_dict = {"rf":"Random Forrest", "knn":"KNN", "svm":"SVM", "vae":"VAE", "esm2":"ESM-2", "esm1v":"ESM-1v"}

class Protein:
    """
    The protein object contains information about a single protein,
    such as its sequence, name, and its mathematical representations.
    
    Attributes:
        name (str): Name/id of the protein.
        seq (str): Protein sequence.
        rep (list): List of available representations.
        rep_path (str): Path to representations directory.
        design (str): Output of design.
    """

    def __init__(self, name: Union[str, None] = None, seq: Union[str, None] = None, struc: Union[str, struc.AtomArray, None] = None, reps: Union[list, tuple] = [], user: Union[str, None] = 'guest', y = None, fasta: str = None):
        """
        Initialize a new protein object.

        Args:
            name (str): Name/id of the protein.
            seq (str): Protein sequence.
            struc (str, AtomArray): Protein structure.
            reps (list): List of available representations.
            user (str): Path to the user. Will create one if the path does not exist. Default guest.
            y (float, int, str): Label for the protein.
            fasta (str): path to fasta file
        """

        # assertions and checks
        assert isinstance(name, (str, type(None)))
        assert isinstance(seq, (str, type(None)))
        assert isinstance(reps, (list, tuple))
        assert isinstance(user, (str, type(None)))

        self.name = name
        self.seq = seq
        self.reps = list(reps)
        self.struc = struc
        self.atom_array = None
        self.chains = []
        self.y = y
        self.design = None
        
        # If path is not provided, use the directory of the calling script
        if user is None:
            caller_path = os.path.dirname(self.get_caller_path())
            self.user = os.path.join(caller_path)
            self.rep_path = os.path.join(caller_path, 'protein/rep')
        else:
            assert isinstance(user, str)
            self.user = user
            self.rep_path = os.path.join(user, 'protein/rep')
            if not os.path.exists(user):
                os.makedirs(user)

        # If file is not None, then initialize load fasta
        if fasta is not None:
            self.load_fasta(file=fasta)
        
        # If file is not None, then initialize load fasta
        if struc is not None:
            self.atom_array = self.load_structure(struc)

    def get_caller_path(self):
        """Returns the path of the script that called the function."""
        caller_frame = inspect.stack()[1]
        caller_path = caller_frame[1]
        return os.path.abspath(caller_path)

    def __str__(self):
        if self.atom_array is not None:
            struc_loaded = "loaded"
        return f"proteusAI.Protein():\n____________________\nname\t: {self.name}\nseq\t: {self.seq}\nrep\t: {self.reps}\ny:\t{self.y}\nstruc:\t{self.struc}\n"
    
    __repr__ = __str__

    def load_fasta(self, file: str):
        """
        Load protein sequence from a FASTA file.

        Args:
            file (str): Path to the FASTA file.
        """
        sequences = []
        headers = []
        header = None
        seq = []

        with open(file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('>'):
                    if header:
                        sequences.append(''.join(seq))
                        seq = []
                    header = line[1:]
                    headers.append(header)
                else:
                    seq.append(line)

            if seq:
                sequences.append(''.join(seq))

        if not headers:
            raise ValueError(f"The file {file} is not in FASTA format or is empty.")
        
        if len(headers) > 1:
            warnings.warn("The provided FASTA file contains multiple entries. Using only the first entry.")

        # Set the header as self.name
        name = headers[0].strip()  # remove potential leading spaces

        # Store the first sequence in self.seq
        seq = sequences[0]

        # Create and return a new Protein instance
        self.name = name
        self.seq = seq

    def load_structure(self, prot_f, name = None):
        """
        Load a structure from a pdb or cif file or an AtomArray.

        Args:
            struc: path to structure file or AtomArray
            name: provide protein name, else name of the file is assumed.
        """
        if name is None and type(prot_f) == str:
            name = prot_f.split('/')[-1].split('.')[0]

        prot = load_struc(prot_f)
        seqs = get_sequences(prot_f)
        chains = chain_parser(self.struc)

        self.seq = seqs[chains[0]]
        self.name = name
        self.atom_array = prot
        self.chains = chains

    def view_struc(self, color=None, highlight=None, sticks=None):
        """
        3D visualization of protein structure.

        Args:
            color (str): Choose different coloration options
        """
        view = show_pdb(self.struc, color=color, highlight=highlight, sticks=sticks)
        return view
    
    ### Zero-shot prediction ###
    def zs_prediction(self, model='esm2', batch_size=100, pbar=None):
        """
        Compute zero-shot scores

        Args:
            model (str): Model used to compute ZS scores
            batch_size (int): Batch size used to compute ZS-Scores
            pbar: App progress bar
        """
        seq = self.seq

        # check scores for this protein and model have already been computed
        name = self.name

        user_path = self.user

        if self.name:
            dest = os.path.join(user_path, f"{self.name}/zero_shot/results", model)
        else:
            dest = os.path.join(user_path, f"protein/zero_shot/results", model)

        # Check if results already exist
        if os.path.exists(dest):
            print(f"Results already computed. Loading from {dest}")
            p = torch.load(os.path.join(dest, "prob_dist.pt"))
            mmp = torch.load(os.path.join(dest, "masked_marginal_probability.pt"))
            entropy = torch.load(os.path.join(dest, "per_position_entropy.pt"))
            logits = torch.load(os.path.join(dest, "masked_logits.pt"))
            df = pd.read_csv(os.path.join(dest, "zs_scores.csv"))
        else:
            # Perform computation if results do not exist
            print("Computing logits")
            logits, alphabet = get_mutant_logits(seq, batch_size=batch_size, model=model, pbar=pbar)

            # Calculations
            p = get_probability_distribution(logits)
            mmp = masked_marginal_probability(p, seq, alphabet)
            entropy = per_position_entropy(p)

            # Create directory if it doesn't exist
            if not os.path.exists(dest):
                os.makedirs(dest)
                print(f"Directory created at {dest}")

            # Save tensors
            torch.save(p, os.path.join(dest, "prob_dist.pt"))
            torch.save(mmp, os.path.join(dest, "masked_marginal_probability.pt"))
            torch.save(entropy, os.path.join(dest, "per_position_entropy.pt"))
            torch.save(logits, os.path.join(dest, "masked_logits.pt"))

            self.p = p
            self.mmp = mmp
            self.entropy = entropy
            self.logits = logits

            df = zs_to_csv(seq, alphabet, p, mmp, entropy, os.path.join(dest, "zs_scores.csv"))

        return df

    # Plot zero-shot entropy
    def plot_entropy(self, model='esm2', title=None, section=None):
        seq = self.seq
        name = self.name

        if self.name:
            dest = os.path.join(self.user, f"{self.name}/zero_shot/results", model)
        else:
            dest = os.path.join(self.user, f"protein/zero_shot/results", model)

        # Load required data
        self.p = torch.load(os.path.join(dest, "prob_dist.pt"))
        self.mmp = torch.load(os.path.join(dest, "masked_marginal_probability.pt"))
        self.entropy = torch.load(os.path.join(dest, "per_position_entropy.pt"))
        self.logits = torch.load(os.path.join(dest, "masked_logits.pt"))

        # Section handling
        seq_len = len(seq)
        if section is None:
            section = (0, seq_len)
        elif isinstance(section, tuple):
            if len(section) != 2 or any(type(i) != int for i in section):
                raise ValueError("Section must be a tuple of two integers.")
            if section[0] < 0 or section[0] >= seq_len or section[1] > seq_len:
                raise ValueError("Section indices are out of sequence range.")
            if section[1] < section[0]:
                raise ValueError("Section start index must be less than end index.")
        else:
            raise TypeError("Section must be a tuple or None.")

        # Set title
        if title is None:
            title = f"{model_dict[model]} per-position entropy"

        # Plot entropy
        fig = plot_per_position_entropy(per_position_entropy=self.entropy, sequence=seq, highlight_positions=None, dest=None, title=title, section=section)
        return fig
    
    ### Inverse Folding ###
    def esm_if(self, fixed=[], chain=None, temperature=1.0, num_samples=100, outpath=None, model=None, alphabet=None, pbar=None):
        """
        Perform inverse folding using ESM-IF
        """
        pdbfile = self.struc

        if chain == None:
            chain = self.chains[0]

        out = esm_design(pdbfile, chain, fixed=fixed, temperature=temperature, num_samples=num_samples, model=model, alphabet=alphabet, pbar=pbar)
        
        return out
    
    # Plot 
    def plot_scores(self, model='esm2', section=None, color_scheme=None, title=None):
        seq = self.seq
        name = self.name

        if self.name:
            dest = os.path.join(self.user, f"{self.name}/zero_shot/results", model)
        else:
            dest = os.path.join(self.user, f"protein/zero_shot/results", model)

        # Load required data
        self.p = torch.load(os.path.join(dest, "prob_dist.pt"))
        self.mmp = torch.load(os.path.join(dest, "masked_marginal_probability.pt"))
        self.entropy = torch.load(os.path.join(dest, "per_position_entropy.pt"))
        self.logits = torch.load(os.path.join(dest, "masked_logits.pt"))

        # Section handling
        seq_len = len(seq)
        if section is None:
            section = (0, seq_len)
        elif isinstance(section, tuple):
            if len(section) != 2 or any(type(i) != int for i in section):
                raise ValueError("Section must be a tuple of two integers.")
            if section[0] < 0 or section[0] >= seq_len or section[1] > seq_len:
                raise ValueError("Section indices are out of sequence range.")
            if section[1] < section[0]:
                raise ValueError("Section start index must be less than end index.")
        else:
            raise TypeError("Section must be a tuple or None.")

        # Set color scheme
        if color_scheme is None:
            color_scheme = "rwb"

        # Set title
        if title is None:
            title = f"{model_dict[model]} Zero-shot prediction scores"

        # Plot heatmap
        fig = plot_heatmap(p=self.mmp, alphabet=alphabet, dest=None, title=title, show=False, remove_tokens=True, color_sheme=color_scheme, section=section)
        return fig

    
    ### getters and setters ###
    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        if not isinstance(value, str) and value is not None:
            raise TypeError(f"Expected 'name' to be of type 'str', but got '{type(value).__name__}'")
        self._name = value

    # For seq
    @property
    def seq(self):
        return self._seq

    @seq.setter
    def seq(self, value):
        if not isinstance(value, str) and value is not None:
            raise TypeError(f"Expected 'seq' to be of type 'str', but got '{type(value).__name__}'")
        self._seq = value

    # For rep
    @property
    def reps(self):
        return self._reps

    @reps.setter
    def reps(self, value):
        if not isinstance(value, (list, tuple)) and value is not None:
            raise TypeError(f"Expected 'rep' to be of type 'list' or 'tuple', but got '{type(value).__name__}'")
        self._reps = list(value)

    # For y
    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        if not isinstance(value, (str, int, float)) and value is not None:
            raise TypeError(f"Expected 'rep' to be of type 'int', 'float', or 'str', but got '{type(value).__name__}'")
        self._y = value