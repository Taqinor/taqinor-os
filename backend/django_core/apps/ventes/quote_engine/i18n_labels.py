"""NTI18N5 — libellés STRUCTURELS du document client rendu par le moteur
``/proposal`` (règle #4 : ce moteur est le seul chemin PDF devis client, et il
ne fait que RENDRE).

CE QUE CE MODULE CONTIENT — et seulement ça : les mots que le GABARIT écrit
lui-même (en-têtes de colonnes, chaîne des totaux, libellés des conditions de
paiement, « Réf. »). Trois langues : fr / en / ar.

CE QU'IL NE CONTIENT PAS, ET NE CONTIENDRA JAMAIS :
  * les DONNÉES du devis — désignations produit, marques, notes de TVA, textes
    de validité éditables par la société, ligne légale de l'entreprise. Ce sont
    des données réelles saisies par un humain : un moteur de rendu ne les
    traduit pas, il les imprime telles quelles (la traduction du contenu saisi
    est le périmètre de YHARD4). Une « mention légale » appartient donc à
    l'entreprise, pas à ce dictionnaire ;
  * le moindre CHIFFRE, ni le moindre format de montant. Les libellés reçoivent
    les nombres déjà formatés par les utilitaires du moteur ; ce module n'en
    fabrique, n'en arrondit et n'en reformate aucun.

REPLI : toujours le FRANÇAIS, jamais une clé brute (un client ne doit jamais
lire ``total_ttc`` dans son devis). Une langue inconnue, vide ou ``None`` rend
le document français d'aujourd'hui, au caractère près. Une clé ABSENTE du
catalogue lève ``KeyError`` : c'est une faute de frappe du gabarit, qui doit
échouer bruyamment au test plutôt qu'imprimer une chaîne vide ou un nom de
variable sur un document client.

VALEURS PRÊTES POUR LE HTML. Le gabarit les interpole directement dans le HTML
envoyé à WeasyPrint, donc les valeurs FRANÇAISES gardent EXACTEMENT l'écriture
qu'elles avaient dans le gabarit, entités numériques comprises
(``D&#233;signation``) : un devis français reste ainsi octet pour octet celui
d'hier. L'anglais est en ASCII pur et l'arabe en UTF-8 (le gabarit déclare
``<meta charset="UTF-8">`` et le HTML est écrit en UTF-8).
"""
from __future__ import annotations

#: Langues de sortie possibles d'un document — mêmes trois langues que le cadre
#: i18n du produit (``apps.parametres.i18n_resolver.LANGUES_SUPPORTEES``).
LANGUES = ('fr', 'en', 'ar')

#: Repli de tout dernier recours : le comportement historique du moteur.
LANGUE_DE_REPLI = 'fr'

#: Langues écrites de droite à gauche.
LANGUES_RTL = ('ar',)

