"""Textes PAR DÉFAUT des quatre actes, en arabe — la traduction qui accompagne
l'acte français (loi n° 31-08, art. 206). Jumeau de ``textes.py`` : mêmes
fonctions publiques, mêmes signatures, mêmes ``cle`` d'article, mêmes
conditions sur ``options``, mêmes repères ``{…}`` — sauf ``{total_lettres}`` et
``{exigible_lettres}`` : le montant en lettres n'est pas imprimé en arabe
(aucun convertisseur vérifié, décision de Reda du 24/11/2026), les phrases se
lisent sans lui.

Règles de traduction : arabe standard des actes juridiques et administratifs
marocains ; chaque phrase française a sa phrase arabe, rien d'ajouté, rien
d'adouci ni de durci ; les marqueurs ``**gras**`` encadrent les mêmes mots ; les
puces commencent par « - ». Jamais traduits ni translittérés : nom de la
société, noms des clients, désignations et marques, références, identifiants,
courriel, téléphone. Chiffres occidentaux partout (usage marocain). À faire
relire par un arabophone avant un usage réel.

Lexique (tenu partout, le même que ``rendu/libelles.py``) :

    le Client ......................... الزبون
    devis ............................. عرض الأثمان
    acompte ........................... تسبيق
    solde (du prix) ................... باقي الثمن
    tranche / étape de paiement ....... دفعة
    procès-verbal de livraison ........ محضر تسليم المعدات
    procès-verbal de réception ........ محضر تسلُّم الأشغال
    réception des travaux ............. تسلُّم الأشغال
    réserves (d'un procès-verbal) ..... التحفظات
    chantier .......................... الورش
    installation (solaire) ............ المنظومة (الشمسية)
    installation électrique du Client . التركيبات الكهربائية للزبون
    matériel .......................... المعدات
    pose / mise en service ............ التركيب / التشغيل
    clé en main ....................... بصيغة تسليم المفتاح
    garantie / garantie légale ........ الضمان / الضمان القانوني
    réserve de propriété .............. شرط الاحتفاظ بالملكية
    garde (du matériel) ............... الحراسة
    mise en demeure ................... إنذار
    force majeure ..................... القوة القاهرة
    quitus ............................ إبراء الذمة
    service après-vente ............... خدمة ما بعد البيع
    gestionnaire du réseau ............ مسيّر الشبكة
    onduleur .......................... العاكس
    application de suivi .............. تطبيق التتبع
    avenant / exemplaires originaux ... ملحق / نظيران أصليان
    Dahir des obligations et contrats . قانون الالتزامات والعقود (الفصل)
    loi n° 31-08 ...................... القانون رقم 31.08 القاضي بتحديد
                                        تدابير لحماية المستهلك (المادة)
    loi n° 82-21 ...................... القانون رقم 82.21 المتعلق بالإنتاج
                                        الذاتي للطاقة الكهربائية
    loi n° 09-08 ...................... القانون رقم 09.08 المتعلق بحماية
                                        الأشخاص الذاتيين تجاه معالجة المعطيات
                                        ذات الطابع الشخصي

Le ``ctx`` arabe porte les MÊMES clés que le français, mises en forme pour une
phrase arabe — la forme attendue de chaque repère est dans ``FORMES_CTX``.
"""

A_PRECISER = 'يُحدَّد لاحقًا'

