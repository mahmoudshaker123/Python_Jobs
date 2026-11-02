from .site_i18n import TRANSLATIONS, get_site_language


def site_ui(request):
    language = get_site_language(request)
    return {
        'site_language': language,
        'site_direction': 'rtl' if language == 'ar' else 'ltr',
        'tr': TRANSLATIONS[language],
        'language_switch_code': 'en' if language == 'ar' else 'ar',
    }
