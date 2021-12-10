"""EntanglementForgedDriver."""

import numpy as np
from qiskit_nature.drivers import FermionicDriver, QMolecule


# pylint: disable=too-many-arguments)
class EntanglementForgedDriver(FermionicDriver):
    """EntanglementForgedDriver."""

    def __init__(self,
                 hcore: np.ndarray,
                 mo_coeff: np.ndarray,
                 eri: np.ndarray,
                 num_alpha: int,
                 num_beta: int,
                 nuclear_repulsion_energy: float):
        """Entanglement forging driver

        Args:
            hcore: hcore integral
            mo_coeff: MO coefficients
            eri: eri integral
            num_alpha: number of alpha electrons
            num_beta: number of beta electrons
            nuclear_repulsion_energy: nuclear repulsion energy
        """
        super().__init__()

        self._hcore = hcore
        self._mo_coeff = mo_coeff
        self._eri = eri
        self._num_alpha = num_alpha
        self._num_beta = num_beta
        self._nuclear_repulsion_energy = nuclear_repulsion_energy

    def run(self) -> QMolecule:
        """Returns QMolecule constructed from input data."""
        q_molecule = QMolecule()
        q_molecule.hcore = self._hcore
        q_molecule.mo_coeff = self._mo_coeff
        q_molecule.eri = self._eri
        q_molecule.num_molecular_orbitals = self._mo_coeff.shape[0]
        q_molecule.num_alpha = self._num_alpha
        q_molecule.num_beta = self._num_beta
        q_molecule.nuclear_repulsion_energy = self._nuclear_repulsion_energy

        one_body_in_mo_basis = QMolecule.oneeints2mo(self._hcore, self._mo_coeff)
        q_molecule.mo_onee_ints = one_body_in_mo_basis
        q_molecule.mo_onee_ints_b = one_body_in_mo_basis

        two_body_in_mo_basis = QMolecule.twoeints2mo(self._eri, self._mo_coeff)
        q_molecule.mo_eri_ints = two_body_in_mo_basis
        q_molecule.mo_eri_ints_ba = two_body_in_mo_basis
        q_molecule.mo_eri_ints_bb = two_body_in_mo_basis

        return q_molecule