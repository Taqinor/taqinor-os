"""Modèles de message WhatsApp éditables (``MessageTemplate``).

Domaine « Messages & relances ». Extrait de l'ancien ``models.py`` sans aucun
changement de champ, de ``Meta`` ou de nom de table — la table reste
``parametres_messagetemplate`` (split sans migration)."""
from django.db import models


# Modèles de message WhatsApp éditables (Paramètres → Messages). Placeholders
# supportés : {civilite} {nom} {reference} {lien} {n}. Le défaut s'applique tant
# que l'entreprise n'a pas enregistré sa propre version (rien ne change sinon).
MESSAGE_TEMPLATE_DEFAULTS = {
    'devis_unique':
        'Bonjour {civilite} {nom}, voici votre devis Taqinor '
        '({reference}) : {lien}',
    'devis_multi_entete':
        'Bonjour {civilite} {nom}, voici vos {n} devis Taqinor :',
    'devis_multi_ligne':
        '{reference} : {lien}',
    'facture':
        'Bonjour {civilite} {nom}, voici votre facture Taqinor '
        '({reference}) : {lien}',
    'relance':
        'Bonjour {civilite} {nom}, petit rappel concernant votre facture '
        'Taqinor ({reference}) : {lien}',
    # XSAV4 — transitions de ticket SAV (client). {lien} = lien-client FG86.
    'ticket_recu':
        'Bonjour {civilite} {nom}, votre ticket SAV {reference} a bien été '
        'reçu par notre équipe. Suivi : {lien}',
    'ticket_planifie':
        'Bonjour {civilite} {nom}, votre intervention {reference} est '
        'planifiée. Suivi : {lien}',
    'ticket_resolu':
        'Bonjour {civilite} {nom}, votre ticket SAV {reference} a été '
        'résolu. Suivi : {lien}',
    # XSTK22 — notifications client aux transitions de livraison.
    'livraison_en_transit':
        'Bonjour {civilite} {nom}, votre matériel {reference} est en route '
        'vers votre chantier. Suivi : {lien}',
    'livraison_livree':
        'Bonjour {civilite} {nom}, votre matériel {reference} a été livré '
        'sur votre chantier. Suivi : {lien}',
    # XFSM6 — rappel client J-1 (intervention planifiée demain, non confirmée).
    'rappel_rdv':
        'Bonjour {civilite} {nom}, petit rappel : notre équipe est prévue '
        'chez vous demain pour {reference}. Merci de confirmer : {lien}',
}


