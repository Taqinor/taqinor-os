"""CPDF — libellés des couvertures C&I (cartes « sans / avec batterie »,
lignes consommation / production sans réserve), résolus par
``ci.blocs.libelle`` — JAMAIS ajoutés au catalogue ``i18n_labels.LIBELLES``
(sa table publiée ``libelles_document`` ne bouge pas selon l'ordre des
imports ; le catalogue dépasse 2 000 lignes). Trois langues par clé."""

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
    # R1 (fondateur 28/10/2026) — taille limitée par le toit en pose rasante.
    'ci_h_taille_toit': {
        'fr': 'Taille limitée par le toit', 'en': 'Size limited by the roof',
        'ar': 'الحجم محدود بمساحة السطح'},
    'ci_h_taille_toit_rasante': {
        'fr': '{m2}&#160;m² déclarés → {kwc}&#160;kWc en pose rasante',
        'en': '{m2}&#160;m² declared → {kwc}&#160;kWp in low-tilt layout',
        'ar': '{m2}&#160;م² مصرح بها ← {kwc}&#160;kWp بتركيب منخفض الميل'},
    # CEC15 (affichage) — l'apport, les frais et le retour de l'offre de
    # financement servis par ``economie_ci.financement``.
    'ci_fin_apport': {
        'fr': 'Apport à la signature', 'en': 'Deposit at signature',
        'ar': 'المساهمة عند التوقيع'},
    'ci_fin_frais': {
        'fr': "Frais de l'offre", 'en': 'Offer fees',
        'ar': 'مصاريف العرض'},
    'ci_fin_retour': {
        'fr': "Retour sur l'offre", 'en': 'Payback with the offer',
        'ar': 'مدة الاسترداد مع العرض'},
    # D-CI-BATTERIE-NON-RENTABLE (fondateur 30/10/2026) — option « avec
    # batterie » hors de la règle marginale : montrée, marquée, jamais
    # recommandée. Texte brut (servi aussi à /proposition) : aucune entité.
    'ci_opt_non_rentable': {
        'fr': 'non rentable sur les seuls critères financiers',
        'en': 'not cost-effective on financial criteria alone',
        'ar': 'غير مربح وفق المعايير المالية وحدها'},
    'ci_opt_non_rentable_ligne': {
        'fr': 'Retour estimé {n} ans (remplacement batterie inclus), au-delà de '
              "l'horizon de {h} ans retenu : l'option solaire seule est recommandée.",
        'en': 'Estimated payback {n} years (battery replacement included), beyond '
              'the {h}-year horizon used: the solar-only option is recommended.',
        'ar': 'مدة استرداد تقديرية {n} سنوات (مع احتساب استبدال البطارية)، تتجاوز '
              'أفق {h} سنوات المعتمد: يوصى بخيار الطاقة الشمسية وحدها.'},
}