#: Catalogue par CLÉ (et non par langue) : impossible d'ajouter un libellé
#: arabe sans son équivalent français, donc impossible de construire un repli
#: qui n'existe pas. Un test vérifie que chaque clé porte les trois langues.
LIBELLES = {
    # ── Bloc client ─────────────────────────────────────────────────────────
    'client': {
        'fr': 'Client',
        'en': 'Client',
        'ar': 'العميل',
    },
    # ── En-têtes de colonnes du tableau d'équipements ───────────────────────
    'designation': {
        'fr': 'D&#233;signation',
        'en': 'Description',
        'ar': 'البيان',
    },
    'marque': {
        'fr': 'Marque',
        'en': 'Brand',
        'ar': 'العلامة',
    },
    'qte': {
        'fr': 'Qt&#233;',
        'en': 'Qty',
        'ar': 'الكمية',
    },
    'pu_ht': {
        'fr': 'P.U. HT',
        'en': 'Unit price excl. VAT',
        'ar': 'سعر الوحدة (خ.ض)',
    },
    # Colonne étroite ET lignes de totaux : l'abréviation est la forme lisible
    # dans les deux (« ض.ق.م » = الضريبة على القيمة المضافة).
    'tva': {
        'fr': 'TVA',
        'en': 'VAT',
        'ar': 'ض.ق.م',
    },
    'total_ht': {
        'fr': 'Total HT',
        'en': 'Total excl. VAT',
        'ar': 'المجموع (خ.ض)',
    },
    # ── Chaîne des totaux ───────────────────────────────────────────────────
    'sous_total_ht': {
        'fr': 'Sous-total HT',
        'en': 'Subtotal excl. VAT',
        'ar': 'المجموع الفرعي (خ.ض)',
    },
    'remise': {
        'fr': 'Remise',
        'en': 'Discount',
        'ar': 'الخصم',
    },
    # ARRONDI-100 — la baisse qui ramène le total au palier de 100 MAD.
    'arrondi': {
        'fr': 'Arrondi commercial',
        'en': 'Rounding adjustment',
        'ar': 'تقريب تجاري',
    },
    'total_ttc': {
        'fr': 'Total TTC',
        'en': 'Total incl. VAT',
        'ar': 'المجموع شامل الضريبة',
    },
    # ── Conditions de paiement ──────────────────────────────────────────────
    'conditions_paiement': {
        'fr': 'Conditions de paiement',
        'en': 'Payment terms',
        'ar': 'شروط الدفع',
    },
    'acompte': {
        'fr': 'Acompte',
        'en': 'Down payment',
        'ar': 'الدفعة المقدمة',
    },
    'a_la_reception_materiel': {
        'fr': '&#224; la r&#233;ception du mat&#233;riel',
        'en': 'on delivery of the equipment',
        'ar': 'عند استلام المعدات',
    },
    'apres_mise_en_marche': {
        'fr': 'apr&#232;s mise en marche',
        'en': 'after commissioning',
        'ar': 'بعد التشغيل',
    },
    # ── Résumé du une-page agricole (AGR302) ────────────────────────────────
    # Les gabarits ``debit_a_hmt`` et ``sur_heures_pompage`` reçoivent un
    # nombre DÉJÀ formaté par le moteur (``{hmt}``, ``{heures}``) : ce module
    # n'en fabrique aucun. L'arabe est écrit maintenant et relu après par le
    # fondateur (D-AGR-11, sans bloquer l'envoi).
    'puissance_pompe': {
        'fr': 'Puissance pompe',
        'en': 'Pump power',
        'ar': 'قدرة المضخة',
    },
    'debit_a_hmt': {
        'fr': 'D&#233;bit &#224; {hmt} m',
        'en': 'Flow at {hmt} m',
        'ar': 'الصبيب على ارتفاع {hmt} م',
    },
    'eau_jour': {
        'fr': 'Eau / jour',
        'en': 'Water / day',
        'ar': 'الماء / اليوم',
    },
    'sur_heures_pompage': {
        'fr': 'sur {heures} h de pompage',
        'en': 'over {heures} h of pumping',
        'ar': 'على مدى {heures} ساعات من الضخ',
    },
    'estimation': {
        'fr': 'estimation',
        'en': 'estimate',
        'ar': 'تقدير',
    },
    'hypothese': {
        'fr': 'hypoth&#232;se',
        'en': 'assumption',
        'ar': 'افتراض',
    },
    'champ_pv': {
        'fr': 'Champ PV',
        'en': 'PV array',
        'ar': 'الحقل الشمسي',
    },
    # ── Une-page agricole lu dans ``synthese_agricole`` (AGR313) ────────────
    'besoin_livre_mois_serre': {
        'fr': 'Mois le plus serr&#233; : besoin / livr&#233;',
        'en': 'Tightest month: need / delivered',
        'ar': 'الشهر الأصعب: الحاجة / الماء المضخوخ',
    },
    'bon_pour_accord': {
        'fr': 'Bon pour accord',
        'en': 'Agreed and accepted',
        'ar': 'موافق عليه',
    },
    'bpa_nom': {
        'fr': 'Nom',
        'en': 'Name',
        'ar': 'الاسم',
    },
    'bpa_date': {
        'fr': 'Date',
        'en': 'Date',
        'ar': 'التاريخ',
    },
    'bpa_signature': {
        'fr': 'signature du client',
        'en': "client's signature",
        'ar': 'توقيع الزبون',
    },
    # ── Document agricole de 3 pages (AGR314) ──────────────────────────────
    # Tous les libellés STRUCTURELS du renderer ``quote_engine/agricole``
    # (préfixe ``agr_``). Les gabarits ``{…}`` reçoivent des nombres DÉJÀ
    # formatés ; les DONNÉES saisies ne sont jamais traduites. L'arabe est
    # écrit maintenant et relu par un natif après, sans bloquer l'envoi.
    'agr_kicker_p1': {'fr': 'Proposition · pompage solaire',
                      'en': 'Proposal · solar pumping',
                      'ar': 'عرض · الضخ بالطاقة الشمسية'},
    'agr_titre_p1': {'fr': "L'eau de votre exploitation, pompée par le soleil",
                     'en': "Your farm's water, pumped by the sun",
                     'ar': 'ماء استغلاليتكم، تضخه الشمس'},
    'agr_valable_court': {'fr': "offre valable jusqu'au {date}",
                          'en': 'offer valid until {date}',
                          'ar': 'العرض صالح إلى غاية {date}'},
    'agr_hero_sans_volume_titre': {'fr': 'Pompage solaire',
                                   'en': 'Solar pumping',
                                   'ar': 'الضخ بالطاقة الشمسية'},
    'agr_hero_sans_volume': {
        'fr': "Volume d'eau par jour non calculé : à confirmer par la visite.",
        'en': 'Daily water volume not computed: to be confirmed by the site '
              'visit.',
        'ar': 'حجم الماء اليومي غير محسوب: يؤكد خلال الزيارة.'},
    'agr_hero_m3_jour': {'fr': "m³ d'eau par jour",
                         'en': 'm³ of water per day',
                         'ar': 'م³ من الماء يوميا'},
    'agr_hero_a_hmt': {'fr': 'à {hmt} m de hauteur',
                       'en': 'at {hmt} m of head',
                       'ar': 'على ارتفاع {hmt} م'},
    'agr_debit': {'fr': 'Débit', 'en': 'Flow', 'ar': 'الصبيب'},
    'agr_panneaux_n': {'fr': '{n} panneaux', 'en': '{n} panels',
                       'ar': '{n} لوحا'},
    'agr_surface_irrigable': {'fr': 'Surface irrigable',
                              'en': 'Irrigable area',
                              'ar': 'المساحة القابلة للسقي'},
    'agr_votre_argent': {'fr': 'Votre argent', 'en': 'Your money',
                         'ar': 'أموالكم'},
    'agr_depense_actuelle': {'fr': 'Votre dépense actuelle par an',
                             'en': 'Your current spending per year',
                             'ar': 'مصاريفكم الحالية في السنة'},
    'agr_energie_butane': {'fr': 'butane (bouteilles)',
                           'en': 'butane (bottles)',
                           'ar': 'البوتان (قنينات)'},
    'agr_energie_diesel': {'fr': 'gasoil (groupe électrogène)',
                           'en': 'diesel (generator)',
                           'ar': 'الغازوال (مولد كهربائي)'},
    'agr_energie_electrique': {'fr': 'réseau électrique (facture)',
                               'en': 'grid electricity (bill)',
                               'ar': 'الشبكة الكهربائية (فاتورة)'},
    'agr_energie_aucune': {'fr': 'aucune (nouveau forage)',
                           'en': 'none (new borehole)',
                           'ar': 'لا شيء (ثقب جديد)'},
    'agr_charges_solaires': {'fr': 'Charges du solaire par an (barème)',
                             'en': 'Solar running costs per year (price list)',
                             'ar': 'تكاليف الطاقة الشمسية في السنة (حسب التسعيرة)'},
    'agr_economie_nette_an1': {'fr': 'Économie nette, année 1',
                               'en': 'Net saving, year 1',
                               'ar': 'التوفير الصافي، السنة الأولى'},
    'agr_retour_sans_aide': {'fr': 'Retour sur investissement, sans aide',
                             'en': 'Payback, without subsidy',
                             'ar': 'استرجاع الاستثمار، بدون دعم'},
    'agr_n_ans': {'fr': '{n} ans', 'en': '{n} years', 'ar': '{n} سنوات'},
    'agr_n_an': {'fr': '{n} an', 'en': '{n} year', 'ar': '{n} سنة'},
    'agr_n_mois': {'fr': '{n} mois', 'en': '{n} months', 'ar': '{n} أشهر'},
    'agr_cout_m3': {'fr': 'Coût du m³ : avant / avec le solaire',
                    'en': 'Cost per m³: before / with solar',
                    'ar': 'تكلفة المتر المكعب: قبل / مع الطاقة الشمسية'},
    'agr_remplacement': {'fr': 'Remplacement {composant}, année {annee} (compté)',
                         'en': 'Replacement of the {composant}, year {annee} '
                               '(included)',
                         'ar': 'استبدال {composant}، السنة {annee} (محتسب)'},
    'agr_composant_pompe': {'fr': 'pompe', 'en': 'pump', 'ar': 'المضخة'},
    'agr_composant_variateur': {'fr': 'variateur', 'en': 'drive',
                                'ar': 'المغير'},
    'agr_conso_prix_paye': {'fr': 'Consommation et prix payé : {phrase}.',
                            'en': 'Consumption and price paid: {phrase}.',
                            'ar': 'الاستهلاك والثمن المؤدى: {phrase}.'},
    'agr_indexation': {'fr': 'Indexation du carburant : 0 %.',
                       'en': 'Fuel price indexation: 0%.',
                       'ar': 'مراجعة ثمن الوقود: 0 %.'},
    'agr_fda_non_comptee': {'fr': "L'aide FDA éventuelle n'est pas comptée.",
                            'en': 'Any FDA subsidy is not counted.',
                            'ar': 'الدعم المحتمل من صندوق التنمية الفلاحية غير محتسب.'},
    'agr_provenance_titre': {'fr': "D'où viennent ces chiffres",
                             'en': 'Where these figures come from',
                             'ar': 'مصدر هذه الأرقام'},
    'agr_a_confirmer_visite': {'fr': 'À confirmer par la visite :',
                               'en': 'To be confirmed by the site visit:',
                               'ar': 'يؤكد خلال الزيارة:'},
    'agr_entree_volume_m3_jour': {'fr': "Volume d'eau par jour",
                                  'en': 'Daily water volume',
                                  'ar': 'حجم الماء اليومي'},
    'agr_entree_niveau_statique_m': {'fr': 'Niveau statique',
                                     'en': 'Static water level',
                                     'ar': 'المستوى الساكن'},
    'agr_entree_niveau_dynamique_m': {'fr': 'Niveau dynamique',
                                      'en': 'Dynamic water level',
                                      'ar': 'المستوى الدينامي'},
    'agr_entree_debit_exploitation_m3h': {
        'fr': "Débit d'exploitation du forage",
        'en': 'Borehole operating flow',
        'ar': 'صبيب استغلال الثقب'},
    'agr_entree_profondeur_forage_m': {'fr': 'Profondeur du forage',
                                       'en': 'Borehole depth',
                                       'ar': 'عمق الثقب'},
    'agr_entree_hmt_m': {'fr': 'Hauteur manométrique totale',
                         'en': 'Total dynamic head',
                         'ar': 'الارتفاع المانومتري الكلي'},
    'agr_entree_energie_actuelle': {'fr': 'Énergie actuelle',
                                    'en': 'Current energy',
                                    'ar': 'الطاقة الحالية'},
    'agr_entree_plaque': {'fr': 'Plaque de la pompe',
                          'en': 'Pump nameplate',
                          'ar': 'لوحة المضخة'},
    'agr_entree_localisation': {'fr': 'Localisation', 'en': 'Location',
                                'ar': 'الموقع'},
    'agr_entree_cultures': {'fr': 'Cultures', 'en': 'Crops',
                            'ar': 'الزراعات'},
    'agr_entree_surface_ha': {'fr': 'Surface', 'en': 'Area',
                              'ar': 'المساحة'},
    'agr_kicker_p2': {'fr': 'Votre installation', 'en': 'Your installation',
                      'ar': 'منشأتكم'},
    'agr_titre_p2': {'fr': 'Comment ça marche', 'en': 'How it works',
                     'ar': 'كيف تعمل'},
    'agr_point_fonctionnement': {'fr': 'Point de fonctionnement',
                                 'en': 'Operating point',
                                 'ar': 'نقطة التشغيل'},
    'agr_point_omis': {'fr': 'Point de fonctionnement omis.',
                       'en': 'Operating point omitted.',
                       'ar': 'نقطة التشغيل غير معروضة.'},
    'agr_besoin_livre_titre': {'fr': 'Besoin et eau livrée',
                               'en': 'Need and water delivered',
                               'ar': 'الحاجة والماء المضخوخ'},
    'agr_legende_barres': {
        'fr': "Gris : votre besoin par jour ; bleu : l'eau livrée par jour.",
        'en': 'Grey: your daily need; blue: water delivered per day.',
        'ar': 'الرمادي: حاجتكم اليومية؛ الأزرق: الماء المضخوخ يوميا.'},
    # AMOT44 — légende quand le besoin est le besoin AGRONOMIQUE PLEIN
    # (FAO-56) et non une nature déclarée ; ``{phrase}`` =
    # ``agricole.mentions.PHRASES_PROVENANCE['agronomique']``.
    'agr_base_besoin_agronomique': {
        'fr': "Gris : {phrase} par jour ; bleu : l'eau livrée par jour.",
        'en': 'Grey: {phrase} per day; blue: water delivered per day.',
        'ar': 'الرمادي: {phrase} يوميا؛ الأزرق: الماء المضخوخ يوميا.'},
    'agr_mois_serre': {'fr': 'Mois le plus serré : <b>{mois}</b>.',
                       'en': 'Tightest month: <b>{mois}</b>.',
                       'ar': 'الشهر الأصعب: <b>{mois}</b>.'},
    'agr_besoin_omis_motif': {'fr': 'Besoin et eau livrée par mois : {motif}.',
                              'en': 'Monthly need and water delivered: '
                                    '{motif}.',
                              'ar': 'الحاجة والماء المضخوخ شهريا: {motif}.'},
    'agr_besoin_omis': {
        'fr': 'Besoin et eau livrée par mois : comparaison omise (données '
              'insuffisantes).',
        'en': 'Monthly need and water delivered: comparison omitted '
              '(insufficient data).',
        'ar': 'الحاجة والماء المضخوخ شهريا: المقارنة غير معروضة (معطيات غير كافية).'},
    'agr_pompe_existante': {'fr': 'Votre pompe existante',
                            'en': 'Your existing pump',
                            'ar': 'مضختكم الحالية'},
    'agr_plaque_relevee': {
        'fr': 'Plaque relevée : {plaque}. Le variateur et les panneaux sont '
              'dimensionnés sur cette plaque.',
        'en': 'Nameplate read: {plaque}. The drive and the panels are sized '
              'on this nameplate.',
        'ar': 'اللوحة المسجلة: {plaque}. تم تحديد المغير والألواح على أساس هذه اللوحة.'},
    'agr_plaque_illisible': {'fr': 'non lisible', 'en': 'not legible',
                             'ar': 'غير مقروءة'},
    'agr_plaque_non_relevee': {
        'fr': 'Plaque de la pompe non relevée : compatibilité à vérifier à la '
              'visite.',
        'en': 'Pump nameplate not read: compatibility to be checked at the '
              'site visit.',
        'ar': 'لوحة المضخة غير مسجلة: يتم التحقق من التوافق خلال الزيارة.'},
    'agr_aide_titre': {'fr': "Aide de l'État (FDA) : la règle",
                       'en': 'State aid (FDA): the rule',
                       'ar': 'دعم الدولة (صندوق التنمية الفلاحية): القاعدة'},
    'agr_kicker_p3': {'fr': 'Votre kit de pompage', 'en': 'Your pumping kit',
                      'ar': 'عدة الضخ الخاصة بكم'},
    'agr_titre_p3': {'fr': 'Équipement, prix et garanties',
                     'en': 'Equipment, price and warranties',
                     'ar': 'المعدات والثمن والضمانات'},
    'agr_garanties': {'fr': 'Garanties', 'en': 'Warranties',
                      'ar': 'الضمانات'},
    'agr_garanties_fiches': {
        'fr': 'durées constructeur à lire sur les fiches produits.',
        'en': 'manufacturer periods on the product sheets.',
        'ar': 'مدد الصانع مدونة في بطاقات المنتجات.'},
    'agr_garantie_pompe': {'fr': 'Garantie constructeur de la pompe : {duree}',
                           'en': 'Pump manufacturer warranty: {duree}',
                           'ar': 'ضمان الصانع للمضخة: {duree}'},
    'agr_garantie_variateur': {
        'fr': 'Garantie constructeur du variateur : {duree}',
        'en': 'Drive manufacturer warranty: {duree}',
        'ar': 'ضمان الصانع للمغير: {duree}'},
    'agr_garantie_panneaux': {'fr': 'Garantie produit des panneaux : {duree}',
                              'en': 'Panel product warranty: {duree}',
                              'ar': 'ضمان منتوج الألواح: {duree}'},
    'agr_garantie_performance_panneaux': {
        'fr': 'Garantie de production des panneaux : {duree}',
        'en': 'Panel output warranty: {duree}',
        'ar': 'ضمان إنتاج الألواح: {duree}'},
    'agr_non_inclus': {'fr': 'Non inclus', 'en': 'Not included',
                       'ar': 'غير مشمول'},
    'agr_non_inclus_forage': {'fr': 'le forage', 'en': 'the borehole',
                              'ar': 'الثقب'},
    'agr_non_inclus_genie_civil': {'fr': 'le génie civil',
                                   'en': 'civil works',
                                   'ar': 'الهندسة المدنية'},
    'agr_formalites': {'fr': 'Formalités', 'en': 'Formalities',
                       'ar': 'الإجراءات'},
    'agr_valable': {'fr': "Offre valable jusqu'au <b>{date}</b>",
                    'en': 'Offer valid until <b>{date}</b>',
                    'ar': 'العرض صالح إلى غاية <b>{date}</b>'},
    'agr_options_kit': {
        'fr': '<b>Options du kit</b> (cochez celles que vous retenez ; prix '
              'du supplément, hors total ci-dessus)',
        'en': '<b>Kit options</b> (tick the ones you choose; price of the '
              'extra, not in the total above)',
        'ar': '<b>خيارات العدة</b> (ضعوا علامة على ما تختارونه؛ ثمن الإضافة، خارج المجموع أعلاه)'},
    'agr_creneau_acompte': {'fr': 'Acompte à la commande',
                            'en': 'Down payment on order',
                            'ar': 'دفعة مقدمة عند الطلب'},
    'agr_creneau_materiel': {'fr': 'À la réception du matériel',
                             'en': 'On delivery of the equipment',
                             'ar': 'عند استلام المعدات'},
    'agr_creneau_solde': {'fr': 'Après mise en marche',
                          'en': 'After commissioning',
                          'ar': 'بعد التشغيل'},
    'agr_bpa_client': {'fr': 'Bon pour accord — le client',
                       'en': 'Agreed and accepted — the client',
                       'ar': 'موافق عليه — الزبون'},
    'agr_bpa_pour': {'fr': 'Pour {societe}', 'en': 'For {societe}',
                     'ar': 'عن {societe}'},
    'agr_bpa_cachet': {'fr': 'Cachet et signature',
                       'en': 'Stamp and signature',
                       'ar': 'الختم والتوقيع'},
    'agr_bpa_mention': {
        'fr': 'Nom, date, mention « Bon pour accord » et signature',
        'en': 'Name, date, the words “Agreed and accepted” and signature',
        'ar': 'الاسم والتاريخ وعبارة «موافق عليه» والتوقيع'},
    'agr_scannez': {'fr': 'Scannez pour signer', 'en': 'Scan to sign',
                    'ar': 'امسحوا للتوقيع'},
    # Mois (long : légende du mois le plus serré ; court : axe des barres).
    'agr_mois_1': {'fr': 'janvier', 'en': 'January', 'ar': 'يناير'},
    'agr_mois_2': {'fr': 'février', 'en': 'February', 'ar': 'فبراير'},
    'agr_mois_3': {'fr': 'mars', 'en': 'March', 'ar': 'مارس'},
    'agr_mois_4': {'fr': 'avril', 'en': 'April', 'ar': 'أبريل'},
    'agr_mois_5': {'fr': 'mai', 'en': 'May', 'ar': 'ماي'},
    'agr_mois_6': {'fr': 'juin', 'en': 'June', 'ar': 'يونيو'},
    'agr_mois_7': {'fr': 'juillet', 'en': 'July', 'ar': 'يوليوز'},
    'agr_mois_8': {'fr': 'août', 'en': 'August', 'ar': 'غشت'},
    'agr_mois_9': {'fr': 'septembre', 'en': 'September', 'ar': 'شتنبر'},
    'agr_mois_10': {'fr': 'octobre', 'en': 'October', 'ar': 'أكتوبر'},
    'agr_mois_11': {'fr': 'novembre', 'en': 'November', 'ar': 'نونبر'},
    'agr_mois_12': {'fr': 'décembre', 'en': 'December', 'ar': 'دجنبر'},
    'agr_moisc_1': {'fr': 'Jan', 'en': 'Jan', 'ar': 'ينا'},
    'agr_moisc_2': {'fr': 'Fév', 'en': 'Feb', 'ar': 'فبر'},
    'agr_moisc_3': {'fr': 'Mar', 'en': 'Mar', 'ar': 'مار'},
    'agr_moisc_4': {'fr': 'Avr', 'en': 'Apr', 'ar': 'أبر'},
    'agr_moisc_5': {'fr': 'Mai', 'en': 'May', 'ar': 'ماي'},
    'agr_moisc_6': {'fr': 'Juin', 'en': 'Jun', 'ar': 'يون'},
    'agr_moisc_7': {'fr': 'Juil', 'en': 'Jul', 'ar': 'يول'},
    'agr_moisc_8': {'fr': 'Août', 'en': 'Aug', 'ar': 'غشت'},
    'agr_moisc_9': {'fr': 'Sep', 'en': 'Sep', 'ar': 'شتن'},
    'agr_moisc_10': {'fr': 'Oct', 'en': 'Oct', 'ar': 'أكت'},
    'agr_moisc_11': {'fr': 'Nov', 'en': 'Nov', 'ar': 'نون'},
    'agr_moisc_12': {'fr': 'Déc', 'en': 'Dec', 'ar': 'دجن'},
    # Schéma et courbe (``agricole/schema.py`` : étiquettes d'un mot).
    'agr_schema_forage': {'fr': 'Forage', 'en': 'Borehole', 'ar': 'البئر'},
    'agr_schema_pompe': {'fr': 'Pompe', 'en': 'Pump', 'ar': 'المضخة'},
    'agr_schema_variateur': {'fr': 'Variateur', 'en': 'Drive',
                             'ar': 'المغير'},
    'agr_schema_panneaux': {'fr': 'Panneaux', 'en': 'Panels',
                            'ar': 'الألواح'},
    'agr_schema_bassin': {'fr': 'Bassin', 'en': 'Tank', 'ar': 'الحوض'},
    'agr_schema_irrigation': {'fr': 'Irrigation', 'en': 'Irrigation',
                              'ar': 'السقي'},
    'agr_schema_profondeur': {'fr': 'Profondeur', 'en': 'Depth',
                              'ar': 'العمق'},
    'agr_schema_niveau': {'fr': 'Niveau', 'en': 'Level', 'ar': 'المستوى'},
    'agr_schema_distance': {'fr': 'Distance', 'en': 'Distance',
                            'ar': 'المسافة'},
    'agr_schema_hmt': {'fr': 'HMT', 'en': 'Head', 'ar': 'الارتفاع'},
    'agr_schema_debit': {'fr': 'Débit', 'en': 'Flow', 'ar': 'الصبيب'},
    # Annexe « Note de calcul du kit de pompage » (AGR319, dossier FDA).
    'agr_annexe_kicker': {'fr': 'Annexe · dossier FDA',
                          'en': 'Appendix · FDA file',
                          'ar': 'ملحق · ملف صندوق التنمية الفلاحية'},
    'agr_annexe_titre': {'fr': 'Note de calcul du kit de pompage',
                         'en': 'Pumping kit design note',
                         'ar': 'مذكرة حساب عدة الضخ'},
    'agr_annexe_equipement': {'fr': 'Équipement dimensionné',
                              'en': 'Sized equipment',
                              'ar': 'المعدات المحددة'},
    'agr_annexe_champ': {'fr': 'Champ photovoltaïque : {kwc} kWc, {n} panneaux',
                         'en': 'PV array: {kwc} kWp, {n} panels',
                         'ar': 'الحقل الشمسي: {kwc} كيلوواط ذروة، {n} لوحا'},
    'agr_annexe_garantie': {'fr': 'garantie {duree}', 'en': 'warranty {duree}',
                            'ar': 'ضمان {duree}'},
    'agr_annexe_hmt': {'fr': 'Hauteur manométrique totale retenue : {hmt} m',
                       'en': 'Total dynamic head used: {hmt} m',
                       'ar': 'الارتفاع المانومتري الكلي المعتمد: {hmt} م'},
    'agr_annexe_provenance': {'fr': 'Provenance : {phrase}',
                              'en': 'Source: {phrase}',
                              'ar': 'المصدر: {phrase}'},
    'agr_comp_niveau_dynamique_m': {'fr': 'Niveau dynamique',
                                    'en': 'Dynamic water level',
                                    'ar': 'المستوى الدينامي'},
    'agr_comp_denivele_m': {'fr': 'Dénivelé', 'en': 'Elevation difference',
                            'ar': 'فرق الارتفاع'},
    'agr_comp_pertes_lineaires_m': {'fr': 'Pertes linéaires',
                                    'en': 'Pipe friction losses',
                                    'ar': 'الضياع الخطي'},
    'agr_comp_pertes_singulieres_m': {'fr': 'Pertes singulières',
                                      'en': 'Fitting losses',
                                      'ar': 'الضياع الموضعي'},
    'agr_comp_pression_service_m': {'fr': 'Pression de service',
                                    'en': 'Service pressure',
                                    'ar': 'ضغط الخدمة'},
    'agr_annexe_debit_conception': {
        'fr': 'Débit de conception : {q} m³/h (mois critique : {mois})',
        'en': 'Design flow: {q} m³/h (critical month: {mois})',
        'ar': 'صبيب التصميم: {q} م³/س (الشهر الحرج: {mois})'},
    'agr_annexe_m3_mois': {
        'fr': 'Eau livrée par jour, mois par mois (m³/jour)',
        'en': 'Water delivered per day, month by month (m³/day)',
        'ar': 'الماء المضخوخ يوميا، شهرا بشهر (م³/يوم)'},
    'agr_annexe_hypotheses': {'fr': 'Hypothèses de calcul et leurs sources',
                              'en': 'Calculation assumptions and their sources',
                              'ar': 'فرضيات الحساب ومصادرها'},
    'agr_annexe_est': {'fr': 'EST.', 'en': 'EST.', 'ar': 'تقدير'},
    'agr_annexe_fiches': {'fr': 'Fiches produits', 'en': 'Product sheets',
                          'ar': 'بطاقات المنتجات'},
    'agr_annexe_references': {'fr': 'Références de la société',
                              'en': 'Company references',
                              'ar': 'مراجع الشركة'},
    'agr_annexe_aucune_reference': {
        'fr': 'Aucune référence de pompage à ce jour.',
        'en': 'No pumping reference to date.',
        'ar': 'لا توجد مراجع للضخ إلى حد الآن.'},
    'agr_annexe_omis': {'fr': 'Non renseigné à ce jour.',
                        'en': 'Not provided to date.',
                        'ar': 'غير مدخل إلى حد الآن.'},
    # ── Documents commercial et industriel (CIQ333, CIQ345) ────────────────
    # Libellés STRUCTURELS des pages premium C&I et des blocs partagés
    # (``ci/blocs.py``, ``ci/couverture.py``, ``commercial/equip.py``) —
    # préfixe ``ci_``. Le français est le littéral historique du gabarit
    # (un devis français reste octet pour octet celui d'hier : le gabarit
    # passe son littéral à ``theme.libelle_doc``). Les gabarits ``{…}``
    # reçoivent des valeurs DÉJÀ formatées. L'arabe est écrit maintenant et
    # relu ensuite par un natif (tâche manuelle).
    'ci_ref_devis': {'fr': 'Réf. devis', 'en': 'Quote ref.',
                     'ar': 'مرجع العرض'},
    'ci_valable_jusqu': {'fr': 'Valable jusqu&#8217;au {date}',
                         'en': 'Valid until {date}',
                         'ar': 'صالح إلى غاية {date}'},
    'ci_kicker_commercial': {
        'fr': 'Proposition — Autoconsommation solaire commerciale',
        'en': 'Proposal — Commercial solar self-consumption',
        'ar': 'عرض — الاستهلاك الذاتي للطاقة الشمسية للمحلات التجارية'},
    'ci_puissance_crete': {'fr': 'Puissance crête', 'en': 'Peak power',
                           'ar': 'القدرة القصوى'},
    'ci_production_annuelle': {'fr': 'Production annuelle',
                               'en': 'Annual production',
                               'ar': 'الإنتاج السنوي'},
    'ci_unite_kwh_an': {'fr': '&nbsp;kWh/an', 'en': '&nbsp;kWh/yr',
                        'ar': '&nbsp;kWh/سنة'},
    'ci_autoconsommation': {'fr': 'Autoconsommation',
                            'en': 'Self-consumption',
                            'ar': 'الاستهلاك الذاتي'},
    'ci_couverture_conso': {'fr': 'Couverture conso',
                            'en': 'Consumption coverage',
                            'ar': 'تغطية الاستهلاك'},
    'ci_note_autoconso_commercial': {
        'fr': "L'installation vise l'<b>autoconsommation</b> : la valeur "
              "porte d'abord sur la consommation de <b>journée</b> de votre "
              "établissement.",
        'en': 'The installation targets <b>self-consumption</b>: its value '
              "lies first in your establishment's <b>daytime</b> "
              'consumption.',
        'ar': 'تستهدف المنشأة <b>الاستهلاك الذاتي</b>: تكمن قيمتها أولا في '
              'استهلاك مؤسستكم خلال <b>النهار</b>.'},
    'ci_economies_estimees': {'fr': 'Économies estimées / an',
                              'en': 'Estimated savings / yr',
                              'ar': 'الوفورات المقدرة / سنة'},
    'ci_retour_estime': {'fr': 'Retour estimé', 'en': 'Estimated payback',
                         'ar': 'مدة الاسترداد المقدرة'},
    'ci_unite_ans': {'fr': '&nbsp;ans', 'en': '&nbsp;years',
                     'ar': '&nbsp;سنوات'},
    'ci_ht': {'fr': 'HT', 'en': 'excl. VAT', 'ar': 'دون احتساب الضريبة'},
    'ci_ttc': {'fr': 'TTC', 'en': 'incl. VAT', 'ar': 'شامل الضريبة'},
    'ci_a_confirmer': {'fr': 'À confirmer : ', 'en': 'To be confirmed: ',
                       'ar': 'يجب تأكيده: '},
    'ci_confirmer_tension': {
        'fr': 'Tension de raccordement (BT ou MT), à relever à la visite',
        'en': 'Connection voltage (LV or MV), to be checked at the visit',
        'ar': 'جهد الربط (منخفض أو متوسط)، يُعاين أثناء الزيارة'},
    'ci_confirmer_puissance_souscrite_kva': {
        'fr': 'Puissance souscrite, à relever sur la facture ou à la visite',
        'en': 'Subscribed power, to be read on the bill or at the visit',
        'ar': 'القدرة المكتتبة، تُقرأ في الفاتورة أو أثناء الزيارة'},
    'ci_confirmer_toit': {
        'fr': 'Type et charge admissible de la toiture, à la visite',
        'en': 'Roof type and permissible load, at the visit',
        'ar': 'نوع السقف والحمولة المسموح بها، أثناء الزيارة'},
    'ci_confirmer_etude_ci': {
        'fr': 'étude détaillée de votre site à finaliser : chiffres '
              'préliminaires',
        'en': 'detailed study of your site to be finalised: preliminary '
              'figures',
        'ar': 'الدراسة المفصلة لموقعكم قيد الإنجاز: أرقام أولية'},
    'ci_confirmer_visite': {
        'fr': 'Relevé du site à la visite technique',
        'en': 'Site survey at the technical visit',
        'ar': 'معاينة الموقع أثناء الزيارة التقنية'},
    'ci_methode_horaire_declare': {
        'fr': 'Taux calculés heure par heure sur vos horaires déclarés.',
        'en': 'Rates calculated hour by hour on your declared schedule.',
        'ar': 'نسب محسوبة ساعة بساعة على أساس أوقاتكم المصرح بها.'},
    'ci_methode_horaire_mesure': {
        'fr': 'Taux calculés heure par heure sur votre courbe de charge '
              'mesurée.',
        'en': 'Rates calculated hour by hour on your measured load curve.',
        'ar': 'نسب محسوبة ساعة بساعة على أساس منحنى الحمل المقاس.'},
    'ci_methode_registres_mt': {
        'fr': 'Taux calculés sur vos registres de compteur MT.',
        'en': 'Rates calculated on your MV meter registers.',
        'ar': 'نسب محسوبة على أساس سجلات عداد الجهد المتوسط.'},
    'ci_methode_archetype_estimation': {
        'fr': 'Taux calculés sur un profil type de votre activité — '
              'estimation.',
        'en': 'Rates calculated on a typical profile of your activity — '
              'estimate.',
        'ar': 'نسب محسوبة على أساس نموذج نمطي لنشاطكم — تقدير.'},
    'ci_methode_estimation': {'fr': 'Taux calculés par estimation.',
                              'en': 'Rates calculated by estimate.',
                              'ar': 'نسب محسوبة بالتقدير.'},
    'ci_non_chiffre_mt': {
        'fr': 'Dossier raccordé en MOYENNE TENSION : les économies et le '
              'retour sur investissement ne sont pas chiffrés au barème '
              'basse tension. Communiquez-nous {motif} et nous les calculons '
              'sur le barème MT.',
        'en': 'Site connected at MEDIUM VOLTAGE: savings and payback are not '
              'calculated on the low-voltage tariff. Send us {motif} and we '
              'calculate them on the MV tariff.',
        'ar': 'موقع مربوط بالجهد المتوسط: لا تُحسب الوفورات ومدة الاسترداد '
              'بتعريفة الجهد المنخفض. أرسلوا إلينا {motif} وسنحسبها بتعريفة '
              'الجهد المتوسط.'},
    'ci_non_chiffre': {
        'fr': 'Économies et retour sur investissement non chiffrés à ce '
              'stade : communiquez-nous {motif}.',
        'en': 'Savings and payback not calculated at this stage: send us '
              '{motif}.',
        'ar': 'لم تُحسب الوفورات ومدة الاسترداد في هذه المرحلة: أرسلوا '
              'إلينا {motif}.'},
    'ci_motif_argent_bt': {'fr': 'vos 12 dernières factures',
                           'en': 'your last 12 bills',
                           'ar': 'فواتيركم الاثنتي عشرة الأخيرة'},
    'ci_motif_argent_mt': {
        'fr': 'vos 12 dernières factures MT : prix des trois postes, prime '
              'fixe, puissance souscrite',
        'en': 'your last 12 MV bills: prices of the three time bands, fixed '
              'charge, subscribed power',
        'ar': 'فواتيركم الاثنتي عشرة الأخيرة للجهد المتوسط: أسعار الفترات '
              'الثلاث، الإتاوة الثابتة، القدرة المكتتبة'},
    'ci_invest_ht': {'fr': 'Investissement HT (clé en main)',
                     'en': 'Investment excl. VAT (turnkey)',
                     'ar': 'الاستثمار دون احتساب الضريبة (تسليم مفتاح)'},
    'ci_invest': {'fr': 'Investissement (clé en main)',
                  'en': 'Investment (turnkey)',
                  'ar': 'الاستثمار (تسليم مفتاح)'},
    'ci_invest_ttc': {'fr': 'Investissement (TTC, clé en main)',
                      'en': 'Investment (incl. VAT, turnkey)',
                      'ar': 'الاستثمار (شامل الضريبة، تسليم مفتاح)'},
    'ci_soit': {'fr': 'soit', 'en': 'i.e.', 'ar': 'أي'},
    'ci_note_tva_recuperable': {
        'fr': 'TVA récupérable selon votre régime fiscal — à confirmer avec '
              'votre comptable.',
        'en': 'VAT recoverable depending on your tax regime — to be '
              'confirmed with your accountant.',
        'ar': 'الضريبة على القيمة المضافة قابلة للاسترجاع حسب نظامكم '
              'الضريبي — يُؤكد مع محاسبكم.'},
    'ci_raison_sociale': {'fr': 'Raison sociale', 'en': 'Company name',
                          'ar': 'الاسم التجاري'},
    'ci_siege': {'fr': 'Siège', 'en': 'Head office',
                 'ar': 'المقر الاجتماعي'},
    'ci_a_l_attention': {'fr': "À l'attention de", 'en': 'For the attention of',
                         'ar': 'لعناية'},
    'ci_a_l_attention_fonction': {
        'fr': "À l'attention de la fonction", 'en': 'For the attention of',
        'ar': 'لعناية المسؤول عن'},
    'ci_votre_installation': {'fr': 'Votre installation',
                              'en': 'Your installation', 'ar': 'منشأتكم'},
    'ci_equipements_investissement': {
        'fr': 'Équipements &amp; investissement',
        'en': 'Equipment &amp; investment',
        'ar': 'المعدات والاستثمار'},
    'ci_tva_pct': {'fr': 'TVA %', 'en': 'VAT %', 'ar': 'ض.ق.م %'},
    'ci_note': {'fr': 'Note', 'en': 'Note', 'ar': 'ملاحظة'},
    'ci_options_proposees': {
        'fr': 'Options propos&eacute;es (non incluses dans le total)',
        'en': 'Proposed options (not included in the total)',
        'ar': 'خيارات مقترحة (غير مدرجة في المجموع)'},
    'ci_surplus_injecte': {'fr': 'surplus injecté', 'en': 'surplus fed in',
                           'ar': 'الفائض المحقون في الشبكة'},
    'ci_mad_an': {'fr': 'MAD/an', 'en': 'MAD/yr', 'ar': 'درهم/سنة'},
    'ci_kicker_etapes': {'fr': 'Votre projet, étape par étape',
                         'en': 'Your project, step by step',
                         'ar': 'مشروعكم، خطوة بخطوة'},
    'ci_comment_nous_procedons': {'fr': 'Comment nous procédons',
                                  'en': 'How we proceed',
                                  'ar': 'كيف نعمل'},
    'ci_etape_etude_t': {'fr': 'Étude &amp; validation',
                         'en': 'Study &amp; validation',
                         'ar': 'الدراسة والمصادقة'},
    'ci_etape_etude_s': {
        'fr': 'Dimensionnement, visite technique et validation du projet.',
        'en': 'Sizing, technical visit and project validation.',
        'ar': 'التحجيم والزيارة التقنية والمصادقة على المشروع.'},
    'ci_etape_installation_t': {'fr': 'Installation', 'en': 'Installation',
                                'ar': 'التركيب'},
    # AMOT83 — « en coordination avec votre activité » (jamais une promesse
    # de continuité que le chantier ne tient pas toujours).
    'ci_etape_installation_s': {
        'fr': 'Pose des équipements par nos équipes, en coordination avec '
              'votre activité.',
        'en': 'Equipment installed by our teams, in coordination with your '
              'business.',
        'ar': 'تركيب المعدات من طرف فرقنا بتنسيق مع نشاطكم.'},
    'ci_etape_mes_t': {'fr': 'Mise en service', 'en': 'Commissioning',
                       'ar': 'التشغيل'},
    'ci_etape_mes_s': {
        'fr': 'Raccordement, tests et réception — votre production démarre.',
        'en': 'Connection, tests and acceptance — your production starts.',
        'ar': 'الربط والاختبارات والتسلم — يبدأ إنتاجكم.'},
    'ci_garanties': {'fr': 'Garanties', 'en': 'Warranties',
                     'ar': 'الضمانات'},
    'ci_garantie_installation': {'fr': 'Installation', 'en': 'Installation',
                                 'ar': 'التركيب'},
    'ci_garantie_onduleur': {'fr': 'Onduleur', 'en': 'Inverter',
                             'ar': 'العاكس'},
    'ci_garantie_panneaux': {'fr': 'Panneaux', 'en': 'Panels',
                             'ar': 'الألواح'},
    'ci_garantie_performance': {'fr': 'Performance', 'en': 'Performance',
                                'ar': 'المردودية'},
    'ci_garantie_batterie': {'fr': 'Batterie', 'en': 'Battery',
                             'ar': 'البطارية'},
    'ci_ans': {'fr': 'ans', 'en': 'years', 'ar': 'سنوات'},
    'ci_legende_garanties': {
        'fr': "Durées : garanties du fabricant (fiches produit) ; pose : "
              "engagement de l'installateur.",
        'en': "Durations: manufacturer warranties (product sheets); "
              "installation: the installer's commitment.",
        'ar': 'المدد: ضمانات الصانع (بطاقات المنتجات)؛ التركيب: التزام '
              'المركِّب.'},
    'ci_echeancier': {'fr': 'Échéancier de paiement',
                      'en': 'Payment schedule', 'ar': 'جدول الأداء'},
    'ci_jalon_commande': {'fr': 'À la commande', 'en': 'On order',
                          'ar': 'عند الطلب'},
    'ci_jalon_livraison': {'fr': 'À la livraison', 'en': 'On delivery',
                           'ar': 'عند التسليم'},
    'ci_jalon_mise_en_service': {'fr': 'À la mise en service',
                                 'en': 'On commissioning',
                                 'ar': 'عند التشغيل'},
    'ci_jalon_reception_definitive': {'fr': 'À la réception définitive',
                                      'en': 'On final acceptance',
                                      'ar': 'عند التسلم النهائي'},
    'ci_services': {'fr': 'Services', 'en': 'Services', 'ar': 'الخدمات'},
    'ci_maintenance': {'fr': 'Maintenance (O&amp;M)',
                       'en': 'Maintenance (O&amp;M)',
                       'ar': 'الصيانة (التشغيل والصيانة)'},
    'ci_prix_a_renseigner': {'fr': 'prix à renseigner',
                             'en': 'price to be set',
                             'ar': 'السعر في انتظار التحديد'},
    'ci_propose_non_inclus': {'fr': ' (proposé, non inclus dans le total)',
                              'en': ' (proposed, not included in the total)',
                              'ar': ' (مقترح، غير مدرج في المجموع)'},
    'ci_suivi_production': {'fr': 'Suivi de production',
                            'en': 'Production monitoring',
                            'ar': 'تتبع الإنتاج'},
    # AMOT83 (D-ACI-11=a, D-ACI-12=a) — suivi nommé sans délai inventé ;
    # dossier 82-21 monté par la société émettrice.
    'ci_suivi_production_inclus': {'fr': 'Suivi de production inclus',
                                   'en': 'Production monitoring included',
                                   'ar': 'تتبع الإنتاج مشمول'},
    'ci_dossier_raccordement': {
        'fr': 'Raccordement et autorisations du site&#160;: dossier monté et '
              'suivi par {societe}',
        'en': 'Site grid connection and permits: file prepared and followed '
              'up by {societe}',
        'ar': 'الربط بالشبكة وتراخيص الموقع: ملف تعدّه وتتابعه {societe}'},
    'ci_intervention_sous': {'fr': 'intervention sous {heures}&#160;h',
                             'en': 'intervention within {heures}&#160;h',
                             'ar': 'التدخل في غضون {heures}&#160;ساعة'},
    'ci_offre_financement': {'fr': 'Offre de financement',
                             'en': 'Financing offer', 'ar': 'عرض التمويل'},
    'ci_echeance_mensuelle': {'fr': 'Échéance mensuelle',
                              'en': 'Monthly instalment',
                              'ar': 'القسط الشهري'},
    'ci_sur_mois': {'fr': 'sur {mois} mois', 'en': 'over {mois} months',
                    'ar': 'على مدى {mois} شهرا'},
    'ci_economie_mensuelle': {
        'fr': 'Économie mensuelle moyenne estimée',
        'en': 'Estimated average monthly saving',
        'ar': 'متوسط الوفر الشهري المقدر'},
    'ci_ecart_mensuel': {'fr': 'Écart mensuel', 'en': 'Monthly difference',
                         'ar': 'الفارق الشهري'},
    'ci_source': {'fr': 'Source', 'en': 'Source', 'ar': 'المصدر'},
    'ci_cgv_titre': {'fr': 'Conditions générales du devis',
                     'en': 'General terms of the quote',
                     'ar': 'الشروط العامة للعرض'},
    # AMOT36 / APDF13 — puces CGV tronquées : la suite est DÉCLARÉE.
    'ci_cgv_suite': {'fr': 'Suite des conditions : proposition en ligne',
                     'en': 'Terms continued in the online proposal',
                     'ar': 'تتمة الشروط في العرض عبر الإنترنت'},
    'ci_pour_la_societe': {'fr': 'pour la société', 'en': 'for the company',
                           'ar': 'عن الشركة'},
    'ci_signataire': {'fr': 'Nom et qualité du signataire',
                      'en': "Signatory's name and position",
                      'ar': 'اسم الموقع وصفته'},
    'ci_signature': {'fr': 'Signature', 'en': 'Signature', 'ar': 'التوقيع'},
    'ci_cachet': {'fr': 'Cachet de la société', 'en': 'Company stamp',
                  'ar': 'ختم الشركة'},
    'ci_bpa_mention': {
        'fr': 'Lu et approuvé — Signature précédée de « Bon pour accord »',
        'en': 'Read and approved — signature preceded by « Agreed and '
              'accepted »',
        'ar': 'قرئ وصودق عليه — التوقيع مسبوق بعبارة « موافق عليه »'},
    'ci_pour': {'fr': 'Pour {marque}', 'en': 'For {marque}',
                'ar': 'عن {marque}'},
    'ci_le_date': {'fr': 'Le {date}', 'en': 'On {date}', 'ar': 'بتاريخ {date}'},
    'ci_mad_mois': {'fr': 'MAD/mois', 'en': 'MAD/month', 'ar': 'درهم/شهر'},
    # ── Document industriel (CIQ341, CIQ345) — préfixe ``ci_ind_`` ─────────
    'ci_ind_kicker': {
        'fr': 'Proposition — Autoconsommation solaire industrielle',
        'en': 'Proposal — Industrial solar self-consumption',
        'ar': 'عرض — الاستهلاك الذاتي للطاقة الشمسية الصناعية'},
    'ci_ind_titre': {'fr': "Réduire votre coût de l'énergie",
                     'en': 'Reduce your energy cost',
                     'ar': 'خفض تكلفة الطاقة لديكم'},
    'ci_ind_sous_titre': {
        'fr': 'Analyse de rentabilité (CFO) — baseline, cashflow et payback.',
        'en': 'Profitability analysis (CFO) — baseline, cash flow and '
              'payback.',
        'ar': 'تحليل المردودية (المدير المالي) — الاستهلاك المرجعي والتدفق '
              'النقدي ومدة الاسترداد.'},
    'ci_ind_tag': {'fr': 'Industrielle', 'en': 'Industrial',
                   'ar': 'صناعية'},
    'ci_ind_synthese': {'fr': 'Synthèse', 'en': 'Summary', 'ar': 'الخلاصة'},
    'ci_ind_investissement': {'fr': 'Investissement', 'en': 'Investment',
                              'ar': 'الاستثمار'},
    'ci_ind_economie_an1': {'fr': "Économie de l'année 1",
                            'en': 'Year-1 saving',
                            'ar': 'وفر السنة الأولى'},
    'ci_ind_tri_sur': {'fr': 'TRI sur {n} ans', 'en': 'IRR over {n} years',
                       'ar': 'معدل العائد الداخلي على {n} سنة'},
    'ci_ind_van': {'fr': 'VAN au taux déclaré de {taux} %',
                   'en': 'NPV at the declared rate of {taux} %',
                   'ar': 'القيمة الحالية الصافية بالمعدل المصرح به {taux} %'},
    'ci_ind_financement': {'fr': 'Financement', 'en': 'Financing',
                           'ar': 'التمويل'},
    'ci_ind_rentabilite': {'fr': 'Rentabilité', 'en': 'Profitability',
                           'ar': 'المردودية'},
    'ci_ind_statut': {'fr': "Statut de l'étude", 'en': 'Study status',
                      'ar': 'وضعية الدراسة'},
    'ci_ind_offre_ferme': {'fr': 'offre ferme', 'en': 'firm offer',
                           'ar': 'عرض نهائي'},
    'ci_ind_baseline': {'fr': 'Baseline énergétique',
                        'en': 'Energy baseline',
                        'ar': 'الاستهلاك الطاقي المرجعي'},
    'ci_ind_baseline_factures': {'fr': '12 factures', 'en': '12 bills',
                                 'ar': '12 فاتورة'},
    'ci_ind_baseline_interpoles': {
        'fr': '{n} factures, mois interpolés — estimation',
        'en': '{n} bills, interpolated months — estimate',
        'ar': '{n} فواتير، أشهر مستكملة بالاستيفاء — تقدير'},
    'ci_ind_baseline_interpoles_sans_n': {
        'fr': 'mois interpolés — estimation',
        'en': 'interpolated months — estimate',
        'ar': 'أشهر مستكملة بالاستيفاء — تقدير'},
    'ci_ind_baseline_kwh': {'fr': 'kWh déclarés', 'en': 'declared kWh',
                            'ar': 'كيلوواط ساعة مصرح بها'},
    'ci_ind_facture_actuelle': {'fr': 'Facture électrique actuelle',
                                'en': 'Current electricity bill',
                                'ar': 'فاتورة الكهرباء الحالية'},
    'ci_ind_facture_estimee': {'fr': 'Facture électrique estimée',
                               'en': 'Estimated electricity bill',
                               'ar': 'فاتورة الكهرباء المقدرة'},
    'ci_ind_facture_non_communiquee': {
        'fr': 'Facture électrique actuelle non communiquée — transmettez 12 '
              'mois de factures et la baseline se chiffre.',
        'en': 'Current electricity bill not provided — send 12 months of '
              'bills and the baseline is calculated.',
        'ar': 'فاتورة الكهرباء الحالية غير مقدمة — أرسلوا فواتير 12 شهرا '
              'ليُحسب الاستهلاك المرجعي.'},
    'ci_ind_conso': {'fr': 'Consommation ≈ {kwh} kWh/an',
                     'en': 'Consumption ≈ {kwh} kWh/yr',
                     'ar': 'الاستهلاك ≈ {kwh} kWh/سنة'},
    'ci_ind_conso_a_confirmer': {
        'fr': 'Consommation à confirmer (facture 12 mois)',
        'en': 'Consumption to be confirmed (12-month bill)',
        'ar': 'الاستهلاك في انتظار التأكيد (فواتير 12 شهرا)'},
    'ci_ind_production_estimee': {
        'fr': 'Production estimée ≈ {kwh} kWh/an',
        'en': 'Estimated production ≈ {kwh} kWh/yr',
        'ar': 'الإنتاج المقدر ≈ {kwh} kWh/سنة'},
    'ci_ind_note_autoconso': {
        'fr': "L'installation vise l'<b>autoconsommation</b> : la valeur "
              "porte d'abord sur les <b>heures pleines</b> (production en "
              "journée).",
        'en': 'The installation targets <b>self-consumption</b>: its value '
              'lies first in the <b>peak-rate hours</b> (daytime '
              'production).',
        'ar': 'تستهدف المنشأة <b>الاستهلاك الذاتي</b>: تكمن قيمتها أولا في '
              '<b>الساعات العادية</b> (الإنتاج خلال النهار).'},
    # ── Page finance industrielle (CIQ342, CIQ343) ─────────────────────────
    'ci_ind_analyse_financiere': {'fr': 'Analyse financière',
                                  'en': 'Financial analysis',
                                  'ar': 'التحليل المالي'},
    'ci_ind_rentabilite_sur': {'fr': 'Rentabilité sur {n} ans',
                               'en': 'Profitability over {n} years',
                               'ar': 'المردودية على مدى {n} سنة'},
    'ci_ind_lead': {
        'fr': 'Projection du moteur C&amp;I sur {n} ans : flux, retour et TRI '
              'tirés de la même série ; hypothèses détaillées ci-dessous.',
        'en': 'C&amp;I engine projection over {n} years: cash flow, payback '
              'and IRR drawn from the same series; assumptions detailed '
              'below.',
        'ar': 'إسقاط المحرك التجاري والصناعي على مدى {n} سنة: التدفق ومدة '
              'الاسترداد ومعدل العائد الداخلي مستخرجة من نفس السلسلة؛ '
              'الافتراضات مفصلة أدناه.'},
    'ci_ind_lead_non_chiffre': {
        'fr': "Aucune rentabilité n'est publiée tant qu'elle n'est pas "
              "calculée sur vos données.",
        'en': 'No profitability is published until it is calculated on your '
              'data.',
        'ar': 'لا تُنشر أي مردودية ما لم تُحسب على أساس معطياتكم.'},
    'ci_ind_non_chiffre_titre': {
        'fr': 'Rentabilité non chiffrée sur ce dossier',
        'en': 'Profitability not calculated for this file',
        'ar': 'المردودية غير محسوبة في هذا الملف'},
    'ci_ind_motif_mt': {
        'fr': 'Votre installation est raccordée en <b>MOYENNE TENSION</b> : '
              'ses économies se chiffrent sur le barème MT par poste '
              "horaire, pas sur le barème basse tension. Nous préférons ne "
              "rien afficher plutôt qu'un chiffre qui n'est pas le vôtre.",
        'en': 'Your installation is connected at <b>MEDIUM VOLTAGE</b>: its '
              'savings are calculated on the MV tariff by time band, not on '
              'the low-voltage tariff. We prefer to show nothing rather than '
              'a figure that is not yours.',
        'ar': 'منشأتكم مربوطة <b>بالجهد المتوسط</b>: تُحسب وفوراتها بتعريفة '
              'الجهد المتوسط حسب الفترات الزمنية، لا بتعريفة الجهد المنخفض. '
              'نفضل ألا نعرض شيئا بدل رقم لا يخصكم.'},
    'ci_ind_motif_bt': {
        'fr': "Les <b>économies annuelles</b> de cette installation n'ont pas "
              "encore été calculées sur vos données. Nous préférons ne rien "
              "afficher plutôt qu'un cashflow, un point mort ou un TRI qui ne "
              "reposeraient sur aucune mesure.",
        'en': 'The <b>annual savings</b> of this installation have not yet '
              'been calculated on your data. We prefer to show nothing rather '
              'than a cash flow, a break-even point or an IRR resting on no '
              'measurement.',
        'ar': 'لم تُحسب بعد <b>الوفورات السنوية</b> لهذه المنشأة على أساس '
              'معطياتكم. نفضل ألا نعرض شيئا بدل تدفق نقدي أو نقطة تعادل أو '
              'معدل عائد لا يستند إلى أي قياس.'},
    'ci_ind_retour_flux': {'fr': 'Retour (même flux)',
                           'en': 'Payback (same cash flow)',
                           'ar': 'مدة الاسترداد (نفس التدفق)'},
    'ci_ind_cumul_titre': {'fr': "Cumul net de l'investissement ({base})",
                           'en': 'Net cumulative of the investment ({base})',
                           'ar': 'الرصيد الصافي التراكمي للاستثمار ({base})'},
    'ci_ind_jalon': {'fr': 'Jalon', 'en': 'Milestone', 'ar': 'المرحلة'},
    'ci_ind_cumul_net': {'fr': 'Cumul net', 'en': 'Net cumulative',
                         'ar': 'الرصيد الصافي'},
    'ci_ind_annee': {'fr': 'Année {n}', 'en': 'Year {n}', 'ar': 'السنة {n}'},
    'ci_ind_hypotheses': {'fr': 'Hypothèses du moteur',
                          'en': 'Engine assumptions',
                          'ar': 'افتراضات المحرك'},
    'ci_ind_h_investissement': {'fr': 'Investissement', 'en': 'Investment',
                                'ar': 'الاستثمار'},
    'ci_ind_h_economie': {'fr': "Économie de l'année 1",
                          'en': 'Year-1 saving', 'ar': 'وفر السنة الأولى'},
    'ci_ind_h_production': {'fr': "Production de l'année 1",
                            'en': 'Year-1 production',
                            'ar': 'إنتاج السنة الأولى'},
    'ci_ind_h_horizon': {'fr': 'Horizon', 'en': 'Horizon', 'ar': 'الأفق'},
    'ci_ind_h_taux': {'fr': "Taux d'actualisation", 'en': 'Discount rate',
                      'ar': 'معدل الخصم'},
    'ci_ind_h_indexation': {'fr': 'Indexation du tarif',
                            'en': 'Tariff indexation',
                            'ar': 'فهرسة التعريفة'},
    'ci_ind_h_degradation': {'fr': 'Dégradation des panneaux',
                             'en': 'Panel degradation',
                             'ar': 'تدهور الألواح'},
    'ci_ind_n_ans': {'fr': '{n} ans', 'en': '{n} years', 'ar': '{n} سنة'},
    'ci_ind_remplacement': {
        'fr': 'Remplacement {composant} en année {annee}',
        'en': 'Replacement of the {composant} in year {annee}',
        'ar': 'استبدال {composant} في السنة {annee}'},
    'ci_ind_om_deduite': {'fr': 'O&amp;M déduite du flux : {montant} MAD/an',
                          'en': 'O&amp;M deducted from the cash flow: '
                                '{montant} MAD/yr',
                          'ar': 'الصيانة مخصومة من التدفق: {montant} درهم/سنة'},
    'ci_ind_om_non_deduite': {
        'fr': 'O&amp;M proposée, non déduite de ces montants',
        'en': 'O&amp;M proposed, not deducted from these amounts',
        'ar': 'الصيانة مقترحة، غير مخصومة من هذه المبالغ'},
    'ci_ind_revente_hors_cashflow': {
        'fr': 'revente du surplus, hors cashflow (non comptée dans le retour '
              'ni le TRI).',
        'en': 'sale of the surplus, outside the cash flow (not counted in '
              'the payback or the IRR).',
        'ar': 'بيع الفائض، خارج التدفق النقدي (غير محتسب في مدة الاسترداد '
              'ولا في معدل العائد).'},
    'ci_ind_methode_tri': {
        'fr': 'TRI et retour lus sur le flux servi par le moteur C&amp;I '
              '(méthode actuarielle) ; chiffres indicatifs.',
        'en': 'IRR and payback read on the cash flow served by the C&amp;I '
              'engine (actuarial method); indicative figures.',
        'ar': 'معدل العائد ومدة الاسترداد مقروءان من التدفق الذي يقدمه المحرك '
              'التجاري والصناعي (طريقة اكتوارية)؛ أرقام إرشادية.'},
    'ci_ind_indicateurs': {
        'fr': 'Indicateurs pour votre direction financière',
        'en': 'Indicators for your finance department',
        'ar': 'مؤشرات لإدارتكم المالية'},
    'ci_ind_lcoe': {'fr': 'Coût du kWh solaire (LCOE, {base})',
                    'en': 'Cost of the solar kWh (LCOE, {base})',
                    'ar': 'تكلفة الكيلوواط ساعة الشمسي (LCOE، {base})'},
    'ci_ind_tarif_client': {
        'fr': 'prix moyen de votre kWh évité : {tarif} MAD/kWh',
        'en': 'average price of your avoided kWh: {tarif} MAD/kWh',
        'ar': 'متوسط ثمن الكيلوواط ساعة الذي تتجنبونه: {tarif} MAD/kWh'},
    'ci_ind_van_omise': {'fr': 'VAN non calculée', 'en': 'NPV not calculated',
                         'ar': 'القيمة الحالية الصافية غير محسوبة'},
    'ci_ind_sens_indexation_tarif': {'fr': 'Indexation du tarif',
                                     'en': 'Tariff indexation',
                                     'ar': 'فهرسة التعريفة'},
    'ci_ind_sens_degradation': {'fr': 'Dégradation', 'en': 'Degradation',
                                'ar': 'التدهور'},
    'ci_ind_sens_tarif_kwh': {'fr': 'Prix du kWh', 'en': 'kWh price',
                              'ar': 'ثمن الكيلوواط ساعة'},
    'ci_ind_sens_production': {'fr': 'Production', 'en': 'Production',
                               'ar': 'الإنتاج'},
    'ci_ind_sens_retour': {'fr': 'retour {n} ans', 'en': 'payback {n} years',
                           'ar': 'مدة الاسترداد {n} سنة'},
    'ci_ind_sens_tri': {'fr': 'TRI {t} %', 'en': 'IRR {t} %',
                        'ar': 'معدل العائد {t} %'},
    'ci_ind_sens_base': {
        'fr': "Sensibilités saisies par la société ; base : 0 % "
              "d'indexation du tarif.",
        'en': 'Sensitivities entered by the company; base: 0 % tariff '
              'indexation.',
        'ar': 'حساسيات أدخلتها الشركة؛ الأساس: 0 % فهرسة للتعريفة.'},
    'ci_ind_p90': {
        'fr': 'Production à 90 % de probabilité (P90) : {kwh} kWh/an',
        'en': 'Production at 90 % probability (P90): {kwh} kWh/yr',
        'ar': 'الإنتاج باحتمال 90 % (P90): {kwh} kWh/سنة'},
    # ── Page 4 industrielle (CIQ344, CIQ345) ───────────────────────────────
    'ci_ind_deploiement': {'fr': 'Déploiement &amp; conditions',
                           'en': 'Deployment &amp; terms',
                           'ar': 'التنفيذ والشروط'},
    'ci_ind_valeur_entreprise': {'fr': "Valeur pour l'entreprise",
                                 'en': 'Value for the company',
                                 'ar': 'القيمة بالنسبة للمقاولة'},
    'ci_ind_iso_titre': {'fr': "ISO 50001 — management de l'énergie",
                         'en': 'ISO 50001 — energy management',
                         'ar': 'إيزو 50001 — تدبير الطاقة'},
    'ci_ind_iso_texte': {
        'fr': 'Les données de production et de consommation peuvent '
              'alimenter votre <b>revue énergétique</b> — sans promesse de '
              'conformité à la norme.',
        'en': 'Production and consumption data can feed your <b>energy '
              'review</b> — with no promise of compliance with the standard.',
        'ar': 'يمكن لمعطيات الإنتاج والاستهلاك أن تغذي <b>مراجعتكم '
              'الطاقية</b> — دون وعد بالمطابقة للمعيار.'},
    'ci_ind_cbam_titre': {
        'fr': 'CBAM — ajustement carbone aux frontières (UE)',
        'en': 'CBAM — carbon border adjustment (EU)',
        'ar': 'CBAM — تعديل الكربون على الحدود (الاتحاد الأوروبي)'},
    'ci_ind_bilan_carbone_titre': {
        'fr': 'Bilan carbone de votre électricité',
        'en': 'Carbon footprint of your electricity',
        'ar': 'البصمة الكربونية لكهربائكم'},
    'ci_ind_van_motif': {
        'fr': "aucun taux d'actualisation déclaré par le client",
        'en': 'no discount rate declared by the client',
        'ar': 'لم يصرح الزبون بأي معدل خصم'},
    'ci_ind_pct_an': {'fr': '% / an', 'en': '% / yr', 'ar': '% / سنة'},
    # ── APDF8 — devis RÉSIDENTIEL premium (couverture, détail, confiance) ──
    # Préfixe ``res_``. Le français est le littéral EXACT du gabarit (le
    # gabarit le garde : ``cover.libelle_fixe`` le rend tel quel en fr) ; les
    # ``{…}`` reçoivent des valeurs DÉJÀ formatées (date, nombre, marque).
    'res_valable_jusqu': {'fr': "Valable jusqu'au {date}",
                          'en': 'Valid until {date}',
                          'ar': 'صالح إلى غاية {date}'},
    'res_ref_devis': {'fr': 'Réf. devis', 'en': 'Quote ref.',
                      'ar': 'مرجع العرض'},
    'res_kicker': {'fr': 'Proposition commerciale — Installation solaire',
                   'en': 'Commercial proposal - Solar installation',
                   'ar': 'عرض تجاري — تركيب شمسي'},
    'res_bonjour': {'fr': 'Bonjour {nom},', 'en': 'Hello {nom},',
                    'ar': 'مرحبًا {nom}،'},
    'res_votre_installation_solaire': {'fr': 'Votre installation solaire',
                                       'en': 'Your solar installation',
                                       'ar': 'منشأتكم الشمسية'},
    'res_facture_reduite': {
        'fr': "Votre facture d'électricité réduite d'environ {pct}&nbsp;%",
        'en': 'Your electricity bill reduced by about {pct}&nbsp;%',
        'ar': 'فاتورة الكهرباء لديكم تنخفض بنحو {pct}&nbsp;%'},
    # AGNR6 (D-AGNR-1 option (a)) — libellé client de la source
    # ``facture_hiver_ete`` (contrat ``factures_client.json``) : la variation
    # mensuelle vient de DEUX factures répétées en marches, jamais « réelles ».
    'res_estimation_deux_factures': {
        'fr': 'Estimation — deux factures (hiver/été)',
        'en': 'Estimate — two bills (winter/summer)',
        'ar': 'تقدير — فاتورتان (الشتاء/الصيف)'},
    'res_perf_garantie': {'fr': 'performance garantie {ans}&nbsp;ans',
                          'en': 'performance guaranteed {ans}&nbsp;years',
                          'ar': 'أداء مضمون لمدة {ans}&nbsp;سنة'},
    'res_perf_trust': {'fr': 'Performance garantie {ans} ans &middot; ',
                       'en': 'Performance guaranteed {ans} years &middot; ',
                       'ar': 'أداء مضمون لمدة {ans} سنة &middot; '},
    'res_pourquoi_pas_cov': {
        'fr': ('Pourquoi pas \u2212{cov} % ? Seuls les kWh autoconsommés '
               "réduisent la facture (loi 82-21) — le surplus injecté n'est "
               'pas rémunéré.'),
        'en': ('Why not -{cov} %? Only self-consumed kWh reduce the bill '
               '(law 82-21) - the surplus fed into the grid is not paid for.'),
        'ar': ('لماذا ليس \u2212{cov} %؟ وحدها الكيلوواط ساعة المستهلكة ذاتيًا '
               'تخفض الفاتورة (القانون 82-21) — الفائض المحقون في الشبكة غير '
               'مؤدى عنه.')},
    'res_consultez_proposition': {
        'fr': 'Consultez votre proposition interactive',
        'en': 'View your interactive proposal',
        'ar': 'اطلعوا على عرضكم التفاعلي'},
    'res_scannez_code': {'fr': '— scannez le code', 'en': '- scan the code',
                         'ar': '— امسحوا الرمز'},
    'res_recommande': {'fr': 'Recommandé', 'en': 'Recommended',
                       'ar': 'موصى به'},
    'res_detail_page2': {'fr': 'Détail &amp; équipement en page 2',
                         'en': 'Details &amp; equipment on page 2',
                         'ar': 'التفاصيل والمعدات في الصفحة 2'},
    'res_ingenieurs': {'fr': 'Ingénieurs solaires', 'en': 'Solar engineers',
                       'ar': 'مهندسو الطاقة الشمسية'},
    'res_suivi_temps_reel': {'fr': 'Suivi en temps réel',
                             'en': 'Real-time monitoring',
                             'ar': 'تتبع في الوقت الحقيقي'},
    'res_votre_installation': {'fr': 'Votre installation',
                               'en': 'Your installation', 'ar': 'منشأتكم'},
    'res_detail_projet': {'fr': 'Le détail de votre projet',
                          'en': 'Your project in detail',
                          'ar': 'تفاصيل مشروعكم'},
    'res_kwc_installes': {'fr': 'kWc installés', 'en': 'kWp installed',
                          'ar': 'كيلوواط ذروة مركبة'},
    'res_kwc_installes_sans_avec': {
        'fr': 'kWc installés (sans · avec)',
        'en': 'kWp installed (without · with)',
        'ar': 'كيلوواط ذروة مركبة (بدون · مع)'},
    'res_kwh_produits': {'fr': 'kWh / an produits',
                         'en': 'kWh / year produced',
                         'ar': 'كيلوواط ساعة / سنة منتجة'},
    'res_kwh_produits_sans_avec': {
        'fr': 'kWh / an produits (sans · avec)',
        'en': 'kWh / year produced (without · with)',
        'ar': 'كيلوواط ساعة / سنة منتجة (بدون · مع)'},
    'res_votre_equipement': {'fr': 'Votre équipement',
                             'en': 'Your equipment', 'ar': 'معداتكم'},
    'res_equipement_commun': {'fr': 'Équipement commun aux deux options',
                              'en': 'Equipment common to both options',
                              'ar': 'معدات مشتركة بين الخيارين'},
    'res_equipement_deux': {'fr': 'Équipement des deux options',
                            'en': 'Equipment of both options',
                            'ar': 'معدات الخيارين'},
    'res_pourquoi_avec': {
        'fr': ('Pourquoi nous la recommandons : vos soirées et les coupures '
               'passent sur batterie.'),
        'en': 'Why we recommend it: your evenings and power cuts run on the '
              'battery.',
        'ar': 'لماذا نوصي به: أمسياتكم وانقطاعات التيار تمر عبر البطارية.'},
    'res_pourquoi_sans': {
        'fr': ("Pourquoi nous la recommandons : l'investissement le plus "
               'court à rembourser.'),
        'en': 'Why we recommend it: the investment with the shortest '
              'payback.',
        'ar': 'لماذا نوصي به: الاستثمار الأسرع استردادًا.'},
    'res_pourquoi_hybride': {
        'fr': ("Pourquoi nous la recommandons : l'onduleur hybride est prêt "
               "pour la batterie — vous l'ajoutez quand vous voulez, sans "
               "changer d'onduleur."),
        'en': ('Why we recommend it: the hybrid inverter is battery-ready - '
               'you add the battery whenever you like, without changing the '
               'inverter.'),
        'ar': ('لماذا نوصي به: العاكس الهجين جاهز للبطارية — تضيفونها متى '
               'شئتم دون تغيير العاكس.')},
    'res_confiance': {'fr': 'Confiance &amp; Engagement',
                      'en': 'Trust &amp; Commitment',
                      'ar': 'الثقة والالتزام'},
    'res_pourquoi_marque': {'fr': 'Pourquoi {marque}', 'en': 'Why {marque}',
                            'ar': 'لماذا {marque}'},
    'res_nos_garanties': {'fr': 'Nos garanties', 'en': 'Our warranties',
                          'ar': 'ضماناتنا'},
    'res_garanties_note': {
        'fr': ('Les garanties fabricant sont attachées au matériel : elles '
               'suivent votre installation, restent transférables avec le '
               "bien et demeurent valables quel que soit l'installateur."),
        'en': ('Manufacturer warranties are attached to the equipment: they '
               'follow your installation, remain transferable with the '
               'property and stay valid whoever the installer is.'),
        'ar': ('ضمانات المصنع مرتبطة بالمعدات: تتبع منشأتكم، وتبقى قابلة '
               'للتحويل مع العقار، وتظل سارية أيًا كان المركب.')},
    'res_preuve_en_ligne': {'fr': 'La preuve, en ligne',
                            'en': 'The proof, online',
                            'ar': 'الدليل، على الإنترنت'},
    'res_realisations_avis': {'fr': 'Réalisations et avis clients',
                              'en': 'Projects and customer reviews',
                              'ar': 'إنجازات وآراء العملاء'},
    'res_fiches_produits': {'fr': 'Fiches techniques produits',
                            'en': 'Product datasheets',
                            'ar': 'البطاقات التقنية للمنتجات'},
    'res_garanties_certifs': {'fr': 'Garanties et certifications',
                              'en': 'Warranties and certifications',
                              'ar': 'الضمانات والشهادات'},
    'res_conditions': {'fr': 'Conditions', 'en': 'Terms', 'ar': 'الشروط'},
    'res_prochaines_etapes': {'fr': 'Prochaines étapes', 'en': 'Next steps',
                              'ar': 'الخطوات التالية'},
    'res_validite_offre': {'fr': "Validité de l'offre",
                           'en': 'Offer validity', 'ar': 'صلاحية العرض'},
    'res_jusqu_au': {'fr': "jusqu'au {date}", 'en': 'until {date}',
                     'ar': 'إلى غاية {date}'},
    'res_paiement': {'fr': 'Paiement', 'en': 'Payment', 'ar': 'الأداء'},
    'res_signature_devis': {'fr': 'Signature du devis',
                            'en': 'Quote signature', 'ar': 'توقيع العرض'},
    'res_plus_acompte': {'fr': '+ acompte {pct}%', 'en': '+ {pct}% deposit',
                         'ar': '+ تسبيق {pct}%'},
    'res_visite_technique': {'fr': 'Visite technique',
                             'en': 'Technical visit', 'ar': 'زيارة تقنية'},
    'res_installation': {'fr': 'Installation', 'en': 'Installation',
                         'ar': 'التركيب'},
    'res_mise_en_service': {'fr': 'Mise en service', 'en': 'Commissioning',
                            'ar': 'التشغيل'},
    'res_tests_formation': {'fr': 'tests + formation',
                            'en': 'tests + training',
                            'ar': 'اختبارات + تكوين'},
    'res_offre_valable': {'fr': "Offre valable jusqu'au {date}",
                          'en': 'Offer valid until {date}',
                          'ar': 'العرض صالح إلى غاية {date}'},
    'res_cta_offre': {'fr': " Offre valable jusqu'au {date}.",
                      'en': ' Offer valid until {date}.',
                      'ar': ' العرض صالح إلى غاية {date}.'},
    'res_cochez_option': {'fr': 'Cochez votre option :',
                          'en': 'Tick your option:',
                          'ar': 'ضعوا علامة على خياركم:'},
    'res_bon_pour_accord': {'fr': 'Bon pour accord',
                            'en': 'Approved and agreed',
                            'ar': 'موافقة وقبول'},
    'res_bpa_client': {'fr': 'Bon pour accord — le client',
                       'en': 'Approved and agreed - the client',
                       'ar': 'موافقة وقبول — العميل'},
    'res_bpa_mention': {
        'fr': 'Nom, date, mention « Bon pour accord » &amp; signature',
        'en': 'Name, date, the words "Approved and agreed" &amp; signature',
        'ar': 'الاسم والتاريخ وعبارة «موافقة وقبول» والتوقيع'},
    'res_pour_marque': {'fr': 'Pour {marque}', 'en': 'For {marque}',
                        'ar': 'عن {marque}'},
    'res_cachet_signature': {'fr': 'Cachet et signature',
                             'en': 'Stamp and signature',
                             'ar': 'الختم والتوقيع'},
    'res_devis_fait_foi': {
        'fr': "Le devis fait foi dès réception de l'acompte",
        'en': 'The quote is binding upon receipt of the deposit',
        'ar': 'يصبح العرض ملزمًا عند استلام التسبيق'},
    'res_pret_solaire': {'fr': 'Prêt à passer au solaire ?',
                         'en': 'Ready to go solar?',
                         'ar': 'مستعدون للانتقال إلى الطاقة الشمسية؟'},
    'res_validez_devis': {
        'fr': 'Validez votre devis en quelques clics, sans vous déplacer.',
        'en': 'Approve your quote in a few clicks, without travelling.',
        'ar': 'صادقوا على عرضكم ببضع نقرات دون أن تتنقلوا.'},
    'res_signez_en_ligne': {'fr': 'Signez en ligne', 'en': 'Sign online',
                            'ar': 'وقعوا عبر الإنترنت'},
    'res_scannez_signer': {'fr': 'Scannez pour signer', 'en': 'Scan to sign',
                           'ar': 'امسحوا للتوقيع'},
    # ── APDF9 — UNE PAGE legacy + titre des clauses particulières ──────────
    # Préfixe ``op_``. Le français est le littéral EXACT du gabarit legacy
    # (entités comprises) : ``_L`` le rend tel quel, octet pour octet.
    'op_consultez_proposition': {
        'fr': 'Consultez votre<br>proposition interactive',
        'en': 'View your<br>interactive proposal',
        'ar': 'اطلعوا على<br>عرضكم التفاعلي'},
    'op_devis': {'fr': 'DEVIS', 'en': 'QUOTE', 'ar': 'عرض سعر'},
    'op_numero': {'fr': 'N&#176;', 'en': 'No.', 'ar': 'رقم'},
    'op_puissance_crete': {'fr': 'Puissance cr&#234;te', 'en': 'Peak power',
                           'ar': 'القدرة القصوى'},
    'op_production_annuelle': {'fr': 'Production annuelle',
                               'en': 'Annual production',
                               'ar': 'الإنتاج السنوي'},
    'op_economie_annuelle': {'fr': '&#201;conomie annuelle',
                             'en': 'Annual savings', 'ar': 'التوفير السنوي'},
    'op_estimation': {'fr': ' (estimation)', 'en': ' (estimate)',
                      'ar': ' (تقدير)'},
    'op_prix_par_kwc': {'fr': 'Prix par kWc', 'en': 'Price per kWp',
                        'ar': 'السعر لكل كيلوواط ذروة'},
    'op_residuel_vise': {'fr': 'R&#233;siduel vis&#233;',
                         'en': 'Target residual', 'ar': 'المتبقي المستهدف'},
    'op_economies_estimees_an': {'fr': '&#201;conomies estim&#233;es / an',
                                 'en': 'Estimated savings / year',
                                 'ar': 'التوفير المقدر / سنة'},
    'op_retour_estime': {'fr': 'Retour estim&#233;',
                         'en': 'Estimated payback',
                         'ar': 'مدة الاسترداد المقدرة'},
    'op_validite_jusqu': {
        'fr': 'Validit&#233;&#160;: jusqu&#8217;au {date}',
        'en': 'Valid until {date}', 'ar': 'صالح إلى غاية {date}'},
    'op_siege': {'fr': 'Si\u00e8ge\u00a0:', 'en': 'Head office:',
                 'ar': 'المقر:'},
    'clauses_particulieres': {'fr': 'Clauses particulières',
                              'en': 'Special terms', 'ar': 'شروط خاصة'},
    # ── APDF10 — puces CGV PAR DÉFAUT et note de TVA du builder ────────────
    # Le français est EXACTEMENT ``DEFAULT_DOC_TEXTS['cgv_bullets']`` / le
    # texte de ``builder.tva_note_des_lignes`` : marqueurs ``{…}`` et
    # pourcentages identiques dans les trois langues. Une puce SAISIE par la
    # société n'est jamais traduite (décision : son texte reste souverain).
    'cgv_validite_offre': {
        'fr': 'Validit&#233; de l&#8217;offre&#160;: jusqu&#8217;au {date}',
        'en': 'Offer valid until {date}',
        'ar': 'العرض صالح إلى غاية {date}'},
    'cgv_acompte_commande': {
        'fr': 'Acompte à la commande&#160;: {acompte}&#37;',
        'en': 'Down payment on order: {acompte}&#37;',
        'ar': 'تسبيق عند الطلب: {acompte}&#37;'},
    'cgv_reception_materiel': {
        'fr': '{materiel}&#37; à la réception du matériel',
        'en': '{materiel}&#37; on delivery of the equipment',
        'ar': '{materiel}&#37; عند استلام المعدات'},
    'cgv_mise_en_marche': {
        'fr': '{solde}&#37; après la mise en marche',
        'en': '{solde}&#37; after commissioning',
        'ar': '{solde}&#37; بعد التشغيل'},
    'cgv_tarifs_reference': {
        'fr': 'Tarifs de référence&#160;: barème ONEE/SRM',
        'en': 'Reference tariffs: ONEE/SRM schedule',
        'ar': 'التعريفات المرجعية: جدول ONEE/SRM'},
    'tva_unique': {
        'fr': ("TVA {taux} % appliquée sur l'ensemble des équipements et "
               "travaux."),
        'en': 'VAT {taux} % applied to all equipment and works.',
        'ar': 'ضريبة القيمة المضافة {taux} % مطبقة على كل المعدات والأشغال.'},
    'tva_10_20': {
        'fr': ('TVA : 10% panneaux photovoltaïques · 20% autres équipements '
               'et prestations'),
        'en': 'VAT: 10% solar panels · 20% other equipment and services',
        'ar': ('ضريبة القيمة المضافة: 10% الألواح الكهروضوئية · 20% '
               'المعدات والخدمات الأخرى')},
    'tva_ligne_par_ligne': {
        'fr': 'TVA appliquée ligne par ligne : {taux}',
        'en': 'VAT applied line by line: {taux}',
        'ar': 'ضريبة القيمة المضافة مطبقة سطرًا بسطر: {taux}'},
    'tva_taux_tableau': {
        'fr': ' — taux indiqué dans le tableau',
        'en': ' - rate shown in the table',
        'ar': ' — النسبة مبينة في الجدول'},
    'tva_exoneration': {'fr': 'exonération : {base}',
                        'en': 'exemption: {base}', 'ar': 'إعفاء: {base}'},
    # ── APDF46 — page 3 du moteur LEGACY (étude résidentielle 4 pages) ──────
    # Préfixe ``lg_`` ; le français est le littéral exact du gabarit.
    'lg_confiance_bpa': {'fr': 'Confiance, Garanties &amp; Bon pour accord',
                         'en': 'Trust, Warranties &amp; Approval',
                         'ar': 'الثقة والضمانات والموافقة'},
    'lg_pourquoi_choisir': {'fr': 'Pourquoi choisir {marque}&#160;?',
                            'en': 'Why choose {marque}?',
                            'ar': 'لماذا تختارون {marque}؟'},
    'lg_experts_engages': {
        'fr': 'Des experts engagés pour votre transition énergétique',
        'en': 'Committed experts for your energy transition',
        'ar': 'خبراء ملتزمون بانتقالكم الطاقي'},
    # ── ERR-APDF-LIBELLES-FR-RESTANTS-EN-AR — libellés fixes restés en dur ──
    # Devis résidentiel premium (couverture, détail, confiance), une-page
    # legacy et jalons des CGV C&I. Le français est le littéral EXACT du
    # gabarit (ou du libellé par défaut du builder) : octet pour octet.
    'res_tag_residentielle': {'fr': 'Résidentielle', 'en': 'Residential',
                              'ar': 'سكني'},
    'res_hook_titre': {'fr': 'Ce que le solaire change pour vous',
                       'en': 'What solar changes for you',
                       'ar': 'ما تغيّره الطاقة الشمسية لكم'},
    'res_sur_facture': {'fr': "sur votre facture<br>d'électricité",
                        'en': 'on your<br>electricity bill',
                        'ar': 'من فاتورة<br>الكهرباء'},
    'res_aujourdhui': {'fr': "aujourd'hui", 'en': 'today', 'ar': 'اليوم'},
    'res_chiffres_reco': {
        'fr': "Chiffres calculés pour l'option recommandée — {option}.",
        'en': 'Figures calculated for the recommended option — {option}.',
        'ar': 'أرقام محسوبة للخيار الموصى به — {option}.'},
    'res_chiffres_presentee': {
        'fr': "Chiffres calculés pour l'option présentée — {option}.",
        'en': 'Figures calculated for the option shown — {option}.',
        'ar': 'أرقام محسوبة للخيار المعروض — {option}.'},
    'res_donut_titre': {'fr': 'Énergie solaire', 'en': 'Solar energy',
                        'ar': 'الطاقة الشمسية'},
    'res_donut_cap': {
        'fr': ('de votre consommation<span>annuelle assurée par le '
               'solaire{est}</span>'),
        'en': 'of your annual<span>consumption covered by solar{est}</span>',
        'ar': 'من استهلاككم<span>السنوي تغطيه الطاقة الشمسية{est}</span>'},
    'res_facture_mois': {'fr': 'Votre facture mois par mois — avant / après',
                         'en': 'Your bill month by month — before / after',
                         'ar': 'فاتورتكم شهراً بشهر — قبل / بعد'},
    'res_avec_marque': {'fr': 'avec {marque}', 'en': 'with {marque}',
                        'ar': 'مع {marque}'},
    'res_kpi_puissance_nw': {'fr': 'Puissance · {n} panneaux × {w} W',
                             'en': 'Power · {n} panels × {w} W',
                             'ar': 'القدرة · {n} ألواح × {w} W'},
    'res_kpi_puissance_n': {'fr': 'Puissance · {n} panneaux',
                            'en': 'Power · {n} panels',
                            'ar': 'القدرة · {n} ألواح'},
    'res_kpi_puissance': {'fr': 'Puissance', 'en': 'Power', 'ar': 'القدرة'},
    'res_kpi_puissance_sans_avec': {
        'fr': 'Puissance sans · avec · {s} · {a} panneaux',
        'en': 'Power without · with · {s} · {a} panels',
        'ar': 'القدرة بدون · مع · {s} · {a} ألواح'},
    'res_unite_kwc': {'fr': '&nbsp;kWc', 'en': '&nbsp;kWp', 'ar': '&nbsp;kWp'},
    'res_n_kwc': {'fr': '{n} kWc', 'en': '{n} kWp', 'ar': '{n} kWp'},
    'res_kpi_production': {'fr': 'Production estimée',
                           'en': 'Estimated production',
                           'ar': 'الإنتاج المقدر'},
    'res_kpi_production_sans_avec': {
        'fr': 'Production estimée sans · avec',
        'en': 'Estimated production without · with',
        'ar': 'الإنتاج المقدر بدون · مع'},
    'res_kpi_eco_calculee': {'fr': 'Économie calculée',
                             'en': 'Calculated savings',
                             'ar': 'الوفورات المحسوبة'},
    'res_kpi_eco_estimee': {'fr': 'Économie estimée',
                            'en': 'Estimated savings',
                            'ar': 'الوفورات المقدرة'},
    'res_impact_planete': {
        'fr': ('Et pour la planète&nbsp;: ≈&nbsp;<b>{co2} tonnes de '
               'CO<sub>2</sub></b>\n        évitées chaque année.'),
        'en': ('And for the planet: ≈&nbsp;<b>{co2} tonnes of '
               'CO<sub>2</sub></b> avoided every year.'),
        'ar': ('ومن أجل الكوكب: ≈&nbsp;<b>{co2} طن من CO<sub>2</sub></b> '
               'يتم تجنبها كل سنة.')},
    'res_et_planete': {'fr': 'Et pour la planète', 'en': 'And for the planet',
                       'ar': 'ومن أجل الكوكب'},
    'res_co2_evitees': {'fr': 'de CO<sub>2</sub> évitées chaque année',
                        'en': 'of CO<sub>2</sub> avoided every year',
                        'ar': 'من CO<sub>2</sub> يتم تجنبها كل سنة'},
    # Noms d'option : « Sans batterie » du gabarit, puis les deux libellés
    # que le builder sert pour l'option 2 (``libelle_avec``, BAT-DIFF) —
    # voir ``CLES_OPTION`` ; un libellé saisi hors catalogue reste tel quel.
    'res_opt_sans': {'fr': 'Sans batterie', 'en': 'Without battery',
                     'ar': 'بدون بطارية'},
    'res_opt_avec': {'fr': 'Avec batterie', 'en': 'With battery',
                     'ar': 'مع بطارية'},
    'res_opt_hybride': {'fr': 'Hybride, batterie plus tard',
                        'en': 'Hybrid, battery later',
                        'ar': 'هجين، البطارية لاحقاً'},
    'res_option_n': {'fr': 'Option {n}', 'en': 'Option {n}',
                     'ar': 'الخيار {n}'},
    'res_option_n_nom': {'fr': 'Option {n} — {option}',
                         'en': 'Option {n} — {option}',
                         'ar': 'الخيار {n} — {option}'},
    'res_option_nom': {'fr': 'option {option}', 'en': 'option {option}',
                       'ar': 'خيار {option}'},
    'res_specifique_option': {'fr': 'Spécifique à l&rsquo;option {n} — {option}',
                              'en': 'Specific to option {n} — {option}',
                              'ar': 'خاص بالخيار {n} — {option}'},
    'res_total_option': {'fr': 'Total — {option}', 'en': 'Total — {option}',
                         'ar': 'المجموع — {option}'},
    'res_prix_kwc': {'fr': 'soit {prix} MAD/kWc · TTC',
                     'en': 'i.e. {prix} MAD/kWp · incl. VAT',
                     'ar': 'أي {prix} درهم/kWp · شامل الضريبة'},
    'res_rentabilise_en': {'fr': 'Rentabilisé en {n} ans',
                           'en': 'Paid back in {n} years',
                           'ar': 'مسترد خلال {n} سنوات'},
    'res_non_rentabilise_25': {'fr': 'Non rentabilisé sur 25 ans',
                               'en': 'Not paid back within 25 years',
                               'ar': 'غير مسترد خلال 25 سنة'},
    'res_non_rentabilise_maj': {'fr': 'Non rentabilisé',
                                'en': 'Not paid back', 'ar': 'غير مسترد'},
    'res_non_rentabilise': {'fr': 'non rentabilisé', 'en': 'not paid back',
                            'ar': 'غير مسترد'},
    'res_opt_eco': {'fr': 'Économie ≈ <b>{v} MAD/an</b>',
                    'en': 'Savings ≈ <b>{v} MAD/yr</b>',
                    'ar': 'الوفورات ≈ <b>{v} درهم/سنة</b>'},
    'res_opt_eco_calculee': {'fr': 'Économie calculée ≈ <b>{v} MAD/an</b>',
                             'en': 'Calculated savings ≈ <b>{v} MAD/yr</b>',
                             'ar': 'الوفورات المحسوبة ≈ <b>{v} درهم/سنة</b>'},
    'res_opt_eco_estimee': {'fr': 'Économie estimée ≈ <b>{v} MAD/an</b>',
                            'en': 'Estimated savings ≈ <b>{v} MAD/yr</b>',
                            'ar': 'الوفورات المقدرة ≈ <b>{v} درهم/سنة</b>'},
    'res_spec_panneaux': {'fr': 'panneaux{w}', 'en': 'panels{w}',
                          'ar': 'ألواح{w}'},
    'res_spec_panneaux_sans_avec': {'fr': 'panneaux (sans · avec){w}',
                                    'en': 'panels (without · with){w}',
                                    'ar': 'ألواح (بدون · مع){w}'},
    'res_n_ans': {'fr': '{n} ans', 'en': '{n} years', 'ar': '{n} سنوات'},
    'res_n_m_ans': {'fr': '{a} – {b} ans', 'en': '{a} – {b} years',
                    'ar': '{a} – {b} سنوات'},
    'res_au_tarif_actuel': {'fr': 'au tarif actuel',
                            'en': 'at the current tariff',
                            'ar': 'بالتعريفة الحالية'},
    'res_se_rembourse': {'fr': "l'installation se rembourse",
                         'en': 'the installation pays for itself',
                         'ar': 'المنشأة تسترد تكلفتها'},
    'res_gain_mult': {'fr': ' — soit ≈ <b>{x}×</b> votre investissement',
                      'en': ' — i.e. ≈ <b>{x}×</b> your investment',
                      'ar': ' — أي ≈ <b>{x}×</b> استثماركم'},
    'res_cmp_batteries': {'fr': 'Batteries', 'en': 'Batteries',
                          'ar': 'البطاريات'},
    'res_cmp_prix_ttc': {'fr': 'Prix TTC', 'en': 'Price incl. VAT',
                         'ar': 'السعر شامل الضريبة'},
    'res_cmp_eco': {'fr': 'Économies / an', 'en': 'Savings / yr',
                    'ar': 'الوفورات / سنة'},
    'res_cmp_eco_calculees': {'fr': 'Économies calculées / an',
                              'en': 'Calculated savings / yr',
                              'ar': 'الوفورات المحسوبة / سنة'},
    'res_cmp_eco_estimees': {'fr': 'Économies estimées / an',
                             'en': 'Estimated savings / yr',
                             'ar': 'الوفورات المقدرة / سنة'},
    'res_retour_invest': {'fr': 'Retour sur investissement',
                          'en': 'Payback', 'ar': 'استرداد الاستثمار'},
    'res_gain_net_25': {'fr': 'Gain net sur 25 ans',
                        'en': 'Net gain over 25 years',
                        'ar': 'صافي الربح على 25 سنة'},
    'res_perf_garantie_titre': {'fr': 'Performance garantie',
                                'en': 'Guaranteed performance',
                                'ar': 'الأداء المضمون'},
    'res_perf_panneaux': {'fr': 'panneaux — {sub}', 'en': 'panels — {sub}',
                          'ar': 'الألواح — {sub}'},
    'res_gar_pct_garanti': {'fr': '{pct} garanti', 'en': '{pct} guaranteed',
                            'ar': '{pct} مضمون'},
    'res_gar_lineaire': {'fr': 'performance linéaire',
                         'en': 'linear performance', 'ar': 'أداء خطي'},
    'res_fin_sub_deux': {
        'fr': ('gain cumulé, deux scénarios — le point marque le retour '
               'sur investissement'),
        'en': 'cumulative gain, two scenarios — the dot marks the payback',
        'ar': 'الربح التراكمي، سيناريوهان — النقطة تحدد استرداد الاستثمار'},
    'res_fin_sub_un': {
        'fr': 'gain cumulé — le point marque le retour sur investissement',
        'en': 'cumulative gain — the dot marks the payback',
        'ar': 'الربح التراكمي — النقطة تحدد استرداد الاستثمار'},
    'res_fin_remplacement': {
        'fr': (' · remplacement onduleur provisionné en année {an} '
               '({montant} MAD)'),
        'en': ' · inverter replacement provisioned in year {an} ({montant} MAD)',
        'ar': ' · استبدال العاكس مرصود في السنة {an} ({montant} درهم)'},
    'res_fin_cap': {
        'fr': ("Projection <b>à tarif électricité constant</b> — toute hausse "
               "future du prix de l'électricité accélère votre rentabilité, "
               "votre coût solaire restant fixe."),
        'en': ('Projection <b>at a constant electricity tariff</b> — any '
               'future rise in electricity prices speeds up your return, '
               'your solar cost staying fixed.'),
        'ar': ('إسقاط <b>بتعريفة كهرباء ثابتة</b> — أي ارتفاع مستقبلي في سعر '
               'الكهرباء يسرّع مردوديتكم، إذ تبقى تكلفتكم الشمسية ثابتة.')},
    'res_palier': {
        'fr': (" Le palier en année&nbsp;{an} : provision de remplacement de "
               "l'onduleur, déjà déduite."),
        'en': (' The step in year&nbsp;{an}: inverter replacement provision, '
               'already deducted.'),
        'ar': ' العتبة في السنة&nbsp;{an}: مخصص استبدال العاكس، مخصوم مسبقاً.'},
    'res_rentabilite_25': {'fr': 'Rentabilité sur 25 ans',
                           'en': 'Return over 25 years',
                           'ar': 'المردودية على 25 سنة'},
    'res_votre_rentabilite': {'fr': 'Votre rentabilité', 'en': 'Your return',
                              'ar': 'مردوديتكم'},
    'res_rentabilite_invest': {'fr': 'Rentabilité de votre investissement',
                               'en': 'Return on your investment',
                               'ar': 'مردودية استثماركم'},
    'res_equipement_suite': {'fr': 'Équipement — suite',
                             'en': 'Equipment — continued',
                             'ar': 'المعدات — تتمة'},
    'res_suite_lbl': {'fr': '{lbl} (suite)', 'en': '{lbl} (continued)',
                      'ar': '{lbl} (تتمة)'},
    'res_suite_page': {'fr': "Suite de l'équipement page suivante &rsaquo;",
                       'en': 'Equipment continued on next page &rsaquo;',
                       'ar': 'تتمة المعدات في الصفحة التالية &rsaquo;'},
    'res_callout': {
        'fr': ('≈ {gain} MAD de gain net sur 25 ans — <b>{x}× le prix de '
               'votre installation</b>'),
        'en': ('≈ {gain} MAD net gain over 25 years — <b>{x}× the price of '
               'your installation</b>'),
        'ar': '≈ {gain} درهم صافي ربح على 25 سنة — <b>{x}× سعر منشأتكم</b>'},
    'res_votre_toiture': {'fr': 'Votre toiture', 'en': 'Your roof',
                          'ar': 'سطحكم'},
    'res_votre_calepinage': {'fr': 'Votre calepinage',
                             'en': 'Your panel layout',
                             'ar': 'توزيع ألواحكم'},
    'res_deux_valeurs': {
        'fr': 'deux valeurs&nbsp;: <b>sans</b> &middot; <b>avec</b> batterie',
        'en': 'two values: <b>without</b> &middot; <b>with</b> battery',
        'ar': 'قيمتان: <b>بدون</b> &middot; <b>مع</b> بطارية'},
    'res_fiches_techniques': {'fr': ' &middot; fiches techniques&nbsp;: ',
                              'en': ' &middot; datasheets: ',
                              'ar': ' &middot; البطاقات التقنية: '},
    'res_note_remise': {
        'fr': (' &middot; Remise de {pct}\u202f% appliquée sur chaque ligne '
               '— prix catalogue barrés, totaux après remise.'),
        'en': (' &middot; {pct}\u202f% discount applied to each line — list '
               'prices struck through, totals after discount.'),
        'ar': (' &middot; خصم {pct}\u202f% مطبق على كل سطر — أسعار الكتالوج '
               'مشطوبة، والمجاميع بعد الخصم.')},
    'res_options_proposees': {
        'fr': 'Options propos&eacute;es (non incluses dans le total)',
        'en': 'Proposed options (not included in the total)',
        'ar': 'خيارات مقترحة (غير مدرجة في المجموع)'},
    'res_activez_option': {
        'fr': ('Activez une option avant signature pour l&rsquo;inclure '
               '&agrave; votre devis.'),
        'en': 'Activate an option before signing to include it in your quote.',
        'ar': 'فعّلوا خياراً قبل التوقيع لإدراجه في عرض السعر.'},
    'res_multi_identiques': {
        'fr': '&times;&nbsp;{n} propriétés identiques{total}',
        'en': '&times;&nbsp;{n} identical properties{total}',
        'ar': '&times;&nbsp;{n} عقارات متطابقة{total}'},
    'res_multi_total': {'fr': ' — total pour {n} propriétés : {montant} MAD',
                        'en': ' — total for {n} properties: {montant} MAD',
                        'ar': ' — المجموع لـ {n} عقارات: {montant} درهم'},
    'res_total_general': {'fr': 'Total général', 'en': 'Grand total',
                          'ar': 'المجموع العام'},
    'res_detail_propriete': {'fr': 'Détail par propriété',
                             'en': 'Breakdown by property',
                             'ar': 'التفاصيل حسب العقار'},
    'res_propriete': {'fr': 'Propriété', 'en': 'Property', 'ar': 'العقار'},
    'res_methode_titre': {'fr': 'Comment nous calculons vos économies',
                          'en': 'How we calculate your savings',
                          'ar': 'كيف نحسب وفوراتكم'},
    # Phrases de méthode du builder (QF3), par ``savings_method['model']``.
    'res_methode_factures': {
        'fr': ('Facture recalculée au barème réel du distributeur (progressif '
               '≤ 150 kWh/mois, puis sélectif : toute la conso du mois au '
               'tarif de SA tranche) : facture actuelle moins facture '
               'résiduelle après autoconsommation — jamais un prix moyen '
               'inventé.'),
        'en': ("Bill recalculated on the distributor's actual tariff "
               '(progressive up to 150 kWh/month, then selective: the whole '
               "month's consumption at ITS band's rate): current bill minus "
               'the residual bill after self-consumption — never an invented '
               'average price.'),
        'ar': ('فاتورة أعيد حسابها وفق التعريفة الفعلية للموزع (تصاعدية حتى '
               '150 kWh/شهر، ثم انتقائية: كل استهلاك الشهر بسعر شريحته): '
               'الفاتورة الحالية ناقص الفاتورة المتبقية بعد الاستهلاك الذاتي — '
               'لا سعر متوسط مختلق أبداً.')},
    'res_methode_horaire': {
        'fr': ('Économies intégrées heure par heure : la production solaire de '
               'votre site (données PVGIS) confrontée à votre courbe de '
               'consommation, mois par mois, chaque mois valorisé au barème '
               'réel du distributeur. Le point de départ est VOTRE facture — '
               "c'est la méthode la plus fine de ce document."),
        'en': ('Savings integrated hour by hour: the solar production of your '
               'site (PVGIS data) set against your consumption curve, month '
               "by month, each month valued at the distributor's actual "
               'tariff. The starting point is YOUR bill — the finest method '
               'in this document.'),
        'ar': ('وفورات محسوبة ساعة بساعة: الإنتاج الشمسي لموقعكم (بيانات '
               'PVGIS) مقابل منحنى استهلاككم، شهراً بشهر، وكل شهر مقيّم وفق '
               'التعريفة الفعلية للموزع. نقطة الانطلاق هي فاتورتكم — وهي أدق '
               'طريقة في هذه الوثيقة.')},
    'res_methode_etude_corrige': {
        'fr': ("Économies saisies dans l'étude de consommation enregistrée "
               'avec ce devis ; le retour sur investissement et le gain net '
               "sur 25 ans en sont calculés pour chaque option (prix de "
               "l'option, dégradation des panneaux, remplacement de "
               "l'onduleur)."),
        'en': ('Savings entered in the consumption study saved with this '
               'quote; the payback and the 25-year net gain are calculated '
               "from them for each option (option price, panel degradation, "
               'inverter replacement).'),
        'ar': ('وفورات مُدخلة في دراسة الاستهلاك المسجلة مع هذا العرض؛ ومنها '
               'تُحسب مدة الاسترداد وصافي الربح على 25 سنة لكل خيار (سعر '
               'الخيار، تراجع مردود الألواح، استبدال العاكس).')},
    'res_methode_etude': {
        'fr': ("Économies issues de l'étude de consommation enregistrée avec "
               'ce devis (production et économies calculées sur votre profil '
               'réel).'),
        'en': ('Savings taken from the consumption study saved with this '
               'quote (production and savings calculated on your actual '
               'profile).'),
        'ar': ('وفورات مستمدة من دراسة الاستهلاك المسجلة مع هذا العرض (الإنتاج '
               'والوفورات محسوبان على ملفكم الفعلي).')},
    'res_methode_estimation': {
        'fr': ('Estimation : production annuelle × part autoconsommée × tarif '
               "kWh (loi 82-21 : seul l'autoconsommé est valorisé — détail "
               'dans nos hypothèses). Fournissez une facture réelle pour un '
               'calcul par tranche exact.'),
        'en': ('Estimate: annual production × self-consumed share × kWh '
               'tariff (law 82-21: only self-consumption is valued — details '
               'in our assumptions). Provide a real bill for an exact '
               'band-by-band calculation.'),
        'ar': ('تقدير: الإنتاج السنوي × الحصة المستهلكة ذاتياً × تعريفة kWh '
               '(القانون 82-21: لا يُثمَّن إلا الاستهلاك الذاتي — التفاصيل في '
               'فرضياتنا). قدموا فاتورة حقيقية لحساب دقيق حسب الشرائح.')},
    'res_methode_exemple': {
        'fr': ('Facture actuelle ≈ {a} MAD/an → avec solaire ≈ {b} MAD/an → '
               'économie ≈ {c} MAD/an'),
        'en': ('Current bill ≈ {a} MAD/yr → with solar ≈ {b} MAD/yr → '
               'savings ≈ {c} MAD/yr'),
        'ar': ('الفاتورة الحالية ≈ {a} درهم/سنة ← مع الطاقة الشمسية ≈ {b} '
               'درهم/سنة ← الوفورات ≈ {c} درهم/سنة')},
    'res_approximatif': {'fr': ' (approximatif)', 'en': ' (approximate)',
                         'ar': ' (تقريبي)'},
    'res_votre_conseiller': {'fr': 'Votre conseiller', 'en': 'Your advisor',
                             'ar': 'مستشاركم'},
    'res_note': {'fr': 'Note', 'en': 'Note', 'ar': 'ملاحظة'},
    'res_delai_sous': {'fr': 'sous {delai} (indicatif)',
                       'en': 'within {delai} (indicative)',
                       'ar': 'خلال {delai} (إرشادي)'},
    'res_delai_indicatif': {'fr': '{delai} (indicatif)',
                            'en': '{delai} (indicative)',
                            'ar': '{delai} (إرشادي)'},
    'res_recommande_min': {'fr': 'recommandé', 'en': 'recommended',
                           'ar': 'موصى به'},
    'res_virement': {'fr': 'Virement bancaire&nbsp;:', 'en': 'Bank transfer:',
                     'ar': 'تحويل بنكي:'},
    'res_le_client': {'fr': 'Le client', 'en': 'The client', 'ar': 'العميل'},
    'res_estimations_nc': {
        'fr': ('Estimations non contractuelles —\n    hypothèses de calcul '
               'détaillées sur votre proposition en ligne.'),
        'en': ('Non-contractual estimates — detailed calculation assumptions '
               'in your online proposal.'),
        'ar': 'تقديرات غير تعاقدية — فرضيات الحساب مفصلة في عرضكم على الإنترنت.'},
    'res_page': {'fr': 'Page', 'en': 'Page', 'ar': 'صفحة'},
    # Une-page legacy (préfixe ``op_``) : lignes tronquées, note batterie.
    'op_lignes_tronquees_1': {
        'fr': ('&#8230; et {n} autre ligne d&#8217;&#233;quipement &#8212; '
               'incluse dans les totaux ci-dessous, d&#233;tail complet sur '
               '{renvoi}.'),
        'en': ('&#8230; and {n} more equipment line &#8212; included in the '
               'totals below, full detail in {renvoi}.'),
        'ar': ('&#8230; و{n} سطر معدات آخر &#8212; مدرج في المجاميع أدناه، '
               'والتفاصيل الكاملة في {renvoi}.')},
    'op_lignes_tronquees_n': {
        'fr': ('&#8230; et {n} autres lignes d&#8217;&#233;quipement &#8212; '
               'incluses dans les totaux ci-dessous, d&#233;tail complet sur '
               '{renvoi}.'),
        'en': ('&#8230; and {n} more equipment lines &#8212; included in the '
               'totals below, full detail in {renvoi}.'),
        'ar': ('&#8230; و{n} أسطر معدات أخرى &#8212; مدرجة في المجاميع أدناه، '
               'والتفاصيل الكاملة في {renvoi}.')},
    'op_renvoi_multipages': {'fr': 'le devis multi-pages',
                             'en': 'the multi-page quote',
                             'ar': 'عرض السعر متعدد الصفحات'},
    'op_renvoi_agricole': {'fr': 'le document complet (3 pages)',
                           'en': 'the full document (3 pages)',
                           'ar': 'الوثيقة الكاملة (3 صفحات)'},
    'op_note_batterie': {
        'fr': ('Ce document chiffre l&#8217;option {ceci}. Une option {autre} '
               'est disponible &#8212; voir la proposition compl&#232;te.'),
        'en': ('This document prices the option {ceci}. An option {autre} is '
               'also available &#8212; see the full proposal.'),
        'ar': ('تحدد هذه الوثيقة سعر الخيار {ceci}. يتوفر خيار {autre} '
               '&#8212; انظروا العرض الكامل.')},
    # Jalons des CGV C&I (marqueur ``{echeancier}``, préfixe ``cgv_``) : le
    # français est ``apps.ventes.utils.echeancier.TRANCHE_LABELS`` mot pour
    # mot ; un libellé renommé par la société reste tel quel.
    'cgv_jalon_acompte': {'fr': 'Acompte', 'en': 'Down payment',
                          'ar': 'الدفعة المقدمة'},
    'cgv_jalon_materiel': {'fr': 'Livraison du matériel',
                           'en': 'Equipment delivery', 'ar': 'تسليم المعدات'},
    'cgv_jalon_solde': {'fr': 'Solde', 'en': 'Balance', 'ar': 'الرصيد'},
    'cgv_jalon_commande': {'fr': 'Commande', 'en': 'Order', 'ar': 'الطلب'},
    'cgv_jalon_livraison_materiel': {'fr': 'Livraison du matériel',
                                     'en': 'Equipment delivery',
                                     'ar': 'تسليم المعدات'},
    'cgv_jalon_mise_en_service': {'fr': 'Mise en service',
                                  'en': 'Commissioning', 'ar': 'التشغيل'},
    'cgv_jalon_reception_definitive': {'fr': 'Réception définitive',
                                       'en': 'Final acceptance',
                                       'ar': 'الاستلام النهائي'},
    'cgv_jalon_reception_financeur': {
        'fr': "Règlement par l'organisme financeur à la réception signée",
        'en': 'Payment by the financing body on signed acceptance',
        'ar': 'أداء من طرف الجهة الممولة عند الاستلام الموقّع'},
    'cgv_jalon_liberation_retenue': {
        'fr': 'Libération de la retenue de garantie',
        'en': 'Release of the retention',
        'ar': 'تحرير اقتطاع الضمان'},
    'cgv_jalon_format': {'fr': '{libelle} : {valeur} {unite}',
                         'en': '{libelle}: {valeur} {unite}',
                         'ar': '{libelle}: {valeur} {unite}'},
    'cgv_mad_ttc': {'fr': 'MAD TTC', 'en': 'MAD incl. VAT',
                    'ar': 'درهم شامل الضريبة'},
    'cgv_retenue': {
        'fr': ('retenue de garantie de {taux} %, libérée à la réception '
               'définitive'),
        'en': 'retention of {taux} %, released on final acceptance',
        'ar': 'اقتطاع ضمان بنسبة {taux} %، يُحرَّر عند الاستلام النهائي'},
    # ── AMOT52 (D-AMOT-1 = a) — moteur LEGACY plein format (pages 1 à annexe) ─
    # Préfixe ``lg_`` : le français est le littéral EXACT du gabarit
    # (entités, espaces insécables et sauts de ligne compris) ; en / ar
    # reçoivent les MÊMES ``{…}`` que le français.
    'lg_hero_l1': {'fr': 'Installation solaire photovolta&#239;que', 'en': 'Solar photovoltaic installation',
                   'ar': 'منظومة طاقة شمسية كهروضوئية'},
    'lg_hero_l2': {'fr': 'Proposition commerciale &#8212; Confidentiel',
                   'en': 'Commercial proposal &#8212; Confidential', 'ar': 'عرض تجاري &#8212; سري'},
    'lg_proposition_commerciale': {'fr': 'PROPOSITION COMMERCIALE', 'en': 'COMMERCIAL PROPOSAL',
                                   'ar': 'عرض تجاري'},
    'lg_titre_hero': {'fr': 'Installation<br>Solaire', 'en': 'Solar<br>Installation', 'ar': 'منظومة<br>شمسية'},
    'lg_reference_devis': {'fr': 'R&#233;f&#233;rence devis', 'en': 'Quote reference', 'ar': 'مرجع العرض'},
    'lg_type_commerciale': {'fr': 'Commerciale', 'en': 'Commercial', 'ar': 'تجارية'},
    'lg_type_agricole': {'fr': 'Agricole', 'en': 'Agricultural', 'ar': 'فلاحية'},
    'lg_kpi_puissance': {'fr': 'Puissance Install&#233;e', 'en': 'Installed Power', 'ar': 'القدرة المركبة'},
    'lg_kpi_production': {'fr': 'Production Annuelle', 'en': 'Annual Production', 'ar': 'الإنتاج السنوي'},
    'lg_energie_propre_an': {'fr': '&#233;nergie propre / an', 'en': 'clean energy / year',
                             'ar': 'طاقة نظيفة / سنة'},
    'lg_energie_propre_an_sa': {'fr': '&#233;nergie propre / an (sans &#183; avec)',
                                'en': 'clean energy / year (without &#183; with)',
                                'ar': 'طاقة نظيفة / سنة (بدون &#183; مع)'},
    'lg_n_panneaux_w': {'fr': '{n} panneaux &#215; {w}&nbsp;W', 'en': '{n} panels &#215; {w}&nbsp;W',
                        'ar': '{n} ألواح &#215; {w}&nbsp;W'},
    'lg_n_panneaux': {'fr': '{n} panneaux', 'en': '{n} panels', 'ar': '{n} ألواح'},
    'lg_n_panneaux_sa': {'fr': '{s} &#183; {a} panneaux (sans &#183; avec)',
                         'en': '{s} &#183; {a} panels (without &#183; with)',
                         'ar': '{s} &#183; {a} ألواح (بدون &#183; مع)'},
    'lg_par_an': {'fr': '/an', 'en': '/yr', 'ar': '/سنة'},
    'lg_eco_estimee': {'fr': '&#201;conomie estim&#233;e&#160;: ', 'en': 'Estimated savings: ',
                       'ar': 'التوفير المقدر: '},
    'lg_mt_note': {
        'fr': ('Raccordement MOYENNE TENSION&#160;: les &#233;conomies et le retour sur investissement seront '
               'chiffr&#233;s sur le bar&#232;me MT, jamais au bar&#232;me basse tension.'),
        'en': ('MEDIUM VOLTAGE connection: savings and payback will be calculated on the MV tariff, never on '
               'the low-voltage tariff.'),
        'ar': ('ربط بالجهد المتوسط: سيُحتسب التوفير وعائد الاستثمار وفق تعريفة الجهد المتوسط، وليس أبدًا وفق '
               'تعريفة الجهد المنخفض.')},
    'lg_retour_en': {'fr': 'Retour en {n} ans', 'en': 'Payback in {n} years', 'ar': 'استرداد خلال {n} سنوات'},
    'lg_recommande_maj': {'fr': 'RECOMMANDÉ', 'en': 'RECOMMENDED', 'ar': 'موصى به'},
    'lg_remise_maj': {'fr': 'REMISE', 'en': 'DISCOUNT', 'ar': 'خصم'},
    'lg_soit_kwc': {'fr': ' &#183; soit {prix}/kWc', 'en': ' &#183; i.e. {prix}/kWc', 'ar': ' &#183; أي {prix}/kWc'},
    'lg_eq_detaille_p2': {'fr': 'Équipement détaillé en page 2', 'en': 'Equipment detailed on page 2',
                          'ar': 'تفاصيل المعدات في الصفحة 2'},
    'lg_chiffrees_mt': {'fr': 'chiffr&#233;es sur bar&#232;me MT', 'en': 'calculated on the MV tariff',
                        'ar': 'محتسبة وفق تعريفة الجهد المتوسط'},
    'lg_eco_par_an': {'fr': '&#233;conomies par an{est}', 'en': 'savings per year{est}', 'ar': 'توفير سنوي{est}'},
    'lg_selon_option': {'fr': 'selon option choisie{est}', 'en': 'depending on the chosen option{est}',
                        'ar': 'حسب الخيار المختار{est}'},
    'lg_pill_productible': {
        'fr': '&#8776;&#160;{n}&#160;kWh par kWc et par an &#224; {ville} {suffixe}',
        'en': '&#8776;&#160;{n}&#160;kWh per kWc per year in {ville} {suffixe}',
        'ar': '&#8776;&#160;{n}&#160;kWh لكل kWc سنويًا في {ville} {suffixe}'},
    'lg_donnee_pvgis': {'fr': '(donn&#233;e PVGIS)', 'en': '(PVGIS data)', 'ar': '(بيانات PVGIS)'},
    'lg_donnee_pvgis_ref': {
        'fr': '(donn&#233;e PVGIS &#8212; ville de r&#233;f&#233;rence la plus proche)',
        'en': '(PVGIS data &#8212; nearest reference city)', 'ar': '(بيانات PVGIS &#8212; أقرب مدينة مرجعية)'},
    'lg_vos_options': {'fr': 'Vos Options d&#8217;Installation', 'en': 'Your Installation Options',
                       'ar': 'خيارات التركيب الخاصة بكم'},
    'lg_autoconso_directe': {'fr': 'Autoconsommation directe', 'en': 'Direct self-consumption',
                             'ar': 'استهلاك ذاتي مباشر'},
    'lg_sous_titre_hybride': {'fr': 'Onduleur hybride &#8212; batterie ajoutable',
                              'en': 'Hybrid inverter &#8212; battery can be added',
                              'ar': 'عاكس هجين &#8212; يمكن إضافة بطارية'},
    'lg_sous_titre_stockage': {'fr': 'Stockage + autonomie nocturne', 'en': 'Storage + night-time autonomy',
                               'ar': 'تخزين + استقلالية ليلية'},
    'lg_prix_total_ttc': {'fr': 'Prix total TTC', 'en': 'Total price incl. VAT', 'ar': 'السعر الإجمالي شامل الضريبة'},
    'lg_prix_onee_hausse': {'fr': 'Prix ONEE en hausse', 'en': 'Rising ONEE prices', 'ar': 'أسعار ONEE في ارتفاع'},
    'lg_energie_propre': {'fr': '&#201;nergie propre', 'en': 'Clean energy', 'ar': 'طاقة نظيفة'},
    'lg_etape_devis': {'fr': 'Devis', 'en': 'Quote', 'ar': 'العرض'},
    'lg_etape_visite': {'fr': 'Visite', 'en': 'Visit', 'ar': 'الزيارة'},
    'lg_ref': {'fr': 'Réf.', 'en': 'Ref.', 'ar': 'المرجع'},
    'lg_mis_a_jour_le': {'fr': 'Document mis &#224; jour le {date}', 'en': 'Document updated on {date}',
                         'ar': 'تم تحديث المستند في {date}'},
    'lg_remplace_devis': {'fr': 'Remplace le devis {ref}', 'en': 'Replaces quote {ref}',
                          'ar': 'يحل محل العرض {ref}'},
    'lg_votre_conseiller': {'fr': 'Votre conseiller&#160;: {nom}', 'en': 'Your advisor: {nom}',
                            'ar': 'مستشاركم: {nom}'},
    'lg_methode_titre': {'fr': 'Comment nous calculons vos &#233;conomies', 'en': 'How we calculate your savings',
                         'ar': 'كيف نحتسب توفيركم'},
    'lg_eco_estimees_confirmer': {
        'fr': 'Économies estimées{approx} — à confirmer sur vos factures.',
        'en': 'Estimated savings{approx} — to be confirmed on your bills.',
        'ar': 'التوفير المقدر{approx} — يُؤكَّد على فواتيركم.'},
    'lg_multi_total': {
        'fr': ' &#8212; total pour {n} propriétés&#160;: <b>{montant}</b>',
        'en': ' &#8212; total for {n} properties: <b>{montant}</b>',
        'ar': ' &#8212; المجموع لـ {n} عقارات: <b>{montant}</b>'},
    'lg_multi_identiques': {'fr': '&#215;&#160;{n} propriétés identiques{total}',
                            'en': '&#215;&#160;{n} identical properties{total}',
                            'ar': '&#215;&#160;{n} عقارات متطابقة{total}'},
    'lg_options_proposees': {'fr': 'Options propos&#233;es (non incluses dans le total)',
                             'en': 'Proposed options (not included in the total)',
                             'ar': 'خيارات مقترحة (غير مدرجة في المجموع)'},
    'lg_activez_option': {
        'fr': 'Activez une option avant signature pour l&#8217;inclure &#224; votre devis.',
        'en': 'Activate an option before signing to include it in your quote.',
        'ar': 'فعّلوا خيارًا قبل التوقيع لإدراجه في عرضكم.'},
    'lg_p2_titre': {'fr': 'Détail des équipements &amp; Analyse financière',
                    'en': 'Equipment details &amp; Financial analysis', 'ar': 'تفاصيل المعدات والتحليل المالي'},
    'lg_devis_n_nbsp': {'fr': 'Devis N°\xa0{ref}', 'en': 'Quote No.\xa0{ref}', 'ar': 'عرض رقم\xa0{ref}'},
    'lg_th_designation': {'fr': 'Désignation', 'en': 'Description', 'ar': 'البيان'},
    'lg_th_garantie': {'fr': 'Garantie', 'en': 'Warranty', 'ar': 'الضمان'},
    'lg_th_qte': {'fr': 'Qté', 'en': 'Qty', 'ar': 'الكمية'},
    'lg_th_spec': {'fr': 'Spécification', 'en': 'Specification', 'ar': 'المواصفة'},
    'lg_gain_cumule_titre': {
        'fr': 'Gain cumulé sur 25 ans — Point de retour sur investissement',
        'en': 'Cumulative gain over 25 years — Payback point',
        'ar': 'الربح التراكمي على 25 سنة — نقطة استرداد الاستثمار'},
    'lg_eco_mensuelles': {'fr': 'Économies mensuelles estimées (MAD\xa0/\xa0mois)',
                          'en': 'Estimated monthly savings (MAD\xa0/\xa0month)',
                          'ar': 'التوفير الشهري المقدر (MAD\xa0/\xa0شهر)'},
    'lg_facture_vs_eco': {'fr': 'Facture ONEE vs &#233;conomies solaires par mois',
                          'en': 'ONEE bill vs solar savings per month',
                          'ar': 'فاتورة ONEE مقابل التوفير الشمسي شهريًا'},
    'lg_eco_solaires_mois': {'fr': '&#201;conomies solaires par mois', 'en': 'Solar savings per month',
                             'ar': 'التوفير الشمسي شهريًا'},
    'lg_remise_pct': {'fr': 'Remise ({pct} %)', 'en': 'Discount ({pct} %)', 'ar': 'خصم ({pct} %)'},
    'lg_tva_pct': {'fr': 'TVA ({r} %)', 'en': 'VAT ({r} %)', 'ar': 'ض.ق.م ({r} %)'},
    'lg_note_remise': {
        'fr': 'Remise de {pct} % appliquée sur chaque ligne — prix catalogue barrés, totaux après remise.',
        'en': '{pct} % discount applied to each line — list prices struck through, totals after discount.',
        'ar': 'خصم {pct} % مطبق على كل سطر — أسعار الكتالوج مشطوبة، والمجاميع بعد الخصم.'},
    'lg_ans_maj': {'fr': 'ANS', 'en': 'YEARS', 'ar': 'سنوات'},
    'lg_gar_onduleur': {'fr': 'Onduleur', 'en': 'Inverter', 'ar': 'العاكس'},
    'lg_gar_panneaux_produit': {'fr': 'Panneaux (produit)', 'en': 'Panels (product)', 'ar': 'الألواح (المنتج)'},
    'lg_gar_performance': {'fr': 'Performance panneau', 'en': 'Panel performance', 'ar': 'أداء الألواح'},
    'lg_gar_batterie': {'fr': 'Batterie', 'en': 'Battery', 'ar': 'البطارية'},
    'lg_garanties_jusqu': {'fr': 'Garanties jusqu&#8217;&#224; {n} ans', 'en': 'Warranties up to {n} years',
                           'ar': 'ضمانات تصل إلى {n} سنوات'},
    'lg_gar_ligne': {'fr': '{lbl} {n} ans', 'en': '{lbl} {n} years', 'ar': '{lbl} {n} سنوات'},
    'lg_garanties_fabricant': {
        'fr': ('Garanties fabricant des produits install&#233;s, telles que d&#233;taill&#233;es sur leurs '
               'fiches techniques.'),
        'en': 'Manufacturer warranties for the installed products, as detailed in their datasheets.',
        'ar': 'ضمانات المصنّع للمنتجات المركبة، كما هي مفصلة في بطاقاتها التقنية.'},
    'lg_eq_panneaux': {'fr': 'Panneaux {m}', 'en': '{m} panels', 'ar': 'ألواح {m}'},
    'lg_eq_onduleurs': {'fr': 'onduleurs {m}', 'en': '{m} inverters', 'ar': 'عاكسات {m}'},
    'lg_eq_batterie': {'fr': 'batterie {m}', 'en': '{m} battery', 'ar': 'بطارية {m}'},
    'lg_eq_titre': {'fr': 'Équipements de votre installation', 'en': 'Your installation equipment',
                    'ar': 'معدات منظومتكم'},
    'lg_eq_garantie': {'fr': ' — avec la garantie fabricant de chaque produit.',
                       'en': ' — with the manufacturer warranty of each product.',
                       'ar': ' — مع ضمان المصنّع لكل منتج.'},
    'lg_monitoring_texte': {
        'fr': ('Supervision de la production, des économies et de l’état de votre installation, via le '
               'matériel de communication chiffré au devis.'),
        'en': ('Monitoring of production, savings and the status of your installation, through the '
               'communication equipment priced in the quote.'),
        'ar': 'مراقبة الإنتاج والتوفير وحالة منظومتكم، عبر معدات الاتصال المسعّرة في العرض.'},
    'lg_delai_sous': {'fr': 'Sous {delai} (indicatif)', 'en': 'Within {delai} (indicative)',
                      'ar': 'خلال {delai} (إرشادي)'},
    'lg_option_choisie': {'fr': 'Option choisie par le client', 'en': 'Option chosen by the client',
                          'ar': 'الخيار الذي اختاره العميل'},
    'lg_option1_reseau': {'fr': 'Option 1 &#8212; R&#233;seau uniquement', 'en': 'Option 1 &#8212; Grid only',
                          'ar': 'الخيار 1 &#8212; الشبكة فقط'},
    'lg_option2_compo': {'fr': 'Option 2 &#8212; {compo}', 'en': 'Option 2 &#8212; {compo}',
                         'ar': 'الخيار 2 &#8212; {compo}'},
    'lg_compo_hybride': {'fr': 'Hybride', 'en': 'Hybrid', 'ar': 'هجين'},
    'lg_compo_stockage': {'fr': 'R&#233;seau + Stockage', 'en': 'Grid + Storage', 'ar': 'الشبكة + التخزين'},
    'lg_confirmation_commande': {'fr': 'Confirmation de la commande', 'en': 'Order confirmation',
                                 'ar': 'تأكيد الطلبية'},
    'lg_systeme_pv': {'fr': 'Syst&#232;me photovolta&#239;que{kwc} &#8212; ', 'en': 'Photovoltaic system{kwc} &#8212; ',
                      'ar': 'نظام كهروضوئي{kwc} &#8212; '},
    'lg_je_confirme': {'fr': 'Je confirme la commande du syst&#232;me d&#233;crit dans ce devis',
                       'en': 'I confirm the order of the system described in this quote',
                       'ar': 'أؤكد طلب النظام الموصوف في هذا العرض'},
    'lg_pay_acompte': {'fr': 'Acompte · À la signature', 'en': 'Down payment · On signature',
                       'ar': 'دفعة مقدمة · عند التوقيع'},
    'lg_pay_materiel': {'fr': 'Matériel · Avant installation', 'en': 'Equipment · Before installation',
                        'ar': 'المعدات · قبل التركيب'},
    'lg_pay_solde': {'fr': 'Solde · Après installation', 'en': 'Balance · After installation',
                     'ar': 'الرصيد · بعد التركيب'},
    'lg_pay_solde_livraison': {'fr': 'Solde · À la livraison', 'en': 'Balance · On delivery',
                               'ar': 'الرصيد · عند التسليم'},
    'lg_modalites_paiement': {'fr': 'Modalités de paiement', 'en': 'Payment terms', 'ar': 'طرق الأداء'},
    'lg_pay_note': {
        'fr': '* La réception du matériel et le solde s’appliquent même si réalisés le même jour.',
        'en': '* Equipment delivery and the balance apply even if they take place on the same day.',
        'ar': '* يُطبَّق استلام المعدات والرصيد حتى لو تمّا في اليوم نفسه.'},
    'lg_virement': {'fr': 'Virement bancaire\xa0: ', 'en': 'Bank transfer: ', 'ar': 'تحويل بنكي: '},
    'lg_ingenieurs': {'fr': 'Ingénieurs spécialisés', 'en': 'Specialised engineers', 'ar': 'مهندسون متخصصون'},
    'lg_ingenieurs_texte': {
        'fr': ('Installation conforme aux normes marocaines et internationales, réalisée par des techniciens '
               'certifiés.'),
        'en': ('Installation compliant with Moroccan and international standards, carried out by certified '
               'technicians.'),
        'ar': 'تركيب مطابق للمعايير المغربية والدولية، ينجزه تقنيون معتمدون.'},
    'lg_engagement_titre': {'fr': 'Notre Engagement', 'en': 'Our Commitment', 'ar': 'التزامنا'},
    'lg_engagement_texte': {
        'fr': ('Notre équipe reste à votre disposition pour toute question.<br>\n'
               '      Nous planifierons l&#8217;installation dès validation du devis.'),
        'en': ('Our team remains at your disposal for any question.<br>\n'
               '      We will schedule the installation as soon as the quote is approved.'),
        'ar': 'يبقى فريقنا رهن إشارتكم لأي سؤال.<br>\n      سنبرمج التركيب فور المصادقة على العرض.'},
    'lg_prochaines_etapes': {'fr': 'PROCHAINES ÉTAPES', 'en': 'NEXT STEPS', 'ar': 'الخطوات التالية'},
    'lg_plus_acompte': {'fr': '+ acompte {pct}&#37;', 'en': '+ {pct}&#37; down payment',
                        'ar': '+ دفعة مقدمة {pct}&#37;'},
    'lg_tests_formation': {'fr': 'Tests + formation', 'en': 'Tests + training', 'ar': 'اختبارات + تكوين'},
    'lg_signature_client': {'fr': 'Signature du client', 'en': 'Client signature', 'ar': 'توقيع العميل'},
    'lg_nom': {'fr': 'Nom&#160;:', 'en': 'Name:', 'ar': 'الاسم:'},
    'lg_date_ligne': {'fr': 'Date&#160;: _______________', 'en': 'Date: _______________',
                      'ar': 'التاريخ: _______________'},
    'lg_signature_marque': {'fr': 'Signature {marque}', 'en': 'Signature {marque}', 'ar': 'توقيع {marque}'},
    'lg_representant': {'fr': 'Représentant&#160;:', 'en': 'Representative:', 'ar': 'الممثل:'},
    'lg_cachet_societe': {'fr': 'Cachet et signature de la société', 'en': 'Company stamp and signature',
                          'ar': 'ختم وتوقيع الشركة'},
    'lg_accepte_le': {'fr': 'Accepté le {date} par {nom}', 'en': 'Accepted on {date} by {nom}',
                      'ar': 'تم القبول بتاريخ {date} من طرف {nom}'},
    'lg_puissance_crete': {'fr': 'Puissance crête', 'en': 'Peak power', 'ar': 'القدرة القصوى'},
    'lg_conso_annuelle': {'fr': 'Consommation annuelle', 'en': 'Annual consumption', 'ar': 'الاستهلاك السنوي'},
    'lg_taux_autoconso': {'fr': "Taux d'autoconsommation", 'en': 'Self-consumption rate',
                          'ar': 'نسبة الاستهلاك الذاتي'},
    'lg_taux_couverture': {'fr': 'Taux de couverture', 'en': 'Coverage rate', 'ar': 'نسبة التغطية'},
    'lg_eco_annuelles': {'fr': 'Économies annuelles', 'en': 'Annual savings', 'ar': 'التوفير السنوي'},
    'lg_unite_ans': {'fr': '\xa0ans', 'en': '\xa0years', 'ar': '\xa0سنوات'},
    'lg_rates_note': {
        'fr': ("* Taux d'autoconsommation : part de la production solaire consommée sur site. Taux de "
               "couverture : part de la consommation totale couverte par le solaire. "),
        'en': ('* Self-consumption rate: share of solar production consumed on site. Coverage rate: share of '
               'total consumption covered by solar. '),
        'ar': ('* نسبة الاستهلاك الذاتي: حصة الإنتاج الشمسي المستهلكة في الموقع. نسبة التغطية: حصة الاستهلاك '
               'الإجمالي التي تغطيها الطاقة الشمسية. ')},
    'lg_kwh_mois': {'fr': '{n} kWh/mois', 'en': '{n} kWh/month', 'ar': '{n} kWh/شهر'},
    'lg_residuel_marche': {'fr': 'Résiduel sous la marche{branche}', 'en': 'Residual below the threshold{branche}',
                           'ar': 'المتبقي تحت العتبة{branche}'},
    'lg_tranche_actuelle': {'fr': 'Tranche actuelle', 'en': 'Current bracket', 'ar': 'الشطر الحالي'},
    'lg_batterie_remplit': {'fr': 'La batterie se remplit chaque jour', 'en': 'The battery fills up every day',
                            'ar': 'تمتلئ البطارية كل يوم'},
    'lg_remplissage': {'fr': 'Remplissage batterie (moyen){branche}', 'en': 'Battery filling (average){branche}',
                       'ar': 'امتلاء البطارية (المتوسط){branche}'},
    'lg_part_pointes': {'fr': 'Part des pointes rattrapée par la batterie{branche}',
                        'en': 'Share of peaks covered by the battery{branche}',
                        'ar': 'حصة الذروات التي تغطيها البطارية{branche}'},
    'lg_sous_marche': {'fr': ' sous la marche {t}', 'en': ' below the {t} threshold', 'ar': ' تحت عتبة {t}'},
    'lg_falaise_phrase': {
        'fr': ('Aujourd&rsquo;hui, votre facture se calcule sur la tranche {t}. Ce dimensionnement{branche} '
               'fait atterrir votre consommation résiduelle à {n} kWh/mois{sous}.'),
        'en': ('Today, your bill is calculated on the {t} bracket. This sizing{branche} brings your residual '
               'consumption down to {n} kWh/month{sous}.'),
        'ar': ('اليوم، تُحتسب فاتورتكم على الشطر {t}. هذا التحجيم{branche} ينزل باستهلاككم المتبقي إلى '
               '{n} kWh/شهر{sous}.')},
    'lg_branche_option': {'fr': ' &#8212; option {option}', 'en': ' &#8212; option {option}',
                          'ar': ' &#8212; خيار {option}'},
    'lg_branche_incise': {'fr': ' (option {option})', 'en': ' (option {option})', 'ar': ' (خيار {option})'},
    'lg_chart_etude': {'fr': 'Production PV vs consommation — mensuel', 'en': 'PV production vs consumption — monthly',
                       'ar': 'الإنتاج الكهروضوئي مقابل الاستهلاك — شهريًا'},
    'lg_etude_titre': {'fr': "Étude d'autoconsommation", 'en': 'Self-consumption study',
                       'ar': 'دراسة الاستهلاك الذاتي'},
    'lg_etude_pied': {'fr': 'Étude — Réf.\xa0{ref}', 'en': 'Study — Ref.\xa0{ref}', 'ar': 'الدراسة — المرجع\xa0{ref}'},
    'lg_estimations_nc': {'fr': 'Estimations non contractuelles.', 'en': 'Non-contractual estimates.',
                          'ar': 'تقديرات غير تعاقدية.'},
    'lg_methode_etude_ville': {
        'fr': ('Simulation établie sur le productible de {ville} et le profil de consommation communiqué. '
               'Mode\xa0: {mode}'),
        'en': 'Simulation based on the solar yield of {ville} and the consumption profile provided. Mode: {mode}',
        'ar': 'محاكاة مبنية على المردودية الشمسية لـ{ville} وعلى بيانات الاستهلاك المقدمة. النمط: {mode}'},
    'lg_methode_etude': {
        'fr': 'Simulation établie et le profil de consommation communiqué. Mode\xa0: {mode}',
        'en': 'Simulation based on the consumption profile provided. Mode: {mode}',
        'ar': 'محاكاة مبنية على بيانات الاستهلاك المقدمة. النمط: {mode}'},
    'lg_racc_tri': {'fr': 'raccordement triphasé', 'en': 'three-phase connection', 'ar': 'ربط ثلاثي الطور'},
    'lg_racc_mono': {'fr': 'raccordement monophasé', 'en': 'single-phase connection', 'ar': 'ربط أحادي الطور'},
    'lg_p50': {'fr': 'Production P50 (médiane)\xa0: <b>{v}\xa0kWh/an</b>',
               'en': 'P50 production (median): <b>{v}\xa0kWh/yr</b>',
               'ar': 'إنتاج P50 (الوسيط): <b>{v}\xa0kWh/سنة</b>'},
    'lg_p90': {'fr': 'P90 (retenue par les banques)\xa0: <b>{v}\xa0kWh/an</b>',
               'en': 'P90 (used by banks): <b>{v}\xa0kWh/yr</b>',
               'ar': 'P90 (المعتمد لدى البنوك): <b>{v}\xa0kWh/سنة</b>'},
    'lg_ratio_perf': {'fr': 'Ratio de performance\xa0: <b>{v}\xa0%</b>', 'en': 'Performance ratio: <b>{v}\xa0%</b>',
                      'ar': 'نسبة الأداء: <b>{v}\xa0%</b>'},
    'lg_poste_temperature': {'fr': 'Température', 'en': 'Temperature', 'ar': 'الحرارة'},
    'lg_poste_soiling': {'fr': 'Salissures', 'en': 'Soiling', 'ar': 'الاتساخ'},
    'lg_poste_shading': {'fr': 'Ombrage', 'en': 'Shading', 'ar': 'التظليل'},
    'lg_poste_wiring': {'fr': 'Câblage', 'en': 'Wiring', 'ar': 'الأسلاك'},
    'lg_poste_inverter': {'fr': 'Onduleur', 'en': 'Inverter', 'ar': 'العاكس'},
    'lg_poste_mismatch': {'fr': 'Dispersion modules', 'en': 'Module mismatch', 'ar': 'تباين الألواح'},
    'lg_poste_availability': {'fr': 'Disponibilité', 'en': 'Availability', 'ar': 'التوفر'},
    'lg_poste_lid': {'fr': 'LID (1re année)', 'en': 'LID (1st year)', 'ar': 'LID (السنة الأولى)'},
    'lg_poste_reflection': {'fr': 'Réflexion (IAM)', 'en': 'Reflection (IAM)', 'ar': 'الانعكاس (IAM)'},
    'lg_total_pct': {'fr': 'Total\xa0{v}\xa0%', 'en': 'Total\xa0{v}\xa0%', 'ar': 'المجموع\xa0{v}\xa0%'},
    'lg_cascade': {'fr': 'Cascade de pertes\xa0: ', 'en': 'Loss cascade: ', 'ar': 'تسلسل الخسائر: '},
    'lg_bancable_titre': {'fr': 'Étude bancable — productible et pertes', 'en': 'Bankable study — yield and losses',
                          'ar': 'دراسة قابلة للتمويل — المردودية والخسائر'},
    'lg_schema': {'fr': 'Schéma unifilaire', 'en': 'Single-line diagram', 'ar': 'المخطط أحادي الخط'},
    'lg_bom_reste_1': {
        'fr': '&#8230; et {n} autre composant &#8212; nomenclature compl&#232;te fournie avec le dossier technique.',
        'en': '&#8230; and {n} more component &#8212; full bill of materials provided with the technical file.',
        'ar': '&#8230; و{n} مكوّن آخر &#8212; القائمة الكاملة مرفقة بالملف التقني.'},
    'lg_bom_reste_n': {
        'fr': '&#8230; et {n} autres composants &#8212; nomenclature compl&#232;te fournie avec le dossier technique.',
        'en': '&#8230; and {n} more components &#8212; full bill of materials provided with the technical file.',
        'ar': '&#8230; و{n} مكونات أخرى &#8212; القائمة الكاملة مرفقة بالملف التقني.'},
    'lg_nomenclature': {'fr': 'Nomenclature électrique', 'en': 'Electrical bill of materials',
                        'ar': 'القائمة الكهربائية'},
    'lg_chaines': {'fr': '{n} chaîne(s)', 'en': '{n} string(s)', 'ar': '{n} سلسلة (سلاسل)'},
    'lg_triphase': {'fr': 'triphasé', 'en': 'three-phase', 'ar': 'ثلاثي الطور'},
    'lg_monophase': {'fr': 'monophasé', 'en': 'single-phase', 'ar': 'أحادي الطور'},
    'lg_regime': {'fr': 'régime {r}', 'en': 'earthing system {r}', 'ar': 'نظام التأريض {r}'},
    'lg_annexe_technique': {'fr': 'Annexe technique', 'en': 'Technical appendix', 'ar': 'الملحق التقني'},
    'lg_annexe_note': {
        'fr': ("Pièce technique jointe au dossier de raccordement. Les quantités de\n"
               "      l'annexe sont données à titre d'étude\xa0; seule la liste d'équipements du\n"
               "      devis fait foi commercialement."),
        'en': ('Technical document attached to the grid-connection file. The quantities in the\n'
               '      appendix are given for study purposes; only the equipment list of the\n'
               '      quote is commercially binding.'),
        'ar': ('وثيقة تقنية مرفقة بملف الربط بالشبكة. الكميات الواردة في الملحق\n'
               '      مقدمة على سبيل الدراسة؛ لائحة معدات العرض وحدها هي المعتمدة تجاريًا.')},
    'lg_annexe_pied': {'fr': 'Annexe technique — Réf.\xa0{ref}', 'en': 'Technical appendix — Ref.\xa0{ref}',
                       'ar': 'الملحق التقني — المرجع\xa0{ref}'},
    'lg_ret_titre': {'fr': 'Annexe — Droit de rétractation', 'en': 'Appendix — Right of withdrawal',
                     'ar': 'ملحق — حق التراجع'},
    'lg_ret_pied': {'fr': 'Rétractation — Réf. {ref}', 'en': 'Withdrawal — Ref. {ref}',
                    'ar': 'التراجع — المرجع {ref}'},
    'lg_calepinage': {'fr': 'Calepinage', 'en': 'Panel layout', 'ar': 'مخطط توزيع الألواح'},
    'lg_calep_intro': {
        'fr': ("Implantation des modules relevée sur la toiture, à l'échelle portée par\n"
               "      la planche. Les cotes sont mesurées sur la géométrie de la conception."),
        'en': ('Module layout surveyed on the roof, at the scale shown on\n'
               '      the drawing. Dimensions are measured on the design geometry.'),
        'ar': ('توزيع الألواح كما تم رفعه على السطح، بالمقياس المبيّن على\n'
               '      اللوحة. الأبعاد مقيسة على هندسة التصميم.')},
    'lg_calep_note': {
        'fr': ("Pièce technique jointe à la proposition. L'implantation définitive est\n"
               "      confirmée à la visite technique ; seule la liste d'équipements du devis\n"
               "      fait foi commercialement."),
        'en': ('Technical document attached to the proposal. The final layout is\n'
               '      confirmed at the technical visit; only the equipment list of the quote\n'
               '      is commercially binding.'),
        'ar': ('وثيقة تقنية مرفقة بالعرض. يُؤكَّد التوزيع النهائي\n'
               '      عند الزيارة التقنية؛ لائحة معدات العرض وحدها هي المعتمدة تجاريًا.')},
    'lg_calep_pied': {'fr': 'Calepinage — Réf. {ref}', 'en': 'Panel layout — Ref. {ref}',
                      'ar': 'مخطط توزيع الألواح — المرجع {ref}'},
    # AMOT52 — phrases « Nos hypothèses » du builder et de ``pricing`` : le
    # français est le texte EXACT servi ; ``residential.trust.hypothese_traduite``
    # le reconnaît (``{…}`` = valeur) et rend la langue du document.
    'res_hyp_titre': {'fr': 'Nos hypothèses', 'en': 'Our assumptions', 'ar': 'فرضياتنا'},
    'res_hyp_tarif_estime': {
        'fr': ('Tarif électricité : référence prudente (estimation) — transmettez une facture récente et '
               'nous recalculons vos économies par tranches, sur votre barème exact.'),
        'en': ('Electricity tariff: cautious reference (estimate) — send us a recent bill and we will '
               'recalculate your savings by bracket, on your exact tariff.'),
        'ar': ('تعريفة الكهرباء: مرجع حذر (تقدير) — أرسلوا لنا فاتورة حديثة وسنعيد احتساب توفيركم حسب '
               'الأشطر، وفق تعريفتكم الدقيقة.')},
    'res_hyp_tarif_retenu': {'fr': 'Tarif électricité retenu : {tarif} MAD/kWh ({distributeur})',
                             'en': 'Electricity tariff used: {tarif} MAD/kWh ({distributeur})',
                             'ar': 'تعريفة الكهرباء المعتمدة: {tarif} MAD/kWh ({distributeur})'},
    'res_hyp_tarif_saisi': {
        'fr': ('Tarif électricité : {tarif} MAD/kWh, saisi pour ce devis — un calcul par tranches sur facture '
               'réelle reste possible.'),
        'en': ('Electricity tariff: {tarif} MAD/kWh, entered for this quote — a bracket calculation on an '
               'actual bill remains possible.'),
        'ar': ('تعريفة الكهرباء: {tarif} MAD/kWh، مُدخلة لهذا العرض — يبقى الاحتساب حسب الأشطر على '
               'فاتورة فعلية ممكنًا.')},
    'res_hyp_bareme': {'fr': 'Tarif électricité : barème {distributeur} par tranche (barème national)',
                       'en': 'Electricity tariff: {distributeur} schedule by bracket (national schedule)',
                       'ar': 'تعريفة الكهرباء: جدول {distributeur} حسب الأشطر (الجدول الوطني)'},
    'res_hyp_revente_bt': {
        'fr': ("Revente du surplus non ouverte en basse tension à ce jour — ANRE décision 04/26 ; installation "
               "dimensionnée pour l'autoconsommation. Seuls les kWh autoconsommés réduisent la facture."),
        'en': ('Resale of surplus not yet open on low voltage — ANRE decision 04/26; installation sized for '
               'self-consumption. Only self-consumed kWh reduce the bill.'),
        'ar': ('بيع الفائض غير متاح بعد على الجهد المنخفض — قرار ANRE 04/26؛ المنظومة محجّمة للاستهلاك '
               'الذاتي. وحدها الكيلوواط ساعة المستهلكة ذاتيًا تخفض الفاتورة.')},
    'res_hyp_production': {
        'fr': 'Production estimée : ≈ {kwh} kWh par kWc et par an, pertes système de {pertes} % déduites.',
        'en': 'Estimated production: ≈ {kwh} kWh per kWc per year, system losses of {pertes} % deducted.',
        'ar': 'الإنتاج المقدر: ≈ {kwh} kWh لكل kWc سنويًا، بعد خصم خسائر النظام البالغة {pertes} %.'},
    'res_hyp_autoconso': {
        'fr': 'Autoconsommation retenue : {sans} % sans batterie · {avec} % avec batterie.',
        'en': 'Self-consumption used: {sans} % without battery · {avec} % with battery.',
        'ar': 'الاستهلاك الذاتي المعتمد: {sans} % بدون بطارية · {avec} % مع بطارية.'},
    'res_hyp_degradation': {
        'fr': ("Dégradation panneau {pct} %/an intégrée ; {tarif} ; coûts d'exploitation (nettoyage, "
               "maintenance, assurance) non déduits de ce résultat."),
        'en': ('Panel degradation of {pct} %/yr included; {tarif}; operating costs (cleaning, maintenance, '
               'insurance) not deducted from this result.'),
        'ar': ('تدهور الألواح {pct} %/سنة محتسب؛ {tarif}؛ تكاليف التشغيل (التنظيف، الصيانة، التأمين) غير '
               'مخصومة من هذه النتيجة.')},
    'res_hyp_tarif_constant': {
        'fr': ('aucune hausse du tarif électrique supposée — projection à tarif constant, toute hausse réelle '
               'améliore votre résultat'),
        'en': ('no electricity tariff increase assumed — projection at a constant tariff, any real increase '
               'improves your result'),
        'ar': 'لا يُفترض أي ارتفاع في تعريفة الكهرباء — إسقاط بتعريفة ثابتة، وكل ارتفاع فعلي يحسّن نتيجتكم'},
    'res_hyp_tarif_hausse': {'fr': 'hausse du tarif électrique supposée {pct} %/an',
                             'en': 'electricity tariff increase assumed at {pct} %/yr',
                             'ar': 'ارتفاع مفترض في تعريفة الكهرباء بنسبة {pct} %/سنة'},
    'res_hyp_stockage_publie': {
        'fr': ('Stockage : rendement aller-retour batterie {pct} % appliqué aux kWh qui transitent par la '
               'batterie (valeur publiée sur la fiche technique du produit chiffré).{omis}'),
        'en': ('Storage: battery round-trip efficiency of {pct} % applied to the kWh that pass through the '
               'battery (value published on the datasheet of the quoted product).{omis}'),
        'ar': ('التخزين: مردود الشحن والتفريغ للبطارية {pct} % مطبق على الكيلوواط ساعة التي تمر عبر '
               'البطارية (قيمة منشورة في البطاقة التقنية للمنتج المسعّر).{omis}')},
    'res_hyp_stockage_ref': {
        'fr': ('Stockage : rendement aller-retour batterie {pct} % appliqué aux kWh qui transitent par la '
               'batterie — hypothèse de référence, le constructeur de ce produit ne publie pas cette valeur '
               'dans notre fiche.{omis}'),
        'en': ('Storage: battery round-trip efficiency of {pct} % applied to the kWh that pass through the '
               'battery — reference assumption, the manufacturer of this product does not publish this value '
               'in our datasheet.{omis}'),
        'ar': ('التخزين: مردود الشحن والتفريغ للبطارية {pct} % مطبق على الكيلوواط ساعة التي تمر عبر '
               'البطارية — فرضية مرجعية، لا ينشر مصنّع هذا المنتج هذه القيمة في بطاقتنا.{omis}')},
    'res_hyp_batt_omis': {
        'fr': " Aucune perte de capacité ni remplacement de la batterie n'est provisionné sur les {ans} ans.",
        'en': ' No capacity loss or battery replacement is provisioned over the {ans} years.',
        'ar': ' لا يُرصد أي فقدان للسعة ولا استبدال للبطارية على مدى {ans} سنة.'},
    'res_hyp_provision': {
        'fr': ("Provision de remplacement de l'onduleur en année {an} : {montant} MAD (le prix de l'onduleur "
               "de ce devis) — c'est le palier visible sur la courbe de rentabilité."),
        'en': ('Inverter replacement provision in year {an}: {montant} MAD (the price of the inverter in this '
               'quote) — this is the step visible on the return curve.'),
        'ar': ('مخصص استبدال العاكس في السنة {an}: {montant} MAD (سعر العاكس في هذا العرض) — وهو '
               'الدرجة الظاهرة على منحنى المردودية.')},
    'res_hyp_sans_provision': {
        'fr': 'Projection établie hors provision de remplacement onduleur (aucun onduleur chiffré sur ce devis).',
        'en': 'Projection made without an inverter replacement provision (no inverter priced in this quote).',
        'ar': 'إسقاط دون مخصص لاستبدال العاكس (لا عاكس مسعّر في هذا العرض).'},
    'res_hyp_estimations_nc': {'fr': 'Estimations non contractuelles.', 'en': 'Non-contractual estimates.',
                               'ar': 'تقديرات غير تعاقدية.'},
    # AMOT52 — annexe de rétractation (``annexe_domicile``, loi 31-08), partagée
    # par le legacy et le résidentiel 3 pages : français = le littéral EXACT du
    # corps (sauts de ligne compris). Traduction à relire par le fondateur.
    'res_ret_kicker': {'fr': 'Annexe', 'en': 'Appendix', 'ar': 'ملحق'},
    'res_ret_titre': {'fr': 'Droit de rétractation', 'en': 'Right of withdrawal', 'ar': 'حق التراجع'},
    'res_ret_intro': {
        'fr': ("Cette commande a été signée à votre domicile. La loi\n"
               "      n° 31-08 édictant des mesures de protection du consommateur vous\n"
               "      ouvre un délai de rétractation de\n"
               "      <strong>{jours} jours</strong> à\n"
               "      compter de la commande. Pendant ce délai, <strong>aucun acompte ni\n"
               "      aucun paiement ne peut être exigé ni encaissé</strong>\n"
               "      (articles 49 et 50)."),
        'en': ('This order was signed at your home. Law No. 31-08 on consumer protection\n'
               '      gives you a withdrawal period of <strong>{jours} days</strong> from the order.\n'
               '      During this period, <strong>no down payment and no payment may be demanded\n'
               '      or collected</strong> (articles 49 and 50).'),
        'ar': ('وُقّعت هذه الطلبية بمنزلكم. يمنحكم القانون رقم 31.08 القاضي بتحديد تدابير لحماية\n'
               '      المستهلك أجلًا للتراجع مدته <strong>{jours} أيام</strong> ابتداءً من تاريخ الطلبية.\n'
               '      خلال هذا الأجل، <strong>لا يجوز المطالبة بأي دفعة مقدمة أو أي أداء ولا\n'
               '      استخلاصه</strong> (المادتان 49 و50).')},
    'res_ret_mentions_titre': {'fr': 'Mentions de l&#8217;article 48', 'en': 'Article 48 particulars',
                               'ar': 'بيانات المادة 48'},
    'res_ret_mention_1': {
        'fr': 'Nom et adresse du vendeur, et nom du représentant qui vous a rendu visite.',
        'en': 'Name and address of the seller, and name of the representative who visited you.',
        'ar': 'اسم البائع وعنوانه، واسم الممثل الذي زاركم.'},
    'res_ret_mention_2': {
        'fr': 'Désignation précise de la nature et des caractéristiques des biens ou services proposés.',
        'en': 'Precise description of the nature and characteristics of the goods or services offered.',
        'ar': 'التعيين الدقيق لطبيعة وخصائص السلع أو الخدمات المقترحة.'},
    'res_ret_mention_3': {
        'fr': 'Conditions d&#8217;exécution du contrat, notamment les modalités et le délai de livraison.',
        'en': 'Terms of performance of the contract, in particular the delivery arrangements and deadline.',
        'ar': 'شروط تنفيذ العقد، ولا سيما كيفيات التسليم وأجله.'},
    'res_ret_mention_4': {'fr': 'Prix global à payer et modalités de paiement.',
                          'en': 'Total price payable and payment terms.',
                          'ar': 'الثمن الإجمالي الواجب أداؤه وكيفيات الأداء.'},
    'res_ret_mention_5': {
        'fr': ('Faculté de renonciation, ainsi que ses conditions d&#8217;exercice, et de façon apparente le '
               'texte intégral des articles 49 et 50.'),
        'en': ('Right of withdrawal and the conditions for exercising it, and, conspicuously, the full text of '
               'articles 49 and 50.'),
        'ar': 'إمكانية التراجع وشروط ممارسته، مع النص الكامل للمادتين 49 و50 بشكل بارز.'},
    'res_ret_detachez': {
        'fr': ("Détachez, complétez et renvoyez le formulaire ci-dessous si vous\n"
               "      souhaitez renoncer à cette commande."),
        'en': ('Detach, complete and return the form below if you\n'
               '      wish to withdraw from this order.'),
        'ar': 'افصلوا الاستمارة أدناه واملؤوها وأعيدوها إذا رغبتم\n      في التراجع عن هذه الطلبية.'},
    'res_ret_formulaire': {'fr': 'Formulaire détachable de rétractation', 'en': 'Detachable withdrawal form',
                           'ar': 'استمارة التراجع القابلة للفصل'},
    'res_ret_formulaire_corps': {
        'fr': ("À l&#8217;attention de : <strong>{vendeur}</strong><br>\n"
               "        Je soussigné(e) : _______________________________________________<br>\n"
               "        Adresse : ____________________________________________________<br>\n"
               "        déclare renoncer à la commande n° <strong>{ref}</strong>,\n"
               "        signée le : ___/___/______<br>\n"
               "        Fait à : _______________________ le : ___/___/______"),
        'en': ('For the attention of: <strong>{vendeur}</strong><br>\n'
               '        I, the undersigned: _______________________________________________<br>\n'
               '        Address: ____________________________________________________<br>\n'
               '        hereby withdraw from order No. <strong>{ref}</strong>,\n'
               '        signed on: ___/___/______<br>\n'
               '        Done at: _______________________ on: ___/___/______'),
        'ar': ('إلى عناية: <strong>{vendeur}</strong><br>\n'
               '        أنا الموقع(ة) أدناه: _______________________________________________<br>\n'
               '        العنوان: ____________________________________________________<br>\n'
               '        أصرّح بالتراجع عن الطلبية رقم <strong>{ref}</strong>،\n'
               '        الموقعة بتاريخ: ___/___/______<br>\n'
               '        حُرّر في: _______________________ بتاريخ: ___/___/______')},
    'res_ret_signature': {'fr': 'Signature du client (de sa main)', 'en': 'Client signature (handwritten)',
                          'ar': 'توقيع العميل (بخط يده)'},
    # AMOT56 (D-AMOT-7 = a) — étiquette du m³/jour d'une pompe SANS courbe
    # dont le débit est déclaré (une-page et document agricole).
    'lg_debit_declare_par_vous': {'fr': 'débit déclaré par vous', 'en': 'flow rate declared by you',
                                  'ar': 'صبيب صرّحتم به'},
    # AMOT80 (D-ACI-8=a) — investissement non chiffré, base de la tuile
    # retour, coût moyen NON actualisé, argent servi sans motif client.
    'ci_invest_non_chiffre': {'fr': 'Investissement non encore chiffré',
                              'en': 'Investment not yet priced',
                              'ar': 'الاستثمار لم يُسعَّر بعد'},
    'ci_invest_non_chiffre_1': {
        'fr': 'Investissement non encore chiffré (1 article sans prix)',
        'en': 'Investment not yet priced (1 item without a price)',
        'ar': 'الاستثمار لم يُسعَّر بعد (بند واحد بدون سعر)'},
    'ci_invest_non_chiffre_n': {
        'fr': 'Investissement non encore chiffré ({n} articles sans prix)',
        'en': 'Investment not yet priced ({n} items without a price)',
        'ar': 'الاستثمار لم يُسعَّر بعد ({n} بنود بدون سعر)'},
    'ci_retour_estime_base': {'fr': 'Retour estimé ({base})',
                              'en': 'Estimated payback ({base})',
                              'ar': 'مدة الاسترداد المقدرة ({base})'},
    'ci_non_chiffre_sans_motif': {
        'fr': 'Économies et retour sur investissement non chiffrés à ce '
              'stade.',
        'en': 'Savings and payback not calculated at this stage.',
        'ar': 'لم تُحتسب الوفورات ومدة الاسترداد في هذه المرحلة.'},
    'ci_ind_motif_invest': {
        'fr': "<b>{motif}</b> : le retour, le TRI et le cashflow ne sont "
              "publiés que sur un investissement entièrement chiffré.",
        'en': '<b>{motif}</b>: payback, IRR and cash flow are only published '
              'on a fully priced investment.',
        'ar': '<b>{motif}</b>: لا تُنشر مدة الاسترداد ومعدل العائد الداخلي '
              'والتدفق النقدي إلا على استثمار مُسعَّر بالكامل.'},
    'ci_ind_lcoe_non_actualise': {
        'fr': 'Coût moyen non actualisé du kWh produit ({base})',
        'en': 'Average undiscounted cost of the kWh produced ({base})',
        'ar': 'متوسط التكلفة غير المحيَّنة للكيلوواط ساعة المنتج ({base})'},
    # AMOT80 — sources d'hypothèses INTERNES du moteur → mots du client
    # (table ``ci.couverture.SOURCES_CLIENT``).
    'ci_src_economie': {
        'fr': 'valorisation heure par heure au tarif de chaque poste',
        'en': 'hour-by-hour valuation at the rate of each time band',
        'ar': 'تقييم ساعة بساعة بسعر كل فترة'},
    'ci_src_production': {
        'fr': 'étude de production de votre site, heure par heure',
        'en': 'hour-by-hour production study of your site',
        'ar': 'دراسة إنتاج موقعكم ساعة بساعة'},
    'ci_src_horizon': {'fr': "durée d'analyse : 25 ans",
                       'en': 'analysis period: 25 years',
                       'ar': 'مدة التحليل: 25 سنة'},
    'ci_src_methode': {'fr': 'méthode de calcul du devis',
                       'en': 'quote calculation method',
                       'ar': 'طريقة حساب عرض السعر'},
    'ci_src_onduleur': {
        'fr': "remplacement à mi-vie (principe IEA PVPS), au montant réel de "
              "la ligne onduleur du devis",
        'en': 'mid-life replacement (IEA PVPS principle), at the actual '
              'amount of the quote inverter line',
        'ar': 'استبدال في منتصف العمر (مبدأ IEA PVPS)، بالمبلغ الفعلي لبند '
              'العاكس في عرض السعر'},
    # ── Pied de page ────────────────────────────────────────────────────────
    'reference': {
        'fr': 'R&#233;f.',
        'en': 'Ref.',
        'ar': 'المرجع',
    },
}


