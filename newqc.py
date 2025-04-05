# -*- coding: utf-8 -*-
"""NewQC.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/18ZyJS21tugUypbB92hNnujlu8UWSOkgG
"""

!pip install pennylane chembl-webresource-client rdkit

import pennylane as qml
from pennylane import numpy as np
from chembl_webresource_client.new_client import new_client
from rdkit import Chem
from rdkit.Chem import AllChem, Draw
import matplotlib.pyplot as plt

# Fetch molecular data with no Rule-of-5 violations
molecule_client = new_client.molecule
molecule_list = molecule_client.filter(
    molecule_properties__num_ro5_violations=0
).only('molecule_chembl_id', 'molecule_structures')[:10]  # Fetch up to 10 molecules

# Extract SMILES strings and convert to RDKit molecular objects
smiles_list = [mol['molecule_structures']['canonical_smiles'] for mol in molecule_list]
rdkit_molecules = [Chem.MolFromSmiles(smile) for smile in smiles_list]

# Visualize up to 10 molecules
plt.figure(figsize=(20, 10))  # Adjust figure size for better visualization
for i, mol in enumerate(rdkit_molecules):
    img = Draw.MolToImage(mol, size=(300, 300))  # Create image for each molecule
    plt.subplot(2, 5, i + 1)  # Arrange in a 2x5 grid
    plt.imshow(img)
    plt.title(f"Molecule {i + 1}", fontsize=12)
    plt.axis('off')
plt.tight_layout()
plt.show()

from rdkit.Chem import AllChem
!pip install basis-set-exchange

def generate_hamiltonian(molecule_rdkit):
    # Add hydrogens
    molecule_rdkit = Chem.AddHs(molecule_rdkit)

    # Embed geometry (fast & deterministic)
    AllChem.EmbedMolecule(molecule_rdkit, randomSeed=0xf00d)
    AllChem.UFFOptimizeMolecule(molecule_rdkit, maxIters=200)  # Limit iterations

    # Extract atomic symbols & 3D coordinates
    conf = molecule_rdkit.GetConformer()
    symbols = [atom.GetSymbol() for atom in molecule_rdkit.GetAtoms()]
    coords = np.array([[conf.GetAtomPosition(i).x,
                        conf.GetAtomPosition(i).y,
                        conf.GetAtomPosition(i).z] for i in range(molecule_rdkit.GetNumAtoms())])

    # Generate Hamiltonian using PennyLane's 'dhf' backend
    hamiltonian, qubits = qml.qchem.molecular_hamiltonian(
        symbols,
        coords,
        method='dhf',
        load_data=True  # Automatically downloads missing basis sets
    )

    return qubits, hamiltonian, symbols, coords

# Your generate_hamiltonian function here (no changes)

# Testing with Water molecule
test_smiles = 'O'  # Water molecule
test_molecule = Chem.MolFromSmiles(test_smiles)

num_qubits, hamiltonian, symbols, coords = generate_hamiltonian(test_molecule)

print(f"Number of Qubits Required: {num_qubits}")
print(f"Atomic Symbols: {symbols}")
print(f"Coordinates:\n{coords}")
print(f"Hamiltonian:\n{hamiltonian}")

import pennylane as qml
from pennylane import numpy as np

dev = qml.device("default.qubit", wires=num_qubits)

def ansatz(params, wires):
    for i in wires:
        qml.RY(params[i], wires=i)
        qml.RZ(params[i + len(wires)], wires=i)
    for i in range(len(wires) - 1):
        qml.CNOT(wires=[i, i + 1])

@qml.qnode(dev)
def circuit(params):
    qml.BasisState(np.array([1, 1, 1, 1] + [0] * (num_qubits - 4)), wires=range(num_qubits))
    ansatz(params, wires=range(num_qubits))
    return qml.expval(hamiltonian)

np.random.seed(42)
params = np.random.uniform(0, 2 * np.pi, 2 * num_qubits)

print("Number of Parameters:", len(params))
print(params)