# ── MRY12 — Textes du moteur de relances de Meryem ──────────────────────────
# SOURCE DE VÉRITÉ : `docs/crm/messages_meryem.md` (Guide v2.1 + Protocole de
# rappel v3, validés par le fondateur). Ces textes sont COPIÉS de ce fichier,
# jamais réécrits ; `tests_mry12_messages_relance.py` re-dérive le fichier et
# casse à la moindre divergence. Les crochets convertis en placeholders sont
# ceux que son en-tête autorise ([Prénom]→{prenom}, [date]→{date_validite},
# [référence]→{reference}, [lien …]→{lien}) ; TOUT autre crochet reste un
# crochet — montant, raison réelle, jour et heure de rappel se saisissent à
# la main, jamais un défaut inventé. Aucun chiffre n'est un placeholder.
MESSAGE_TEMPLATE_DEFAULTS.update({
    'identite':
        "Bonjour {civilite} {prenom}, je suis {conseiller} de {marque}. Vous venez de nous laisser une demande pour le solaire, merci. Je vous appelle dans quelques minutes pour une première estimation ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.",
    # CAD109 (21/09/2026) — loi 31-08 art. 51 : un démarchage téléphonique
    # doit indiquer explicitement l'identité ET le caractère commercial de
    # l'intervention (sanctionné par l'art. 180) ; loi 09-08 art. 5 §3 +
    # décret 2-09-165 art. 34 : pour des données non collectées auprès de la
    # personne (Meta, Odoo), l'information sur leur origine peut être donnée
    # oralement. La « confirmation écrite de l'offre » qu'exige l'art. 51
    # est déjà assurée par le devis envoyé — une phrase courte suffit ici,
    # pas un pavé dans le WhatsApp.
    'appel_ouverture':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque} — c'est un appel commercial. Vous venez de remplir notre formulaire pour le solaire ; vous pouvez me demander à tout moment d'où viennent vos coordonnées. Je vous dérange deux minutes ?",
    'repondeur':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je vous appelle au sujet de votre demande solaire. Je vous envoie un message WhatsApp, répondez-y quand vous voulez. Bonne journée.",
    'valeur_j1':
        "Bonjour {civilite} {prenom}, je n'ai pas réussi à vous joindre. Pour que l'estimation soit juste, j'ai besoin de votre facture (une photo suffit) et de votre adresse : je vous montre vos panneaux posés sur votre toit, avec l'économie estimée. Quel moment vous arrange pour un appel de cinq minutes ?",
    'vocal_j3':
        "Bonjour {civilite} {prenom}, c'est {conseiller} de {marque}. Je vous ai laissé deux messages, je ne veux pas insister : dites-moi juste si le projet est toujours d'actualité, et à quelle heure je peux vous appeler. Bonne journée.",
    # CAD109 — même mention que `appel_ouverture` (loi 31-08 art. 51 +
    # loi 09-08 art. 5 §3), sur le second script d'appel EN DIRECT
    # (`repondeur`/`vocal_j3` restent des scripts de répondeur/vocal, pas des
    # ouvertures de conversation).
    'appel_dimanche':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque} — c'est un appel commercial. Je me permets de vous appeler un dimanche parce que je ne vous trouve pas en semaine ; vous pouvez me demander à tout moment d'où viennent vos coordonnées. Je ne vous retiens pas : votre demande solaire est-elle toujours d'actualité ?",
    # CAD66 (21/09/2026) — « dans trois jours » promettait une clôture à J10 ;
    # le moteur clôture réellement à J14 (`cloture_j14`), donc « dans une
    # semaine » depuis J7. Aucun barreau déplacé, seul le mot change.
    # CAD110 (21/09/2026) — loi 09-08 art. 10 al. 5 : l'exception de
    # prospection exige une opposition possible « chaque fois qu'un
    # courrier […] est adressé » et des coordonnées valables pour faire
    # cesser — l'envoi manuel ne protège de rien (l'article vise le MOYEN
    # et le consentement, pas la main humaine). Porte de sortie ajoutée aux
    # touches qui portent le plus loin (J7, J14, fin d'après-devis, tous
    # les réveils) — pas aux trois premiers messages (garde-fou : ne pas
    # alourdir le début, c'est le suivi long qui expose).
    'je_classe_j7':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Sans nouvelle de votre part, je mets votre demande de côté dans une semaine. Un simple « plus tard » me suffit pour la garder ouverte. Répondez STOP et je n'insiste plus.",
    'cloture_j14':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je classe votre demande pour ne pas vous déranger. Si vous souhaitez reprendre plus tard, ce message suffit : je vous prépare l'étude en 24 h. Répondez STOP et je n'insiste plus.",
    'reveil_a2':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Il y a un mois, vous vous renseigniez sur le solaire. Si le projet revient d'actualité, je reprends votre dossier là où on l'a laissé : une photo de votre dernière facture, et je vous envoie l'estimation à jour. Répondez STOP et je n'insiste plus.",
    'rappel_plus_tard':
        "Très bien, je vous rappelle [jour] à [heure]. D'ici là, si vous avez votre facture sous la main, une photo m'aide à préparer l'estimation.",
    'stop_contact':
        "Compris, je ne vous rappellerai plus. Je vous laisse simplement ce numéro si un jour le projet revient. Bonne journée.",
    # 09/09/2026 — réchauffé sur ordre fondateur (« ce message whatsapp est un
    # peu froid ») : c'était la SEULE touche du guide sans salutation ni
    # prénom. Même voix que le reste (vouvoiement, chaleur sobre, zéro
    # chiffre) ; le fichier source docs/crm/messages_meryem.md porte le même
    # texte (tests_mry12 re-dérive et compare).
    'j1_pdf':
        "Bonjour {civilite} {prenom}, j'espère que vous allez bien. Je vous ai "
        "envoyé votre proposition solaire — est-ce que le PDF s'ouvre bien "
        "de votre côté ? Prenez le temps de la regarder tranquillement, et "
        "dites-moi ce qui vous a le plus parlé. Je suis là pour la moindre "
        "question.",
    'j4_preuve':
        "Voici une installation comparable à la vôtre, posée en {mois_preuve} à {ville_preuve} : {lien_preuve}. Puissance installée : {puissance_preuve} kWc. Le suivi de production est en temps réel, je peux vous montrer. Petite vidéo du chantier : {lien_video_preuve}.",
    'j6_garanties':
        "Ces garanties sont accordées par les fabricants : elles restent valables quoi qu'il arrive. Le détail par équipement est dans votre proposition : {lien}. Ce qui est couvert et pour combien d'années : https://taqinor.ma/garanties",
    'j9_validite':
        "Votre proposition est valable jusqu'au {date_validite}. Après, je dois revalider les prix et la disponibilité du matériel : ce n'est pas pour vous presser, c'est pour ne pas vous annoncer un prix faux.",
    # CAD110 — porte de sortie (voir la note au-dessus de `je_classe_j7`) :
    # les deux DERNIÈRES touches après-devis, celles qui portent le plus
    # loin dans le suivi.
    'j13_dernier':
        "Je ne veux pas insister : dites-moi si le projet est toujours d'actualité, et si non, je vous laisse tranquille. Répondez STOP et je n'insiste plus.",
    'j14_pause':
        "Je mets votre dossier en pause. Votre proposition reste dans notre système ; un message suffit pour la réactiver. Répondez STOP et je n'insiste plus.",
    'dimanche_famille':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je sais que la décision se prend en famille. Si vous en parlez ce week-end, je peux vous envoyer la page résumé (une page, les chiffres clés) pour la partager, ou vous appeler à deux ou trois dimanche après 17 h, comme vous préférez.",
    # CAD60 (21/09/2026) — ENVOI MANUEL, HORS CADENCE, APRÈS LA DÉCISION DU
    # FONDATEUR. Ces deux textes ne sont portés par AUCUN des barreaux
    # après-devis et ne le seront pas : `offre_reda` contient trois blancs
    # ([la raison réelle], [montant en dirhams], [nouveau total TTC]) qui ne
    # sont calculables par rien, et l'appel du fondateur se décide au cas par
    # cas. Ne cherchez pas le bouton : il n'existe pas, et c'est voulu —
    # câbler une touche conditionnelle serait de la sur-ingénierie. Ils se
    # copient depuis le catalogue des messages, au moment choisi.
    'annonce_appel_reda':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Le fondateur, qui valide chaque étude, aimerait vous appeler dimanche vers 18 h pour répondre à vos questions en cinq minutes. Ça vous convient, ou préférez-vous un autre moment ?",
    'offre_reda':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Suite à votre échange avec le fondateur : [la raison réelle], il vous accorde [montant en dirhams] sur la proposition n° {reference}, soit [nouveau total TTC]. Cette proposition est valable jusqu'à mardi 18 h ; ensuite le prix normal reprend. Je reste disponible pour toute question.",
    # CAD73 (21/09/2026) — « il y a quelques mois » était un fait daté FAUX :
    # ce réveil part ~6 semaines après le devis (`cloturer_cadence` démarre
    # la cadence réveil à sa clôture, ~J14, donc reveil_a1 tombe vers J+44),
    # jamais des mois. Reformulé SANS durée plutôt qu'une durée inventée.
    # CAD110 — porte de sortie sur les QUATRE touches de réveil : ce sont
    # les plus lointaines de toute la cadence (J30/J60), donc les plus
    # exposées au regard de l'art. 10 al. 5.
    'reveil_a1':
        "Bonjour {civilite} {prenom}, c'est {conseiller} de {marque}. Vous aviez reçu un devis solaire chez nous. Du nouveau depuis : on peut maintenant vous montrer vos panneaux posés sur VOTRE toit, en 3D, avec l'estimation à jour de vos économies. Je vous prépare la vue et je vous l'envoie ici — c'est gratuit, sans engagement. Je me lance ? (Je dois juste confirmer votre adresse.) Répondez STOP et je n'insiste plus.",
    'reveil_a3':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je ne veux pas insister : si le projet n'est plus d'actualité, je ferme votre dossier, aucun souci. Avant ça, une dernière chose qui aide souvent à décider : je peux vous envoyer la vue 3D de vos panneaux sur votre toit, avec l'estimation à jour. Je vous la prépare, ou je classe le dossier ? Répondez STOP et je n'insiste plus.",
    'reveil_b':
        "Bonjour {civilite} {prenom}, c'est {conseiller} de {marque}. C'est la saison des factures d'été — souvent le moment où le solaire se décide. Votre projet est-il toujours d'actualité ? Si oui, je vous prépare une estimation à jour de vos économies, sans engagement. On en parle ? Répondez STOP et je n'insiste plus.",
    # CAD71 (21/09/2026) — {lien} n'était alimenté que par le devis
    # (`url_proposition`) : ce texte envoyait donc le lien du DEVIS du client
    # à la place d'un lien vers la fiche Google. Placeholder dédié
    # {lien_google}, alimenté par `CompanyProfile.lien_avis_google`.
    'avis_google':
        "Bonjour {civilite} {prenom}, j'espère que l'installation vous donne satisfaction. Si vous avez deux minutes, un avis sur Google nous aide énormément, c'est ce que regardent les futurs clients : {lien_google}. Merci beaucoup !",
    'parrainage':
        "Si quelqu'un autour de vous, un voisin, un frère, un collègue, réfléchit au solaire, vous pouvez lui envoyer votre lien de parrainage ; il aura la même étude gratuite, et on convient ensemble d'une récompense pour vous.",
    # VISITE-CADENCE (textes validés par le fondateur, 15/09/2026) — LA VISITE
    # TECHNIQUE COMME OUTIL DE CLOSING. Doctrine : elle se PROPOSE après
    # l'envoi du devis, quand le client est chaud, et elle se CONFIRME la
    # veille. Zéro chiffre, zéro promesse, aucun prénom codé en dur
    # ({conseiller} = le responsable du lead). La phrase portant
    # {date_visite} est OMISE (MRY13) quand aucune date n'est posée sur la
    # fiche — jamais un crochet vide envoyé au client.
    'visite_proposition':
        "Pour verrouiller votre proposition, on peut passer chez vous pour la vérification technique gratuite : le technicien confirme l'orientation du toit, la charpente et le tableau électrique, et répond à toutes vos questions sur place. Ça ne vous engage à rien. Dites-moi le jour qui vous arrange cette semaine et je bloque le créneau. — {conseiller}",
    # Ordre fondateur du 15/09/2026 : la visite ne se fait qu'avec le VRAI
    # client présent — jamais le gardien ni la bonne. La phrase le demande sans
    # le dire de façon blessante : elle donne la RAISON (« répondre à toutes
    # vos questions »), qui est aussi la vraie valeur du passage.
    'visite_confirmation':
        "Bonjour, on confirme la visite technique prévue {date_visite} chez vous. Le technicien vérifie le toit, la charpente et le tableau électrique — prévoyez l'accès au compteur. Votre présence est importante : c'est l'occasion de répondre à toutes vos questions sur place. En cas d'empêchement, répondez-moi ici et on recale le passage. — {conseiller}",
    # CAD67 (21/09/2026) — deux appels de la cadence contact n'avaient aucune
    # phrase d'ouverture (`apps/parametres/models_relance.py` ordre 4 et 10).
    # `appel_relance` (Appel 3, J1 10:30) : troisième tentative, ton court
    # comme `appel_ouverture`/`vocal_j3`/`appel_dimanche`. `appel_dernier`
    # (Appel 6, dernier avant clôture J14) : celui qui décide du classement.
    # CAD96 (21/09/2026, fold post-merge) — {marque} plutôt que « TAQINOR »
    # codé en dur (même règle que le reste du catalogue, garde SCA29).
    'appel_relance':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je reviens vers vous pour votre demande solaire d'hier — vous avez deux minutes maintenant ?",
    'appel_dernier':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Dernier essai avant de classer votre demande : votre projet solaire est-il toujours d'actualité ?",
    # CAD98 (23/09/2026) — les trois « Appel de suivi » de la cadence après
    # devis (`apps/parametres/models_relance.py` ordres 2, 6 et 8 : J2, J7,
    # J11) n'avaient aucun script. Trois scripts courts, sur le patron de
    # CAD67 : le client connaît déjà le dossier, on ouvre sur SA proposition
    # et on pose une question. Zéro chiffre, aucune promesse de date (la
    # validité est dite par `j9_validite`, la clôture par `j13_dernier`), ni
    # « dernier appel » — le réveil J30 est encore un appel (CAD74).
    'appel_suivi_j2':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je vous appelle au sujet de la proposition solaire que je vous ai envoyée : avez-vous pu la regarder ? Dites-moi ce qui vous paraît clair et ce qui mérite une explication.",
    'appel_suivi_j7':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je reviens vers vous au sujet de votre proposition solaire : qu'est-ce qui reste à éclaircir avant de décider ? Si un point vous freine, le budget, la pose ou le calendrier, on le regarde ensemble.",
    'appel_suivi_j11':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je fais le point avec vous sur votre proposition solaire : où en est votre réflexion ? S'il vous faut plus de temps ou d'autres informations, dites-le-moi simplement.",
    # CAD125 (21/09/2026) — LE DOSSIER INSTITUTIONNEL, ENFIN UNE PAROLE.
    # `Lead.regularisation_8221` est capté et LU par le scoring, mais par
    # aucune logique de message : aucune des clés de relance ne parlait d'une
    # subvention ni d'un dossier institutionnel, alors que le résidentiel a
    # son équivalent avec `j6_garanties`. Ces deux textes sont posés par un
    # playbook conditionné sur `{type_installation}` — zéro migration de
    # cadence, zéro barreau ajouté.
    # GARDE-FOU « zéro chiffre inventé » : AUCUN montant, AUCUN plafond,
    # AUCUNE fenêtre de dépôt, AUCUN nombre de régimes. Le plafond FDA et la
    # fenêtre de dépôt cités au round 2 sont INTROUVABLES sur leur source et
    # ne doivent jamais réapparaître ici ; « trois régimes » 82-21 n'est pas
    # sourcé non plus. On pose LA question, le client apporte les chiffres.
    'dossier_8221':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Une question sur votre projet : où en est votre dossier d'autoproduction (loi 82-21) ? Selon l'étape où vous en êtes, on adapte l'étude et le calendrier de raccordement — et si le dossier n'est pas encore lancé, je vous explique les étapes en cinq minutes.",
    'dossier_fda':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Une question sur votre projet de pompage : avez-vous déposé un dossier de subvention agricole (FDA), ou comptez-vous le faire ? Cela change le calendrier et les pièces à préparer — dites-moi où vous en êtes et je cale l'étude dessus.",
})