# La forme arabe attendue de chaque repère du ``ctx`` (exemple tiré des
# données d'exemple du contrat). Les montants viennent de
# ``rendu.composants.montant(…, langue='ar')``, les dates de
# ``date_longue(…, langue='ar')``, les durées de ``duree_mois(…, langue='ar')``.
FORMES_CTX = {
    'societe': 'Société Exemple',
    'client': 'M. Youssef EL EXEMPLE',
    'devis_reference': 'DEV-202611-0042',
    # Fragment collé à la référence (vide si la date manque).
    'devis_accepte_le': '، الذي قبله الزبون بتاريخ 20 نونبر 2026',
    'total_ttc': '98 500,00 درهم',
    # Nombre de dfaat après « على » (génitif) : composants.nombre_de_dfaat.
    'nombre_etapes': '3 دفعات',
    'liste_tranches': (
        '- **30 %**، أي 29 550,00 درهم، عند توقيع هذا العقد؛\n'
        '- **60 %**، أي 59 100,00 درهم، عند تسليم المعدات '
        'إلى الزبون؛\n'
        '- **10 %**، أي 9 850,00 درهم، عند تسلُّم الأشغال.'),
    'modalites_paiement': ('يتم الأداء بتحويل بنكي أو بشيك لأمر الشركة. '
                           'RIB : 000 000 0000000000000000 00 — Banque '
                           'Exemple.'),
    # Une date nue : la phrase porte déjà « في أجل أقصاه ».
    'date_limite': '23 يناير 2027',
    # Au nominatif (« ومدته سنتان ») : duree_mois(…, langue='ar').
    'garantie_installation': 'سنتان',
    'pieces_detachees': 'قطع الغيار اللازمة متوفرة طوال مدة الضمانات.',
    'delai_mise_en_demeure': '8 أيام',
    'penalite_retard': '10 %',
    'email_societe': 'contact@exemple.ma',
    # Phrase complète précédée d'une espace, ou vide.
    'cndp': '',
    'delai_reponse': '15 يومًا',
    'contrat_reference': 'CTR-2026-11-0007',
    # Fragment collé à la référence du contrat, comme le français
    # « ␠du 24 novembre 2026 » : une espace, « المؤرَّخ في » et la date
    # longue arabe ; vide si la date est inconnue (la phrase se lit alors
    # « في العقد CTR-… وفي عرض الأثمان … »). Pas de virgule : le français
    # n'en met pas.
    'contrat_du': ' المؤرَّخ في 24 نونبر 2026',
    'total_regle': '88 650,00 درهم',
    'pourcentage_regle': '90 %',
    # Plus lus par les textes par défaut depuis la revue 1 (T6, T7) ; gardés
    # tant que le serveur les pose.
    'reste_apres_livraison': '9 850,00 درهم',
    'libelle_tranche_livraison': 'تسليم المعدات',
    # Prix − total réglé (la valeur de l'encadré), montant arabe.
    'reste_a_regler': '9 850,00 درهم',
    'exigible_maintenant': '59 100,00 درهم',
}


class _Contexte(dict):
    """Un repère absent s'imprime « يُحدَّد لاحقًا », jamais une accolade."""

    def __missing__(self, cle):
        return A_PRECISER


def _f(texte, ctx):
    return texte.format_map(_Contexte(ctx or {}))


def _article(cle, titre, paragraphes, ctx):
    return {'cle': cle, 'titre': _f(titre, ctx),
            'paragraphes': [_f(p, ctx) for p in paragraphes if p]}


_LOI_31_08 = 'القانون رقم 31.08 القاضي بتحديد تدابير لحماية المستهلك'
_DOC = 'قانون الالتزامات والعقود'
_GARANTIE_LEGALE = (
    "تُضاف هذه الضمانات إلى **الضمان القانوني** للعيوب، بما فيها العيوب "
    "الخفية (الفصول من 549 إلى 575 من " + _DOC + "، والمادة 65 من "
    + _LOI_31_08 + ")، الذي تلتزم به {societe} في جميع الأحوال.")

# Une seule règle de garde, comme en français (revue 1, T8).
_GARDE_LIVRAISON = (
    "ابتداءً من تسليم المعدات وإلى حين بداية التركيب، يتولى الزبون حراسة "
    "المعدات المسلَّمة: يحفظها في مأمن، داخل مكان مغلق، ")
_GARDE_SANS_OUVRIR = "دون فتحها أو نقلها، "
_GARDE_REPOND = (
    "ويُسأل عن ضياعها أو تلفها متى كان ذلك ناتجًا عن فعله أو عن تقصير منه "
    "في الحراسة. ")
_GARDE_POSE = (
    "وخلال التركيب وإلى حين التسلُّم، تتولى {societe} حراسة الورش؛ وعند "
    "التسلُّم، ")
_GARDE_TRANSFERT = "تنتقل حراسة المنظومة إلى الزبون."


def _regle_de_garde(sans_ouvrir=False):
    return (_GARDE_LIVRAISON + (_GARDE_SANS_OUVRIR if sans_ouvrir else '')
            + _GARDE_REPOND + _GARDE_POSE + _GARDE_TRANSFERT)


# ── Acte 1 — Contrat d'installation ─────────────────────────────────────────

