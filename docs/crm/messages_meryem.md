# Messages de Meryem — textes validés (Guide v2.1 + Protocole de rappel v3, 04/09/2026)

Source de vérité des gabarits `parametres.MessageTemplate` que MRY12 seed dans `MESSAGE_TEMPLATE_DEFAULTS`
(`corps_fr` = colonne FR ; `corps_darija` = colonne darija, écriture arabe, revue native le 04/09/2026).
Règles : aucun chiffre qui ne vienne du devis ou du lead ; placeholders autorisés `{civilite} {nom} {prenom} {ville}
{reference} {lien} {lien_rdv} {date_validite} {conseiller}` ; le crochet `[…]` des textes ci-dessous devient le
placeholder correspondant au seed (`[Prénom]` → `{prenom}`, `[date]` → `{date_validite}`, `[référence]` →
`{reference}`, `[lien …]` → `{lien}`) ; ce qui n'a pas de placeholder (montant, raison réelle, jour/heure de rappel)
reste à saisir par Meryem au moment de l'envoi — jamais un défaut. Une phrase dont le placeholder est vide est OMISE
au rendu (MRY13).

## Cadence « contact » (Protocole v3, chapitre 5)

### identite — J0, WhatsApp, dans les cinq minutes (M1)
FR : Bonjour [Prénom], je suis Meryem de TAQINOR Solutions. Vous venez de nous laisser une demande pour le solaire, merci. Je vous appelle dans quelques minutes pour une première estimation ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.
DARIJA : السلام عليكم [الاسم]، أنا مريم من TAQINOR Solutions. وصلنا الطلب ديالكم على الطاقة الشمسية، شكرا. غادي نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير أولي. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.

### appel_ouverture — J0, script d'ouverture de l'appel n° 1 (A1)
FR : Bonjour [Prénom], Meryem de TAQINOR Solutions. Vous venez de remplir notre formulaire pour le solaire. Je vous dérange deux minutes ?
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR Solutions. عمرتو دابا الفورم ديالنا على الطاقة الشمسية. نقدر ناخد منكم جوج دقايق؟

### repondeur — appels 2 et 4, message sur répondeur (R1)
FR : Bonjour [Prénom], Meryem de TAQINOR. Je vous appelle au sujet de votre demande solaire. Je vous envoie un message WhatsApp, répondez-y quand vous voulez. Bonne journée.
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. كنعيط ليكم بخصوص الطلب ديالكم على الطاقة الشمسية. غادي نصيفط ليكم رسالة على الواتساب، جاوبو فوقاش ما بغيتو. نهاركم مبروك.

### valeur_j1 — J1, WhatsApp de valeur (M2)
FR : Bonjour [Prénom], je n'ai pas réussi à vous joindre. Pour que l'estimation soit juste, j'ai besoin de votre facture (une photo suffit) et de votre adresse : je vous montre vos panneaux posés sur votre toit, avec l'économie estimée. Quel moment vous arrange pour un appel de cinq minutes ?
DARIJA : السلام عليكم [الاسم]، حاولت نعيط ليكم ولكن ما لقيتكمش. باش يكون التقدير مضبوط، خاصني غير تصويرة ديال فاتورة الضو والعنوان ديالكم، ونوريكم كيفاش غادي يجيو الألواح فوق السطح ديالكم مع شحال غادي توفرو ف الفاتورة. شمن وقت يناسبكم باش نعيط ليكم خمس دقايق؟

### vocal_j3 — J3, vocal WhatsApp de trente secondes (M3, script à dire)
FR : Bonjour [Prénom], c'est Meryem de TAQINOR. Je vous ai laissé deux messages, je ne veux pas insister : dites-moi juste si le projet est toujours d'actualité, et à quelle heure je peux vous appeler. Bonne journée.
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. صيفطت ليكم جوج رسائل وما بغيتش نثقل عليكم. غير قولوا ليا واش مشروع الطاقة الشمسية مازال كيهمكم، وفوقاش نقدر نعيط ليكم. نهاركم مبروك.

### appel_dimanche — 5e appel, le dimanche 16 h–19 h, pour les injoignables (A3)
FR : Bonjour [Prénom], Meryem de TAQINOR. Je me permets de vous appeler un dimanche parce que je ne vous trouve pas en semaine. Je ne vous retiens pas : votre demande solaire est-elle toujours d'actualité ?
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. سمحو ليا كنعيط ليكم نهار الحد، حيت ف الأسبوع ما كنلقاكمش. ما غاديش نطول عليكم: واش الطلب ديالكم على الطاقة الشمسية مازال كيهمكم؟

