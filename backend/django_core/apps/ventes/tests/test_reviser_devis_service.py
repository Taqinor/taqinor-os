"""QJR521 (Groupe QJR5, D-QJR5-2) — « Réviser » passe par UN service de
domaine verrouillé (``domain/cycle_vie.reviser_devis``) : une seule V+1,
jamais de fourche, jamais de réactivation, trace au chatter.

Run:
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.ventes.tests.test_reviser_devis_service"
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.roles.models import Role
from apps.stock.models import Produit
from apps.ventes.models import Devis, DevisActivity, LigneDevis
from authentication.models import Company

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReviserDevisService(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='QJR521 Co', slug='qjr521-co')
        self.user = User.objects.create_user(
            username='qjr521_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = _api(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='QJR521',
            email='qjr521@example.test', telephone='+212600005210')
        self.produit = Produit.objects.create(
            company=self.company, nom='Panneau Canadien Solar 710W',
            sku='QJR521-PV', prix_vente=Decimal('1000'),
            prix_achat=Decimal('700'), quantite_stock=100)
        self.n = 0

    def _devis(self, statut=Devis.Statut.ENVOYE, auteur=None):
        self.n += 1
        # Références espacées de 10 : « Réviser » numérote la v2 au plus haut
        # numéro utilisé + 1 (core.numbering) ; des références manuelles
        # consécutives entreraient en collision avec elle.
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-521{self.n}0',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            created_by=auteur or self.user)
        LigneDevis.objects.create(
            devis=devis, produit=self.produit, designation=self.produit.nom,
            quantite=Decimal('10'), prix_unitaire=Decimal('1000'),
            remise=Decimal('0'))
        return devis

    def _post(self, devis, api=None):
        return (api or self.api).post(
            f'/api/django/ventes/devis/{devis.id}/reviser/')

    def _v2_de(self, v1):
        return Devis.objects.filter(version_parent=v1)

    def test_double_post_une_seule_v2(self):
        v1 = self._devis()
        r1 = self._post(v1)
        self.assertEqual(r1.status_code, 201, r1.content)
        r2 = self._post(v1)
        self.assertEqual(r2.status_code, 409, r2.content)
        self.assertIn(r1.data['reference'], r2.data['detail'])
        self.assertEqual(self._v2_de(v1).count(), 1)
        v1.refresh_from_db()
        self.assertEqual(v1.superseded_by_id, r1.data['id'])

    def test_brouillon_refuse(self):
        v1 = self._devis(Devis.Statut.BROUILLON)
        r = self._post(v1)
        self.assertEqual(r.status_code, 409, r.content)
        self.assertIn('brouillon', r.data['detail'].lower())
        self.assertFalse(self._v2_de(v1).exists())
        v1.refresh_from_db()
        self.assertTrue(v1.is_active)

    def test_accepte_refuse_expire_revisables(self):
        for statut in (Devis.Statut.ACCEPTE, Devis.Statut.REFUSE,
                       Devis.Statut.EXPIRE):
            with self.subTest(statut=statut):
                v1 = self._devis(statut)
                r = self._post(v1)
                self.assertEqual(r.status_code, 201, r.content)
                v1.refresh_from_db()
                # Le statut de v1 n'est JAMAIS écrit (règle #4).
                self.assertEqual(v1.statut, statut)
                self.assertFalse(v1.is_active)

    def test_exception_apres_cloner_rien_ne_reste(self):
        from apps.ventes.domain.revision import reviser_devis
        v1 = self._devis()
        nb_avant = Devis.objects.count()
        with patch('apps.ventes.activity.log_devis_note',
                   side_effect=RuntimeError('panne')):
            with self.assertRaises(RuntimeError):
                reviser_devis(v1, user=self.user)
        v1.refresh_from_db()
        self.assertTrue(v1.is_active)
        self.assertIsNone(v1.superseded_by_id)
        self.assertEqual(Devis.objects.count(), nb_avant)
        self.assertFalse(self._v2_de(v1).exists())

    def test_chatter_v1_et_v2(self):
        v1 = self._devis()
        r = self._post(v1)
        self.assertEqual(r.status_code, 201, r.content)
        v2 = Devis.objects.get(pk=r.data['id'])
        corps_v1 = ' '.join(DevisActivity.objects.filter(devis=v1)
                            .values_list('body', flat=True))
        corps_v2 = ' '.join(DevisActivity.objects.filter(devis=v2)
                            .values_list('body', flat=True))
        self.assertIn(f'Remplacé par {v2.reference} (révision)', corps_v1)
        self.assertIn(f'Révision de {v1.reference}', corps_v2)

    def test_reactivation_refusee(self):
        v1 = self._devis()
        self.assertEqual(self._post(v1).status_code, 201)
        r = self.api.patch(f'/api/django/ventes/devis/{v1.id}/',
                           {'is_active': True}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('is_active', r.data)
        v1.refresh_from_db()
        self.assertFalse(v1.is_active)

    def test_permissions_commercial_201_lecture_seule_403(self):
        commercial = User.objects.create_user(
            username='qjr521_com', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Commercial',
                permissions=['ventes_voir', 'ventes_creer']))
        lecteur = User.objects.create_user(
            username='qjr521_ro', password='x', company=self.company,
            role=Role.objects.create(
                company=self.company, nom='Lecture',
                permissions=['ventes_voir']))
        self.assertEqual(
            self._post(self._devis(auteur=commercial),
                       api=_api(commercial)).status_code, 201)
        v1 = self._devis(auteur=lecteur)
        self.assertEqual(self._post(v1, api=_api(lecteur)).status_code, 403)
        v1.refresh_from_db()
        self.assertTrue(v1.is_active)

    def test_vnt24_meme_409_successeur_tete_pour_les_quatre_gestes(self):
        """VNT24 — V1 → V2 → V3 : un geste sur V2 (ou V1) rend LA forme 409
        ``{detail, code: version_remplacee, successeur: {id, reference}}``
        où ``successeur`` est la TÊTE (V3), jamais le successeur direct."""
        v1 = self._devis()
        r = self._post(v1)
        self.assertEqual(r.status_code, 201, r.content)
        v2 = Devis.objects.get(pk=r.data['id'])
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        r = self._post(v2)
        self.assertEqual(r.status_code, 201, r.content)
        v3 = Devis.objects.get(pk=r.data['id'])
        tete = {'id': v3.id, 'reference': v3.reference}
        for version in (v1, v2):
            for action, corps in (('accepter', {'nom': 'Client'}),
                                  ('reviser', None), ('refuser', None),
                                  ('share-link', {'envoi': True})):
                with self.subTest(version=version.version, action=action):
                    r = self.api.post(
                        f'/api/django/ventes/devis/{version.id}/{action}/',
                        corps or {}, format='json')
                    self.assertEqual(r.status_code, 409, r.content)
                    corps_409 = r.json()
                    self.assertEqual(corps_409['code'], 'version_remplacee')
                    self.assertEqual(corps_409['successeur'], tete)
                    self.assertIn(v3.reference, corps_409['detail'])
        for version in (v1, v2):
            version.refresh_from_db()
            self.assertFalse(version.is_active)
            self.assertNotEqual(version.statut, Devis.Statut.ACCEPTE)

    def test_vnt24_brouillon_porte_un_code(self):
        r = self._post(self._devis(Devis.Statut.BROUILLON))
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data['code'], 'brouillon')

    # ── VNT55 (D-ADEV-1) — abandonner la révision réactive la V1 acceptée ──

    def _v1_acceptee_et_v2(self):
        from apps.ventes.models import BonCommande
        v1 = self._devis(Devis.Statut.ACCEPTE)
        bc = BonCommande.objects.create(
            company=self.company, reference=f'BC-{MONTH}-5210', devis=v1,
            client=self.client_obj, statut=BonCommande.Statut.EN_ATTENTE)
        r = self._post(v1)
        self.assertEqual(r.status_code, 201, r.content)
        return v1, Devis.objects.get(pk=r.data['id']), bc

    def _assert_v1_reactivee(self, v1, bc):
        v1.refresh_from_db()
        self.assertTrue(v1.is_active)
        self.assertIsNone(v1.superseded_by_id)
        self.assertEqual(v1.statut, Devis.Statut.ACCEPTE)
        bc.refresh_from_db()
        self.assertEqual(bc.devis_id, v1.pk)
        self.assertTrue(DevisActivity.objects.filter(
            devis=v1, body__contains='révision abandonnée').exists())
        # Révisable à nouveau.
        self.assertEqual(self._post(v1).status_code, 201)

    def test_vnt55_suppression_du_brouillon_v2_reactive_v1(self):
        admin = User.objects.create_user(
            username='qjr521_admin', password='x', role_legacy='admin',
            company=self.company)
        v1, v2, bc = self._v1_acceptee_et_v2()
        r = _api(admin).delete(f'/api/django/ventes/devis/{v2.id}/')
        self.assertEqual(r.status_code, 204, r.content)
        self.assertFalse(Devis.objects.filter(pk=v2.pk).exists())
        self._assert_v1_reactivee(v1, bc)

    def test_vnt55_archivage_de_la_v2_reactive_v1(self):
        v1, v2, bc = self._v1_acceptee_et_v2()
        r = self.api.patch(f'/api/django/ventes/devis/{v2.id}/',
                           {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self._assert_v1_reactivee(v1, bc)

    # ── VNT56 — les jumeaux refus et expiration d'une V2 non acceptée ──────

    def _v2_envoyee(self):
        v1, v2, bc = self._v1_acceptee_et_v2()
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ENVOYE)
        v2.refresh_from_db()
        return v1, v2, bc

    def test_vnt56_refus_de_la_v2_reactive_v1(self):
        v1, v2, bc = self._v2_envoyee()
        r = self.api.post(f'/api/django/ventes/devis/{v2.id}/refuser/',
                          {}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self._assert_v1_reactivee(v1, bc)

    def test_vnt56_expiration_de_la_v2_reactive_v1(self):
        import datetime
        from apps.ventes.domain.recouvrement import expire_stale_devis
        v1, v2, bc = self._v2_envoyee()
        Devis.objects.filter(pk=v2.pk).update(
            date_validite=datetime.date(2020, 1, 1))
        expire_stale_devis()
        v2.refresh_from_db()
        self.assertEqual(v2.statut, Devis.Statut.EXPIRE)
        self._assert_v1_reactivee(v1, bc)

    # ── VNT60 — POST prix-negocie / avenant/demander-signature ─────────────

    def _api_role(self, nom, permissions):
        role = Role.objects.create(
            company=self.company, nom=nom, permissions=list(permissions))
        return _api(User.objects.create_user(
            username=f'vnt60_{nom.split()[0].lower()}', password='x',
            role=role, role_legacy='normal', company=self.company))

    def _prix_negocie(self, devis, api=None, **corps):
        return (api or self.api).post(
            f'/api/django/ventes/devis/{devis.id}/prix-negocie/', corps,
            format='json')

    def test_vnt60_commercial_et_technicien_responsable_403(self):
        from apps.roles.permissions_registre import (
            COMMERCIAL_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS)
        v1 = self._devis(Devis.Statut.ACCEPTE)
        for nom, perms in (('Commercial VNT60', COMMERCIAL_PERMISSIONS),
                           ('Technicien responsable VNT60',
                            TECHNICIEN_RESP_PERMISSIONS)):
            with self.subTest(role=nom):
                r = self._prix_negocie(v1, api=self._api_role(nom, perms),
                                       prix_ttc='10800', mode='apercu')
                self.assertEqual(r.status_code, 403, r.content)
        v1.refresh_from_db()
        self.assertTrue(v1.is_active)

    def test_vnt60_responsable_apercu_200_appliquer_201(self):
        v1 = self._devis(Devis.Statut.ACCEPTE)
        r = self._prix_negocie(v1, prix_ttc='10800', mode='apercu')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['remise_pct'], '10.00')
        self.assertEqual(r.data['devis_v2']['id'], None)
        self.assertNotIn('_remise', r.data)
        self.assertFalse(self._v2_de(v1).exists())
        r = self._prix_negocie(v1, prix_ttc='10800', mode='appliquer')
        self.assertEqual(r.status_code, 201, r.content)
        v2 = Devis.objects.get(pk=r.data['devis_v2']['id'])
        self.assertEqual(v2.statut, Devis.Statut.ACCEPTE)
        self.assertEqual(v2.remise_globale, Decimal('10.00'))
        # Double clic : 409 au format de VNT24 (successeur).
        r = self._prix_negocie(v1, prix_ttc='10800', mode='appliquer')
        self.assertEqual(r.status_code, 409, r.content)
        self.assertEqual(r.data['code'], 'version_remplacee')
        self.assertEqual(r.data['successeur']['id'], v2.pk)

    def test_vnt60_demander_signature_deux_fois_une_tache_meme_lien(self):
        from apps.crm.models import Lead
        from apps.crm.receivers_cadence import LIBELLE_FAIRE_SIGNER_AVENANT
        lead = Lead.objects.create(company=self.company, nom='Lead VNT60')
        v1 = self._devis(Devis.Statut.ACCEPTE)
        Devis.objects.filter(pk=v1.pk).update(lead=lead)
        r = self._prix_negocie(v1, prix_ttc='10800', mode='appliquer')
        self.assertEqual(r.status_code, 201, r.content)
        url = (f"/api/django/ventes/devis/{r.data['devis_v2']['id']}/"
               'avenant/demander-signature/')
        r1 = self.api.post(url, {}, format='json')
        r2 = self.api.post(url, {}, format='json')
        self.assertEqual(r1.status_code, 200, r1.content)
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertEqual(r1.data['share_link'], r2.data['share_link'])
        self.assertIn('/proposition/', r1.data['share_link'])
        self.assertEqual(r1.data['tache_id'], r2.data['tache_id'])
        self.assertEqual(lead.relance_etapes.filter(
            libelle=LIBELLE_FAIRE_SIGNER_AVENANT).count(), 1)
        # Un devis qui n'est pas un avenant : 409, aucune tâche.
        r = self.api.post(
            f'/api/django/ventes/devis/{v1.id}/avenant/demander-signature/',
            {}, format='json')
        self.assertEqual(r.status_code, 409, r.content)
