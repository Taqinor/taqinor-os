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
        'fr': "étude du moteur C&I à faire : chiffres préliminaires",
        'en': 'C&I study still to be run: preliminary figures',
        'ar': 'دراسة المحرك التجاري والصناعي لم تنجز بعد: أرقام أولية'},
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
    'ci_etape_installation_s': {
        'fr': 'Pose des équipements par nos équipes, sans interrompre votre '
              'activité.',
        'en': 'Equipment installed by our teams, without interrupting your '
              'business.',
        'ar': 'تركيب المعدات من طرف فرقنا دون توقيف نشاطكم.'},
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
        'ar': 'متوسط ثمن الكيلوواط ساعة الذي تتجنبونه: {tarif} درهم/kWh'},
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