### je_classe_j7 — J7, WhatsApp « je classe ? » (M4)
FR : Bonjour [Prénom], Meryem de TAQINOR. Sans nouvelle de votre part, je mets votre demande de côté dans trois jours. Un simple « plus tard » me suffit pour la garder ouverte.
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. إلا ما جاوبتونيش، غادي نحط الطلب ديالكم على جنب من هنا لتلت أيام. كلمة «من بعد» كافية باش نخلي الطلب ديالكم محلول.

### cloture_j14 — J14, WhatsApp de clôture, passage en Froid (M5)
FR : Bonjour [Prénom], Meryem de TAQINOR. Je classe votre demande pour ne pas vous déranger. Si vous souhaitez reprendre plus tard, ce message suffit : je vous prépare l'étude en 24 h.
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. غادي نسد الطلب ديالكم باش ما نزعجكمش. إلا بغيتو ترجعو للمشروع من بعد، صيفطو ليا غير هاد الرسالة ونوجد ليكم الدراسة ف 24 ساعة.

### reveil_a2 — J30 puis J60, réveil des leads jamais chiffrés (M6)
FR : Bonjour [Prénom], Meryem de TAQINOR. Il y a un mois, vous vous renseigniez sur le solaire. Si le projet revient d'actualité, je reprends votre dossier là où on l'a laissé : une photo de votre dernière facture, et je vous envoie l'estimation à jour.
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. هادي شهر كنتو كتسولو على الطاقة الشمسية. إلا رجع المشروع كيهمكم، غادي نكمل الملف ديالكم من فين وقفنا: تصويرة ديال آخر فاتورة، وغادي نصيفط ليكم التقدير الجديد.

### rappel_plus_tard — réponse à « rappelez-moi plus tard » (M9)
FR : Très bien, je vous rappelle [jour] à [heure]. D'ici là, si vous avez votre facture sous la main, une photo m'aide à préparer l'estimation.
DARIJA : واخا، غادي نعيط ليكم [النهار] على [الساعة]. وحتى لذاك الوقت، إلا كانت الفاتورة عندكم، تصويرة ديالها غادي تعاونني نوجد التقدير.

### stop_contact — réponse à « ne me rappelez plus » (M10)
FR : Compris, je ne vous rappellerai plus. Je vous laisse simplement ce numéro si un jour le projet revient. Bonne journée.
DARIJA : واخا، فهمتكم، ما غاديش نعاود نعيط ليكم. غير كنخلي ليكم هاد الرقم إلا شي نهار رجع المشروع. نهاركم مبروك.

## Cadence « après devis » (Guide v2.1, chapitre 7) et dimanche

### j1_pdf — J1, WhatsApp
FR : Le PDF s'ouvre bien ? Qu'est-ce qui vous a le plus parlé ?

### j4_preuve — J4, WhatsApp (la vue de SON toit avec les panneaux, ou la photo d'un chantier comparable)
FR : Voici une installation comparable à la vôtre, posée en [mois] à [ville] ; le suivi de production est en temps réel, je peux vous montrer.

### j6_garanties — J6, WhatsApp (avec les certificats de garantie des fabricants)
FR : Ces garanties sont accordées par les fabricants : elles restent valables quoi qu'il arrive.

### j9_validite — J9, WhatsApp
FR : Votre proposition est valable jusqu'au [date]. Après, je dois revalider les prix et la disponibilité du matériel : ce n'est pas pour vous presser, c'est pour ne pas vous annoncer un prix faux.

### j13_dernier — J13, WhatsApp
FR : Je ne veux pas insister : dites-moi si le projet est toujours d'actualité, et si non, je vous laisse tranquille.

### j14_pause — J14, WhatsApp, passage en Froid
FR : Je mets votre dossier en pause. Votre proposition reste dans notre système ; un message suffit pour la réactiver.

