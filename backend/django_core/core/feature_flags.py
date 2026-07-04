"""FG391 — Flags de fonctionnalités / modules par tenant (services).

Couche de FONDATION : décide si un module est actif POUR UNE SOCIÉTÉ à partir de
la table ``ModuleToggle``. ``core`` ne connaît AUCUN module métier (contrat
import-linter ``core-foundation-is-a-base-layer``) : ``module`` est une clé libre
fournie par l'appelant. Politique : ACTIVÉ PAR DÉFAUT (l'absence de ligne ⇒
actif) ; une ligne ``actif=False`` désactive le module pour la société.
"""
from __future__ import annotations


def module_actif(company, module, *, defaut=True):
    """Vrai si ``module`` est actif pour ``company``.

    Sans ligne ``ModuleToggle`` → ``defaut`` (activé par défaut). Avec ligne →
    son champ ``actif``. ``company`` ``None`` → ``defaut`` (pas de scope).
    """
    if company is None:
        return defaut
    from .models import ModuleToggle
    toggle = (ModuleToggle.objects
              .filter(company=company, module=module)
              .values_list('actif', flat=True)
              .first())
    return defaut if toggle is None else bool(toggle)


def modules_desactives(company):
    """Ensemble des clés de modules explicitement désactivés pour la société."""
    if company is None:
        return set()
    from .models import ModuleToggle
    return set(
        ModuleToggle.objects
        .filter(company=company, actif=False)
        .values_list('module', flat=True)
    )


# ---------------------------------------------------------------------------
# ODX3 — Catalogue de modules + fermeture de dépendances (activer/désactiver).
# Fusionne les manifests (``core.modules``) avec l'état ``ModuleToggle`` de la
# société. Politique FG391 conservée : ABSENCE de ligne ⇒ actif.
# ---------------------------------------------------------------------------


class DependencyError(ValueError):
    """Levée quand une désactivation casserait un module actif dépendant."""

    def __init__(self, message, dependents=None):
        super().__init__(message)
        self.dependents = list(dependents or [])


def catalogue_modules(company):
    """Catalogue des modules installables + leur état pour ``company``.

    Renvoie une liste de dicts (manifest + ``actif`` effectif). Seuls les
    modules ``installable=True`` sont retournés (les couches fondation ne se
    désactivent pas). ``actif`` = état effectif (défaut actif, politique FG391).
    """
    from . import modules as modules_infra

    manifests = modules_infra.collect_manifests()
    desactives = modules_desactives(company)
    out = []
    for key, manifest in sorted(manifests.items()):
        if not manifest['installable']:
            continue
        row = dict(manifest)
        row['actif'] = key not in desactives
        out.append(row)
    return out


def activer_module(company, key):
    """Active ``key`` pour la société + la fermeture de ses dépendances.

    Comme l'auto-install d'Odoo : activer un module réactive aussi tous les
    modules dont il dépend (transitivement). Idempotent. Renvoie la liste des
    clés effectivement (ré)activées.
    """
    from . import modules as modules_infra
    from .models import ModuleToggle

    manifests = modules_infra.collect_manifests()
    if key not in manifests:
        raise DependencyError(f'Module inconnu : « {key} ».')
    a_activer = {key} | modules_infra.dependency_closure(key, manifests)
    active = []
    for k in sorted(a_activer):
        toggle = (ModuleToggle.objects
                  .filter(company=company, module=k).first())
        if toggle is not None and not toggle.actif:
            toggle.actif = True
            toggle.save(update_fields=['actif', 'updated_at'])
            active.append(k)
        elif toggle is None:
            # Défaut déjà actif : rien à écrire (politique FG391).
            active.append(k)
    return sorted(set(active))


def desactiver_module(company, key, *, cascade=False):
    """Désactive ``key`` pour la société.

    Refuse (``DependencyError``) si des modules ACTIFS en dépendent, sauf
    ``cascade=True`` qui les désactive aussi (transitivement). Renvoie la liste
    des clés désactivées.
    """
    from . import modules as modules_infra
    from .models import ModuleToggle

    manifests = modules_infra.collect_manifests()
    if key not in manifests:
        raise DependencyError(f'Module inconnu : « {key} ».')

    desactives = modules_desactives(company)

    def dependants_actifs(k):
        return {
            d for d in modules_infra.dependents(k, manifests)
            if d not in desactives
        }

    if not cascade:
        bloquants = dependants_actifs(key)
        if bloquants:
            noms = ', '.join(sorted(bloquants))
            raise DependencyError(
                f'Impossible de désactiver « {key} » : les modules actifs '
                f'suivants en dépendent — {noms}. Utilisez cascade=1 pour les '
                'désactiver aussi.',
                dependents=sorted(bloquants))
        a_desactiver = {key}
    else:
        # Fermeture descendante : key + tous ses dépendants transitifs actifs.
        a_desactiver = set()
        pile = [key]
        while pile:
            cur = pile.pop()
            if cur in a_desactiver:
                continue
            a_desactiver.add(cur)
            pile.extend(dependants_actifs(cur))

    for k in sorted(a_desactiver):
        toggle, _ = ModuleToggle.objects.get_or_create(
            company=company, module=k, defaults={'actif': False})
        if toggle.actif:
            toggle.actif = False
            toggle.save(update_fields=['actif', 'updated_at'])
    return sorted(a_desactiver)
