"""ACHT79 (C-ACHT-049/054/055) — garde de CLASSE des permissions
d'`apps/installations` et `apps/outillage`.

Le balai énumère TOUS les viewsets des deux routeurs et, pour chaque action
d'ÉCRITURE (méthode non sûre : actions standard create/update/partial_update/
destroy + chaque `@action` POST/PUT/PATCH/DELETE), vérifie que la chaîne de
permissions (`get_permissions`) REFUSE un Viewer et un Admin RH (rôle sans code
d'écriture du module). Une nouvelle action mal rangée dans la liste des
lectures fait échouer la CI en NOMMANT l'action.

Le passif GELÉ ci-dessous ne peut que décroître : une entrée qui n'est plus
acceptée doit être retirée (le test échoue sinon).

Complément DONNÉES : un Technicien de portée équipe ne voit, dans les vues
agrégées `calendrier` et `gantt`, aucun id absent de sa liste.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht79_balai_permissions"
"""
import datetime

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.request import Request
from rest_framework.test import (
    APIClient, APIRequestFactory, force_authenticate,
)
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import Installation, Intervention
from apps.installations.urls import router as router_installations
from apps.outillage.urls import router as router_outillage
from apps.roles.models import Role
from apps.roles.permissions_registre import (
    ADMIN_RH_PERMISSIONS, CANONICAL_SYSTEM_ROLES, TECHNICIEN_PERMISSIONS,
    VIEWER_PERMISSIONS,
)

User = get_user_model()
SAFE = ('GET', 'HEAD', 'OPTIONS')
STD = {'create': 'POST', 'update': 'PUT', 'partial_update': 'PATCH',
       'destroy': 'DELETE'}

#: PASSIF GELÉ (cliquet décroissant) : (viewset, action, méthode) → raison.
#: Écritures acceptées à un Viewer / Admin RH, assumées et documentées.
PASSIF_ECRITURES = {
    ('InterventionViewSet', 'suggerer_creneau', 'POST'):
        "calcul en LECTURE SEULE (XFSM2) : POST uniquement pour porter les "
        "paramètres, ne mute rien",
    ('PositionTechnicienViewSet', 'ping', 'POST'):
        "chaque utilisateur interne pose SA PROPRE position (XFSM23, "
        "consentement GPS vérifié côté service), jamais celle d'un autre",
}

#: Agrégats nominatifs NON balayés côté données (passif nommé, ACHT50 → suite) :
#: ils lisent toujours `Intervention.objects` brut et restent à ranger sur
#: `get_queryset()` ; la garde (2) ci-dessus ne les concerne pas (GET).
AGREGATS_NON_BALAYES = (
    'plan-de-charge', 'conflits-affectation', 'nivellement-charge',
    'planning-camionnettes', 'taux-ponctualite',
)


def _utilisateur(nom, permissions):
    """Utilisateur EN MÉMOIRE (aucune base) porteur d'un rôle fin."""
    role = Role(nom=nom, permissions=list(permissions))
    role.pk = 9000
    user = User(username=nom.lower().replace(' ', '-'), company_id=1)
    user.role = role
    user.role_id = 9000
    return user


def _actions_ecriture(viewset):
    sorties = [(nom, methode) for nom, methode in STD.items()
               if hasattr(viewset, nom)]
    for extra in viewset.get_extra_actions():
        for methode in extra.mapping:
            if methode.upper() not in SAFE:
                sorties.append((extra.__name__, methode.upper()))
    return sorties


def _autorise(viewset, action, methode, user):
    django_request = APIRequestFactory().generic(methode, '/')
    force_authenticate(django_request, user=user)
    request = Request(django_request)
    view = viewset()
    view.action = action
    view.request = request
    view.kwargs = {}
    view.args = ()
    view.format_kwarg = None
    return all(p.has_permission(request, view) for p in view.get_permissions())


class BalaiPermissionsTests(SimpleTestCase):
    def test_ecritures_refusees_au_viewer_et_a_admin_rh(self):
        viewer = _utilisateur('Viewer', VIEWER_PERMISSIONS)
        rh = _utilisateur('Admin RH', ADMIN_RH_PERMISSIONS)
        acceptees = set()
        vues = 0
        for router in (router_installations, router_outillage):
            for _prefix, viewset, _basename in router.registry:
                vues += 1
                for action, methode in _actions_ecriture(viewset):
                    for user in (viewer, rh):
                        if _autorise(viewset, action, methode, user):
                            acceptees.add(
                                (viewset.__name__, action, methode))
        self.assertGreater(vues, 50)    # le balai voit bien tous les routeurs
        nouvelles = sorted(acceptees - set(PASSIF_ECRITURES))
        self.assertEqual(
            nouvelles, [],
            "Écriture acceptée à un Viewer / Admin RH — rangez l'action dans "
            "la branche ÉCRITURE de get_permissions (IsResponsableOrAdmin ou "
            f"code fin) : {nouvelles}")
        perimees = sorted(set(PASSIF_ECRITURES) - acceptees)
        self.assertEqual(
            perimees, [],
            f"Passif gelé périmé (cliquet) : retirez-le : {perimees}")


class FuiteListesTechnicienTests(TestCase):
    """(1) — un Technicien de portée équipe ne reçoit, des vues agrégées
    `calendrier` et `gantt`, aucun id absent de sa liste."""

    def setUp(self):
        self.company = Company.objects.create(nom='ACHT79', slug='acht79-co')
        role_tech = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        role_admin = Role.objects.create(
            company=self.company, nom='Administrateur',
            permissions=list(dict(CANONICAL_SYSTEM_ROLES)['Administrateur']))
        self.t1 = User.objects.create_user(
            username='t1-acht79', password='x', company=self.company,
            role=role_tech)
        self.t2 = User.objects.create_user(
            username='t2-acht79', password='x', company=self.company,
            role=role_tech)
        admin = User.objects.create_user(
            username='admin-acht79', password='x', company=self.company,
            role=role_admin)
        self.chantier = Installation.objects.create(
            company=self.company, reference='CH-ACHT79',
            technicien_responsable=admin, created_by=admin)
        jour = datetime.date.today() + datetime.timedelta(days=2)
        self.i1 = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.t1, date_prevue=jour)
        self.i2 = Intervention.objects.create(
            company=self.company, installation=self.chantier,
            type_intervention='pose', technicien=self.t2, date_prevue=jour)
        self.fenetre = {
            'date_from': str(jour - datetime.timedelta(days=1)),
            'date_to': str(jour + datetime.timedelta(days=1))}

    def test_calendrier_et_gantt_sans_fuite(self):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.t1)}')
        r = api.get('/api/django/installations/interventions/calendrier/',
                    self.fenetre)
        self.assertEqual(r.status_code, 200, r.data)
        ids = {iv['id'] for groupe in r.data
               for iv in groupe['interventions']}
        self.assertEqual(ids, {self.i1.id})
        r = api.get('/api/django/installations/chantiers/gantt/')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertNotIn(self.chantier.id, [row['id'] for row in r.data])