# Variantes darija (écriture arabe, revue native le 04/09/2026). Une clé
# ABSENTE d'ici retombe sur le FR (`get_corps`) — jamais une traduction
# automatique.
MESSAGE_TEMPLATE_DEFAULTS_DARIJA = {
    'identite':
        "السلام عليكم {civilite} {prenom}، أنا {conseiller} من {marque}. وصلنا الطلب ديالكم على الطاقة الشمسية، شكرا. غادي نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير أولي. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.",
    'appel_ouverture':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque} — هادا اتصال تجاري. عمرتو دابا الفورم ديالنا على الطاقة الشمسية؛ تقدرو تسولوني فأي وقت منين جاو المعلومات ديالكم. نقدر ناخد منكم جوج دقايق؟",
    'repondeur':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. كنعيط ليكم بخصوص الطلب ديالكم على الطاقة الشمسية. غادي نصيفط ليكم رسالة على الواتساب، جاوبو فوقاش ما بغيتو. نهاركم مبروك.",
    'valeur_j1':
        "السلام عليكم {civilite} {prenom}، حاولت نعيط ليكم ولكن ما لقيتكمش. باش يكون التقدير مضبوط، خاصني غير تصويرة ديال فاتورة الضو والعنوان ديالكم، ونوريكم كيفاش غادي يجيو الألواح فوق السطح ديالكم مع شحال غادي توفرو ف الفاتورة. شمن وقت يناسبكم باش نعيط ليكم خمس دقايق؟",
    'vocal_j3':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. صيفطت ليكم جوج رسائل وما بغيتش نثقل عليكم. غير قولوا ليا واش مشروع الطاقة الشمسية مازال كيهمكم، وفوقاش نقدر نعيط ليكم. نهاركم مبروك.",
    'appel_dimanche':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque} — هادا اتصال تجاري. سمحو ليا كنعيط ليكم نهار الحد، حيت ف الأسبوع ما كنلقاكمش؛ تقدرو تسولوني فأي وقت منين جاو المعلومات ديالكم. ما غاديش نطول عليكم: واش الطلب ديالكم على الطاقة الشمسية مازال كيهمكم؟",
    # CAD110 (21/09/2026) — même porte de sortie que côté FR (voir la note
    # au-dessus de `je_classe_j7` FR) : « جاوبو STOP وما نلحوش عليكم » =
    # « répondez STOP et je n'insiste plus ».
    'je_classe_j7':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. إلا ما جاوبتونيش، غادي نحط الطلب ديالكم على جنب من هنا لأسبوع. كلمة «من بعد» كافية باش نخلي الطلب ديالكم محلول. جاوبو STOP وما نلحوش عليكم.",
    'cloture_j14':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. غادي نسد الطلب ديالكم باش ما نزعجكمش. إلا بغيتو ترجعو للمشروع من بعد، صيفطو ليا غير هاد الرسالة ونوجد ليكم الدراسة ف 24 ساعة. جاوبو STOP وما نلحوش عليكم.",
    'reveil_a2':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. هادي شهر كنتو كتسولو على الطاقة الشمسية. إلا رجع المشروع كيهمكم، غادي نكمل الملف ديالكم من فين وقفنا: تصويرة ديال آخر فاتورة، وغادي نصيفط ليكم التقدير الجديد. جاوبو STOP وما نلحوش عليكم.",
    'rappel_plus_tard':
        "واخا، غادي نعيط ليكم [النهار] على [الساعة]. وحتى لذاك الوقت، إلا كانت الفاتورة عندكم، تصويرة ديالها غادي تعاونني نوجد التقدير.",
    'stop_contact':
        "واخا، فهمتكم، ما غاديش نعاود نعيط ليكم. غير كنخلي ليكم هاد الرقم إلا شي نهار رجع المشروع. نهاركم مبروك.",
    'dimanche_famille':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. عارفة بلي القرار كيتاخد مع العائلة. إلا غادي تهضرو عليه هاد الويكاند، نقدر نصيفط ليكم ورقة الملخص (صفحة وحدة فيها الأرقام المهمة) باش تشاركوها، ولا نعيط ليكم نهار الحد من بعد 5 ديال العشية وتكونو جوج ولا تلاتة، كيف ما بغيتو.",
    'annonce_appel_reda':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. المؤسس ديال الشركة اللي كيراجع كل دراسة بغا يعيط ليكم نهار الحد على 6 ديال العشية باش يجاوب على الأسئلة ديالكم ف خمس دقايق. واش مناسب ليكم، ولا كتفضلو وقت آخر؟",
    'offre_reda':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. بعد الهضرة ديالكم مع المؤسس: [السبب الحقيقي]، نقص ليكم [المبلغ بالدرهم] من العرض رقم {reference}، يعني [المجموع الجديد TTC]. هاد العرض صالح حتى الثلاثاء على 6 ديال العشية، ومن بعد كيرجع الثمن العادي. إلا كان عندكم شي سؤال أنا هنا.",
    # VISITE-CADENCE — darija à faire relire par un locuteur natif (fondateur) :
    # ces deux textes suivent le FR validé phrase par phrase (aucune promesse
    # ajoutée, aucun chiffre) mais n'ont PAS encore reçu la relecture native du
    # 04/09/2026 dont bénéficient les clés au-dessus.
    'visite_proposition':
        "باش نثبتو ليكم العرض، نقدرو نجيو عندكم لزيارة تقنية بلا فلوس: التقني كيتأكد من الاتجاه ديال السطح، من الهيكل ومن الطابلو ديال الضو، وكيجاوب على كل الأسئلة ديالكم فعين المكان. ما كتلزمكم بوالو. قولوا ليا شمن نهار يناسبكم هاد السيمانة ونحجز ليكم الوقت. — {conseiller}",
    'visite_confirmation':
        "السلام عليكم، كنأكدو ليكم الزيارة التقنية المبرمجة {date_visite} عندكم. التقني غادي يشوف السطح، الهيكل والطابلو ديال الضو — وجدو ليه الوصول للكونتور. الحضور ديالكم مهم: هي الفرصة باش نجاوبو على جميع الأسئلة ديالكم فعين المكان. إلا طرا ليكم شي مانع، جاوبوني هنا ونعاودو نبرمجو الزيارة. — {conseiller}",
    # CAD-F — CAD67 (21/09/2026) — darija des deux nouveaux scripts d'appel.
    # CAD96 (fold post-merge) — {marque} plutôt que « TAQINOR » codé en dur.
    'appel_relance':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. كنرجع ليكم بخصوص الطلب ديالكم ديال البارح — عندكم جوج دقايق دابا؟",
    'appel_dernier':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. هادي آخر محاولة قبل ما نسد الطلب ديالكم: واش مشروع الطاقة الشمسية ديالكم مازال كيهمكم؟",
    # CAD98 (23/09/2026) — darija des trois scripts d'appel de suivi après
    # devis. Traduction phrase par phrase du FR (aucune promesse ajoutée,
    # aucun chiffre, jamais une traduction automatique), PAS ENCORE relue par
    # un locuteur natif (CADM1, à faire avant tout usage réel).
    'appel_suivi_j2':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. كنعيط ليكم بخصوص العرض ديال الطاقة الشمسية اللي صيفطت ليكم: واش قدرتو تشوفوه؟ قولوا ليا شنو اللي واضح ليكم وشنو اللي خاصو شرح.",
    'appel_suivi_j7':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. كنرجع ليكم بخصوص العرض ديال الطاقة الشمسية ديالكم: شنو باقي خاصو يتوضح قبل ما تقررو؟ إلا كانت شي نقطة مخلياكم مترددين، الميزانية، التركيب ولا الوقت، نشوفوها مع بعضياتنا.",
    'appel_suivi_j11':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. بغيت نديرو النقطة معاكم على العرض ديال الطاقة الشمسية ديالكم: فين وصلتو ف التفكير؟ إلا خاصكم شي وقت زايد ولا شي معلومات أخرى، غير قولوها ليا بلا حرج.",
    # CAD-F — CAD62 (21/09/2026) — les 11 clés qui manquaient au repli darija de
    # la marche après-devis, du réveil et de l'après-signature. Même patron que
    # `visite_proposition`/`visite_confirmation` ci-dessus : traduction phrase
    # par phrase du FR validé (aucune promesse ajoutée, aucun chiffre, jamais
    # une traduction automatique), source dans
    # `docs/crm/messages_meryem.md` — mais PAS ENCORE relues par un locuteur
    # natif (CADM1, à faire avant tout envoi réel, comme les deux clés visite).
    'j1_pdf':
        "السلام عليكم {civilite} {prenom}، كنتمنى تكونو بخير. صيفطت ليكم العرض ديال الطاقة الشمسية ديالكم — واش كيحل عندكم مزيان الـ PDF؟ خدو الوقت باش تشوفوه بشوية، وقولوا ليا شنو اللي عجبكم بزاف. أنا هنا لأي سؤال.",
    'j4_preuve':
        "هادي تجهيزة شبيهة بديالكم، تركبات ف {mois_preuve} ف {ville_preuve} : {lien_preuve}. القوة المركبة: {puissance_preuve} kWc. متابعة الإنتاج كاينة ف الوقت الحقيقي، نقدر نوريكم.",
    'j6_garanties':
        "هاد الضمانات كتعطيهم الشركات المصنعة: كيبقاو صالحين ف كل الأحوال. التفاصيل ديال كل معدة كاينة ف العرض ديالكم: {lien}. شنو المغطى وشحال ديال السنين: https://taqinor.ma/garanties",
    'j9_validite':
        "العرض ديالكم صالح حتى {date_validite}. من بعد، خاصني نعاود نتأكد من الأثمنة وتوفر المعدات: ماشي باش نضغط عليكم، باش ما نعطيكمش ثمن غير صحيح.",
    # CAD110 — porte de sortie sur les deux dernières touches après-devis.
    'j13_dernier':
        "ما بغيتش نلح عليكم: قولوا ليا واش المشروع مازال كيهمكم، وإلا لا، نخليكم ف حالكم. جاوبو STOP وما نلحوش عليكم.",
    'j14_pause':
        "غادي نحط الملف ديالكم فالوقفة. العرض ديالكم كيبقى محفوظ عندنا؛ رسالة وحدة كافية باش نرجعو نفعلوه. جاوبو STOP وما نلحوش عليكم.",
    # CAD110 — porte de sortie sur les QUATRE touches de réveil.
    # CAD96 (fold post-merge) — {marque} plutôt que « Taqinor Solutions »
    # codé en dur (même règle que le reste du catalogue, garde SCA29).
    'reveil_a1':
        "السلام عليكم {civilite} {prenom}، أنا {conseiller} من {marque}. كنتو توصلتو بعرض للطاقة الشمسية عندنا. كاين جديد: دابا نقدرو نوريوكم الألواح فوق السطح ديالكم بالضبط، ب 3D، مع تقدير محين ديال التوفير ديالكم. غادي نوجد ليكم الصورة ونصيفطها ليكم هنا — بلاش، بلا ما تلتزمو بوالو. نبدا؟ (خاصني غير نتأكد من العنوان ديالكم.) جاوبو STOP وما نلحوش عليكم.",
    'reveil_a3':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. ما بغيتش نلح: إلا ماشي مازال كيهمكم المشروع، نسد ليكم الملف، بلا مشكل. قبل هادشي، شي حاجة كتعاون بزاف باش تقرر: نقدر نصيفط ليكم الصورة ب 3D ديال الألواح فوق السطح ديالكم، مع تقدير محين. نوجدها ليكم، ولا نسد الملف؟ جاوبو STOP وما نلحوش عليكم.",
    'reveil_b':
        "السلام عليكم {civilite} {prenom}، أنا {conseiller} من {marque}. هادي موسم فواتير الصيف — غالبا هو الوقت اللي فيه كيتقرر مشروع الطاقة الشمسية. واش المشروع ديالكم مازال كيهمكم؟ إلا واخا، نوجد ليكم تقدير محين ديال التوفير، بلا ما تلتزمو بوالو. نهضرو عليه؟ جاوبو STOP وما نلحوش عليكم.",
    'avis_google':
        "السلام عليكم {civilite} {prenom}، كنتمنى تكونو راضيين على التجهيزة. إلا عندكم جوج دقايق، رأي على Google كيعاوننا بزاف، هادشي اللي كيشوفوه الزبناء الجداد: {lien_google}. شكرا بزاف!",
    'parrainage':
        "إلا كان شي واحد حداكم، جار، خو، ولا زميل، كيفكر ف الطاقة الشمسية، تقدرو تصيفطو ليه الرابط ديال الرعاية ديالكم؛ غادي يكون عندو نفس الدراسة بلاش، ونتافقو مع بعضياتنا على مكافأة ليكم.",
    # CAD-F — CAD62 (21/09/2026, complément) — les 7 clés NÉES APRÈS CAD62
    # (CAD125 `dossier_8221`/`dossier_fda`, CAD127 les quatre identités par
    # origine, CAD128 `deuxieme_affaire`). La doctrine CAD62 est « darija
    # COMPLÈTE » : toute clé de `CLES_RELANCE` porte un défaut darija non
    # vide, sinon un lead `langue_preferee='darija'` recevrait du français en
    # silence — et ces 7 clés sont précisément les premiers mots qu'on lui
    # dit. Même patron que les 11 de CAD62 : traduction phrase par phrase du
    # FR validé (aucune promesse ajoutée, aucun chiffre ajouté, jamais une
    # traduction automatique), source dans `docs/crm/messages_meryem.md`, et
    # PAS ENCORE relues par un locuteur natif (CADM1, à faire avant tout
    # envoi réel, comme les deux clés visite et les 11 de CAD62).
    'dossier_8221':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. عندي سؤال على المشروع ديالكم: فين وصل الملف ديالكم ديال الإنتاج الذاتي (قانون 82-21)؟ حسب المرحلة اللي وصلتو ليها، كنلائمو الدراسة والروزنامة ديال الربط — وإلا الملف مازال ما تلانسا، كنشرح ليكم المراحل ف خمس دقايق.",
    'dossier_fda':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. عندي سؤال على المشروع ديال الضخ ديالكم: واش دخّلتو ملف الدعم الفلاحي (FDA)، ولا ناويين تدخّلوه؟ هادشي كيبدل الروزنامة والوثائق اللي خاصكم توجدو — قولوا ليا فين وصلتو ونوجد الدراسة على هاد الأساس.",
    'identite_reference':
        "السلام عليكم {civilite} {prenom}، أنا {conseiller} من {marque}. {prescripteur} هضر لينا عليكم بخصوص الطاقة الشمسية. غادي نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير أولي. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.",
    'identite_telephone':
        "السلام عليكم {civilite} {prenom}، أنا {conseiller} من {marque}. بعد الهضرة ديالنا على الطاقة الشمسية، غادي نعاود نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير أولي. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.",
    'identite_whatsapp_entrant':
        "السلام عليكم {civilite} {prenom}، أنا {conseiller} من {marque}. شكرا على الرسالة ديالكم بخصوص الطاقة الشمسية. غادي نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير أولي. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.",
    'identite_ancien_dossier':
        "السلام عليكم {civilite} {prenom}، أنا {conseiller} من {marque}. كنتو سولتونا ف {mois_dossier} على الطاقة الشمسية. غادي نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير محين. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.",
    'deuxieme_affaire':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. خدمنا مع بعضياتنا ف التجهيزة الأولى ديالكم — شكرا على الثقة ديالكم من جديد. قولوا ليا شنو بغيتو تجهزو هاد المرة ونوجد ليكم الدراسة؛ غادي نعيط ليكم من دابا شي دقايق.",
    # CAD151 (23/09/2026) — traduction phrase par phrase du FR validé (aucune
    # promesse ajoutée, aucun chiffre, jamais une traduction automatique),
    # PAS ENCORE relue par un locuteur natif (CADM1, à faire avant tout usage
    # réel — comme le reste des textes nés dans ce lot).
    'debrief_visite':
        "السلام عليكم {civilite} {prenom}، {conseiller} من {marque}. كنعيط ليكم من بعد ما جا التقني ديالنا عندكم: شنو رايكم فالزيارة ديالو، وواش بقا عندكم شي سؤال قبل ما نكملو مع بعضياتنا؟",
}

