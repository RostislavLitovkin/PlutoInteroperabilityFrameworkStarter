# App Design Scraper - Analyzátor designu aplikací

Webová aplikace pro analýzu designu aplikací a extrakci klíčových informací o vizuální konfiguraci.

## Funkce

Aplikace analyzuje webovou stránku a extrahuje:

- **Základní informace**: Název, popis, URL
- **Ikony**: Front icon, Background icon, Background color
- **Splash Screen**: Icon a barva
- **Fonty**: Použité fonty na stránce
- **Barvy**: Primary, Secondary, Tertiary
- **UI Specifikace**: Shadow, Border, Corner Radius, Item Spacing

## Instalace

### 1. Vytvoření conda prostředí

```bash
conda env create -f environment.yml
```

### 2. Aktivace prostředí

```bash
conda activate app_design_scraper
```

### 3. Instalace závislostí (alternativa k conda)

Pokud preferujete pip:

```bash
pip install -r requirements.txt
```

## Spuštění

```bash
python app.py
```

Aplikace poběží na `http://localhost:5000`

## Použití

1. Otevřete prohlížeč a přejděte na `http://localhost:5000`
2. Zadejte URL webové stránky, kterou chcete analyzovat
3. Klikněte na tlačítko "Analyzovat"
4. Výsledky se zobrazí níže

## Struktura projektu

```
app_design_scraper/
├── app.py              # Flask aplikace
├── scraper.py          # Hlavní logika pro scraping a analýzu
├── templates/
│   └── index.html      # HTML template
├── environment.yml      # Conda environment
├── requirements.txt     # Python závislosti
└── README.md           # Tento soubor
```

## Závislosti

- **Flask**: Web framework
- **requests**: HTTP požadavky
- **beautifulsoup4**: Parsování HTML
- **lxml**: HTML parser
- **cssutils**: Parsování CSS
- **pillow**: Práce s obrázky
- **webcolors**: Práce s barvami

## Poznámky

- Aplikace používá User-Agent pro lepší kompatibilitu s webovými stránkami
- Některé informace nemusí být dostupné na všech stránkách
- Analýza může trvat několik sekund v závislosti na velikosti stránky

