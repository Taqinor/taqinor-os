"""ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES — un kWh mensuel DÉCLARÉ que les
factures du MÊME dossier contredisent BLOQUE l'enregistrement du devis.

DÉCISION FONDATEUR du 30/09/2026 : si facture_barème(kWh déclaré) ÷ facture
déclarée ∉ [0,5 ; 2], le devis n'est pas enregistré (« kWh déclarés
incohérents avec les factures — corriger la fiche du lead »). Cas prod
DEV-202609-0082/-0085 : 46 kWh/mois (≈ 82 MAD) face à 15 000 MAD/mois. Quand
les deux concordent, la priorité Q14 (CAD166) du kWh déclaré reste intacte.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_err_kwh_declare_incoherent -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.etude_horaire import (
    controle_kwh_declare_du_devis, profil_conso_du_devis,
)
from apps.ventes.horaire.conso import (
    CODE_KWH_INCOHERENT, MESSAGE_KWH_INCOHERENT,
    coherence_kwh_declare_factures,
)
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()


class CoherencePureTests(SimpleTestCase):

    def test_cas_prod_46_kwh_contre_15000_mad_incoherent(self):
        res = coherence_kwh_declare_factures(46, [15000])
        self.assertFalse(res['coherent'])
        self.assertLess(res['ratios'][0], 0.5)

    def test_kwh_concordant_reste_coherent(self):
        # 650 kWh/mois ≈ 1 195 MAD au barème 2026 : ratio ≈ 1 face à 1 200.
        self.assertTrue(coherence_kwh_declare_factures(650, [1200])['coherent'])

    def test_bornes_de_la_bande(self):
        facture = coherence_kwh_declare_factures(650, [1])['facture_bareme_mad']
        self.assertTrue(coherence_kwh_declare_factures(
            650, [facture / 1.99])['coherent'])
        self.assertTrue(coherence_kwh_declare_factures(
            650, [facture / 0.51])['coherent'])
        self.assertFalse(coherence_kwh_declare_factures(
            650, [facture / 2.01])['coherent'])
        self.assertFalse(coherence_kwh_declare_factures(
            650, [facture / 0.49])['coherent'])

    def test_une_seule_facture_dans_la_bande_suffit(self):
        # Hiver 1 200 MAD cohérent, été 10 000 MAD non : le kWh passe.
        self.assertTrue(coherence_kwh_declare_factures(
            650, [1200, 10000])['coherent'])

    def test_rien_a_confronter(self):
        self.assertIsNone(coherence_kwh_declare_factures(None, [1200]))
        self.assertIsNone(coherence_kwh_declare_factures(650, [None, 0]))


class GardeServeurTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(
            nom='ERR kWh incoh', slug='err-kwh-incoherent')
        cls.user = User.objects.create_user(
            username='err_kwh_resp', password='x', role_legacy='responsable',
            company=cls.company)
        cls.client_obj = Client.objects.create(
            company=cls.company, nom='Client', prenom='kWh',
            email='err-kwh@example.com', telephone='+212600007301')
        cls.produit = Produit.objects.create(
            company=cls.company, nom='Panneau Canadien Solar 710W',
            sku='ERRKWH-PV', prix_vente=Decimal('1450'), quantite_stock=10)

    def setUp(self):
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _lead(self, kwh, facture_hiver):
        return Lead.objects.create(
            company=self.company, nom='Lead', prenom='kWh',
            telephone='+212600007302', ville='Casablanca',
            client=self.client_obj, facture_hiver=facture_hiver,
            ete_differente=False, conso_mensuelle_kwh=kwh)

    def _creer(self, lead):
        return self.api.post('/api/django/ventes/devis/atomic/', {
            'lead': lead.id, 'taux_tva': '20',
            'lignes': [{'produit': self.produit.id,
                        'designation': self.produit.nom,
                        'quantite': '4', 'prix_unitaire': '1450'}]},
            format='json')

    def test_atomic_refuse_le_kwh_contredit_et_ne_cree_rien(self):
        lead = self._lead(Decimal('46'), Decimal('15000'))
        avant = Devis.objects.filter(company=self.company).count()
        r = self._creer(lead)
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['detail'], MESSAGE_KWH_INCOHERENT)
        self.assertEqual(r.data['code'], CODE_KWH_INCOHERENT)
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), avant)

    def test_atomic_accepte_le_kwh_concordant_et_garde_sa_priorite(self):
        lead = self._lead(Decimal('650'), Decimal('1200'))
        r = self._creer(lead)
        self.assertEqual(r.status_code, 201, r.content)
        devis = Devis.objects.get(pk=r.data['id'])
        conso, source, _detail = profil_conso_du_devis(devis)
        self.assertEqual(source, 'kwh_mensuel_saisi')
        self.assertEqual(conso, [650.0] * 12)

    def test_replace_lines_refuse_tant_que_la_fiche_n_est_pas_corrigee(self):
        lead = self._lead(Decimal('650'), Decimal('1200'))
        r = self._creer(lead)
        self.assertEqual(r.status_code, 201, r.content)
        devis_id = r.data['id']
        Lead.objects.filter(pk=lead.pk).update(
            conso_mensuelle_kwh=Decimal('46'), facture_hiver=Decimal('15000'))
        lignes = [{'produit': self.produit.id, 'designation': self.produit.nom,
                   'quantite': '6', 'prix_unitaire': '1450'}]
        url = f'/api/django/ventes/devis/{devis_id}/replace-lines/'
        r = self.api.post(url, {'lignes': lignes}, format='json')
        self.assertEqual(r.status_code, 400, r.content)
        self.assertEqual(r.data['code'], CODE_KWH_INCOHERENT)
        # Fiche corrigée ⇒ l'enregistrement repasse.
        Lead.objects.filter(pk=lead.pk).update(
            conso_mensuelle_kwh=Decimal('9000'))
        r = self.api.post(url, {'lignes': lignes}, format='json')
        self.assertEqual(r.status_code, 200, r.content)

    def test_devis_automatique_refuse_aussi(self):
        lead = self._lead(Decimal('46'), Decimal('15000'))
        avant = Devis.objects.filter(company=self.company).count()
        r = self.api.post('/api/django/ventes/devis/auto/',
                          {'lead': lead.id}, format='json')
        self.assertEqual(r.status_code, 422, r.content)
        self.assertEqual(r.data['detail'], MESSAGE_KWH_INCOHERENT)
        self.assertEqual(r.data['field'], 'conso_mensuelle_kwh')
        self.assertEqual(
            Devis.objects.filter(company=self.company).count(), avant)

    def test_douze_kwh_mesures_neutralisent_la_garde(self):
        lead = self._lead(Decimal('46'), Decimal('15000'))
        devis = Devis.objects.create(
            company=self.company, reference='DEV-ERR-KWH-12M',
            client=self.client_obj, lead=lead, statut='brouillon',
            taux_tva=Decimal('20'),
            etude_params={'conso_kwh_mensuelles': [9000] * 12})
        self.assertIsNone(controle_kwh_declare_du_devis(devis))