def _contrat_installation(ctx, options):
    consommateur = options.get('consommateur', True)
    arts = [
        ('objet', 'موضوع العقد', [
            "تتولى {societe} توريد المنظومة الشمسية المبيَّنة في عرض الأثمان "
            "{devis_reference}{devis_accepte_le}، وتركيبها وتشغيلها لدى "
            "الزبون، في عنوان الورش.",
            "تُسلَّم المنظومة **بصيغة تسليم المفتاح**: الدراسة، وتوريد "
            "المعدات، والتركيب، والربط بالتركيبات الكهربائية للزبون، "
            "والتشغيل، وشرح طريقة الاشتغال.",
            "يُعدّ عرض الأثمان المقبول جزءًا من العقد. وإذا تعارض نصّان، "
            "تُقدَّم الشروط الخاصة، ثم هذا العقد، ثم عرض الأثمان.",
        ]),
        ('prix', 'الثمن', [
            "الثمن **ثابت ونهائي**: {total_ttc} مع احتساب جميع الرسوم. "
            "ويشمل المعدات والتركيب والتشغيل والرسوم.",
            "كل عمل غير وارد في عرض الأثمان يكون موضوع عرض أثمان تكميلي، "
            "يقبله الزبون كتابةً قبل إنجازه.",
            "لا تغيّر {societe} من تلقاء نفسها الثمن ولا المعدات المتفق "
            "عليها. وإذا أصبحت إحدى المعدات غير متوفرة، تقترح على الزبون "
            "معدات ذات جودة مماثلة على الأقل، دون أي زيادة في الثمن؛ ويعطي "
            "الزبون موافقته كتابةً.",
        ]),
        ('paiement', 'الأداء', [
            "يُؤدّى الثمن على {nombre_etapes}، ترتبط كل واحدة منها بمرحلة "
            "محددة من الورش:",
            "{liste_tranches}",
            "تُحرَّر فاتورة عن كل أداء. {modalites_paiement}",
            "يُطلَق طلب المعدات فور تحصيل الدفعة الأولى.",
        ]),
        ('delais', 'الآجال', [
            "تلتزم {societe} بتسليم المعدات وتركيب المنظومة وتشغيلها **في "
            "أجل أقصاه {date_limite}**.",
            "يُوقَف هذا الأجل طوال حالة القوة القاهرة، وخلال الأحوال الجوية "
            "التي تجعل العمل فوق السطح خطيرًا، وطوال كل تأخير يُعزى إلى "
            "الزبون (تعذّر الوصول إلى الورش، أداء معلّق، أشغال تمهيدية على "
            "عاتقه لم تُنجز). وتُخبر {societe} الزبون كتابةً بكل توقيف.",
            ("إذا تم تجاوز الأجل الأقصى بأكثر من سبعة أيام دون قوة قاهرة، "
             "جاز للزبون إنهاء العقد وفق الشروط المنصوص عليها في المواد من 12 "
             "إلى 14 من " + _LOI_31_08 + "؛ وتُرَدّ إليه حينئذ المبالغ "
             "المدفوعة داخل أجل سبعة أيام."
             if consommateur else ''),
        ]),
        ('engagements_societe', 'ما تلتزم {societe} بالقيام به', [
            "- إنجاز الأشغال وفق أصول الصنعة وطبقًا لمعايير السلامة "
            "الكهربائية الجاري بها العمل؛\n"
            "- الاستعانة بمستخدمين مؤهلين وبالمعدات المنصوص عليها في عرض "
            "الأثمان، جديدةً ومضمونةً من صانعها؛\n"
            "- حماية المكان طوال مدة الورش وتركه نظيفًا عند انتهائه؛\n"
            "- تسليم الزبون، عند التسلُّم، دلائل الاستعمال والبطاقات التقنية، "
            "وعند الاختتام، شهادة الضمان.",
        ]),
        ('engagements_client', 'ما يلتزم الزبون بالقيام به', [
            "- تمكين الولوج إلى الورش وإلى الماء والكهرباء في التواريخ "
            "المتفق عليها؛\n"
            "- ضمان أنه مالك المكان أو أنه حصل على الإذن اللازم (المالك، "
            "الملكية المشتركة)؛\n"
            "- الإخبار، قبل بدء الأشغال، بكل ما من شأنه أن يعرقلها أو يجعلها "
            "خطيرة: حالة السطح، العزل المائي، تركيبات كهربائية قديمة؛\n"
            "- أداء كل دفعة في التاريخ المحدد.",
        ]),
    ]
    if options.get('raccorde_reseau', True):
        arts.append(('demarches', 'الإجراءات لدى الشبكة الكهربائية', [
            "يُلزم القانون رقم 82.21 المتعلق بالإنتاج الذاتي للطاقة "
            "الكهربائية مالكَ منشأة مرتبطة بالشبكة بأن يصرّح بها لدى مسيّر "
            "الشبكة قبل الأشغال، أو أن يحصل، حسب قدرتها، على موافقته على "
            "الربط.",
            "يُكلِّف الزبون {societe} بإعداد هذا الملف وتتبّعه نيابة عنه؛ "
            "ويوقّع الوثائق المطلوبة. وتبقى المصاريف المحتملة لمسيّر الشبكة، "
            "ومنها مصاريف العداد، على عاتق الزبون.",
        ]))
    if options.get('reserve_propriete', True):
        arts.append(('propriete', 'ملكية المعدات', [
            "تبقى المعدات في ملكية {societe} إلى حين الأداء الكامل للثمن "
            "(الفصول 618-21 وما يليها من " + _DOC + "). وإلى ذلك الحين، "
            "لا يجوز للزبون بيعها ولا تقديمها ضمانًا ولا العمل على تفكيكها.",
            _regle_de_garde(),
        ]))
    arts += [
        ('reception', 'تسلُّم الأشغال', [
            "عند انتهاء التركيب، تشغّل {societe} المنظومة بحضور الزبون "
            "وتشرح له طريقة اشتغالها. ويوقّع الطرفان حينئذ محضر تسلُّم "
            "الأشغال.",
            "يجوز للزبون أن يدوّن فيه تحفظات؛ وترفعها {societe} داخل الأجل "
            "المدوَّن في المحضر. ولا تحول التحفظات دون استعمال المنظومة. "
            "وإذا دُوِّنت تحفظات، جاز للطرفين أن يحدّدا فيه، باتفاق بينهما، "
            "مبلغ جزء من باقي الثمن يُحتجز إلى حين رفعها، دون أن يتجاوز قيمة "
            "الأشغال المتبقية؛ وإذا لم يُحدَّد أي مبلغ، فلا يُحتجز أي جزء.",
            "إذا رفض الزبون توقيع المحضر، بيّن كتابةً، داخل أجل السبعة أيام "
            "الموالية للتشغيل، العيوب التي تبرّر رفضه؛ وتتولى {societe} "
            "إصلاحها، ثم يُقترح تسلُّم جديد. وفي غياب جواب مكتوب داخل هذا "
            "الأجل، أمكن {societe} أن توجّه إلى الزبون إنذارًا بتسلُّم الأشغال "
            "(الفصل 774 من " + _DOC + ").",
            "يشكّل التسلُّم نقطة انطلاق الضمانات، ويجعل باقي الثمن مستحق "
            "الأداء.",
        ]),
        ('garanties', 'الضمانات', [
            "يستفيد الزبون من الضمانات المبيَّنة في جدول «ضماناتكم»: "
            "ضمانات الصانعين على المعدات، وضمان {societe} على أشغال التركيب "
            "التي تنجزها، ومدته {garantie_installation}.",
            "خلال هذه المدد، تكون {societe} المخاطَب الوحيد للزبون: تقوم "
            "بالتشخيص، وتتابع الطلب لدى الصانع، وتتحمّل مصاريف نقل المعدات "
            "المضمونة. وتُمدَّد مدة الضمان بقدر المدة التي تظل فيها المعدات "
            "معطَّلة للإصلاح. {pieces_detachees}",
            _GARANTIE_LEGALE,
            "ولا تشمل هذه الضمانات الأضرار الناتجة عن تدخّل أو تعديل من طرف "
            "الغير، أو عن صدمة أو حريق أو فيضان أو صاعقة أو فرط جهد الشبكة، "
            "ولا عن تقصير في الصيانة أو استعمال مخالف لدلائل الاستعمال.",
        ]),
        ('estimations', 'الإنتاج والتوفير المقدَّران', [
            "أرقام الإنتاج والتوفير الواردة في عرض الأثمان تقديرات، محسوبة "
            "انطلاقًا من متوسط أشعة الشمس في الموقع ومن الاستهلاك الذي صرّح "
            "به الزبون. ويتغيّر الإنتاج الفعلي بحسب الطقس والظل وطريقة "
            "الاستعمال: فهذه الأرقام ليست وعدًا بتحقيق نتيجة.",
        ]),
    ]
    retard = [
        "إذا لم يُنجَز أداءٌ في تاريخه المحدد، توجّه {societe} إلى الزبون "
        "إنذارًا كتابيًا. وإذا انقضى أجل {delai_mise_en_demeure} دون أن "
        "يُحدث الإنذار أثرًا، أمكن {societe} أن توقف الأشغال، ثم أن تطالب "
        "قضائيًا بأداء المبالغ المستحقة أو باسترجاع المعدات التي ظلّت في "
        "ملكيتها.",
    ]
    if options.get('penalite_retard_pct'):
        retard.append(
            "بعد انقضاء هذا الأجل، تستحق {societe} تعويضًا جزافيًا قدره "
            "{penalite_retard} من المبالغ غير المؤداة، مرة واحدة فقط، أيًّا "
            "كانت مدة التأخير وعدد التذكيرات.")
    arts += [
        ('retard', 'التأخر في الأداء', retard),
        ('fin_anticipee', 'إنهاء العقد قبل أوانه', [
            "إذا عدل الزبون عن العقد بعد طلب المعدات أو بدء الأشغال، تحتفظ "
            "{societe}، من المبالغ المدفوعة وبناءً على مستندات مثبتة، بكلفة "
            "المعدات المطلوبة لفائدته وبكلفة الأشغال المنجزة؛ ويُرَدّ إليه "
            "الباقي.",
            "إذا تعذّر على {societe} تنفيذ العقد، تردّ إلى الزبون جميع "
            "المبالغ المدفوعة.",
        ]),
        ('donnees', 'المعطيات الشخصية', [
            "تستعمل {societe} معطيات الزبون (الهوية، وسائل الاتصال، العنوان، "
            "استهلاك الكهرباء) لإعداد عرض الأثمان، وتنفيذ العقد، وتأمين "
            "الضمانات وخدمة ما بعد البيع. ولا تُحال إلا إلى المتدخلين في "
            "الورش أو في الضمانات: الصانعون، مسيّر الشبكة.",
            "طبقًا للقانون رقم 09.08 المتعلق بحماية الأشخاص الذاتيين تجاه "
            "معالجة المعطيات ذات الطابع الشخصي، يحق للزبون الولوج إلى "
            "معطياته، وتصحيحها، أو الاعتراض على استعمالها، بمراسلة "
            "{email_societe}.{cndp}",
        ]),
        ('differends', 'في حالة الخلاف', [
            "يسعى الطرفان أولًا إلى حل ودي: يراسل الزبون {societe}، التي "
            "تجيبه داخل أجل {delai_reponse}.",
            ("فإن تعذّر الاتفاق، يُعرض النزاع على المحكمة المختصة وفق "
             "القانون؛ ويجوز للزبون رفعه أمام محكمة موطنه (المادة 202 من "
             + _LOI_31_08 + ")." if consommateur
             else "فإن تعذّر الاتفاق، يُعرض النزاع على المحكمة المختصة التي "
                  "يوجد بدائرتها مقر {societe}."),
        ]),
        ('dispositions_finales', 'التعديلات والنظائر', [
            "كل تعديل للعقد يكون موضوع ملحق مكتوب يوقّعه الطرفان. ويُحرَّر "
            "العقد في نظيرين أصليين، لكل طرف نظير.",
        ]),
    ]
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


