# App Design Scraper - Application Design Analyzer

Web application for analyzing app design and extracting key information about the visual configuration.

## Features

The app inspects a target webpage and extracts:

- **Basic Information**: Name, description, URL
- **Icons**: Front icon, background icon, background color
- **Splash Screen**: Icon and color
- **Fonts**: Fonts used on the page
- **Colors**: Primary, secondary, tertiary
- **UI Specifications**: Shadow, border, corner radius, item spacing

## Installation

### 1. Create the conda environment

```bash
conda env create -f environment.yml
```

### 2. Activate the environment

```bash
conda activate app_design_scraper
```

### 3. Install dependencies (pip alternative)

If you prefer pip:

```bash
pip install -r requirements.txt
```

## Running the app

```bash
python app.py
```

The application will be available at `http://localhost:5000`.

## Usage

1. Open your browser and navigate to `http://localhost:5000`
2. Enter the URL of the website you want to analyze
3. Click the "Analyze" button
4. Review the results displayed below the form

## Project structure

```
app_design_scraper/
├── app.py              # Flask application
├── scraper.py          # Core scraping and analysis logic
├── templates/
│   └── index.html      # HTML template
├── environment.yml     # Conda environment definition
├── requirements.txt    # Python dependencies
└── README.md           # Documentation
```

## Dependencies

- **Flask**: Web framework
- **requests**: HTTP client
- **beautifulsoup4**: HTML parsing
- **lxml**: HTML parser backend
- **cssutils**: CSS parsing
- **pillow**: Image manipulation
- **webcolors**: Color utilities

## Notes

- The app sets a custom User-Agent for better compatibility with websites
- Some information may be missing depending on the inspected page
- Analysis can take a few seconds based on page size

