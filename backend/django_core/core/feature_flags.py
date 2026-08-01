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


def _emettre_bascule(toggle, *, user=None):
    """ODY25 — annonce une bascule RÉELLE de module sur le bus M6.

    Appelée UNIQUEMENT après un franchissement effectivement écrit (jamais pour
    une bascule no-op). ``core`` reste fondation : l'import du bus est local et
    aucun abonné n'est connu d'ici.
    """
    from . import events

    events.module_toggled.send(
        sender='core.feature_flags',
        toggle=toggle,
        company=toggle.company,
        module=toggle.module,
        actif=toggle.actif,
        user=user,
        raison=toggle.raison,
    )


def activer_module(company, key, *, user=None):
    """Active ``key`` pour la société + la fermeture de ses dépendances.

    Comme l'auto-install d'Odoo : activer un module réactive aussi tous les
    modules dont il dépend (transitivement). Idempotent. Renvoie la liste des
    clés effectivement (ré)activées.

    ODY25 — ``user`` (optionnel, TOUJOURS posé côté serveur par l'appelant,
    jamais lu d'un corps de requête) n'est utilisé que pour journaliser QUI a
    basculé : il ne change ni le résultat ni les droits. Un événement
    ``module_toggled`` est émis PAR module réellement (ré)activé — donc rien
    pour un module déjà actif (politique FG391 : absence de ligne = actif).
    """
    from . import modules as modules_infra
    from .models import ModuleToggle

    manifests = modules_infra.collect_manifests()
    if key not in manifests:
        raise DependencyError(f'Module inconnu : « {key} ».')
    a_activer = {key} | modules_infra.dependency_closure(key, manifests)
    active = []
    bascules = []
    for k in sorted(a_activer):
        toggle = (ModuleToggle.objects
                  .filter(company=company, module=k).first())
        if toggle is not None and not toggle.actif:
            toggle.actif = True
            toggle.save(update_fields=['actif', 'updated_at'])
            active.append(k)
            bascules.append(toggle)
        elif toggle is None:
            # Défaut déjà actif : rien à écrire (politique FG391).
            active.append(k)
    for toggle in bascules:
        _emettre_bascule(toggle, user=user)
    return sorted(set(active))


def desactiver_module(company, key, *, cascade=False, user=None):
    """Désactive ``key`` pour la société.

    Refuse (``DependencyError``) si des modules ACTIFS en dépendent, sauf
    ``cascade=True`` qui les désactive aussi (transitivement). Renvoie la liste
    des clés désactivées.

    ODY25 — ``user`` (optionnel, posé côté serveur) sert UNIQUEMENT à
    journaliser qui a désinstallé. Un événement ``module_toggled`` est émis par
    module réellement basculé : une cascade produit donc une ligne de journal
    par module désinstallé, jamais une seule pour le module cliqué.
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

    bascules = []
    for k in sorted(a_desactiver):
        toggle, cree = ModuleToggle.objects.get_or_create(
            company=company, module=k, defaults={'actif': False})
        if toggle.actif:
            toggle.actif = False
            toggle.save(update_fields=['actif', 'updated_at'])
            bascules.append(toggle)
        elif cree:
            # La ligne vient d'être créée à `actif=False` : c'est bien un
            # franchissement (le défaut FG391 « pas de ligne = actif » vient
            # d'être quitté), même si aucun `save` supplémentaire n'a eu lieu.
            bascules.append(toggle)
    for toggle in bascules:
        _emettre_bascule(toggle, user=user)
    return sorted(a_desactiver)


# ---------------------------------------------------------------------------
# ODY25 — Journal d'installation : qui a activé quoi, quand.
#
# Le journal N'A PAS son propre modèle : il est stocké dans le CHATTER
# GÉNÉRIQUE ``records.Activity`` (ARC8), la cible étant le ``ModuleToggle``
# lui-même (écrit par ``core.receivers``). Deux conséquences voulues :
#   * zéro migration, zéro 14ᵉ modèle de journal maison ;
#   * l'isolation multi-tenant est STRUCTURELLE — on ne lit que les entrées
#     dont la cible est un toggle DE LA SOCIÉTÉ demandée, et on re-filtre en
#     plus sur ``Activity.company`` (ceinture + bretelles).
# ---------------------------------------------------------------------------

# Libellés FR portés par l'entrée de chatter (``old_value``/``new_value``) —
# une SEULE source pour l'écriture (``core.receivers``) et la relecture.
ACTIF_INSTALLEE = 'Installée'
ACTIF_DESINSTALLEE = 'Désinstallée'


def journal_modules(company, *, limite_par_module=1):
    """Dernières bascules de modules de ``company`` (plus récente d'abord).

    Renvoie une liste de dicts sérialisables :
    ``{module, actif, par, le}`` — ``par`` est le nom d'affichage de
    l'utilisateur (``''`` pour une bascule système), ``le`` un ISO 8601.
    ``limite_par_module`` borne le nombre d'entrées rendues par module
    (1 = seulement la plus récente, ce dont la boutique a besoin).
    """
    if company is None:
        return []
    from django.contrib.contenttypes.models import ContentType

    from apps.records.models import Activity

    from .models import ModuleToggle

    par_id = dict(
        ModuleToggle.objects.filter(company=company)
        .values_list('id', 'module')
    )
    if not par_id:
        return []
    ct = ContentType.objects.get_for_model(ModuleToggle)
    lignes = (
        Activity.objects
        .filter(company=company, content_type=ct,
                object_id__in=list(par_id), field='actif')
        .select_related('created_by')
        .order_by('-created_at', '-id')
    )
    vus = {}
    out = []
    for ligne in lignes:
        module = par_id.get(ligne.object_id)
        if module is None:
            continue
        deja = vus.get(module, 0)
        if deja >= limite_par_module:
            continue
        vus[module] = deja + 1
        auteur = ligne.created_by
        out.append({
            'module': module,
            'actif': ligne.new_value == ACTIF_INSTALLEE,
            'par': (auteur.get_full_name() or auteur.username) if auteur else '',
            'le': ligne.created_at.isoformat() if ligne.created_at else None,
            'raison': ligne.body or '',
        })
    return out