# ── Acte 2 — Procès-verbal de livraison ─────────────────────────────────────

def _pv_livraison(ctx, options, variante):
    arts = [
        ('constat', 'ما يثبته هذا المحضر', [
            "عاين الزبون، بحضور {societe}، المعدات المبيَّنة أعلاه. وكل ما "
            "وُضعت أمامه علامة يُعدّ معايَنًا؛ وكل عيب ظاهر يُدوَّن في "
            "التحفظات.",
            "العيب الذي لم يكن ممكنًا رؤيته عند التسليم يظل مشمولًا بضمانات "
            "العقد.",
        ]),
        ('garde', 'حراسة المعدات', [
            _regle_de_garde(sans_ouvrir=True),
        ]),
    ]
    if options.get('reserve_propriete', True):
        arts.append(('propriete', 'الملكية', [
            "تبقى المعدات في ملكية {societe} إلى حين الأداء الكامل للثمن، "
            "كما ينص على ذلك العقد {contrat_reference}.",
        ]))
    if variante == 'tranche_reglee':
        arts.append(('paiement', 'الأداء', [
            "تؤكد {societe} أنها حصّلت إلى غاية اليوم {total_regle}، أي "
            "{pourcentage_regle} من الثمن. ولا شيء يُؤدّى عند التسليم.",
            "يصبح باقي الثمن، أي {reste_a_regler}، مستحق الأداء عند تسلُّم "
            "الأشغال.",
        ]))
    else:
        arts.append(('paiement', 'أداء هذه المرحلة', [
            "وفقًا لجدول الدفعات في العقد {contrat_reference}، تبلغ المبالغ "
            "المستحقة في تاريخ هذا المحضر {exigible_maintenant}. ويقرّ "
            "الزبون بأنه توصّل بالمعدات المبيَّنة أعلاه وبأن هذا المبلغ دين "
            "عليه لفائدة {societe}.",
            "يُبرمَج التركيب فور تحصيل هذا المبلغ.",
        ]))
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


