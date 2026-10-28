"""Lectures de l'app fondation ``roles``.

Organigramme (fondateur, 27/10/2026) — ``organisation_societe`` construit la
réponse de ``GET /api/django/roles/organisation/`` (contrat :
``contract_samples/organisation.json``). Les équipes commerciales et terrain
sont lues par LIBELLÉ (``django.apps.get_model``) : jamais d'import des
modèles ``crm``/``installations``."""
from django.apps import apps as django_apps

from .permissions_registre import CANONICAL_PORTAIL_ROLES

#: (type publié, app, modèle, champ du chef) — ordre d'affichage.
TYPES_EQUIPES = (
    ('commerciale', 'crm', 'EquipeCommerciale', 'responsable'),
    ('terrain', 'installations', 'Equipe', 'chef'),
    ('autre', 'roles', 'EquipeOrg', 'chef'),
)
ROLES_PORTAIL = frozenset(nom for nom, _perms in CANONICAL_PORTAIL_ROLES)


def est_compte_portail(user):
    """Compte portail externe (portée ou rôle portail) : hors organigramme."""
    if getattr(user, 'portee', 'interne') != 'interne':
        return True
    return bool(user.role_id and user.role.nom in ROLES_PORTAIL)


def personne(user):
    """``{id, nom, fonction, role}`` d'un compte, ou None."""
    if user is None:
        return None
    return {
        'id': user.pk,
        'nom': (user.get_full_name() or '').strip() or user.username,
        'fonction': user.fonction.intitule if user.fonction_id else None,
        'role': user.role.nom if user.role_id else None,
    }


def _equipes_actives(company_id, comptes):
    """Équipes actives des trois types : liste de (département, dict publié,
    ids des personnes rattachées — chef compris)."""
    sortie = []
    for type_, app_label, nom_modele, champ in TYPES_EQUIPES:
        try:
            Modele = django_apps.get_model(app_label, nom_modele)
        except LookupError:
            continue
        qs = Modele.objects.filter(company_id=company_id, actif=True)
        for e in qs.prefetch_related('membres').order_by('nom'):
            chef_id = getattr(e, f'{champ}_id')
            membres = [u.pk for u in e.membres.all()
                       if u.pk != chef_id and u.pk in comptes]
            sortie.append((e.departement_id, {
                'id': e.pk,
                'type': type_,
                'nom': e.nom,
                'chef': personne(comptes.get(chef_id)),
                'recoit_leads': (e.recoit_leads if type_ == 'commerciale'
                                 else None),
                'membres': [personne(comptes[pk]) for pk in membres],
                # Liste COMPLÈTE (chef et comptes inactifs compris) : l'écran
                # d'édition repart d'elle pour ne jamais retirer un membre
                # caché de l'arbre (revue Fable 27/10).
                'membres_ids': sorted(u.pk for u in e.membres.all()),
            }, set(membres) | {chef_id}))
    return sortie


def _a_completer(comptes):
    lignes = []
    for u in sorted(comptes.values(), key=lambda c: c.pk):
        manque = [cle for cle, ok in (('fonction', u.fonction_id),
                                      ('role', u.role_id)) if not ok]
        if manque:
            lignes.append({**personne(u), 'manque': manque})
    return lignes


def organisation_societe(company):
    """Organigramme de ``company`` (lecture pure) : Direction, départements
    (responsable, équipes, personnes sans équipe), équipes sans département,
    et comptes actifs (hors portails) à qui il manque la fonction ou le rôle."""
    from authentication.models import CustomUser

    from .models import Departement

    comptes = {
        u.pk: u for u in CustomUser.objects.filter(
            company=company, is_active=True).select_related(
                'role', 'fonction', 'fonction__departement')
        if not est_compte_portail(u)}
    deps = list(Departement.objects.filter(company=company, actif=True))
    equipes = _equipes_actives(getattr(company, 'pk', None), comptes)
    rattaches = set().union(*(ids for _d, _e, ids in equipes))
    direction = next((d for d in deps if d.est_direction), None)
    par_dep = {}
    for u in comptes.values():
        if u.fonction_id and u.fonction.departement_id:
            par_dep.setdefault(u.fonction.departement_id, []).append(u)
    return {
        'direction': None if direction is None else {
            'id': direction.pk,
            'nom': direction.nom,
            'responsable': personne(comptes.get(direction.responsable_id)),
            'membres': [personne(u) for u in par_dep.get(direction.pk, [])
                        if u.pk != direction.responsable_id],
        },
        'departements': [{
            'id': d.pk,
            'nom': d.nom,
            'ordre': d.ordre,
            'responsable': personne(comptes.get(d.responsable_id)),
            'equipes': [e for dep, e, _ids in equipes if dep == d.pk],
            'sans_equipe': [personne(u) for u in par_dep.get(d.pk, [])
                            if u.pk not in rattaches
                            and u.pk != d.responsable_id],
        } for d in deps if not d.est_direction],
        'equipes_sans_departement': [
            e for dep, e, _ids in equipes
            if dep not in {d.pk for d in deps if not d.est_direction}],
        'a_completer': _a_completer(comptes),
    }
