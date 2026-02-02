"""
Apple Style - macOS-inspired stylesheet for the application
"""

# Apple-inspired color palette
COLORS = {
    # Backgrounds
    'bg_primary': '#FFFFFF',
    'bg_secondary': '#F5F5F7',
    'bg_tertiary': '#E8E8ED',
    'bg_sidebar': '#F0F0F5',

    # Text
    'text_primary': '#1D1D1F',
    'text_secondary': '#86868B',
    'text_tertiary': '#AEAEB2',

    # Accents
    'accent_blue': '#007AFF',
    'accent_blue_hover': '#0056CC',
    'accent_blue_pressed': '#004499',
    'accent_green': '#34C759',
    'accent_red': '#FF3B30',
    'accent_orange': '#FF9500',

    # Borders
    'border_light': '#D2D2D7',
    'border_medium': '#C7C7CC',

    # Shadows
    'shadow': 'rgba(0, 0, 0, 0.04)',
    'shadow_hover': 'rgba(0, 0, 0, 0.08)',
}

def get_stylesheet():
    """Return the complete Apple-style stylesheet."""
    return f'''
    /* ===== GLOBAL ===== */
    QMainWindow {{
        background-color: {COLORS['bg_secondary']};
    }}

    QWidget {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
        font-size: 13px;
        color: {COLORS['text_primary']};
    }}

    /* ===== LABELS ===== */
    QLabel {{
        color: {COLORS['text_primary']};
        padding: 2px;
    }}

    QLabel[class="secondary"] {{
        color: {COLORS['text_secondary']};
        font-size: 12px;
    }}

    QLabel[class="title"] {{
        font-size: 15px;
        font-weight: 600;
    }}

    /* ===== BUTTONS ===== */
    QPushButton {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 6px;
        padding: 6px 16px;
        font-size: 13px;
        font-weight: 500;
        color: {COLORS['text_primary']};
        min-height: 24px;
    }}

    QPushButton:hover {{
        background-color: {COLORS['bg_tertiary']};
        border-color: {COLORS['border_medium']};
    }}

    QPushButton:pressed {{
        background-color: {COLORS['border_light']};
    }}

    QPushButton:disabled {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_tertiary']};
        border-color: {COLORS['bg_tertiary']};
    }}

    /* Primary Button (accent) */
    QPushButton[class="primary"] {{
        background-color: {COLORS['accent_blue']};
        border: none;
        color: white;
        font-weight: 600;
    }}

    QPushButton[class="primary"]:hover {{
        background-color: {COLORS['accent_blue_hover']};
    }}

    QPushButton[class="primary"]:pressed {{
        background-color: {COLORS['accent_blue_pressed']};
    }}

    QPushButton[class="primary"]:disabled {{
        background-color: {COLORS['border_light']};
        color: {COLORS['text_tertiary']};
    }}

    /* Small button */
    QPushButton[class="small"] {{
        padding: 4px 10px;
        font-size: 12px;
        min-height: 20px;
        border-radius: 5px;
    }}

    /* Icon button */
    QPushButton[class="icon"] {{
        padding: 6px;
        min-width: 28px;
        max-width: 28px;
        min-height: 28px;
        max-height: 28px;
        border-radius: 6px;
    }}

    /* ===== INPUT FIELDS ===== */
    QLineEdit {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 13px;
        selection-background-color: {COLORS['accent_blue']};
    }}

    QLineEdit:focus {{
        border-color: {COLORS['accent_blue']};
        border-width: 2px;
        padding: 5px 9px;
    }}

    QLineEdit:disabled {{
        background-color: {COLORS['bg_secondary']};
        color: {COLORS['text_tertiary']};
    }}

    QLineEdit[readOnly="true"] {{
        background-color: {COLORS['bg_tertiary']};
        color: {COLORS['text_secondary']};
    }}

    /* ===== SPINBOX ===== */
    QSpinBox {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 6px;
        padding: 4px 8px;
        font-size: 13px;
        min-width: 70px;
    }}

    QSpinBox:focus {{
        border-color: {COLORS['accent_blue']};
        border-width: 2px;
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        width: 20px;
        border: none;
        background: transparent;
    }}

    QSpinBox::up-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-bottom: 5px solid {COLORS['text_secondary']};
        width: 0;
        height: 0;
    }}

    QSpinBox::down-arrow {{
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid {COLORS['text_secondary']};
        width: 0;
        height: 0;
    }}

    /* ===== COMBOBOX ===== */
    QComboBox {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 6px;
        padding: 6px 12px;
        padding-right: 30px;
        font-size: 13px;
        min-width: 100px;
    }}

    QComboBox:hover {{
        border-color: {COLORS['border_medium']};
    }}

    QComboBox:focus {{
        border-color: {COLORS['accent_blue']};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {COLORS['text_secondary']};
        width: 0;
        height: 0;
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 8px;
        padding: 4px;
        selection-background-color: {COLORS['accent_blue']};
        selection-color: white;
        outline: none;
    }}

    QComboBox QAbstractItemView::item {{
        padding: 6px 12px;
        border-radius: 4px;
        min-height: 24px;
    }}

    QComboBox QAbstractItemView::item:hover {{
        background-color: {COLORS['bg_tertiary']};
    }}

    /* ===== CHECKBOX ===== */
    QCheckBox {{
        spacing: 8px;
        font-size: 13px;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid {COLORS['border_medium']};
        background-color: {COLORS['bg_primary']};
    }}

    QCheckBox::indicator:hover {{
        border-color: {COLORS['accent_blue']};
    }}

    QCheckBox::indicator:checked {{
        background-color: {COLORS['accent_blue']};
        border-color: {COLORS['accent_blue']};
        image: url(data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIj48cGF0aCBmaWxsPSJ3aGl0ZSIgZD0iTTEwIDNMNC41IDguNSAyIDYiIHN0cm9rZT0id2hpdGUiIHN0cm9rZS13aWR0aD0iMiIgZmlsbD0ibm9uZSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIi8+PC9zdmc+);
    }}

    QCheckBox::indicator:disabled {{
        background-color: {COLORS['bg_tertiary']};
        border-color: {COLORS['border_light']};
    }}

    /* ===== SLIDER ===== */
    QSlider::groove:horizontal {{
        height: 4px;
        background-color: {COLORS['bg_tertiary']};
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        width: 18px;
        height: 18px;
        margin: -7px 0;
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 9px;
    }}

    QSlider::handle:horizontal:hover {{
        border-color: {COLORS['accent_blue']};
        box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.2);
    }}

    QSlider::sub-page:horizontal {{
        background-color: {COLORS['accent_blue']};
        border-radius: 2px;
    }}

    QSlider:disabled {{
        opacity: 0.5;
    }}

    /* ===== GROUP BOX ===== */
    QGroupBox {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 10px;
        margin-top: 8px;
        padding: 16px;
        padding-top: 28px;
        font-weight: 500;
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 16px;
        top: 8px;
        color: {COLORS['text_primary']};
        font-size: 13px;
        font-weight: 600;
    }}

    /* ===== SCROLL AREA ===== */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}

    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    QScrollBar:horizontal {{
        height: 8px;
        background: transparent;
        margin: 0;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {COLORS['border_medium']};
        border-radius: 4px;
        min-width: 30px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {COLORS['text_tertiary']};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}

    QScrollBar:vertical {{
        width: 8px;
        background: transparent;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background-color: {COLORS['border_medium']};
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {COLORS['text_tertiary']};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    /* ===== PROGRESS BAR ===== */
    QProgressBar {{
        background-color: {COLORS['bg_tertiary']};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
    }}

    QProgressBar::chunk {{
        background-color: {COLORS['accent_blue']};
        border-radius: 4px;
    }}

    /* ===== STATUS BAR ===== */
    QStatusBar {{
        background-color: {COLORS['bg_secondary']};
        border-top: 1px solid {COLORS['border_light']};
        padding: 4px 12px;
        font-size: 12px;
        color: {COLORS['text_secondary']};
    }}

    /* ===== FRAME (for cards) ===== */
    QFrame[class="card"] {{
        background-color: {COLORS['bg_primary']};
        border: 1px solid {COLORS['border_light']};
        border-radius: 10px;
    }}

    QFrame[class="card"]:hover {{
        border-color: {COLORS['accent_blue']};
    }}

    /* ===== TOOLTIP ===== */
    QToolTip {{
        background-color: {COLORS['text_primary']};
        color: {COLORS['bg_primary']};
        border: none;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
    }}

    /* ===== DIALOG ===== */
    QDialog {{
        background-color: {COLORS['bg_secondary']};
    }}

    /* ===== MESSAGE BOX ===== */
    QMessageBox {{
        background-color: {COLORS['bg_secondary']};
    }}

    QMessageBox QLabel {{
        font-size: 13px;
        color: {COLORS['text_primary']};
    }}
    '''


def get_video_preview_style():
    """Return stylesheet for video preview area."""
    return f'''
        background-color: #000000;
        border-radius: 8px;
    '''


def get_frame_thumbnail_style(selected=False):
    """Return stylesheet for frame thumbnails."""
    if selected:
        return f'''
            QFrame {{
                background-color: {COLORS['bg_primary']};
                border: 2px solid {COLORS['accent_blue']};
                border-radius: 8px;
            }}
        '''
    return f'''
        QFrame {{
            background-color: {COLORS['bg_primary']};
            border: 1px solid {COLORS['border_light']};
            border-radius: 8px;
        }}
        QFrame:hover {{
            border-color: {COLORS['accent_blue']};
            border-width: 2px;
        }}
    '''
