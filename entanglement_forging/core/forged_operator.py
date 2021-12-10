"""Forged operator."""

from typing import List

import numpy as np
import qiskit_nature.drivers

from .cholesky_hamiltonian import get_fermionic_ops_with_cholesky
from .orbitals_to_reduce import OrbitalsToReduce
from ..utils.log import Log


# pylint: disable=too-many-locals,too-few-public-methods
class ForgedOperator:
    """ A class for the forged operator.

    Attributes:
        h_1_op (utils.legacy.weighted_pauli_operator.WeightedPauliOperator):
            TODO  # pylint: disable=fixme
        h_chol_ops (list(utils.legacy.weighted_pauli_operator.WeightedPauliOperator)):
            TODO  # pylint: disable=fixme

    E.g. a WeightedPauliOperator can be constructued as follows:
    WeightedPauliOperator([[(0.29994114732731),
                            Pauli(z=[False, False, False],
                                  x=[False, False, False])],
                          [(-0.13390761441581106),
                           Pauli(z=[True, False, False],
                                 x=[False, False, False])]]])
    """

    def __init__(self,
                 qmolecule: qiskit_nature.drivers.QMolecule,
                 all_orbitals_to_reduce: List[int]):
        """Initializes the forged operator class.

        Args:
            qmolecule: Molecule data class containing driver result.
            all_orbitals_to_reduce: All orbitals to be reduced.
        """
        self.qmolecule = qmolecule
        self.all_orbitals_to_reduce = all_orbitals_to_reduce
        self.orbitals_to_reduce = OrbitalsToReduce(
            self.all_orbitals_to_reduce, qmolecule)
        self.epsilon_cholesky = 1e-10

        fermionic_results = get_fermionic_ops_with_cholesky(
            self.qmolecule.mo_coeff,
            self.qmolecule.hcore,
            self.qmolecule.eri,
            opname='H',
            halve_transformed_h2=True,
            occupied_orbitals_to_reduce=self.orbitals_to_reduce.occupied(),
            virtual_orbitals_to_reduce=self.orbitals_to_reduce.virtual(),
            epsilon_cholesky=self.epsilon_cholesky)

        self.h_1_op, self.h_chol_ops, _, _, _ = fermionic_results

        assert self.qmolecule.num_alpha == self.qmolecule.num_beta, \
            "Currently only supports molecules with equal number of alpha and beta particles."

    def construct(self):
        """Constructs the forged operator by extracting the Pauli operators and weights.

        The forged operator takes the form: Forged Operator = sum_ij w_ij T_ij + sum_ab w_ab S_ij,
        where w_ij and w_ab are coefficients, T_ij and S_ij are operators, and where the first term
        corresponds to the tensor product states while the second term corresponds to the
        superposition states. For more detail, refer to the paper
        TODO: add citation and equation ref

        Returns:
            tuple: a tuple containing:
                - tensor_paulis (list of str): e.g. ['III', 'IIZ', 'IXX', 'IYY', 'IZI',
                                                     'IZZ', 'XXI', 'XZX', 'YYI', 'YZY',
                                                     'ZII', 'ZIZ', 'ZZI']
                - superpos_paulis (list of str): e.g. ['III', 'IIZ', 'IXX', 'IYY', 'IZI',
                                                       'XXI', 'XZX', 'YYI', 'YZY', 'ZII']
                - w_ij (numpy.ndarray): 2D array
                - w_ab (numpy.ndarray): 2D array
        """

        hamiltonian_ops = [self.h_1_op]
        if self.h_chol_ops is not None:
            for chol_op in self.h_chol_ops:
                hamiltonian_ops.append(chol_op)
        op1 = hamiltonian_ops[0]
        cholesky_ops = hamiltonian_ops[1:]
        # The block below calculate the Pauli-pair prefactors W_ij and returns
        # them as a dictionary
        tensor_paulis = set()
        superpos_paulis = set()
        paulis_each_op = [{label: weight
                           for label, weight in op.primitive.to_list()
                           if np.abs(weight) > 0}
                          for op in [op1] + list(cholesky_ops)]
        paulis_each_op = [paulis_each_op[0]] + \
                         [p for p in paulis_each_op[1:] if p]
        for op_idx, paulis_this_op in enumerate(paulis_each_op):
            pnames = list(paulis_this_op.keys())
            tensor_paulis.update(pnames)
            if op_idx > 0:
                superpos_paulis.update(pnames)
        # ensure Identity string is represented since we will need it
        identity_string = 'I' * len(pnames[0])
        tensor_paulis.add(identity_string)
        Log.log('num paulis for tensor states:', len(tensor_paulis))
        Log.log('num paulis for superpos states:', len(superpos_paulis))
        tensor_paulis = list(sorted(tensor_paulis))
        superpos_paulis = list(sorted(superpos_paulis))
        pauli_ordering_for_tensor_states = {
            pname: idx for idx, pname in enumerate(tensor_paulis)}
        pauli_ordering_for_superpos_states = {pname: idx for idx, pname
                                              in enumerate(superpos_paulis)}
        w_ij = np.zeros((len(tensor_paulis), len(tensor_paulis)))
        w_ab = np.zeros((len(superpos_paulis), len(superpos_paulis)))
        # Processes the non-Cholesky operator
        identity_idx = pauli_ordering_for_tensor_states[identity_string]
        for pname_i, w_i in paulis_each_op[0].items():
            i = pauli_ordering_for_tensor_states[pname_i]
            w_ij[i, identity_idx] += np.real(w_i)  # H_spin-up
            w_ij[identity_idx, i] += np.real(w_i)  # H_spin-down
        # Processes the Cholesky operators (indexed by gamma)
        for paulis_this_gamma in paulis_each_op[1:]:
            for pname_1, w_1 in paulis_this_gamma.items():
                i = pauli_ordering_for_tensor_states[pname_1]
                a = pauli_ordering_for_superpos_states[pname_1]  # pylint: disable=invalid-name
                for pname_2, w_2 in paulis_this_gamma.items():
                    j = pauli_ordering_for_tensor_states[pname_2]
                    b = pauli_ordering_for_superpos_states[pname_2]  # pylint: disable=invalid-name
                    w_ij[i, j] += np.real(w_1 * w_2)
                    w_ab[a, b] += np.real(w_1 * w_2)  # pylint: disable=invalid-name
        return tensor_paulis, superpos_paulis, w_ij, w_ab