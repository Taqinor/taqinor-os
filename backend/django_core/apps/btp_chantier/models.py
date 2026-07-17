"""Modèles du vertical BTP/EPC (Groupe NTCON) — situations, RFI, visas,
réserves de chantier géo-localisées, journal de chantier, avenants, DGD.

Frontières cross-app (CLAUDE.md) : le ``chantier`` référence
``installations.Installation`` par FK RÉELLE (chaîne ``'installations.
Installation'``, aucun import statique de ``installations.models`` — pattern
déjà utilisé par ``sav.models``/``achats.models``). Tout autre objet d'une
AUTRE app (document GED, ordre de sous-traitance, avenant contractuel,
retenue de garantie, situation de travaux) est référencé par un ID lâche
(``PositiveIntegerField``/``JSONField``) — jamais un FK dur, jamais un import
de modèle.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

from core.models import TenantModel


# ── NTCON1 — ReserveChantier (punch-list géo-localisée sur plan) ───────────

class ReserveChantier(TenantModel):
    """Une réserve (punch-list) posée sur un plan (document GED) d'un chantier.

    Distincte de XFSM18 (``installations``) qui part d'une réserve EXISTANTE
    d'``installations`` pour générer un devis : NTCON1 EST la création/gestion
    de la réserve elle-même, avec un pin normalisé (x, y ∈ [0, 1]) sur un
    document GED (image/PDF du plan) — ``localisation_plan`` porte
    ``document_ged_id`` (référence lâche vers ``ged.Document``) + les
    coordonnées du pin.

    Les photos avant/après de levée passent par ``records.Attachment``
    (déclaré dans ``platform.py`` → ``record_targets``), jamais un champ fichier
    local. Multi-tenant : ``company`` posée côté serveur, jamais lue du corps
    de requête.
    """

    class Gravite(models.TextChoices):
        MINEURE = 'mineure', 'Mineure'
        MAJEURE = 'majeure', 'Majeure'
        BLOQUANTE = 'bloquante', 'Bloquante'

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        EN_COURS = 'en_cours', 'En cours'
        LEVEE = 'levee', 'Levée'
        CONTESTEE = 'contestee', 'Contestée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='btp_reserves_chantier', verbose_name='Société')
    # FK réelle (chaîne, aucun import statique) — pattern sav.models/achats.models.
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='btp_reserves', verbose_name='Chantier')
    lot = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='Lot (gros-œuvre, électricité, plomberie…)')
    # Pin sur plan : {'document_ged_id': int, 'x': float 0-1, 'y': float 0-1}.
    localisation_plan = models.JSONField(
        default=dict, blank=True, verbose_name='Localisation sur le plan')
    description = models.TextField(verbose_name='Description')
    gravite = models.CharField(
        max_length=10, choices=Gravite.choices, default=Gravite.MINEURE,
        verbose_name='Gravité')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERTE,
        verbose_name='Statut')
    responsable_leve = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_reserves_a_lever',
        verbose_name='Responsable de la levée')
    date_limite = models.DateField(
        null=True, blank=True, verbose_name='Date limite')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_reserves_creees',
        verbose_name='Créée par')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Modifiée le')

    # ── NTCON2 — preuve de levée / contestation ─────────────────────────────
    date_levee = models.DateTimeField(
        null=True, blank=True, verbose_name='Levée le')
    leve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_reserves_levees',
        verbose_name='Levée par')
    motif_contestation = models.TextField(
        blank=True, default='', verbose_name='Motif de contestation')

    class Meta:
        verbose_name = 'Réserve de chantier'
        verbose_name_plural = 'Réserves de chantier'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'chantier', 'statut']),
            models.Index(fields=['company', 'lot']),
        ]

    def __str__(self):
        return f'Réserve #{self.pk} — {self.get_gravite_display()}'


class ReserveChantierHistorique(TenantModel):
    """NTCON2 — historique des transitions de statut d'une ``ReserveChantier``.

    Trace minimale (ancien → nouveau statut, auteur+date serveur, motif
    optionnel) — un journal local à l'app, distinct du chatter transverse
    (``NTCON32``, hors périmètre de ce lot). Toujours écrit par le service,
    jamais par la vue directement.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='btp_reserve_historiques', verbose_name='Société')
    reserve = models.ForeignKey(
        ReserveChantier, on_delete=models.CASCADE,
        related_name='historique', verbose_name='Réserve')
    ancien_statut = models.CharField(max_length=10, blank=True, default='')
    nouveau_statut = models.CharField(max_length=10)
    motif = models.TextField(blank=True, default='')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_reserve_transitions')
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Historique de réserve'
        verbose_name_plural = 'Historiques de réserve'
        ordering = ['-date_creation', '-id']

    def __str__(self):
        return f'{self.reserve_id}: {self.ancien_statut} → {self.nouveau_statut}'


