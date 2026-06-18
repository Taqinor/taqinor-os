"""N58 — Configuration par société des libellés & de l'ordre d'affichage des
statuts métier (chantier / SAV / bon de commande).

Cette couche est PUREMENT COSMÉTIQUE : elle surcharge le LIBELLÉ et l'ORDRE
d'affichage (et l'éventuelle visibilité) d'un statut, jamais sa clé canonique
ni la logique de la machine à états. Les clés et les transitions restent
définies à la source (``installations.Installation`` / ``sav.Ticket`` /
``ventes.BonCommande``). Tant qu'aucune ligne n'est enregistrée, l'affichage
reste IDENTIQUE aux libellés codés en dur (les défauts sont calculés à la
lecture depuis ces modèles — pas de migration de données).

L'entonnoir du lead (``STAGES.py``) est un contrat CI figé : il n'est NI
touché NI référencé ici (couche permanente et séparée).
"""
from django.db import models


class StatutConfig(models.Model):
    """Surcharge company-scopée du libellé/ordre/visibilité d'UN statut métier.

    Additif : la table est vide par défaut ; chaque ligne est une surcharge
    explicite d'un statut existant. La clé (`cle`) reste celle du modèle
    source — on ne crée jamais de nouveau statut ici, on n'en supprime jamais.
    """

    class Domaine(models.TextChoices):
        CHANTIER = 'chantier', 'Chantier'
        SAV = 'sav', 'SAV'
        BON_COMMANDE = 'bon_commande', 'Bon de commande'

    company = models.ForeignKey(
        'authentication.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='statut_configs',
    )
    # Domaine du statut (chantier / sav / bon_commande).
    domaine = models.CharField(max_length=20, choices=Domaine.choices)
    # Clé canonique du statut (ex. 'signe', 'nouveau', 'en_attente') — JAMAIS
    # modifiable côté serveur : elle pilote la machine à états du modèle source.
    cle = models.CharField(max_length=40)
    # Libellé d'affichage (FR). Surcharge le libellé codé en dur du modèle.
    libelle = models.CharField(max_length=120)
    # Position d'affichage dans l'entonnoir (le tri non-alphabétique en dérive).
    ordre = models.PositiveIntegerField(default=0)
    # Visible dans les filtres/listes ? (n'affecte JAMAIS les transitions ni
    # les données existantes — purement un masque d'affichage).
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        # app_label explicite : ce module n'est pas importé par ``models.py``
        # (gardé séparé pour l'indépendance des lanes) ; il est chargé via
        # ``apps.py`` ready(). L'étiquette d'app reste « parametres ».
        app_label = 'parametres'
        ordering = ['domaine', 'ordre', 'id']
        unique_together = [('company', 'domaine', 'cle')]
        verbose_name = "Configuration de statut"
        verbose_name_plural = "Configurations de statut"

    def __str__(self):
        return f'{self.domaine}.{self.cle} → {self.libelle}'