# ── Acte 3 — Procès-verbal de réception ─────────────────────────────────────

def _pv_reception(ctx, options):
    arts = [
        ('portee', 'ما يعنيه التسلُّم', [
            "بتوقيعه، يقرّ الزبون بأن {societe} أتمّت الأشغال المنصوص عليها "
            "في العقد {contrat_reference}{contrat_du} وفي عرض الأثمان "
            "{devis_reference}، وبأن المنظومة مطابقة لهاتين الوثيقتين "
            "وتشتغل، وبأنه لم يلاحظ أي خلل ظاهر خارج التحفظات المكتوبة "
            "أعلاه.",
            "عند التسلُّم، " + _GARDE_TRANSFERT + " وترفع {societe} "
            "التحفظات المحتملة داخل الأجل المبيَّن؛ ويُثبَت رفعها في محرَّر "
            "يوقّعه الزبون.",
            "تسري الضمانات المنصوص عليها في العقد **ابتداءً من هذا اليوم**. "
            "وتُسلَّم إلى الزبون في هذا اليوم دلائل الاستعمال والبطاقات "
            "التقنية؛ وتُسلَّم إليه شهادة الضمان الجامعة مع وثيقة الاختتام.",
        ]),
        ('solde', 'باقي الثمن', [
            "يقرّ الزبون بأن في ذمته لفائدة {societe} مبلغ "
            "{exigible_maintenant}، وهو باقي ثمن العقد {contrat_reference} "
            "الذي لا يزال مستحقًا إلى غاية اليوم، يُؤدّى عند توقيع هذا "
            "المحضر.",
            "إذا دُوِّنت تحفظات، يحدّد الطرفان أعلاه، باتفاق بينهما، مبلغ "
            "الجزء من باقي الثمن المحتجز إلى حين رفعها؛ ولا يجوز أن يتجاوز "
            "هذا الجزء قيمة الأشغال المتبقية. ويُؤدّى ما سوى هذا الجزء عند "
            "التوقيع؛ ويُؤدّى الجزء المحتجز داخل أجل الثمانية أيام الموالية "
            "للمعاينة الكتابية لرفع التحفظات. وإذا لم يُحدَّد أي مبلغ، فلا "
            "يُحتجز أي جزء.",
        ] + (["إلى حين الأداء الكامل، تبقى المعدات في ملكية {societe}."]
             if options.get('reserve_propriete', True) else [])),
        ('retard', 'التأخر في الأداء', [
            "إذا لم يُؤدَّ باقي الثمن، توجّه {societe} إلى الزبون إنذارًا "
            "كتابيًا. وإذا انقضى أجل {delai_mise_en_demeure} دون أن يُحدث "
            "الإنذار أثرًا، أمكن {societe} أن تطالب قضائيًا بأداء باقي الثمن "
            "أو باسترجاع المعدات التي ظلّت في ملكيتها.",
        ] + (["بعد انقضاء هذا الأجل، تستحق {societe} تعويضًا جزافيًا قدره "
              "{penalite_retard} من المبالغ غير المؤداة، مرة واحدة فقط."]
             if options.get('penalite_retard_pct') else [])),
    ]
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


