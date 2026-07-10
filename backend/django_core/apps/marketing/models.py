"""Modèles du module Marketing (``apps.marketing``).

Équivalent Odoo Email/SMS Marketing + Marketing Automation + Surveys +
Events. Ces modèles ont d'abord vécu dans ``apps.compta`` (FG201–208,
FG238–241, XMKT*, ZMKT*) ; ODX9 les a SORTIS de compta en préservant à
l'IDENTIQUE les tables physiques existantes (``db_table = 'compta_<model>'``)
via des migrations ``SeparateDatabaseAndState`` (state-only, aucun SQL, aucune
donnée déplacée). Un shim de ré-export subsiste dans ``apps/compta/models.py``
pour le code/migrations historiques.

Frontière cross-app (CLAUDE.md) : marketing ne lit crm/ventes QUE via leurs
``selectors.py``/``services.py`` ou par référence opaque (id/texte) — jamais
d'import de leurs ``models``. Tout est multi-société : chaque modèle porte un
FK ``company`` posé côté serveur (jamais lu du corps de requête).
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


# ── FG201 — Campagnes d'envoi groupé email / SMS ───────────────────────────

class Campagne(models.Model):
    """Campagne d'envoi groupé email / SMS vers un segment ciblé (FG201).

    Sert à « réveiller » une base froide : on définit un segment (critères de
    ciblage libres, stockés en JSON), un canal et un message, puis on déclenche
    l'envoi groupé. L'envoi RÉEL passe par Brevo et n'a lieu que si l'intégration
    est explicitement activée (réglage ``BREVO_ENABLED`` + clé) — sinon l'envoi
    est un NO-OP (aucun appel payant, aucune dépendance dure). Les compteurs
    d'ouvertures/clics sont stockés ici pour mesurer le réveil.
    """
    class Canal(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        # XMKT10 — envoi groupé WhatsApp (opt-in XMKT4 uniquement). Réel via
        # BSP quand ``notifications.whatsapp_bsp.get_whatsapp_provider()``
        # renvoie ``BspProvider`` actif (jeton présent) ; sinon repli EXACT
        # sur une file de liens wa.me ordonnée (comportement manuel actuel).
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        # ZMKT1 — pipeline d'envoi (Draft → In Queue → Sending → Sent, style
        # Odoo) : `en_file` = planifiée, en attente du beat (XMKT7) ;
        # `envoi_en_cours` = lot en cours d'envoi (throttle par lots XMKT7).
        EN_FILE = 'en_file', 'En file'
        ENVOI_EN_COURS = 'envoi_en_cours', 'Envoi en cours'
        ENVOYEE = 'envoyee', 'Envoyée'
        ANNULEE = 'annulee', 'Annulée'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='campagnes_marketing',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom de la campagne')
    canal = models.CharField(
        max_length=8, choices=Canal.choices, default=Canal.EMAIL,
        verbose_name='Canal')
    objet = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Objet (email)')
    corps = models.TextField(blank=True, default='', verbose_name='Message')
    segment = models.JSONField(
        default=dict, blank=True,
        verbose_name='Critères de segment (JSON)')
    listes = models.ManyToManyField(
        'marketing.ListeDiffusion', blank=True, related_name='campagnes',
        verbose_name='Listes de diffusion ciblées (XMKT5)')
    sms_sender_id = models.CharField(
        max_length=11, blank=True, default='',
        verbose_name="Sender-ID SMS déclaré (XMKT15)")
    # XMKT10 — gabarit BSP approuvé (nom+langue) pour le canal whatsapp.
    # NULL = comportement historique (corps libre, canal email/sms) ou envoi
    # WhatsApp en repli manuel (file wa.me construite depuis ``corps``).
    whatsapp_template = models.ForeignKey(
        'notifications.WhatsAppTemplate',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campagnes_marketing',
        verbose_name='Gabarit WhatsApp (BSP)',
    )
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    # Compteurs de réveil — alimentés par les webhooks Brevo (gated).
    nb_destinataires = models.PositiveIntegerField(
        default=0, verbose_name='Destinataires')
    nb_envois = models.PositiveIntegerField(default=0, verbose_name='Envoyés')
    nb_ouvertures = models.PositiveIntegerField(
        default=0, verbose_name='Ouvertures')
    nb_clics = models.PositiveIntegerField(default=0, verbose_name='Clics')
    envoyee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Envoyée le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')
    # ── XMKT7 — planification, throttling, fenêtres de silence ──────────────
    planifiee_le = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Envoi planifié le (Celery beat)')
    debit_max_par_heure = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='Débit max par heure (envoi par lots)')
    # ── XMKT11 — variantes de contenu par langue (fr/ar/darija) ──────────────
    # Vide par défaut = comportement actuel (un seul corps, ``objet``/``corps``
    # ci-dessus servent de fallback FR). Structure :
    # {"ar": {"objet": "...", "corps": "..."}, "darija": {...}}. Le FR n'a
    # pas besoin d'entrée ici (déjà porté par les champs historiques).
    variantes_langue = models.JSONField(
        default=dict, blank=True,
        verbose_name='Variantes de contenu par langue (JSON)')
    # ── XMKT14 — Test A/B avec gagnant automatique ──────────────────────────
    # Vide par défaut = pas de test A/B (comportement actuel, un seul envoi).
    # Structure : {"objet": "...", "corps": "...", "pct_echantillon": 20,
    # "fenetre_heures": 4, "critere": "ouvertures"|"clics"}.
    ab_test = models.JSONField(
        default=dict, blank=True, verbose_name='Configuration test A/B (JSON)')
    ab_gagnant = models.CharField(
        max_length=1, blank=True, default='',
        verbose_name='Variante gagnante (A/B)')
    ab_decide_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Décision A/B prise le')
    # ── XMKT17 — Coût & ROI MAD par campagne ────────────────────────────────
    budget_mad = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Budget prévu (MAD)')
    cout_reel_mad = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        verbose_name='Coût réel (MAD)')
    # Lignes de coût libres : [{"libelle": "Ads Meta", "montant_mad": 500}, …].
    lignes_cout = models.JSONField(
        default=list, blank=True, verbose_name='Lignes de coût (JSON)')
    # ── XMKT31 — conteneur de campagne multi-canal ──────────────────────────
    # NULL = campagne autonome (comportement actuel). Une campagne "mère"
    # regroupe emails/SMS/WhatsApp/séquences d'une même opération marketing ;
    # les événements (XMKT28) et codes promo (FG209) se rattachent par leur
    # propre FK/référence, pas ici.
    parente = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='enfants',
        verbose_name='Campagne mère',
    )
    # Rattachements OPAQUES d'objets non-Campagne (séquences, formulaires,
    # codes promo FG209, événements XMKT28) à cette campagne — uniquement
    # pertinent sur une campagne MÈRE (parente=None). Format :
    # [{"type": "sequence"|"formulaire"|"code_promo"|"evenement", "id": N}].
    rattachements = models.JSONField(
        default=list, blank=True,
        verbose_name='Rattachements (JSON, campagne mère)')
    # ── ZMKT3 — enregistrer une campagne comme modèle réutilisable ──────────
    est_modele = models.BooleanField(
        default=False,
        verbose_name='Modèle réutilisable (jamais envoyé)')

    class Meta:
        db_table = 'compta_campagne'
        verbose_name = 'Campagne email/SMS'
        verbose_name_plural = 'Campagnes email/SMS'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.nom} ({self.canal})'


# ── XMKT2 — Journal d'envoi par destinataire (trace de campagne) ───────────

class EnvoiCampagne(models.Model):
    """Une ligne par destinataire réel d'une campagne (XMKT2).

    Les compteurs agrégés de ``Campagne`` (FG201) sont dérivés de ces lignes ;
    permet le drill-down depuis chaque KPI vers la liste exacte des
    destinataires, et alimente les webhooks Brevo (gated).
    """
    class Statut(models.TextChoices):
        QUEUED = 'queued', 'En file'
        ENVOYE = 'envoye', 'Envoyé'
        DELIVRE = 'delivre', 'Délivré'
        OUVERT = 'ouvert', 'Ouvert'
        CLIQUE = 'clique', 'Cliqué'
        REBOND = 'rebond', 'Rebond'
        DESINSCRIT = 'desinscrit', 'Désinscrit'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='envois_campagne',
        verbose_name='Société',
    )
    campagne = models.ForeignKey(
        Campagne,
        on_delete=models.CASCADE,
        related_name='envois',
        verbose_name='Campagne',
    )
    destinataire = models.CharField(
        max_length=255, verbose_name='Destinataire (email/téléphone)')
    contact_ref = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Référence contact (lead/client, opaque)')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.QUEUED,
        db_index=True, verbose_name='Statut')
    raison_smtp = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Raison SMTP')
    envoye_le = models.DateTimeField(null=True, blank=True,
                                     verbose_name='Envoyé le')
    ouvert_le = models.DateTimeField(null=True, blank=True,
                                     verbose_name='Ouvert le')
    clique_le = models.DateTimeField(null=True, blank=True,
                                     verbose_name='Cliqué le')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')
    # XMKT14 — variante A/B reçue par ce destinataire ('a'/'b'), vide = hors
    # test A/B ou envoi au reste après décision du gagnant.
    variante_ab = models.CharField(
        max_length=1, blank=True, default='', verbose_name='Variante A/B')

    class Meta:
        db_table = 'compta_envoicampagne'
        verbose_name = "Envoi de campagne (destinataire)"
        verbose_name_plural = "Envois de campagne (destinataires)"
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.campagne_id} → {self.destinataire} ({self.statut})'


# ── XMKT3 — Désinscription un clic + liste de suppression globale ──────────

class SuppressionMarketing(models.Model):
    """Un destinataire jamais ciblé par une campagne/séquence (XMKT3, preuve
    loi 09-08). Vérifiée AU MOMENT DE L'ENVOI — jamais appliquée aux messages
    transactionnels (devis/factures/tickets, canal inchangé).
    """
    class Motif(models.TextChoices):
        DESINSCRIT = 'desinscrit', 'Désinscription volontaire'
        REBOND_DUR = 'rebond_dur', 'Rebond dur'
        PLAINTE = 'plainte', 'Plainte spam'
        IMPORT = 'import', "Liste d'opposition importée"

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='suppressions_marketing',
        verbose_name='Société',
    )
    destinataire = models.CharField(
        max_length=255, verbose_name='Destinataire (email/téléphone normalisé)')
    motif = models.CharField(
        max_length=12, choices=Motif.choices, default=Motif.DESINSCRIT,
        verbose_name='Motif')
    source = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Source')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        db_table = 'compta_suppressionmarketing'
        verbose_name = 'Suppression marketing'
        verbose_name_plural = 'Suppressions marketing'
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'destinataire'],
                name='uniq_suppression_marketing_par_destinataire',
            ),
        ]

    def __str__(self):
        return f'{self.destinataire} ({self.motif})'


# ── XMKT5 — Listes de diffusion nommées + abonnements ───────────────────────

class ListeDiffusion(models.Model):
    """Liste de diffusion nommée et réutilisable (XMKT5), cible additionnelle
    d'une ``Campagne`` en plus du segment JSON libre.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='listes_diffusion',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom de la liste')
    description = models.TextField(blank=True, default='',
                                   verbose_name='Description')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        db_table = 'compta_listediffusion'
        verbose_name = 'Liste de diffusion'
        verbose_name_plural = 'Listes de diffusion'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class AbonnementListe(models.Model):
    """Abonnement d'un contact à une ``ListeDiffusion`` (XMKT5).

    ``contact_ref`` est une référence OPAQUE lead/client (jamais d'import des
    modèles crm/ventes). Dédoublonnage par destinataire normalisé à
    l'import ; l'historique d'adhésion horodaté vit sur ce même enregistrement
    (``date_creation``/``date_maj``).
    """
    class Statut(models.TextChoices):
        INSCRIT = 'inscrit', 'Inscrit'
        DESINSCRIT = 'desinscrit', 'Désinscrit'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='abonnements_liste',
        verbose_name='Société',
    )
    liste = models.ForeignKey(
        ListeDiffusion,
        on_delete=models.CASCADE,
        related_name='abonnements',
        verbose_name='Liste',
    )
    destinataire = models.CharField(
        max_length=255, verbose_name='Destinataire (email/téléphone normalisé)')
    contact_ref = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Référence contact (lead/client, opaque)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.INSCRIT,
        verbose_name='Statut')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')
    date_maj = models.DateTimeField(
        auto_now=True, verbose_name='Mis à jour le')

    class Meta:
        db_table = 'compta_abonnementliste'
        verbose_name = 'Abonnement à une liste'
        verbose_name_plural = 'Abonnements à une liste'
        ordering = ['-date_creation']
        constraints = [
            models.UniqueConstraint(
                fields=['liste', 'destinataire'],
                name='uniq_abonnement_par_destinataire_liste',
            ),
        ]

    def __str__(self):
        return f'{self.destinataire} → {self.liste_id} ({self.statut})'


