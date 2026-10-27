"""CPDF — libellés des couvertures C&I (cartes « sans / avec batterie »,
lignes consommation / production sans réserve), enregistrés dans le
catalogue ``i18n_labels.LIBELLES`` à l'import (le catalogue dépasse 2 000
lignes : il ne grossit plus). Trois langues par clé."""
from . import i18n_labels

LIBELLES_CI = {
    'ci_opt_sans_batterie': {
        'fr': 'Sans batterie', 'en': 'Without battery',
        'ar': 'بدون بطارية'},
    'ci_opt_avec_batterie': {
        'fr': 'Avec batterie', 'en': 'With battery', 'ar': 'مع بطارية'},
    'ci_opt_puissance': {
        'fr': 'Puissance', 'en': 'Power', 'ar': 'القدرة'},
    'ci_opt_investissement_ttc': {
        'fr': 'Investissement TTC', 'en': 'Investment incl. VAT',
        'ar': 'الاستثمار شامل الضريبة'},
    'ci_opt_investissement_ht': {
        'fr': 'Investissement HT', 'en': 'Investment excl. VAT',
        'ar': 'الاستثمار دون احتساب الضريبة'},
    'ci_opt_economie_annuelle': {
        'fr': 'Économie annuelle', 'en': 'Annual saving',
        'ar': 'التوفير السنوي'},
    'ci_opt_retour': {
        'fr': 'Retour sur investissement', 'en': 'Payback',
        'ar': 'مدة استرداد الاستثمار'},
    'ci_opt_couverture': {
        'fr': 'Part de votre consommation couverte',
        'en': 'Share of your consumption covered',
        'ar': 'حصة استهلاككم المغطاة'},
    'ci_cpdf_conso': {
        'fr': 'Consommation : {kwh}&#160;kWh/an',
        'en': 'Consumption: {kwh}&#160;kWh/yr',
        'ar': 'الاستهلاك: {kwh}&#160;kWh/سنة'},
    'ci_cpdf_production': {
        'fr': 'Production : {kwh}&#160;kWh/an',
        'en': 'Production: {kwh}&#160;kWh/yr',
        'ar': 'الإنتاج: {kwh}&#160;kWh/سنة'},
    'ci_cpdf_lead_finance': {
        'fr': 'Projection sur {n} ans : flux annuels, délai de retour et TRI '
              'tirés de la même série ; bases du calcul ci-dessous.',
        'en': 'Projection over {n} years: annual cash flows, payback and IRR '
              'drawn from the same series; calculation basis below.',
        'ar': 'إسقاط على مدى {n} سنة: التدفقات السنوية ومدة الاسترداد ومعدل '
              'العائد الداخلي مستخرجة من نفس السلسلة؛ أسس الحساب أدناه.'},
}

for _cle, _val in LIBELLES_CI.items():
    i18n_labels.LIBELLES.setdefault(_cle, _val)
