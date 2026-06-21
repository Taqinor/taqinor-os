"""Modèles de la Gestion des contrats (module `apps.contrats`).

Socle du cycle de vie contractuel (CLM) : le modèle ``Contrat`` recense les
contrats de la société (vente, O&M, monitoring, garantie, PPA, fournisseur,
sous-traitance, location, emploi, NDA, maintenance…) avec leur statut, leurs
dates et leur montant.

Tout est multi-société : chaque modèle porte un FK ``company`` posé côté serveur
(jamais lu du corps de requête). Référence au client en lien lâche
(``client_id``) — jamais un import cross-app du modèle ``crm.Client``. Ce module
est entièrement additif.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models


class Contrat(models.Model):
    """Un contrat de la société (cycle de vie contractuel).

    Le ``type_contrat`` qualifie la nature du contrat et le ``statut`` son
    avancement (brouillon → en approbation → signé → actif → suspendu/résilié/
    expiré). Le client est référencé en lien lâche par ``client_id``.
    """
    class TypeContrat(models.TextChoices):
        VENTE = 'vente', 'Vente'
        OM = 'om', 'O&M'
        MONITORING = 'monitoring', 'Monitoring'
        GARANTIE = 'garantie', 'Garantie'
        PPA = 'ppa', 'PPA'
        FOURNISSEUR = 'fournisseur', 'Fournisseur'
        SOUS_TRAITANCE = 'sous_traitance', 'Sous-traitance'
        LOCATION = 'location', 'Location'
        EMPLOI = 'emploi', 'Emploi'
        NDA = 'nda', 'NDA'
        MAINTENANCE = 'maintenance', 'Maintenance'
        AUTRE = 'autre', 'Autre'

    class Statut(models.TextChoices):
        BROUILLON = 'brouillon', 'Brouillon'
        EN_APPROBATION = 'en_approbation', 'En approbation'
        SIGNE = 'signe', 'Signé'
        ACTIF = 'actif', 'Actif'
        SUSPENDU = 'suspendu', 'Suspendu'
        RESILIE = 'resilie', 'Résilié'
        EXPIRE = 'expire', 'Expiré'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        related_name='contrats',
        verbose_name='Société',
    )
    reference = models.CharField(
        max_length=50, blank=True, default='', verbose_name='Référence')
    type_contrat = models.CharField(
        max_length=20, choices=TypeContrat.choices,
        default=TypeContrat.VENTE, verbose_name='Type de contrat')
    objet = models.CharField(max_length=255, verbose_name='Objet')
    statut = models.CharField(
        max_length=20, choices=Statut.choices,
        default=Statut.BROUILLON, verbose_name='Statut')
    # Référence au client (crm.Client) en lien lâche — jamais un import du
    # modèle d'une autre app. NULL = pas de client rattaché.
    client_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name='ID du client')
    date_debut = models.DateField(
        null=True, blank=True, verbose_name='Date de début')
    date_fin = models.DateField(
        null=True, blank=True, verbose_name='Date de fin')
    montant = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        verbose_name='Montant')
    devise = models.CharField(
        max_length=3, default='MAD', verbose_name='Devise')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contrats_crees',
        verbose_name='Créé par',
    )
    date_creation = models.DateTimeField(
        auto_now_add=True, verbose_name='Créé le')

    class Meta:
        verbose_name = 'Contrat'
        verbose_name_plural = 'Contrats'
        ordering = ['-id']

    def __str__(self):
        return f'{self.objet} ({self.get_type_contrat_display()})'
