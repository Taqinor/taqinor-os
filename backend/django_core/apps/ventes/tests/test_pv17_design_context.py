"""PV17 — GET /ventes/devis/<id>/design-context/ : UN appel, UNE forme.

L'écran de conception 3D lit ici TOUT ce dont il a besoin. Toutes les clés
sont TOUJOURS présentes (contrat ``contract_samples/devis_design_context.json``)
— un panier vide vaut ``[]``, une valeur inconnue ``None``/``''``, jamais une
clé absente : c'est exactement l'incident du 03/08/2026 que cette forme fixe
empêche de se reproduire.

Run:
    DJANGO_SETTINGS_MODULE=erp_agentique.settings._local_sqlite_test \
        python manage.py test apps.ventes.tests.test_pv17_design_context -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis

User = get_user_model()

CLES_RACINE = {'devis', 'geometrie', 'cible', 'carte', 'modifiable',
               'raison_lecture_seule', 'avertissements'}
CLES_DEVIS = {'id', 'reference', 'statut', 'mode_installation', 'lead',
              'client', 'client_nom', 'client_telephone', 'client_ville',
              'client_adresse'}
CLES_GEOMETRIE = {'source', 'roof_layout', 'pin', 'outline'}
CLES_CIBLE = {'panneaux', 'kwc', 'panel_watt', 'scenario', 'batterie',
              'avertissements', 'bill_kwh'}
CLES_CARTE = {'available', 'maptilerKey', 'mapboxToken'}


def make_company(slug):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': slug})
    return company


def auth_client(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestDesignContext(TestCase):
    def setUp(self):
        self.company = make_company('pv17-co')
        self.user = User.objects.create_user(
            username='pv17user', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client PV17')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W', sku='PV17-PAN',
            prix_vente=Decimal('1100'), prix_achat=Decimal('700'),
            quantite_stock=50)
        self.compteur = 0

    def _lead(self, **extra):
        return Lead.objects.create(
            company=self.company, nom='Toit', prenom='PV17', **extra)

    def _devis(self, *, statut=Devis.Statut.BROUILLON, mode=None, lead=None,
               layout=None, panneaux=12):
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-PV17-{self.compteur}',
            client=self.client_obj, lead=lead, statut=statut,
            mode_installation=mode, roof_layout=layout,
            created_by=self.user)
        if panneaux:
            devis.lignes.create(
                produit=self.panneau, designation='Panneau Jinko 550W',
                quantite=Decimal(str(panneaux)),
                prix_unitaire=Decimal('1100'))
        return devis

    def _get(self, devis):
        return self.api.get(
            f'/api/django/ventes/devis/{devis.id}/design-context/')

    def _assert_forme_complete(self, data):
        self.assertEqual(set(data), CLES_RACINE)
        self.assertEqual(set(data['devis']), CLES_DEVIS)
        self.assertEqual(set(data['geometrie']), CLES_GEOMETRIE)
        self.assertEqual(set(data['cible']), CLES_CIBLE)
        self.assertEqual(set(data['carte']), CLES_CARTE)

    # ── PV23bis — coordonnées client pour l'outil 3D (client, repli lead) ────
    def test_coordonnees_client_du_client_d_abord(self):
        """Le téléphone/adresse viennent du CLIENT quand il les porte ; la
        ville vient toujours du lead (crm.Client n'en a pas)."""
        self.client_obj.telephone = '+212600112233'
        self.client_obj.adresse = '5 rue des Fleurs'
        self.client_obj.save(update_fields=['telephone', 'adresse'])
        lead = self._lead(telephone='+212677889900', whatsapp='+212677000000',
                          ville='Rabat', adresse='Hay Riad')
        devis = self._devis(lead=lead)
        data = self._get(devis).data
        self.assertEqual(data['devis']['client_telephone'], '+212600112233')
        self.assertEqual(data['devis']['client_adresse'], '5 rue des Fleurs')
        self.assertEqual(data['devis']['client_ville'], 'Rabat')

    def test_coordonnees_client_repli_sur_le_lead(self):
        """Client muet → repli lead, whatsapp AVANT téléphone (même priorité
        que le mode lead de l'écran) ; sans lead ni saisie → chaînes vides,
        jamais une valeur inventée."""
        lead = self._lead(telephone='+212677889900', whatsapp='+212677000000',
                          ville='Rabat', adresse='Hay Riad')
        devis = self._devis(lead=lead)
        data = self._get(devis).data
        self.assertEqual(data['devis']['client_telephone'], '+212677000000')
        self.assertEqual(data['devis']['client_ville'], 'Rabat')
        self.assertEqual(data['devis']['client_adresse'], 'Hay Riad')

        muet = self._devis()
        data = self._get(muet).data
        self.assertEqual(data['devis']['client_telephone'], '')
        self.assertEqual(data['devis']['client_ville'], '')
        self.assertEqual(data['devis']['client_adresse'], '')

    # ── Forme du contrat, sur les DEUX chemins de géométrie ─────────────────
    def test_forme_complete_geometrie_depuis_le_devis(self):
        layout = {
            'version': 1,
            'pin': {'lat': 33.5, 'lng': -7.6},
            'outline': [[33.5, -7.6], [33.51, -7.6], [33.51, -7.59]],
            'zones': [],
        }
        devis = self._devis(layout=layout)
        resp = self._get(devis)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self._assert_forme_complete(data)
        self.assertEqual(data['geometrie']['source'], 'devis')
        self.assertEqual(data['geometrie']['roof_layout'], layout)
        self.assertEqual(data['geometrie']['pin'], {'lat': 33.5, 'lng': -7.6})
        self.assertEqual(len(data['geometrie']['outline']), 3)
        self.assertTrue(data['modifiable'])
        self.assertEqual(data['raison_lecture_seule'], '')

    def test_forme_complete_geometrie_depuis_le_lead(self):
        lead = self._lead(
            roof_point={'lat': 31.6, 'lng': -8.0},
            roof_outline=[[31.6, -8.0], [31.61, -8.0]],
            bill_kwh=Decimal('850'))
        devis = self._devis(lead=lead)
        resp = self._get(devis)
        self.assertEqual(resp.status_code, 200)
        data = resp.data
        self._assert_forme_complete(data)
        self.assertEqual(data['geometrie']['source'], 'lead')
        self.assertIsNone(data['geometrie']['roof_layout'])
        self.assertEqual(data['geometrie']['pin'], {'lat': 31.6, 'lng': -8.0})
        self.assertEqual(len(data['geometrie']['outline']), 2)
        self.assertEqual(data['cible']['bill_kwh'], 850.0)
        self.assertEqual(data['devis']['lead'], lead.id)

    def test_forme_complete_sans_aucune_geometrie(self):
        devis = self._devis()
        data = self._get(devis).data
        self._assert_forme_complete(data)
        self.assertEqual(data['geometrie']['source'], 'none')
        self.assertIsNone(data['geometrie']['roof_layout'])
        self.assertIsNone(data['geometrie']['pin'])
        # Jamais None : une liste vide, pour que l'écran puisse .map() dessus.
        self.assertEqual(data['geometrie']['outline'], [])
        self.assertIsNone(data['cible']['bill_kwh'])
        self.assertTrue(any('géométrie' in a
                            for a in data['avertissements']))

    def test_cible_lue_dans_les_lignes(self):
        devis = self._devis(panneaux=14)
        data = self._get(devis).data
        self.assertEqual(data['cible']['panneaux'], 14)
        self.assertEqual(data['cible']['panel_watt'], 550)
        self.assertAlmostEqual(data['cible']['kwc'], 7.7, places=3)
        self.assertEqual(data['cible']['scenario'], 'reseau')
        self.assertFalse(data['cible']['batterie'])

    # ── Les trois raisons de LECTURE SEULE ─────────────────────────────────
    def test_lecture_seule_statut_hors_cycle(self):
        for statut in (Devis.Statut.ACCEPTE, Devis.Statut.REFUSE,
                       Devis.Statut.EXPIRE):
            with self.subTest(statut=statut):
                devis = self._devis(statut=statut)
                data = self._get(devis).data
                self._assert_forme_complete(data)
                self.assertFalse(data['modifiable'])
                self.assertIn('plus modifiable',
                              data['raison_lecture_seule'])
                self.assertIn('Réviser', data['raison_lecture_seule'])

    def test_lecture_seule_devis_agricole(self):
        devis = self._devis(mode=Devis.ModeInstallation.AGRICOLE)
        data = self._get(devis).data
        self.assertFalse(data['modifiable'])
        self.assertEqual(
            data['raison_lecture_seule'],
            'Devis agricole (pompage) — le calepinage de toiture ne '
            's\'applique pas.')

    def test_lecture_seule_multi_villa(self):
        devis = self._devis()
        devis.lignes.create(
            produit=self.panneau, designation='Panneau Jinko 550W',
            quantite=Decimal('8'), prix_unitaire=Decimal('1100'),
            groupe_index=1, groupe_label='Villa A')
        data = self._get(devis).data
        self.assertFalse(data['modifiable'])
        self.assertIn('multi-villa', data['raison_lecture_seule'])

    def test_groupe_index_zero_reste_modifiable(self):
        """``groupe_index=0`` = équipement COMMUN, pas une villa."""
        devis = self._devis(panneaux=0)
        devis.lignes.create(
            produit=self.panneau, designation='Panneau Jinko 550W',
            quantite=Decimal('12'), prix_unitaire=Decimal('1100'),
            groupe_index=0)
        data = self._get(devis).data
        self.assertTrue(data['modifiable'])
        self.assertEqual(data['raison_lecture_seule'], '')

    def test_devis_residentiel_brouillon_est_modifiable(self):
        devis = self._devis(mode=Devis.ModeInstallation.RESIDENTIEL)
        data = self._get(devis).data
        self.assertTrue(data['modifiable'])
        self.assertEqual(data['raison_lecture_seule'], '')

    # ── Portée société & étanchéité ────────────────────────────────────────
    def test_devis_d_une_autre_societe_404(self):
        autre = make_company('pv17-autre-co')
        client_autre = Client.objects.create(company=autre, nom='Ailleurs')
        devis = Devis.objects.create(
            company=autre, reference='DEV-PV17-ETR', client=client_autre,
            statut=Devis.Statut.BROUILLON)
        self.assertEqual(self._get(devis).status_code, 404)

    def test_aucun_prix_achat_ni_marge(self):
        devis = self._devis()
        corps = str(self._get(devis).data)
        self.assertNotIn('prix_achat', corps)
        self.assertNotIn('marge', corps)

    def test_aucune_ecriture(self):
        devis = self._devis(statut=Devis.Statut.ENVOYE)
        self.assertEqual(self._get(devis).status_code, 200)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertIsNone(devis.roof_layout)
        self.assertEqual(devis.lignes.count(), 1)
