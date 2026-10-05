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
    # ── Pied de page ────────────────────────────────────────────────────────
    'reference': {
        'fr': 'R&#233;f.',
        'en': 'Ref.',
        'ar': 'المرجع',
    },
}


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