# ── XMKT6 — Segments dynamiques enregistrés et réutilisables ────────────────

class SegmentMarketing(models.Model):
    """Segment NOMMÉ et réutilisable, auto-actualisé à chaque usage (XMKT6).

    ``regles`` est un JSON validé (champs lead whitelistés, lus via
    ``apps.crm.selectors.leads_matching_regles`` — jamais d'import du modèle
    CRM) + des règles d'activité marketing optionnelles évaluées sur
    ``EnvoiCampagne`` (XMKT2) : ``activite: 'a_ouvert' | 'a_clique' |
    'jamais_ouvert'``. Utilisable par les campagnes ET les séquences.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='segments_marketing',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du segment')
    regles = models.JSONField(
        default=dict, blank=True, verbose_name='Règles (JSON)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_segmentmarketing'
        verbose_name = 'Segment marketing'
        verbose_name_plural = 'Segments marketing'
        ordering = ['nom']

    def __str__(self):
        return self.nom


# ── XMKT12 — Gestion des rebonds hard/soft ──────────────────────────────────

class RebondSoft(models.Model):
    """Compteur de rebonds SOFT par destinataire (XMKT12), à travers TOUTES
    les campagnes — un rebond soft persiste au-delà d'un seul envoi. Une fois
    ``compte`` >= au seuil société (défaut 3, paramétrable par l'appelant),
    le destinataire est supprimé (XMKT3) comme un rebond dur.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='rebonds_soft',
        verbose_name='Société',
    )
    destinataire = models.CharField(max_length=255, verbose_name='Destinataire')
    compte = models.PositiveIntegerField(default=0, verbose_name='Nombre de rebonds soft')
    date_maj = models.DateTimeField(auto_now=True, verbose_name='Mis à jour le')

    class Meta:
        db_table = 'compta_rebondsoft'
        verbose_name = 'Rebond soft'
        verbose_name_plural = 'Rebonds soft'
        ordering = ['-date_maj']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'destinataire'],
                name='uniq_rebond_soft_par_destinataire',
            ),
        ]

    def __str__(self):
        return f'{self.destinataire} ({self.compte})'


# ── FG202 — Séquences de relance automatisées (drip / nurture) ─────────────

