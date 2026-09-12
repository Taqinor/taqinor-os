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
import secrets

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

from core.models import TenantModel


def _default_btp_token():
    """Jeton public long/imprévisible (NTCON8/NTCON12) — réplique le motif
    ``ged.PartageGed``/``ventes.ShareLink`` (``secrets.token_urlsafe``, 32
    octets) SANS importer ces apps : ``btp_chantier`` génère son propre jeton
    local, résolu par lookup (jamais un JWT/token signé)."""
    return secrets.token_urlsafe(32)


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
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_reserves_chantier', verbose_name='Société')
    # FK réelle (chaîne, aucun import statique) — pattern sav.models/achats.models.
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
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

    # ── NTCON27 — archivage des réserves levées anciennes ───────────────────
    # JAMAIS une suppression physique : la réserve levée porte une signature
    # (``SignatureBtp``) et un historique de transitions qui sont des PREUVES
    # de réception. On pose un drapeau, cohérent avec la politique
    # soft-delete du dépôt (``core.SoftDeleteQuerySet``).
    archivee = models.BooleanField(
        default=False, verbose_name='Archivée')
    archivee_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Archivée le')

    class Meta:
        verbose_name = 'Réserve de chantier'
        verbose_name_plural = 'Réserves de chantier'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'chantier', 'statut']),
            models.Index(fields=['company', 'lot']),
            # NTCON27 — PAS d'index dédié sur ``archivee`` : le filtre par
            # défaut est toujours combiné à ``company`` (+ ``statut``), déjà
            # couvert ci-dessus, et un AddIndex sur une table PEUPLÉE prend un
            # verrou d'écriture bloquant (garde `check_safe_migrations`
            # YOPSB6) pour un gain nul sur un booléen à deux valeurs.
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
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_reserve_historiques', verbose_name='Société')
    reserve = models.ForeignKey(
        ReserveChantier, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
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
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_signatures', verbose_name='Société')
    content_type = models.ForeignKey(
        'contenttypes.ContentType', on_delete=models.CASCADE)
    # on_delete: cascade parent→enfant (composant du parent)
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
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_rfis', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
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
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_rfi_reponses', verbose_name='Société')
    rfi = models.ForeignKey(
        RFI, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='reponses',
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
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_visas', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
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
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_journaux_chantier', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
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


# ── NTCON7/NTCON8 — Avenant marché côté projet (chiffrage + approbation) ───

class AvenantChantier(TenantModel):
    """Chiffrage/impact opérationnel d'un avenant marché (NTCON7), avec
    approbation CLIENT par lien public tokenisé + signature typée (NTCON8).

    Distinct de ``contrats.Avenant`` (CONTRAT24, l'amendement CONTRACTUEL —
    nouvelle version de contrat) : ``avenant_contrat_id`` le référence
    LÂCHEMENT (optionnel). ``reference`` est posée via ``core.numbering``
    (préfixe ``AVC``). ``impact_budget`` est le CHOIX fait à la création
    (spec NTCON7) qui détermine, à l'approbation :

    * ``impact_budget=False`` (défaut) → génère une ``ventes.Facture``
      d'acompte via la fonction cross-app SANCTIONNÉE
      ``apps.ventes.services.creer_facture_acompte_situation`` (jamais un
      import de ``ventes.models`` — appel FONCTION-LOCAL) ; ``facture_id``
      référence LÂCHEMENT la facture créée.
    * ``impact_budget=True`` → résout (best-effort, LECTURE SEULE, jamais
      d'écriture cross-app) le ``BudgetProjet`` actif du projet auquel ce
      chantier est rattaché (``gestion_projet.ProjetChantier`` → ``apps.
      gestion_projet.selectors.budget_effectif`` — aucune fonction de
      SERVICE n'existe aujourd'hui côté ``gestion_projet`` pour MUTER un
      budget depuis une autre app ; conformément à la frontière cross-app
      [CLAUDE.md : lecture via ``selectors.py``, écriture via
      ``services.py`` OU référence lâche], l'« impact » se traduit par une
      référence lâche ``budget_projet_id`` posée ici — le montant de
      l'avenant approuvé est ensuite AGRÉGÉ par les sélecteurs de CE module
      (NTCON9 ``calculer_dgd``, NTCON11 ``debourse_sec_vs_facture``), jamais
      par une mutation directe des lignes de ``gestion_projet.BudgetProjet``.

    Un avenant REFUSÉ n'impacte jamais rien (ni facture, ni référence
    budget) — state machine stricte (``services.TransitionInvalide``).
    """

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        SOUMIS_CLIENT = 'soumis_client', 'Soumis au client'
        APPROUVE = 'approuve', 'Approuvé'
        REFUSE = 'refuse', 'Refusé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_avenants_chantier', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='btp_avenants', verbose_name='Chantier')
    avenant_contrat_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="ID de l'avenant contractuel (contrats.Avenant)")
    reference = models.CharField(max_length=50, verbose_name='Référence')
    description = models.TextField(verbose_name='Description')
    montant_ht = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name='Montant HT')
    impact_delai_jours = models.IntegerField(
        null=True, blank=True, verbose_name='Impact délai (jours)')
    impact_budget = models.BooleanField(
        default=False,
        verbose_name='Impact budget projet (sinon facture acompte)')
    # Lignes simples matériel/MO/sous-traitance : [{type, libelle, montant}].
    lignes = models.JSONField(
        default=list, blank=True, verbose_name='Lignes')
    statut = models.CharField(
        max_length=15, choices=Statut.choices, default=Statut.BROUILLON,
        verbose_name='Statut')
    # NTCON8 — lien public tokenisé (approbation client sans compte ERP).
    token = models.CharField(
        max_length=64, unique=True, default=_default_btp_token,
        editable=False)
    token_expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Lien expire le')
    # NTCON7 — traces d'impact posées À L'APPROBATION UNIQUEMENT.
    budget_projet_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID du budget projet impacté (gestion_projet.BudgetProjet)')
    facture_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="ID de la facture d'acompte générée (ventes.Facture)")
    motif_refus = models.TextField(
        blank=True, default='', verbose_name='Motif de refus')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_avenants_crees',
        verbose_name='Créé par')
    approuve_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_avenants_approuves',
        # Nullable : un signataire CLIENT externe (NTCON8) n'a pas de compte ERP.
        verbose_name='Approuvé par')
    date_approbation = models.DateTimeField(
        null=True, blank=True, verbose_name='Approuvé le')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Avenant de chantier'
        verbose_name_plural = 'Avenants de chantier'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='btp_avenant_company_reference_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'chantier', 'statut']),
        ]

    def __str__(self):
        return f'Avenant {self.reference} ({self.get_statut_display()})'


