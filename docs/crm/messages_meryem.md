# Messages de Meryem — textes validés (Guide v2.1 + Protocole de rappel v3, 04/09/2026)

Source de vérité des gabarits `parametres.MessageTemplate` que MRY12 seed dans `MESSAGE_TEMPLATE_DEFAULTS`
(`corps_fr` = colonne FR ; `corps_darija` = colonne darija, écriture arabe, revue native le 04/09/2026).
Règles : aucun chiffre qui ne vienne du devis ou du lead ; placeholders autorisés `{civilite} {nom} {prenom} {ville}
{reference} {lien} {lien_rdv} {date_validite} {conseiller} {mois_preuve} {ville_preuve} {lien_preuve} {puissance_preuve}
{date_visite} {lien_video_preuve} {marque} {lien_google}` ; le crochet
`[…]` des textes ci-dessous devient le placeholder correspondant au seed (`M. [Prénom]` → `{prenom}`, `[date]` →
`{date_validite}`, `[date de la visite]`/`[تاريخ الزيارة]` → `{date_visite}`, `[référence]` → `{reference}`, `[lien preuve]` → `{lien_preuve}` (AVANT la règle générale), `[puissance preuve]` → `{puissance_preuve}`, `[lien vidéo]` →
`{lien_video_preuve}` (CAD95, 21/09/2026 — vidéo courte proposée EN PLUS du lien, jamais à la place),
`[lien de la fiche TAQINOR]` → `{lien_google}` (CAD71, 21/09/2026 — AVANT la règle générale : ce n'est PAS le lien du
devis), `[lien …]` → `{lien}` (dont `[lien de votre proposition]`, J6 — relevé fondateur 08/09/2026 : la touche « garanties » partait sans aucun lien), `[mois]` → `{mois_preuve}`, `[ville]` → `{ville_preuve}`, `[Conseiller]` → `{conseiller}`,
`[المستشار]` → `{conseiller}`, `[Marque]` → `{marque}` (CAD96, 21/09/2026 — le nom affiché de la société,
résolu côté serveur ; remplace les trois graphies incohérentes du guide d'origine) ; ce qui n'a pas de placeholder (montant, raison réelle, jour/heure de rappel) reste à
saisir par Meryem au moment de l'envoi — jamais un défaut. Une phrase dont le placeholder est vide est OMISE au rendu
(MRY13).

CAD71 (21/09/2026) — `avis_google` envoyait le lien du DEVIS du client (seule source alimentant `{lien}` dans
`apps/crm/services.message_pour_etape`) à la place d'un lien vers la fiche Google : `{lien_google}` est désormais
alimenté par `CompanyProfile.lien_avis_google` (réglage société), et le gabarit est refusé à l'assignation tant que
ce réglage est vide.

Ordre fondateur du 08/09/2026 (catalogue « Réalisations ») : les placeholders `{mois_preuve}`, `{ville_preuve}`,
`{lien_preuve}` et `{puissance_preuve}` de la touche `j4_preuve` ne se saisissent plus à la main. Le serveur les
remplit depuis `parametres.Realisation` via `parametres.selectors.realisation_pour_lead` : l'installation RÉELLE de la
même ville que le lead, sinon la plus proche à moins de 60 km, sinon — repli fondateur du 08/09/2026 — la DERNIÈRE
installation de la société (puissance la plus proche du devis si connue) ; la ville affichée est toujours la sienne,
vraie : « comparable » parle de la taille, jamais du lieu. Mois de mise en service, lien de la page publique et
puissance viennent de la fiche ; une puissance inconnue fait tomber SA phrase seule. Sans aucune réalisation au
catalogue, les placeholders restent vides et la phrase entière est omise — jamais une preuve inventée.

Règle fondateur du 08/09/2026 : aucun prénom de personne (ex. Meryem, Reda) n'est codé en dur dans un texte qui
atteint le client. L'expéditeur d'un message est désigné par `[Conseiller]`/`[المستشار]` → `{conseiller}`, rempli
côté serveur avec le prénom (à défaut le nom d'utilisateur) du RESPONSABLE du lead ; à défaut, le responsable par
défaut des leads de la société ; en dernier repli, l'utilisateur qui déclenche l'envoi. Toute mention du fondateur
dans un texte client utilise le rôle « le fondateur », jamais son prénom.

## Cadence « contact » (Protocole v3, chapitre 5)

### identite — J0, WhatsApp, dans les cinq minutes (M1)
FR : Bonjour M. [Prénom], je suis [Conseiller] de [Marque]. Vous venez de nous laisser une demande pour le solaire, merci. Je vous appelle dans quelques minutes pour une première estimation ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.
DARIJA : السلام عليكم السي [الاسم]، أنا [المستشار] من [Marque]. وصلنا الطلب ديالكم على الطاقة الشمسية، شكرا. غادي نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير أولي. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.

### appel_ouverture — J0, script d'ouverture de l'appel n° 1 (A1)
CAD109 (21/09/2026) — loi 31-08 art. 51 : un démarchage téléphonique doit indiquer explicitement l'identité ET le
caractère commercial de l'intervention (sanctionné par l'art. 180) ; loi 09-08 art. 5 §3 + décret 2-09-165 art. 34 :
pour des données non collectées auprès de la personne (Meta, Odoo), l'information sur leur origine peut être donnée
oralement. La « confirmation écrite de l'offre » qu'exige l'art. 51 est déjà assurée par le devis envoyé.
FR : Bonjour M. [Prénom], [Conseiller] de [Marque] — c'est un appel commercial. Vous venez de remplir notre formulaire pour le solaire ; vous pouvez me demander à tout moment d'où viennent vos coordonnées. Je vous dérange deux minutes ?
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque] — هادا اتصال تجاري. عمرتو دابا الفورم ديالنا على الطاقة الشمسية؛ تقدرو تسولوني فأي وقت منين جاو المعلومات ديالكم. نقدر ناخد منكم جوج دقايق؟

### repondeur — appels 2 et 4, message sur répondeur (R1)
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Je vous appelle au sujet de votre demande solaire. Je vous envoie un message WhatsApp, répondez-y quand vous voulez. Bonne journée.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. كنعيط ليكم بخصوص الطلب ديالكم على الطاقة الشمسية. غادي نصيفط ليكم رسالة على الواتساب، جاوبو فوقاش ما بغيتو. نهاركم مبروك.

### appel_relance — Appel 3, J1 10 h 30, troisième tentative (CAD67, 21/09/2026)
Avant CAD67, `repondeur` partait aussi ici (ordre 4), à ~20 h du premier envoi (ordre 3) — contraire au document
ci-dessus qui le réserve aux appels 2 et 4. Script court dédié, comme `appel_ouverture`/`vocal_j3`/`appel_dimanche`.
CAD96 (fold post-merge) — [Marque] plutôt que « TAQINOR » codé en dur.
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Je reviens vers vous pour votre demande solaire d'hier — vous avez deux minutes maintenant ?
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. كنرجع ليكم بخصوص الطلب ديالكم ديال البارح — عندكم جوج دقايق دابا؟

### valeur_j1 — J1, WhatsApp de valeur (M2)
FR : Bonjour M. [Prénom], je n'ai pas réussi à vous joindre. Pour que l'estimation soit juste, j'ai besoin de votre facture (une photo suffit) et de votre adresse : je vous montre vos panneaux posés sur votre toit, avec l'économie estimée. Quel moment vous arrange pour un appel de cinq minutes ?
DARIJA : السلام عليكم السي [الاسم]، حاولت نعيط ليكم ولكن ما لقيتكمش. باش يكون التقدير مضبوط، خاصني غير تصويرة ديال فاتورة الضو والعنوان ديالكم، ونوريكم كيفاش غادي يجيو الألواح فوق السطح ديالكم مع شحال غادي توفرو ف الفاتورة. شمن وقت يناسبكم باش نعيط ليكم خمس دقايق؟

### vocal_j3 — J3, vocal WhatsApp de trente secondes (M3, script à dire)
FR : Bonjour M. [Prénom], c'est [Conseiller] de [Marque]. Je vous ai laissé deux messages, je ne veux pas insister : dites-moi juste si le projet est toujours d'actualité, et à quelle heure je peux vous appeler. Bonne journée.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. صيفطت ليكم جوج رسائل وما بغيتش نثقل عليكم. غير قولوا ليا واش مشروع الطاقة الشمسية مازال كيهمكم، وفوقاش نقدر نعيط ليكم. نهاركم مبروك.

### appel_dimanche — 5e appel, le dimanche 16 h–19 h, pour les injoignables (A3)
CAD109 — même mention que `appel_ouverture` (loi 31-08 art. 51 + loi 09-08 art. 5 §3), sur le second script d'appel
EN DIRECT (`repondeur`/`vocal_j3` restent des scripts de répondeur/vocal, pas des ouvertures de conversation).
FR : Bonjour M. [Prénom], [Conseiller] de [Marque] — c'est un appel commercial. Je me permets de vous appeler un dimanche parce que je ne vous trouve pas en semaine ; vous pouvez me demander à tout moment d'où viennent vos coordonnées. Je ne vous retiens pas : votre demande solaire est-elle toujours d'actualité ?
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque] — هادا اتصال تجاري. سمحو ليا كنعيط ليكم نهار الحد، حيت ف الأسبوع ما كنلقاكمش؛ تقدرو تسولوني فأي وقت منين جاو المعلومات ديالكم. ما غاديش نطول عليكم: واش الطلب ديالكم على الطاقة الشمسية مازال كيهمكم؟