class SequenceRelance(models.Model):
    """Séquence multi-étapes déclenchée par l'entrée d'un lead en étape (FG202).

    Exemple : J0 WhatsApp → J3 email → J7 appel. La séquence est attachée à un
    déclencheur (l'entrée dans une étape du pipeline, désignée par sa CLÉ
    canonique ``STAGES.py`` stockée en texte — jamais codée en dur ici). Les
    étapes réelles (envoi WhatsApp/email) sont gated comme FG201 : tant que les
    intégrations sont OFF, le moteur ne fait qu'enregistrer/planifier, sans
    appel payant.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='sequences_relance',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom de la séquence')
    # Clé de l'étape déclencheuse (vient de STAGES.py — stockée en texte, jamais
    # hardcodée dans le code). Vide = manuelle.
    stage_declencheur = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name="Clé d'étape déclencheuse")
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        db_table = 'compta_sequencerelance'
        verbose_name = 'Séquence de relance'
        verbose_name_plural = 'Séquences de relance'
        ordering = ['nom']

    def __str__(self):
        return self.nom


class EtapeSequence(models.Model):
    """Une étape d'une séquence de relance (FG202).

    ``delai_jours`` = décalage depuis le déclenchement (J0, J3, J7…). ``canal``
    = WhatsApp/email/appel. L'ordre détermine l'enchaînement.
    """
    class Canal(models.TextChoices):
        WHATSAPP = 'whatsapp', 'WhatsApp'
        EMAIL = 'email', 'Email'
        APPEL = 'appel', 'Appel'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='etapes_sequence',
        verbose_name='Société',
    )
    sequence = models.ForeignKey(
        SequenceRelance,
        on_delete=models.CASCADE,
        related_name='etapes',
        verbose_name='Séquence',
    )
    ordre = models.PositiveIntegerField(default=1, verbose_name='Ordre')
    delai_jours = models.PositiveIntegerField(
        default=0, verbose_name='Délai (jours depuis le déclenchement)')
    canal = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.EMAIL,
        verbose_name='Canal')
    modele_message = models.TextField(
        blank=True, default='', verbose_name='Modèle de message')

    # ── XMKT18 — condition d'exécution + action alternative ─────────────────
    class Condition(models.TextChoices):
        TOUJOURS = 'toujours', 'Toujours'
        A_OUVERT = 'a_ouvert', 'A ouvert'
        A_CLIQUE = 'a_clique', 'A cliqué'
        N_A_PAS_OUVERT = 'n_a_pas_ouvert', "N'a pas ouvert"
        A_REPONDU = 'a_repondu', 'A répondu (WhatsApp)'

    condition = models.CharField(
        max_length=20, choices=Condition.choices, default=Condition.TOUJOURS,
        verbose_name="Condition d'exécution")
    # Action alternative si la condition est fausse (ex. non-ouvert après 3j
    # → renvoyer avec un autre objet ; cliqué → tâche commerciale). Vide =
    # aucune action alternative (comportement actuel : étape simplement
    # sautée si la condition n'est pas vraie).
    action_alternative = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='Action alternative si condition fausse')

    # ── XMKT19 — actions CRM dans les étapes de séquence ────────────────────
    class TypeEtape(models.TextChoices):
        MESSAGE = 'message', 'Message (canal)'
        ACTION_CRM = 'action_crm', 'Action CRM'

    type_etape = models.CharField(
        max_length=12, choices=TypeEtape.choices, default=TypeEtape.MESSAGE,
        verbose_name="Type d'étape")
    # Config de l'action CRM si ``type_etape == 'action_crm'`` :
    # {"action": "avancer_stage"|"assigner"|"tag"|"score"|"tache",
    #  "params": {...}} — jamais de clé de stage hardcodée, la valeur vient
    # toujours de STAGES.py côté appelant (crm.services).
    action_crm = models.JSONField(
        default=dict, blank=True, verbose_name='Action CRM (JSON)')

    class Meta:
        db_table = 'compta_etapesequence'
        verbose_name = 'Étape de séquence'
        verbose_name_plural = 'Étapes de séquence'
        ordering = ['sequence', 'ordre']
        constraints = [
            models.UniqueConstraint(
                fields=['sequence', 'ordre'],
                name='uniq_etape_sequence_ordre',
            ),
        ]

    def __str__(self):
        return f'{self.sequence_id} #{self.ordre} ({self.canal}, J+{self.delai_jours})'


# ── XMKT1 — Moteur d'exécution réel des séquences de relance ───────────────

class InscriptionSequence(models.Model):
    """Un lead inscrit dans une séquence de relance (FG202), en cours d'exécution.

    ``lead_id`` est une référence OPAQUE vers ``crm.Lead`` (jamais d'import du
    modèle CRM — lu via ``apps/crm/selectors.get_company_lead``). L'inscription
    avance étape par étape ; ``etape_courante`` pointe la prochaine étape à
    exécuter (``None`` = toutes les étapes sont passées → statut ``termine``).
    """
    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        SORTI = 'sorti', 'Sorti'
        TERMINE = 'termine', 'Terminé'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='inscriptions_sequence',
        verbose_name='Société',
    )
    sequence = models.ForeignKey(
        SequenceRelance,
        on_delete=models.CASCADE,
        related_name='inscriptions',
        verbose_name='Séquence',
    )
    lead_id = models.PositiveIntegerField(verbose_name='Lead (référence opaque)')
    lead_reference = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Référence lisible du lead')
    etape_courante = models.ForeignKey(
        EtapeSequence,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inscriptions_en_cours',
        verbose_name='Étape courante',
    )
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    motif_sortie = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de sortie')
    declenchee_le = models.DateTimeField(
        auto_now_add=True, verbose_name="Déclenchée le")
    sortie_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Sortie le')

    class Meta:
        db_table = 'compta_inscriptionsequence'
        verbose_name = 'Inscription à une séquence'
        verbose_name_plural = 'Inscriptions à une séquence'
        ordering = ['-declenchee_le']
        constraints = [
            models.UniqueConstraint(
                fields=['sequence', 'lead_id'],
                condition=models.Q(statut='actif'),
                name='uniq_inscription_active_par_lead',
            ),
        ]

    def __str__(self):
        return f'Lead {self.lead_id} → {self.sequence_id} ({self.statut})'


class ExecutionEtapeSequence(models.Model):
    """Trace d'une exécution d'étape pour une inscription (XMKT1).

    Une ligne par étape effectivement traitée (envoyée ou planifiée en manuel
    faute de clé d'intégration — cf. FG31), pour un journal lisible par
    participant : quel nœud, quand, quoi envoyé, erreur éventuelle.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='executions_etape_sequence',
        verbose_name='Société',
    )
    inscription = models.ForeignKey(
        InscriptionSequence,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='Inscription',
    )
    etape = models.ForeignKey(
        EtapeSequence,
        on_delete=models.CASCADE,
        related_name='executions',
        verbose_name='Étape',
    )
    execute_le = models.DateTimeField(
        auto_now_add=True, verbose_name='Exécutée le')
    canal = models.CharField(max_length=10, blank=True, default='',
                             verbose_name='Canal')
    resultat = models.CharField(
        max_length=20, default='planifie',
        verbose_name='Résultat (planifie/envoye/erreur)')
    erreur = models.CharField(max_length=500, blank=True, default='',
                              verbose_name='Erreur')
    # XMKT18 — branche prise à l'exécution : vide (pas de condition/toujours),
    # 'condition' (condition vraie, étape normale exécutée) ou 'alternative'
    # (condition fausse, action alternative exécutée à la place).
    branche_prise = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Branche prise (XMKT18)')

    # ── ZMKT5 — traces d'activité (planifié/traité/rejeté) + motif ──────────
    class StatutTrace(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        TRAITE = 'traite', 'Traité'
        REJETE = 'rejete', 'Rejeté'

    class MotifRejet(models.TextChoices):
        SANS_CONSENTEMENT = 'sans_consentement', 'Pas de consentement'
        SUPPRIME = 'supprime', 'Supprimé (liste de suppression)'
        HORS_FENETRE = 'hors_fenetre', 'Hors fenêtre de silence'
        ERREUR_ENVOI = 'erreur_envoi', "Erreur d'envoi"

    statut_trace = models.CharField(
        max_length=10, choices=StatutTrace.choices,
        default=StatutTrace.TRAITE, verbose_name='Statut de trace')
    motif_rejet = models.CharField(
        max_length=20, choices=MotifRejet.choices, blank=True, default='',
        verbose_name='Motif de rejet')

    class Meta:
        db_table = 'compta_executionetapesequence'
        verbose_name = "Exécution d'étape de séquence"
        verbose_name_plural = "Exécutions d'étape de séquence"
        ordering = ['-execute_le']

    def __str__(self):
        return f'{self.inscription_id} · étape {self.etape_id} ({self.resultat})'


# ── XMKT9 — Tracker de liens + auto-tag UTM ─────────────────────────────────

class LienTrackee(models.Model):
    """Un lien du corps d'une campagne, réécrit en redirection tokenisée
    (XMKT9) : ``/r/<token>`` → ``url_cible`` auto-taguée
    utm_source/medium/campaign=nom de la campagne. Compte les clics PAR LIEN.

    ``campagne`` NULL (XMKT29) : le lien tracké n'est pas issu d'un corps de
    campagne mais d'un ``SupportOffline`` (QR flyer/bâche/véhicule) —
    réutilise le même mécanisme de redirection tokenisée + comptage.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='liens_trackes',
        verbose_name='Société',
    )
    campagne = models.ForeignKey(
        Campagne,
        on_delete=models.CASCADE,
        related_name='liens_trackes',
        verbose_name='Campagne',
        null=True, blank=True,
    )
    token = models.CharField(
        max_length=64, unique=True, verbose_name='Jeton public')
    url_cible = models.URLField(max_length=1000, verbose_name='URL cible')
    nb_clics = models.PositiveIntegerField(default=0, verbose_name='Clics')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_lientrackee'
        verbose_name = 'Lien tracké'
        verbose_name_plural = 'Liens trackés'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.campagne_id} → {self.url_cible[:60]} ({self.nb_clics})'


class ClicLien(models.Model):
    """Un clic sur un ``LienTrackee``, par destinataire (XMKT9) — alimente le
    drill-down « clics par lien » sur le détail campagne.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='clics_lien',
        verbose_name='Société',
    )
    lien = models.ForeignKey(
        LienTrackee,
        on_delete=models.CASCADE,
        related_name='clics',
        verbose_name='Lien tracké',
    )
    destinataire = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Destinataire (email/téléphone, si connu)')
    clique_le = models.DateTimeField(
        auto_now_add=True, verbose_name='Cliqué le')

    class Meta:
        db_table = 'compta_cliclien'
        verbose_name = 'Clic de lien'
        verbose_name_plural = 'Clics de lien'
        ordering = ['-clique_le']

    def __str__(self):
        return f'{self.lien_id} ← {self.destinataire or "?"}'


