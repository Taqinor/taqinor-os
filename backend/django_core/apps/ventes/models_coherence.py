"""QA-COHERENCE — mémoire des violations d'invariants de l'auditeur nocturne.

Une ligne = UNE violation d'UNE règle sur UN objet (empreinte stable :
règle + objet + valeurs identifiantes, voir
``apps/ventes/coherence/registre.Violation.empreinte``). L'auditeur
(``coherence.moteur.run_audit``) la tient à jour à chaque passe :

* vue pour la première fois → créée (``first_seen``) : c'est une NOUVELLE
  violation, la seule qui notifie ;
* toujours présente → ``last_seen`` avancé ;
* disparue → ``resolved_at`` posé (réapparue plus tard → ``resolved_at``
  remis à vide et de nouveau « nouvelle »).

Données d'AUDIT seulement : l'auditeur ne modifie JAMAIS l'objet métier
examiné (devis, facture, lead). Multi-tenant : ``company`` obligatoire,
unicité (société, empreinte).
"""
from django.db import models

from core.models import TenantModel


class ViolationCoherence(TenantModel):
    rule_id = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=20)
    object_type = models.CharField(max_length=32)
    object_id = models.BigIntegerField()
    reference = models.CharField(max_length=80, blank=True, default='')
    fingerprint = models.CharField(max_length=64)
    first_seen = models.DateTimeField()
    last_seen = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Violation de cohérence'
        verbose_name_plural = 'Violations de cohérence'
        db_table = 'ventes_violationcoherence'
        ordering = ['-last_seen']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'fingerprint'],
                name='uniq_violationcoherence_co_empreinte'),
        ]
        indexes = [
            models.Index(fields=['company', 'resolved_at'],
                         name='idx_violcoh_co_resolu'),
        ]

    def __str__(self):
        return f'{self.rule_id} — {self.object_type} {self.reference}'
