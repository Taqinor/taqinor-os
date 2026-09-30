"""QA-COHERENCE — invariants CRM ↔ ventes (lecture par ``apps.crm.selectors``).

Frontière cross-app (CLAUDE.md) : aucune importation des modèles CRM ici ;
l'étape SIGNED vient de STAGES.py via ``apps.crm.stages`` à l'intérieur du
sélecteur, jamais codée en dur.

Invariant écarté après lecture du code : « ``devis.client`` ≠ client résolu
du lead ». ``Lead.client`` est « rempli au premier devis OU MANUELLEMENT »
(apps/crm/models.py) et reste modifiable ensuite — un devis ancien peut donc
légitimement pointer l'ancien client. Règle non fiable, non ajoutée.
"""
from __future__ import annotations

from .registre import GRAVITE_AVERTISSEMENT, PORTEE_SOCIETE, regle


@regle('CRM_SIGNE_SANS_DEVIS_ACCEPTE',
       "Lead à l'étape Signé sans aucun devis accepté (« signé fantôme »)",
       gravite=GRAVITE_AVERTISSEMENT, portee=PORTEE_SOCIETE)
def signe_sans_devis_accepte(r, company, ctx):
    """Décision fondateur U11 (apps/crm/services.py,
    ``lead_signe_sans_devis_actif``) : le funnel ne recule jamais, donc un
    lead peut rester SIGNED alors que son seul devis accepté a disparu — on
    le SIGNALE sans reculer l'étape. Leads perdus, archivés et importés
    d'Odoo exclus (voir le sélecteur)."""
    from apps.crm.selectors import leads_signes_sans_devis_accepte
    return [r.violation(
        None, "Lead à l'étape Signé sans devis accepté.",
        object_type='lead', object_id=lead['id'],
        reference=f"LEAD-{lead['id']}", company_id=company.pk,
        valeurs={'stage': lead['stage'], 'source': lead['source']},
        attendu='au moins un devis accepté')
        for lead in leads_signes_sans_devis_accepte(company)]