# Placeholders AUTORISÉS dans un message de relance (MRY12). Aucun chiffre
# (prix, kWc, économies) : ces valeurs restent dans le devis et la
# proposition, jamais dans un message automatique.
#
# Ordre fondateur du 08/09/2026 — les trois derniers sont la PREUVE de la
# touche `j4_preuve` : mois, ville et lien de page publique d'une
# `parametres.Realisation` RÉELLE, choisie côté serveur par
# `parametres.selectors.realisation_pour_lead`. Ce ne sont pas des chiffres
# commerciaux : ce sont les coordonnées d'un chantier existant que le client
# peut aller voir. Sans réalisation, ils restent vides et la phrase est OMISE
# (MRY13) — jamais un crochet à remplir à la main, jamais une preuve inventée.
# VISITE-CADENCE (15/09/2026) — `{date_visite}` est la date de la visite
# technique POSÉE sur la fiche (`Lead.visite_prevue_le`), rendue en français
# (« mardi 16 septembre »). Ce n'est pas un chiffre commercial : c'est un
# rendez-vous que le client a lui-même accepté. Sans date sur la fiche, la
# valeur reste VIDE et `_omettre_phrases_incompletes` retire la phrase entière
# (MRY13) — jamais un crochet, jamais une date approximative.
# CAD95 (21/09/2026) — `{lien_video_preuve}` : vidéo courte (30-60 s) EN PLUS
# du lien de la touche `j4_preuve`, même sélection serveur, même repli VIDE +
# phrase omise (MRY13) sans vidéo au catalogue.
# CAD96 (21/09/2026) — `{marque}` : le nom AFFICHÉ de la société
# (`parametres.CompanyProfile.nom`), résolu côté serveur — jamais une graphie
# de marque codée en dur dans un texte (garde SCA29). Remplace les trois
# graphies incohérentes qui coexistaient (majuscules seules, suivies de
# « Solutions », casse mixte suivie de « Solutions ») par UNE seule source,
# la société elle-même.
# CAD71 (21/09/2026) — `{lien_google}` : lien de la fiche Google (réglage
# société `CompanyProfile.lien_avis_google`), PAS le lien du devis.
# CAD127 (21/09/2026) — `{prescripteur}` : le nom de la personne qui a
# recommandé le prospect (résolu côté serveur depuis le parrainage
# enregistré ; aucun prénom codé en dur). `{mois_dossier}` : le mois où le
# prospect nous avait consultés, dérivé de la date de création de SA fiche.
# Les deux sont VIDES quand la donnée n'existe pas — leur phrase est alors
# OMISE (MRY13), jamais un crochet envoyé au client.
PLACEHOLDERS_RELANCE = ["{civilite}", "{nom}", "{prenom}", "{ville}", "{reference}", "{lien}", "{lien_rdv}", "{date_validite}", "{conseiller}", "{mois_preuve}", "{ville_preuve}", "{lien_preuve}", "{puissance_preuve}", "{date_visite}", "{lien_video_preuve}", "{marque}", "{lien_google}", "{prescripteur}", "{mois_dossier}"]