# ── XMKT22 — Politique « sunset » d'engagement ──────────────────────────────

class StatutEngagementContact(models.Model):
    """Statut d'engagement d'un destinataire marketing (XMKT22) : ``dormant``
    quand il n'a ouvert/cliqué aucun envoi sur une fenêtre paramétrable
    (90-180 j). Un contact dormant est sauté aux envois (journalisé XMKT2)
    tant qu'il n'a pas cliqué une campagne de re-permission.
    """
    class Statut(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        DORMANT = 'dormant', 'Dormant'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='statuts_engagement',
        verbose_name='Société',
    )
    destinataire = models.CharField(
        max_length=255, verbose_name='Destinataire (email/téléphone normalisé)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.ACTIF,
        verbose_name='Statut')
    date_maj = models.DateTimeField(auto_now=True, verbose_name='Mis à jour le')

    class Meta:
        db_table = 'compta_statutengagementcontact'
        verbose_name = "Statut d'engagement (contact)"
        verbose_name_plural = "Statuts d'engagement (contacts)"
        ordering = ['-date_maj']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'destinataire'],
                name='uniq_statut_engagement_par_destinataire',
            ),
        ]

    def __str__(self):
        return f'{self.destinataire} ({self.statut})'


# ── XMKT23 — Approbation avant envoi de masse + journal d'audit ────────────

class ApprobationEnvoiCampagne(models.Model):
    """Demande d'approbation d'un envoi de masse (XMKT23), pattern identique à
    ``automation.AutomationApproval`` (pending/approved/rejected) mais local à
    marketing — au-delà d'un seuil société de destinataires, l'envoi reste
    bloqué tant qu'un Responsable/Directeur n'a pas approuvé.
    """
    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPROUVE = 'approuve', 'Approuvé'
        REJETE = 'rejete', 'Rejeté'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='approbations_envoi_campagne',
        verbose_name='Société',
    )
    campagne = models.ForeignKey(
        Campagne,
        on_delete=models.CASCADE,
        related_name='approbations_envoi',
        verbose_name='Campagne',
    )
    nb_destinataires_demandes = models.PositiveIntegerField(
        default=0, verbose_name='Nb destinataires demandés')
    statut = models.CharField(
        max_length=12, choices=Statut.choices, default=Statut.EN_ATTENTE,
        verbose_name='Statut')
    demande_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approbations_envoi_demandees',
        verbose_name='Demandé par',
    )
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approbations_envoi_decidees',
        verbose_name='Décidé par',
    )
    motif_rejet = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Motif de rejet')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')
    date_decision = models.DateTimeField(
        null=True, blank=True, verbose_name='Décidée le')

    class Meta:
        db_table = 'compta_approbationenvoicampagne'
        verbose_name = "Approbation d'envoi de campagne"
        verbose_name_plural = "Approbations d'envoi de campagne"
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.campagne_id} ({self.statut})'


# ── FG203 — Récupération des devis abandonnés ──────────────────────────────

class RelanceDevisAbandonne(models.Model):
    """Trace d'une relance sur un devis envoyé non répondu après N jours (FG203).

    On ne touche JAMAIS le modèle Devis (ventes) : on le référence par sa
    ``devis_reference`` (texte) et son ``devis_id`` (entier opaque), lus via les
    selectors de ventes. Ce log consigne la relance émise (jamais l'envoi
    lui-même), comme ``RelanceLog`` côté factures.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='relances_devis_abandonnes',
        verbose_name='Société',
    )
    devis_id = models.PositiveIntegerField(verbose_name='Devis (id ventes)')
    devis_reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence devis')
    jours_sans_reponse = models.PositiveIntegerField(
        default=0, verbose_name='Jours sans réponse à la relance')
    canal = models.CharField(
        max_length=20, blank=True, default='', verbose_name='Canal de relance')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    date_relance = models.DateTimeField(
        auto_now_add=True, verbose_name='Relancé le')

    class Meta:
        db_table = 'compta_relancedevisabandonne'
        verbose_name = 'Relance devis abandonné'
        verbose_name_plural = 'Relances devis abandonnés'
        ordering = ['-date_relance']

    def __str__(self):
        return f'Relance devis {self.devis_reference or self.devis_id}'


# ── FG205 — Tracking d'ouverture des ShareLink devis/facture ───────────────

class OuverturePartage(models.Model):
    """Horodatage des ouvertures d'un lien de partage devis/facture (FG205).

    Le ShareLink lui-même vit dans ventes ; on ne l'importe pas. On indexe ici
    les ÉVÉNEMENTS d'ouverture par ``token`` (texte opaque) pour prioriser les
    relances : premier vu, dernier vu, nombre de vues. Aucune donnée client
    n'est dupliquée.
    """
    class Cible(models.TextChoices):
        DEVIS = 'devis', 'Devis'
        FACTURE = 'facture', 'Facture'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='ouvertures_partage',
        verbose_name='Société',
    )
    token = models.CharField(max_length=64, db_index=True,
                             verbose_name='Token du lien de partage')
    cible = models.CharField(
        max_length=8, choices=Cible.choices, default=Cible.DEVIS,
        verbose_name='Cible')
    cible_reference = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name='Référence document')
    nb_ouvertures = models.PositiveIntegerField(
        default=0, verbose_name="Nombre d'ouvertures")
    premier_vu_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Premier vu le')
    dernier_vu_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernier vu le')

    class Meta:
        db_table = 'compta_ouverturepartage'
        verbose_name = "Ouverture de lien de partage"
        verbose_name_plural = "Ouvertures de liens de partage"
        ordering = ['-dernier_vu_le']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'token'],
                name='uniq_ouverture_partage_token',
            ),
        ]

    def __str__(self):
        return f'{self.cible} {self.token[:8]}… ({self.nb_ouvertures} vues)'


# ── FG206 — Constructeur de formulaires / landing pages multiples ──────────

class FormulaireIntake(models.Model):
    """Définition d'un formulaire d'intake / landing page (FG206).

    Plusieurs formulaires d'entrée (pompage agricole, régularisation 82-21…),
    chacun pré-taguant le lead créé avec un ``tag_prefill`` et un
    ``type_installation`` par défaut. Les champs sont décrits en JSON (libre).
    Le slug tokenisé rend la page adressable publiquement (création de lead via
    crm.services, jamais d'import de modèles crm).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='formulaires_intake',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du formulaire')
    slug = models.SlugField(max_length=80, verbose_name='Slug public')
    tag_prefill = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Tag pré-rempli sur le lead')
    type_installation = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name="Type d'installation par défaut")
    champs = models.JSONField(
        default=list, blank=True, verbose_name='Définition des champs (JSON)')
    actif = models.BooleanField(default=True, verbose_name='Actif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_formulaireintake'
        verbose_name = "Formulaire d'intake"
        verbose_name_plural = "Formulaires d'intake"
        ordering = ['nom']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'slug'],
                name='uniq_formulaire_intake_slug',
            ),
        ]

    def __str__(self):
        return self.nom