### je_classe_j7 — J7, WhatsApp « je classe ? » (M4)
CAD66 (21/09/2026) — « dans trois jours » promettait une clôture à J10 ; le moteur clôture réellement à J14
(`cloture_j14`), donc « dans une semaine » depuis J7. Aucun barreau déplacé, seul le mot change.
CAD110 (21/09/2026) — porte de sortie (loi 09-08 art. 10 al. 5 : opposition possible + coordonnées valables pour
faire cesser — l'envoi manuel ne protège de rien, l'article vise le MOYEN et le consentement) sur les touches qui
portent le plus loin (J7, J14, fin d'après-devis, tous les réveils) ; pas les trois premiers messages.
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Sans nouvelle de votre part, je mets votre demande de côté dans une semaine. Un simple « plus tard » me suffit pour la garder ouverte. Répondez STOP et je n'insiste plus.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. إلا ما جاوبتونيش، غادي نحط الطلب ديالكم على جنب من هنا لأسبوع. كلمة «من بعد» كافية باش نخلي الطلب ديالكم محلول. جاوبو STOP وما نلحوش عليكم.

### appel_dernier — Appel 6 (dernier), J10, avant clôture (CAD67, 21/09/2026)
Le dernier appel avant `cloture_j14` — celui qui décide du classement du lead — n'avait aucune phrase d'ouverture.
CAD96 (fold post-merge) — [Marque] plutôt que « TAQINOR » codé en dur.
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Dernier essai avant de classer votre demande : votre projet solaire est-il toujours d'actualité ?
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. هادي آخر محاولة قبل ما نسد الطلب ديالكم: واش مشروع الطاقة الشمسية ديالكم مازال كيهمكم؟

### cloture_j14 — J14, WhatsApp de clôture, passage en Froid (M5)
CAD110 — porte de sortie (voir note ci-dessus, section `je_classe_j7`).
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Je classe votre demande pour ne pas vous déranger. Si vous souhaitez reprendre plus tard, ce message suffit : je vous prépare l'étude en 24 h. Répondez STOP et je n'insiste plus.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. غادي نسد الطلب ديالكم باش ما نزعجكمش. إلا بغيتو ترجعو للمشروع من بعد، صيفطو ليا غير هاد الرسالة ونوجد ليكم الدراسة ف 24 ساعة. جاوبو STOP وما نلحوش عليكم.

### reveil_a2 — J30 seulement, réveil des leads jamais chiffrés (M6)
CAD68 (21/09/2026) — routage RÉEL (`apps/crm/services._adapter_gabarits_reveil`, appelée par
`initialiser_plan_relance`) : à J30, le gabarit part selon le dossier — `reveil_a1` si le lead a déjà reçu un
devis, `reveil_a2` sinon ; à J60, TOUS les leads reçoivent `reveil_a3` (dernière chance), jamais `reveil_a2` — le
barreau J60 seedé sous `reveil_a2` (`CADENCE_REVEIL_DEFAUT`) est TOUJOURS remplacé. `reveil_a2` ne part donc
qu'à J30, jamais à J60 malgré son ancien intitulé.
CAD110 — porte de sortie (voir note ci-dessus, section `je_classe_j7`) : les QUATRE touches de réveil, les plus
lointaines de la cadence (J30/J60), sont les plus exposées.
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Il y a un mois, vous vous renseigniez sur le solaire. Si le projet revient d'actualité, je reprends votre dossier là où on l'a laissé : une photo de votre dernière facture, et je vous envoie l'estimation à jour. Répondez STOP et je n'insiste plus.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. هادي شهر كنتو كتسولو على الطاقة الشمسية. إلا رجع المشروع كيهمكم، غادي نكمل الملف ديالكم من فين وقفنا: تصويرة ديال آخر فاتورة، وغادي نصيفط ليكم التقدير الجديد. جاوبو STOP وما نلحوش عليكم.

### rappel_plus_tard — réponse à « rappelez-moi plus tard » (M9)
FR : Très bien, je vous rappelle [jour] à [heure]. D'ici là, si vous avez votre facture sous la main, une photo m'aide à préparer l'estimation.
DARIJA : واخا، غادي نعيط ليكم [النهار] على [الساعة]. وحتى لذاك الوقت، إلا كانت الفاتورة عندكم، تصويرة ديالها غادي تعاونني نوجد التقدير.

### stop_contact — réponse à « ne me rappelez plus » (M10)
FR : Compris, je ne vous rappellerai plus. Je vous laisse simplement ce numéro si un jour le projet revient. Bonne journée.
DARIJA : واخا، فهمتكم، ما غاديش نعاود نعيط ليكم. غير كنخلي ليكم هاد الرقم إلا شي نهار رجع المشروع. نهاركم مبروك.

## Cadence « après devis » (Guide v2.1, chapitre 7) et dimanche

### j1_pdf — J1, WhatsApp
FR : Bonjour M. [Prénom], j'espère que vous allez bien. Je vous ai envoyé votre proposition solaire — est-ce que le PDF s'ouvre bien de votre côté ? Prenez le temps de la regarder tranquillement, et dites-moi ce qui vous a le plus parlé. Je suis là pour la moindre question.
DARIJA : السلام عليكم السي [الاسم]، كنتمنى تكونو بخير. صيفطت ليكم العرض ديال الطاقة الشمسية ديالكم — واش كيحل عندكم مزيان الـ PDF؟ خدو الوقت باش تشوفوه بشوية، وقولوا ليا شنو اللي عجبكم بزاف. أنا هنا لأي سؤال.

### j4_preuve — J4, WhatsApp (la vue de SON toit avec les panneaux, ou la photo d'un chantier comparable)
FR : Voici une installation comparable à la vôtre, posée en [mois] à [ville] : [lien preuve]. Puissance installée : [puissance preuve] kWc. Le suivi de production est en temps réel, je peux vous montrer. Petite vidéo du chantier : [lien vidéo].
DARIJA : هادي تجهيزة شبيهة بديالكم، تركبات ف [mois] ف [ville] : [lien preuve]. القوة المركبة: [puissance preuve] kWc. متابعة الإنتاج كاينة ف الوقت الحقيقي، نقدر نوريكم.

### j6_garanties — J6, WhatsApp (avec les certificats de garantie des fabricants)
FR : Ces garanties sont accordées par les fabricants : elles restent valables quoi qu'il arrive. Le détail par équipement est dans votre proposition : [lien de votre proposition]. Ce qui est couvert et pour combien d'années : https://taqinor.ma/garanties
DARIJA : هاد الضمانات كتعطيهم الشركات المصنعة: كيبقاو صالحين ف كل الأحوال. التفاصيل ديال كل معدة كاينة ف العرض ديالكم: [lien de votre proposition]. شنو المغطى وشحال ديال السنين: https://taqinor.ma/garanties

### j9_validite — J9, WhatsApp
FR : Votre proposition est valable jusqu'au [date]. Après, je dois revalider les prix et la disponibilité du matériel : ce n'est pas pour vous presser, c'est pour ne pas vous annoncer un prix faux.
DARIJA : العرض ديالكم صالح حتى [date]. من بعد، خاصني نعاود نتأكد من الأثمنة وتوفر المعدات: ماشي باش نضغط عليكم، باش ما نعطيكمش ثمن غير صحيح.

### j13_dernier — J13, WhatsApp
CAD110 — porte de sortie (voir note, section `je_classe_j7`) : les deux DERNIÈRES touches après-devis.
FR : Je ne veux pas insister : dites-moi si le projet est toujours d'actualité, et si non, je vous laisse tranquille. Répondez STOP et je n'insiste plus.
DARIJA : ما بغيتش نلح عليكم: قولوا ليا واش المشروع مازال كيهمكم، وإلا لا، نخليكم ف حالكم. جاوبو STOP وما نلحوش عليكم.

### j14_pause — J14, WhatsApp, passage en Froid
CAD110 — porte de sortie (voir note, section `je_classe_j7`).
FR : Je mets votre dossier en pause. Votre proposition reste dans notre système ; un message suffit pour la réactiver. Répondez STOP et je n'insiste plus.
DARIJA : غادي نحط الملف ديالكم فالوقفة. العرض ديالكم كيبقى محفوظ عندنا؛ رسالة وحدة كافية باش نرجعو نفعلوه. جاوبو STOP وما نلحوش عليكم.

### dimanche_famille — premier dimanche 16 h après J3, leads « Décision à plusieurs » (M7)
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Je sais que la décision se prend en famille. Si vous en parlez ce week-end, je peux vous envoyer la page résumé (une page, les chiffres clés) pour la partager, ou vous appeler à deux ou trois dimanche après 17 h, comme vous préférez.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. عارفة بلي القرار كيتاخد مع العائلة. إلا غادي تهضرو عليه هاد الويكاند، نقدر نصيفط ليكم ورقة الملخص (صفحة وحدة فيها الأرقام المهمة) باش تشاركوها، ولا نعيط ليكم نهار الحد من بعد 5 ديال العشية وتكونو جوج ولا تلاتة، كيف ما بغيتو.

### annonce_appel_reda — le vendredi, annoncer l'appel de Reda du dimanche (M11)
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Le fondateur, qui valide chaque étude, aimerait vous appeler dimanche vers 18 h pour répondre à vos questions en cinq minutes. Ça vous convient, ou préférez-vous un autre moment ?
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. المؤسس ديال الشركة اللي كيراجع كل دراسة بغا يعيط ليكم نهار الحد على 6 ديال العشية باش يجاوب على الأسئلة ديالكم ف خمس دقايق. واش مناسب ليكم، ولا كتفضلو وقت آخر؟

### offre_reda — après la décision de Reda seulement, jamais avant (M8)
FR : Bonjour M. [Prénom], [Conseiller] de [Marque]. Suite à votre échange avec le fondateur : [la raison réelle], il vous accorde [montant en dirhams] sur la proposition n° [référence], soit [nouveau total TTC]. Cette proposition est valable jusqu'à mardi 18 h ; ensuite le prix normal reprend. Je reste disponible pour toute question.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. بعد الهضرة ديالكم مع المؤسس: [السبب الحقيقي]، نقص ليكم [المبلغ بالدرهم] من العرض رقم [المرجع]، يعني [المجموع الجديد TTC]. هاد العرض صالح حتى الثلاثاء على 6 ديال العشية، ومن بعد كيرجع الثمن العادي. إلا كان عندكم شي سؤال أنا هنا.

### reveil_a1 — dormants avec devis (A1 du Guide)
CAD73 (21/09/2026) — « il y a quelques mois » était un fait daté FAUX : ce réveil part ~6 semaines après le devis
(`cloturer_cadence` démarre la cadence réveil à sa clôture, ~J14, donc `reveil_a1` tombe vers J+44), jamais des
mois. Reformulé SANS durée plutôt qu'une durée inventée.
CAD110 — porte de sortie sur les QUATRE touches de réveil (voir note, section `je_classe_j7`).
FR : Bonjour M. [prénom], c'est [Conseiller] de [Marque]. Vous aviez reçu un devis solaire chez nous. Du nouveau depuis : on peut maintenant vous montrer vos panneaux posés sur VOTRE toit, en 3D, avec l'estimation à jour de vos économies. Je vous prépare la vue et je vous l'envoie ici — c'est gratuit, sans engagement. Je me lance ? (Je dois juste confirmer votre adresse.) Répondez STOP et je n'insiste plus.
DARIJA : السلام عليكم السي [الاسم]، أنا [المستشار] من [Marque]. كنتو توصلتو بعرض للطاقة الشمسية عندنا. كاين جديد: دابا نقدرو نوريوكم الألواح فوق السطح ديالكم بالضبط، ب 3D، مع تقدير محين ديال التوفير ديالكم. غادي نوجد ليكم الصورة ونصيفطها ليكم هنا — بلاش، بلا ما تلتزمو بوالو. نبدا؟ (خاصني غير نتأكد من العنوان ديالكم.) جاوبو STOP وما نلحوش عليكم.

### reveil_a3 — dernière chance, la rupture honnête (A3 du Guide)
CAD110 — porte de sortie (voir note, section `je_classe_j7`).
FR : Bonjour M. [prénom], [Conseiller] de [Marque]. Je ne veux pas insister : si le projet n'est plus d'actualité, je ferme votre dossier, aucun souci. Avant ça, une dernière chose qui aide souvent à décider : je peux vous envoyer la vue 3D de vos panneaux sur votre toit, avec l'estimation à jour. Je vous la prépare, ou je classe le dossier ? Répondez STOP et je n'insiste plus.
DARIJA : السلام عليكم السي [الاسم]، [المستشار] من [Marque]. ما بغيتش نلح: إلا ماشي مازال كيهمكم المشروع، نسد ليكم الملف، بلا مشكل. قبل هادشي، شي حاجة كتعاون بزاف باش تقرر: نقدر نصيفط ليكم الصورة ب 3D ديال الألواح فوق السطح ديالكم، مع تقدير محين. نوجدها ليكم، ولا نسد الملف؟ جاوبو STOP وما نلحوش عليكم.

### reveil_b — la saison des factures (B du Guide)
CAD110 — porte de sortie (voir note, section `je_classe_j7`).
FR : Bonjour M. [prénom], c'est [Conseiller] de [Marque]. C'est la saison des factures d'été — souvent le moment où le solaire se décide. Votre projet est-il toujours d'actualité ? Si oui, je vous prépare une estimation à jour de vos économies, sans engagement. On en parle ? Répondez STOP et je n'insiste plus.
DARIJA : السلام عليكم السي [الاسم]، أنا [المستشار] من [Marque]. هادي موسم فواتير الصيف — غالبا هو الوقت اللي فيه كيتقرر مشروع الطاقة الشمسية. واش المشروع ديالكم مازال كيهمكم؟ إلا واخا، نوجد ليكم تقدير محين ديال التوفير، بلا ما تلتزمو بوالو. نهضرو عليه؟ جاوبو STOP وما نلحوش عليكم.

## Après la signature (Guide v2.1, chapitre 13)

### avis_google — à tous les clients, de la même façon, sans contrepartie
FR : Bonjour M. [Prénom], j'espère que l'installation vous donne satisfaction. Si vous avez deux minutes, un avis sur Google nous aide énormément, c'est ce que regardent les futurs clients : [lien de la fiche TAQINOR]. Merci beaucoup !
DARIJA : السلام عليكم السي [الاسم]، كنتمنى تكونو راضيين على التجهيزة. إلا عندكم جوج دقايق، رأي على Google كيعاوننا بزاف، هادشي اللي كيشوفوه الزبناء الجداد: [lien de la fiche TAQINOR]. شكرا بزاف!

### parrainage
FR : Si quelqu'un autour de vous, un voisin, un frère, un collègue, réfléchit au solaire, vous pouvez lui envoyer votre lien de parrainage ; il aura la même étude gratuite, et on convient ensemble d'une récompense pour vous.
DARIJA : إلا كان شي واحد حداكم، جار، خو، ولا زميل، كيفكر ف الطاقة الشمسية، تقدرو تصيفطو ليه الرابط ديال الرعاية ديالكم؛ غادي يكون عندو نفس الدراسة بلاش، ونتافقو مع بعضياتنا على مكافأة ليكم.

## La visite technique, étape du suivi (ordre fondateur 15/09/2026)

La visite technique n'est pas un préalable à l'étude : elle se place APRÈS l'envoi du devis, comme outil de closing,
pendant que le client est chaud. Deux textes seulement — la PROPOSER, puis la CONFIRMER la veille. Le retour du
terrain, lui, n'est pas un message client : il redescend dans l'historique du lead et déclenche le rappel du
responsable sous 24-48 h.

### visite_proposition — après l'envoi du devis, WhatsApp
FR : Pour verrouiller votre proposition, on peut passer chez vous pour la vérification technique gratuite : le technicien confirme l'orientation du toit, la charpente et le tableau électrique, et répond à toutes vos questions sur place. Ça ne vous engage à rien. Dites-moi le jour qui vous arrange cette semaine et je bloque le créneau. — [Conseiller]
DARIJA : باش نثبتو ليكم العرض، نقدرو نجيو عندكم لزيارة تقنية بلا فلوس: التقني كيتأكد من الاتجاه ديال السطح، من الهيكل ومن الطابلو ديال الضو، وكيجاوب على كل الأسئلة ديالكم فعين المكان. ما كتلزمكم بوالو. قولوا ليا شمن نهار يناسبكم هاد السيمانة ونحجز ليكم الوقت. — [المستشار]

### visite_confirmation — la veille de la visite, WhatsApp
FR : Bonjour, on confirme la visite technique prévue [date de la visite] chez vous. Le technicien vérifie le toit, la charpente et le tableau électrique — prévoyez l'accès au compteur. Votre présence est importante : c'est l'occasion de répondre à toutes vos questions sur place. En cas d'empêchement, répondez-moi ici et on recale le passage. — [Conseiller]
DARIJA : السلام عليكم، كنأكدو ليكم الزيارة التقنية المبرمجة [تاريخ الزيارة] عندكم. التقني غادي يشوف السطح، الهيكل والطابلو ديال الضو — وجدو ليه الوصول للكونتور. الحضور ديالكم مهم: هي الفرصة باش نجاوبو على جميع الأسئلة ديالكم فعين المكان. إلا طرا ليكم شي مانع، جاوبوني هنا ونعاودو نبرمجو الزيارة. — [المستشار]

Ordre fondateur du 15/09/2026 : la visite ne se fait qu'avec le VRAI client présent — jamais le gardien ni la bonne. La
phrase « Votre présence est importante » le demande sans être blessante, en donnant la RAISON (répondre à ses questions
sur place), qui est aussi la vraie valeur du passage.

Les deux variantes darija ci-dessus sont À FAIRE RELIRE par un locuteur natif : elles suivent le FR validé phrase par
phrase (aucune promesse ajoutée, aucun chiffre) mais n'ont pas reçu la revue native du 04/09/2026.

Décision fondateur du 21/09/2026 (CAD170) — VÉHICULE ÉLECTRIQUE, RECHARGE DE NUIT : **aucun texte ne conseille au
client de recharger sa voiture en journée.** C'est le cas majoritaire (fenêtre 21h-6h) et l'effet mesuré sur
l'autoconsommation est nul, même avec une batterie de 10 kWh. La réponse commerciale est le DIMENSIONNEMENT : les
kWh/jour de recharge nocturne s'ajoutent au besoin de stockage, servis par une taille d'offre réellement vendue
(`apps/ventes/etude_horaire.besoin_stockage_avec_recharge_ve`) — jamais une batterie sur mesure, jamais au-delà du
catalogue. Le conseil « décalez la recharge en journée » est ÉCARTÉ : le gain qui le soutenait venait d'une
autoconsommation non bornée, corrigée depuis (CAD165). Toute rédaction future de texte client sur ce sujet parle de la
batterie qui couvre la nuit, jamais d'un changement d'habitude du client.

Décisions fondateur du 21/09/2026 (CAD173) — TROIS RÈGLES DE CONTENU, à tenir dans tout texte futur :
- **Coupures (Q15)** : « tenir pendant les coupures » est un ARGUMENT commercial, rien d'autre. Aucun texte ne promet
  une autonomie, une durée de secours ou un nombre d'heures : aucun dimensionnement de secours n'est calculé, donc
  aucun chiffre de secours n'existe. La réponse du client vit dans l'objectif de projet de sa fiche.
- **Carburant agricole (Q17)** : l'économie de carburant se calcule UNIQUEMENT sur ce que le client déclare (litres ou
  dirhams par mois). **Aucun prix de gasoil de référence n'est écrit nulle part** — ni dans le code, ni dans un texte.
  Sans déclaration du client, la phrase est omise ; jamais un prix de marché supposé.
- **Subventions (Q22)** : on ne promet RIEN. Aucun texte n'annonce un montant, un taux, une éligibilité ni un délai de
  subvention : on renvoie le client aux conditions officielles du programme concerné.

## Sans texte validé (ne PAS seeder — à rédiger par Reda/Meryem avant tout usage)
visite_veille, visite_matin, apres_visite : aucun texte validé n'existe dans le Guide v2.1 ni dans le Protocole v3.
(`visite_proposition` et `visite_confirmation`, eux, ont reçu leur texte validé le 15/09/2026 — section ci-dessus.)

CAD62 (21/09/2026) — les 11 darija manquantes (les 6 touches après-devis, `reveil_a1/a3/b`, `avis_google`,
`parrainage`) sont traduites ci-dessus : `CLES_RELANCE` a désormais 27/27 clés avec un équivalent darija. Comme
`visite_proposition`/`visite_confirmation`, ces 11 traductions n'ont PAS encore reçu la relecture native du
04/09/2026 (CADM1 — à faire avant tout envoi réel) ; elles suivent le FR validé phrase par phrase (aucune promesse
ajoutée, aucun chiffre, aucune traduction automatique).
