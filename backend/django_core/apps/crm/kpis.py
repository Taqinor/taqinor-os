"""AUD606 — tuiles KPI du funnel CRM pour le hub fédéré (ARC40).

``apps/crm/platform.py`` déclarait ``kpi_providers: ['crm_sales_report']`` — une
chaîne SANS POINT. Le seul consommateur, ``reporting.reports.kpi_federes``,
saute explicitement toute clé sans point (« clé libre héritée, pas un provider
résoluble ») : le hub KPI fédéré et les badges d'accueil n'ont donc JAMAIS
affiché la moindre tuile de funnel commercial, contrairement à cpq/ventes/ao/
adsengine dont les ``kpi_providers`` résolvent réellement.

Miroir LÉGER de ``reporting.reports.sales_report`` : ce dernier est une vue DRF
(elle lit ``request``, gère les périodes, exporte en XLSX/PDF) et n'est donc pas
appelable comme fournisseur. Les compteurs ci-dessous sont les mêmes, réduits à
la forme normalisée de tuile ``{id, label, valeur, unite?}``.

Les ÉTAPES viennent de ``apps.crm.stages`` (donc de ``STAGES.py`` à la racine —
règle #2 du dépôt) : aucune clé d'étape n'est écrite en dur ici.
"""
from __future__ import annotations

from . import stages as stage_mod


def kpi_crm(company):
    """Tuiles KPI du funnel commercial d'une société.

    Contrat de tuile : ``{id, label, valeur, unite?}``. Le hub résout ce
    callable par son chemin dotted déclaré dans ``apps/crm/platform.py``.
    """
    from .models import Lead

    actifs = Lead.objects.filter(company=company, is_archived=False)
    tuiles = [
        {'id': 'crm_leads_actifs', 'label': 'Leads actifs',
         'valeur': actifs.filter(perdu=False).count()},
    ]
    for cle in stage_mod.STAGES:
        tuiles.append({
            'id': f'crm_funnel_{cle.lower()}',
            'label': 'Leads — %s' % stage_mod.STAGE_LABELS.get(cle, cle),
            'valeur': actifs.filter(stage=cle, perdu=False).count(),
        })
    tuiles.append({
        'id': 'crm_leads_perdus', 'label': 'Leads perdus',
        'valeur': actifs.filter(perdu=True).count(),
    })
    return tuiles