#: ERR-APDF-LIBELLES-FR-RESTANTS-EN-AR — noms d'option que le GABARIT
#: (« Sans batterie ») ou le builder (``libelle_avec``, BAT-DIFF) impriment →
#: clé du catalogue. Un nom saisi par la société n'y est pas : il reste tel
#: quel (donnée, jamais traduite par le moteur).
CLES_OPTION = {
    'Sans batterie': 'res_opt_sans',
    'Avec batterie': 'res_opt_avec',
    'Hybride, batterie plus tard': 'res_opt_hybride',
    # AMOT52 — types d'installation que le legacy imprime (``inst_type`` du
    # builder), traduits par la même fonction ``nom_option``.
    'Résidentielle': 'res_tag_residentielle',
    'Industrielle': 'ci_ind_tag',
    'Commerciale': 'lg_type_commerciale',
    'Agricole': 'lg_type_agricole',
}


def nom_option(nom, langue=None, minuscule=False) -> str:
    """Nom d'option ``nom`` dans ``langue`` (français : ``nom`` lui-même,
    octet pour octet) ; ``minuscule`` baisse la première lettre, comme les
    gabarits le faisaient au milieu d'une phrase (« option avec batterie »)."""
    cle = CLES_OPTION.get(nom)
    texte = libelle(cle, langue) if cle else str(nom or '')
    return texte[:1].lower() + texte[1:] if minuscule else texte


