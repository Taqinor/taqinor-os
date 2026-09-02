"""FG391 — Flags de fonctionnalités / modules par tenant (services).

Couche de FONDATION : décide si un module est actif POUR UNE SOCIÉTÉ à partir de
la table ``ModuleToggle``. ``core`` ne connaît AUCUN module métier (contrat
import-linter ``core-foundation-is-a-base-layer``) : ``module`` est une clé libre
fournie par l'appelant. Politique : ACTIVÉ PAR DÉFAUT (l'absence de ligne ⇒
actif) ; une ligne ``actif=False`` désactive le module pour la société.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SOL9 — Deuxième axe d'accès : le PLAN DE LICENCE, sur le MÊME chemin.
# ---------------------------------------------------------------------------
# `ModuleToggle` dit ce que la SOCIÉTÉ a éteint ; le plan de licence
# (`adminops.PlanLicence` via `CompanyProfile.plan`) dit ce que son ABONNEMENT
# inclut. Les deux doivent produire le MÊME effet, par le MÊME chemin — sinon
# on obtient deux gatings divergents (le classique « masqué dans la nav mais
# servi par l'API », ou l'inverse).
#
# `core` reste une couche de FONDATION : il n'importe AUCUNE app métier. Les
# apps s'enregistrent ici (même motif que `core.signup_hooks` / le bus M6) et
# `core` ne connaît que des callables opaques.
#
# Contrat d'un vérificateur :  fn(company, module_key) -> bool
#   `False` = le module est HORS PÉRIMÈTRE pour cette société.
# Politique NON-RESTRICTIVE : aucun vérificateur enregistré, ou un vérificateur
# qui lève → accès accordé (comportement historique, zéro régression).
_VERIFICATEURS_ACCES: list = []


def register_module_access_check(name, fn, *, exclus=None):
    """Enregistre (idempotent par ``name``) un vérificateur d'accès module.

    ``fn(company, module_key) -> bool`` répond pour UNE clé (chemin du
    middleware : un appel par requête). ``exclus(company) -> set[str]``, si
    fourni, répond pour TOUTES les clés en une fois — indispensable pour
    ``/auth/me``, qui interroge ~70 modules : sans version groupée, ce serait
    ~70 requêtes SQL par appel.
    """
    if not name or not callable(fn):
        raise ValueError('register_module_access_check : nom + callable requis.')
    _VERIFICATEURS_ACCES[:] = [
        v for v in _VERIFICATEURS_ACCES if v[0] != name]
    _VERIFICATEURS_ACCES.append((name, fn, exclus))


def registered_access_checks():
    """Noms des vérificateurs enregistrés (introspection / tests)."""
    return [v[0] for v in _VERIFICATEURS_ACCES]


def acces_module_autorise(company, module):
    """Vrai si AUCUN vérificateur enregistré n'exclut ``module``."""
    if company is None:
        return True
    for nom, fn, _exclus in _VERIFICATEURS_ACCES:
        try:
            if not fn(company, module):
                return False
        except Exception as exc:  # noqa: BLE001 — jamais enfermer un tenant
            logger.warning(
                'vérificateur d\'accès module %s a échoué (%s) : accès '
                'accordé par défaut', nom, exc)
    return True


def module_actif(company, module, *, defaut=True):
    """Vrai si ``module`` est actif pour ``company``.

    Sans ligne ``ModuleToggle`` → ``defaut`` (activé par défaut). Avec ligne →
    son champ ``actif``. ``company`` ``None`` → ``defaut`` (pas de scope).

    SOL9 — un module INCLUS côté toggle mais HORS du plan de licence est
    inactif : les deux axes se composent en ET, sur ce seul point d'entrée.
    """
    if company is None:
        return defaut
    from .models import ModuleToggle
    toggle = (ModuleToggle.objects
              .filter(company=company, module=module)
              .values_list('actif', flat=True)
              .first())
    actif = defaut if toggle is None else bool(toggle)
    if not actif:
        return False
    return acces_module_autorise(company, module)


def modules_desactives(company):
    """Ensemble des clés de modules INDISPONIBLES pour la société.

    Union des deux axes (SOL9) : les modules explicitement éteints
    (``ModuleToggle.actif=False``) ET les modules exclus par le plan de licence.
    C'est la MÊME liste que sert ``/auth/me`` et que lit le masquage de nav
    côté frontend : un module hors plan disparaît donc de l'UI exactement comme
    un module éteint, et l'API le renvoie en 404 par le même middleware.
    """
    if company is None:
        return set()
    from .models import ModuleToggle
    hors = set(
        ModuleToggle.objects
        .filter(company=company, actif=False)
        .values_list('module', flat=True)
    )
    hors |= _modules_hors_perimetre(company)
    return hors


