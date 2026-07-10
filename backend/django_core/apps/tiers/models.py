"""Modèle ``Tiers`` — le ``res.partner`` de TAQINOR (ARC17).

L'identité d'une partie prenante (nom/coordonnées/identifiants légaux) est
aujourd'hui re-saisie dans 5+ modèles de domaine (crm.Client, crm.Lead,
stock.Fournisseur, compta.Tiers…). ``apps.tiers`` est une COUCHE FONDATION :
elle ne dépend d'AUCUNE app de domaine — les domaines pourront la référencer
plus tard (par FK string, dans des tâches séparées ARC18/19), jamais l'inverse.
Le contrat import-linter ``tiers-is-a-base-layer`` verrouille ce sens unique.

Multi-société : chaque ``Tiers`` porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Entièrement additif — aucune table existante
touchée par cette tâche.
"""
from django.db import models


class Tiers(models.Model):
    """Une partie prenante d'une société (client, fournisseur, partenaire,
    sous-traitant — potentiellement plusieurs rôles à la fois).

    Modélise l'identité commune (nom/coordonnées/identifiants légaux marocains
    ICE/RC/IF/CIN, RIB, GPS) que les modèles de domaine dupliquent aujourd'hui.
    """

    class TypeTiers(models.TextChoices):
        PARTICULIER = 'particulier', 'Particulier'
        ENTREPRISE = 'entreprise', 'Entreprise'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='tiers',
        verbose_name='Société',
    )
    type_tiers = models.CharField(
        max_length=20, choices=TypeTiers.choices,
        default=TypeTiers.PARTICULIER, verbose_name='Type de tiers')

    # ── Identité ────────────────────────────────────────────────────────────
    # Particulier : nom/prénom. Entreprise : raison sociale. Les trois champs
    # coexistent (un contact chez une entreprise a aussi un nom/prénom) ; seul
    # ``nom`` (nom de famille ou raison sociale) est requis.
    nom = models.CharField(
        max_length=255, verbose_name='Nom / Raison sociale')
    prenom = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Prénom')
    raison_sociale = models.CharField(
        max_length=255, blank=True, default='', verbose_name='Raison sociale')

    # ── Coordonnées ─────────────────────────────────────────────────────────
    telephone = models.CharField(
        max_length=30, blank=True, default='', verbose_name='Téléphone')
    whatsapp = models.CharField(
        max_length=30, blank=True, default='', verbose_name='WhatsApp')
    email = models.EmailField(blank=True, default='', verbose_name='Email')
    adresse = models.TextField(blank=True, default='', verbose_name='Adresse')
    ville = models.CharField(
        max_length=120, blank=True, default='', verbose_name='Ville')
    # GPS (motif Lead crm) — coordonnées optionnelles du site du tiers.
    gps_lat = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        verbose_name='Latitude GPS')
    gps_lng = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True,
        verbose_name='Longitude GPS')

    # ── Identifiants légaux marocains ───────────────────────────────────────
    ice = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='ICE',
        help_text="Identifiant Commun de l'Entreprise.")
    rc = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='RC', help_text='Registre de Commerce.')
    identifiant_fiscal = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='IF', help_text='Identifiant Fiscal.')
    cin = models.CharField(
        max_length=30, blank=True, default='',
        verbose_name='CIN',
        help_text="Carte d'Identité Nationale (particulier).")
    rib = models.CharField(
        max_length=50, blank=True, default='', verbose_name='RIB')

    # ── Rôles (un tiers peut cumuler plusieurs rôles) ───────────────────────
    is_client = models.BooleanField(default=False, verbose_name='Client')
    is_fournisseur = models.BooleanField(
        default=False, verbose_name='Fournisseur')
    is_partenaire = models.BooleanField(
        default=False, verbose_name='Partenaire')
    is_soustraitant = models.BooleanField(
        default=False, verbose_name='Sous-traitant')

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Tiers'
        verbose_name_plural = 'Tiers'
        ordering = ['nom', 'prenom']
        indexes = [
            models.Index(fields=['company', 'nom']),
            models.Index(fields=['company', 'email']),
        ]

    def __str__(self):
        if self.type_tiers == self.TypeTiers.ENTREPRISE and self.raison_sociale:
            return self.raison_sociale
        plein = f'{self.prenom} {self.nom}'.strip()
        return plein or self.nom

    @property
    def nom_complet(self):
        """Libellé d'affichage : raison sociale (entreprise) ou prénom+nom."""
        return str(self)
