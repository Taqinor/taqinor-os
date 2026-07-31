"""Verrouille la correspondance entre le kwarg ``permission_classes`` de chaque
``@action`` de ``PaiementViewSet`` et le tier RÉELLEMENT appliqué par
``get_permissions()`` — le trou RBAC réel refermé ci-dessous.

Contexte du bug (voir ``core/permissions.py::declared_action_permissions`` et
le commentaire dans ``apps/ventes/views/paiement.py::PaiementViewSet.
get_permissions``) : l'ancienne surcharge ne consultait JAMAIS
``self.permission_classes`` — elle branchait uniquement sur ``self.action``
via un ``if/else`` en dur (``enregistrer_avance``/``ventiler``/``rejeter`` →
``IsResponsableOrAdmin`` ; tout le reste → ``IsAnyRole``). Trois ``@action``
d'ÉCRITURE déclaraient pourtant ``permission_classes=[IsResponsableOrAdmin]``
sur leur décorateur (``paiement_avec_retenue``, ``attestation_recue``,
``envoyer_recu``) mais retombaient SILENCIEUSEMENT sur ``IsAnyRole`` : le kwarg
du décorateur était du code mort et n'importe quel rôle authentifié pouvait
solder une facture via une retenue à la source, cocher la réception d'une
attestation RAS, ou envoyer une quittance au client.

Le correctif ajoute une première ligne à ``get_permissions()`` :
``declared_action_permissions(self)`` — qui respecte le ``permission_classes``
déclaré par l'``@action`` elle-même quand il existe. Trois niveaux de preuve :

1. ``PaiementActionPermissionTierTests`` — test générique (même forme que
   ``apps/sav/tests_ticket_action_permissions.py``) : chaque ``@action`` à
   ``permission_classes`` déclaré doit obtenir EXACTEMENT ce tier via
   ``get_permissions()``. Attrape aussi toute FUTURE ``@action`` ajoutée sans
   mise à jour de ``get_permissions()``.
2. ``PaiementActionRoleGateHTTPTests`` — appels HTTP réels (``APIClient``) :
   un rôle authentifié NON-responsable reçoit désormais 403 sur les actions
   tightened (c'est le trou refermé — il passait avant) ; un Responsable/Admin
   n'est jamais bloqué ; un appel non-authentifié reçoit 401/403.
3. ``PaiementActionCompanyScopingTests`` — le scoping multi-tenant reste
   intact : un Responsable de la société B ne peut jamais agir sur un
   paiement/facture/retenue de la société A (404, jamais 200).
"""
import inspect
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement, RetenueSubie
from apps.ventes.views import PaiementViewSet

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_company(slug, nom):
    return Company.objects.create(nom=nom, slug=slug)


def make_client(company, email):
    return Client.objects.create(
        company=company, nom='Retenue', prenom='Client',
        email=email, telephone='+212600000099', adresse='Casablanca',
    )


def _action_methods():
    """Toutes les méthodes ``@action`` de ``PaiementViewSet`` (marquées par
    DRF avec un attribut ``mapping``) portant un ``permission_classes``
    explicite sur le décorateur."""
    out = {}
    for name, method in inspect.getmembers(PaiementViewSet, inspect.isfunction):
        if not hasattr(method, 'mapping'):
            continue  # pas une @action
        declared = (getattr(method, 'kwargs', {}) or {}).get('permission_classes')
        if declared:
            out[name] = declared
    return out


def _tier_name(action):
    view = PaiementViewSet()
    view.action = action
    perms = view.get_permissions()
    assert len(perms) == 1, f"{action}: {len(perms)} permission(s)"
    return type(perms[0]).__name__


