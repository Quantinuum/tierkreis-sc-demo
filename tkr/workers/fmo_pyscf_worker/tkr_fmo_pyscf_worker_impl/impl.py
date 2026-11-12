from pyscf import scf, fci, gto
import pyscf.gto.mole as mole
from tierkreis.worker import Worker

worker = Worker("fmo_pyscf_worker")


@worker.task()
def build_He_atom() -> str:
    mol = gto.Mole()
    mol.atom = [("He", (0, 0, 0))]
    mol.max_memory = 8e3  # MB
    mol.charge = 0
    mol.spin = 0
    mol.basis = "cc-pvdz"
    mol.symmetry = False
    mol.build()

    return mole.dumps(mol)


@worker.task()
def fci_energy(
    mole_str: str, conv_tol_grad: float = 1e-14, max_cycle: int = 200
) -> float:
    mol = mole.loads(mole_str)

    mf = scf.RHF(mol)
    mf.conv_tol_grad = conv_tol_grad
    mf.max_cycle = max_cycle
    mf.kernel()

    cisolver = fci.FCI(mf)
    e, fcivec = cisolver.kernel()

    return e