class SignatureBtp(TenantModel):
    """NTCON2/NTCON8 — point de capture de signature électronique IN-APP.

    Réplique le PATTERN de ``contrats.SignatureContrat`` (loi 53-05 : un nom
    dactylographié consenti vaut signature électronique) SANS importer
    ``contrats.models`` — modèle propre à ``btp_chantier``, réutilisé pour la
    levée de réserve (NTCON2, signataire interne) ET l'approbation client d'un
    avenant (NTCON8, signataire externe potentiellement sans compte ERP).
    Cible générique via ``contenttypes`` (comme ``records.Attachment``).
    """

    class Methode(models.TextChoices):
        TYPED = 'typed', 'Nom dactylographié'
        DRAW = 'draw', 'Signature dessinée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='btp_signatures', verbose_name='Société')
    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    contexte = models.CharField(
        max_length=40, blank=True, default='',
        verbose_name='Contexte (levee_reserve, approbation_avenant…)')
    signataire_nom = models.CharField(
        max_length=255, verbose_name='Nom du signataire')
    signataire = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_signatures',
        verbose_name='Utilisateur signataire')
    methode = models.CharField(
        max_length=20, choices=Methode.choices, default=Methode.TYPED)
    date_signature = models.DateTimeField(auto_now_add=True)
    ip_adresse = models.CharField(max_length=45, blank=True, default='')
    user_agent = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Signature BTP'
        verbose_name_plural = 'Signatures BTP'
        ordering = ['-date_signature', '-id']

    def __str__(self):
        return f'{self.contexte}: {self.signataire_nom}'


# ── NTCON3 — RFI (Request For Information) ──────────────────────────────────

class RFI(TenantModel):
    """Question technique posée au MOE/BE, avec délai de réponse (NTCON3).

    ``numero`` est INCRÉMENTAL PAR CHANTIER (jamais ``count()+1`` — pattern
    ``gestion_projet.services.prochain_numero_situation`` : verrou de ligne
    sur le ``chantier`` + plus-haut-utilisé+1, dans une transaction atomique ;
    ``core.numbering`` ne convient pas ici car il scope par SOCIÉTÉ+période,
    pas par chantier). ``date_limite_reponse`` est calculée à la création
    depuis ``delai_jours`` (jours OUVRÉS, ``apps.notifications.calendar_utils.
    ajouter_jours_ouvres`` — férié-aware).
    """

    class Statut(models.TextChoices):
        OUVERT = 'ouvert', 'Ouvert'
        REPONDU = 'repondu', 'Répondu'
        CLOS = 'clos', 'Clos'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='btp_rfis', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='btp_rfis', verbose_name='Chantier')
    numero = models.PositiveIntegerField(verbose_name='N° de RFI')
    question = models.TextField(verbose_name='Question')
    pose_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_rfis_poses',
        verbose_name='Posé par')
    destinataire_texte = models.CharField(
        max_length=255, blank=True, default='',
        verbose_name='Destinataire (texte libre — MOE/BE)')
    destinataire_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_rfis_destinataire',
        verbose_name='Destinataire (utilisateur)')
    delai_jours = models.PositiveIntegerField(
        default=5, verbose_name='Délai de réponse (jours ouvrés)')
    date_limite_reponse = models.DateField(
        null=True, blank=True, verbose_name='Date limite de réponse')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERT,
        verbose_name='Statut')
    impact_cout = models.BooleanField(
        default=False, verbose_name='Impact coût')
    impact_delai_jours = models.IntegerField(
        null=True, blank=True, verbose_name='Impact délai (jours)')
    # NTCON4 — une seule alerte de retard par jour (idempotence du sweep).
    derniere_alerte_retard = models.DateField(
        null=True, blank=True, verbose_name='Dernière alerte de retard')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'RFI'
        verbose_name_plural = 'RFI'
        ordering = ['date_limite_reponse', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['chantier', 'numero'], name='btp_rfi_chantier_numero_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'chantier', 'statut']),
        ]

    def __str__(self):
        return f'RFI #{self.numero} — chantier {self.chantier_id}'


class RFIReponse(TenantModel):
    """Réponse à un ``RFI`` (NTCON3). Pièces jointes via ``records.
    Attachment`` (déclaré dans ``platform.py``)."""
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='btp_rfi_reponses', verbose_name='Société')
    rfi = models.ForeignKey(
        RFI, on_delete=models.CASCADE, related_name='reponses',
        verbose_name='RFI')
    texte = models.TextField(verbose_name='Réponse')
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_rfi_reponses',
        verbose_name='Auteur')
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Réponse RFI'
        verbose_name_plural = 'Réponses RFI'
        ordering = ['-date_creation', '-id']

    def __str__(self):
        return f'Réponse à RFI #{self.rfi_id}'


# ── NTCON5 — Visas de documents techniques ──────────────────────────────────

