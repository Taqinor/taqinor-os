"""CIQ620 — équipements figés au dépôt du dossier 82-21 : un changement de
modèle ou de puissance après dépôt AVERTIT (loi 82-21 art. 8-9), sans
jamais bloquer la révision.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, RegulatoryDossier
from authentication.models import Company

User = get_user_model()
DOSSIERS = '/api/django/ventes/dossiers-reglementaires/'
MESSAGE = ("modification du dossier — accord préalable requis "
           "(loi 82-21 art. 9)")


class EquipementsFigesTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='CIQ620', slug='ciq620-co')
        self.user = User.objects.create_user(
            username='ciq620', password='x', role_legacy='responsable',
            company=self.company)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Usine', email='ciq620@example.com')
        self.panneau = self._produit('Panneau 710W mono', 'PAN-620')
        self.ond_a = self._produit('Onduleur réseau 100kW A', 'OND-620-A')
        self.ond_b = self._produit('Onduleur réseau 100kW B', 'OND-620-B')
        self.v1 = self._devis('DEV-CIQ620-10', self.ond_a)
        self.dossier = RegulatoryDossier.objects.create(
            company=self.company, devis=self.v1,
            regime_8221='accord_raccordement')

    def _produit(self, nom, sku):
        return Produit.objects.create(
            company=self.company, nom=nom, sku=sku, marque='Marque',
            prix_vente=Decimal('1000'), quantite_stock=10)

    def _devis(self, ref, onduleur):
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='accepte', taux_tva=Decimal('20'))
        LigneDevis.objects.create(
            devis=devis, produit=self.panneau, designation=self.panneau.nom,
            quantite=Decimal('200'), prix_unitaire=Decimal('1000'))
        LigneDevis.objects.create(
            devis=devis, produit=onduleur, designation=onduleur.nom,
            quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
        return devis

    def _deposer(self):
        r = self.api.patch(f'{DOSSIERS}{self.dossier.id}/',
                           {'statut': 'depose'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r

    def _resume(self):
        return self.api.get(f'{DOSSIERS}{self.dossier.id}/').data['resume']

    def test_avant_depot_rien_de_fige_aucune_alerte(self):
        resume = self._resume()
        self.assertEqual(resume['equipements_figes'], [])
        self.assertEqual(resume['alertes_modification'], [])

    def test_depot_fige_les_equipements(self):
        self._deposer()
        self.dossier.refresh_from_db()
        figes = {e['modele']: e for e in self.dossier.equipements_figes}
        self.assertEqual(set(figes), {self.panneau.nom, self.ond_a.nom})
        self.assertEqual(figes[self.panneau.nom]['quantite'], 200.0)
        self.assertEqual(figes[self.ond_a.nom]['fabricant'], 'Marque')
        for cle in ('fabricant', 'modele', 'quantite', 'puissance'):
            self.assertIn(cle, figes[self.ond_a.nom])
        self.assertEqual(self._resume()['alertes_modification'], [])

    def test_v2_autre_onduleur_alerte_sans_bloquer(self):
        self._deposer()
        v2 = self._devis('DEV-CIQ620-20', self.ond_b)
        Devis.objects.filter(pk=self.v1.pk).update(superseded_by=v2)
        alertes = self._resume()['alertes_modification']
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0]['message'], MESSAGE)
        self.assertEqual(alertes[0]['origine'], 'devis')
        # Les équipements figés ne bougent pas, la révision reste possible.
        self.dossier.refresh_from_db()
        self.assertIn(self.ond_a.id, {e['produit_id']
                                      for e in self.dossier.equipements_figes})
        self.assertEqual(self.dossier.statut, 'depose')

    def test_meme_materiel_aucune_alerte(self):
        self._deposer()
        v2 = self._devis('DEV-CIQ620-30', self.ond_a)
        Devis.objects.filter(pk=self.v1.pk).update(superseded_by=v2)
        self.assertEqual(self._resume()['alertes_modification'], [])

    def test_redeposer_ne_refige_jamais(self):
        self._deposer()
        LigneDevis.objects.filter(devis=self.v1, produit=self.ond_a).update(
            produit=self.ond_b)
        self.api.patch(f'{DOSSIERS}{self.dossier.id}/',
                       {'statut': 'en_instruction'}, format='json')
        self.dossier.refresh_from_db()
        self.assertIn(self.ond_a.id, {e['produit_id']
                                      for e in self.dossier.equipements_figes})
        self.assertEqual(len(self._resume()['alertes_modification']), 1)
