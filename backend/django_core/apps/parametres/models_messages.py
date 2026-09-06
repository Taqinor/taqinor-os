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
        "Bonjour {prenom}, je suis Meryem de TAQINOR Solutions. Vous venez de nous laisser une demande pour le solaire, merci. Je vous appelle dans quelques minutes pour une première estimation ; si ce n'est pas le bon moment, dites-moi l'heure qui vous arrange.",
    'appel_ouverture':
        "Bonjour {prenom}, Meryem de TAQINOR Solutions. Vous venez de remplir notre formulaire pour le solaire. Je vous dérange deux minutes ?",
    'repondeur':
        "Bonjour {prenom}, Meryem de TAQINOR. Je vous appelle au sujet de votre demande solaire. Je vous envoie un message WhatsApp, répondez-y quand vous voulez. Bonne journée.",
    'valeur_j1':
        "Bonjour {prenom}, je n'ai pas réussi à vous joindre. Pour que l'estimation soit juste, j'ai besoin de votre facture (une photo suffit) et de votre adresse : je vous montre vos panneaux posés sur votre toit, avec l'économie estimée. Quel moment vous arrange pour un appel de cinq minutes ?",
    'vocal_j3':
        "Bonjour {prenom}, c'est Meryem de TAQINOR. Je vous ai laissé deux messages, je ne veux pas insister : dites-moi juste si le projet est toujours d'actualité, et à quelle heure je peux vous appeler. Bonne journée.",
    'appel_dimanche':
        "Bonjour {prenom}, Meryem de TAQINOR. Je me permets de vous appeler un dimanche parce que je ne vous trouve pas en semaine. Je ne vous retiens pas : votre demande solaire est-elle toujours d'actualité ?",
    'je_classe_j7':
        "Bonjour {prenom}, Meryem de TAQINOR. Sans nouvelle de votre part, je mets votre demande de côté dans trois jours. Un simple « plus tard » me suffit pour la garder ouverte.",
    'cloture_j14':
        "Bonjour {prenom}, Meryem de TAQINOR. Je classe votre demande pour ne pas vous déranger. Si vous souhaitez reprendre plus tard, ce message suffit : je vous prépare l'étude en 24 h.",
    'reveil_a2':
        "Bonjour {prenom}, Meryem de TAQINOR. Il y a un mois, vous vous renseigniez sur le solaire. Si le projet revient d'actualité, je reprends votre dossier là où on l'a laissé : une photo de votre dernière facture, et je vous envoie l'estimation à jour.",
    'rappel_plus_tard':
        "Très bien, je vous rappelle [jour] à [heure]. D'ici là, si vous avez votre facture sous la main, une photo m'aide à préparer l'estimation.",
    'stop_contact':
        "Compris, je ne vous rappellerai plus. Je vous laisse simplement ce numéro si un jour le projet revient. Bonne journée.",
    'j1_pdf':
        "Le PDF s'ouvre bien ? Qu'est-ce qui vous a le plus parlé ?",
    'j4_preuve':
        "Voici une installation comparable à la vôtre, posée en [mois] à [ville] ; le suivi de production est en temps réel, je peux vous montrer.",
    'j6_garanties':
        "Ces garanties sont accordées par les fabricants : elles restent valables quoi qu'il arrive.",
    'j9_validite':
        "Votre proposition est valable jusqu'au {date_validite}. Après, je dois revalider les prix et la disponibilité du matériel : ce n'est pas pour vous presser, c'est pour ne pas vous annoncer un prix faux.",
    'j13_dernier':
        "Je ne veux pas insister : dites-moi si le projet est toujours d'actualité, et si non, je vous laisse tranquille.",
    'j14_pause':
        "Je mets votre dossier en pause. Votre proposition reste dans notre système ; un message suffit pour la réactiver.",
    'dimanche_famille':
        "Bonjour {prenom}, Meryem de TAQINOR. Je sais que la décision se prend en famille. Si vous en parlez ce week-end, je peux vous envoyer la page résumé (une page, les chiffres clés) pour la partager, ou vous appeler à deux ou trois dimanche après 17 h, comme vous préférez.",
    'annonce_appel_reda':
        "Bonjour {prenom}, Meryem de TAQINOR. Reda, le fondateur, qui valide chaque étude, aimerait vous appeler dimanche vers 18 h pour répondre à vos questions en cinq minutes. Ça vous convient, ou préférez-vous un autre moment ?",
    'offre_reda':
        "Bonjour {prenom}, Meryem de TAQINOR. Suite à votre échange avec Reda : [la raison réelle], il vous accorde [montant en dirhams] sur la proposition n° {reference}, soit [nouveau total TTC]. Cette proposition est valable jusqu'à mardi 18 h ; ensuite le prix normal reprend. Je reste disponible pour toute question.",
    'reveil_a1':
        "Bonjour {prenom}, c'est Meryem de Taqinor Solutions. Vous aviez reçu un devis solaire chez nous il y a quelques mois. Du nouveau depuis : on peut maintenant vous montrer vos panneaux posés sur VOTRE toit, en 3D, avec l'estimation à jour de vos économies. Je vous prépare la vue et je vous l'envoie ici — c'est gratuit, sans engagement. Je me lance ? (Je dois juste confirmer votre adresse.)",
    'reveil_a3':
        "Bonjour {prenom}, Meryem de Taqinor Solutions. Je ne veux pas insister : si le projet n'est plus d'actualité, je ferme votre dossier, aucun souci. Avant ça, une dernière chose qui aide souvent à décider : je peux vous envoyer la vue 3D de vos panneaux sur votre toit, avec l'estimation à jour. Je vous la prépare, ou je classe le dossier ?",
    'reveil_b':
        "Bonjour {prenom}, c'est Meryem de Taqinor Solutions. C'est la saison des factures d'été — souvent le moment où le solaire se décide. Votre projet est-il toujours d'actualité ? Si oui, je vous prépare une estimation à jour de vos économies, sans engagement. On en parle ?",
    'avis_google':
        "Bonjour {prenom}, j'espère que l'installation vous donne satisfaction. Si vous avez deux minutes, un avis sur Google nous aide énormément, c'est ce que regardent les futurs clients : {lien}. Merci beaucoup !",
    'parrainage':
        "Si quelqu'un autour de vous, un voisin, un frère, un collègue, réfléchit au solaire, vous pouvez lui envoyer votre lien de parrainage ; il aura la même étude gratuite, et on convient ensemble d'une récompense pour vous.",
})

