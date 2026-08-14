"""NTEXT16 — Vues de liste PERSONNALISÉES et partageables (fondation).

``VuePersonnalisee`` (défini dans ``core/models.py``) mémorise la façon dont un
utilisateur regarde une liste — filtres, tri, colonnes, groupement — et permet
de la partager : ``prive`` (soi seul), ``equipe`` (les membres de l'équipe
désignée), ``societe`` (tout le tenant).

``core`` reste FONDATION : il n'importe AUCUNE app métier (contrat import-linter
``core-foundation-is-a-base-layer``). Deux conséquences de conception :

* ``cible`` est une CHAÎNE (``'crm.lead'``) — jamais un import de modèle ;
* ``equipe`` est un IDENTIFIANT OPAQUE (même patron que
  ``core.sharing.SharingRule.principal_id``) : ``core`` ne connaît aucun modèle
  d'équipe. L'app qui POSSÈDE la notion d'équipe branche un fournisseur
  d'appartenance via :func:`register_equipe_membres_provider` (même patron que
  ``core.data_explorer.register_dataset``), typiquement dans son
  ``apps.py ready()``.

SANS fournisseur enregistré, :func:`equipes_de` renvoie un ensemble VIDE : une
vue ``equipe`` n'est alors visible que de son propriétaire. C'est le défaut SÛR
(on ne montre jamais plus que prévu), et purement additif.
"""
import logging

from django.db.models import Q

logger = logging.getLogger(__name__)

_EQUIPE_PROVIDERS = []


def register_equipe_membres_provider(fn):
    """Enregistre un fournisseur d'appartenance d'équipe.

    ``fn(user)`` renvoie un itérable d'IDENTIFIANTS d'équipe (convertis en
    chaînes) auxquelles ``user`` appartient. Plusieurs fournisseurs peuvent
    coexister (leurs résultats sont unis).
    """
    if not callable(fn):
        raise ValueError("Fournisseur d'équipe : fonction requise.")
    if fn not in _EQUIPE_PROVIDERS:
        _EQUIPE_PROVIDERS.append(fn)


def equipes_de(user):
    """Identifiants (chaînes) des équipes de ``user``. Ne lève jamais."""
    if user is None or not getattr(user, 'pk', None):
        return set()
    equipes = set()
    for provider in _EQUIPE_PROVIDERS:
        try:
            for identifiant in provider(user) or ():
                if identifiant not in (None, ''):
                    equipes.add(str(identifiant))
        except Exception:  # pragma: no cover - un fournisseur fautif est isolé
            logger.warning("core.vues: fournisseur d'équipe en échec",
                           exc_info=True)
    return equipes


def filtre_visibilite(qs, user):
    """Restreint ``qs`` aux vues que ``user`` a le droit de voir.

    Se compose APRÈS le filtre société (jamais à sa place) : ses propres vues,
    les vues de société, et les vues d'équipe des équipes dont il est membre.
    """
    from .models import VuePersonnalisee

    condition = Q(owner=user) | Q(partage=VuePersonnalisee.Partage.SOCIETE)
    equipes = equipes_de(user)
    if equipes:
        condition |= Q(partage=VuePersonnalisee.Partage.EQUIPE,
                       equipe__in=equipes)
    return qs.filter(condition).distinct()


# ── NTEXT17 — vue par DÉFAUT d'une liste (perso > rôle > société) ───────────

def tier_de(user):
    """Palier de rôle de ``user`` (``menu_tier``), ou ``''``. Ne lève jamais."""
    try:
        return (getattr(user, 'menu_tier', '') or '').strip()
    except Exception:  # pragma: no cover - défensif (user exotique)
        return ''


def resoudre_vue_defaut(qs, user, cible):
    """Vue par défaut APPLICABLE à ``user`` pour ``cible``, ou ``None``.

    ``qs`` doit DÉJÀ être scopé société (et, en pratique, filtré par
    :func:`filtre_visibilite`) : cette fonction ne fait qu'appliquer la
    PRÉCÉDENCE — défaut personnel de l'utilisateur, sinon défaut de son palier
    de rôle, sinon défaut de la société. Première trouvée, sinon ``None``.
    """
    from .models import VuePersonnalisee

    base = qs.filter(cible=cible, est_defaut=True)
    if getattr(user, 'pk', None):
        perso = base.filter(
            role_tier='', owner=user,
            partage=VuePersonnalisee.Partage.PRIVE).first()
        if perso is not None:
            return perso
    tier = tier_de(user)
    if tier:
        du_role = base.filter(role_tier=tier).first()
        if du_role is not None:
            return du_role
    return base.filter(
        role_tier='', partage=VuePersonnalisee.Partage.SOCIETE).first()


def demarquer_defauts_concurrents(vue):
    """Une SEULE vue défaut par (cible, portée) : démarque les concurrentes.

    Portée déduite de la ligne elle-même : ``role_tier`` renseigné = portée
    RÔLE ; sinon partage ``prive`` = portée PERSONNELLE (celle de son
    propriétaire) ; sinon portée SOCIÉTÉ. Appelée au moment d'écrire une vue
    ``est_defaut=True`` (jamais ailleurs) ; ne touche jamais une autre société
    ni une autre cible.
    """
    from .models import VuePersonnalisee

    if not vue.est_defaut:
        return 0
    concurrentes = VuePersonnalisee.objects.filter(
        company=vue.company, cible=vue.cible, est_defaut=True,
    ).exclude(pk=vue.pk)
    if (vue.role_tier or '').strip():
        concurrentes = concurrentes.filter(role_tier=vue.role_tier)
    elif vue.partage == VuePersonnalisee.Partage.PRIVE:
        concurrentes = concurrentes.filter(
            role_tier='', owner_id=vue.owner_id,
            partage=VuePersonnalisee.Partage.PRIVE)
    else:
        concurrentes = concurrentes.filter(
            role_tier='').exclude(partage=VuePersonnalisee.Partage.PRIVE)
    return concurrentes.update(est_defaut=False)
