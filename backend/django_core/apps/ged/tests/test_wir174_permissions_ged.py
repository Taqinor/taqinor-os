"""WIR174 — gouvernance documentaire GED réservée à la direction.

Constat corrigé : le caviardage DÉFINITIF, la rétention légale (legal hold) et
les politiques de rétention n'étaient gardés que par ``IsResponsableOrAdmin`` —
c'est-à-dire par TOUT porteur d'une écriture, même totalement hors GED. Un
Technicien (``sav_gerer``, ``installation_gerer``…) pouvait geler, dégeler ou
caviarder n'importe quel document de la société.

Ce que ce module PROUVE :

* un **Technicien** reçoit **403** sur les trois actions de gouvernance
  (``placer-legal-hold``, ``lever-legal-hold``, ``caviarder``) — et aussi sur
  les DEUX routes équivalentes (``POST /legal-holds/``, ``POST
  /politiques-retention/``), sinon la garde se contournerait par une autre URL ;
* le même Technicien **garde** la liste, la recherche et le téléchargement ZIP
  (les branches ``IsAnyRole`` du contrat GED37 ne sont pas refermées) ;
* ``ged_gerer`` SANS ``ged_gouvernance`` → 403 sur la gouvernance, mais écrit
  toujours un document ordinaire ;
* ``ged_gouvernance`` passe ;
* la **défense en profondeur** côté service : ``services.placer_legal_hold`` /
  ``lever_legal_hold`` lèvent ``PermissionError`` pour un porteur sans le code,
  même appelées hors HTTP ;
* un compte **LÉGACY** (sans rôle fin) est inchangé ;
* l'**ACL coffre-fort** (GED8) est inchangée.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.ged import services
from apps.ged.models import Cabinet, Coffre, Document, Folder, LegalHold
from apps.roles.models import (
    ADMIN_RH_PERMISSIONS, ADMIN_VENTES_PERMISSIONS, ALL_PERMISSIONS,
    COMMERCIAL_PERMISSIONS, COMMERCIAL_RESP_PERMISSIONS,
    DIRECTEUR_PERMISSIONS, ELEVATED_PERMISSIONS, RESPONSABLE_PERMISSIONS,
    Role, TECHNICIEN_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS,
    VIEWER_PERMISSIONS,
)

User = get_user_model()

BASE = '/api/django/ged'

GED_VOIR = 'ged_voir'
GED_GERER = 'ged_gerer'
GED_GOUVERNANCE = 'ged_gouvernance'


def _auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class _GedGouvernanceBase(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='WIR174 Co', slug='wir174-co')
        self.cabinet = Cabinet.objects.create(company=self.company, nom='Docs')
        self.folder = Folder.objects.create(
            company=self.company, cabinet=self.cabinet, nom='Dossier')
        self.doc = Document.objects.create(
            company=self.company, folder=self.folder, nom='Contrat')

    def _user(self, suffix, perms=None, role_legacy=None):
        role = None
        if perms is not None:
            role = Role.objects.create(
                company=self.company, nom=f'wir174-{suffix}',
                permissions=list(perms))
        kwargs = {}
        if role_legacy is not None:
            kwargs['role_legacy'] = role_legacy
        return User.objects.create_user(
            username=f'wir174-{suffix}', password='x', role=role,
            company=self.company, **kwargs)

    def _routes_gouvernance(self):
        return (
            f'{BASE}/documents/{self.doc.pk}/placer-legal-hold/',
            f'{BASE}/documents/{self.doc.pk}/lever-legal-hold/',
            f'{BASE}/documents/{self.doc.pk}/caviarder/',
        )


class GouvernanceRefuseeHorsDirectionTests(_GedGouvernanceBase):
    """LE BUG : un Technicien gelait/caviardait n'importe quel document."""

    def test_technicien_403_sur_les_trois_actions(self):
        technicien = self._user('technicien', perms=TECHNICIEN_PERMISSIONS)
        # Garde-fou : ce rôle porte bien des écritures — il passait donc
        # l'ancien IsResponsableOrAdmin.
        self.assertTrue(technicien.is_responsable)
        client = _auth(technicien)
        for path in self._routes_gouvernance():
            with self.subTest(path=path):
                self.assertEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_technicien_403_sur_les_routes_equivalentes(self):
        """Poser un hold / écrire une politique par l'autre URL : même 403."""
        client = _auth(self._user('technicien-bis', perms=TECHNICIEN_PERMISSIONS))
        self.assertEqual(
            client.post(f'{BASE}/legal-holds/',
                        {'document': self.doc.pk}, format='json').status_code,
            403)
        self.assertEqual(
            client.post(f'{BASE}/politiques-retention/',
                        {'nom': 'Purge', 'duree_conservation_jours': 30},
                        format='json').status_code,
            403)

    def test_technicien_garde_liste_recherche_et_zip(self):
        """Les branches IsAnyRole (contrat GED37) ne sont PAS refermées."""
        client = _auth(self._user('technicien-lecture',
                                  perms=TECHNICIEN_PERMISSIONS))
        self.assertEqual(client.get(f'{BASE}/documents/').status_code, 200)
        self.assertEqual(
            client.get(f'{BASE}/documents/recherche/', {'q': 'Contrat'})
            .status_code, 200)
        zip_resp = client.post(
            f'{BASE}/documents/operations-lot/',
            {'operation': 'telecharger_zip', 'documents': [self.doc.pk]},
            format='json')
        self.assertNotEqual(zip_resp.status_code, 403)

    def test_viewer_garde_la_lecture(self):
        client = _auth(self._user('viewer', perms=VIEWER_PERMISSIONS))
        self.assertEqual(client.get(f'{BASE}/documents/').status_code, 200)
        self.assertEqual(
            client.post(self._routes_gouvernance()[0], {},
                        format='json').status_code, 403)

    def test_ged_gerer_sans_gouvernance_403_sur_la_gouvernance(self):
        client = _auth(self._user('gerer', perms=[GED_VOIR, GED_GERER]))
        for path in self._routes_gouvernance():
            with self.subTest(path=path):
                self.assertEqual(
                    client.post(path, {}, format='json').status_code, 403)

    def test_ged_gerer_ecrit_toujours_un_document(self):
        """L'écriture documentaire COURANTE reste ouverte à ``ged_gerer``."""
        client = _auth(self._user('gerer-write', perms=[GED_VOIR, GED_GERER]))
        resp = client.post(
            f'{BASE}/documents/',
            {'nom': 'Nouveau', 'folder': self.folder.pk}, format='json')
        self.assertNotEqual(resp.status_code, 403, resp.data)

    def test_admins_delegues_ecrivent_toujours_mais_pas_la_gouvernance(self):
        """NTADM20 — Admin RH / Admin Ventes portaient déjà une écriture, donc
        l'ancien gate GED : ils gardent l'écriture documentaire courante et
        n'obtiennent PAS la gouvernance."""
        for nom, perms in (('admin-rh', ADMIN_RH_PERMISSIONS),
                           ('admin-ventes', ADMIN_VENTES_PERMISSIONS)):
            client = _auth(self._user(nom, perms=perms))
            with self.subTest(role=nom):
                ecriture = client.post(
                    f'{BASE}/documents/',
                    {'nom': f'Doc {nom}', 'folder': self.folder.pk},
                    format='json')
                self.assertNotEqual(ecriture.status_code, 403, ecriture.data)
                self.assertEqual(
                    client.post(self._routes_gouvernance()[0], {},
                                format='json').status_code, 403)

    def test_ged_gouvernance_passe(self):
        client = _auth(self._user(
            'gouvernance', perms=[GED_VOIR, GED_GERER, GED_GOUVERNANCE]))
        resp = client.post(
            f'{BASE}/documents/{self.doc.pk}/placer-legal-hold/',
            {'motif': 'Litige'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            LegalHold.objects.filter(document=self.doc, actif=True).exists())
        # La levée aussi.
        leve = client.post(
            f'{BASE}/documents/{self.doc.pk}/lever-legal-hold/', {},
            format='json')
        self.assertEqual(leve.status_code, 200, leve.data)

    def test_compte_legacy_inchange(self):
        """Compte SANS rôle fin (palier admin) : accès historique préservé."""
        client = _auth(self._user(
            'legacy', perms=None, role_legacy=CustomUser.ROLE_ADMIN))
        resp = client.post(
            f'{BASE}/documents/{self.doc.pk}/placer-legal-hold/', {},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)


class DefenseEnProfondeurServiceTests(_GedGouvernanceBase):
    """La garde ne vit pas QUE dans la vue : le service refuse aussi."""

    def test_placer_refuse_sans_gouvernance(self):
        technicien = self._user('svc-technicien', perms=TECHNICIEN_PERMISSIONS)
        with self.assertRaises(PermissionError):
            services.placer_legal_hold(self.doc, user=technicien)
        self.assertFalse(LegalHold.objects.filter(document=self.doc).exists())

    def test_lever_refuse_sans_gouvernance(self):
        directeur = self._user('svc-directeur', perms=DIRECTEUR_PERMISSIONS)
        services.placer_legal_hold(self.doc, user=directeur)
        technicien = self._user('svc-technicien-2',
                                perms=TECHNICIEN_PERMISSIONS)
        with self.assertRaises(PermissionError):
            services.lever_legal_hold(self.doc, user=technicien)
        self.assertTrue(
            LegalHold.objects.filter(document=self.doc, actif=True).exists())

    def test_gouvernance_et_legacy_passent(self):
        porteur = self._user('svc-gouv', perms=[GED_GOUVERNANCE])
        hold = services.placer_legal_hold(self.doc, user=porteur)
        self.assertTrue(hold.actif)
        legacy = self._user(
            'svc-legacy', perms=None, role_legacy=CustomUser.ROLE_ADMIN)
        self.assertEqual(
            services.lever_legal_hold(self.doc, user=legacy), 1)


class AclCoffreFortInchangeeTests(_GedGouvernanceBase):
    """GED8 — WIR174 ne touche pas au filtrage du queryset."""

    def test_document_en_coffre_invisible_au_non_proprietaire(self):
        proprietaire = self._user('coffre-owner', perms=[GED_VOIR, GED_GERER])
        coffre = Coffre.objects.create(
            company=self.company, nom='Confidentiel',
            proprietaire=proprietaire)
        secret = Document.objects.create(
            company=self.company, folder=self.folder, coffre=coffre,
            nom='Secret')
        autre = self._user('coffre-autre', perms=[GED_VOIR, GED_GERER])
        resp = _auth(autre).get(f'{BASE}/documents/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        rows = data['results'] if isinstance(data, dict) and 'results' in data \
            else data
        self.assertNotIn(secret.pk, [r['id'] for r in rows])
        # Le propriétaire, lui, le voit toujours.
        resp_owner = _auth(proprietaire).get(f'{BASE}/documents/')
        data_o = resp_owner.data
        rows_o = data_o['results'] \
            if isinstance(data_o, dict) and 'results' in data_o else data_o
        self.assertIn(secret.pk, [r['id'] for r in rows_o])


class GedCatalogueTests(TestCase):
    """Les 3 codes sont enregistrés et distribués selon leur palier."""

    def test_codes_au_catalogue(self):
        for code in (GED_VOIR, GED_GERER, GED_GOUVERNANCE):
            with self.subTest(code=code):
                self.assertIn(code, ALL_PERMISSIONS)

    # Tous les presets qui portaient DÉJÀ une écriture (donc ``is_responsable``
    # vrai, donc l'ancien ``IsResponsableOrAdmin`` de la GED satisfait) — y
    # compris les DEUX administrateurs délégués NTADM20, dont l'omission serait
    # une régression silencieuse de l'écriture documentaire courante.
    PRESETS_ECRIVAINS = {
        'Responsable': RESPONSABLE_PERMISSIONS,
        'Commercial responsable': COMMERCIAL_RESP_PERMISSIONS,
        'Commercial': COMMERCIAL_PERMISSIONS,
        'Technicien responsable': TECHNICIEN_RESP_PERMISSIONS,
        'Technicien': TECHNICIEN_PERMISSIONS,
        'Admin RH': ADMIN_RH_PERMISSIONS,
        'Admin Ventes': ADMIN_VENTES_PERMISSIONS,
    }

    def test_gouvernance_est_direction_seule(self):
        self.assertIn(GED_GOUVERNANCE, DIRECTEUR_PERMISSIONS)
        self.assertNotIn(GED_GOUVERNANCE, VIEWER_PERMISSIONS)
        # AUCUN preset non-direction ne la porte (délégués NTADM20 inclus).
        for nom, perms in self.PRESETS_ECRIVAINS.items():
            with self.subTest(role=nom):
                self.assertNotIn(GED_GOUVERNANCE, perms)
        # ÉLEVÉE : un non-administrateur ne peut pas se l'octroyer.
        self.assertIn(GED_GOUVERNANCE, ELEVATED_PERMISSIONS)

    def test_ecriture_courante_preservee_pour_les_roles_metier(self):
        """INVARIANT WIR174 : aucun accès d'écriture COURANTE n'est retiré.

        Tout preset qui accordait déjà une écriture passait ``is_responsable``,
        donc l'ancien gate GED — il DOIT garder ``ged_voir``+``ged_gerer``.
        """
        for nom, perms in self.PRESETS_ECRIVAINS.items():
            with self.subTest(role=nom):
                self.assertIn(GED_VOIR, perms)
                self.assertIn(GED_GERER, perms)
        # Le Viewer reste en lecture seule.
        self.assertIn(GED_VOIR, VIEWER_PERMISSIONS)
        self.assertNotIn(GED_GERER, VIEWER_PERMISSIONS)