# ── Acte 4 — Quitus, certificat de garantie, conseils ───────────────────────

def _cloture_garanties(ctx, options):
    arts = [
        ('contact', 'بمن تتصلون', [
            "مخاطَب واحد: خدمة ما بعد البيع لدى {societe}. صِفوا ما "
            "تلاحظونه، وأرسلوا صورة لشاشة العاكس أو لتطبيق التتبع.",
        ]),
        ('demarche', 'كيف يُعالَج الطلب', [
            "- تقوم {societe} بالتشخيص، عن بُعد أو في عين المكان؛\n"
            "- إذا كان أحد الضمانات ساريًا، تصلح {societe} المعدات أو "
            "تستبدلها، وتتابع الطلب لدى الصانع؛\n"
            "- مصاريف نقل المعدات المضمونة على عاتق {societe}؛\n"
            "- تُمدَّد مدة الضمان بقدر المدة التي تظل فيها المعدات معطَّلة؛ "
            "ويُسلَّم إليكم وصل مؤرَّخ عند أخذها وعند إرجاعها.",
        ]),
        ('couvert', 'ما يشمله الضمان', [
            "عيوب المعدات، وفق شروط كل صانع، وعيوب التركيب طوال مدة ضمان "
            "التركيب. {pieces_detachees}",
        ]),
        ('exclusions', 'ما لا يشمله', [
            "- تدخّل أو تعديل من طرف شخص أجنبي عن {societe}؛\n"
            "- صدمة أو حريق أو فيضان أو صاعقة أو فرط جهد الشبكة؛\n"
            "- تقصير في الصيانة أو استعمال مخالف لدلائل الاستعمال.",
        ]),
        ('garantie_legale', 'حقوقكم في جميع الأحوال', [
            _GARANTIE_LEGALE,
            "في حالة خلاف حول أحد الضمانات، راسلوا {societe}، التي تجيبكم "
            "داخل أجل {delai_reponse}؛ وإن تعذّر الاتفاق، يمكنكم رفع الأمر "
            "إلى محكمة موطنكم.",
        ]),
    ]
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