class VisaDocument(TenantModel):
    """Cycle soumission → observations → approbation d'un document technique
    (plan d'exécution, note de calcul, fiche technique, méthode…) — NTCON5.

    ``reference`` est posée via ``core.numbering`` (race-safe par société+
    période, préfixe ``VIS``). Le document GED est référencé LÂCHEMENT
    (``document_ged_id``, aucun FK dur) : une nouvelle ``ged.DocumentVersion``
    sur ce document RÉ-OUVRE automatiquement le visa (statut → ``soumis``,
    ``nb_resoumissions`` incrémenté) via ``receivers.py`` (signal ``post_save``
    connecté PARESSEUSEMENT — aucun import statique de ``ged.models``).
    """

    class TypeVisa(models.TextChoices):
        PLAN_EXECUTION = 'plan_execution', "Plan d'exécution"
        NOTE_CALCUL = 'note_calcul', 'Note de calcul'
        FICHE_TECHNIQUE = 'fiche_technique', 'Fiche technique'
        METHODE = 'methode', 'Méthode'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        SOUMIS = 'soumis', 'Soumis'
        EN_REVUE = 'en_revue', 'En revue'
        APPROUVE_SANS_RESERVE = (
            'approuve_sans_reserve', 'Approuvé sans réserve')
        APPROUVE_AVEC_OBSERVATIONS = (
            'approuve_avec_observations', 'Approuvé avec observations')
        REFUSE = 'refuse', 'Refusé'

    # Statuts « décidés » — une nouvelle version GED en repart toujours.
    STATUTS_DECIDES = (
        Statut.APPROUVE_SANS_RESERVE, Statut.APPROUVE_AVEC_OBSERVATIONS,
        Statut.REFUSE,
    )

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='btp_visas', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='btp_visas', verbose_name='Chantier')
    document_ged_id = models.PositiveIntegerField(
        verbose_name='ID du document GED')
    reference = models.CharField(max_length=50, verbose_name='Référence')
    type_visa = models.CharField(
        max_length=20, choices=TypeVisa.choices,
        default=TypeVisa.AUTRE, verbose_name='Type de visa')
    statut = models.CharField(
        max_length=30, choices=Statut.choices, default=Statut.SOUMIS,
        verbose_name='Statut')
    soumis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_visas_soumis',
        verbose_name='Soumis par')
    date_soumission = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de soumission')
    revu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_visas_revus',
        verbose_name='Revu par')
    date_revue = models.DateTimeField(
        null=True, blank=True, verbose_name='Date de revue')
    observations = models.TextField(
        blank=True, default='', verbose_name='Observations')
    delai_revue_jours = models.PositiveIntegerField(
        default=10, verbose_name='Délai de revue (jours ouvrés)')
    date_limite = models.DateField(
        null=True, blank=True, verbose_name='Date limite de revue')
    nb_resoumissions = models.PositiveIntegerField(
        default=0, verbose_name='Nombre de resoumissions')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Visa de document'
        verbose_name_plural = 'Visas de document'
        ordering = ['date_limite', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='btp_visa_company_reference_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'chantier', 'statut']),
            models.Index(fields=['company', 'document_ged_id']),
        ]

    def __str__(self):
        return f'Visa {self.reference} ({self.get_statut_display()})'


# ── NTCON6 — Journal de chantier quotidien ──────────────────────────────────

class JournalChantier(TenantModel):
    """Entrée quotidienne du journal de chantier (NTCON6) — une par jour par
    chantier (contrainte unique). Photos via ``records.Attachment``
    (déclaré dans ``platform.py``)."""

    class Meteo(models.TextChoices):
        ENSOLEILLE = 'ensoleille', 'Ensoleillé'
        NUAGEUX = 'nuageux', 'Nuageux'
        PLUVIEUX = 'pluvieux', 'Pluvieux'
        VENTEUX = 'venteux', 'Venteux'
        AUTRE = 'autre', 'Autre'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        related_name='btp_journaux_chantier', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        related_name='btp_journaux', verbose_name='Chantier')
    date = models.DateField(verbose_name='Date')
    redacteur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_journaux_rediges',
        verbose_name='Rédacteur')
    meteo = models.CharField(
        max_length=15, choices=Meteo.choices, blank=True, default='',
        verbose_name='Météo')
    # Métier → nombre, ex. {'macon': 4, 'electricien': 2}.
    effectif_interne = models.JSONField(
        default=dict, blank=True, verbose_name='Effectif interne')
    # OrdreSousTraitance loose-FK (id, texte) → nombre — réutilise FG304/305.
    effectif_sous_traitant = models.JSONField(
        default=dict, blank=True, verbose_name='Effectif sous-traitant')
    materiel_present = models.TextField(
        blank=True, default='', verbose_name='Matériel présent')
    evenements = models.TextField(
        blank=True, default='', verbose_name='Événements')
    # Liste de {'nom', 'societe', 'motif'}.
    visiteurs = models.JSONField(
        default=list, blank=True, verbose_name='Visiteurs')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Créée le')

    class Meta:
        verbose_name = 'Journal de chantier'
        verbose_name_plural = 'Journaux de chantier'
        ordering = ['-date', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['chantier', 'date'],
                name='btp_journal_chantier_date_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'chantier', 'date']),
        ]

    def __str__(self):
        return f'Journal {self.chantier_id} — {self.date}'
