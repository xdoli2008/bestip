# Project Overview: bestip

`bestip` is a comprehensive Python-based tool designed for batch testing the quality of IP addresses and domains, with specific optimizations for proxy servers and VPN nodes. It identifies high-quality nodes through a two-phase testing process—quick screening followed by deep testing—and generates detailed reports including quality scores for streaming, gaming, and real-time communication.

## Key Technologies
- **Python 3.6+**: Core programming language.
- **Concurrent Execution**: Uses `ThreadPoolExecutor` for high-concurrency testing.
- **Networking**: Utilizes `socket`, `ssl`, and `subprocess` (for ping) to measure network metrics.
- **Data Handling**: Uses `PyYAML` for configuration and generates reports in Markdown and TXT formats.
- **Statistical Analysis**: Includes modules for outlier filtering (IQR, Z-Score, MAD) and confidence interval calculations.

## Architecture
- `main.py`: The primary entry point.
- `src/core/ip_tester_pro.py`: Core logic for the advanced IP testing process.
- `src/config/config.py`: Configuration management.
- `src/analyzers/`: Contains `proxy_score_calculator.py` and `statistical_analyzer.py` for performance evaluation.
- `src/utils/url_fetcher.py`: Utility for fetching IP lists from remote URLs.
- `src/utils/ip_info_client.py`: Client for the ipinfo.dkly.net API (New).
- `data/`: Directory for input lists (`testip.txt`, `custom.txt`) and output results (`best.txt`, `ip.txt`, `result_pro.md`, `result_history.json`).
- `docs/IPINFO_API.md`: Detailed documentation for IP information integration (New).

## Building and Running

### Prerequisites
- Python 3.6 or higher.
- Install dependencies (mainly `PyYAML` for configuration):
  ```bash
  pip install pyyaml
  ```

### Running the Tool
- **Using the batch script (Windows):**
  Double-click `run.bat` or `run_pro.bat`.
- **Using Python directly:**
  ```bash
  python main.py
  ```

### Configuration
1. Copy `config.example.yaml` to `config.yaml`.
2. Modify `config.yaml` to suit your needs (e.g., set `test_mode`, add `url_sources`, or enable `streaming_test`).

## Development Conventions
- **Two-Phase Testing**: Always maintain the separation between quick screening (to discard unreachable nodes) and deep analysis (to measure quality).
- **Configuration-Driven**: New features should be configurable via the YAML configuration file.
- **Reporting**: Ensure results are consistently outputted to both `data/output/result_pro.md` (for readability) and `data/output/best.txt` (for programmatic use), with `result_history.json` enabling report comparisons.
- **Concurrency**: Use the `print_lock` for thread-safe console output during parallel tests.
