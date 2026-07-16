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


# ── NTCON1 — ReserveChantier (punch-list géo-localisée sur plan) ───────────

class ReserveChantier(models.Model):
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


class ReserveChantierHistorique(models.Model):
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


class SignatureBtp(models.Model):
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
