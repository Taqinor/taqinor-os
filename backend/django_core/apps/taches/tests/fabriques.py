"""Fabriques de test PARTAGÉES de l'app `taches` (reference/donnees.md §5, signatures fixées).

Écrites une fois avec la migration, lecture seule ensuite : une fabrique neuve va dans le module
de test de la lane qui en a besoin. Rien ici ne passe par les services (`creer_taches`,
`planifier`) : ce sont des lignes posées par l'ORM.
"""
import hashlib
import itertools
import secrets
import string

from django.contrib.auth import get_user_model
from django.db.models import Max
from django.utils import timezone

from apps.records.models import Activity
from apps.roles.models import Role
from apps.taches.choix import Couleur, UsageJeton
from apps.taches.models.agenda import AgendaExterne
from apps.taches.models.journee import PlanJour
from apps.taches.models.presence import JetonAcces
from apps.taches.models.projets import Projet, Section
from apps.taches.models.rythme import ReglagesRythme
from apps.taches.models.taches import Tache
from authentication.models import Company

PAS_RANG = 1024
PREFIXES_JETON = {UsageJeton.CAPTURE: 'tqc_', UsageJeton.FLUX: 'tqf_', UsageJeton.TUILE: 'tqt_'}
_ALPHABET_JETON = string.ascii_letters + string.digits
_numeros = itertools.count(1)


def _numero():
    return next(_numeros)


def societe(slug='a'):
    """`Company` neuve (module `taches` actif : aucune bascule ne l'éteint). Deux slugs distincts
    donnent deux sociétés distinctes — jamais un `get_or_create` qui rendrait la même."""
    return Company.objects.create(nom=f'Société {slug.upper()}', slug=f'taches-{slug}')


def compte(societe, *, voir=True, admin=False, nom='u1'):
    """Utilisateur interne actif de `societe`, porteur d'un rôle de TEST (aucun rôle système ne
    porte `taches_voir` avant l'activation) : `taches_voir` si `voir`, `roles_gerer`
    (administrateur, `IsAdminRole`) si `admin`. `voir=False, admin=False` : rôle fin sans le droit."""
    permissions = (['taches_voir'] if voir else []) + (['roles_gerer'] if admin else [])
    role = Role.objects.create(company=societe, nom=f'Test tâches {nom}', permissions=permissions)
    return get_user_model().objects.create_user(
        username=f'{nom}@{societe.slug}', password=None, company=societe, role=role,
        first_name=nom)


def projet(compte, **champs):
    """`Projet` vivant de `compte` (nom unique « Projet <n> », priorité 0, couleur `terre`)."""
    champs.setdefault('nom', f'Projet {_numero()}')
    champs.setdefault('couleur', Couleur.TERRE)
    return Projet.objects.create(company=compte.company, proprietaire=compte, **champs)


def section(projet, **champs):
    """Étape de `projet` (même société, même propriétaire que lui)."""
    champs.setdefault('nom', f'Étape {_numero()}')
    return Section.objects.create(company=projet.company, projet=projet, **champs)


def tache(compte, *, projet=None, **champs):
    """`Tache` posée par l'ORM : `triee_le` posé si projet ou jour, `rang_projet` = dernier de la
    même liste (le projet, ou « À trier ») + 1 024."""
    champs.setdefault('titre', f'Tâche {_numero()}')
    if projet is not None or champs.get('jour_prevu') is not None:
        champs.setdefault('triee_le', timezone.now())
    if 'rang_projet' not in champs:
        dernier = (Tache.objects
                   .filter(company=compte.company, proprietaire=compte, projet=projet)
                   .aggregate(m=Max('rang_projet'))['m'])
        champs['rang_projet'] = (dernier or 0) + PAS_RANG
    return Tache.objects.create(company=compte.company, proprietaire=compte, projet=projet, **champs)


def reglages(compte, **champs):
    """`ReglagesRythme` de `compte` (en production, seul `creer_taches` la crée)."""
    return ReglagesRythme.objects.create(company=compte.company, proprietaire=compte, **champs)


def plan(compte, jour, **champs):
    """`PlanJour` de `compte` pour `jour`."""
    return PlanJour.objects.create(company=compte.company, proprietaire=compte, jour=jour, **champs)


def jeton(compte, usage):
    """`(JetonAcces, clair)` : le clair (`tqc_`/`tqf_`/`tqt_` + 40 caractères) n'est rendu
    qu'ici ; la base garde son SHA-256 hexadécimal et ses 8 premiers caractères."""
    clair = PREFIXES_JETON[UsageJeton(usage)] + ''.join(
        secrets.choice(_ALPHABET_JETON) for _ in range(40))
    objet = JetonAcces.objects.create(
        company=compte.company, proprietaire=compte, usage=usage, prefixe=clair[:8],
        jeton_hash=hashlib.sha256(clair.encode('utf-8')).hexdigest())
    return objet, clair


def activite(compte, **champs):
    """`records.Activity` assignée à `compte` et ouverte (à-faire personnel, échéance aujourd'hui)."""
    champs.setdefault('summary', f'Activité {_numero()}')
    champs.setdefault('due_date', timezone.localdate())
    champs.setdefault('personnelle', True)
    champs.setdefault('assigned_to', compte)
    champs.setdefault('created_by', compte)
    return Activity.objects.create(company=compte.company, done=False, **champs)


def agenda_externe(compte, **champs):
    """`AgendaExterne` de `compte` ; aucune lecture réseau."""
    champs.setdefault('url', 'https://agenda.example/a.ics')
    return AgendaExterne.objects.create(company=compte.company, proprietaire=compte, **champs)
