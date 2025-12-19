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
        title = None
        meta_title = self.soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            title = meta_title.get('content')
        if not title:
            title_tag = self.soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
        if not title:
            h1 = self.soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
        return title or "Neznámý název"
    
    def extract_description(self):
        """Extrahuje popis webu"""
        description = None
        meta_desc = self.soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description = meta_desc.get('content')
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
        icon_links = self.soup.find_all('link', rel=re.compile(r'icon|apple-touch-icon|shortcut', re.I))
        sorted_icons = []
        for link in icon_links:
            href = link.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                rel = link.get('rel', [])
                sizes = link.get('sizes', '')
                priority = 0
                if any('apple-touch-icon' in r.lower() for r in rel):
                    priority = 3
                elif sizes and sizes != 'any':
                    priority = 2
                else:
                    priority = 1
                sorted_icons.append((priority, full_url, rel))
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
        if not icons['front_icon']:
            favicon_url = urljoin(self.base_url, '/favicon.ico')
            try:
                response = self.session.head(favicon_url, timeout=5)
                if response.status_code == 200:
                    icons['front_icon'] = favicon_url
                    icons['background_icon'] = favicon_url
            except:
                pass
        background_color = None
        theme_color = self.soup.find('meta', attrs={'name': 'theme-color'})
        if theme_color and theme_color.get('content'):
            background_color = self.normalize_color(theme_color.get('content'))
        if not background_color:
            ms_tile = self.soup.find('meta', attrs={'name': 'msapplication-TileColor'})
            if ms_tile and ms_tile.get('content'):
                background_color = self.normalize_color(ms_tile.get('content'))
        if not background_color:
            css_text = self.get_all_css()
            bg_matches = re.findall(r'(?:body|html)[^{]*\{[^}]*background(?:-color)?:\s*([^;]+)', css_text, re.I)
            if bg_matches:
                for match in bg_matches:
                    color = self.normalize_color(match.strip())
                    if color and color.startswith('#'):
                        background_color = color
                        break
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
        startup_images = self.soup.find_all('link', rel=re.compile(r'apple-touch-startup-image', re.I))
        sorted_images = []
        for img in startup_images:
            href = img.get('href')
            if href:
                full_url = urljoin(self.base_url, href)
                media = img.get('media', '')
                size_match = re.search(r'(\d+)x(\d+)', media)
                if size_match:
                    width, height = map(int, size_match.groups())
                    sorted_images.append((width * height, full_url))
                else:
                    sorted_images.append((0, full_url))
        if sorted_images:
            sorted_images.sort(key=lambda x: x[0], reverse=True)
            splash['icon'] = sorted_images[0][1]
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
        splash_color = None
        theme_color = self.soup.find('meta', attrs={'name': 'theme-color'})
        if theme_color and theme_color.get('content'):
            splash_color = self.normalize_color(theme_color.get('content'))
        if not splash_color:
            status_bar = self.soup.find('meta', attrs={'name': 'apple-mobile-web-app-status-bar-style'})
            if status_bar:
                content = status_bar.get('content', '').lower()
                if 'black' in content:
                    splash_color = '#000000'
                elif 'default' in content:
                    css_text = self.get_all_css()
                    bg_matches = re.findall(r'background(?:-color)?:\s*([^;]+)', css_text, re.I)
                    if bg_matches:
                        for match in bg_matches[:5]:
                            color = self.normalize_color(match.strip())
                            if color and color.startswith('#'):
                                splash_color = color
                                break
        if not splash_color:
            css_text = self.get_all_css()
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
        """Extrahuje použité fonty a jejich definice"""
        fonts = []
        font_set = set()
        font_styles = []
        style_map = {}
        font_urls = {}
        visited_imports = set()
        
        def normalize_font_name(font_name):
            if not font_name:
                return None
            cleaned = font_name.split(',')[0].strip().strip("\"'")
            if cleaned.lower() in ['inherit', 'initial', 'unset', 'serif', 'sans-serif', 'monospace']:
                return None
            return cleaned
        
        def add_font(font_name):
            normalized = normalize_font_name(font_name)
            if not normalized:
                return None
            if normalized not in font_set:
                fonts.append(normalized)
                font_set.add(normalized)
            return normalized
        
        def absolutize_font_urls(css_block, base):
            def replace(match):
                raw_url = match.group(1).strip().strip("\"'")
                if raw_url.startswith('data:') or raw_url.startswith('http://') or raw_url.startswith('https://'):
                    resolved = raw_url
                else:
                    resolved = urljoin(base, raw_url) if base else raw_url
                return f"url('{resolved}')"
            return re.sub(r'url\(([^)]+)\)', replace, css_block)
        
        def inline_imports(css_content, base_url, depth=0):
            if depth > 3 or not css_content:
                return css_content or ''
            
            def replace(match):
                import_target = match.group(1).strip().strip("\"'")
                full_url = urljoin(base_url, import_target) if base_url else import_target
                if full_url in visited_imports:
                    return ''
                visited_imports.add(full_url)
                imported_css = self.fetch_css(full_url)
                if not imported_css:
                    return ''
                return inline_imports(imported_css, full_url, depth + 1)
            return re.sub(r'@import\s+(?:url\()?["\']?([^);\s]+)["\']?\s*\)?\s*;?', replace, css_content, flags=re.I)
        
        google_fonts = self.soup.find_all('link', href=re.compile(r'fonts\.googleapis\.com|fonts\.gstatic\.com'))
        for link in google_fonts:
            href = link.get('href', '')
            match = re.search(r'family=([^&:]+)', href)
            if match:
                font_name = match.group(1).replace('+', ' ').split(':')[0]
                add_font(font_name)
        
        css_sources = []
        style_tags = self.soup.find_all('style')
        for style in style_tags:
            if style.string:
                inlined = inline_imports(style.string, self.base_url)
                css_sources.append({'content': inlined, 'base': self.base_url})
        
        def is_stylesheet_link(link):
            rel_values = link.get('rel') or []
            if isinstance(rel_values, str):
                rel_values = [rel_values]
            rel_values = [r.lower() for r in rel_values]
            as_attr = (link.get('as') or '').lower()
            if 'stylesheet' in rel_values:
                return True
            return 'preload' in rel_values and as_attr == 'style'
        
        fetched_css_urls = set()
        css_links = self.soup.find_all('link')
        for link in css_links:
            if not is_stylesheet_link(link):
                continue
            href = link.get('href')
            if not href:
                continue
            full_url = urljoin(self.base_url, href)
            if full_url in fetched_css_urls:
                continue
            css_content = self.fetch_css(full_url)
            if css_content:
                inlined = inline_imports(css_content, full_url)
                css_sources.append({'content': inlined, 'base': full_url})
                fetched_css_urls.add(full_url)
        
        css_text = "\n".join(source['content'] for source in css_sources)
        font_face_pattern = re.compile(r'@font-face\s*\{[^}]+\}', re.I | re.S)
        for source in css_sources:
            content = source['content']
            base = source['base']
            for match in font_face_pattern.finditer(content):
                block = match.group(0)
                family_match = re.search(r'font-family:\s*["\']?([^;"\']+)["\']?', block, re.I)
                if not family_match:
                    continue
                family_name = normalize_font_name(family_match.group(1))
                if not family_name:
                    continue
                add_font(family_name)
                absolutized_block = absolutize_font_urls(block, base)
                # Collect first downloadable font URL for this family
                found_urls = re.findall(r"url\(['\"]?([^'\"\)]+)['\"]?\)", absolutized_block)
                preferred_url = None
                for candidate in found_urls:
                    if candidate.startswith('http://') or candidate.startswith('https://'):
                        preferred_url = candidate
                        break
                    if not preferred_url and candidate.startswith('data:'):
                        preferred_url = candidate
                if preferred_url:
                    font_urls.setdefault(family_name, preferred_url)
                if family_name not in style_map:
                    font_styles.append({'name': family_name, 'css': absolutized_block})
                    style_map[family_name] = True
        
        priority_selectors = ['body', 'html', 'h1', 'h2', 'h3', '.heading', '.title', '.text', 'p']
        for selector in priority_selectors:
            pattern = rf'{re.escape(selector)}[^{{]*\{{[^}}]*font-family:\s*["\']?([^;"\']+)["\']?'
            matches = re.findall(pattern, css_text, re.I)
            for match in matches:
                add_font(match)
        
        for style in style_tags:
            font_matches = re.findall(r'font-family:\s*["\']?([^;"\']+)["\']?', style.string or '', re.I)
            for match in font_matches:
                add_font(match)
        
        elements_with_style = self.soup.find_all(attrs={'style': re.compile(r'font-family', re.I)})
        for element in elements_with_style[:10]:
            style = element.get('style', '')
            font_match = re.search(r'font-family:\s*["\']?([^;"\']+)["\']?', style, re.I)
            if font_match:
                add_font(font_match.group(1))
        
        selected_names = fonts[:10]
        selected_styles = []
        seen_families = set()
        for entry in font_styles:
            if entry['name'] in selected_names and entry['name'] not in seen_families:
                selected_styles.append(entry['css'])
                seen_families.add(entry['name'])
        
        return {
            'names': selected_names,
            'styles': selected_styles,
            'urls': {name: font_urls.get(name) for name in selected_names}
        }
    
    def get_all_css(self):
        """Získá veškerý CSS kód ze stránky"""
        css_text = ""
        style_tags = self.soup.find_all('style')
        for style in style_tags:
            if style.string:
                css_text += style.string + "\n"
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
        css_vars = {}
        var_matches = re.findall(r'--([^:]+):\s*([^;]+)', css_text)
        for var_name, var_value in var_matches:
            var_name_lower = var_name.lower().strip()
            var_value_clean = var_value.strip().strip('"\'')
            css_vars[var_name_lower] = var_value_clean
        primary_keys = [k for k in css_vars.keys() if 'primary' in k and ('color' in k or 'main' in k or k == 'primary')]
        secondary_keys = [k for k in css_vars.keys() if 'secondary' in k and ('color' in k or 'main' in k or k == 'secondary')]
        tertiary_keys = [k for k in css_vars.keys() if 'tertiary' in k and ('color' in k or 'main' in k or k == 'tertiary')]
        if primary_keys:
            colors['primary'] = self.normalize_color(css_vars[primary_keys[0]])
        if secondary_keys:
            colors['secondary'] = self.normalize_color(css_vars[secondary_keys[0]])
        if tertiary_keys:
            colors['tertiary'] = self.normalize_color(css_vars[tertiary_keys[0]])
        if not colors['primary']:
            primary_selectors = [r'\.primary[^{}]*\{[^}]*color:\s*([^;]+)', r'\.btn-primary[^{}]*\{[^}]*background(?:-color)?:\s*([^;]+)', r'\.primary-color[^{}]*\{[^}]*color:\s*([^;]+)']
            for pattern in primary_selectors:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    colors['primary'] = self.normalize_color(matches[0].strip())
                    break
        if not colors['secondary']:
            secondary_selectors = [r'\.secondary[^{}]*\{[^}]*color:\s*([^;]+)', r'\.btn-secondary[^{}]*\{[^}]*background(?:-color)?:\s*([^;]+)', r'\.secondary-color[^{}]*\{[^}]*color:\s*([^;]+)']
            for pattern in secondary_selectors:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    colors['secondary'] = self.normalize_color(matches[0].strip())
                    break
        if not colors['tertiary']:
            tertiary_selectors = [r'\.tertiary[^{}]*\{[^}]*color:\s*([^;]+)', r'\.btn-tertiary[^{}]*\{[^}]*background(?:-color)?:\s*([^;]+)']
            for pattern in tertiary_selectors:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    colors['tertiary'] = self.normalize_color(matches[0].strip())
                    break
        if not colors['primary']:
            ui_patterns = [r'button[^{}]*\{[^}]*background(?:-color)?:\s*([^;]+)', r'\.btn[^{}]*\{[^}]*background(?:-color)?:\s*([^;]+)', r'a[^{}]*\{[^}]*color:\s*([^;]+)']
            for pattern in ui_patterns:
                matches = re.findall(pattern, css_text, re.I)
                if matches:
                    color = self.normalize_color(matches[0].strip())
                    if color and color.startswith('#') and color != '#000000' and color != '#ffffff':
                        colors['primary'] = color
                        break
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
        color_value = color_value.strip().strip('"\'')
        if re.match(r'^#?[0-9A-Fa-f]{3,6}$', color_value):
            return '#' + color_value.lstrip('#')
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color_value)
        if rgb_match:
            r, g, b = rgb_match.groups()
            return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
        try:
            rgb = webcolors.name_to_rgb(color_value)
            return f"#{rgb.red:02x}{rgb.green:02x}{rgb.blue:02x}"
        except:
            pass
        return color_value
    
    def find_common_colors(self, css_text):
        color_pattern = r'(?:#(?:[0-9a-fA-F]{3}){1,2}|rgb\([^)]+\)|rgba\([^)]+\)|hsl\([^)]+\)|hsla\([^)]+\)|[a-zA-Z]+)'
        colors = re.findall(color_pattern, css_text)
        exclude_words = {'transparent', 'inherit', 'initial', 'unset', 'none', 'auto', 'currentcolor', 'current-color'}
        colors = [c for c in colors if c.lower() not in exclude_words]
        normalized = {}
        for color in colors[:100]:
            normalized_color = self.normalize_color(color)
            if normalized_color and normalized_color.startswith('#'):
                if normalized_color.lower() not in ['#000000', '#000', '#ffffff', '#fff', '#fff', '#ffffff']:
                    normalized[normalized_color] = normalized.get(normalized_color, 0) + 1
        sorted_colors = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
        return [color for color, count in sorted_colors[:5]]
    
    def extract_ui_specs(self):
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
        shadow_matches = re.findall(r'box-shadow:\s*([^;]+)', css_text, re.I)
        if shadow_matches:
            shadow_value = shadow_matches[0]
            shadow_parts = shadow_value.split()
            if len(shadow_parts) >= 4:
                for part in reversed(shadow_parts):
                    if '#' in part or 'rgb' in part or part in webcolors.CSS3_NAMES_TO_HEX:
                        specs['shadow']['color'] = self.normalize_color(part)
                        break
                if len(shadow_parts) >= 2:
                    try:
                        x, y = float(shadow_parts[0]), float(shadow_parts[1])
                        import math
                        angle = math.degrees(math.atan2(y, x))
                        specs['shadow']['angle'] = f"{angle:.1f}°"
                    except:
                        pass
        border_matches = re.findall(r'border(?:-width)?:\s*([^;]+)', css_text, re.I)
        if border_matches:
            border_value = border_matches[0]
            border_parts = border_value.split()
            for part in border_parts:
                if part.replace('.', '').replace('px', '').isdigit():
                    specs['border']['thickness'] = part
                elif '#' in part or 'rgb' in part or part in webcolors.CSS3_NAMES_TO_HEX:
                    specs['border']['color'] = self.normalize_color(part)
        border_color_matches = re.findall(r'border-color:\s*([^;]+)', css_text, re.I)
        if border_color_matches and not specs['border']['color']:
            specs['border']['color'] = self.normalize_color(border_color_matches[0])
        radius_matches = re.findall(r'border-radius:\s*([^;]+)', css_text, re.I)
        if radius_matches:
            specs['corner_radius'] = radius_matches[0].strip()
        gap_matches = re.findall(r'gap:\s*([^;]+)', css_text, re.I)
        if gap_matches:
            specs['item_spacing'] = gap_matches[0].strip()
        else:
            margin_matches = re.findall(r'margin:\s*([^;]+)', css_text, re.I)
            if margin_matches:
                specs['item_spacing'] = margin_matches[0].strip()
        return specs
    
    def extract_links(self):
        links = []
        seen_urls = set()
        anchor_tags = self.soup.find_all('a', href=True)
        for anchor in anchor_tags:
            href = anchor.get('href', '').strip()
            if not href:
                continue
            if href.startswith('javascript:') or href.startswith('#'):
                continue
            try:
                full_url = urljoin(self.base_url, href)
                parsed_url = urlparse(full_url)
                if not parsed_url.netloc:
                    continue
                link_text = anchor.get_text(strip=True)
                if not link_text:
                    link_text = anchor.get('title', '') or anchor.get('alt', '') or href
                title = anchor.get('title', '')
                target = anchor.get('target', '')
                rel = anchor.get('rel', [])
                base_domain = urlparse(self.base_url).netloc
                is_internal = parsed_url.netloc == base_domain or parsed_url.netloc == ''
                link_key = (full_url, link_text[:50])
                if link_key not in seen_urls:
                    seen_urls.add(link_key)
                    links.append({
                        'url': full_url,
                        'text': link_text[:200],
                        'title': title,
                        'target': target,
                        'rel': ' '.join(rel) if isinstance(rel, list) else rel,
                        'is_internal': is_internal
                    })
            except Exception:
                continue
        links.sort(key=lambda x: (not x['is_internal'], x['url']))
        return links
    
    def analyze(self):
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

