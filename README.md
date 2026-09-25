# CSE Stock Analyzer

A native **Windows 11 desktop application** built with Python and Tkinter for technical analysis, signal scanning, backtesting, portfolio tracking, and AI-powered market insights on the **Colombo Stock Exchange (CSE)**.

Styled with the modern **Windows 11 Fluent Light Theme (`sv-ttk` + custom tokens)**, Mica materials, and native Segoe UI typography.

---

## Key Features

- **Market Dashboard**: 
  - Real-time overview with 6 summary KPI cards (Total Symbols, Enabled Symbols, Total Bars, Last Bar Date, 7-Day Signals).
  - **Everyday New Feature**: Daily Stock Spotlight & Insight banner with deterministic daily pick rotation, target edges, stop loss levels, composite ratings, and interactive candidate cycling.
  - Synchronous local database loading so all tables and cards appear simultaneously with zero pop-in.
  - Top Gainers & Top Losers table with live price, volume, and percentage change.
  - Recent QQE trading signals table with 1-click double-click to view charts.
  - One-click daily scan to fetch latest CSE historical bars and recompute signals.

- **QQE Signal Scanner**:
  - Scan all 260+ CSE listed stocks using the Qualitative Quantitative Estimation (QQE) technical indicator.
  - Custom parameters: RSI Period, Smoothing Factor (SF), QQE Factor, Threshold.
  - Filter signals: All, Long Only, Short Only.

- **Interactive Candlestick Charts**:
  - Embedded `mplfinance` candlestick & volume charts.
  - Period selector: 1M, 3M, 6M, 1Y, All.
  - Indicator overlays: 50-day & 200-day Moving Averages, QQE Buy/Sell signal markers.
  - Matplotlib toolbar with zoom, pan, and export capabilities.

- **Portfolio Tracker**:
  - Track buy/sell positions, entry price, quantity, and current value.
  - Live P&L (Profit & Loss) and P&L% calculations.
  - Industry sector diversification pie chart.

- **Backtest Engine**:
  - Vector-based backtesting engine with configurable capital, commissions, stop-loss, and take-profit percentages.
  - Performance metrics: Total Return, Win Rate, Profit Factor, Average Win/Loss, Max Drawdown.
  - Strategy equity curve visualization and trade-by-trade audit log.

- **AI Analysis (Google Gemini)**:
  - Single-stock technical & fundamental analysis with Google Gemini 2.5 Flash.
  - Daily CSE market summary generator.
  - Rich formatted output with syntax highlighting, bullet points, and clipboard export.

- **Settings & Configuration**:
  - Custom SQLite database path selector.
  - Telegram alert integration (Bot Token & Chat ID test sender).
  - Gemini API key management.
  - Windows 11 Light / Dark appearance toggle.

---

## Installation & Setup

### Prerequisites
- Windows 10 or Windows 11
- Python 3.10+ (Tested on Python 3.14.7)

### 1. Clone the repository
```bash
git clone https://github.com/praneeththilina/CSE-ANALYZER.git
cd CSE-ANALYZER
```

### 2. Create and activate a virtual environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

### 4. Configuration (Optional)
Copy `.env.example` to `.env` and add your Telegram bot credentials or Gemini API key:
```powershell
copy .env.example .env
```

---

## Running the App

### Option 1: Double-Click Launcher
Double-click `run.bat` in the project root folder.

### Option 2: Terminal
```powershell
python main.py
```

---

## Tech Stack
- **GUI**: Python `tkinter` + `ttk`
- **Theme**: `sv-ttk` (Sun Valley Windows 11 Light Theme) + `pywinstyles` (Mica title bar)
- **Data & Calculations**: `pandas`, `numpy`, SQLite3
- **Visualization**: `matplotlib`, `mplfinance`
- **AI**: Google Gemini API via `requests`

---

## License
MIT License. See [LICENSE](LICENSE) for details.