# ── NTCON9/NTCON10 — DGD (Décompte Général et Définitif) ───────────────────

class DecompteGeneral(TenantModel):
    """Décompte Général et Définitif d'un chantier (NTCON9), avec
    contestation/finalisation verrouillante (NTCON10).

    Les totaux (``total_avenants_ht``, ``total_situations_facturees_ht``,
    ``solde_du_ht``) sont RECALCULÉS À LA DEMANDE par le sélecteur
    ``selectors.calculer_dgd`` (jamais stockés en dur sans recalcul) — les
    champs ici ne portent que le DERNIER instantané calculé (utile à
    l'affichage/PDF sans recalcul systématique). ``situations_incluses``
    référence LÂCHEMENT une liste d'IDs ``gestion_projet.SituationTravaux``.
    ``retenue_garantie_id`` référence LÂCHEMENT une ``compta.RetenueGarantie``
    (FG145) — le SUIVI de sa libération reste dans ``compta``, jamais réécrit
    ici.

    ``statut=definitif`` VERROUILLE le décompte (pattern ``compta.
    PeriodeComptable.verrouillee`` — toute écriture ultérieure est refusée en
    403, sauf déverrouillage admin JOURNALISÉ dans
    ``historique_deverrouillage``).
    """

    class Statut(models.TextChoices):
        PROJET = 'projet', 'Projet'
        NOTIFIE = 'notifie', 'Notifié'
        ACCEPTE = 'accepte', 'Accepté'
        CONTESTE = 'conteste', 'Contesté'
        DEFINITIF = 'definitif', 'Définitif'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_decomptes_generaux', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='btp_decomptes', verbose_name='Chantier')
    reference = models.CharField(max_length=50, verbose_name='Référence')
    montant_marche_initial_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Montant marché initial HT')
    situations_incluses = models.JSONField(
        default=list, blank=True,
        verbose_name='Situations incluses (IDs gestion_projet.SituationTravaux)')
    total_avenants_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Total avenants approuvés HT')
    total_situations_facturees_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Total situations facturées HT')
    retenue_garantie_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID de la retenue de garantie (compta.RetenueGarantie)')
    retenue_garantie_montant = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant de retenue de garantie libérée (instantané)')
    solde_du_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0, verbose_name='Solde dû HT')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.PROJET,
        verbose_name='Statut')
    motif_contestation = models.TextField(
        blank=True, default='', verbose_name='Motif de contestation')
    montant_conteste = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        verbose_name='Montant contesté')
    date_notification = models.DateTimeField(
        null=True, blank=True, verbose_name='Notifié le')
    date_finalisation = models.DateTimeField(
        null=True, blank=True, verbose_name='Finalisé le')
    finalise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_decomptes_finalises',
        verbose_name='Finalisé par')
    # NTCON10 — déverrouillage admin JOURNALISÉ : [{date, user_id, motif}].
    historique_deverrouillage = models.JSONField(
        default=list, blank=True, verbose_name='Historique de déverrouillage')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_decomptes_crees',
        verbose_name='Créé par')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name='Modifié le')

    class Meta:
        verbose_name = 'Décompte général et définitif'
        verbose_name_plural = 'Décomptes généraux et définitifs'
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'reference'],
                name='btp_dgd_company_reference_uniq'),
        ]
        indexes = [
            models.Index(fields=['company', 'chantier', 'statut']),
        ]

    def __str__(self):
        return f'DGD {self.reference} ({self.get_statut_display()})'