# ── FG207 — Capture de leads via WhatsApp (inbound, GATED) ─────────────────

class MessageWhatsAppEntrant(models.Model):
    """Message WhatsApp entrant capturé pour créer un lead pré-qualifié (FG207).

    L'intégration WhatsApp Business Cloud (Meta) est GATED : sans le jeton
    fourni par le founder, le webhook entrant est inactif (NO-OP) et aucun
    message n'est traité. Quand activé, chaque message crée/rattache un lead
    DRAFT via ``crm.services`` (jamais d'import de modèles crm), en laissant le
    funnel à NEW. Ce modèle journalise l'entrée pour audit/idempotence.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='messages_whatsapp_entrants',
        verbose_name='Société',
    )
    wa_message_id = models.CharField(
        max_length=128, verbose_name='ID message WhatsApp')
    expediteur = models.CharField(
        max_length=32, verbose_name='Numéro expéditeur')
    nom_profil = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Nom du profil')
    texte = models.TextField(blank=True, default='', verbose_name='Texte')
    # Id opaque du lead créé/rattaché côté crm (jamais un FK direct cross-app).
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Lead créé (id crm)')
    traite = models.BooleanField(default=False, verbose_name='Traité')
    date_reception = models.DateTimeField(
        auto_now_add=True, verbose_name='Reçu le')

    class Meta:
        db_table = 'compta_messagewhatsappentrant'
        verbose_name = 'Message WhatsApp entrant'
        verbose_name_plural = 'Messages WhatsApp entrants'
        ordering = ['-date_reception']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'wa_message_id'],
                name='uniq_wa_message_entrant',
            ),
        ]

    def __str__(self):
        return f'WA {self.expediteur} ({self.wa_message_id[:10]}…)'


# ── FG208 — Journal d'appels & click-to-call ───────────────────────────────

class AppelTelephonique(models.Model):
    """Consigne d'un appel téléphonique et de son issue (FG208).

    Mesure l'effort téléphonique. Le bouton ``tel:`` (click-to-call) est un
    rendu front pur ; côté backend on enregistre l'appel, sa direction, sa durée
    et son issue. Le lead/contact est référencé par id opaque (jamais un FK
    cross-app vers crm).
    """
    class Direction(models.TextChoices):
        SORTANT = 'sortant', 'Sortant'
        ENTRANT = 'entrant', 'Entrant'

    class Issue(models.TextChoices):
        REPONDU = 'repondu', 'Répondu'
        SANS_REPONSE = 'sans_reponse', 'Sans réponse'
        RAPPEL = 'rappel', 'À rappeler'
        FAUX_NUMERO = 'faux_numero', 'Faux numéro'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='appels_telephoniques',
        verbose_name='Société',
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='appels_passes',
        verbose_name='Auteur',
    )
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Lead (id crm)')
    numero = models.CharField(max_length=32, verbose_name='Numéro')
    direction = models.CharField(
        max_length=8, choices=Direction.choices, default=Direction.SORTANT,
        verbose_name='Direction')
    issue = models.CharField(
        max_length=14, choices=Issue.choices, default=Issue.REPONDU,
        verbose_name='Issue')
    duree_secondes = models.PositiveIntegerField(
        default=0, verbose_name='Durée (s)')
    note = models.TextField(blank=True, default='', verbose_name='Note')
    a_rappeler_le = models.DateField(
        null=True, blank=True, verbose_name='À rappeler le')
    date_appel = models.DateTimeField(
        auto_now_add=True, verbose_name='Appelé le')

    class Meta:
        db_table = 'compta_appeltelephonique'
        verbose_name = "Journal d'appel"
        verbose_name_plural = "Journal d'appels"
        ordering = ['-date_appel']

    def __str__(self):
        return f'{self.direction} {self.numero} ({self.issue})'


# ── FG238 — Enquête de satisfaction / NPS post-installation ────────────────

class EnqueteNPS(models.Model):
    """Enquête de satisfaction / NPS post-installation (FG238).

    Envoyée automatiquement après réception d'un chantier (envoi RÉEL gated
    Brevo — NO-OP tant que ``BREVO_ENABLED`` est OFF). Le client répond une note
    0–10 : promoteur (9–10), passif (7–8), détracteur (0–6). Le score NPS
    consolidé = % promoteurs − % détracteurs. Client/chantier référencés par id
    (cross-app). Scopée société.
    """
    class Statut(models.TextChoices):
        ENVOYEE = 'envoyee', 'Envoyée'
        REPONDUE = 'repondue', 'Répondue'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='enquetes_nps',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    chantier_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Id du chantier')
    score = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Note (0–10)')
    commentaire = models.TextField(
        blank=True, default='', verbose_name='Commentaire')
    statut = models.CharField(
        max_length=8, choices=Statut.choices, default=Statut.ENVOYEE,
        verbose_name='Statut')
    envoi_reel = models.BooleanField(
        default=False, verbose_name='Envoi réel effectué (Brevo)')
    envoyee_le = models.DateTimeField(
        auto_now_add=True, verbose_name='Envoyée le')
    repondue_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Répondue le')

    class Meta:
        db_table = 'compta_enquetenps'
        verbose_name = 'Enquête NPS'
        verbose_name_plural = 'Enquêtes NPS'
        ordering = ['-envoyee_le']

    def __str__(self):
        return f'NPS client #{self.client_id} ({self.statut})'

    @property
    def categorie(self):
        """Catégorie NPS de la réponse (promoteur/passif/détracteur)."""
        if self.score is None:
            return None
        if self.score >= 9:
            return 'promoteur'
        if self.score >= 7:
            return 'passif'
        return 'detracteur'


# ── FG239 — Capture d'avis/témoignages + push Google Reviews ───────────────

class AvisClient(models.Model):
    """Avis / témoignage client + routage vers Google Reviews (FG239).

    On sollicite un avis (in-app), on capture la note + le témoignage, puis on
    ROUTE le client satisfait vers Google (preuve sociale) via un lien de dépôt
    d'avis Google (paramètre société ``GOOGLE_REVIEW_URL`` — pas d'API payante,
    juste une URL). Le push est un NO-OP propre si l'URL n'est pas configurée.
    Client référencé par id (cross-app). Scopé société.
    """
    class Statut(models.TextChoices):
        SOLLICITE = 'sollicite', 'Sollicité'
        RECU = 'recu', 'Reçu'
        PUBLIE_GOOGLE = 'publie_google', 'Routé vers Google'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='avis_clients',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    note = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Note (1–5)')
    temoignage = models.TextField(
        blank=True, default='', verbose_name='Témoignage')
    statut = models.CharField(
        max_length=14, choices=Statut.choices, default=Statut.SOLLICITE,
        verbose_name='Statut')
    google_review_url = models.URLField(
        blank=True, default='', verbose_name='Lien Google Reviews')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_avisclient'
        verbose_name = 'Avis client'
        verbose_name_plural = 'Avis clients'
        ordering = ['-date_creation']

    def __str__(self):
        return f'Avis client #{self.client_id} ({self.statut})'


# ── FG240 — Programme de fidélité / parrainage étendu ──────────────────────

class CompteFidelite(models.Model):
    """Compte de fidélité d'un client : solde de points + palier (FG240).

    Étend le parrainage simple existant (``crm.Parrainage``) avec des POINTS
    cumulables et des PALIERS (bronze/argent/or/platine) recalculés depuis le
    solde. Client référencé par id (cross-app — jamais d'import crm). Un compte
    par client et par société. Les mouvements (gains/dépenses) vivent dans
    ``MouvementFidelite``.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='comptes_fidelite',
        verbose_name='Société',
    )
    client_id = models.PositiveIntegerField(verbose_name='Id du client')
    points = models.IntegerField(default=0, verbose_name='Solde de points')
    palier = models.CharField(
        max_length=10,
        choices=[
            ('bronze', 'Bronze'),
            ('argent', 'Argent'),
            ('or', 'Or'),
            ('platine', 'Platine'),
        ],
        default='bronze',
        verbose_name='Palier')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_comptefidelite'
        verbose_name = 'Compte de fidélité'
        verbose_name_plural = 'Comptes de fidélité'
        ordering = ['-points']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'client_id'],
                name='uniq_compte_fidelite_client',
            ),
        ]

    def __str__(self):
        return f'Fidélité client #{self.client_id} — {self.points} pts'