class PaiementActionPermissionTierTests(TestCase):
    def test_get_permissions_honors_every_declared_action(self):
        """Chaque @action à permission_classes déclaré doit obtenir, via
        get_permissions(), le MÊME tier que son décorateur annonce — jamais
        un tiering if/else qui l'écrase en silence."""
        decorated = _action_methods()
        self.assertTrue(
            decorated, "aucune @action à permission_classes détectée sur "
            "PaiementViewSet — test cassé ?")
        for name, declared in decorated.items():
            with self.subTest(action=name):
                expected = declared[0].__name__
                actual = _tier_name(name)
                self.assertEqual(
                    actual, expected,
                    f"@action '{name}' déclare {expected} mais "
                    f"get_permissions() renvoie {actual} — le kwarg "
                    f"permission_classes= du décorateur est ignoré par "
                    f"PaiementViewSet.get_permissions().")

    def test_previously_broken_write_actions_now_responsable_or_admin(self):
        """Régression explicite (le trou refermé) : ces trois écritures
        déclaraient IsResponsableOrAdmin mais retombaient sur IsAnyRole avant
        le correctif — n'importe quel rôle authentifié pouvait les appeler."""
        for name in ('paiement_avec_retenue', 'attestation_recue',
                     'envoyer_recu'):
            with self.subTest(action=name):
                self.assertEqual(_tier_name(name), 'IsResponsableOrAdmin')

    def test_recu_pdf_stays_is_any_role(self):
        """Le durcissement ne doit PAS sur-restreindre : recu-pdf déclare
        IsAnyRole et doit rester à IsAnyRole (preuve que le correctif ne
        touche que ce qu'il doit)."""
        self.assertEqual(_tier_name('recu_pdf'), 'IsAnyRole')


