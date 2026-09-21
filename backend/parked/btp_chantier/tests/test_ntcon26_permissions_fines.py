"""NTCON26 — permissions FINES par geste engageant du module BTP.

Ce que le test PROUVE, code par code : un rôle FIN qui porte la lecture ET
l'écriture du module (``btp_voir`` + ``btp_gerer``) mais PAS le code fin reçoit
403 sur l'action correspondante, tout en lisant normalement le chantier — le
critère d'acceptation textuel de NTCON26. Le même rôle, une fois le code fin
ajouté, franchit la garde.

Deux non-régressions gardées ici aussi :
  * un compte HÉRITÉ (``role_legacy``, aucun ``Role`` FK) garde tout son accès
    (repli ``core.permissions._user_has_or_legacy``) — c'est ce que font tous
    les tests NTCON1-25 existants ;
  * les six codes sont RÉELLEMENT au catalogue ``roles.ALL_PERMISSIONS`` (sans
    quoi ``DIRECTEUR_PERMISSIONS`` n'en dériverait pas et le module répondrait
    403 à tout le monde — la classe de bug WIR169).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.btp_chantier.models import (
    AvenantChantier, DecompteGeneral, RFI, ReserveChantier, VisaDocument,
)
from apps.btp_chantier.permissions import PERMISSIONS_FINES_BTP
from apps.roles.models import (
    ALL_PERMISSIONS, DIRECTEUR_PERMISSIONS, RESPONSABLE_PERMISSIONS,
    TECHNICIEN_RESP_PERMISSIONS, Role,
)

from .helpers import auth, make_chantier, make_company, make_user

User = get_user_model()

RACINE = '/api/django/btp-chantier/'

#: Codes fins, dans l'ordre déclaré par ``permissions.PERMISSIONS_FINES_BTP``.
(PERM_RESERVE_CREER, PERM_RESERVE_LEVER, PERM_RFI_REPONDRE,
 PERM_VISA_APPROUVER, PERM_AVENANT_APPROUVER,
 PERM_DGD_FINALISER) = PERMISSIONS_FINES_BTP


class PermissionsFinesBtpTests(TestCase):
    """Le rôle de base porte btp_voir+btp_gerer et AUCUN code fin."""

    def setUp(self):
        self.co = make_company()
        self.chantier = make_chantier(self.co)
        self.legacy = make_user(self.co, role='responsable')

    # ── fabriques d'objets (créés hors API : la garde testée est l'action) ──
    def _reserve(self, statut=ReserveChantier.Statut.OUVERTE):
        return ReserveChantier.objects.create(
            company=self.co, chantier=self.chantier, lot='électricité',
            localisation_plan={'document_ged_id': 1, 'x': 0.2, 'y': 0.3},
            description='Prise à reprendre', gravite='majeure', statut=statut,
            created_by=self.legacy)

    def _rfi(self):
        from apps.btp_chantier import services
        return services.creer_rfi(
            company=self.co, chantier=self.chantier, pose_par=self.legacy,
            question='Quelle section de câble ?')

    def _visa(self):
        return VisaDocument.objects.create(
            company=self.co, chantier=self.chantier, document_ged_id=11,
            reference='VIS-1', statut=VisaDocument.Statut.SOUMIS,
            soumis_par=self.legacy, delai_revue_jours=7)

    def _avenant(self):
        return AvenantChantier.objects.create(
            company=self.co, chantier=self.chantier, reference='AV-1',
            description='Reprise de VRD', montant_ht=1000,
            statut=AvenantChantier.Statut.SOUMIS_CLIENT, cree_par=self.legacy)

    def _dgd(self):
        return DecompteGeneral.objects.create(
            company=self.co, chantier=self.chantier, reference='DGD-1',
            montant_marche_initial_ht=100000,
            statut=DecompteGeneral.Statut.NOTIFIE, cree_par=self.legacy)

    # ── utilitaires rôles ──────────────────────────────────────────────────
    def _api_avec(self, codes, username):
        role = Role.objects.create(
            company=self.co, nom=f'Rôle {username}', permissions=list(codes))
        user = User.objects.create_user(
            username=username, password='x', company=self.co, role=role)
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _api_module_seul(self, username):
        """btp_voir + btp_gerer, AUCUN code fin."""
        return self._api_avec(['btp_voir', 'btp_gerer'], username)

    # ── catalogue ──────────────────────────────────────────────────────────
    def test_les_six_codes_sont_au_catalogue(self):
        for code in PERMISSIONS_FINES_BTP:
            with self.subTest(code=code):
                self.assertIn(code, ALL_PERMISSIONS)
                # Dérivés du catalogue → le Directeur les porte.
                self.assertIn(code, DIRECTEUR_PERMISSIONS)

    def test_responsable_porte_les_six_codes(self):
        for code in PERMISSIONS_FINES_BTP:
            with self.subTest(code=code):
                self.assertIn(code, RESPONSABLE_PERMISSIONS)

    def test_technicien_responsable_sans_gestes_engageants(self):
        """Séparation des tâches : chantier oui, approbations non."""
        for code in (PERM_RESERVE_CREER, PERM_RESERVE_LEVER,
                     PERM_RFI_REPONDRE):
            self.assertIn(code, TECHNICIEN_RESP_PERMISSIONS)
        for code in (PERM_VISA_APPROUVER, PERM_AVENANT_APPROUVER,
                     PERM_DGD_FINALISER):
            self.assertNotIn(code, TECHNICIEN_RESP_PERMISSIONS)

    # ── la lecture reste ouverte (critère d'acceptation) ───────────────────
    def test_lecture_du_chantier_reste_ouverte_sans_code_fin(self):
        api = self._api_module_seul('ntcon26-lecture')
        for route in ('reserves-chantier/', 'rfi/', 'visas/',
                      'avenants-chantier/', 'decomptes-generaux/'):
            with self.subTest(route=route):
                self.assertEqual(
                    api.get(RACINE + route).status_code, status.HTTP_200_OK)

    # ── 403 par geste ──────────────────────────────────────────────────────
    def test_creation_reserve_refusee_sans_code(self):
        api = self._api_module_seul('ntcon26-res-creer')
        resp = api.post(RACINE + 'reserves-chantier/', {
            'chantier': self.chantier.id, 'lot': 'CVC',
            'localisation_plan': {'document_ged_id': 2, 'x': 0.1, 'y': 0.1},
            'description': 'Gaine à reprendre', 'gravite': 'mineure',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)

    def test_creation_reserve_acceptee_avec_code(self):
        api = self._api_avec(
            ['btp_voir', 'btp_gerer', PERM_RESERVE_CREER], 'ntcon26-res-ok')
        resp = api.post(RACINE + 'reserves-chantier/', {
            'chantier': self.chantier.id, 'lot': 'CVC',
            'localisation_plan': {'document_ged_id': 2, 'x': 0.1, 'y': 0.1},
            'description': 'Gaine à reprendre', 'gravite': 'mineure',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED,
                         resp.content)

    def test_levee_reserve_refusee_sans_code(self):
        reserve = self._reserve()
        api = self._api_module_seul('ntcon26-res-lever')
        resp = api.post(
            f'{RACINE}reserves-chantier/{reserve.id}/lever/',
            {'signataire_nom': 'A. Benali'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)

    def test_levee_reserve_franchit_la_garde_avec_code(self):
        """Avec le code : plus de 403 (400 « photo requise » = garde passée)."""
        reserve = self._reserve()
        api = self._api_avec(
            ['btp_voir', 'btp_gerer', PERM_RESERVE_LEVER], 'ntcon26-lev-ok')
        resp = api.post(
            f'{RACINE}reserves-chantier/{reserve.id}/lever/',
            {'signataire_nom': 'A. Benali'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST,
                         resp.content)

    def test_contestation_reserve_refusee_sans_code(self):
        reserve = self._reserve(statut=ReserveChantier.Statut.LEVEE)
        api = self._api_module_seul('ntcon26-res-contester')
        resp = api.post(
            f'{RACINE}reserves-chantier/{reserve.id}/contester/',
            {'motif': 'non conforme'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)

    def test_reponse_rfi_refusee_sans_code(self):
        rfi = self._rfi()
        api = self._api_module_seul('ntcon26-rfi')
        resp = api.post(f'{RACINE}rfi/{rfi.id}/repondre/',
                        {'texte': '3G2,5'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)

    def test_reponse_rfi_acceptee_avec_code(self):
        rfi = self._rfi()
        api = self._api_avec(
            ['btp_voir', 'btp_gerer', PERM_RFI_REPONDRE], 'ntcon26-rfi-ok')
        resp = api.post(f'{RACINE}rfi/{rfi.id}/repondre/',
                        {'texte': '3G2,5'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        rfi.refresh_from_db()
        self.assertEqual(rfi.statut, RFI.Statut.REPONDU)

    def test_cloture_rfi_refusee_sans_code(self):
        rfi = self._rfi()
        api = self._api_module_seul('ntcon26-rfi-clore')
        resp = api.post(f'{RACINE}rfi/{rfi.id}/clore/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)

    def test_approbation_visa_refusee_sans_code(self):
        """LE cas d'acceptation textuel de NTCON26."""
        visa = self._visa()
        api = self._api_module_seul('ntcon26-visa')
        resp = api.post(f'{RACINE}visas/{visa.id}/approuver/', {},
                        format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)
        # …alors que la LECTURE du visa reste ouverte.
        self.assertEqual(
            api.get(f'{RACINE}visas/{visa.id}/').status_code,
            status.HTTP_200_OK)
        visa.refresh_from_db()
        self.assertEqual(visa.statut, VisaDocument.Statut.SOUMIS)

    def test_refus_visa_refuse_sans_code(self):
        """Le refus est la décision MIROIR : même code fin."""
        visa = self._visa()
        api = self._api_module_seul('ntcon26-visa-refus')
        resp = api.post(f'{RACINE}visas/{visa.id}/refuser/',
                        {'observations': 'non'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)

    def test_approbation_visa_acceptee_avec_code(self):
        visa = self._visa()
        api = self._api_avec(
            ['btp_voir', 'btp_gerer', PERM_VISA_APPROUVER], 'ntcon26-visa-ok')
        resp = api.post(f'{RACINE}visas/{visa.id}/approuver/', {},
                        format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        visa.refresh_from_db()
        self.assertEqual(
            visa.statut, VisaDocument.Statut.APPROUVE_SANS_RESERVE)

    def test_approbation_avenant_refusee_sans_code(self):
        avenant = self._avenant()
        api = self._api_module_seul('ntcon26-avenant')
        resp = api.post(f'{RACINE}avenants-chantier/{avenant.id}/approuver/',
                        {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)
        avenant.refresh_from_db()
        self.assertEqual(avenant.statut, AvenantChantier.Statut.SOUMIS_CLIENT)

    def test_refus_avenant_refuse_sans_code(self):
        avenant = self._avenant()
        api = self._api_module_seul('ntcon26-avenant-refus')
        resp = api.post(f'{RACINE}avenants-chantier/{avenant.id}/refuser/',
                        {'motif': 'hors budget'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)

    def test_finalisation_dgd_refusee_sans_code(self):
        dgd = self._dgd()
        api = self._api_module_seul('ntcon26-dgd')
        resp = api.post(f'{RACINE}decomptes-generaux/{dgd.id}/finaliser/', {},
                        format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN,
                         resp.content)
        dgd.refresh_from_db()
        self.assertEqual(dgd.statut, DecompteGeneral.Statut.NOTIFIE)

    # ── non-régression : compte hérité ─────────────────────────────────────
    def test_compte_legacy_franchit_toutes_les_gardes_fines(self):
        """Un compte SANS ``Role`` fin n'a rien perdu (repli historique)."""
        api = auth(self.legacy)
        rfi = self._rfi()
        resp = api.post(f'{RACINE}rfi/{rfi.id}/repondre/',
                        {'texte': 'réponse'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        visa = self._visa()
        resp = api.post(f'{RACINE}visas/{visa.id}/approuver/', {},
                        format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)

    # ── non-régression : isolation société ─────────────────────────────────
    def test_code_fin_ne_traverse_pas_la_frontiere_societe(self):
        """Le code fin ne remplace JAMAIS le filtre ``company``."""
        autre = make_company()
        autre_chantier = make_chantier(autre)
        visa_autre = VisaDocument.objects.create(
            company=autre, chantier=autre_chantier, document_ged_id=99,
            reference='VIS-X', statut=VisaDocument.Statut.SOUMIS,
            delai_revue_jours=7)
        api = self._api_avec(
            ['btp_voir', 'btp_gerer', PERM_VISA_APPROUVER], 'ntcon26-tenant')
        resp = api.post(f'{RACINE}visas/{visa_autre.id}/approuver/', {},
                        format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND,
                         resp.content)