class MouvementFidelite(models.Model):
    """Mouvement de points sur un compte de fidélité (FG240).

    ``points`` positif = gain (parrainage réussi, achat…), négatif = dépense
    (remise convertie). Le solde et le palier du compte sont recalculés par le
    service à chaque mouvement. Scopé société.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='mouvements_fidelite',
        verbose_name='Société',
    )
    compte = models.ForeignKey(
        CompteFidelite,
        on_delete=models.CASCADE,
        related_name='mouvements',
        verbose_name='Compte de fidélité',
    )
    points = models.IntegerField(verbose_name='Points (+ gain / − dépense)')
    motif = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Motif')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_mouvementfidelite'
        verbose_name = 'Mouvement de fidélité'
        verbose_name_plural = 'Mouvements de fidélité'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.points:+d} pts — client #{self.compte.client_id}'


# ── FG241 — Moteur d'upsell / cross-sell ───────────────────────────────────

class RegleUpsell(models.Model):
    """Règle de suggestion contextuelle d'upsell / cross-sell (FG241).

    Chaque règle porte un DÉCLENCHEUR (clé de contexte, ex. ``sans_batterie``,
    ``site_unique``, ``sans_contrat_om``) et une SUGGESTION (libellé produit /
    service + message commercial). Le service ``suggestions_upsell`` évalue un
    contexte client (dict de drapeaux) et renvoie les suggestions actives dont
    le déclencheur est vrai, triées par priorité. Scopée société.
    """
    class Declencheur(models.TextChoices):
        SANS_BATTERIE = 'sans_batterie', 'Client sans batterie'
        SITE_UNIQUE = 'site_unique', 'Un seul site équipé'
        SANS_CONTRAT_OM = 'sans_contrat_om', 'Sans contrat O&M'
        INSTALLATION_ANCIENNE = 'installation_ancienne', 'Installation ancienne'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='regles_upsell',
        verbose_name='Société',
    )
    declencheur = models.CharField(
        max_length=24, choices=Declencheur.choices,
        verbose_name='Déclencheur de contexte')
    produit_suggere = models.CharField(
        max_length=200, verbose_name='Produit / service suggéré')
    message = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Message commercial')
    priorite = models.IntegerField(
        default=0, verbose_name='Priorité (haute = affichée en premier)')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        db_table = 'compta_regleupsell'
        verbose_name = "Règle d'upsell / cross-sell"
        verbose_name_plural = "Règles d'upsell / cross-sell"
        ordering = ['-priorite', 'id']

    def __str__(self):
        return f'{self.get_declencheur_display()} → {self.produit_suggere}'


# ── XMKT27 / FG238 — Enquêtes configurables (au-delà du NPS figé) ──────────

class Enquete(models.Model):
    """Enquête configurable au-delà du NPS figé (XMKT27, FG238).

    ``questions`` est un JSON validé : liste de
    ``{"id": "q1", "type": "choix"|"echelle"|"texte"|"nps", "libelle": ...,
    "options": [...], "obligatoire": bool,
    "condition": {"question_id": "q0", "valeur": ...}}`` — affichage
    conditionnel « question B si réponse A ». Lien public tokenisé
    (``token``), aucune authentification requise pour répondre.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='enquetes',
        verbose_name='Société',
    )
    titre = models.CharField(max_length=200, verbose_name='Titre')
    questions = models.JSONField(
        default=list, blank=True, verbose_name='Questions (JSON)')
    token = models.CharField(
        max_length=64, unique=True, verbose_name='Jeton public')
    actif = models.BooleanField(default=True, verbose_name='Active')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    # ── ZMKT9 — options de mise en page & anti-biais ────────────────────────
    class ModePagination(models.TextChoices):
        UNE_PAGE = 'une_page', 'Une page'
        UNE_PAGE_PAR_SECTION = 'une_page_par_section', 'Une page par section'
        UNE_PAGE_PAR_QUESTION = 'une_page_par_question', 'Une page par question'

    class BarreProgression(models.TextChoices):
        AUCUNE = 'aucune', 'Aucune'
        POURCENTAGE = 'pourcentage', 'Pourcentage'
        NOMBRE = 'nombre', 'Nombre'

    mode_pagination = models.CharField(
        max_length=25, choices=ModePagination.choices,
        default=ModePagination.UNE_PAGE, verbose_name='Mode de pagination')
    barre_progression = models.CharField(
        max_length=12, choices=BarreProgression.choices,
        default=BarreProgression.AUCUNE, verbose_name='Barre de progression')
    bouton_retour = models.BooleanField(
        default=False, verbose_name='Bouton retour')
    limite_temps_minutes = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Limite de temps (minutes)')
    ordre_aleatoire = models.BooleanField(
        default=False, verbose_name='Ordre aléatoire des questions')

    # ── ZMKT10 — scoring d'enquête + mode certification ─────────────────────
    class ModeScoring(models.TextChoices):
        AUCUN = 'aucun', 'Aucun'
        AVEC_REPONSES = 'avec_reponses_a_la_fin', 'Avec réponses à la fin'
        SANS_REPONSES = 'sans_reponses', 'Sans réponses'

    mode_scoring = models.CharField(
        max_length=25, choices=ModeScoring.choices,
        default=ModeScoring.AUCUN, verbose_name='Mode de scoring')
    score_requis_pct = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Score requis (%)')
    est_certification = models.BooleanField(
        default=False, verbose_name='Est une certification')

    # ── ZMKT11 — mode d'accès, connexion requise, tentatives max ────────────
    class ModeAcces(models.TextChoices):
        LIEN_PUBLIC = 'lien_public', 'Lien public'
        INVITES_SEULEMENT = 'invites_seulement', 'Invités seulement'

    mode_acces = models.CharField(
        max_length=20, choices=ModeAcces.choices,
        default=ModeAcces.LIEN_PUBLIC, verbose_name="Mode d'accès")
    connexion_requise = models.BooleanField(
        default=False, verbose_name='Connexion requise (email de contact)')
    tentatives_max = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Tentatives max par répondant')
    # Jetons d'invitation valides (ZMKT11, mode invités-seulement) : liste de
    # jetons émis explicitement, jamais un lien public ouvert.
    jetons_invites = models.JSONField(
        default=list, blank=True, verbose_name="Jetons d'invitation (JSON)")

    # ── ZMKT12 — partage par lien / email / QR ──────────────────────────────
    description_accueil = models.TextField(
        blank=True, default='',
        verbose_name="Description d'accueil (avant de commencer)")
    message_fin = models.TextField(
        blank=True, default='', verbose_name='Message de fin (complétion)')

    class Meta:
        db_table = 'compta_enquete'
        verbose_name = 'Enquête'
        verbose_name_plural = 'Enquêtes'
        ordering = ['-date_creation']

    def __str__(self):
        return self.titre