# ── NTCON12/NTCON13 — Diffusion contrôlée de plans ──────────────────────────

class DiffusionPlan(TenantModel):
    """Diffusion tracée d'une version d'un plan (document GED) à des
    destinataires internes/externes, avec accusé de réception (NTCON12) et
    détection de plan périmé consulté (NTCON13 — ``selectors.
    plans_perimes_sur_chantier``).

    Réutilise ``ged.PartageGed`` (GED20, via ``apps.ged.services.
    create_partage`` — fonction cross-app SANCTIONNÉE, jamais un import de
    ``ged.models``) pour le lien externe tokenisé plutôt que d'inventer un
    2e mécanisme de partage ; ``partage_ged_id`` référence LÂCHEMENT le
    ``PartageGed`` créé. ``token`` (propre à CE module) sert au lien
    d'ACCUSÉ DE RÉCEPTION interne (``accuse_reception``, JSON
    ``{cle_destinataire: {'lu': bool, 'horodatage': iso}}``) — distinct du
    jeton de téléchargement GED.
    """

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_diffusions_plan', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='btp_diffusions', verbose_name='Chantier')
    document_ged_id = models.PositiveIntegerField(
        verbose_name='ID du document GED')
    version_diffusee = models.PositiveIntegerField(
        verbose_name='Version diffusée (ged.DocumentVersion.version)')
    destinataires_internes = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True,
        related_name='btp_diffusions_recues',
        verbose_name='Destinataires internes')
    destinataires_externes = models.JSONField(
        default=list, blank=True,
        verbose_name='Destinataires externes (emails)')
    token = models.CharField(
        max_length=64, unique=True, default=_default_btp_token,
        editable=False)
    partage_ged_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID du partage GED externe (ged.PartageGed)')
    date_diffusion = models.DateTimeField(
        null=True, blank=True, verbose_name='Diffusé le')
    accuse_reception = models.JSONField(
        default=dict, blank=True, verbose_name='Accusé de réception')
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_diffusions_creees',
        verbose_name='Créé par')
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Diffusion de plan'
        verbose_name_plural = 'Diffusions de plan'
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['company', 'chantier', 'document_ged_id']),
        ]

    def __str__(self):
        return f'Diffusion {self.document_ged_id} v{self.version_diffusee} — chantier {self.chantier_id}'


# ── NTCON14 — Planning TCE multi-lots avec jalons contractuels ──────────────

