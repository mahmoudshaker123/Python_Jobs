from .site_i18n import TRANSLATIONS, get_site_language


def site_ui(request):
    language = get_site_language(request)
    translations = {**TRANSLATIONS['en'], **TRANSLATIONS[language]}
    if language == 'ar':
        translations.update({
            'review_pending_note': 'الآراء النظيفة تظهر مباشرة؛ المحتوى المسيء يُحجز للمراجعة.',
            'review_helpful': 'مفيد',
            'review_inaccurate': 'غير دقيق',
        })
    return {
        'site_language': language,
        'site_direction': 'rtl' if language == 'ar' else 'ltr',
        'tr': translations,
        'language_switch_code': 'en' if language == 'ar' else 'ar',
    }
