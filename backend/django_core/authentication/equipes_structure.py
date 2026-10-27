"""Structure du personnel tenue par les ÉQUIPES (fondateur, 26/10/2026).

Les équipes — commerciales (``crm.EquipeCommerciale`` : ``responsable``) et
terrain (``installations.Equipe`` : ``chef``) — sont l'UNIQUE source de « qui
encadre qui » : enregistrer une équipe pose le ``supervisor`` de chacun de ses
membres sur son chef. La portée de visibilité (``core.scoping``) en découle :
le chef voit son équipe par son sous-arbre, un commercial ne voit que les siens.

Une personne appartient à UNE seule équipe active (commerciale OU terrain),
sinon son superviseur serait ambigu.

Fondation : aucun import de modèle métier — les équipes sont lues par les
relations inverses de l'utilisateur (``equipes_commerciales``,
``installations_equipes``).
"""
from core.conflit_etat import ConflitEtat

#: (relation inverse sur l'utilisateur, libellé du type d'équipe)
_RELATIONS_EQUIPES = (
    ('equipes_commerciales', 'commerciale'),
    ('installations_equipes', 'terrain'),
)


def _nom(user):
    getter = getattr(user, 'get_full_name', None)
    nom = (getter() or '').strip() if callable(getter) else ''
    return nom or user.username


def valider_membres_uniques(equipe, membres, chef, nouveaux=None):
    """Lève ``ConflitEtat`` (409, ENF11 : refus d'ÉTAT, le corps était
    conforme) sous ``membres`` si l'un des ``membres``
    appartient déjà à une AUTRE équipe active (commerciale ou terrain), ou si
    un membre encadre déjà — directement ou non — le ``chef`` (cycle).

    ``nouveaux`` (ids) borne le contrôle « une seule équipe » aux personnes
    AJOUTÉES par la requête : une équipe d'avant la règle dont un membre
    figure aussi ailleurs reste renommable/archivable. None = tous."""
    from core.scoping import subtree_user_ids

    erreurs = []
    for membre in membres:
        if chef is not None and membre.pk == chef.pk:
            continue
        for relation, libelle in _RELATIONS_EQUIPES:
            if nouveaux is not None and membre.pk not in nouveaux:
                break
            autres = getattr(membre, relation).filter(actif=True)
            if equipe is not None and equipe.pk is not None and \
                    type(equipe)._meta.label_lower == getattr(
                        membre, relation).model._meta.label_lower:
                autres = autres.exclude(pk=equipe.pk)
            autre = autres.first()
            if autre is not None:
                erreurs.append(
                    f"{_nom(membre)} est déjà membre de l'équipe {libelle} "
                    f"« {autre.nom} ». Une personne n'appartient qu'à une "
                    "seule équipe.")
                break
        if chef is not None and chef.pk in subtree_user_ids(membre):
            erreurs.append(
                f"{_nom(membre)} encadre déjà {_nom(chef)} : il ne peut pas "
                "être membre de son équipe.")
    if erreurs:
        raise ConflitEtat({'membres': erreurs})


def synchroniser_superviseurs(company_id, chef_avant, membres_avant,
                              chef, membres, actif):
    """Pose ``supervisor = chef`` sur les membres d'une équipe active ; rend
    leur liberté (``supervisor = None``) aux personnes qui étaient encadrées
    par l'ancien chef AU TITRE de cette équipe et ne le sont plus (retirées,
    équipe archivée/supprimée, chef retiré ou changé)."""
    from authentication.models import CustomUser

    ids_avant = {u.pk for u in membres_avant}
    ids_apres = {u.pk for u in membres} if actif and chef is not None else set()
    if chef is not None:
        ids_apres.discard(chef.pk)
    base = CustomUser.objects.filter(company_id=company_id)
    if chef_avant is not None:
        liberes = (ids_avant - ids_apres) | (
            ids_avant if chef is None or chef.pk != chef_avant.pk else set())
        liberes -= ids_apres
        if liberes:
            base.filter(pk__in=liberes, supervisor_id=chef_avant.pk).update(
                supervisor=None)
    if ids_apres:
        base.filter(pk__in=ids_apres).exclude(supervisor_id=chef.pk).update(
            supervisor=chef)


def enregistrer_equipe(serializer, champ_chef, **save_kwargs):
    """Contrôle « une seule équipe » + cycle sur l'état FINAL d'une équipe
    validée par ``serializer``, l'enregistre, puis synchronise les
    superviseurs. ``champ_chef`` : ``'chef'`` (terrain) ou ``'responsable'``.
    Seuls les membres AJOUTÉS sont soumis à la règle « une seule équipe »."""
    attrs = serializer.validated_data
    inst = serializer.instance
    actuels = list(inst.membres.all()) if inst else []
    chef_avant = getattr(inst, champ_chef) if inst else None
    if attrs.get('actif', inst.actif if inst else True):
        membres = attrs.get('membres', actuels)
        valider_membres_uniques(
            inst, membres, attrs.get(champ_chef, chef_avant),
            {u.pk for u in membres} - {u.pk for u in actuels})
    equipe = serializer.save(**save_kwargs)
    synchroniser_superviseurs(
        equipe.company_id, chef_avant, actuels, getattr(equipe, champ_chef),
        list(equipe.membres.all()), equipe.actif)
    return equipe
