"""Tous les libellés que le rendu des actes imprime, en français et en arabe.

Une seule table : le rendu n'écrit plus aucun mot en dur, il demande
``libelle(cle, langue, **valeurs)``. Le français est la référence (une clé
absente de la table arabe retombe sur le français) ; l'arabe est la traduction
qui accompagne l'acte (loi n° 31-08, art. 206). Les valeurs ``{…}`` arrivent
déjà échappées et isolées par le rendu : la table ne fait que les placer.

Lexique arabe tenu partout (le même que ``contrats/textes_ar.py``) : الزبون,
عرض الأثمان, تسبيق, باقي الثمن, محضر تسليم المعدات, محضر تسلُّم الأشغال, الورش,
الضمان, إبراء الذمة, خدمة ما بعد البيع.
"""

LIBELLES = {
    'fr': {
        # Parcours des quatre actes (titre court, sous-titre).
        'etape_contrat_installation': 'Contrat',
        'etape_contrat_installation_sous': 'à la signature',
        'etape_pv_livraison': 'Livraison',
        'etape_pv_livraison_sous': 'le matériel chez vous',
        'etape_pv_reception': 'Réception',
        'etape_pv_reception_sous': 'à la fin des travaux',
        'etape_cloture_garanties': 'Clôture',
        'etape_cloture_garanties_sous': 'garanties et conseils',
        'surtitre': 'Acte {rang} sur 4 · {court}',
        'chantier': 'Chantier {ref}',
        'acte': 'Acte',
        # Frise de paiement.
        'etat_regle': 'Réglé',
        'etat_exigible': 'À régler',
        'etat_a_venir': 'À venir',
        'regle_le': '{mot} le {date}',
        # Parties.
        'installateur': "L'installateur",
        'le_client': 'Le client',
        'au_capital': 'au capital de {capital}',
        'representee_par': 'Représentée par {nom}',
        'representee_par_a_remplir': 'Représentée par : ……………………',
        'ci_apres': 'ci-après « {nom} »',
        'ci_apres_client': 'ci-après « le Client »',
        'ci_apres_client_societe': 'ci-après « le Client »',
        'id_rc': 'RC',
        'id_ice': 'ICE',
        'id_if': 'IF',
        'id_patente': 'Patente',
        'id_cnss': 'CNSS',
        'id_cin': 'CIN',
        'cin_a_remplir': 'CIN : ……………………',
        'ice_a_remplir': 'ICE : ……………………',
        # Tableaux.
        'th_designation': 'Désignation',
        'th_marque': 'Marque',
        'th_quantite': 'Quantité',
        'th_serie': 'N° de série',
        'th_garanti': 'Ce qui est garanti',
        'th_duree': 'Durée',
        'th_jusquau': "Jusqu'au",
        'th_couvre': 'Ce que cela couvre',
        'th_date': 'Date',
        'th_objet': 'Objet',
        'th_mode': 'Mode',
        'th_montant': 'Montant',
        'total_regle': 'Total réglé',
        # Articles, signatures, pied.
        'article': 'Article {n}',
        'signe_le': 'Signé le {date}',
        'signe_par': 'par {nom}',
        'alt_signature': 'signature',
        'fait_a': 'Fait à {lieu}, le {quand}',
        'exemplaires': ', en deux exemplaires originaux, un pour chaque partie',
        'pour_societe': 'Pour {nom}',
        'signature_cachet': 'Signature et cachet',
        'paraphe_client': 'Client',
        'paraphe_societe': 'Société',
        # Mots communs des actes.
        'kwc': 'kWc',
        'installation_solaire': 'Installation solaire',
        'conditions_particulieres': 'Conditions particulières',
        'conditions_particulieres_intro': (
            'Ce qui a été convenu en plus pour votre chantier ; ces lignes '
            'priment sur les articles ci-dessus.'),
        'convenu_entre_nous': 'Convenu entre nous',
        'votre_installation': 'Votre installation',
        'date_a_porter': 'Date à porter',
        'vos_garanties': 'Vos garanties',
        'paye_integralement': 'Payé intégralement',
        # Acte 1 — contrat.
        'h1_contrat': "Contrat d'installation photovoltaïque",
        'chapeau_contrat': (
            'Ce contrat fixe ce que {nom} installe chez vous, à quel prix, en '
            'combien de paiements, dans quels délais et avec quelles '
            "garanties. <b>L'essentiel tient sur cette page</b> ; le détail "
            'suit. Dans ce contrat, « vous » et « le Client » désignent la '
            'même personne.'),
        'lessentiel': "L'essentiel",
        'ttc_long': 'toutes taxes comprises',
        'ttc_detail': 'TTC · soit {ht} hors taxes et {tva} de TVA',
        'prix_convenu': 'Prix convenu',
        'termine_au_plus_tard': 'Terminé au plus tard le',
        'a_preciser_maj': 'À préciser',
        'jusqua': "Jusqu'à {duree}",
        'garanties_fabricant': 'Garanties fabricant',
        'paiement_en_1': 'Votre paiement en {n} étape',
        'paiement_en_n': 'Votre paiement en {n} étapes',
        'paiement_intro': (
            'Chaque étape correspond à un moment précis du chantier : '
            "l'acompte lance la commande de votre matériel, les paiements "
            'suivants suivent la livraison puis la fin des travaux.'),
        'entre_soussignes': 'Entre les soussignés',
        'ce_que_nous_installons': 'Ce que nous installons',
        'ce_que_nous_installons_intro': (
            'Le matériel et les prestations sont ceux du devis {devis}, que '
            'vous avez accepté et qui fait partie du contrat.'),
        'garanties_intro': (
            'Elles commencent le jour de la réception des travaux.'),
        'conditions_du_contrat': 'Les conditions du contrat',
        'mention_contrat': (
            'Signature précédée de la mention manuscrite « Lu et approuvé, bon '
            'pour accord »'),
        # Acte 2 — livraison.
        'h1_livraison': 'Procès-verbal de livraison du matériel',
        'chapeau_livraison': (
            'Le matériel de votre installation est arrivé chez vous. Ce '
            'document constate ce qui a été livré, dans quel état, et fait le '
            'point sur votre paiement à cette étape.'),
        'livre_le': 'Livré le',
        'etape_suivante': 'Étape suivante',
        'la_pose': 'La pose',
        'materiel_livre': 'Le matériel livré',
        'conformement_devis': 'Conformément au devis {devis}.',
        'vos_constatations': 'Vos constatations',
        'reserves_eventuelles': 'Réserves éventuelles',
        'reserves_eventuelles_aide': (
            'Colis abîmé, pièce manquante, référence différente : notez-le '
            'ici, nous le corrigeons avant la pose.'),
        'paiement_cette_etape': 'Votre paiement à cette étape',
        'ce_que_vous_convenez': 'Ce que nous convenons ensemble',
        'mention_livraison': (
            'Signature précédée de la mention manuscrite « Reçu le matériel '
            'ci-dessus »'),
        'part_du_prix': '<b>{part}</b> du prix',
        'sommes_dues': 'les sommes dues à ce jour',
        'vous_avez_regle': (
            "Vous avez réglé {quoi} : rien n'est à payer à la livraison."),
        'il_restera': (
            'Il restera <b>{montant}</b>, à régler à la réception des '
            'travaux.'),
        'regle_a_ce_jour': 'Réglé à ce jour',
        'deja_regle': 'Déjà réglé : <b>{montant}</b>',
        'restera_reception': (
            'Restera à régler à la réception des travaux : <b>{montant}</b>'),
        'a_regler_livraison': 'À régler à la livraison',
        # Acte 3 — réception.
        'h1_reception': 'Procès-verbal de réception des travaux',
        'chapeau_reception': (
            'Les travaux sont terminés et votre installation fonctionne. En '
            'signant, vous constatez avec {nom} que le travail prévu au '
            "contrat a été réalisé ; vos garanties commencent aujourd'hui."),
        'mise_en_service': 'Mise en service',
        'verifie_ensemble': 'Ce que nous avons vérifié ensemble',
        'la_reception': 'La réception',
        'une_seule_case': (
            'Cochez une seule des deux cases. Si aucune case n\'est cochée, '
            'la signature vaut réception sans réserve.'),
        'sans_reserve': (
            '**Je prononce la réception sans réserve.** Les travaux sont '
            'conformes au contrat et au devis accepté.'),
        'avec_reserves': (
            '**Je prononce la réception avec les réserves ci-dessous**, que '
            "{nom} s'engage à lever dans le délai indiqué."),
        'reserves': 'Réserves',
        'a_lever_sous': ' — à lever sous {delai}',
        'solde_installation': 'Le solde de votre installation',
        'regle_totalite': (
            'Vous avez réglé la totalité du prix. Il ne reste rien à payer.'),
        'solde_a_regler': 'Solde à régler à la réception',
        'ce_que_reception_change': 'Ce que la réception change',
        'mention_reception': (
            'Signature précédée de la mention manuscrite « Lu et approuvé, bon '
            'pour réception »'),
        # Acte 4 — clôture.
        'h1_cloture': 'Quitus et certificat de garantie',
        'chapeau_cloture': (
            'Votre installation est payée, garantie et à vous. Gardez ce '
            'document : il prouve votre paiement, liste vos garanties et vous '
            'aide à tirer le meilleur de votre énergie solaire.'),
        'solde_zero': 'Solde : <b>0,00 DH</b> · plus rien à régler',
        'attestation': 'Attestation de paiement intégral',
        'quitus': 'Quitus',
        'certificat': 'Certificat de garantie',
        'certificat_intro': (
            'Garanties en vigueur depuis la réception des travaux, le {date}, '
            "à l'adresse {adresse}."),
        'date_inconnue': '…',
        'adresse_du_chantier': 'du chantier',
        'materiel_couvert': 'Le matériel couvert',
        'si_probleme': 'Si quelque chose ne va pas',
        'sav': 'Service après-vente {nom}',
        'bien_consommer': 'Bien consommer votre énergie solaire',
        'entretien': "L'entretien, en peu de mots",
        # Ajouts de la revue 1 (noms partagés, docs/contrats/revue-1.md).
        'part_retenue': (
            "Part du solde retenue jusqu'à la levée des réserves : "
            '………… DH'),
        'signature_en_fin': 'Signature en dernière page',
        # Brouillon et clôture d'une vente non soldée (recette C2).
        'filigrane_projet': 'PROJET — document non émis',
        'reste_a_regler_carte': 'Reste à régler',
        'reste_du_detail': "Le prix n'est pas encore réglé en totalité.",
        'quitus_en_attente': (
            'Le quitus sera établi lorsque le prix aura été payé en '
            'totalité : il reste {montant} à régler.'),
        # Clôture d'une vente non soldée : chapeau, titre et certificat qui
        # n'affirment aucun paiement (recette finale, S1).
        'chapeau_cloture_du': (
            'Ce document deviendra votre quitus et votre certificat de '
            'garantie dès que le prix sera réglé en totalité. Il reste '
            "aujourd'hui <b>{reste}</b> à régler."),
        'attestation_du': 'Le paiement du prix',
        'certificat_intro_du': (
            'Garanties prévues au contrat, à compter de la réception des '
            "travaux, le {date}, à l'adresse {adresse}."),
    },
    'ar': {
        'etape_contrat_installation': 'العقد',
        'etape_contrat_installation_sous': 'عند التوقيع',
        'etape_pv_livraison': 'التسليم',
        'etape_pv_livraison_sous': 'المعدات عندكم',
        'etape_pv_reception': 'التسلُّم',
        'etape_pv_reception_sous': 'عند انتهاء الأشغال',
        'etape_cloture_garanties': 'الاختتام',
        'etape_cloture_garanties_sous': 'الضمانات والنصائح',
        'surtitre': 'الوثيقة {rang} من 4 · {court}',
        'chantier': 'الورش {ref}',
        'acte': 'وثيقة',
        'etat_regle': 'مؤدّاة',
        'etat_exigible': 'واجبة الأداء',
        'etat_a_venir': 'لاحقة',
        'regle_le': '{mot} بتاريخ {date}',
        'installateur': 'المُركِّب',
        'le_client': 'الزبون',
        'au_capital': 'رأسمالها {capital}',
        'representee_par': 'يمثلها {nom}',
        'representee_par_a_remplir': 'يمثلها: ……………………',
        'ci_apres': 'المشار إليها فيما يلي بـ«{nom}»',
        'ci_apres_client': 'المشار إليه فيما يلي بـ«الزبون»',
        # Client société (شركة، مؤنث) : « المشار إليها ».
        'ci_apres_client_societe': 'المشار إليها فيما يلي بـ«الزبون»',
        'id_rc': 'السجل التجاري',
        'id_ice': 'التعريف الموحد للمقاولة (ICE)',
        'id_if': 'التعريف الضريبي',
        'id_patente': 'الرسم المهني',
        'id_cnss': 'الضمان الاجتماعي',
        'id_cin': 'البطاقة الوطنية للتعريف',
        'cin_a_remplir': 'البطاقة الوطنية للتعريف: ……………………',
        'ice_a_remplir': 'التعريف الموحد للمقاولة (ICE): ……………………',
        'th_designation': 'البيان',
        'th_marque': 'العلامة',
        'th_quantite': 'الكمية',
        'th_serie': 'الرقم التسلسلي',
        'th_garanti': 'موضوع الضمان',
        'th_duree': 'المدة',
        'th_jusquau': 'إلى غاية',
        'th_couvre': 'ما يشمله',
        'th_date': 'التاريخ',
        'th_objet': 'الموضوع',
        'th_mode': 'طريقة الأداء',
        'th_montant': 'المبلغ',
        'total_regle': 'مجموع المبالغ المؤداة',
        'article': 'البند {n}',
        'signe_le': 'وُقِّع بتاريخ {date}',
        'signe_par': 'من طرف {nom}',
        'alt_signature': 'التوقيع',
        'fait_a': 'حُرِّر في {lieu}، بتاريخ {quand}',
        'exemplaires': '، في نظيرين أصليين، لكل طرف نظير',
        'pour_societe': 'عن {nom}',
        'signature_cachet': 'التوقيع والخاتم',
        'paraphe_client': 'الزبون',
        'paraphe_societe': 'الشركة',
        'kwc': 'kWc',
        'installation_solaire': 'منظومة شمسية',
        'conditions_particulieres': 'الشروط الخاصة',
        'conditions_particulieres_intro': (
            'ما اتُّفق عليه زيادةً لورشكم؛ وتُقدَّم هذه السطور على البنود '
            'أعلاه.'),
        'convenu_entre_nous': 'المتفق عليه بيننا',
        'votre_installation': 'منظومتكم',
        'date_a_porter': 'يُدوَّن التاريخ',
        'vos_garanties': 'ضماناتكم',
        'paye_integralement': 'مؤدّى بالكامل',
        'h1_contrat': 'عقد تركيب منظومة شمسية كهروضوئية',
        'chapeau_contrat': (
            'يحدد هذا العقد ما تركّبه {nom} لديكم، وبأي ثمن، وعلى كم دفعة، '
            'وفي أي أجل، وبأي ضمانات. <b>الأساسي في هذه الصفحة</b>، '
            'والتفاصيل بعدها. وفي هذا العقد، يُقصد بـ«أنتم» وبـ«الزبون» الشخص '
            'نفسه.'),
        'lessentiel': 'الأساسي',
        'ttc_long': 'مع احتساب جميع الرسوم',
        'ttc_detail': 'مع احتساب الرسوم · أي {ht} دون الرسوم و{tva} '
                      'برسم الضريبة على القيمة المضافة',
        'prix_convenu': 'الثمن المتفق عليه',
        'termine_au_plus_tard': 'الإنجاز في أجل أقصاه',
        'a_preciser_maj': 'يُحدَّد لاحقًا',
        'jusqua': 'المدة القصوى: {duree}',
        'garanties_fabricant': 'ضمانات الصانع',
        'paiement_en_1': 'أداء الثمن على {n}',
        'paiement_en_n': 'أداء الثمن على {n}',
        'paiement_intro': (
            'تقابل كل دفعة مرحلة محددة من الورش: يُطلق التسبيق طلب '
            'معداتكم، وتأتي الدفعات الموالية بعد التسليم ثم بعد انتهاء '
            'الأشغال.'),
        'entre_soussignes': 'بين الموقعين أدناه',
        'ce_que_nous_installons': 'ما نركّبه لكم',
        'ce_que_nous_installons_intro': (
            'المعدات والخدمات هي تلك المبيَّنة في عرض الأثمان {devis}، الذي '
            'قبلتموه والذي يُعدّ جزءًا من العقد.'),
        'garanties_intro': 'تبدأ يوم تسلُّم الأشغال.',
        'conditions_du_contrat': 'شروط العقد',
        'mention_contrat': (
            'التوقيع مسبوقًا بعبارة بخط اليد: «قُرئ وصودق عليه، موافق»'),
        'h1_livraison': 'محضر تسليم المعدات',
        'chapeau_livraison': (
            'وصلت معدات منظومتكم إلى منزلكم. تثبت هذه الوثيقة ما تم تسليمه '
            'وفي أي حالة، وتبيّن وضعية أدائكم في هذه المرحلة.'),
        'livre_le': 'تاريخ التسليم',
        'etape_suivante': 'المرحلة الموالية',
        'la_pose': 'التركيب',
        'materiel_livre': 'المعدات المسلَّمة',
        'conformement_devis': 'طبقًا لعرض الأثمان {devis}.',
        'vos_constatations': 'معايناتكم',
        'reserves_eventuelles': 'التحفظات المحتملة',
        'reserves_eventuelles_aide': (
            'طرد متضرر، قطعة ناقصة، مرجع مختلف: دوّنوه هنا، ونصلحه قبل '
            'التركيب.'),
        'paiement_cette_etape': 'أداؤكم في هذه المرحلة',
        'ce_que_vous_convenez': 'ما نتفق عليه معًا',
        'mention_livraison': (
            'التوقيع مسبوقًا بعبارة بخط اليد: «توصلتُ بالمعدات المبيَّنة '
            'أعلاه»'),
        'part_du_prix': '<b>{part}</b> من الثمن',
        'sommes_dues': 'المبالغ المستحقة إلى غاية اليوم',
        'vous_avez_regle': 'أدّيتم {quoi}: لا شيء يُؤدّى عند التسليم.',
        'il_restera': 'سيبقى <b>{montant}</b>، يُؤدّى عند تسلُّم الأشغال.',
        'regle_a_ce_jour': 'المؤدّى إلى غاية اليوم',
        'deja_regle': 'المؤدّى سابقًا: <b>{montant}</b>',
        'restera_reception': 'يبقى للأداء عند تسلُّم الأشغال: <b>{montant}</b>',
        'a_regler_livraison': 'يُؤدّى عند التسليم',
        'h1_reception': 'محضر تسلُّم الأشغال',
        'chapeau_reception': (
            'انتهت الأشغال ومنظومتكم تشتغل. بتوقيعكم، تعاينون مع {nom} أن '
            'العمل المنصوص عليه في العقد قد أُنجز؛ وتبدأ ضماناتكم اليوم.'),
        'mise_en_service': 'التشغيل',
        'verifie_ensemble': 'ما تحققنا منه معًا',
        'la_reception': 'التسلُّم',
        'une_seule_case': (
            'ضعوا علامة في خانة واحدة فقط من الخانتين. وإذا لم توضع علامة في '
            'أي خانة، يُعدّ التوقيع تسلُّمًا للأشغال دون تحفظ.'),
        'sans_reserve': (
            '**أصرّح بتسلُّم الأشغال دون تحفظ.** الأشغال مطابقة للعقد ولعرض '
            'الأثمان المقبول.'),
        'avec_reserves': (
            '**أصرّح بتسلُّم الأشغال مع التحفظات المبيَّنة أدناه**، التي '
            'تلتزم {nom} برفعها داخل الأجل المحدد.'),
        'reserves': 'التحفظات',
        'a_lever_sous': ' — تُرفع داخل أجل {delai}',
        'solde_installation': 'باقي ثمن منظومتكم',
        'regle_totalite': 'أدّيتم الثمن بكامله. لم يبقَ شيء للأداء.',
        'solde_a_regler': 'باقي الثمن الواجب أداؤه عند التسلُّم',
        'ce_que_reception_change': 'ما يغيّره التسلُّم',
        'mention_reception': (
            'التوقيع مسبوقًا بعبارة بخط اليد: «قُرئ وصودق عليه، صالح '
            'للتسلُّم»'),
        'h1_cloture': 'إبراء الذمة وشهادة الضمان',
        'chapeau_cloture': (
            'منظومتكم مؤدّاة ومضمونة وفي ملكيتكم. احتفظوا بهذه الوثيقة: فهي '
            'تثبت أداءكم، وتبيّن ضماناتكم، وتساعدكم على الاستفادة القصوى من '
            'طاقتكم الشمسية.'),
        'solde_zero': 'الباقي: <b>{zero}</b> · لا شيء يُؤدّى بعد الآن',
        'attestation': 'شهادة الأداء الكامل',
        'quitus': 'إبراء الذمة',
        'certificat': 'شهادة الضمان',
        'certificat_intro': (
            'ضمانات سارية منذ تسلُّم الأشغال بتاريخ {date}، في {adresse}.'),
        'date_inconnue': '…',
        'adresse_du_chantier': 'عنوان الورش',
        'materiel_couvert': 'المعدات المشمولة بالضمان',
        'si_probleme': 'إذا حدث خلل',
        'sav': 'خدمة ما بعد البيع لدى {nom}',
        'bien_consommer': 'استهلكوا طاقتكم الشمسية على النحو الأمثل',
        'entretien': 'الصيانة في كلمات قليلة',
        'part_retenue': (
            'الجزء المحتجز من باقي الثمن إلى حين رفع التحفظات: ………… درهم'),
        'signature_en_fin': 'التوقيع في الصفحة الأخيرة',
        'filigrane_projet': 'مشروع — وثيقة غير صادرة',
        'reste_a_regler_carte': 'الباقي للأداء',
        'reste_du_detail': 'لم يُؤدَّ الثمن بكامله بعد.',
        'quitus_en_attente': (
            'سيُحرَّر إبراء الذمة عند أداء الثمن بكامله: يبقى {montant} '
            'للأداء.'),
        'chapeau_cloture_du': (
            'ستصبح هذه الوثيقة إبراءً للذمة وشهادةً للضمان فور أداء الثمن '
            'بكامله. ويبقى إلى غاية اليوم <b>{reste}</b> للأداء.'),
        'attestation_du': 'أداء الثمن',
        'certificat_intro_du': (
            'الضمانات المنصوص عليها في العقد، ابتداءً من تسلُّم الأشغال '
            'بتاريخ {date}، في {adresse}.'),
    },
}


def libelle(cle, langue='fr', **valeurs):
    """Le libellé ``cle`` dans ``langue`` (repli : le français), avec ses
    ``{valeurs}`` placées. ``KeyError`` si la clé n'existe pas du tout : un
    libellé oublié doit casser le test, jamais s'imprimer vide."""
    francais = LIBELLES['fr']
    texte = LIBELLES.get(langue, francais).get(cle)
    if texte is None:
        texte = francais[cle]
    return texte.format(**valeurs) if valeurs else texte
