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
from django.apps import apps as django_apps
from django.db import transaction

from core.conflit_etat import ConflitEtat

#: (relation inverse sur l'utilisateur, libellé du type d'équipe)
_RELATIONS_EQUIPES = (
    ('equipes_commerciales', 'commerciale'),
    ('installations_equipes', 'terrain'),
    ('equipes_org', 'autre'),
)

#: Organigramme (27/10/2026) — (app, modèle, champ du chef) des trois types
#: d'équipe, résolus par libellé (jamais d'import de modèle métier).
_MODELES_EQUIPES = (
    ('crm', 'EquipeCommerciale', 'responsable'),
    ('installations', 'Equipe', 'chef'),
    ('roles', 'EquipeOrg', 'chef'),
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
    with transaction.atomic():
        equipe = serializer.save(**save_kwargs)
        synchroniser_superviseurs(
            equipe.company_id, chef_avant, actuels,
            getattr(equipe, champ_chef), list(equipe.membres.all()),
            equipe.actif)
        recalculer_hierarchie(equipe.company_id)
    return equipe


def supprimer_equipe(instance, champ_chef, supprimer):
    """Supprime une équipe (``supprimer()``), rend leur liberté à ses membres
    puis recalcule la hiérarchie, le tout dans une transaction."""
    chef, membres = getattr(instance, champ_chef), list(instance.membres.all())
    company_id = instance.company_id
    with transaction.atomic():
        supprimer()
        synchroniser_superviseurs(company_id, chef, membres, None, [], False)
        recalculer_hierarchie(company_id)


# ── Organigramme (fondateur, 27/10/2026) : la hiérarchie se DÉDUIT ────────
# de la structure (Direction → départements → équipes → personnes).


def _modele(app_label, nom):
    try:
        return django_apps.get_model(app_label, nom)
    except LookupError:
        return None


def _structure(company_id):
    """(tête de Direction, {id département actif: (responsable, direction?)},
    [(chef, département, ids membres)] des équipes actives des trois types)."""
    Departement = _modele('roles', 'Departement')
    deps = {}
    if Departement is not None:
        for d in Departement.objects.filter(company_id=company_id, actif=True):
            deps[d.pk] = (d.responsable_id, d.est_direction)
    tete = next((r for r, direction in deps.values() if direction), None)
    equipes = []
    for app_label, nom, champ in _MODELES_EQUIPES:
        Modele = _modele(app_label, nom)
        if Modele is None:
            continue
        qs = Modele.objects.filter(company_id=company_id, actif=True)
        for e in qs.prefetch_related('membres').order_by('pk'):
            equipes.append((getattr(e, f'{champ}_id'), e.departement_id,
                            {u.pk for u in e.membres.all()}))
    return tete, deps, equipes


def _superviseur_calcule(uid, actuel, structure, fonction_dep):
    """Règles (a), (d), (b), (c), (e), (f) — (d) passe avant (b) ; renvoie
    ``actuel`` quand aucune règle ne s'applique."""
    tete, deps, equipes = structure
    if tete is not None and uid == tete:
        return None  # (a) tête de la Direction
    for resp, direction in deps.values():  # (d) tête de département
        if resp == uid and not direction:
            # Avant (b) : une appartenance d'équipe ne doit JAMAIS placer une
            # tête de département sous un chef d'équipe (ce chef verrait tout
            # le département par son sous-arbre — revue Fable 27/10). Sans
            # Direction : aucun superviseur plutôt qu'un chef d'équipe.
            if tete is not None:
                return tete
            chefs_de_uid = {c for c, _d, m in equipes if uid in m}
            return None if actuel in chefs_de_uid else actuel
    chefs = [c for c, _d, m in equipes if c is not None and uid in m
             and c != uid]
    if chefs:  # (b) membre d'une équipe : son chef (l'actuel s'il en est un)
        return actuel if actuel in chefs else chefs[0]
    for chef, dep, _m in equipes:  # (c) chef d'équipe → tête du département
        resp = deps.get(dep, (None, False))[0]
        if chef == uid and resp is not None and resp != uid:
            return resp
    resp, direction = deps.get(fonction_dep, (None, False))  # (e) fonction
    cible = tete if direction else resp
    if cible is not None and cible != uid:
        return cible
    return actuel  # (f) inchangé


def _verifier_cycles(carte, changes, noms):
    """``ConflitEtat`` (409, ENF11 : refus d'ÉTAT, le corps était conforme)
    si un compte dont le superviseur change entre dans une boucle."""
    for depart in changes:
        vus, courant = [], depart
        while courant is not None and courant not in vus:
            vus.append(courant)
            courant = carte.get(courant)
        if courant is not None:
            boucle = vus[vus.index(courant):] + [courant]
            raise ConflitEtat({'hierarchie': [
                'Cette organisation crée une boucle de supervision : '
                + ' → '.join(noms.get(i, str(i)) for i in boucle) + '.']})


def recalculer_hierarchie(company_id):
    """Recalcule le ``supervisor`` de chaque compte ACTIF de la société depuis
    la structure, par priorité : (a) tête de la Direction → aucun ; (b) membre
    (non chef) d'une équipe active → son chef ; (c) chef d'une équipe rattachée
    → tête de ce département ; (d) tête d'un autre département → tête de la
    Direction ; (e) fonction rattachée à un département → sa tête (Direction →
    tête de la Direction) ; (f) sinon INCHANGÉ. La carte entière est calculée
    d'abord ; une boucle est refusée (rien n'est écrit — l'appelant est dans
    sa transaction) ; seules les lignes qui changent sont écrites."""
    from authentication.models import CustomUser

    if company_id is None:
        return 0
    structure = _structure(company_id)
    users = list(CustomUser.objects.filter(company_id=company_id)
                 .select_related('fonction'))
    carte = {u.pk: u.supervisor_id for u in users}
    changes = {}
    for u in users:
        if not u.is_active:
            continue
        fonction_dep = u.fonction.departement_id if u.fonction_id else None
        cible = _superviseur_calcule(u.pk, carte[u.pk], structure, fonction_dep)
        if cible != carte[u.pk]:
            changes[u.pk] = cible
    _verifier_cycles({**carte, **changes}, changes,
                     {u.pk: _nom(u) for u in users})
    for pk, cible in changes.items():
        CustomUser.objects.filter(pk=pk).update(supervisor_id=cible)
    return len(changes)