def societes_avec_module(module, queryset=None):
    """SOL14 — sociétés pour lesquelles ``module`` est ACTIF.

    LA brique des tâches planifiées : une tâche périodique qui boucle sur
    ``Company.objects.all()`` travaille pour des sociétés qui ont éteint le
    module — elle leur écrit des prévisions, leur envoie des notifications, et
    contredit le 404 que l'API leur renvoie au même instant. Elle enveloppe le
    queryset au lieu de le remplacer : l'appelant garde ses propres filtres.

    Le filtrage est fait EN PYTHON (une requête ``ModuleToggle`` groupée puis
    les vérificateurs d'accès SOL9), pas en SQL : la politique « absence de
    ligne = actif » ne s'exprime pas par une jointure, et un futur vérificateur
    d'accès n'a pas à être traduisible en SQL pour être respecté.
    """
    from authentication.models import Company
    from .models import ModuleToggle

    if queryset is None:
        queryset = Company.objects.all()
    eteints = set(
        ModuleToggle.objects
        .filter(module=module, actif=False)
        .values_list('company_id', flat=True)
    )
    return [
        c for c in queryset
        if c.pk not in eteints and acces_module_autorise(c, module)
    ]


def _modules_hors_perimetre(company):
    """Modules INSTALLABLES qu'un vérificateur d'accès exclut (SOL9).

    Restreint aux modules installables : une couche de fondation (roles,
    parametres, core…) n'est jamais bornée par un plan. Utilise la version
    GROUPÉE d'un vérificateur quand elle existe (une requête au lieu d'une par
    module), et retombe sur la version unitaire sinon.
    """
    if company is None or not _VERIFICATEURS_ACCES:
        return set()
    from . import modules as modules_infra
    try:
        manifests = modules_infra.collect_manifests()
    except Exception:  # noqa: BLE001 — jamais casser /auth/me
        return set()
    installables = {
        key for key, manifest in manifests.items()
        if manifest.get('installable')
    }
    hors = set()
    for nom, fn, exclus in _VERIFICATEURS_ACCES:
        try:
            if exclus is not None:
                hors |= {k for k in (exclus(company) or ()) if k in installables}
            else:
                hors |= {k for k in installables if not fn(company, k)}
        except Exception as exc:  # noqa: BLE001 — jamais enfermer un tenant
            logger.warning(
                'vérificateur d\'accès module %s (groupé) a échoué (%s) : '
                'aucun module exclu par lui', nom, exc)
    return hors


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
    # SOL8 — une clé QUI PORTE DÉJÀ une ligne ModuleToggle mais n'a pas de
    # manifeste (surface purement frontend, ex. `magasin` : logistique
    # d'entrepôt sans app backend dédiée) doit rester RÉACTIVABLE EN UN CLIC.
    # Sans cette union, le semis SOL8 l'éteindrait sans qu'aucun écran ne
    # puisse la rallumer — une porte à sens unique. Reste GÉNÉRIQUE : `core`
    # n'énumère aucun module métier, il ne fait que refléter ce que la table
    # contient déjà. Aucune ligne ⇒ liste identique à l'historique.
    for key in sorted(_cles_togglees_sans_manifeste(company, manifests)):
        out.append(_manifest_synthetique(key, actif=key not in desactives))
    return out


def _cles_togglees_sans_manifeste(company, manifests):
    """Clés ayant une ligne ModuleToggle mais aucun manifeste déclaré."""
    if company is None:
        return set()
    from .models import ModuleToggle
    portees = set(
        ModuleToggle.objects
        .filter(company=company)
        .values_list('module', flat=True)
    )
    return {k for k in portees if k and k not in manifests}


def _manifest_synthetique(key, *, actif):
    """Entrée de catalogue pour une clé togglée sans manifeste (SOL8).

    Même FORME qu'un manifeste normalisé (``core.modules``) : les consommateurs
    (écran Applications, sérialisation) n'ont aucun cas particulier à gérer.
    """
    from . import modules as modules_infra

    return {
        'key': key,
        'label': key.replace('_', ' ').capitalize(),
        'icone': '',
        'depends': [],
        'installable': True,
        'description': "Surface sans manifeste backend, activable par société.",
        'categorie': 'Technique',
        'sku': modules_infra.SKU_OPTIONAL,
        'app_label': key,
        'actif': actif,
    }


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
        # SOL8 — une clé SANS manifeste reste pilotable si la société porte
        # déjà une ligne pour elle (surface frontend éteinte au semis) : sinon
        # l'écran Applications l'afficherait sans pouvoir la rallumer.
        if key not in _cles_togglees_sans_manifeste(company, manifests):
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
        # SOL8 — symétrique d'`activer_module` : une clé sans manifeste mais
        # déjà portée par la société reste désactivable (aucun dépendant
        # possible, elle n'est dans le `depends` d'aucun manifeste).
        if key not in _cles_togglees_sans_manifeste(company, manifests):
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
