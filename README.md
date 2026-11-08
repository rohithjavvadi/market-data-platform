# 🏎️ F1 Race Strategy Optimizer

> A graduate-level ML + Simulation project that models Formula 1 pit stop strategy using real telemetry data, tire degradation modeling, and Monte Carlo simulation.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![FastF1](https://img.shields.io/badge/FastF1-3.3+-red.svg)](https://theoehrly.github.io/Fast-F1/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📌 Project Overview

Formula 1 teams employ entire departments dedicated to race strategy. This project builds a data-driven strategy optimizer that answers:

> **"Given current race conditions, when should a driver pit — and on which tyre?"**

This mirrors what real F1 teams (Mercedes, Red Bull) do internally using simulation and ML.

---

## 🗂️ Project Structure

```
f1-strategy-optimizer/
│
├── 📓 notebooks/
│   ├── 01_data_collection.ipynb         ← Phase 1: FastF1 + Ergast ingestion
│   ├── 02_tire_degradation_analysis.ipynb  ← Phase 2: Degradation curves
│   ├── 03_monte_carlo_simulation.ipynb  ← Phase 3: Race simulation engine
│   ├── 04_strategy_optimization.ipynb   ← Phase 4: Optimizer + RL agent
│   └── 05_results_evaluation.ipynb      ← Phase 5: Backtesting + evaluation
│
├── 🔧 src/
│   ├── data_loader.py          # FastF1 + Ergast data ingestion
│   ├── degradation_model.py    # Tyre deg curve fitting
│   ├── simulator.py            # Monte Carlo race simulator
│   ├── optimizer.py            # Strategy decision engine
│   └── utils.py                # Shared utilities
│
├── 📊 dashboard/
│   └── app.py                  # Streamlit interactive dashboard
│
├── 📄 report/
│   └── strategy_optimizer_report.pdf
│
├── data/
│   ├── raw/                    # Raw data from APIs
│   └── processed/              # Cleaned, model-ready data
│
├── models/                     # Saved trained models
├── cache/                      # FastF1 cache (gitignored)
├── requirements.txt
└── README.md
```

---

## 🧠 Methodology

### Phase 1 — Data Collection
- **FastF1**: Lap times, tyre data, safety car periods (2022–2024)
- **Ergast API**: Pit stop timing, race results, grid positions
- 6 circuits × 3 seasons = ~25,000 laps collected

### Phase 2 — Tyre Degradation Model
- Fit degradation curves per compound (Soft/Medium/Hard) per circuit
- Model: `lap_time_delta = f(tyre_age, compound, circuit)`
- Methods: Polynomial regression, exponential decay, Gaussian Process

### Phase 3 — Monte Carlo Simulation
- Simulate 10,000 race scenarios per strategy
- Sample: safety car probability, pit stop time variance, deg noise
- Output: probability distribution of finishing positions

### Phase 4 — Strategy Optimization
- **Greedy heuristic**: pit when projected gap to rivals closes
- **Q-Learning agent**: learns optimal pit window from simulation episodes

### Phase 5 — Backtesting
- Validate against 2024 actual race strategies
- Metrics: predicted vs actual finish position, strategy delta

---

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/f1-strategy-optimizer.git
cd f1-strategy-optimizer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run Phase 1 notebook
jupyter notebook notebooks/01_data_collection.ipynb

# 4. Launch the dashboard (after completing all phases)
streamlit run dashboard/app.py
```

---

## 📊 Key Results

*(To be updated as project progresses)*

| Metric | Value |
|---|---|
| Circuits analyzed | 6 |
| Seasons covered | 2022–2024 |
| Total laps collected | ~25,000 |
| Strategy prediction accuracy | TBD |
| Backtesting win rate vs actual | TBD |

---

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Data | FastF1, Ergast API, Pandas |
| EDA | Matplotlib, Seaborn, Plotly |
| Modeling | Scikit-learn, SciPy, XGBoost |
| Simulation | NumPy Monte Carlo |
| Optimization | SciPy optimize, Q-Learning |
| Dashboard | Streamlit |

---

## 📚 References

- [FastF1 Documentation](https://theoehrly.github.io/Fast-F1/)
- [Ergast Developer API](http://ergast.com/mrd/)
- Bekker, J. & Lotz, W. (2009). *Planning Formula One race strategies using discrete-event simulation*. Journal of the Operational Research Society.

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
