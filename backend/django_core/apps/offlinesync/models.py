"""NTMOB1 — journal des opérations hors-ligne, TOUS modules confondus.

Le terminal (PWA) file localement chaque écriture faite hors réseau avec une
**clé d'idempotence générée côté client** (`client_op_id`, un UUID), puis POST
le lot au point de synchro unique à la reconnexion. Cette table est le JOURNAL
de dédup ET la mémoire de ce qui attend / a échoué :

  * la 1re application mémorise son résultat (`statut='appliquee'`) → **rejouer
    la même clé est un no-op** qui renvoie le résultat mémorisé ;
  * une opération refusée par le serveur reste en base avec `statut='rejetee'`
    et son message : elle ne DISPARAÎT jamais en silence (VX119) et reste
    rejouable après correction ;
  * `statut='conflit'` est réservé à NTMOB2 (l'enregistrement cible a bougé
    entre la mise en file et l'application) — jamais posé ici.

Multi-tenant : `company` vient de ``TenantModel`` et est TOUJOURS posée côté
serveur depuis ``request.user.company``, jamais lue du corps. La clé
d'idempotence est unique PAR SOCIÉTÉ (deux locataires peuvent générer le même
UUID sans se marcher dessus, et aucun ne peut rejouer l'op de l'autre).

Généralise ``installations.FieldOp`` (capture terrain, un seul module) à
l'ensemble crm/ventes/stock/installations/sav — sans le remplacer : le point de
synchro terrain historique (`/installations/sync/`) reste en service et garde
son propre journal, les deux partagent le MÊME contrat de réponse.
"""
from django.conf import settings
from django.db import models

from core.models import TenantModel


class OfflineOperation(TenantModel):
    """Une opération d'écriture mise en file hors-ligne puis rejouée."""

    class Module(models.TextChoices):
        CRM = 'crm', 'CRM'
        VENTES = 'ventes', 'Ventes'
        STOCK = 'stock', 'Stock'
        INSTALLATIONS = 'installations', 'Chantiers'
        SAV = 'sav', 'SAV'

    class Statut(models.TextChoices):
        EN_ATTENTE = 'en_attente', 'En attente'
        APPLIQUEE = 'appliquee', 'Appliquée'
        REJETEE = 'rejetee', 'Rejetée'
        # Réservé NTMOB2 — résolution explicite de conflit, jamais silencieuse.
        CONFLIT = 'conflit', 'En conflit'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Auteur (terminal)')
    module = models.CharField(
        'Module cible', max_length=20, choices=Module.choices, db_index=True)
    op_type = models.CharField('Type d’opération', max_length=60)
    payload = models.JSONField('Corps de l’opération', default=dict, blank=True)
    # Clé d'idempotence générée par le terminal (UUID) — unique PAR SOCIÉTÉ.
    client_op_id = models.CharField('Clé client', max_length=64, db_index=True)
    statut = models.CharField(
        'Statut', max_length=12, choices=Statut.choices,
        default=Statut.EN_ATTENTE, db_index=True)
    # Résultat mémorisé, renvoyé tel quel au rejeu (no-op idempotent).
    resultat = models.JSONField('Résultat', default=dict, blank=True)
    erreur = models.TextField('Motif du refus', blank=True, default='')
    # Date de mise en file CÔTÉ TERMINAL (transmise par le client quand elle est
    # connue) — distincte de `created_at`, qui est la date de RÉCEPTION serveur :
    # un technicien peut filer une op le lundi et ne se reconnecter que le jeudi.
    date_creation = models.DateTimeField(
        'Mise en file (terminal)', null=True, blank=True)
    date_traitement = models.DateTimeField(
        'Traitée le', null=True, blank=True)

    class Meta:
        verbose_name = 'Opération hors-ligne'
        verbose_name_plural = 'Opérations hors-ligne'
        ordering = ['-id']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'client_op_id'],
                name='offlinesync_op_unique_par_societe'),
        ]
        indexes = [
            models.Index(fields=['company', 'statut'],
                         name='offlinesync_co_statut_idx'),
            models.Index(fields=['company', 'module', 'statut'],
                         name='offlinesync_co_mod_statut_idx'),
        ]

    def __str__(self):
        return f'{self.op_type} ({self.client_op_id[:8]}… — {self.statut})'
