"""RPDF — libellés du PDF résidentiel (premium, une page, repli legacy).

Module neuf de la session RPDF (27/10/2026) : ``i18n_labels.py`` dépasse
2 000 lignes et ne grossit plus. Même forme que ``i18n_labels.LIBELLES``
(une clé → ses trois langues) ; ``i18n_labels`` fusionne ce dictionnaire
dans son catalogue (une ligne), si bien que ``libelle``/``_L``/
``libelle_cat`` lisent ces clés comme les autres, et le test « chaque clé
porte les trois langues » les couvre aussi.
"""

LIBELLES_RESIDENTIEL = {
    # CE2E7 — salutation sans prénom (nom de bien ou de société).
    'rpdf_bonjour_neutre': {'fr': 'Bonjour,', 'en': 'Hello,', 'ar': 'مرحبًا،'},
    # CE2E5 — « Nos hypothèses » d'un lead sans distributeur, modèle horaire.
    'rpdf_hyp_bareme_national': {'fr': 'Tarif électricité : barème national par tranche',
                                 'en': 'Electricity tariff: national schedule by bracket',
                                 'ar': 'تعريفة الكهرباء: الجدول الوطني حسب الأشطر'},
    # ── Unités de la une-page (legacy_onepage.py) ──────────────────────────
    'rpdf_kwh_an': {'fr': '{n} kWh/an', 'en': '{n} kWh/year', 'ar': '{n} kWh/سنة'},
    'rpdf_mad_an': {'fr': '{n} MAD/an', 'en': '{n} MAD/year', 'ar': '{n} MAD/سنة'},
    'rpdf_mad_par': {'fr': '{n} MAD/{u}', 'en': '{n} MAD/{u}', 'ar': '{n} MAD/{u}'},
    'rpdf_titre_doc': {'fr': 'Devis {marque} N° {ref}', 'en': 'Quote {marque} No. {ref}',
                       'ar': 'عرض سعر {marque} رقم {ref}'},
    # Valeurs FR en entités HTML : octet pour octet le littéral d'avant.
    'rpdf_debit_estime': {'fr': 'D&#233;bit estim&#233;', 'en': 'Estimated flow',
                          'ar': 'التدفق المقدّر'},
    'rpdf_m3_jour': {'fr': '{n} m&#179;/jour', 'en': '{n} m&#179;/day', 'ar': '{n} م&#179;/يوم'},
    'rpdf_fin_remplacement_deux': {
        'fr': (' · remplacement onduleur provisionné en année {an} '
               '({s} MAD option 1, {a} MAD option 2)'),
        'en': (' · inverter replacement provisioned in year {an} '
               '({s} MAD option 1, {a} MAD option 2)'),
        'ar': (' · استبدال العاكس مرصود في السنة {an} '
               '({s} درهم الخيار 1، {a} درهم الخيار 2)')},
    'rpdf_gar_onduleur_opt1': {'fr': 'Onduleur (option 1)', 'en': 'Inverter (option 1)',
                               'ar': 'العاكس (الخيار 1)'},
    'rpdf_gar_onduleur_opt2': {'fr': 'Onduleur (option 2)', 'en': 'Inverter (option 2)',
                               'ar': 'العاكس (الخيار 2)'},
    'rpdf_hyp_provision_options': {
        'fr': ("Provision de remplacement de l'onduleur en année {an} : {s} MAD (option 1) et {a} MAD "
               "(option 2) — le prix de l'onduleur de chaque option, c'est le palier visible sur chaque "
               "courbe de rentabilité."),
        'en': ('Inverter replacement provision in year {an}: {s} MAD (option 1) and {a} MAD (option 2) '
               "— the price of each option's inverter, the step visible on each return curve."),
        'ar': ('مخصص استبدال العاكس في السنة {an}: {s} درهم (الخيار 1) و{a} درهم (الخيار 2) '
               '— ثمن عاكس كل خيار، وهو العتبة الظاهرة على كل منحنى مردودية.')},
    # ── Graphiques et page calepinage (charts.py, render.py) ───────────────
    'rpdf_ch_mois': {
        'fr': 'Jan,Fév,Mar,Avr,Mai,Juin,Juil,Aoû,Sep,Oct,Nov,Déc',
        'en': 'Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec',
        'ar': 'Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec'},
    'rpdf_ch_variation_estimee': {
        'fr': 'variation mensuelle estimée', 'en': 'estimated monthly variation',
        'ar': 'estimated monthly variation'},
    'rpdf_ch_eco_mois': {
        'fr': 'économie du mois, en MAD', 'en': 'monthly saving, in MAD',
        'ar': 'monthly saving, in MAD'},
    'rpdf_ch_prod_titre': {
        'fr': 'Production solaire estimée, mois par mois',
        'en': 'Estimated solar production, month by month',
        'ar': 'Estimated solar production, month by month'},
    'rpdf_ch_couverture': {'fr': 'couverture', 'en': 'coverage', 'ar': 'coverage'},
    'rpdf_ch_sans_batterie': {'fr': 'Sans batterie', 'en': 'Without battery',
                              'ar': 'Without battery'},
    'rpdf_ch_seuil': {'fr': 'seuil de rentabilité', 'en': 'break-even',
                      'ar': 'break-even'},
    'rpdf_ch_rentab_un': {'fr': 'rentabilisé en {a} ans', 'en': 'paid back in {a} years',
                          'ar': 'paid back in {a} years'},
    'rpdf_ch_rentab_deux': {'fr': 'rentabilisés en {a} et {b} ans',
                            'en': 'paid back in {a} and {b} years',
                            'ar': 'paid back in {a} and {b} years'},
    'rpdf_ch_annees': {'fr': 'Années', 'en': 'Years', 'ar': 'Years'},
    'rpdf_cal_kicker': {'fr': 'Pièce technique', 'en': 'Technical document',
                        'ar': 'وثيقة تقنية'},
    'rpdf_cal_titre': {'fr': 'Calepinage', 'en': 'Panel layout', 'ar': 'مخطط توزيع الألواح'},
    'rpdf_cal_intro': {
        'fr': """Implantation des modules relevée sur la toiture, à
    l'échelle portée par la planche. Les cotes sont mesurées sur la géométrie
    de la conception.""",
        'en': 'Module layout surveyed on the roof, at the scale shown on the '
              'drawing. Dimensions are measured on the design geometry.',
        'ar': 'توزيع الألواح كما رُفع على السطح، وفق المقياس المبيّن على المخطط. '
              'القياسات مأخوذة من هندسة التصميم.'},
    'rpdf_cal_note': {
        'fr': """Pièce technique jointe à la proposition. L'implantation
    définitive est confirmée à la visite technique ; seule la liste
    d'équipements du devis fait foi commercialement.""",
        'en': 'Technical document attached to the proposal. The final layout is '
              'confirmed at the technical visit; only the equipment list of '
              'the quote is commercially binding.',
        'ar': 'وثيقة تقنية مرفقة بالعرض. يتم تأكيد التوزيع النهائي خلال الزيارة '
              'التقنية؛ وقائمة التجهيزات في عرض السعر وحدها هي الملزمة تجاريًا.'},
    'rpdf_jours_ouvres': {'fr': 'jours ouvrés', 'en': 'working days',
                          'ar': 'أيام عمل'},
    'rpdf_heures_abr': {'fr': 'h', 'en': 'h', 'ar': 'ساعة'},
}


def accord_annees_ar(texte, n):
    """RPDF (constat RWEB, 27/10) — l'arabe accorde « ans » au nombre :
    « سنوات » de 3 à 10 ans entiers, « سنة » sinon (12,5 → « 12,5 سنة »).
    Même règle que ``anneesAr`` de la page /proposition."""
    try:
        f = float(n)
    except (TypeError, ValueError):
        return texte
    if f.is_integer() and 3 <= f <= 10:
        return texte
    return texte.replace('سنوات', 'سنة')
