#!/bin/bash
# Vorlage fuer einen HPC mit Slurm. Partition, Konto und Module sind
# clusterspezifisch und hier absichtlich Platzhalter.
#SBATCH --job-name=wissen-lora
#SBATCH --partition=<gpu-partition>
#SBATCH --account=<konto>
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x-%j.out
set -euo pipefail
# module load cuda/12.4 python/3.12          # clusterspezifisch
source "${UNSLOTH_ENV:-$HOME/unsloth_env}/bin/activate"
cd "$(dirname "$0")"
mkdir -p logs
python3 unsloth_sft.py --config "${CONFIG:-config.json}" --trocken
python3 unsloth_sft.py --config "${CONFIG:-config.json}"
