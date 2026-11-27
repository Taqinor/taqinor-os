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
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.parametres.models import CompanyProfile
from apps.sav.models import ContratMaintenance, PrestationContrat
from apps.stock.models import Produit
from apps.ventes.domain.revision import reviser_devis
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

    def test_patch_prestations_editables_et_bornees_au_contrat(self):
        self._accepter(self.devis)
        contrat = self._contrats().get()
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        url = f'/api/django/sav/contrats-maintenance/{contrat.pk}/'
        nettoyage = contrat.prestations.get(type='nettoyage')
        resp = api.patch(url, {'prestations': [
            {'id': nettoyage.pk, 'frequence_an': 2, 'incluse': True,
             'type': 'autre', 'libelle': 'renommé'}]}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        nettoyage.refresh_from_db()
        self.assertEqual(nettoyage.frequence_an, 2)
        self.assertTrue(nettoyage.incluse)
        self.assertEqual(nettoyage.type, 'nettoyage')
        self.assertEqual(nettoyage.libelle, 'Nettoyage des modules')
        self.assertIsNone(nettoyage.prix_ht)
        # Une prestation d'un autre contrat n'est jamais modifiable ici.
        autre = ContratMaintenance.objects.create(
            company=self.company, client=self.client_obj,
            date_debut=timezone.localdate())
        etrangere = PrestationContrat.objects.create(
            company=self.company, contrat=autre, type='autre',
            libelle='Autre')
        resp = api.patch(url, {'prestations': [
            {'id': etrangere.pk, 'frequence_an': 9}]}, format='json')
        # ENF48 (api-fuzz-full) : contrat existant, prestation désignée
        # absente = 409 (était 404, « not available after creation » sur PUT).
        self.assertEqual(resp.status_code, 409)
        self.assertIn('prestations', resp.data)
        etrangere.refresh_from_db()
        self.assertIsNone(etrangere.frequence_an)
        # Une entrée SANS id ne désigne aucune prestation : même 409.
        resp = api.patch(url, {'prestations': [{'frequence_an': 3}]},
                         format='json')
        self.assertEqual(resp.status_code, 409)

    def test_dacal165_technicien_sans_prix_du_contrat(self):
        """D-ACAL-165 — Technicien et Technicien responsable livrés (`sav_voir`,
        sans `prix_vente_voir`) : ni `prix` ni `prestations[].prix_ht` en
        lecture ; l'édition renvoyant ces prix VIDES ne les efface pas ;
        l'administrateur légacy les lit, inchangés. Jeu `sav_contrats` : prix
        et valeur annuelle absents pour le technicien, présents sans acteur."""
        from apps.roles.models import Role
        from apps.roles.permissions_registre import (
            TECHNICIEN_PERMISSIONS, TECHNICIEN_RESP_PERMISSIONS)
        from apps.sav.bi_datasets import CONTRATS_DATASET_NAME
        from core import data_explorer
        self._accepter(self.devis)
        contrat = self._contrats().get()
        ContratMaintenance.objects.filter(pk=contrat.pk).update(prix=Decimal('98765.43'))
        contrat.prestations.update(prix_ht=Decimal('87654.32'))
        url = f'/api/django/sav/contrats-maintenance/{contrat.pk}/'

        def api_de(user):
            api = APIClient()
            api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
            return api

        comptes = {}
        for nom, perms in (('Technicien', TECHNICIEN_PERMISSIONS),
                           ('Technicien responsable', TECHNICIEN_RESP_PERMISSIONS)):
            role = Role.objects.create(company=self.company, nom=nom, permissions=list(perms))
            comptes[nom] = User.objects.create_user(
                username=f'd165-{nom.replace(" ", "-")}', password='x',
                company=self.company, role=role)
            resp = api_de(comptes[nom]).get(url)
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertNotIn('prix', resp.data)
            self.assertTrue(resp.data['prestations'])
            self.assertTrue(all('prix_ht' not in p for p in resp.data['prestations']))
            self.assertNotIn('98765', str(resp.data))
            self.assertNotIn('87654', str(resp.data))
        admin = api_de(self.user).get(url).data
        self.assertEqual(Decimal(str(admin['prix'])), Decimal('98765.43'))
        self.assertEqual(Decimal(str(admin['prestations'][0]['prix_ht'])), Decimal('87654.32'))
        # L'écran du chef renvoie les prix qu'il n'a pas reçus, vides : rien n'est effacé.
        nettoyage = contrat.prestations.get(type='nettoyage')
        resp = api_de(comptes['Technicien responsable']).patch(url, {
            'prix': None, 'prestations': [{'id': nettoyage.pk, 'frequence_an': 2, 'prix_ht': None}],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        contrat.refresh_from_db()
        nettoyage.refresh_from_db()
        self.assertEqual((contrat.prix, nettoyage.prix_ht, nettoyage.frequence_an),
                         (Decimal('98765.43'), Decimal('87654.32'), 2))
        spec = {'select': ['id', 'prix', 'valeur_annuelle']}
        ligne = data_explorer.run_query(CONTRATS_DATASET_NAME, self.company,
                                        comptes['Technicien'], spec)[0]
        self.assertNotIn('prix', ligne)
        self.assertNotIn('valeur_annuelle', ligne)
        ligne = data_explorer.run_query(CONTRATS_DATASET_NAME, self.company, None, spec)[0]
        self.assertEqual(ligne['prix'], Decimal('98765.43'))

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


class DelaiSocieteLecturePureTests(SimpleTestCase):
    """Profil société — le délai d'intervention lu pour le contrat O&M né de
    l'acceptation passe par ``CompanyProfile.lire`` (jamais ``get``, qui
    crée la ligne au fuseau par défaut et périmait les simulations de
    calepinage). Sans profil : None (non engagé), comme hier. Sans base."""

    def test_lit_par_lire_jamais_par_get(self):
        from types import SimpleNamespace
        from unittest import mock

        from apps.parametres.models import CompanyProfile
        from apps.sav.services import _delai_intervention_societe
        company = SimpleNamespace(pk=7, id=7, nom='Sans Profil')
        with mock.patch.object(CompanyProfile, 'get',
                               side_effect=AssertionError('get')) as get, \
                mock.patch.object(CompanyProfile, 'lire',
                                  return_value=CompanyProfile(
                                      nom='Sans Profil')) as lu:
            self.assertIsNone(_delai_intervention_societe(company))
        get.assert_not_called()
        lu.assert_called_once()
