"""CPDF — libellés des pages C&I (accord, bases du calcul, services),
enregistrés dans le catalogue ``i18n_labels.LIBELLES`` à l'import (le
catalogue dépasse 2 000 lignes : il ne grossit plus). Trois langues par clé."""
from . import i18n_labels

LIBELLES_CI_PAGES = {
    'ci_bases_calcul': {
        'fr': 'Bases du calcul', 'en': 'Calculation basis',
        'ar': 'أسس الحساب'},
    'ci_pct_par_an': {'fr': '%/an', 'en': '%/year', 'ar': '%/سنة'},
    'ci_bpa_choix': {
        'fr': 'Option retenue', 'en': 'Selected option',
        'ar': 'الخيار المختار'},
    'ci_bpa_option_sans': {
        'fr': 'Sans batterie — {total} MAD TTC',
        'en': 'Without battery — {total} MAD incl. VAT',
        'ar': 'بدون بطارية — {total} درهم شامل الضريبة'},
    'ci_bpa_option_avec': {
        'fr': 'Avec batterie — {total} MAD TTC',
        'en': 'With battery — {total} MAD incl. VAT',
        'ar': 'مع بطارية — {total} درهم شامل الضريبة'},
    'ci_ind_iso_texte_cpdf': {
        'fr': 'Les données de production et de consommation peuvent '
              'alimenter votre <b>revue énergétique</b>.',
        'en': 'Production and consumption data can feed your <b>energy '
              'review</b>.',
        'ar': 'يمكن لمعطيات الإنتاج والاستهلاك أن تغذي <b>مراجعتكم '
              'الطاقية</b>.'},
    'ci_om_designation': {
        'fr': 'Exploitation et maintenance (O&amp;M)',
        'en': 'Operation and maintenance (O&amp;M)',
        'ar': 'التشغيل والصيانة (O&amp;M)'},
    # CPDF — « جدول الأداء » se lit « tableau de performance » : l'échéancier
    # de PAIEMENT se dit « جدول الدفع ».
    'ci_cpdf_echeancier': {'fr': 'Échéancier de paiement',
                           'en': 'Payment schedule', 'ar': 'جدول الدفع'},
}

for _cle, _val in LIBELLES_CI_PAGES.items():
    i18n_labels.LIBELLES.setdefault(_cle, _val)