### dimanche_famille — premier dimanche 16 h après J3, leads « Décision à plusieurs » (M7)
FR : Bonjour [Prénom], Meryem de TAQINOR. Je sais que la décision se prend en famille. Si vous en parlez ce week-end, je peux vous envoyer la page résumé (une page, les chiffres clés) pour la partager, ou vous appeler à deux ou trois dimanche après 17 h, comme vous préférez.
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. عارفة بلي القرار كيتاخد مع العائلة. إلا غادي تهضرو عليه هاد الويكاند، نقدر نصيفط ليكم ورقة الملخص (صفحة وحدة فيها الأرقام المهمة) باش تشاركوها، ولا نعيط ليكم نهار الحد من بعد 5 ديال العشية وتكونو جوج ولا تلاتة، كيف ما بغيتو.

### annonce_appel_reda — le vendredi, annoncer l'appel de Reda du dimanche (M11)
FR : Bonjour [Prénom], Meryem de TAQINOR. Reda, le fondateur, qui valide chaque étude, aimerait vous appeler dimanche vers 18 h pour répondre à vos questions en cinq minutes. Ça vous convient, ou préférez-vous un autre moment ?
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. رضا، المؤسس ديال الشركة اللي كيراجع كل دراسة، بغا يعيط ليكم نهار الحد على 6 ديال العشية باش يجاوب على الأسئلة ديالكم ف خمس دقايق. واش مناسب ليكم، ولا كتفضلو وقت آخر؟

### offre_reda — après la décision de Reda seulement, jamais avant (M8)
FR : Bonjour [Prénom], Meryem de TAQINOR. Suite à votre échange avec Reda : [la raison réelle], il vous accorde [montant en dirhams] sur la proposition n° [référence], soit [nouveau total TTC]. Cette proposition est valable jusqu'à mardi 18 h ; ensuite le prix normal reprend. Je reste disponible pour toute question.
DARIJA : السلام عليكم [الاسم]، مريم من TAQINOR. بعد الهضرة ديالكم مع رضا: [السبب الحقيقي]، نقص ليكم [المبلغ بالدرهم] من العرض رقم [المرجع]، يعني [المجموع الجديد TTC]. هاد العرض صالح حتى الثلاثاء على 6 ديال العشية، ومن بعد كيرجع الثمن العادي. إلا كان عندكم شي سؤال أنا هنا.

### reveil_a1 — dormants avec devis (A1 du Guide)
FR : Bonjour [prénom], c'est Meryem de Taqinor Solutions. Vous aviez reçu un devis solaire chez nous il y a quelques mois. Du nouveau depuis : on peut maintenant vous montrer vos panneaux posés sur VOTRE toit, en 3D, avec l'estimation à jour de vos économies. Je vous prépare la vue et je vous l'envoie ici — c'est gratuit, sans engagement. Je me lance ? (Je dois juste confirmer votre adresse.)

### reveil_a3 — dernière chance, la rupture honnête (A3 du Guide)
FR : Bonjour [prénom], Meryem de Taqinor Solutions. Je ne veux pas insister : si le projet n'est plus d'actualité, je ferme votre dossier, aucun souci. Avant ça, une dernière chose qui aide souvent à décider : je peux vous envoyer la vue 3D de vos panneaux sur votre toit, avec l'estimation à jour. Je vous la prépare, ou je classe le dossier ?

### reveil_b — la saison des factures (B du Guide)
FR : Bonjour [prénom], c'est Meryem de Taqinor Solutions. C'est la saison des factures d'été — souvent le moment où le solaire se décide. Votre projet est-il toujours d'actualité ? Si oui, je vous prépare une estimation à jour de vos économies, sans engagement. On en parle ?

## Après la signature (Guide v2.1, chapitre 13)

### avis_google — à tous les clients, de la même façon, sans contrepartie
FR : Bonjour [Prénom], j'espère que l'installation vous donne satisfaction. Si vous avez deux minutes, un avis sur Google nous aide énormément, c'est ce que regardent les futurs clients : [lien de la fiche TAQINOR]. Merci beaucoup !

### parrainage
FR : Si quelqu'un autour de vous, un voisin, un frère, un collègue, réfléchit au solaire, vous pouvez lui envoyer votre lien de parrainage ; il aura la même étude gratuite, et on convient ensemble d'une récompense pour vous.

## Sans texte validé (ne PAS seeder — à rédiger par Reda/Meryem avant tout usage)
visite_veille, visite_matin, apres_visite : aucun texte validé n'existe dans le Guide v2.1 ni dans le Protocole v3.
Les versions darija absentes ci-dessus (après devis, réveils A1/A3/B, après signature) retombent sur le FR (`get_corps`).
