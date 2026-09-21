"""SOL9 — semis du plan de licence « Solaire ».

Le périmètre du plan est DÉRIVÉ, jamais recopié : tous les modules
INSTALLABLES du dépôt. Une app ajoutée demain entre donc dans le plan sans
qu'on ait à maintenir une liste à la main.

SOLMVP3 — la soustraction « moins les verticaux parqués par l'édition » a
disparu avec le mécanisme d'édition : il n'y a plus qu'un produit. Les apps
sorties du MVP solaire (`core/parked.py`) quittent le plan d'elles-mêmes dès
leur coquille, parce qu'elles n'exposent plus de manifeste installable — la
dérivation reste la seule source, sans seconde liste à tenir.

Volontairement PAS une migration de données : `modules_inclus` doit refléter
les manifestes RÉELLEMENT chargés. Un semis explicite (commande ou appel de
service), idempotent, garde la liste juste.

Assignation : `CompanyProfile.plan` reste posé par le founder (admin Django) ou
par le gabarit de tenant Solaire (SOL10). Ce module ne touche AUCUNE société.
"""
from __future__ import annotations

CODE_SOLAIRE = 'solaire'
NOM_SOLAIRE = 'Solaire'


def modules_du_plan_solaire():
    """Clés de module installables du périmètre solaire (triées, stables)."""
    from core import modules as modules_infra

    manifests = modules_infra.collect_manifests()
    return sorted(
        key for key, manifest in manifests.items()
        if manifest.get('installable')
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