class ReponseEnquete(models.Model):
    """Une soumission de réponses à une ``Enquete`` (XMKT27).

    ``reponses`` est un JSON ``{"q1": "valeur", ...}``. ``contact_ref`` est
    une référence OPAQUE lead/client (``lead:<id>``/``client:<id>``, jamais
    d'import direct des modèles crm/ventes) — vide si le répondant n'est pas
    identifié (lien public anonyme).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='reponses_enquete',
        verbose_name='Société',
    )
    enquete = models.ForeignKey(
        Enquete,
        on_delete=models.CASCADE,
        related_name='reponses',
        verbose_name='Enquête',
    )
    contact_ref = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Référence contact (lead/client, opaque)')
    reponses = models.JSONField(
        default=dict, blank=True, verbose_name='Réponses (JSON)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Soumise le')

    # ── ZMKT10 — score calculé + certificat ─────────────────────────────────
    score_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Score obtenu (%)')
    reussi = models.BooleanField(
        null=True, blank=True, verbose_name='Réussi (si scoring/certification)')
    certificat_genere = models.BooleanField(
        default=False, verbose_name='Certificat généré')

    class Meta:
        db_table = 'compta_reponseenquete'
        verbose_name = 'Réponse à une enquête'
        verbose_name_plural = 'Réponses à une enquête'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.enquete_id} ← {self.contact_ref or "anonyme"}'


# ── ZMKT14 — Types d'événements + modèles réutilisables ─────────────────────

class TypeEvenement(models.Model):
    """Modèle réutilisable pour créer un ``EvenementMarketing`` (ZMKT14) :
    « créer depuis modèle » recopie sa config par défaut (billets ZMKT15,
    questions ZMKT16, communications ZMKT17 — pré-chargés au moment de leur
    implémentation ; ``config_defaut`` sert de socle générique en attendant).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='types_evenement',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom du modèle')
    type_evenement_defaut = models.CharField(
        max_length=20, default='salon',
        verbose_name="Type d'événement par défaut")
    config_defaut = models.JSONField(
        default=dict, blank=True,
        verbose_name='Configuration par défaut (JSON)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_typeevenement'
        verbose_name = "Type d'événement (modèle)"
        verbose_name_plural = "Types d'événement (modèles)"
        ordering = ['nom']

    def __str__(self):
        return self.nom


# ── XMKT28 — Événements marketing légers (salons, portes ouvertes, webinaires)

class EvenementMarketing(models.Model):
    """Événement marketing léger (XMKT28) : salon (SIAM, foires agricoles),
    porte ouverte, webinaire. L'inscription publique via un
    ``FormulaireIntake`` lié crée un lead dédupliqué (via ``crm.services``) ;
    présents/absents alimentent des segments (XMKT6).
    """
    class Type(models.TextChoices):
        SALON = 'salon', 'Salon'
        PORTE_OUVERTE = 'porte_ouverte', 'Porte ouverte'
        WEBINAIRE = 'webinaire', 'Webinaire'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='evenements_marketing',
        verbose_name='Société',
    )
    nom = models.CharField(max_length=200, verbose_name="Nom de l'événement")
    type_evenement = models.CharField(
        max_length=20, choices=Type.choices, default=Type.SALON,
        verbose_name="Type d'événement")
    date_debut = models.DateTimeField(verbose_name='Date de début')
    date_fin = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de fin')
    lieu = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Lieu (ou lien visio)')
    capacite = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Capacité')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    # ── ZMKT14 — pipeline d'étapes configurable (JAMAIS les clés STAGES.py) ─
    class Etape(models.TextChoices):
        NOUVEAU = 'nouveau', 'Nouveau'
        CONFIRME = 'confirme', 'Confirmé'
        ANNONCE = 'annonce', 'Annoncé'
        TERMINE = 'termine', 'Terminé'

    etape = models.CharField(
        max_length=12, choices=Etape.choices, default=Etape.NOUVEAU,
        verbose_name="Étape (pipeline événement, PAS le funnel CRM)")
    # Type d'événement source (modèle réutilisable, ZMKT14) — nullable, un
    # événement créé sans modèle reste comme aujourd'hui.
    type_modele = models.ForeignKey(
        'marketing.TypeEvenement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='evenements_crees',
        verbose_name='Créé depuis le modèle',
    )

    class Meta:
        db_table = 'compta_evenementmarketing'
        verbose_name = 'Événement marketing'
        verbose_name_plural = 'Événements marketing'
        ordering = ['-date_debut']

    def __str__(self):
        return self.nom


# ── ZMKT15 — Billets d'événement (types, prix MAD, quotas, fenêtre de vente)

