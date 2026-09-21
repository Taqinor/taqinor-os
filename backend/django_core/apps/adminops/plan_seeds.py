"""SOL9 — semis du plan de licence « Solaire ».

Le périmètre du plan est DÉRIVÉ, jamais recopié : tous les modules
INSTALLABLES du dépôt. Une app ajoutée demain entre donc dans le plan sans
qu'on ait à maintenir une liste à la main.

SOLMVP3 — la soustraction « moins les verticaux parqués par l'édition » a
disparu avec le mécanisme d'édition : il n'y a plus qu'un produit.

SOLMVP52 — une coquille de migrations (`core/parked.py`) GARDE son
`module_manifest` (le contrat de coquille l'exige, voir `core/parked.py`) et la
plupart ne posent PAS explicitement `installable: False` dessus : la
dérivation seule ne les exclurait donc PAS. `modules_du_plan_solaire` retire
donc explicitement tout label de `core.parked.APPS_PARQUEES`, quel que soit ce
que porte son manifeste — la SEULE garantie qu'une app sortie du MVP ne
revienne jamais dans un plan de licence vendu.

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
    """Clés de module installables du périmètre solaire (triées, stables).

    SOLMVP52 — exclut explicitement toute app parquée (`core.parked`) : son
    manifeste RESTE (contrat de coquille) et la plupart ne portent PAS
    `installable: False`, donc la dérivation seule les laisserait passer.
    """
    from core import modules as modules_infra
    from core.parked import est_parquee

    manifests = modules_infra.collect_manifests()
    return sorted(
        key for key, manifest in manifests.items()
        if manifest.get('installable')
        and not est_parquee(manifest.get('app_label'))
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