# Variantes darija (écriture arabe, revue native le 04/09/2026). Une clé
# ABSENTE d'ici retombe sur le FR (`get_corps`) — jamais une traduction
# automatique.
MESSAGE_TEMPLATE_DEFAULTS_DARIJA = {
    'identite':
        "السلام عليكم {prenom}، أنا مريم من TAQINOR Solutions. وصلنا الطلب ديالكم على الطاقة الشمسية، شكرا. غادي نعيط ليكم من دابا شي دقايق باش نعطيكم تقدير أولي. إلا ماشي الوقت المناسب، قولوا ليا شمن وقت يناسبكم.",
    'appel_ouverture':
        "السلام عليكم {prenom}، مريم من TAQINOR Solutions. عمرتو دابا الفورم ديالنا على الطاقة الشمسية. نقدر ناخد منكم جوج دقايق؟",
    'repondeur':
        "السلام عليكم {prenom}، مريم من TAQINOR. كنعيط ليكم بخصوص الطلب ديالكم على الطاقة الشمسية. غادي نصيفط ليكم رسالة على الواتساب، جاوبو فوقاش ما بغيتو. نهاركم مبروك.",
    'valeur_j1':
        "السلام عليكم {prenom}، حاولت نعيط ليكم ولكن ما لقيتكمش. باش يكون التقدير مضبوط، خاصني غير تصويرة ديال فاتورة الضو والعنوان ديالكم، ونوريكم كيفاش غادي يجيو الألواح فوق السطح ديالكم مع شحال غادي توفرو ف الفاتورة. شمن وقت يناسبكم باش نعيط ليكم خمس دقايق؟",
    'vocal_j3':
        "السلام عليكم {prenom}، مريم من TAQINOR. صيفطت ليكم جوج رسائل وما بغيتش نثقل عليكم. غير قولوا ليا واش مشروع الطاقة الشمسية مازال كيهمكم، وفوقاش نقدر نعيط ليكم. نهاركم مبروك.",
    'appel_dimanche':
        "السلام عليكم {prenom}، مريم من TAQINOR. سمحو ليا كنعيط ليكم نهار الحد، حيت ف الأسبوع ما كنلقاكمش. ما غاديش نطول عليكم: واش الطلب ديالكم على الطاقة الشمسية مازال كيهمكم؟",
    'je_classe_j7':
        "السلام عليكم {prenom}، مريم من TAQINOR. إلا ما جاوبتونيش، غادي نحط الطلب ديالكم على جنب من هنا لتلت أيام. كلمة «من بعد» كافية باش نخلي الطلب ديالكم محلول.",
    'cloture_j14':
        "السلام عليكم {prenom}، مريم من TAQINOR. غادي نسد الطلب ديالكم باش ما نزعجكمش. إلا بغيتو ترجعو للمشروع من بعد، صيفطو ليا غير هاد الرسالة ونوجد ليكم الدراسة ف 24 ساعة.",
    'reveil_a2':
        "السلام عليكم {prenom}، مريم من TAQINOR. هادي شهر كنتو كتسولو على الطاقة الشمسية. إلا رجع المشروع كيهمكم، غادي نكمل الملف ديالكم من فين وقفنا: تصويرة ديال آخر فاتورة، وغادي نصيفط ليكم التقدير الجديد.",
    'rappel_plus_tard':
        "واخا، غادي نعيط ليكم [النهار] على [الساعة]. وحتى لذاك الوقت، إلا كانت الفاتورة عندكم، تصويرة ديالها غادي تعاونني نوجد التقدير.",
    'stop_contact':
        "واخا، فهمتكم، ما غاديش نعاود نعيط ليكم. غير كنخلي ليكم هاد الرقم إلا شي نهار رجع المشروع. نهاركم مبروك.",
    'dimanche_famille':
        "السلام عليكم {prenom}، مريم من TAQINOR. عارفة بلي القرار كيتاخد مع العائلة. إلا غادي تهضرو عليه هاد الويكاند، نقدر نصيفط ليكم ورقة الملخص (صفحة وحدة فيها الأرقام المهمة) باش تشاركوها، ولا نعيط ليكم نهار الحد من بعد 5 ديال العشية وتكونو جوج ولا تلاتة، كيف ما بغيتو.",
    'annonce_appel_reda':
        "السلام عليكم {prenom}، مريم من TAQINOR. رضا، المؤسس ديال الشركة اللي كيراجع كل دراسة، بغا يعيط ليكم نهار الحد على 6 ديال العشية باش يجاوب على الأسئلة ديالكم ف خمس دقايق. واش مناسب ليكم، ولا كتفضلو وقت آخر؟",
    'offre_reda':
        "السلام عليكم {prenom}، مريم من TAQINOR. بعد الهضرة ديالكم مع رضا: [السبب الحقيقي]، نقص ليكم [المبلغ بالدرهم] من العرض رقم {reference}، يعني [المجموع الجديد TTC]. هاد العرض صالح حتى الثلاثاء على 6 ديال العشية، ومن بعد كيرجع الثمن العادي. إلا كان عندكم شي سؤال أنا هنا.",
}