def articles_par_defaut(type_acte, variante='', ctx=None, options=None):
    """Les articles par défaut d'un acte, en arabe. ``ctx`` : repères déjà mis
    en forme pour l'arabe (``FORMES_CTX``) ; ``options`` : ``consommateur``,
    ``reserve_propriete``, ``raccorde_reseau``, ``penalite_retard_pct``."""
    ctx = ctx or {}
    options = options or {}
    if type_acte == 'contrat_installation':
        return _contrat_installation(ctx, options)
    if type_acte == 'pv_livraison':
        return _pv_livraison(ctx, options, variante)
    if type_acte == 'pv_reception':
        return _pv_reception(ctx, options)
    if type_acte == 'cloture_garanties':
        return _cloture_garanties(ctx, options)
    raise ValueError(f"Type d'acte inconnu : {type_acte!r}")


def quitus_par_defaut(ctx):
    return [_f(p, ctx) for p in (
        "تشهد {societe} بأنها توصّلت من {client} بالمبلغ الإجمالي "
        "**{total_ttc}** مع احتساب جميع الرسوم، أي كامل ثمن المنظومة موضوع "
        "العقد {contrat_reference}.",
        "تبرأ ذمة الزبون من كل مبلغ تجاه {societe} برسم هذا العقد. وتؤول "
        "إليه ملكية جميع المعدات بصفة نهائية.",
    )]


# ── Constats à cocher ───────────────────────────────────────────────────────

def constats_par_defaut(type_acte):
    if type_acte == 'pv_livraison':
        textes = (
            "المعدات المسلَّمة مطابقة لعرض الأثمان المقبول.",
            "وصلت الطرود مغلقة وفي حالة جيدة ظاهريًا.",
            "المعدات مخزَّنة في مأمن، داخل مكان مغلق، في عنوان الورش.",
        )
        return [{'texte': t, 'cochee': False} for t in textes]
    if type_acte == 'pv_reception':
        textes = (
            "المنظومة المركَّبة **مطابقة لعرض الأثمان المقبول وللعقد**.",
            "تم **تشغيلها وهي تشتغل**، بحضوري.",
            "**شُرحت لي** طريقة اشتغالها، وتطبيق التتبع، وإجراءات السلامة.",
            "**توصّلتُ بدلائل الاستعمال والبطاقات التقنية** الخاصة بمنظومتي.",
            "**تُرك الورش نظيفًا**؛ ولم ألاحظ أي ضرر بسطح منزلي ولا داخله.",
        )
        return [{'texte': t, 'cochee': False} for t in textes]
    return []


# ── Conseils d'usage (acte 4) ───────────────────────────────────────────────
# Mêmes sources que le français ; aucun pourcentage ni kilowattheure.