class Lot(TenantModel):
    """Un LOT du planning tous-corps-d'état d'un chantier (gros-œuvre,
    électricité, plomberie, CVC, finitions…) — NTCON14.

    FRONTIÈRE CROSS-APP (CLAUDE.md, contrat de propriété PLAN_VERTICALS).
    Le texte de NTCON14 situait ce modèle dans ``gestion_projet`` (app
    EXISTANTE) et voulait un FK ``lot`` posé sur ``gestion_projet.Tache``.
    Les deux écritures sont INTERDITES à ce module : une app verticale ne
    touche NI les ``models``/``views`` NI la chaîne de migrations d'une autre
    app. ``Lot`` vit donc ICI (même app que le reste du vertical BTP, même FK
    RÉELLE par chaîne vers ``installations.Installation`` que ``ReserveChantier``
    /``RFI``/``JournalChantier``), et le rattachement des tâches existantes
    passe par la table de liaison ``LotTache`` déclarée dans CETTE app
    (M2M ``through``) — strictement additif, zéro migration chez
    ``gestion_projet``, et fonctionnellement équivalent au FK souhaité
    (une tâche appartient à au plus un lot : contrainte d'unicité sur
    ``tache``).

    ``entreprise`` = ``sous_traitant`` (FK CHAÎNE vers ``stock.Fournisseur``,
    le référentiel UNIFIÉ des sous-traitants depuis DC34 — FG304 n'a plus de
    table parallèle) OU ``interne=True`` (exécution en régie). Le couple est
    validé côté sérialiseur (message français nommant le champ fautif).

    ``taux_penalite_retard_pmil`` (‰/jour) + ``plafond_penalite_pct`` reprennent
    le pattern XPRJ27 (``gestion_projet.selectors.penalites_retard``) mais PAR
    LOT : un lot en retard n'expose que SA propre pénalité (NTCON15).
    Donnée INTERNE — jamais dans une sortie client.
    """

    class Statut(models.TextChoices):
        PLANIFIE = 'planifie', 'Planifié'
        EN_COURS = 'en_cours', 'En cours'
        TERMINE = 'termine', 'Terminé'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_lots', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='btp_lots', verbose_name='Chantier')
    nom = models.CharField(
        max_length=120,
        verbose_name='Nom du lot (gros-œuvre, électricité, plomberie…)')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    # Code couleur du Gantt groupé par lot (hex, #RRGGBB).
    couleur = models.CharField(
        max_length=7, blank=True, default='',
        verbose_name='Couleur du lot (Gantt)')
    interne = models.BooleanField(
        default=True, verbose_name='Exécuté en interne (régie)')
    # FK CHAÎNE — jamais un import de ``apps.stock.models`` (contrat M1).
    sous_traitant = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.SET_NULL,
        # on_delete: SET_NULL — retirer un sous-traitant ne détruit pas le lot.
        null=True, blank=True, related_name='btp_lots',
        verbose_name='Entreprise (sous-traitant)')
    date_debut_prevue = models.DateField(
        null=True, blank=True, verbose_name='Début prévu')
    date_fin_prevue = models.DateField(
        null=True, blank=True, verbose_name='Fin prévue')
    date_fin_reelle = models.DateField(
        null=True, blank=True, verbose_name='Fin réelle')
    jalon_contractuel = models.BooleanField(
        default=False, verbose_name='Jalon contractuel')
    montant_ht = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name='Montant du lot HT')
    taux_penalite_retard_pmil = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        verbose_name='Taux de pénalité de retard (‰/jour)')
    plafond_penalite_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Plafond de pénalité (% du montant du lot)')
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.PLANIFIE,
        verbose_name='Statut')
    # Rattachement des ``gestion_projet.Tache`` EXISTANTES — table de liaison
    # locale (``LotTache``), aucune migration chez ``gestion_projet``.
    taches = models.ManyToManyField(
        'gestion_projet.Tache', through='LotTache', blank=True,
        related_name='btp_lots', verbose_name='Tâches rattachées')

    # ── NTCON28 — cache dénormalisé de l'exposition aux pénalités ───────────
    # Le cockpit (NTCON21) affichait la pénalité de CHAQUE lot en relançant le
    # calcul NTCON15 à chaque GET. Le balayage quotidien
    # (``recalculer_penalites_lots``) fige ici le résultat + son horodatage,
    # pour que l'écran LISE au lieu de RECALCULER. Le cache ne remplace jamais
    # le calcul : il en est une photo datée, et le décompte DÉFINITIF reste à
    # établir à la réception du lot.
    penalite_calculee_cache = models.JSONField(
        null=True, blank=True,
        verbose_name='Exposition aux pénalités (cache)')
    penalite_calculee_le = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Exposition aux pénalités calculée le')

    class Meta:
        verbose_name = 'Lot de chantier'
        verbose_name_plural = 'Lots de chantier'
        ordering = ['ordre', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['chantier', 'nom'], name='btp_lot_chantier_nom_uniq'),
        ]
        indexes = [
            # Noms EXPLICITES (≤ 30 car.) : cette migration est écrite à la
            # main, un nom auto-haché divergerait du state (cf. mémoire
            # « migration index-name divergence »).
            models.Index(fields=['company', 'chantier', 'statut'],
                         name='btp_lot_co_chan_statut'),
            models.Index(fields=['company', 'jalon_contractuel'],
                         name='btp_lot_co_jalon'),
        ]

    def __str__(self):
        return f'{self.nom} — chantier {self.chantier_id}'