class PaiementActionRoleGateHTTPTests(TestCase):
    """Preuve HTTP réelle (APIClient) du tiering par-action sur les deux
    actions les plus sensibles (soldent une facture / envoient un email
    client). Un rôle authentifié NON-responsable (role_legacy par défaut =
    'normal', comme un compte Commercial/Technicien) recevait AVANT le
    correctif un accès complet à ces écritures — c'est exactement le trou
    refermé."""

    def setUp(self):
        self.company = make_company('xfacperm-co', 'XFACPERM Co')
        self.client_obj = make_client(self.company, 'xfacperm@example.com')
        # Rôle authentifié NON-responsable : is_authenticated True,
        # is_responsable False (role_legacy='normal' par défaut).
        self.commercial = User.objects.create_user(
            username='xfacperm_com', password='x', company=self.company,
        )
        self.responsable = User.objects.create_user(
            username='xfacperm_resp', password='x',
            role_legacy='responsable', company=self.company,
        )
        self.api_commercial = _auth(self.commercial)
        self.api_responsable = _auth(self.responsable)
        self.anon = APIClient()

    def _facture(self, n, montant_ttc='5000'):
        return Facture.objects.create(
            company=self.company, reference=f'FAC-{MONTH}-{n:04d}',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal(montant_ttc), created_by=self.responsable,
        )

    def _paiement(self, facture):
        return Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('1000'),
            date_paiement=timezone.now().date(), mode='virement',
            created_by=self.responsable,
        )

    def _retenue(self, facture):
        return RetenueSubie.objects.create(
            company=self.company, facture=facture,
            type_retenue=RetenueSubie.TypeRetenue.RAS_TVA,
            taux=Decimal('10'), base=Decimal('500'), montant=Decimal('50'),
        )

    def _retenue_payload(self):
        return {
            'montant': '2000', 'date_paiement': str(timezone.now().date()),
            'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '10',
        }

    # ── envoyer-recu (POST, envoie un email — backend console en test,
    #    aucun appel réseau, comportement identique à test_xfac9) ─────────

    def test_envoyer_recu_commercial_gets_403(self):
        paiement = self._paiement(self._facture(1))
        r = self.api_commercial.post(
            f'/api/django/ventes/paiements/{paiement.id}/envoyer-recu/',
            {}, format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_envoyer_recu_responsable_not_blocked(self):
        paiement = self._paiement(self._facture(2))
        r = self.api_responsable.post(
            f'/api/django/ventes/paiements/{paiement.id}/envoyer-recu/',
            {}, format='json')
        self.assertNotEqual(r.status_code, 403, r.data)

    def test_envoyer_recu_unauthenticated_gets_401_or_403(self):
        paiement = self._paiement(self._facture(3))
        r = self.anon.post(
            f'/api/django/ventes/paiements/{paiement.id}/envoyer-recu/',
            {}, format='json')
        self.assertIn(r.status_code, (401, 403))

    # ── paiement-avec-retenue (POST, solde une facture) ──────────────────

    def test_paiement_avec_retenue_commercial_gets_403(self):
        facture = self._facture(4)
        r = self.api_commercial.post(
            f'/api/django/ventes/paiements/factures/{facture.id}/'
            'paiement-avec-retenue/', self._retenue_payload(), format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_paiement_avec_retenue_responsable_not_blocked(self):
        facture = self._facture(5)
        r = self.api_responsable.post(
            f'/api/django/ventes/paiements/factures/{facture.id}/'
            'paiement-avec-retenue/', self._retenue_payload(), format='json')
        self.assertNotEqual(r.status_code, 403, r.data)

    def test_paiement_avec_retenue_unauthenticated_gets_401_or_403(self):
        facture = self._facture(6)
        r = self.anon.post(
            f'/api/django/ventes/paiements/factures/{facture.id}/'
            'paiement-avec-retenue/', self._retenue_payload(), format='json')
        self.assertIn(r.status_code, (401, 403))

    # ── attestation-recue (troisième action tightened) ───────────────────

    def test_attestation_recue_commercial_gets_403(self):
        retenue = self._retenue(self._facture(7))
        r = self.api_commercial.post(
            f'/api/django/ventes/paiements/retenues/{retenue.id}/'
            'attestation-recue/', {}, format='json')
        self.assertEqual(r.status_code, 403, r.data)

    def test_attestation_recue_responsable_not_blocked(self):
        retenue = self._retenue(self._facture(8))
        r = self.api_responsable.post(
            f'/api/django/ventes/paiements/retenues/{retenue.id}/'
            'attestation-recue/', {}, format='json')
        self.assertNotEqual(r.status_code, 403, r.data)

    def test_attestation_recue_unauthenticated_gets_401_or_403(self):
        retenue = self._retenue(self._facture(9))
        r = self.anon.post(
            f'/api/django/ventes/paiements/retenues/{retenue.id}/'
            'attestation-recue/', {}, format='json')
        self.assertIn(r.status_code, (401, 403))


class PaiementActionCompanyScopingTests(TestCase):
    """Multi-tenant : un Responsable passe la garde IsResponsableOrAdmin (elle
    ne regarde pas la société) mais le scoping objet par société doit encore
    lui refuser l'accès à un paiement/facture/retenue d'UNE AUTRE société —
    404, jamais 200. Prouve que le durcissement RBAC n'a pas affaibli le
    scoping tenant déjà en place (_company_qs)."""

    def setUp(self):
        self.company_a = make_company('xfacperm-a', 'XFACPERM A')
        self.company_b = make_company('xfacperm-b', 'XFACPERM B')
        self.client_a = make_client(self.company_a, 'xfacperm-a@example.com')
        self.resp_a = User.objects.create_user(
            username='xfacperm_resp_a', password='x',
            role_legacy='responsable', company=self.company_a,
        )
        self.resp_b = User.objects.create_user(
            username='xfacperm_resp_b', password='x',
            role_legacy='responsable', company=self.company_b,
        )
        self.api_resp_b = _auth(self.resp_b)

        self.facture_a = Facture.objects.create(
            company=self.company_a, reference=f'FAC-{MONTH}-9001',
            client=self.client_a, statut=Facture.Statut.EMISE,
            montant_ht=Decimal('4166.67'), montant_tva=Decimal('833.33'),
            montant_ttc=Decimal('5000'), created_by=self.resp_a,
        )
        self.paiement_a = Paiement.objects.create(
            company=self.company_a, facture=self.facture_a,
            montant=Decimal('1000'), date_paiement=timezone.now().date(),
            mode='virement', created_by=self.resp_a,
        )
        self.retenue_a = RetenueSubie.objects.create(
            company=self.company_a, facture=self.facture_a,
            type_retenue=RetenueSubie.TypeRetenue.RAS_TVA,
            taux=Decimal('10'), base=Decimal('500'), montant=Decimal('50'),
        )

    def test_envoyer_recu_cross_company_paiement_404(self):
        r = self.api_resp_b.post(
            f'/api/django/ventes/paiements/{self.paiement_a.id}/'
            'envoyer-recu/', {}, format='json')
        self.assertEqual(r.status_code, 404, r.data)

    def test_paiement_avec_retenue_cross_company_facture_404(self):
        r = self.api_resp_b.post(
            f'/api/django/ventes/paiements/factures/{self.facture_a.id}/'
            'paiement-avec-retenue/',
            {'montant': '2000', 'date_paiement': str(timezone.now().date()),
             'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '10'},
            format='json')
        self.assertEqual(r.status_code, 404, r.data)

    def test_attestation_recue_cross_company_retenue_404(self):
        r = self.api_resp_b.post(
            f'/api/django/ventes/paiements/retenues/{self.retenue_a.id}/'
            'attestation-recue/', {}, format='json')
        self.assertEqual(r.status_code, 404, r.data)