def journee_solaire(avec_batterie):
    nuit = 'البطارية، ثم الشبكة' if avec_batterie else 'الشبكة'
    return {
        'plages': [
            {'sorte': 'nuit', 'part': 4, 'libelle': 'الليل', 'sous': nuit},
            {'sorte': 'bord', 'part': 3, 'libelle': 'الصباح',
             'sous': 'الإنتاج يرتفع'},
            {'sorte': 'plein', 'part': 7, 'libelle': 'منتصف النهار',
             'sous': 'أفضل وقت لأجهزتكم الكبيرة'},
            {'sorte': 'bord', 'part': 3, 'libelle': 'آخر النهار',
             'sous': 'الإنتاج ينخفض'},
            {'sorte': 'nuit', 'part': 5, 'libelle': 'المساء والليل',
             'sous': nuit},
        ],
        'legende': "تنتج منظومتكم من شروق الشمس إلى غروبها، ويبلغ إنتاجها "
                   "ذروته في منتصف النهار.",
    }


def conseils_par_defaut(avec_batterie):
    """``(intro, conseils)`` : le texte d'ouverture et les fiches conseil."""
    if avec_batterie:
        intro = ("في النهار، تزوّد ألواحكم المنزل بالكهرباء وتشحن البطارية؛ "
                 "وفي المساء، تتولى البطارية المهمة. وكلما اشتغلت أجهزتكم "
                 "الكبيرة تحت الشمس، بقيت البطارية ممتلئة لليل.")
    else:
        intro = ("بدون بطارية، تُستهلك الكهرباء الشمسية لحظة إنتاجها: فالعادة "
                 "الصحيحة هي تشغيل أجهزتكم حين تكون الشمس ساطعة.")
    conseils = [
        {'rubrique': 'الأجهزة الكبيرة',
         'titre': 'شغّلوها في منتصف النهار',
         'texte': "آلة غسل الملابس، آلة غسل الأواني، آلة تجفيف الملابس، "
                  "الفرن: شغّلوها حين يكون الإنتاج في أقصاه. وخاصية "
                  "التشغيل المؤجَّل تقوم بذلك عنكم في غيابكم."},
        {'rubrique': 'جهاز واحد في كل مرة',
         'titre': 'وزّعوا بدل أن تجمعوا',
         'texte': "قد يتجاوز جهازان كبيران يشتغلان في آن واحد ما تنتجه "
                  "الألواح: شغّلوا الغسيل صباحًا، وآلة غسل الأواني بعد "
                  "الظهر."},
        {'rubrique': 'الماء الساخن',
         'titre': 'سخّنوا الماء بالشمس',
         'texte': "إذا كان سخّان الماء لديكم كهربائيًا، اضبطوا فترة تسخينه "
                  "على منتصف النهار بدل الليل."},
        {'rubrique': 'التكييف',
         'titre': 'برّدوا قبل المساء',
         'texte': "شغّلوا المكيّف بعد الظهر، ما دامت الألواح تنتج، بدل "
                  "تشغيله عند حلول الليل."},
    ]
    if avec_batterie:
        conseils.append(
            {'rubrique': 'البطارية',
             'titre': 'احتفظوا بها للمساء',
             'texte': "تُشحن نهارًا بالفائض وتزوّدكم بالكهرباء بعد غروب "
                      "الشمس: تجنّبوا إفراغها بعد الظهر بالأجهزة الكبيرة."})
    else:
        conseils.append(
            {'rubrique': 'وضع الاستعداد',
             'titre': 'أطفئوا ما لا يُستعمل ليلًا',
             'texte': "في الليل، كل ما يبقى موصولًا تؤدّون ثمنه للشبكة: "
                      "افصلوا الأجهزة الموضوعة في وضع الاستعداد بمقبس متعدد "
                      "مزوَّد بمفتاح."})
    conseils.append(
        {'rubrique': 'التتبع',
         'titre': 'اطّلعوا على التطبيق مرة في الأسبوع',
         'texte': "يبيّن ما تنتجونه وما تستهلكونه: إنها أفضل وسيلة لملاءمة "
                  "عاداتكم مع الشمس ورصد أي خلل."})
    return intro, conseils


def entretien_par_defaut():
    return [
        "- نظرة على التطبيق كل أسبوع: يجب إخبارنا بأي إنتاج منعدم في وضح "
        "النهار؛\n"
        "- ألواح نظيفة: شطفها بالماء الصافي عندما يتراكم الغبار؛\n"
        "- لا ينبغي لأي شيء أن يُلقي ظله على الألواح: هوائي، غسيل، نباتات "
        "تنمو؛\n"
        "- قبل أي أشغال على السطح أو على التركيبات الكهربائية، أخبرونا.",
    ]