class LotTache(TenantModel):
    """NTCON14 — rattachement d'une ``gestion_projet.Tache`` EXISTANTE à un
    ``Lot`` (table de liaison du M2M ``Lot.taches``).

    Vit dans CETTE app (jamais un FK ajouté sur ``gestion_projet.Tache``, qui
    exigerait une migration hors périmètre). ``tache`` est UNIQUE : une tâche
    appartient à au plus UN lot — exactement la sémantique du FK optionnel
    décrit par NTCON14.
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_lot_taches', verbose_name='Société')
    lot = models.ForeignKey(
        Lot, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='rattachements', verbose_name='Lot')
    tache = models.ForeignKey(
        'gestion_projet.Tache', on_delete=models.CASCADE,
        # on_delete: cascade — le rattachement n'a pas de sens sans sa tâche.
        related_name='btp_lot_rattachements', verbose_name='Tâche')
    date_rattachement = models.DateTimeField(
        auto_now_add=True, verbose_name='Rattachée le')

    class Meta:
        verbose_name = 'Rattachement tâche ↔ lot'
        verbose_name_plural = 'Rattachements tâche ↔ lot'
        ordering = ['lot_id', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['tache'], name='btp_lot_tache_unique_lot'),
        ]

    def __str__(self):
        return f'Tâche {self.tache_id} → lot {self.lot_id}'


# ── NTCON16 — PPSPS (plan de prévention) ↔ QHSE ─────────────────────────────

class PPSPSChantier(TenantModel):
    """Plan Particulier de Sécurité et de Protection de la Santé d'un chantier.

    ``qhse.PermisTravail``/``EvaluationRisque`` couvrent déjà le niveau
    chantier GÉNÉRIQUE : NTCON16 ajoute le document PPSPS lui-même, ses LOTS
    couverts (NTCON14) et la SIGNATURE de chaque sous-traitant intervenant
    (``PPSPSSignature``, e-sign typée loi 53-05 — même principe que
    ``SignatureBtp``/``contrats.SignatureContrat``).

    ``document_ged_id`` référence LÂCHEMENT le document GED du PPSPS (aucun FK
    dur vers ``ged``), comme ``VisaDocument``/``DiffusionPlan``. ``qhse`` n'est
    JAMAIS réécrit : le lien se fait par le chantier, en lecture seule.

    Le PPSPS est « opposable » une fois ``date_validation`` posée : c'est ce
    plan-là que les sous-traitants doivent signer avant de démarrer
    (``services.sous_traitant_a_signe_ppsps``, soft-guard NTCON16).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_ppsps', verbose_name='Société')
    chantier = models.ForeignKey(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='btp_ppsps', verbose_name='Chantier')
    titre = models.CharField(
        max_length=200, blank=True, default='', verbose_name='Titre')
    document_ged_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name='ID du document GED du PPSPS')
    date_validation = models.DateField(
        null=True, blank=True, verbose_name='Validé le')
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_ppsps_valides',
        verbose_name='Validé par')
    lots_couverts = models.ManyToManyField(
        Lot, blank=True, related_name='ppsps',
        verbose_name='Lots couverts')
    # FK CHAÎNE vers le référentiel UNIFIÉ des sous-traitants (DC34) —
    # la date de signature vit sur la table de liaison ``PPSPSSignature``.
    sous_traitants_signataires = models.ManyToManyField(
        'stock.Fournisseur', through='PPSPSSignature', blank=True,
        related_name='btp_ppsps_signes',
        verbose_name='Sous-traitants signataires')

    class Meta:
        verbose_name = 'PPSPS de chantier'
        verbose_name_plural = 'PPSPS de chantier'
        ordering = ['-date_validation', '-id']
        indexes = [
            models.Index(fields=['company', 'chantier'],
                         name='btp_ppsps_co_chantier'),
        ]

    def __str__(self):
        return f'PPSPS #{self.pk} — chantier {self.chantier_id}'

    @property
    def est_valide(self):
        return self.date_validation is not None


