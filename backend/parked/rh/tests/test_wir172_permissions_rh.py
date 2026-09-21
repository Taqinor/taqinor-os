"""WIR172 — permissions FINES du module RH (``rh_voir`` / ``rh_gerer``).

Constat corrigé : ``_RhBaseViewSet`` était gardé par le grossier
``IsResponsableOrAdmin``, qui passe dès qu'un rôle accorde UNE permission
d'écriture — même totalement hors RH. Un **Commercial** (``crm_creer``,
``ventes_creer``…) obtenait donc le CRUD complet des dossiers employés, des
sanctions et des visites médicales.

Ce que ce module PROUVE, par rôle, sur les trois surfaces nommées par la tâche
(``employes``, ``sanctions``, ``visites-medicales``) :

* un rôle Commercial (écritures CRM/Ventes, aucun code RH) → **403** ;
* un rôle portant SEULEMENT ``rh_voir`` → **200** en lecture, **403** en
  écriture ;
* un rôle portant ``rh_voir`` + ``rh_gerer`` → 200 en lecture et **jamais 403**
  en écriture ;
* le rôle **Responsable** — mandat RH réel, il porte déjà ``paie_voir``/
  ``paie_gerer`` (XPAI7) — garde son accès historique complet ;
* un compte **LÉGACY** sans rôle fin (``role_legacy=responsable``) garde
  exactement son accès historique (lecture ET écriture) ;
* les **trois exceptions** d'élargissement (``compa-ratio`` gaté
  ``salaires_voir``, ``annuaire`` et ``localisation-du-jour`` gatés
  ``IsAnyRole``) restent atteignables sans aucun code RH ;
* le catalogue de rôles est cohérent : les deux codes existent, Directeur /
  Admin RH (NTADM20) / Responsable les portent, Commercial/Technicien/Viewer
  non — ces trois-là n'obtenaient l'accès que par effet de bord d'une écriture
  ailleurs, exactement le trou fermé ici.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.rh.models import DossierEmploye
from apps.roles.models import (
    ADMIN_RH_PERMISSIONS,
    ALL_PERMISSIONS,
    COMMERCIAL_PERMISSIONS,
    DIRECTEUR_PERMISSIONS,
    RESPONSABLE_PERMISSIONS,
    Role,
    TECHNICIEN_PERMISSIONS,
    VIEWER_PERMISSIONS,
)

User = get_user_model()

EMPLOYES = '/api/django/rh/employes/'
SANCTIONS = '/api/django/rh/sanctions/'
VISITES = '/api/django/rh/visites-medicales/'
SURFACES = (EMPLOYES, SANCTIONS, VISITES)


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _RhPermissionsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='WIR172 Co', slug='wir172-co')

    def _user(self, suffix, perms=None, role_legacy=None):
        """Utilisateur de la société de test.

        ``perms=None`` ⇒ AUCUN rôle fin (compte légacy) ; sinon un ``Role``
        portant exactement ``perms``.
        """
        role = None
        if perms is not None:
            role = Role.objects.create(
                company=self.company, nom=f'wir172-{suffix}',
                permissions=list(perms))
        kwargs = {}
        if role_legacy is not None:
            kwargs['role_legacy'] = role_legacy
        return User.objects.create_user(
            username=f'wir172-{suffix}', password='x', role=role,
            company=self.company, **kwargs)


class RhFineGrainedAccessTests(_RhPermissionsBase):
    """Allow/deny par rôle sur les trois surfaces nommées par WIR172."""

    def test_commercial_refuse_partout(self):
        """LE BUG : un Commercial n'a aucun code RH → 403, plus jamais 200."""
        user = self._user('commercial', perms=COMMERCIAL_PERMISSIONS)
        # Garde-fou : ce rôle porte bien des écritures (il passait donc
        # l'ancien IsResponsableOrAdmin) — sinon le test serait vert pour la
        # mauvaise raison.
        self.assertTrue(user.is_responsable)
        client = _auth(user)
        for path in SURFACES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 403)
                self.assertEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_technicien_et_viewer_refuses(self):
        """Même verrou pour Technicien et Viewer (aucun code RH non plus)."""
        for nom, perms in (('technicien', TECHNICIEN_PERMISSIONS),
                           ('viewer', VIEWER_PERMISSIONS)):
            client = _auth(self._user(nom, perms=perms))
            for path in SURFACES:
                with self.subTest(role=nom, path=path):
                    self.assertEqual(client.get(path).status_code, 403)

    def test_responsable_garde_son_acces_historique(self):
        """Le rôle « Responsable » avait l'accès RH complet et le CONSERVE.

        Même raison que ``paie_voir``/``paie_gerer`` déjà portés par ce preset
        (XPAI7) : c'est un mandat RH réel, pas l'effet de bord d'une écriture
        ailleurs — le resserrement WIR172 vise Commercial/Technicien/Viewer.
        """
        client = _auth(self._user('responsable', perms=RESPONSABLE_PERMISSIONS))
        for path in SURFACES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)
                self.assertNotEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_rh_voir_seul_lit_mais_n_ecrit_pas(self):
        client = _auth(self._user('lecteur', perms=['rh_voir']))
        for path in SURFACES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)
                self.assertEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_rh_gerer_lit_et_ecrit(self):
        client = _auth(
            self._user('gestion', perms=['rh_voir', 'rh_gerer']))
        for path in SURFACES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)
                # Jamais 403 : le POST minimal peut échouer en 400 de
                # validation métier, jamais sur la permission.
                self.assertNotEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_creation_reelle_avec_rh_gerer(self):
        """Bout en bout : ``rh_gerer`` crée réellement un dossier employé."""
        client = _auth(
            self._user('createur', perms=['rh_voir', 'rh_gerer']))
        resp = client.post(
            EMPLOYES,
            {'matricule': 'WIR172-1', 'nom': 'Alaoui', 'prenom': 'Salma'},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        # Multi-tenant : la société est posée CÔTÉ SERVEUR.
        self.assertEqual(
            DossierEmploye.objects.get(id=resp.data['id']).company,
            self.company)

    def test_compte_legacy_garde_son_acces_historique(self):
        """Compte SANS rôle fin : repli ``_user_has_or_legacy`` intact."""
        client = _auth(self._user(
            'legacy', perms=None,
            role_legacy=CustomUser.ROLE_RESPONSABLE))
        for path in SURFACES:
            with self.subTest(path=path):
                self.assertEqual(client.get(path).status_code, 200)
                self.assertNotEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_compte_legacy_normal_reste_refuse(self):
        """Un compte légacy « normal » n'avait pas l'accès : toujours pas."""
        client = _auth(self._user(
            'legacy-normal', perms=None, role_legacy=CustomUser.ROLE_NORMAL))
        self.assertEqual(client.get(EMPLOYES).status_code, 403)

    def test_anonyme_refuse(self):
        self.assertIn(APIClient().get(EMPLOYES).status_code, (401, 403))


class RhExceptionsPreserveesTests(_RhPermissionsBase):
    """Les 3 élargissements existants ne sont PAS refermés par WIR172."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.dossier = DossierEmploye.objects.create(
            company=cls.company, matricule='WIR172-EX', nom='N', prenom='P')

    def test_annuaire_ouvert_a_tout_interne(self):
        """XRH28 — ``IsAnyRole`` : aucun code RH requis."""
        client = _auth(self._user('annuaire', perms=['crm_voir']))
        resp = client.get(f'{EMPLOYES}annuaire/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_localisation_du_jour_ouverte_a_tout_interne(self):
        """ZRH16 — ``IsAnyRole`` : aucun code RH requis."""
        client = _auth(self._user('localisation', perms=['crm_voir']))
        resp = client.get(f'{EMPLOYES}localisation-du-jour/')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_compa_ratio_reste_gate_par_salaires_voir(self):
        """XRH16 — ``salaires_voir`` SEUL suffit (et rien d'autre ne passe)."""
        lecteur_paie = self._user('compa-paie', perms=['salaires_voir'])
        resp = _auth(lecteur_paie).get(
            f'{EMPLOYES}{self.dossier.id}/compa-ratio/')
        # 200 ou 404 (« pas de grille salariale ») — jamais 403.
        self.assertNotEqual(resp.status_code, 403)

        # Un porteur de rh_voir/rh_gerer SANS salaires_voir reste bloqué :
        # la donnée de rémunération ne s'ouvre pas avec le module RH.
        rh = self._user('compa-rh', perms=['rh_voir', 'rh_gerer'])
        self.assertEqual(
            _auth(rh).get(
                f'{EMPLOYES}{self.dossier.id}/compa-ratio/').status_code,
            403)


class RhCatalogueRolesTests(TestCase):
    """Le catalogue déclare les deux codes et les distribue correctement."""

    def test_codes_au_catalogue(self):
        self.assertIn('rh_voir', ALL_PERMISSIONS)
        self.assertIn('rh_gerer', ALL_PERMISSIONS)

    def test_roles_a_mandat_rh_les_portent(self):
        """Directeur, Admin RH (NTADM20) et Responsable — accès historique."""
        for nom, perms in (('directeur', DIRECTEUR_PERMISSIONS),
                           ('admin-rh', ADMIN_RH_PERMISSIONS),
                           ('responsable', RESPONSABLE_PERMISSIONS)):
            for code in ('rh_voir', 'rh_gerer'):
                with self.subTest(role=nom, code=code):
                    self.assertIn(code, perms)

    def test_le_responsable_garde_rh_comme_il_garde_la_paie(self):
        """Cohérence : couper les dossiers RH en laissant la PAIE (donnée plus
        sensible) au même preset serait incohérent."""
        self.assertIn('paie_gerer', RESPONSABLE_PERMISSIONS)
        self.assertIn('rh_gerer', RESPONSABLE_PERMISSIONS)

    def test_roles_non_rh_ne_les_portent_pas(self):
        for nom, perms in (('commercial', COMMERCIAL_PERMISSIONS),
                           ('technicien', TECHNICIEN_PERMISSIONS),
                           ('viewer', VIEWER_PERMISSIONS)):
            for code in ('rh_voir', 'rh_gerer'):
                with self.subTest(role=nom, code=code):
                    self.assertNotIn(code, perms)
