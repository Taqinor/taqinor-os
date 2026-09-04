"""SOL9 — semis du plan de licence « Solaire ».

Le périmètre du plan est DÉRIVÉ, jamais recopié : tous les modules
INSTALLABLES du dépôt, moins les verticaux parqués par l'édition solaire
(registre `erp_agentique/settings/editions.py`). Une app ajoutée demain entre
donc dans le plan sans qu'on ait à maintenir une liste à la main — et un
vertical parqué n'y entre jamais.

Volontairement PAS une migration de données : `modules_inclus` doit refléter
les manifestes RÉELLEMENT chargés, or une migration jouée en édition solaire
n'en verrait que 81 sur 88. Un semis explicite (commande ou appel de service),
idempotent, garde la liste juste.

Assignation : `CompanyProfile.plan` reste posé par le founder (admin Django) ou
par le gabarit de tenant Solaire (SOL10). Ce module ne touche AUCUNE société.
"""
from __future__ import annotations

CODE_SOLAIRE = 'solaire'
NOM_SOLAIRE = 'Solaire'


def modules_du_plan_solaire():
    """Clés de module installables du périmètre solaire (triées, stables)."""
    from core import modules as modules_infra
    from erp_agentique.settings import editions

    manifests = modules_infra.collect_manifests()
    parques = editions.modules_parques(editions.EDITION_SOLAR)
    return sorted(
        key for key, manifest in manifests.items()
        if manifest.get('installable') and key not in parques
    )


def seed_plan_solaire(*, mettre_a_jour=True):
    """Crée (ou rafraîchit) le `PlanLicence` « Solaire ». Idempotent.

    Renvoie ``(plan, cree)``. ``mettre_a_jour=False`` laisse un plan existant
    strictement intact (utile pour ne jamais écraser un périmètre ajusté à la
    main par le founder).
    """
    from .models import PlanLicence

    modules = modules_du_plan_solaire()
    plan, cree = PlanLicence.objects.get_or_create(
        code=CODE_SOLAIRE,
        defaults={'nom': NOM_SOLAIRE, 'modules_inclus': modules,
                  'actif': True},
    )
    if not cree and mettre_a_jour and list(plan.modules_inclus or []) != modules:
        plan.modules_inclus = modules
        plan.save(update_fields=['modules_inclus', 'updated_at'])
    return plan, cree
