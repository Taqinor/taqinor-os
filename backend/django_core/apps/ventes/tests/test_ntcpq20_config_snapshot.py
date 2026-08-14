"""NTCPQ20 — Historique fin des configurations d'un devis brouillon."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.models import ConfigurationDevisSnapshot, Devis, LigneDevis
from apps.ventes.services import (
    capturer_configuration_devis, diff_configurations_devis,
)
from authentication.models import CustomUser
from testkit.factories import (
    CompanyFactory, DevisFactory, ProduitFactory, UserFactory,
)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestConfigurationSnapshot(TestCase):
    def setUp(self):
        self.company = CompanyFactory()
        self.user = UserFactory(
            company=self.company, role_legacy=CustomUser.ROLE_RESPONSABLE)
        self.produit = ProduitFactory(company=self.company)
        self.devis = DevisFactory(company=self.company)

    def _ligne(self, qte='1', prix='100.00'):
        return LigneDevis.objects.create(
            devis=self.devis, produit=self.produit,
            designation=self.produit.nom, quantite=Decimal(qte),
            prix_unitaire=Decimal(prix))

    def test_cinq_reconfigurations_produisent_cinq_etats(self):
        ligne = self._ligne()                       # 1 — ajout
        ligne.quantite = Decimal('2')
        ligne.save(update_fields=['quantite'])      # 2 — quantité
        ligne.quantite = Decimal('3')
        ligne.save(update_fields=['quantite'])      # 3 — quantité
        autre = self._ligne(qte='4')                # 4 — ajout
        autre.delete()                              # 5 — retrait
        snaps = ConfigurationDevisSnapshot.objects.filter(devis=self.devis)
        self.assertEqual(snaps.count(), 5)
        quantites = [
            s.contenu['lignes'][0]['quantite'] for s in snaps.order_by('id')]
        self.assertEqual(quantites[:3], ['1.00', '2.00', '3.00'])

    def test_pas_dinstantane_hors_brouillon(self):
        self.devis.statut = Devis.Statut.ENVOYE
        self.devis.save(update_fields=['statut'])
        self.devis.refresh_from_db()
        self._ligne()
        self.assertEqual(ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).count(), 0)

    def test_contenu_identique_ne_cree_pas_de_doublon(self):
        ligne = self._ligne()
        avant = ConfigurationDevisSnapshot.objects.count()
        ligne.save()  # aucun changement de configuration
        self.assertEqual(ConfigurationDevisSnapshot.objects.count(), avant)

    def test_aucune_donnee_de_marge_dans_le_contenu(self):
        self._ligne()
        snap = ConfigurationDevisSnapshot.objects.get(devis=self.devis)
        blob = str(snap.contenu)
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)

    def test_capture_explicite_porte_lauteur(self):
        ligne = self._ligne()
        # Contenu identique au dernier instantané → aucun doublon.
        self.assertIsNone(
            capturer_configuration_devis(self.devis, user=self.user))
        # Écriture en masse (hors signal) puis capture explicite : l'auteur est
        # bien mémorisé.
        LigneDevis.objects.filter(id=ligne.id).update(quantite=Decimal('8'))
        snap = capturer_configuration_devis(self.devis, user=self.user)
        self.assertIsNotNone(snap)
        self.assertEqual(snap.auteur_id, self.user.id)
        self.assertEqual(snap.company_id, self.company.id)

    def test_diff_entre_deux_instantanes(self):
        ligne = self._ligne()
        premier = ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).order_by('id').first()
        ligne.quantite = Decimal('7')
        ligne.save(update_fields=['quantite'])
        ajoutee = self._ligne(qte='2', prix='50.00')
        dernier = ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).order_by('id').last()
        diff = diff_configurations_devis(premier, dernier)
        self.assertEqual([li['ligne_id'] for li in diff['ajoutees']],
                         [ajoutee.id])
        self.assertEqual(diff['retirees'], [])
        self.assertEqual(diff['modifiees'][0]['ligne_id'], ligne.id)
        self.assertEqual(diff['modifiees'][0]['champs']['quantite'],
                         ['1.00', '7.00'])

    def test_endpoint_historique_et_diff(self):
        ligne = self._ligne()
        ligne.quantite = Decimal('5')
        ligne.save(update_fields=['quantite'])
        snaps = list(ConfigurationDevisSnapshot.objects.filter(
            devis=self.devis).order_by('id'))
        url = (f'/api/django/ventes/devis/{self.devis.id}/'
               'historique-configuration/')
        api = auth(self.user)
        resp = api.get(url)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['snapshots']), 2)
        self.assertNotIn('diff', resp.data)
        resp = api.get(f'{url}?a={snaps[0].id}&b={snaps[1].id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['diff']['modifiees'][0]['champs']
                         ['quantite'], ['1.00', '5.00'])

    def test_endpoint_isole_les_societes(self):
        autre = DevisFactory(company=CompanyFactory())
        resp = auth(self.user).get(
            f'/api/django/ventes/devis/{autre.id}/historique-configuration/')
        self.assertEqual(resp.status_code, 404)