# Placeholders AUTORISÉS dans un message de relance (MRY12). Aucun chiffre
# (prix, kWc, économies) : ces valeurs restent dans le devis et la
# proposition, jamais dans un message automatique.
PLACEHOLDERS_RELANCE = ["{civilite}", "{nom}", "{prenom}", "{ville}", "{reference}", "{lien}", "{lien_rdv}", "{date_validite}", "{conseiller}"]

#: Les clés du moteur de relances (MRY12), dans l'ordre du fichier source.
CLES_RELANCE = [
    'identite',
    'appel_ouverture',
    'repondeur',
    'valeur_j1',
    'vocal_j3',
    'appel_dimanche',
    'je_classe_j7',
    'cloture_j14',
    'reveil_a2',
    'rappel_plus_tard',
    'stop_contact',
    'j1_pdf',
    'j4_preuve',
    'j6_garanties',
    'j9_validite',
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
]


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
        # MRY12 — les 25 clés du moteur de relances (textes validés dans
        # `docs/crm/messages_meryem.md`). PAS `visite_veille`/`visite_matin`/
        # `apres_visite` : aucun texte validé n'existe, on n'en invente pas.
        IDENTITE = 'identite', "Relance — identité (J0)"
        APPEL_OUVERTURE = 'appel_ouverture', "Relance — script d'appel d'ouverture (J0)"
        REPONDEUR = 'repondeur', "Relance — message sur répondeur"
        VALEUR_J1 = 'valeur_j1', "Relance — message de valeur (J1)"
        VOCAL_J3 = 'vocal_j3', "Relance — script du vocal (J3)"
        APPEL_DIMANCHE = 'appel_dimanche', "Relance — script d'appel du dimanche"
        JE_CLASSE_J7 = 'je_classe_j7', "Relance — « je classe ? » (J7)"
        CLOTURE_J14 = 'cloture_j14', "Relance — clôture (J14)"
        REVEIL_A2 = 'reveil_a2', "Réveil — lead jamais chiffré"
        RAPPEL_PLUS_TARD = 'rappel_plus_tard', "Réponse — rappelez-moi plus tard"
        STOP_CONTACT = 'stop_contact', "Réponse — ne me rappelez plus"
        J1_PDF = 'j1_pdf', "Après devis — le PDF s'ouvre bien ? (J1)"
        J4_PREUVE = 'j4_preuve', "Après devis — chantier comparable (J4)"
        J6_GARANTIES = 'j6_garanties', "Après devis — garanties fabricants (J6)"
        J9_VALIDITE = 'j9_validite', "Après devis — validité de la proposition (J9)"
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

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='message_templates',
    )
    cle = models.CharField(max_length=40, choices=Cle.choices)
    corps_fr = models.TextField(blank=True, default='')
    corps_darija = models.TextField(blank=True, default='')

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
        return corps_fr.strip() or default
