# KriptoAnaliz Web Application

## Overview
KriptoAnaliz is a web application that fetches cryptocurrency data from the Binance API and displays it with technical indicators. The application provides insights into market trends and supports analysis through various technical indicators.

## Project Structure
```
kriptoanaliz-web
├── app
│   ├── __init__.py
│   ├── routes.py
│   ├── templates
│   │   └── index.html
│   ├── static
│   │   └── style.css
│   └── data_utils.py
├── requirements.txt
├── run.py
└── README.md
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd kriptoanaliz-web
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Windows:
     ```
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python run.py
   ```

2. Open your web browser and go to `http://127.0.0.1:5000` to view the application.

## Features
- Fetches cryptocurrency data from the Binance API.
- Calculates technical indicators such as RSI and MACD.
- Displays support and resistance levels based on historical data.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for details.