"""Modèles des salles de données sécurisées (module ``apps.datarooms``).

NTDOC11 — une ``SalleDeDonnees`` est une COLLECTION THÉMATIQUE de documents
GED déjà existants (levée de fonds, due diligence, appel d'offres). Elle ne
DÉPLACE ni ne DUPLIQUE rien : ``SalleDeDonneesDocument`` est une table de
liaison explicite vers ``ged.Document``, référencé par string-FK (jamais
d'import de ``ged.models`` — la lecture croisée passe par ``ged.selectors``).

Multi-société : tout modèle hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage, ARC1) ; la société est TOUJOURS posée côté serveur.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class SalleDeDonnees(TenantModel):
    """Une salle de données : un dossier virtuel ouvert à des tiers.

    ``dossier_source`` est un simple POINT DE DÉPART facultatif (le dossier GED
    d'où la salle a été montée) — il ne contraint pas le contenu : une salle
    agrège des documents de dossiers différents.

    ``deal_type`` est un texte LIBRE assumé (« levée de fonds », « due
    diligence », « appel d'offres »… ) : le vocabulaire des opérations varie
    d'une société à l'autre, une énumération fermée serait fausse dès le
    deuxième client.
    """

    class Statut(models.TextChoices):
        OUVERTE = 'ouverte', 'Ouverte'
        FERMEE = 'fermee', 'Fermée'

    nom = models.CharField(max_length=255, verbose_name='Nom')
    description = models.TextField(
        blank=True, default='', verbose_name='Description')
    # String-FK vers la GED : aucune import de ``ged.models`` ici (ARC/M3).
    dossier_source = models.ForeignKey(
        'ged.Folder', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='salles_donnees',
        verbose_name='Dossier GED de départ')
    deal_type = models.CharField(
        max_length=120, blank=True, default='',
        verbose_name="Type d'opération")
    statut = models.CharField(
        max_length=10, choices=Statut.choices, default=Statut.OUVERTE,
        verbose_name='Statut')
    # Expiration GLOBALE de la salle (NULL = pas d'expiration globale). Chaque
    # viewer porte en plus SA propre expiration (NTDOC12).
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name='Expire le')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='salles_donnees_creees',
        verbose_name='Créée par')

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name = 'Salle de données'
        verbose_name_plural = 'Salles de données'
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='dataroom_co_statut_idx'),
        ]

    def __str__(self):
        return self.nom

    @property
    def est_ouverte(self):
        """Une salle est exploitable tant qu'elle n'est pas fermée.

        L'expiration globale est évaluée à la LECTURE (NTDOC12) et non figée en
        base : une date dépassée ne « ferme » pas la salle, elle la rend
        seulement inaccessible côté public."""
        return self.statut == self.Statut.OUVERTE


class SalleDeDonneesDocument(TenantModel):
    """Appartenance d'un document GED à une salle (table de liaison explicite).

    Retirer cette ligne SORT le document de la salle — il reste intact dans la
    GED (aucune suppression, aucun déplacement, aucune copie).
    """

    salle = models.ForeignKey(
        # on_delete: une ligne d'appartenance n'existe que pour sa salle ;
        # supprimer la salle ne doit laisser aucune ligne orpheline.
        SalleDeDonnees, on_delete=models.CASCADE, related_name='documents',
        verbose_name='Salle')
    document = models.ForeignKey(
        # on_delete: une APPARTENANCE n'a aucun sens sans son document ; la
        # cascade ne détruit que le lien (le document reste maître, jamais
        # l'inverse — retirer une salle ne touche jamais la GED).
        'ged.Document', on_delete=models.CASCADE,
        related_name='appartenances_salle', verbose_name='Document')
    ordre = models.PositiveIntegerField(
        default=0, verbose_name="Ordre d'affichage")
    # Un document peut être préparé dans la salle sans être encore exposé aux
    # viewers : `visible=False` le masque du public sans le retirer.
    visible = models.BooleanField(default=True, verbose_name='Visible')

    class Meta:
        ordering = ['ordre', 'id']
        verbose_name = 'Document de salle de données'
        verbose_name_plural = 'Documents de salle de données'
        constraints = [
            models.UniqueConstraint(
                fields=('salle', 'document'),
                name='dataroom_uniq_salle_document'),
        ]

    def __str__(self):
        return f'{self.salle_id} → {self.document_id}'