class BilletEvenement(models.Model):
    """Billet d'un ``EvenementMarketing`` (ZMKT15) : libellé, prix TTC MAD,
    fenêtre de vente, quota de places. Descripteur de capacité/tarif —
    AUCUN encaissement en ligne ici (le paiement CMI reste la surface
    portail existante).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='billets_evenement',
        verbose_name='Société',
    )
    evenement = models.ForeignKey(
        EvenementMarketing,
        on_delete=models.CASCADE,
        related_name='billets',
        verbose_name='Événement',
    )
    libelle = models.CharField(max_length=200, verbose_name='Libellé')
    prix_ttc_mad = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0'),
        verbose_name='Prix TTC (MAD)')
    date_debut_vente = models.DateTimeField(
        null=True, blank=True, verbose_name='Début de vente')
    date_fin_vente = models.DateTimeField(
        null=True, blank=True, verbose_name='Fin de vente')
    quota = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Quota de places')

    class Meta:
        db_table = 'compta_billetevenement'
        verbose_name = "Billet d'événement"
        verbose_name_plural = "Billets d'événement"
        ordering = ['libelle']

    def __str__(self):
        return f'{self.libelle} ({self.prix_ttc_mad} MAD)'

    def dans_fenetre_vente(self, *, maintenant=None):
        from django.utils import timezone
        maintenant = maintenant or timezone.now()
        if self.date_debut_vente and maintenant < self.date_debut_vente:
            return False
        if self.date_fin_vente and maintenant > self.date_fin_vente:
            return False
        return True

    @property
    def places_restantes(self):
        if self.quota is None:
            return None
        return max(0, self.quota - self.inscriptions.count())


# ── ZMKT16 — Questions d'inscription par événement ──────────────────────────

class QuestionEvenement(models.Model):
    """Question de capture de données à l'inscription (ZMKT16), au-delà de
    nom/email/téléphone. Réponses stockées en JSON sur
    ``InscriptionEvenement.reponses_questions`` (portée par_commande ou
    par_inscrit)."""
    class Type(models.TextChoices):
        CHOIX = 'choix', 'Choix'
        TEXTE = 'texte', 'Texte'
        BOOLEEN = 'booleen', 'Booléen'

    class Portee(models.TextChoices):
        PAR_INSCRIT = 'par_inscrit', 'Par inscrit'
        PAR_COMMANDE = 'par_commande', 'Par commande'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='questions_evenement',
        verbose_name='Société',
    )
    evenement = models.ForeignKey(
        EvenementMarketing,
        on_delete=models.CASCADE,
        related_name='questions',
        verbose_name='Événement',
    )
    libelle = models.CharField(max_length=255, verbose_name='Libellé')
    type_question = models.CharField(
        max_length=10, choices=Type.choices, default=Type.TEXTE,
        verbose_name='Type')
    obligatoire = models.BooleanField(default=False, verbose_name='Obligatoire')
    portee = models.CharField(
        max_length=15, choices=Portee.choices, default=Portee.PAR_INSCRIT,
        verbose_name='Portée')

    class Meta:
        db_table = 'compta_questionevenement'
        verbose_name = "Question d'inscription (événement)"
        verbose_name_plural = "Questions d'inscription (événement)"
        ordering = ['id']

    def __str__(self):
        return self.libelle


# ── ZMKT17 — Communications programmées d'événement ─────────────────────────

class CommunicationEvenement(models.Model):
    """Communication programmée attachée à un événement (ZMKT17) — rappel
    avant / relance après, à échéance relative au début de l'événement.
    Envoi gated comme FG201 (no-op sans clé → file de relance manuelle
    FG31), consentement + suppression respectés (XMKT3/XMKT4).
    """
    class Canal(models.TextChoices):
        EMAIL = 'email', 'Email'
        SMS = 'sms', 'SMS'
        WHATSAPP = 'whatsapp', 'WhatsApp'

    class UniteIntervalle(models.TextChoices):
        HEURES = 'heures', 'Heures'
        JOURS = 'jours', 'Jours'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='communications_evenement',
        verbose_name='Société',
    )
    evenement = models.ForeignKey(
        EvenementMarketing,
        on_delete=models.CASCADE,
        related_name='communications',
        verbose_name='Événement',
    )
    canal = models.CharField(
        max_length=10, choices=Canal.choices, default=Canal.EMAIL,
        verbose_name='Canal')
    gabarit = models.TextField(blank=True, default='', verbose_name='Corps')
    # Intervalle SIGNÉ relatif au début de l'événement (ex. -2 j confirmation,
    # -2 h rappel, +1 j remerciement).
    intervalle = models.IntegerField(verbose_name='Intervalle (signé)')
    unite_intervalle = models.CharField(
        max_length=10, choices=UniteIntervalle.choices,
        default=UniteIntervalle.JOURS, verbose_name='Unité')
    envoyee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Envoyée le')

    class Meta:
        db_table = 'compta_communicationevenement'
        verbose_name = "Communication d'événement"
        verbose_name_plural = "Communications d'événement"
        ordering = ['intervalle']

    def __str__(self):
        signe = '+' if self.intervalle >= 0 else ''
        return f'{self.evenement_id} ({signe}{self.intervalle} {self.unite_intervalle})'

    def echeance(self):
        import datetime
        delta = datetime.timedelta(**{
            'hours' if self.unite_intervalle == self.UniteIntervalle.HEURES
            else 'days': self.intervalle})
        return self.evenement.date_debut + delta


class InscriptionEvenement(models.Model):
    """Inscription à un ``EvenementMarketing`` (XMKT28) — nom/email/téléphone
    normalisé, statut de présence + check-in sur place (option QR token par
    inscrit). Chaque inscrit devient un lead via ``crm.services``
    (dédupliqué), jamais de doublon."""
    class Statut(models.TextChoices):
        INSCRIT = 'inscrit', 'Inscrit'
        CONFIRME = 'confirme', 'Confirmé'
        PRESENT = 'present', 'Présent'
        ABSENT = 'absent', 'Absent'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='inscriptions_evenement',
        verbose_name='Société',
    )
    evenement = models.ForeignKey(
        EvenementMarketing,
        on_delete=models.CASCADE,
        related_name='inscriptions',
        verbose_name='Événement',
    )
    nom = models.CharField(max_length=200, verbose_name='Nom')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    telephone = models.CharField(
        max_length=32, blank=True, default='',
        verbose_name='Téléphone (normalisé)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.INSCRIT,
        verbose_name='Statut')
    qr_token = models.CharField(
        max_length=64, blank=True, default='', unique=True, null=True,
        verbose_name='Jeton QR de check-in')
    lead_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='Lead créé (id crm)')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Inscrit le')
    date_pointage = models.DateTimeField(
        null=True, blank=True, verbose_name='Pointé (check-in) le')
    # ── ZMKT15 — billet optionnel (descripteur capacité/tarif) ──────────────
    billet = models.ForeignKey(
        'marketing.BilletEvenement',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='inscriptions',
        verbose_name='Billet',
    )
    # ── ZMKT16 — réponses aux questions d'inscription (JSON) ────────────────
    reponses_questions = models.JSONField(
        default=dict, blank=True,
        verbose_name="Réponses aux questions d'inscription (JSON)")

    class Meta:
        db_table = 'compta_inscriptionevenement'
        verbose_name = 'Inscription à un événement'
        verbose_name_plural = 'Inscriptions à un événement'
        ordering = ['-date_creation']

    def __str__(self):
        return f'{self.nom} → {self.evenement_id} ({self.statut})'


# ── XMKT29 — Ponts QR pour supports offline (flyers, bâches, véhicules) ────

class SupportOffline(models.Model):
    """Support offline (flyer, bâche, véhicule) avec QR de scan (XMKT29).

    ``url_cible`` = landing/FormulaireIntake auto-taguée
    utm_source=offline&utm_campaign=<nom>. Le QR encode une redirection
    tokenisée (réutilise ``LienTrackee`` XMKT9) → compte les scans ET
    attribue les leads issus de l'impression papier au support précis.
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='supports_offline',
        verbose_name='Société',
    )
    nom = models.CharField(
        max_length=200, verbose_name='Nom (ex. « Flyer SIAM 2026 »)')
    url_cible = models.URLField(max_length=1000, verbose_name='URL cible')
    lien_tracke = models.ForeignKey(
        'marketing.LienTrackee',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='supports_offline',
        verbose_name='Lien tracké (QR)',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        db_table = 'compta_supportoffline'
        verbose_name = 'Support offline'
        verbose_name_plural = 'Supports offline'
        ordering = ['-date_creation']

    def __str__(self):
        return self.nom


# ── XMKT33 — Assistant d'authentification du domaine d'envoi (SPF/DKIM/DMARC)

class DomaineEnvoi(models.Model):
    """Domaine d'envoi marketing + statut de vérification DNS (XMKT33).

    Vérification par lookup DNS (dnspython, dépendance libre) — jamais
    d'appel réseau en test (mocké). Statut par enregistrement stocké pour
    affichage + pour le pré-check XMKT13 (avertissement domaine non
    authentifié).
    """
    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='domaines_envoi',
        verbose_name='Société',
    )
    domaine = models.CharField(max_length=255, verbose_name='Domaine')
    spf_verifie = models.BooleanField(default=False, verbose_name='SPF vérifié')
    dkim_verifie = models.BooleanField(default=False, verbose_name='DKIM vérifié')
    dmarc_verifie = models.BooleanField(default=False, verbose_name='DMARC vérifié')
    derniere_verification_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Dernière vérification le')

    class Meta:
        db_table = 'compta_domaineenvoi'
        verbose_name = "Domaine d'envoi"
        verbose_name_plural = "Domaines d'envoi"
        ordering = ['domaine']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'domaine'],
                name='uniq_domaine_envoi_par_societe',
            ),
        ]

    def __str__(self):
        return self.domaine

    @property
    def authentifie(self):
        return self.spf_verifie and self.dkim_verifie and self.dmarc_verifie


# ── XMKT35 — Planification de posts réseaux sociaux (publication gated) ─────

class PostSocial(models.Model):
    """Post réseau social planifié (XMKT35) — calendrier de contenu XMKT30.

    La PUBLICATION réelle via l'API Meta Graph est gated (défaut OFF,
    ``compta.services.meta_graph_actif``) : sans jeton, le post devient à
    l'échéance un RAPPEL manuel notifié à son auteur avec le texte prêt à
    coller (aucun appel réseau, aucun statut ``publie`` posé tout seul).
    ``media_key`` = clé d'objet MinIO opaque (bucket uploads existant, posée
    par le flux d'upload standard) — jamais un chemin local. Multi-société.
    """
    class Reseau(models.TextChoices):
        FACEBOOK = 'facebook', 'Facebook'
        INSTAGRAM = 'instagram', 'Instagram'
        LINKEDIN = 'linkedin', 'LinkedIn'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        PLANIFIE = 'planifie', 'Planifié'
        PUBLIE = 'publie', 'Publié'
        ECHEC = 'echec', 'Échec'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='posts_sociaux',
        verbose_name='Société',
    )
    reseau = models.CharField(
        max_length=12, choices=Reseau.choices, default=Reseau.FACEBOOK,
        verbose_name='Réseau')
    texte = models.TextField(blank=True, default='', verbose_name='Texte du post')
    # Clé d'objet MinIO du média joint (image/vidéo) — opaque, optionnelle.
    media_key = models.CharField(
        max_length=512, blank=True, default='', verbose_name='Média (clé MinIO)')
    date_planifiee = models.DateTimeField(
        null=True, blank=True, verbose_name='Publication planifiée le')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    # Rappel manuel (chemin sans jeton) : envoyé UNE fois à l'échéance.
    rappel_envoye = models.BooleanField(
        default=False, verbose_name='Rappel manuel envoyé')
    publie_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Publié le')
    # ID du post renvoyé par l'API Meta Graph (chemin gated uniquement).
    external_id = models.CharField(
        max_length=255, blank=True, default='', verbose_name='ID externe Meta')
    erreur = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Erreur (échec)')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Créé par')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Post réseau social'
        verbose_name_plural = 'Posts réseaux sociaux'
        ordering = ['-date_planifiee', '-id']
        indexes = [
            models.Index(
                fields=['company', 'statut', 'date_planifiee'],
                name='mkt_postsocial_co_st_date_idx'),
        ]

    def __str__(self):
        return f'{self.get_reseau_display()} — {self.texte[:40]} ({self.statut})'