class PPSPSSignature(TenantModel):
    """NTCON16 — signature d'un sous-traitant sur le PPSPS d'un chantier.

    Table de liaison du M2M ``PPSPSChantier.sous_traitants_signataires``, qui
    porte la DATE de signature et la preuve e-sign (nom dactylographié + IP +
    user-agent serveur — loi 53-05, même forme que ``SignatureBtp``). Un
    sous-traitant ne signe qu'UNE fois un PPSPS donné (contrainte d'unicité).
    """

    class Methode(models.TextChoices):
        TYPED = 'typed', 'Nom dactylographié'
        DRAW = 'draw', 'Signature dessinée'

    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_ppsps_signatures', verbose_name='Société')
    ppsps = models.ForeignKey(
        PPSPSChantier, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='signatures', verbose_name='PPSPS')
    sous_traitant = models.ForeignKey(
        'stock.Fournisseur', on_delete=models.CASCADE,
        # on_delete: cascade — la signature n'a pas de sens sans son signataire.
        related_name='btp_ppsps_signatures', verbose_name='Sous-traitant')
    signataire_nom = models.CharField(
        max_length=255, verbose_name='Nom du signataire')
    methode = models.CharField(
        max_length=20, choices=Methode.choices, default=Methode.TYPED,
        verbose_name='Méthode de signature')
    date_signature = models.DateTimeField(
        auto_now_add=True, verbose_name='Signé le')
    ip_adresse = models.CharField(max_length=45, blank=True, default='')
    user_agent = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'Signature de PPSPS'
        verbose_name_plural = 'Signatures de PPSPS'
        ordering = ['-date_signature', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['ppsps', 'sous_traitant'],
                name='btp_ppsps_signataire_uniq'),
        ]

    def __str__(self):
        return f'PPSPS {self.ppsps_id} signé par {self.sous_traitant_id}'


# ── NTCON18 — Photo-rapport hebdomadaire (opt-in PAR CHANTIER) ─────────────