#: Les clés du moteur de relances (MRY12), dans l'ordre du fichier source.
CLES_RELANCE = [
    'identite',
    'appel_ouverture',
    'repondeur',
    # CAD67 — Appel 3 (relance J1) et Appel 6 (dernier, avant clôture).
    'appel_relance',
    'appel_dernier',
    'valeur_j1',
    'vocal_j3',
    'appel_dimanche',
    'je_classe_j7',
    'cloture_j14',
    'reveil_a2',
    'rappel_plus_tard',
    'stop_contact',
    'j1_pdf',
    # CAD98 — les trois scripts des « Appel de suivi » après devis, chacun
    # rangé à sa place dans la chronologie de la cadence (J2, J7, J11).
    'appel_suivi_j2',
    'j4_preuve',
    'j6_garanties',
    'appel_suivi_j7',
    'j9_validite',
    'appel_suivi_j11',
    'j13_dernier',
    'j14_pause',
    'dimanche_famille',
    'annonce_appel_reda',
    'offre_reda',
    'reveil_a1',
    'reveil_a3',
    'reveil_b',
    'avis_google',
    'parrainage',
    # VISITE-CADENCE — la visite technique proposée après le devis, puis
    # confirmée la veille.
    'visite_proposition',
    'visite_confirmation',
    # CAD151 — le débrief après le retour du technicien (envoi manuel, comme
    # `annonce_appel_reda`/`offre_reda` juste en dessous).
    'debrief_visite',
    # CAD125 — dossiers institutionnels, posés par playbook de SEGMENT
    # (industriel/commercial et agricole), jamais par un barreau de cadence.
    'dossier_8221',
    'dossier_fda',
    # CAD127 — premier message par ORIGINE : « vous venez de remplir notre
    # formulaire » est faux pour la moitié des canaux. Clés ADDITIVES
    # (`unique_together (company, cle)` interdit une variante sur `identite`).
    'identite_reference',
    'identite_telephone',
    'identite_whatsapp_entrant',
    'identite_ancien_dossier',
    # CAD128 — le client DÉJÀ SIGNÉ qui redemande un devis : cadence courte,
    # texte propre. Jamais le protocole contact sur un client acquis.
    'deuxieme_affaire',
]

