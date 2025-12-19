from flask import Flask, render_template, request, jsonify
from scraper import WebAnalyzer
import traceback

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'URL není zadána'}), 400
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        analyzer = WebAnalyzer(url)
        result = analyzer.analyze()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