class AbonnementRapportPhoto(TenantModel):
    """NTCON18 — opt-in d'un chantier au photo-rapport hebdomadaire.

    Le sweep ``manage.py rapport_photo_hebdo`` ne traite QUE les chantiers
    ayant une ligne ``actif=True`` : aucun envoi n'est jamais déclenché par
    défaut (opt-in strict). ``destinataires`` porte les emails client/MOE ;
    le PDF produit est un document d'AVANCEMENT PHOTO — jamais un coût
    interne, jamais un prix d'achat (règle CLAUDE.md).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_abonnements_rapport_photo', verbose_name='Société')
    chantier = models.OneToOneField(
        'installations.Installation', on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='btp_abonnement_rapport_photo', verbose_name='Chantier')
    actif = models.BooleanField(
        default=True, verbose_name='Envoi hebdomadaire activé')
    destinataires = models.JSONField(
        default=list, blank=True,
        verbose_name='Destinataires (emails client/MOE)')
    dernier_envoi = models.DateField(
        null=True, blank=True, verbose_name='Dernier envoi')

    class Meta:
        verbose_name = 'Abonnement au photo-rapport hebdomadaire'
        verbose_name_plural = 'Abonnements au photo-rapport hebdomadaire'
        ordering = ['-id']
        indexes = [
            models.Index(fields=['company', 'actif'],
                         name='btp_rapportphoto_co_actif'),
        ]

    def __str__(self):
        return f'Photo-rapport chantier {self.chantier_id}'


# ── NTCON19 — Checklist de réception de LOT ────────────────────────────────

class LotChecklistItem(TenantModel):
    """Étape de la checklist de RÉCEPTION d'un ``Lot`` (NTCON19).

    Réplique le PATTERN d'``installations.ChantierChecklistItem`` (clé +
    libellé + ordre + fait/fait_par/fait_le, unicité par parent+clé) SANS
    importer ``installations.models`` ni toucher sa chaîne de migrations : la
    checklist de réception d'un LOT est un objet DISTINCT de la checklist
    d'exécution du CHANTIER (qui reste entièrement gérée par ``installations``,
    inchangée). Un lot ne peut passer ``termine`` que si toutes ses étapes
    ``obligatoire`` sont cochées — soft-guard paramétrable
    (``services.config_btp`` → ``guard_checklist_lot_bloquant``, NTCON25).
    """
    company = models.ForeignKey(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_lot_checklist_items', verbose_name='Société')
    lot = models.ForeignKey(
        Lot, on_delete=models.CASCADE,
        # on_delete: cascade parent→enfant (composant du parent)
        related_name='checklist', verbose_name='Lot')
    cle = models.CharField(max_length=40, verbose_name='Clé')
    libelle = models.CharField(max_length=120, verbose_name='Libellé')
    ordre = models.PositiveIntegerField(default=0, verbose_name='Ordre')
    obligatoire = models.BooleanField(
        default=True, verbose_name='Obligatoire pour la réception')
    fait = models.BooleanField(default=False, verbose_name='Fait')
    fait_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='btp_lot_checklist_faits',
        verbose_name='Fait par')
    fait_le = models.DateTimeField(
        null=True, blank=True, verbose_name='Fait le')

    class Meta:
        verbose_name = 'Étape de checklist de réception (lot)'
        verbose_name_plural = 'Étapes de checklist de réception (lot)'
        ordering = ['ordre', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['lot', 'cle'], name='btp_lot_checklist_cle_uniq'),
        ]

    def __str__(self):
        return f'{self.lot_id} · {self.libelle} · {"✓" if self.fait else "—"}'


# ── NTCON25 — Réglages BTP par société (singleton par tenant) ──────────────

#: Corps d'état classiques d'un chantier TCE — SUGGESTION par défaut de
#: l'assistant NTCON23, éditable par société via ``ParametresBtpChantier``.
LOTS_TYPES_DEFAUT = [
    'Gros-œuvre', 'Électricité', 'Plomberie', 'CVC', 'Finitions',
]


def lots_types_defaut():
    """Défaut CALLABLE du champ JSON (jamais une liste mutable partagée)."""
    return list(LOTS_TYPES_DEFAUT)


class ParametresBtpChantier(TenantModel):
    """Réglages du module BTP pour UNE société (NTCON25).

    Singleton par tenant (``OneToOneField`` sur ``company``), même patron que
    les paramètres existants du dépôt (``qhse.CalendrierQhse``…) : au plus une
    ligne par société, créée à la demande. Les valeurs sont lues par
    ``services.config_btp`` — modifier un réglage change IMMÉDIATEMENT le
    comportement du guard correspondant, sans redéploiement :

    * ``guard_ppsps_bloquant`` → NTCON16 (bloque vs avertit au démarrage d'un
      ordre de sous-traitance) ;
    * ``guard_checklist_lot_bloquant`` → NTCON19 (bloque vs avertit à la
      réception d'un lot).

    Les délais et le taux de pénalité servent de DÉFAUTS de saisie ; ils ne
    réécrivent jamais un objet déjà créé.
    """
    company = models.OneToOneField(
        'authentication.Company', on_delete=models.CASCADE,
        # on_delete: cascade tenant (purge des données de la société supprimée)
        related_name='btp_parametres', verbose_name='Société')
    delai_reponse_rfi_defaut_jours = models.PositiveIntegerField(
        default=5, verbose_name='Délai de réponse RFI par défaut (jours ouvrés)')
    delai_revue_visa_defaut_jours = models.PositiveIntegerField(
        default=10, verbose_name='Délai de revue de visa par défaut (jours ouvrés)')
    guard_ppsps_bloquant = models.BooleanField(
        default=True,
        verbose_name='Bloquer le démarrage sans PPSPS signé (sinon avertir)')
    guard_checklist_lot_bloquant = models.BooleanField(
        default=True,
        verbose_name='Bloquer la réception si la checklist du lot est incomplète')
    lots_types_defaut = models.JSONField(
        default=lots_types_defaut, blank=True,
        verbose_name="Lots types suggérés par l'assistant")
    taux_penalite_retard_defaut_pmil = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        verbose_name='Taux de pénalité de retard par défaut (‰/jour)')
    # NTCON27 — ancienneté à partir de laquelle une réserve LEVÉE sort des
    # listes actives (drapeau ``archivee``, jamais une suppression).
    delai_archivage_reserves_levees_mois = models.PositiveIntegerField(
        default=24,
        verbose_name='Archiver les réserves levées après (mois)')

    class Meta:
        verbose_name = 'Réglages BTP'
        verbose_name_plural = 'Réglages BTP'

    def __str__(self):
        return f'Réglages BTP — société {self.company_id}'