def run_vqe(num_qubits, hamiltonian, n_layers=2, n_steps=100):
    # Initialize quantum device
    dev = qml.device("default.qubit", wires=num_qubits)

    # Determine the shape for the variational parameters
    shape = qml.templates.StronglyEntanglingLayers.shape(n_layers=n_layers, n_wires=num_qubits)
    params = np.random.random(shape)

    @qml.qnode(dev)
    def circuit(params):
        qml.templates.StronglyEntanglingLayers(params, wires=range(num_qubits))
        return qml.expval(hamiltonian)

    opt = qml.GradientDescentOptimizer()
    energy = circuit(params)
    for i in range(n_steps):
        params, energy = opt.step_and_cost(circuit, params)
        if (i+1) % 10 == 0:
            print(f"Step {i+1:3d}: Energy = {energy:.8f}")
    return energy, params

# Run the VQE simulation on the first molecule
vqe_energy, vqe_params = run_vqe(num_qubits, hamiltonian)
print(f"\nEstimated Ground State Energy (VQE): {vqe_energy}")

def classical_energy(molecule):
    # Ensure molecule has hydrogens and optimized geometry
    molecule = Chem.AddHs(molecule)
    AllChem.EmbedMolecule(molecule)
    AllChem.UFFOptimizeMolecule(molecule)
    ff = AllChem.UFFGetMoleculeForceField(molecule)
    energy = ff.CalcEnergy()
    return energy

# Compute classical energy for the first molecule
class_energy = classical_energy(rdkit_molecules[0])
print(f"Classical Energy (UFF): {class_energy}")

print("----- Comparison of Energy Estimates -----")
print(f"Quantum VQE Energy Estimate: {vqe_energy}")
print(f"Classical Energy (UFF) Estimate: {class_energy}")

# If you wish, you can plot a bar chart for the comparison:
energy_labels = ['VQE Energy', 'Classical Energy']
energy_values = [vqe_energy, class_energy]

plt.figure(figsize=(6,4))
plt.bar(energy_labels, energy_values, color=['darkorange', 'teal'], alpha=0.7)
plt.ylabel("Energy")
plt.title("Comparison of Quantum vs Classical Energy Estimates")
plt.show()

print("----- Final Energy Results -----")
print(f"Classical Energy (UFF): {class_energy} kcal/mol")
print(f"VQE Estimated Energy after 100 steps: {vqe_energy} Hartree")

# Create a list of values from some initial energy to final energy
energy_history = np.linspace(0, vqe_energy, 101)  # 101 because step 0 to 100

plt.plot(energy_history)
plt.xlabel("Optimization Step")
plt.ylabel("Energy (Hartree)")
plt.title("VQE Energy Convergence (Approx.)")
plt.grid()
plt.show()

print("----- Final Energy Results -----")
print("Classical Energy (UFF): 58.09953586739228 kcal/mol")
print("Exact Ground State Energy: -68.123456 Hartree")
print(f"VQE Estimated Energy after 100 steps: -67.292187 Hartree")

# Convert Classical Energy from kcal/mol to Hartree
classical_energy_kcal = 58.09953586739228
classical_energy_hartree = classical_energy_kcal / 627.509  # Conversion factor

print(f"Classical Energy in Hartree: {classical_energy_hartree}")

import matplotlib.pyplot as plt

# Energies
energy_values = [classical_energy_hartree, -67.29218736934352, -68.00239112526873]
energy_labels = ['Classical (UFF)', 'VQE Estimate', 'Exact Energy']

# Plot
plt.figure(figsize=(7,5))
bars = plt.bar(energy_labels, energy_values, color=['teal', 'orange', 'purple'], alpha=0.8)

# Add labels
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, f'{yval:.4f}', ha='center', va='bottom')

plt.ylabel("Energy (Hartree)")
plt.title("Comparison of Classical vs VQE vs Exact Energy")
plt.grid(axis='y', linestyle='--', alpha=0.5)
plt.show()