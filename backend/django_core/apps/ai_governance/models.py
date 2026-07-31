"""Modèles du module « ai_governance » (Groupe NTAI).

MULTI-TENANT : tout modèle ici hérite de ``core.models.TenantModel`` (FK
``company`` + horodatage) — la société est TOUJOURS posée côté serveur, jamais
lue d'un corps de requête.
"""
from django.db import models

from core.models import TenantModel


class DriftSnapshot(TenantModel):
    """NTAI29 — Photo mensuelle de la distribution des features d'un scorer.

    Sert à détecter une DÉRIVE (drift) : quand la population sur laquelle un
    scorer tourne ne ressemble plus à celle de sa baseline, ses prédictions
    deviennent silencieusement moins fiables. Le ``psi`` (Population Stability
    Index) mesure cet écart par rapport au snapshot de RÉFÉRENCE de la même
    société et du même modèle.

    Purement OFFLINE : aucune donnée ne sort, aucun LLM n'est appelé — le PSI
    est calculé avec la bibliothèque standard (``math.log``).
    """

    #: Le premier snapshot d'un couple (société, modèle) devient la référence
    #: à laquelle les suivants se comparent ; son ``psi`` reste nul.
    modele = models.CharField(
        max_length=60,
        help_text="Nom du scorer surveillé (churn, win_proba, "
                  "retard_paiement…).")
    date = models.DateField(
        help_text='Premier jour de la période observée.')
    distribution_json = models.JSONField(
        default=dict, blank=True,
        help_text='{bucket: proportion} des features d\'entrée observées.')
    psi = models.FloatField(
        default=0.0,
        help_text='Population Stability Index vs la baseline (0 = identique).')
    est_baseline = models.BooleanField(
        default=False,
        help_text='Snapshot de référence auquel les suivants se comparent.')
    alerte_emise = models.BooleanField(
        default=False,
        help_text='Une alerte de dérive a été notifiée pour ce snapshot.')

    class Meta:
        verbose_name = 'Snapshot de dérive'
        verbose_name_plural = 'Snapshots de dérive'
        ordering = ['-date', 'modele']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'modele', 'date'],
                name='uniq_driftsnapshot_company_modele_date'),
        ]
        indexes = [
            # Nom EXPLICITE : sans lui, Django en dérive un hash qui diverge
            # du nom écrit à la main dans la migration (piège connu du dépôt).
            models.Index(fields=['company', 'modele', '-date'],
                         name='ai_gov_drift_co_mod_date_idx'),
        ]

    def __str__(self):
        return f'{self.modele} @ {self.date} (PSI {self.psi:.3f})'