#: CAD60 (21/09/2026) — les textes à ENVOI MANUEL, hors cadence.
#:
#: Aucun des 10 barreaux après-devis ne les porte, et aucun ne les portera :
#: `offre_reda` contient trois blancs non calculables ([la raison réelle],
#: [montant en dirhams], [nouveau total TTC]) et l'appel du fondateur se
#: décide au cas par cas, après SA décision — jamais avant. Câbler un bouton
#: conditionnel serait de la sur-ingénierie ; la liste existe pour que l'écran
#: puisse DIRE « envoi manuel » au lieu de laisser chercher un bouton absent.
CLES_ENVOI_MANUEL = frozenset({
    'annonce_appel_reda', 'offre_reda',
    # CAD151 — le débrief après le retour du technicien : même doctrine,
    # aucun barreau de cadence ne le porte.
    'debrief_visite',
})

#: La phrase à afficher à côté de ces textes, au catalogue comme au guide.
MENTION_ENVOI_MANUEL = (
    'Envoi manuel, hors cadence, après la décision du fondateur — aucun '
    'bouton ne l’envoie.')


class MessageTemplate(models.Model):
    """Un modèle de message WhatsApp éditable, par entreprise et par clé.

    Deux variantes de langue : Français (`corps_fr`) et Darija (`corps_darija`).
    La Darija retombe sur le FR tant qu'elle est vide.
    """
    class Cle(models.TextChoices):
        DEVIS_UNIQUE = 'devis_unique', 'Devis (un seul)'
        DEVIS_MULTI_ENTETE = 'devis_multi_entete', 'Devis (plusieurs) — en-tête'
        DEVIS_MULTI_LIGNE = 'devis_multi_ligne', 'Devis (plusieurs) — ligne'
        FACTURE = 'facture', 'Facture'
        RELANCE = 'relance', 'Rappel de paiement'
        # XSAV4 — notifications client aux transitions du ticket SAV.
        TICKET_RECU = 'ticket_recu', 'Ticket SAV reçu'
        TICKET_PLANIFIE = 'ticket_planifie', 'Ticket SAV planifié'
        TICKET_RESOLU = 'ticket_resolu', 'Ticket SAV résolu'
        # XSTK22 — notifications client aux transitions de livraison.
        LIVRAISON_EN_TRANSIT = 'livraison_en_transit', 'Livraison en transit'
        LIVRAISON_LIVREE = 'livraison_livree', 'Livraison livrée'
        # XFSM6 — rappel client J-1 (RDV planifié demain, non confirmé).
        RAPPEL_RDV = 'rappel_rdv', 'Rappel de RDV (J-1)'
        # MRY12 — les clés du moteur de relances (textes validés dans
        # `docs/crm/messages_meryem.md`). PAS `visite_veille`/`visite_matin`/
        # `apres_visite` : aucun texte validé n'existe, on n'en invente pas.
        # VISITE-CADENCE (15/09/2026) — les deux clés de la visite, elles, ont
        # reçu leur texte validé du fondateur : elles sont donc seedées (voir
        # tout en bas de cette énumération).
        IDENTITE = 'identite', "Relance — identité (J0)"
        APPEL_OUVERTURE = 'appel_ouverture', "Relance — script d'appel d'ouverture (J0)"
        REPONDEUR = 'repondeur', "Relance — message sur répondeur"
        # CAD67 — Appel 3 (relance, J1) et Appel 6 (dernier, avant clôture).
        APPEL_RELANCE = 'appel_relance', "Relance — script d'appel 3 (J1)"
        APPEL_DERNIER = 'appel_dernier', "Relance — script du dernier appel (J10)"
        VALEUR_J1 = 'valeur_j1', "Relance — message de valeur (J1)"
        VOCAL_J3 = 'vocal_j3', "Relance — script du vocal (J3)"
        APPEL_DIMANCHE = 'appel_dimanche', "Relance — script d'appel du dimanche"
        JE_CLASSE_J7 = 'je_classe_j7', "Relance — « je classe ? » (J7)"
        CLOTURE_J14 = 'cloture_j14', "Relance — clôture (J14)"
        REVEIL_A2 = 'reveil_a2', "Réveil — lead jamais chiffré"
        RAPPEL_PLUS_TARD = 'rappel_plus_tard', "Réponse — rappelez-moi plus tard"
        STOP_CONTACT = 'stop_contact', "Réponse — ne me rappelez plus"
        J1_PDF = 'j1_pdf', "Après devis — le PDF s'ouvre bien ? (J1)"
        # CAD98 — scripts des trois « Appel de suivi » après devis.
        APPEL_SUIVI_J2 = (
            'appel_suivi_j2', "Après devis — script d'appel de suivi (J2)")
        J4_PREUVE = 'j4_preuve', "Après devis — chantier comparable (J4)"
        J6_GARANTIES = 'j6_garanties', "Après devis — garanties fabricants (J6)"
        APPEL_SUIVI_J7 = (
            'appel_suivi_j7', "Après devis — script d'appel de suivi (J7)")
        J9_VALIDITE = 'j9_validite', "Après devis — validité de la proposition (J9)"
        APPEL_SUIVI_J11 = (
            'appel_suivi_j11', "Après devis — script d'appel de suivi (J11)")
        J13_DERNIER = 'j13_dernier', "Après devis — dernier message (J13)"
        J14_PAUSE = 'j14_pause', "Après devis — mise en pause (J14)"
        DIMANCHE_FAMILLE = 'dimanche_famille', "Après devis — dimanche famille"
        ANNONCE_APPEL_REDA = 'annonce_appel_reda', "Annonce de l'appel du fondateur"
        OFFRE_REDA = 'offre_reda', "Offre du fondateur (après sa décision)"
        REVEIL_A1 = 'reveil_a1', "Réveil — dormant avec devis"
        REVEIL_A3 = 'reveil_a3', "Réveil — dernière chance"
        REVEIL_B = 'reveil_b', "Réveil — saison des factures"
        AVIS_GOOGLE = 'avis_google', "Après signature — avis Google"
        PARRAINAGE = 'parrainage', "Après signature — parrainage"
        # VISITE-CADENCE — la visite technique est une ÉTAPE DU SUIVI, placée
        # APRÈS l'envoi du devis : on la PROPOSE pour verrouiller la
        # proposition, puis on la CONFIRME la veille.
        VISITE_PROPOSITION = (
            'visite_proposition',
            "Après devis — proposer la visite technique")
        VISITE_CONFIRMATION = (
            'visite_confirmation',
            "Visite — confirmation la veille")
        # CAD151 (23/09/2026) — le DÉBRIEF après le retour du technicien.
        # ENVOI MANUEL comme `annonce_appel_reda`/`offre_reda` (CAD60) : aucun
        # barreau de cadence ne le déclenche, c'est le rappel du responsable
        # sous 24-48 h que `apps.crm.services.reprendre_plan_apres_retour_visite`
        # documente déjà (note d'historique) qui s'en sert, au moment choisi.
        DEBRIEF_VISITE = (
            'debrief_visite',
            "Après visite — débrief avec le client (envoi manuel)")
        # CAD125 — dossiers institutionnels, par SEGMENT (playbook conditionné
        # sur `{type_installation}`), jamais un barreau de cadence.
        DOSSIER_8221 = (
            'dossier_8221',
            "Segment — dossier d'autoproduction 82-21 (industriel/commercial)")
        DOSSIER_FDA = (
            'dossier_fda',
            "Segment — dossier de subvention agricole (FDA)")
        # CAD127 — premier message selon l'ORIGINE réelle du lead.
        IDENTITE_REFERENCE = (
            'identite_reference',
            "Identité — lead venu par recommandation")
        IDENTITE_TELEPHONE = (
            'identite_telephone',
            "Identité — lead venu par téléphone ou en boutique")
        IDENTITE_WHATSAPP_ENTRANT = (
            'identite_whatsapp_entrant',
            "Identité — lead né d'un message entrant")
        IDENTITE_ANCIEN_DOSSIER = (
            'identite_ancien_dossier',
            "Identité — dossier ancien repris")
        # CAD128 — client déjà signé qui revient.
        DEUXIEME_AFFAIRE = (
            'deuxieme_affaire',
            "Identité — client déjà signé qui revient")

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='message_templates',
    )
    cle = models.CharField(max_length=40, choices=Cle.choices)
    corps_fr = models.TextField(blank=True, default='')
    corps_darija = models.TextField(blank=True, default='')
    # ── NTI18N26 — au-delà de fr/darija : anglais + arabe CLASSIQUE ─────────
    # Additifs, vides par défaut (comportement historique inchangé tant
    # qu'aucune société ne les renseigne). `corps_ar` est l'arabe standard
    # (MSA), DISTINCT de `corps_darija` (arabe dialectal marocain) déjà
    # existant — deux registres différents, jamais confondus.
    corps_en = models.TextField(blank=True, default='')
    corps_ar = models.TextField(blank=True, default='')

    class Meta:
        unique_together = [('company', 'cle')]
        ordering = ['cle']

    def __str__(self):
        return f'{self.company_id}:{self.cle}'

    @classmethod
    def get_corps(cls, company, cle, langue='fr'):
        """Corps du message pour (company, cle, langue), défaut si absent.

        MRY12 — la Darija a son PROPRE défaut validé
        (``MESSAGE_TEMPLATE_DEFAULTS_DARIJA``) : ``row.corps_darija`` prime
        s'il est renseigné ; sinon le défaut Darija de la clé s'il existe ;
        sinon seulement la chaîne FR (``row.corps_fr`` puis le défaut FR) —
        jamais une traduction automatique.

        NTI18N26 — ``en``/``ar`` (arabe standard, distinct de la Darija) :
        même patron que la Darija, mais SANS défaut dédié (aucun texte validé
        n'existe pour ces deux langues) — un corps EN/AR non renseigné par la
        société retombe directement sur le FR (jamais un échec silencieux
        visible côté client : une chaîne non-vide est toujours renvoyée).
        L'appelant résout `langue` via la même priorité que NTI18N4
        (`apps.parametres.i18n_resolver.resolve_langue_sortie` — langue du
        client d'abord).
        """
        row = cls.objects.filter(company=company, cle=cle).first()
        default = MESSAGE_TEMPLATE_DEFAULTS.get(cle, '')
        corps_fr = row.corps_fr if row is not None else ''
        corps_darija = row.corps_darija if row is not None else ''
        if langue == 'darija':
            if corps_darija.strip():
                return corps_darija
            default_darija = MESSAGE_TEMPLATE_DEFAULTS_DARIJA.get(cle)
            if default_darija:
                return default_darija
        elif langue in ('en', 'ar') and row is not None:
            corps_langue = row.corps_en if langue == 'en' else row.corps_ar
            if corps_langue.strip():
                return corps_langue
        return corps_fr.strip() or default


