# Earth Simulator Pro++

A calibrated multi-agent global simulation engine modeling economy, politics, environment, and technology across 15 countries (1900–2100). Includes Monte Carlo prediction, sensitivity analysis, sovereign credit scoring, and real-world data integration.

## Features
- 15-country multi-agent model (GDP, demographics, politics, resources, technology, alliances, war)
- Environment-economy-emission feedback loops
- Technology tree from steam power to quantum computing
- Historical calibration with World Bank data (1900–2020)
- Monte Carlo prediction with VaR/CVaR tail risk analysis
- Sensitivity analysis (Tornado charts)
- Scenario matrix & sovereign credit scoring
- AI news impact analysis (via DeepSeek API)
- PDF professional report generation
- Desktop (PySide6) and Web (Streamlit) interfaces

## Tech Stack
Python, Streamlit, PySide6, NumPy, Pandas, Matplotlib, SciPy, Optuna, ReportLab, Pydeck, Folium, OpenAI API, World Bank API

## Quick Start
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run web version: `streamlit run app.py`
4. Run desktop version: `python desktop_app.py`

## Documentation
- **Technical Architecture**: The core engine is in `earth_sim/`, with modules for economy, ecology, politics, knowledge, warfare, and agents.
- **User Guide**: Use the sliders to adjust parameters (war probability, emission intensity, green policy) and click "Start Simulation". See the live demo at [https://earth-sim-pro-h5k9a3ywutgkahq9posv5g.streamlit.app](https://earth-sim-pro-h5k9a3ywutgkahq9posv5g.streamlit.app).
- **Parameter Description**: All adjustable parameters are defined in `earth_sim/config/default_params.py` with Chinese annotations.

## License
MIT License. See [LICENSE](LICENSE) file.

## Contact
- Developer: [Ou Yan]
- Email: [2922125696@qq.com]
- WeChat: [你的微信]