def normaliser(langue) -> str:
    """Langue de sortie utilisable : une des trois du cadre, sinon le FR.

    Défense en profondeur : une valeur inconnue venue d'un appelant (ou d'une
    charge utile bricolée) ne traverse jamais ce module autrement qu'en repli
    français.
    """
    return langue if langue in LANGUES else LANGUE_DE_REPLI


def libelle(cle: str, langue=None) -> str:
    """Libellé structurel ``cle`` dans ``langue`` (repli FR).

    Lève ``KeyError`` sur une clé absente du catalogue : le gabarit s'est
    trompé de nom, et cela doit casser au test — jamais imprimer un nom de
    variable ou un blanc sur un document client.
    """
    try:
        traductions = LIBELLES[cle]
    except KeyError:
        raise KeyError(
            f"i18n_labels: libellé inconnu {cle!r} — ajouter la clé au "
            f"catalogue (les trois langues) avant de l'appeler dans un gabarit"
        ) from None
    return traductions.get(normaliser(langue)) or traductions[LANGUE_DE_REPLI]


def libelles(langue=None) -> dict:
    """Toute la table résolue pour ``langue`` (chaque clé, repli FR appliqué).

    C'est la forme que le builder publie dans sa charge utile : le gabarit lit
    un dictionnaire plat, sans jamais refaire de résolution de langue.
    """
    active = normaliser(langue)
    return {cle: libelle(cle, active) for cle in LIBELLES}


def est_rtl(langue=None) -> bool:
    """Vrai si ``langue`` s'écrit de droite à gauche."""
    return normaliser(langue) in LANGUES_RTL


def direction(langue=None) -> str:
    """``'rtl'`` ou ``'ltr'`` — la valeur CSS/HTML ``dir`` du document."""
    return 'rtl' if est_rtl(langue) else 'ltr'