# ── CAD126 (21/09/2026) — VARIANTES DE SEGMENT, PAR EXCEPTION ──────────────
#
# Les 27 textes sont 100 % résidentiels : « vos panneaux posés sur votre
# toit » (`valeur_j1`, `reveil_a1`, `reveil_a3`), « la décision se prend en
# famille » (`dimanche_famille`), « orientation du toit, charpente »
# (`visite_proposition`/`visite_confirmation`). Pour un pompage agricole il
# n'y a littéralement pas de toit, et `valeur_j1` demande « votre facture »,
# sans objet pour une exploitation au butane. Pour un industriel, « en
# famille » ne correspond à aucun processus d'achat — et le round 2 précise
# le vrai défaut : `dimanche_famille` EST filtré par l'étiquette « décision à
# plusieurs », donc c'est un industriel TAGUÉ qui reçoit « en famille ».
#
# Modèle : le dictionnaire darija ci-dessus — dict SÉPARÉ, repli sur le FR
# quand la clé est absente. On ne fabrique PAS une matrice 27 × langues ×
# segments : seules les clés qui MENTENT ont une variante, et seulement en
# français (aucune variante darija n'est validée — le repli reste le texte FR
# de base, jamais une traduction automatique).
#
# Un texte que la société a PERSONNALISÉ n'est jamais remplacé par une
# variante (même règle que `_REVEIL_CLES_SEEDEES`) : la variante ne s'applique
# qu'au texte encore au catalogue d'origine.

#: Les segments qui ont des variantes. Clés de `crm.Lead.TypeInstallation`,
#: reprises en littéral (ce module ne dépend d'aucun modèle du CRM).
SEGMENT_POMPAGE = 'agricole'
SEGMENTS_B2B = ('industriel', 'commercial')

#: `{segment: {cle: texte FR}}`. Une clé absente = le texte de base.
MESSAGE_TEMPLATE_VARIANTES_SEGMENT = {
    # Pompage agricole : pas de toit, pas de facture d'électricité (butane),
    # pas de « chez vous » — le chantier est au bord d'un forage.
    'agricole': {
        'valeur_j1':
            "Bonjour {civilite} {prenom}, je n'ai pas réussi à vous joindre. Pour que l'estimation soit juste, j'ai besoin de connaître votre pompe (puissance, profondeur du forage, débit souhaité) et l'emplacement du point d'eau : je vous montre l'installation adaptée, avec l'économie estimée. Quel moment vous arrange pour un appel de cinq minutes ?",
        'reveil_a1':
            "Bonjour {civilite} {prenom}, c'est {conseiller} de {marque}. Vous aviez reçu un devis de pompage solaire chez nous. Du nouveau depuis : on peut maintenant vous montrer votre installation en 3D, sur VOTRE parcelle, avec l'estimation à jour de vos économies. Je vous prépare la vue et je vous l'envoie ici — c'est gratuit, sans engagement. Je me lance ? (Je dois juste confirmer l'emplacement.) Répondez STOP et je n'insiste plus.",
        'reveil_a3':
            "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je ne veux pas insister : si le projet n'est plus d'actualité, je ferme votre dossier, aucun souci. Avant ça, une dernière chose qui aide souvent à décider : je peux vous envoyer la vue 3D de votre installation de pompage, avec l'estimation à jour. Je vous la prépare, ou je classe le dossier ? Répondez STOP et je n'insiste plus.",
        # Une exploitation se décide souvent à plusieurs — associés, frères,
        # coopérative — pas nécessairement « en famille » : formulation
        # neutre, même chaleur, aucune supposition sur qui décide.
        'dimanche_famille':
            "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je sais que la décision se prend à plusieurs. Si vous en parlez ce week-end, je peux vous envoyer la page résumé (une page, les chiffres clés) pour la partager, ou vous appeler à deux ou trois dimanche après 17 h, comme vous préférez.",
        'visite_proposition':
            "Pour verrouiller votre proposition, on peut passer sur place pour la vérification technique gratuite : le technicien confirme l'emplacement des panneaux, les caractéristiques du forage et le coffret électrique, et répond à toutes vos questions sur place. Ça ne vous engage à rien. Dites-moi le jour qui vous arrange cette semaine et je bloque le créneau. — {conseiller}",
        'visite_confirmation':
            "Bonjour, on confirme la visite technique prévue {date_visite} sur votre exploitation. Le technicien vérifie l'emplacement des panneaux, le forage et le coffret électrique — prévoyez l'accès au point d'eau. Votre présence est importante : c'est l'occasion de répondre à toutes vos questions sur place. En cas d'empêchement, répondez-moi ici et on recale le passage. — {conseiller}",
    },
    # Industriel / commercial : on parle à une ORGANISATION. « En famille »
    # ne décrit aucun processus d'achat B2B ; le site n'est pas « chez vous ».
    'industriel': {
        'valeur_j1':
            "Bonjour {civilite} {prenom}, je n'ai pas réussi à vous joindre. Pour que l'estimation soit juste, j'ai besoin de vos relevés de consommation (une photo suffit) et de l'adresse du site : je vous montre l'installation sur vos bâtiments, avec l'économie estimée. Quel moment vous arrange pour un appel de cinq minutes ?",
        'reveil_a1':
            "Bonjour {civilite} {prenom}, c'est {conseiller} de {marque}. Vous aviez reçu une étude solaire chez nous. Du nouveau depuis : on peut maintenant vous montrer l'installation posée sur VOS bâtiments, en 3D, avec l'estimation à jour de vos économies. Je vous prépare la vue et je vous l'envoie ici — c'est gratuit, sans engagement. Je me lance ? (Je dois juste confirmer l'adresse du site.) Répondez STOP et je n'insiste plus.",
        'reveil_a3':
            "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je ne veux pas insister : si le projet n'est plus d'actualité, je ferme votre dossier, aucun souci. Avant ça, une dernière chose qui aide souvent à décider : je peux vous envoyer la vue 3D de l'installation sur vos bâtiments, avec l'estimation à jour. Je vous la prépare, ou je classe le dossier ? Répondez STOP et je n'insiste plus.",
        'dimanche_famille':
            "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je sais que la décision se prend à plusieurs. Si vous en parlez avec votre équipe, je peux vous envoyer la page résumé (une page, les chiffres clés) pour la partager, ou nous réunir à deux ou trois au moment qui vous arrange, comme vous préférez.",
        'visite_proposition':
            "Pour verrouiller votre proposition, on peut passer sur votre site pour la vérification technique gratuite : le technicien confirme l'orientation et la structure des bâtiments ainsi que le tableau électrique, et répond à toutes les questions de votre équipe sur place. Ça ne vous engage à rien. Dites-moi le jour qui vous arrange cette semaine et je bloque le créneau. — {conseiller}",
        'visite_confirmation':
            "Bonjour, on confirme la visite technique prévue {date_visite} sur votre site. Le technicien vérifie la structure des bâtiments et le tableau électrique — prévoyez l'accès au local technique. La présence d'un responsable est importante : c'est l'occasion de répondre à toutes les questions sur place. En cas d'empêchement, répondez-moi ici et on recale le passage. — {conseiller}",
    },
}
# Le commercial partage EXACTEMENT les textes de l'industriel : même
# organisation, même processus d'achat. Un dict partagé plutôt que recopié —
# une correction sur l'un vaut pour l'autre, par construction.
MESSAGE_TEMPLATE_VARIANTES_SEGMENT['commercial'] = (
    MESSAGE_TEMPLATE_VARIANTES_SEGMENT['industriel'])

