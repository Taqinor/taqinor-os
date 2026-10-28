"""CPDF — libellés des pages C&I (accord, bases du calcul, services),
résolus par ``ci.blocs.libelle`` — JAMAIS ajoutés au catalogue
``i18n_labels.LIBELLES`` (sa table publiée ``libelles_document`` ne bouge pas
selon l'ordre des imports ; le catalogue dépasse 2 000 lignes). Trois langues par clé."""

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
    # CPDF — « جدول الأداء » se lit « tableau de performance » : l'échéancier
    # de PAIEMENT se dit « جدول الدفع ».
    'ci_cpdf_echeancier': {'fr': 'Échéancier de paiement',
                           'en': 'Payment schedule', 'ar': 'جدول الدفع'},
}
