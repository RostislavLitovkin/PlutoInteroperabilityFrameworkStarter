import requests
from bs4 import BeautifulSoup
import cssutils
import re
from urllib.parse import urljoin, urlparse
import base64
from io import BytesIO
from PIL import Image
import webcolors

class WebAnalyzer:
    def __init__(self, url):
        self.url = url
        self.base_url = url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.soup = None
        self.css_rules = []
        
    def fetch_page(self):
        """Načte HTML stránku"""
        try:
            response = self.session.get(self.url, timeout=10)
            response.raise_for_status()
            self.soup = BeautifulSoup(response.content, 'lxml')
            self.base_url = response.url  # Aktualizace base_url pro relativní odkazy
            return True
        except Exception as e:
            raise Exception(f"Chyba při načítání stránky: {str(e)}")
    
    def fetch_css(self, css_url):
        """Načte CSS soubor"""
        try:
            full_url = urljoin(self.base_url, css_url)
            response = self.session.get(full_url, timeout=10)
            return response.text
        except:
            return None
    
    def extract_title(self):
        """Extrahuje název webu"""
        # Zkusíme různé zdroje
        title = None
        
        # 1. Meta title
        meta_title = self.soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            title = meta_title.get('content')
        
        # 2. Title tag
        if not title:
            title_tag = self.soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
        
        # 3. H1 jako fallback
        if not title:
            h1 = self.soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
        
        return title or "Neznámý název"
    
    def extract_description(self):
        """Extrahuje popis webu"""
        description = None
        
        # 1. Meta description
        meta_desc = self.soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description = meta_desc.get('content')
        
        # 2. Open Graph description
        if not description:
            og_desc = self.soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                description = og_desc.get('content')
        
        return description or ""
    
    def extract_icons(self):
        """Extrahuje ikony (favicon, apple-touch-icon, atd.)"""
        icons = {
            'front_icon': None,
            'background_icon': None,
            'background_color': None
        }
        
        # Hledání různých typů ikon
        icon_links = self.soup.find_all('link', rel=re.compile(r'icon|apple-touch-icon|shortcut', re.I))
        
        # Seřadíme podle priority (větší ikony mají přednost)
        sorted_icons = []
        for link in icon_links:
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                rel = link.get('rel', [])
                sizes = link.get('sizes', '')
                
                # Priorita: apple-touch-icon > icon s sizes > icon
                priority = 0
                if any('apple-touch-icon' in r.lower() for r in rel):
                    priority = 3
                elif sizes and sizes != 'any':
                    priority = 2
                else:
                    priority = 1
                
                sorted_icons.append((priority, full_url, rel))
        
        # Seřadíme podle priority
        sorted_icons.sort(key=lambda x: x[0], reverse=True)
        
        for priority, full_url, rel in sorted_icons:
            if any('apple-touch-icon' in r.lower() for r in rel):
                if not icons['front_icon']:
                    icons['front_icon'] = full_url
            elif any('icon' in r.lower() for r in rel):
                if not icons['front_icon']:
                    icons['front_icon'] = full_url
                if not icons['background_icon']:
                    icons['background_icon'] = full_url
        
        # Fallback na standardní favicon.ico
        if not icons['front_icon']:
            favicon_url = urljoin(self.base_url, '/favicon.ico')
            try:
                response = self.session.head(favicon_url, timeout=5)
                if response.status_code == 200:
                    icons['front_icon'] = favicon_url
                    icons['background_icon'] = favicon_url
            except:
                pass
        
        # Zkusíme najít barvu pozadí z více zdrojů
        background_color = None
        
        # 1. Meta theme-color
        theme_color = self.soup.find('meta', attrs={'name': 'theme-color'})
        if theme_color and theme_color.get('content'):
            background_color = self.normalize_color(theme_color.get('content'))
        
        # 2. Meta msapplication-TileColor
        if not background_color:
            ms_tile = self.soup.find('meta', attrs={'name': 'msapplication-TileColor'})
            if ms_tile and ms_tile.get('content'):
                background_color = self.normalize_color(ms_tile.get('content'))
        
        # 3. CSS - background-color z body nebo html
        if not background_color:
            css_text = self.get_all_css()
            bg_matches = re.findall(r'(?:body|html)[^{]*\{[^}]*background(?:-color)?:\s*([^;]+)', css_text, re.I)
            if bg_matches:
                for match in bg_matches:
                    color = self.normalize_color(match.strip())
                    if color and color.startswith('#'):
                        background_color = color
                        break
        
        # 4. Inline style z body tagu
        if not background_color:
            body = self.soup.find('body')
            if body and body.get('style'):
                style = body.get('style')
                bg_match = re.search(r'background(?:-color)?:\s*([^;]+)', style, re.I)
                if bg_match:
                    background_color = self.normalize_color(bg_match.group(1).strip())
        
        icons['background_color'] = background_color
        
        return icons
    
    def extract_splash_screen(self):
        """Extrahuje informace o splash screen"""
        splash = {
            'icon': None,
            'color': None
        }
        
        # Apple splash screen - hledáme všechny možné varianty
        startup_images = self.soup.find_all('link', rel=re.compile(r'apple-touch-startup-image', re.I))
        
        # Seřadíme podle velikosti (větší má přednost)
        sorted_images = []
        for img in startup_images:
            href = img.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                media = img.get('media', '')
                # Extrahujeme rozlišení z media query
                size_match = re.search(r'(\d+)x(\d+)', media)
                if size_match:
                    width, height = map(int, size_match.groups())
                    sorted_images.append((width * height, full_url))
                else:
                    sorted_images.append((0, full_url))
        
        if sorted_images:
            sorted_images.sort(key=lambda x: x[0], reverse=True)
            splash['icon'] = sorted_images[0][1]
        
        # Fallback: použijeme největší apple-touch-icon
        if not splash['icon']:
            apple_icons = self.soup.find_all('link', rel=re.compile(r'apple-touch-icon', re.I))
            largest_icon = None
            largest_size = 0
            for icon in apple_icons:
                href = icon.get('href')
                if href:
                    sizes = icon.get('sizes', '')
                    size_match = re.search(r'(\d+)x(\d+)', sizes)
                    if size_match:
                        width, height = map(int, size_match.groups())
                        if width * height > largest_size:
                            largest_size = width * height
                            largest_icon = urljoin(self.base_url, href)
                    elif not largest_icon:
                        largest_icon = urljoin(self.base_url, href)
            
            if largest_icon:
                splash['icon'] = largest_icon
        
        # Barva splash screen - více zdrojů
        splash_color = None
        
        # 1. Meta theme-color
        theme_color = self.soup.find('meta', attrs={'name': 'theme-color'})
        if theme_color and theme_color.get('content'):
            splash_color = self.normalize_color(theme_color.get('content'))
        
        # 2. Meta apple-mobile-web-app-status-bar-style s barvou
        if not splash_color:
            status_bar = self.soup.find('meta', attrs={'name': 'apple-mobile-web-app-status-bar-style'})
            if status_bar:
                content = status_bar.get('content', '').lower()
                # black-translucent nebo default
                if 'black' in content:
                    splash_color = '#000000'
                elif 'default' in content:
                    # Zkusíme najít barvu z CSS
                    css_text = self.get_all_css()
                    bg_matches = re.findall(r'background(?:-color)?:\s*([^;]+)', css_text, re.I)
                    if bg_matches:
                        for match in bg_matches[:5]:  # Zkontrolujeme prvních 5
                            color = self.normalize_color(match.strip())
                            if color and color.startswith('#'):
                                splash_color = color
                                break
        
        # 3. CSS - background-color z hlavního kontejneru
        if not splash_color:
            css_text = self.get_all_css()
            # Hledáme v hlavních selektorech
            main_selectors = ['body', 'html', '#app', '#root', '.app', '.main', '.container']
            for selector in main_selectors:
                pattern = rf'{re.escape(selector)}[^{{]*\{{[^}}]*background(?:-color)?:\s*([^;]+)'
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    color = self.normalize_color(matches[0].strip())
                    if color and color.startswith('#'):
                        splash_color = color
                        break
        
        splash['color'] = splash_color
        
        return splash
    
    def extract_fonts(self):
        """Extrahuje použité fonty"""
        fonts = []
        font_set = set()
        
        # 1. Google Fonts
        google_fonts = self.soup.find_all('link', href=re.compile(r'fonts\.googleapis\.com|fonts\.gstatic\.com'))
        for link in google_fonts:
            href = link.get('href', '')
            # Extrahujeme název fontu z URL
            match = re.search(r'family=([^&:]+)', href)
            if match:
                font_name = match.group(1).replace('+', ' ').split(':')[0]  # Odstraníme varianty
                if font_name and font_name not in font_set:
                    fonts.append(font_name)
                    font_set.add(font_name)
        
        # 2. Adobe Fonts / Typekit
        adobe_fonts = self.soup.find_all('link', href=re.compile(r'use\.typekit\.net|use\.adobe\.com'))
        for link in adobe_fonts:
            # Zkusíme najít v CSS nebo JavaScript
            pass  # Adobe fonts jsou obvykle načteny přes JS
        
        # 3. Font-face v CSS
        css_text = self.get_all_css()
        font_face_matches = re.findall(r'@font-face\s*\{[^}]*font-family:\s*["\']?([^;"\']+)["\']?', css_text, re.I)
        for font in font_face_matches:
            font_clean = font.strip().strip('"\'')
            # Odstraníme fallback fonty (za čárkou)
            font_clean = font_clean.split(',')[0].strip()
            if font_clean and font_clean not in font_set:
                fonts.append(font_clean)
                font_set.add(font_clean)
        
        # 4. Font-family z CSS selektorů (prioritní selektory)
        priority_selectors = ['body', 'html', 'h1', 'h2', 'h3', '.heading', '.title', '.text', 'p']
        for selector in priority_selectors:
            pattern = rf'{re.escape(selector)}[^{{]*\{{[^}}]*font-family:\s*["\']?([^;"\']+)["\']?'
            matches = re.findall(pattern, css_text, re.I)
            for match in matches:
                font_clean = match.strip().strip('"\'')
                font_clean = font_clean.split(',')[0].strip()
                # Odstraníme systémové fonty
                if font_clean and font_clean.lower() not in ['inherit', 'initial', 'unset', 'serif', 'sans-serif', 'monospace']:
                    if font_clean not in font_set:
                        fonts.append(font_clean)
                        font_set.add(font_clean)
        
        # 5. Font-family z inline stylů
        style_tags = self.soup.find_all('style')
        for style in style_tags:
            font_matches = re.findall(r'font-family:\s*["\']?([^;"\']+)["\']?', style.string or '', re.I)
            for match in font_matches:
                font_clean = match.strip().strip('"\'')
                font_clean = font_clean.split(',')[0].strip()
                if font_clean and font_clean.lower() not in ['inherit', 'initial', 'unset', 'serif', 'sans-serif', 'monospace']:
                    if font_clean not in font_set:
                        fonts.append(font_clean)
                        font_set.add(font_clean)
        
        # 6. Font-family z inline style atributů
        elements_with_style = self.soup.find_all(attrs={'style': re.compile(r'font-family', re.I)})
        for element in elements_with_style[:10]:  # Limit pro výkon
            style = element.get('style', '')
            font_match = re.search(r'font-family:\s*["\']?([^;"\']+)["\']?', style, re.I)
            if font_match:
                font_clean = font_match.group(1).strip().strip('"\'')
                font_clean = font_clean.split(',')[0].strip()
                if font_clean and font_clean.lower() not in ['inherit', 'initial', 'unset', 'serif', 'sans-serif', 'monospace']:
                    if font_clean not in font_set:
                        fonts.append(font_clean)
                        font_set.add(font_clean)
        
        return fonts[:10]  # Vrátíme max 10 fontů
    
    def get_all_css(self):
        """Získá veškerý CSS kód ze stránky"""
        css_text = ""
        
        # Inline CSS v style tagách
        style_tags = self.soup.find_all('style')
        for style in style_tags:
            if style.string:
                css_text += style.string + "\n"
        
        # Externí CSS soubory
        css_links = self.soup.find_all('link', rel='stylesheet')
        for link in css_links:
            href = link.get('href')
            if href:
                css_content = self.fetch_css(href)
                if css_content:
                    css_text += css_content + "\n"
        
        return css_text
    
    def extract_colors(self):
        """Extrahuje barvy z CSS a HTML"""
        colors = {
            'primary': None,
            'secondary': None,
            'tertiary': None
        }
        
        css_text = self.get_all_css()
        
        # 1. Extrakce CSS proměnných (nejspolehlivější)
        css_vars = {}
        var_matches = re.findall(r'--([^:]+):\s*([^;]+)', css_text)
        for var_name, var_value in var_matches:
            var_name_lower = var_name.lower().strip()
            var_value_clean = var_value.strip().strip('"\'')
            css_vars[var_name_lower] = var_value_clean
        
        # Hledání primary, secondary, tertiary v CSS proměnných
        primary_keys = [k for k in css_vars.keys() if 'primary' in k and ('color' in k or 'main' in k or k == 'primary')]
        secondary_keys = [k for k in css_vars.keys() if 'secondary' in k and ('color' in k or 'main' in k or k == 'secondary')]
        tertiary_keys = [k for k in css_vars.keys() if 'tertiary' in k and ('color' in k or 'main' in k or k == 'tertiary')]
        
        if primary_keys:
            colors['primary'] = self.normalize_color(css_vars[primary_keys[0]])
        if secondary_keys:
            colors['secondary'] = self.normalize_color(css_vars[secondary_keys[0]])
        if tertiary_keys:
            colors['tertiary'] = self.normalize_color(css_vars[tertiary_keys[0]])
        
        # 2. Hledání v CSS selektorech (.primary, .secondary, atd.)
        if not colors['primary']:
            primary_selectors = [r'\.primary[^{]*\{[^}]*color:\s*([^;]+)',
                                r'\.btn-primary[^{]*\{[^}]*background(?:-color)?:\s*([^;]+)',
                                r'\.primary-color[^{]*\{[^}]*color:\s*([^;]+)']
            for pattern in primary_selectors:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    colors['primary'] = self.normalize_color(matches[0].strip())
                    break
        
        if not colors['secondary']:
            secondary_selectors = [r'\.secondary[^{]*\{[^}]*color:\s*([^;]+)',
                                   r'\.btn-secondary[^{]*\{[^}]*background(?:-color)?:\s*([^;]+)',
                                   r'\.secondary-color[^{]*\{[^}]*color:\s*([^;]+)']
            for pattern in secondary_selectors:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    colors['secondary'] = self.normalize_color(matches[0].strip())
                    break
        
        if not colors['tertiary']:
            tertiary_selectors = [r'\.tertiary[^{]*\{[^}]*color:\s*([^;]+)',
                                  r'\.btn-tertiary[^{]*\{[^}]*background(?:-color)?:\s*([^;]+)']
            for pattern in tertiary_selectors:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    colors['tertiary'] = self.normalize_color(matches[0].strip())
                    break
        
        # 3. Hledání v hlavních UI elementech (buttons, links, atd.)
        if not colors['primary']:
            ui_patterns = [
                r'button[^{]*\{[^}]*background(?:-color)?:\s*([^;]+)',
                r'\.btn[^{]*\{[^}]*background(?:-color)?:\s*([^;]+)',
                r'a[^{]*\{[^}]*color:\s*([^;]+)',
            ]
            for pattern in ui_patterns:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    color = self.normalize_color(matches[0].strip())
                    if color and color.startswith('#') and color != '#000000' and color != '#ffffff':
                        colors['primary'] = color
                        break
        
        # 4. Fallback: hledání nejčastějších barev (kromě černé a bílé)
        if not all(colors.values()):
            common_colors = self.find_common_colors(css_text)
            if not colors['primary'] and len(common_colors) > 0:
                colors['primary'] = common_colors[0]
            if not colors['secondary'] and len(common_colors) > 1:
                colors['secondary'] = common_colors[1]
            if not colors['tertiary'] and len(common_colors) > 2:
                colors['tertiary'] = common_colors[2]
        
        return colors
    
    def normalize_color(self, color_value):
        """Normalizuje barvu do hex formátu"""
        color_value = color_value.strip().strip('"\'')
        
        # Pokud už je hex
        if re.match(r'^#?[0-9A-Fa-f]{3,6}$', color_value):
            return '#' + color_value.lstrip('#')
        
        # Pokud je RGB/RGBA
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color_value)
        if rgb_match:
            r, g, b = rgb_match.groups()
            return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
        
        # Zkusíme webcolors pro pojmenované barvy
        try:
            rgb = webcolors.name_to_rgb(color_value)
            return f"#{rgb.red:02x}{rgb.green:02x}{rgb.blue:02x}"
        except:
            pass
        
        return color_value
    
    def find_common_colors(self, css_text):
        """Najde nejčastější barvy v CSS"""
        color_pattern = r'(?:#(?:[0-9a-fA-F]{3}){1,2}|rgb\([^)]+\)|rgba\([^)]+\)|hsl\([^)]+\)|hsla\([^)]+\)|[a-zA-Z]+)'
        colors = re.findall(color_pattern, css_text)
        
        # Filtrujeme běžné slova, která nejsou barvy
        exclude_words = {'transparent', 'inherit', 'initial', 'unset', 'none', 'auto', 'currentcolor', 'current-color'}
        # Také vyloučíme černou a bílou (jsou příliš běžné)
        colors = [c for c in colors if c.lower() not in exclude_words]
        
        # Normalizujeme a počítáme
        normalized = {}
        for color in colors[:100]:  # Zvýšili jsme limit
            normalized_color = self.normalize_color(color)
            if normalized_color and normalized_color.startswith('#'):
                # Vyloučíme černou a bílou
                if normalized_color.lower() not in ['#000000', '#000', '#ffffff', '#fff', '#fff', '#ffffff']:
                    normalized[normalized_color] = normalized.get(normalized_color, 0) + 1
        
        # Seřadíme podle četnosti
        sorted_colors = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
        return [color for color, count in sorted_colors[:5]]  # Vrátíme top 5
    
    def extract_ui_specs(self):
        """Extrahuje další UI specifikace"""
        specs = {
            'shadow': {
                'color': None,
                'opacity': None,
                'angle': None
            },
            'border': {
                'color': None,
                'thickness': None
            },
            'corner_radius': None,
            'item_spacing': None
        }
        
        css_text = self.get_all_css()
        
        # Shadow
        shadow_matches = re.findall(r'box-shadow:\s*([^;]+)', css_text, re.I)
        if shadow_matches:
            shadow_value = shadow_matches[0]
            # Parsování shadow (x y blur spread color)
            shadow_parts = shadow_value.split()
            if len(shadow_parts) >= 4:
                # Barva je obvykle poslední
                for part in reversed(shadow_parts):
                    if '#' in part or 'rgb' in part or part in webcolors.CSS3_NAMES_TO_HEX:
                        specs['shadow']['color'] = self.normalize_color(part)
                        break
                # Úhel můžeme odvodit z x, y offsetů
                if len(shadow_parts) >= 2:
                    try:
                        x, y = float(shadow_parts[0]), float(shadow_parts[1])
                        import math
                        angle = math.degrees(math.atan2(y, x))
                        specs['shadow']['angle'] = f"{angle:.1f}°"
                    except:
                        pass
        
        # Border
        border_matches = re.findall(r'border(?:-width)?:\s*([^;]+)', css_text, re.I)
        if border_matches:
            border_value = border_matches[0]
            # Parsování border (width style color)
            border_parts = border_value.split()
            for part in border_parts:
                if part.replace('.', '').replace('px', '').isdigit():
                    specs['border']['thickness'] = part
                elif '#' in part or 'rgb' in part or part in webcolors.CSS3_NAMES_TO_HEX:
                    specs['border']['color'] = self.normalize_color(part)
        
        # Border color explicitně
        border_color_matches = re.findall(r'border-color:\s*([^;]+)', css_text, re.I)
        if border_color_matches and not specs['border']['color']:
            specs['border']['color'] = self.normalize_color(border_color_matches[0])
        
        # Corner radius
        radius_matches = re.findall(r'border-radius:\s*([^;]+)', css_text, re.I)
        if radius_matches:
            specs['corner_radius'] = radius_matches[0].strip()
        
        # Item spacing (gap, margin, padding)
        gap_matches = re.findall(r'gap:\s*([^;]+)', css_text, re.I)
        if gap_matches:
            specs['item_spacing'] = gap_matches[0].strip()
        else:
            margin_matches = re.findall(r'margin:\s*([^;]+)', css_text, re.I)
            if margin_matches:
                specs['item_spacing'] = margin_matches[0].strip()
        
        return specs
    
    def extract_links(self):
        """Extrahuje všechny odkazy ze stránky"""
        links = []
        seen_urls = set()
        
        # Najdeme všechny <a> tagy s href atributem
        anchor_tags = self.soup.find_all('a', href=True)
        
        for anchor in anchor_tags:
            href = anchor.get('href', '').strip()
            if not href:
                continue
            
            # Přeskočíme javascript: a mailto: odkazy (nebo je můžeme zahrnout)
            if href.startswith('javascript:') or href.startswith('#'):
                continue
            
            # Normalizujeme URL na absolutní
            try:
                full_url = urljoin(self.base_url, href)
                parsed_url = urlparse(full_url)
                
                # Přeskočíme prázdné nebo neplatné URL
                if not parsed_url.netloc:
                    continue
                
                # Získáme text odkazu
                link_text = anchor.get_text(strip=True)
                if not link_text:
                    # Pokud není text, zkusíme title nebo alt
                    link_text = anchor.get('title', '') or anchor.get('alt', '') or href
                
                # Získáme další atributy
                title = anchor.get('title', '')
                target = anchor.get('target', '')
                rel = anchor.get('rel', [])
                
                # Určíme, zda je interní nebo externí odkaz
                base_domain = urlparse(self.base_url).netloc
                is_internal = parsed_url.netloc == base_domain or parsed_url.netloc == ''
                
                # Vytvoříme unikátní klíč (URL + text, aby se odlišily duplikáty s různým textem)
                link_key = (full_url, link_text[:50])  # Použijeme prvních 50 znaků textu
                
                if link_key not in seen_urls:
                    seen_urls.add(link_key)
                    links.append({
                        'url': full_url,
                        'text': link_text[:200],  # Omezíme délku textu
                        'title': title,
                        'target': target,
                        'rel': ' '.join(rel) if isinstance(rel, list) else rel,
                        'is_internal': is_internal
                    })
            except Exception as e:
                # Přeskočíme neplatné URL
                continue
        
        # Seřadíme odkazy (nejdřív interní, pak externí)
        links.sort(key=lambda x: (not x['is_internal'], x['url']))
        
        return links
    
    def analyze(self):
        """Hlavní metoda pro analýzu webu"""
        self.fetch_page()
        
        result = {
            'url': self.url,
            'title': self.extract_title(),
            'description': self.extract_description(),
            'icons': self.extract_icons(),
            'splash_screen': self.extract_splash_screen(),
            'fonts': self.extract_fonts(),
            'colors': self.extract_colors(),
            'ui_specs': self.extract_ui_specs(),
            'links': self.extract_links()
        }
        
        return result