#: Les clés qui MENTENT au résidentiel près — celles qui ont une variante.
#: Sert au test paramétré et à l'écran qui voudra signaler « texte adapté ».
CLES_VARIANTES_SEGMENT = frozenset(
    cle
    for textes in MESSAGE_TEMPLATE_VARIANTES_SEGMENT.values()
    for cle in textes
)


def variante_segment(cle, type_installation):
    """Le texte FR adapté à CE segment, ou ``None`` (repli sur le texte FR).

    Tolérant : un segment inconnu, vide ou résidentiel n'a jamais de variante.
    """
    segment = (type_installation or '').strip()
    if not segment:
        return None
    return MESSAGE_TEMPLATE_VARIANTES_SEGMENT.get(segment, {}).get(cle)


# ── CAD127 (21/09/2026) — LE PREMIER MESSAGE DIT LA VÉRITÉ SUR L'ORIGINE ──
#
# « Vous venez de remplir notre formulaire » est FAUX pour la moitié des
# origines : la même cadence part pour un lead arrivé par téléphone, en
# boutique, par recommandation, depuis un salon, repositionné par l'écran de
# placement, ou né d'une conversation entrante (CTWA, livechat). Une première
# phrase fausse est exactement ce qui fait perdre la confiance au premier
# contact — et `unique_together (company, cle)` interdit toute VARIANTE sur
# une clé existante : ces quatre clés sont donc ADDITIVES.
#
# Correction du round 2 : le ticket SAV n'est PAS une origine —
# `create_lead_depuis_ticket` ne démarre aucune cadence (vérifié sur les 8
# appelants de `demarrer_cadence_contact`). Aucune clé pour lui.
#
# Aucun prénom codé en dur (règle fondateur 08/09) : le prescripteur est un
# PLACEHOLDER de gabarit, résolu côté serveur depuis le parrainage enregistré.
# Vide ⇒ sa phrase est OMISE (MRY13), jamais un crochet envoyé au client.
MESSAGE_TEMPLATE_DEFAULTS.update({
    'identite_reference':
        "Bonjour {civilite} {prenom}, je suis {conseiller} de {marque}. {prescripteur} nous a parlé de vous pour le solaire. Je vous appelle dans quelques minutes pour une première estimation ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.",
    'identite_telephone':
        "Bonjour {civilite} {prenom}, je suis {conseiller} de {marque}. Suite à notre échange au sujet du solaire, je vous rappelle dans quelques minutes pour une première estimation ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.",
    'identite_whatsapp_entrant':
        "Bonjour {civilite} {prenom}, je suis {conseiller} de {marque}. Merci pour votre message au sujet du solaire. Je vous appelle dans quelques minutes pour une première estimation ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.",
    'identite_ancien_dossier':
        "Bonjour {civilite} {prenom}, je suis {conseiller} de {marque}. Vous nous aviez consultés en {mois_dossier} au sujet du solaire. Je vous appelle dans quelques minutes pour une estimation à jour ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.",
})

#: CAD127 — les quatre clés d'identité par ORIGINE, plus celle du formulaire.
#: L'écran et le moteur lisent CETTE liste, jamais une énumération recopiée.
CLES_IDENTITE_PAR_ORIGINE = (
    'identite', 'identite_reference', 'identite_telephone',
    'identite_whatsapp_entrant', 'identite_ancien_dossier',
)

#: Canal d'origine (valeurs de ``crm.Lead.Canal``) → clé d'identité. Les
#: canaux ABSENTS gardent `identite` : `site_web` et `meta_ads` sont de VRAIS
#: formulaires remplis par le prospect, la phrase d'origine y est exacte.
CLE_IDENTITE_PAR_CANAL = {
    'reference': 'identite_reference',
    'telephone': 'identite_telephone',
    # Une visite en boutique est un ÉCHANGE, pas un formulaire : même texte.
    'walk_in': 'identite_telephone',
    'whatsapp_ctwa': 'identite_whatsapp_entrant',
}


# ── CAD128 (21/09/2026) — LE CLIENT DÉJÀ SIGNÉ QUI REVIENT ────────────────
#
# La garde doublon retenait tout lead partageant le téléphone ou l'e-mail et
# n'écartait que les archivés et les perdus : une fiche SIGNÉE était donc un
# doublon vivant, et le meilleur lead du portefeuille — il a déjà acheté —
# repartait sans protocole, avec une simple ligne « doublon possible de #… ».
#
# Son texte lui est propre : on ne se présente pas à quelqu'un qui nous
# connaît. GARDE-FOU « zéro chiffre inventé » : AUCUN mois n'est cité. La
# tâche l'illustrait par « nous avons déjà installé chez vous en {mois} »,
# mais rien ne relie encore les deux fiches en base (la liaison se fait par
# une note d'historique, pas par un champ) : plutôt qu'une date approximative,
# le mois est OMIS. Il reviendra le jour où CADM7 tranchera la liaison.
MESSAGE_TEMPLATE_DEFAULTS.update({
    'deuxieme_affaire':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Nous avons déjà travaillé ensemble sur votre première installation — merci de nous redonner votre confiance. Dites-moi ce que vous souhaitez équiper cette fois et je vous prépare l'étude ; je vous appelle dans quelques minutes.",
})

# ── CAD151 (23/09/2026) — LE DÉBRIEF APRÈS LE RETOUR DU TECHNICIEN ─────────
#
# La visite technique (VISITE-CADENCE, 15/09/2026) se PROPOSE puis se
# CONFIRME — mais son RETOUR n'avait aucun script : `reprendre_plan_apres_
# retour_visite` reprend la cadence après-devis là où elle en était, et
# `composer_note_retour_visite` écrit le compte-rendu dans l'historique, mais
# rien ne guide l'appel que le responsable passe au client dans les 24-48 h
# qui suivent (la note d'historique existante le dit déjà). ENVOI MANUEL,
# même patron que `annonce_appel_reda`/`offre_reda` (CAD60) : aucun barreau
# de cadence ne le porte, et il n'en aura pas — ouvrir un barreau dédié
# dupliquerait la reprise déjà exécutée par le retour de visite.
# ✎ Texte à valider par le fondateur ; darija pas encore relue par un
# locuteur natif (CADM1), comme le reste des textes nés dans ce lot.
MESSAGE_TEMPLATE_DEFAULTS.update({
    'debrief_visite':
        "Bonjour {civilite} {prenom}, {conseiller} de {marque}. Je vous appelle après le passage de notre technicien chez vous : qu'avez-vous pensé de sa visite, et reste-t-il des questions avant qu'on avance ensemble ?",
})
