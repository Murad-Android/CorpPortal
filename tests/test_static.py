"""
Тесты статических файлов (проверка что локальные ресурсы на месте)
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, 'app', 'static')


def test_tailwind_css_exists():
    """Скомпилированный Tailwind CSS на месте"""
    path = os.path.join(STATIC_DIR, 'css', 'tailwind.min.css')
    assert os.path.exists(path)
    assert os.path.getsize(path) > 10000  # минимум 10KB


def test_fontawesome_css_exists():
    """Font Awesome CSS на месте"""
    path = os.path.join(STATIC_DIR, 'fontawesome', 'css', 'all.min.css')
    assert os.path.exists(path)


def test_fontawesome_webfonts_exist():
    """Font Awesome webfonts на месте"""
    webfonts_dir = os.path.join(STATIC_DIR, 'fontawesome', 'webfonts')
    assert os.path.exists(webfonts_dir)

    required_fonts = [
        'fa-solid-900.woff2',
        'fa-regular-400.woff2',
        'fa-brands-400.woff2',
    ]
    for font in required_fonts:
        assert os.path.exists(os.path.join(
            webfonts_dir, font)), f'{font} missing'


def test_inter_font_exists():
    """Шрифт Inter на месте"""
    fonts_dir = os.path.join(STATIC_DIR, 'fonts')
    assert os.path.exists(os.path.join(fonts_dir, 'inter.css'))
    assert os.path.exists(os.path.join(fonts_dir, 'inter-cyrillic.woff2'))
    assert os.path.exists(os.path.join(fonts_dir, 'inter-latin.woff2'))


def test_no_cdn_references():
    """Шаблоны не содержат CDN-ссылок на шрифты и Tailwind"""
    templates_dir = os.path.join(BASE_DIR, 'app', 'templates')

    cdn_patterns = [
        'cdn.tailwindcss.com',
        'fonts.googleapis.com',
        'cdnjs.cloudflare.com/ajax/libs/font-awesome',
    ]

    for root, dirs, files in os.walk(templates_dir):
        for fname in files:
            if not fname.endswith('.html'):
                continue
            filepath = os.path.join(root, fname)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            for pattern in cdn_patterns:
                assert pattern not in content, \
                    f'CDN reference "{pattern}" found in {filepath}'
