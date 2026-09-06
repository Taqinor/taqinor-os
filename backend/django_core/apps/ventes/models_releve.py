"""AUD121 — Session d'import de relevé bancaire (dry-run jetonné).

POURQUOI CE MODÈLE EXISTE. L'import de relevé (FG42) était en deux appels
INDÉPENDANTS : `dry_run` parsait et matchait le fichier pour l'aperçu, puis
`commit` le re-parsait et le RE-matchait tout seul, sans aucun lien avec ce
que l'opérateur venait de voir. Trois conséquences, toutes d'argent :

  * l'aperçu ne montrait que 10 lignes (``max_preview``) alors que le commit
    en écrivait jusqu'à ``MAX_ROWS`` (5 000) — l'opérateur validait un
    échantillon et signait le lot entier ;
  * aucune déduplication : le même fichier importé deux fois refaisait le
    même travail, donc pouvait recréer des paiements sur toute facture
    encore ouverte (règlement partiel) ;
  * le rapprochement retenu au commit pouvait DIFFÉRER de celui montré au
    dry-run (l'état des factures ayant bougé entre les deux).

La session referme les trois : le dry-run persiste la liste COMPLÈTE des
décisions {ligne → facture}, jetonnée ; le commit ne fait plus AUCUN
matching — il rejoue les décisions déjà validées, une seule fois
(``consomme_at``), et refuse un fichier dont le contenu (``fichier_hash``) a
déjà été importé pour cette société.

Multi-tenant : ``company`` obligatoire (TenantModel) ; toute lecture par
jeton est scopée société, un jeton d'une autre société est introuvable.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class ReleveImportSession(TenantModel):
    """Un dry-run d'import de relevé, avec ses décisions de rapprochement.

    ``decisions`` est la liste COMPLÈTE des lignes du fichier (pas l'aperçu
    tronqué) : ``[{ligne, statut, montant, date, mode, reference,
    facture_id, facture_reference, match_type, candidats}]``. Le commit ne
    rejoue que les lignes que l'opérateur a validées, et seulement celles
    dont le statut est importable.
    """

    # Jeton opaque remis au dry-run et exigé par le commit. Unique global :
    # deux sociétés ne peuvent pas se croiser, et une collision est
    # impossible plutôt qu'improbable.
    token = models.CharField(max_length=64, unique=True)
    # SHA-256 du contenu du fichier — la clé de déduplication : le même
    # relevé ré-importé pour la même société est refusé, quel que soit son
    # nom de fichier.
    fichier_hash = models.CharField(max_length=64, db_index=True)
    fichier_nom = models.CharField(max_length=255, blank=True, default='')
    decisions = models.JSONField(default=list, blank=True)
    # Horodatage de consommation : un jeton ne sert qu'UNE fois.
    consomme_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='releve_import_sessions',
    )

    class Meta:
        verbose_name = "Session d'import de relevé"
        verbose_name_plural = "Sessions d'import de relevé"
        db_table = 'ventes_releveimportsession'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'fichier_hash'],
                         name='idx_relevesess_co_hash'),
        ]

    def __str__(self):
        return f'Import relevé {self.token[:8]} ({self.fichier_nom})'

    @property
    def est_consomme(self):
        return self.consomme_at is not None
