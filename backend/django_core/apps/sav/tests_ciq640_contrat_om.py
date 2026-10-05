"""CIQ640 — contrat O&M C&I créé depuis la ligne O&M (rôle ``om_ci``) d'un
devis accepté : quatre prestations NOMMÉES, fréquences et prix « à
renseigner » (NULL), délai d'intervention repris du réglage société
(CIQ622), jamais un nombre inventé. Forme du contrat partagé
``contract_samples/contrat_om.json``.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.sav.tests_ciq640_contrat_om"
"""
import json
from decimal import Decimal
from importlib import import_module
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import migrations
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.sav.models import ContratMaintenance, PrestationContrat
from apps.stock.models import Produit
from apps.ventes.domain.cycle_vie import reviser_devis
from apps.ventes.models import Devis, LigneDevis
from core.events import devis_accepted

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')
CONTRAT = Path(__file__).resolve().parent / 'contract_samples' / 'contrat_om.json'


class ContratOmCiTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='ciq640-sav', defaults={'nom': 'CIQ640 Sav'})
        self.user = User.objects.create_user(
            username='ciq640_sav', password='x', role_legacy='admin',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='CIQ640',
            email='ciq640-sav@example.invalid')
        self.om = Produit.objects.create(
            company=self.company, nom='Option O&M site pro', sku='OM-CIQ640',
            prix_achat=0, prix_vente=0, role_ci='om_ci')
        self.devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-6401',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        self.ligne = LigneDevis.objects.create(
            devis=self.devis, produit=self.om, designation='Option O&M',
            quantite=1, prix_unitaire=Decimal('0'), taux_tva=Decimal('20'))

    def _accepter(self, devis):
        devis_accepted.send(sender=None, devis=devis, user=self.user,
                            ancien_statut='envoye')

    def _contrats(self):
        return ContratMaintenance.objects.filter(client=self.client_obj)

    def test_ligne_om_un_contrat_quatre_prestations_sans_frequence(self):
        self._accepter(self.devis)
        self.assertEqual(self._contrats().count(), 1)
        contrat = self._contrats().get()
        self.assertIsNone(contrat.prix)
        self.assertEqual(contrat.origine_devis_id, self.devis.pk)
        self.assertEqual(contrat.origine_ligne_om_id, self.ligne.pk)
        prestations = list(contrat.prestations.all())
        self.assertEqual([p.type for p in prestations],
                         ['nettoyage', 'inspection', 'thermographie',
                          'test_protections'])
        for p in prestations:
            self.assertIsNone(p.frequence_an)
            self.assertIsNone(p.prix_ht)
            self.assertFalse(p.incluse)
            self.assertEqual(p.company_id, self.company.pk)
        self.assertIsNone(contrat.visites_incluses_an)

    def test_reemission_et_v2_pas_de_second_contrat(self):
        self._accepter(self.devis)
        self._accepter(self.devis)
        self.assertEqual(self._contrats().count(), 1)
        v2 = reviser_devis(self.devis, user=self.user)
        Devis.objects.filter(pk=v2.pk).update(statut=Devis.Statut.ACCEPTE)
        v2.refresh_from_db()
        self._accepter(v2)
        self.assertEqual(self._contrats().count(), 1)
        self.assertEqual(PrestationContrat.objects.filter(
            contrat__client=self.client_obj).count(), 4)

    def test_delai_societe_48h_repris(self):
        profil = CompanyProfile.get(company=self.company)
        profil.delai_intervention_suivi_heures = 48
        profil.save()
        self._accepter(self.devis)
        self.assertEqual(self._contrats().get().delai_intervention_heures, 48)

    def test_delai_vide_null(self):
        self._accepter(self.devis)
        self.assertIsNone(self._contrats().get().delai_intervention_heures)

    def test_devis_sans_ligne_om_ni_recurrente_rien(self):
        self.ligne.delete()
        self._accepter(self.devis)
        self.assertEqual(self._contrats().count(), 0)

    def test_forme_du_contrat_partage(self):
        document = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self._accepter(self.devis)
        contrat = self._contrats().get()
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        resp = api.get(f'/api/django/sav/contrats-maintenance/{contrat.pk}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        for cle in document['exemple_vide']:
            self.assertIn(cle, resp.data)
        attendu = document['exemple_vide']['prestations'][0]
        self.assertEqual(set(resp.data['prestations'][0]), set(attendu))
        self.assertEqual(set(resp.data['origine']),
                         set(document['exemple_vide']['origine']))
        self.assertEqual(resp.data['origine']['devis_id'], self.devis.pk)
        self.assertIsNone(resp.data['delai_intervention_heures'])
        self.assertEqual(
            [p['libelle'] for p in resp.data['prestations']],
            [p['libelle'] for p in document['exemple_vide']['prestations']])

    def test_migration_additive(self):
        module = import_module(
            'apps.sav.migrations.0066_ciq640_prestations_contrat')
        for op in module.Migration.operations:
            self.assertIsInstance(op, (migrations.AddField,
                                       migrations.CreateModel))
            self.assertTrue(op.reversible)


class CheminRecurrentInchangeTest(TestCase):
    def test_ligne_recurrente_seule_identique(self):
        company, _ = Company.objects.get_or_create(
            slug='ciq640-rec', defaults={'nom': 'CIQ640 Rec'})
        user = User.objects.create_user(
            username='ciq640_rec', password='x', role_legacy='admin',
            company=company)
        client = Client.objects.create(
            company=company, nom='Client', prenom='Rec',
            email='ciq640-rec@example.invalid')
        produit = Produit.objects.create(
            company=company, nom='Monitoring annuel', sku='MON-CIQ640',
            prix_achat=0, prix_vente=1200, est_recurrent=True)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{MONTH}-6402', client=client,
            statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation='Monitoring annuel',
            quantite=1, prix_unitaire=Decimal('1200'), taux_tva=Decimal('20'))
        devis_accepted.send(sender=None, devis=devis, user=user,
                            ancien_statut='envoye')
        contrat = ContratMaintenance.objects.get(client=client)
        self.assertEqual(contrat.prix, Decimal('1440.00'))
        self.assertEqual(contrat.prestations.count(), 0)
        self.assertIsNone(contrat.origine_devis_id)
        self.assertIsNone(contrat.delai_intervention_heures)
