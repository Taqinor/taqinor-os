"""Barème transport par ville (fondateur 07/09/2026) — départ Nouaceur.

Verrouille : les cinq ANCRES rendent exactement le prix fondateur ; la zone
proche part du plancher validé (800 HT) ; le Sahara est couvert (supplément
GeoNames EH) ; une ville inconnue ne reprice JAMAIS rien (zéro chiffre
inventé) ; et l'application aux lignes (dry-run sérialisé + devis sauvé)
touche la seule ligne Transport.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company

from apps.parametres.transport_bareme import (
    PLANCHER_HT, prix_transport_ht, prix_transport_ttc)
from apps.ventes.domain.transport import (
    repricer_transport_devis, repricer_transport_lignes_dict)
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


class BaremeTests(TestCase):
    def test_les_cinq_ancres_rendent_exactement_le_prix_fondateur(self):
        self.assertEqual(prix_transport_ht('Rabat'), 1200)
        self.assertEqual(prix_transport_ht('Kénitra'), 1500)
        self.assertEqual(prix_transport_ht('Marrakech'), 1500)
        self.assertEqual(prix_transport_ht('Fès'), 2000)
        self.assertEqual(prix_transport_ht('Tanger'), 2000)

    def test_zone_proche_depuis_le_plancher_valide(self):
        # « yes for both » (07/09/2026) : plancher 800 HT à Nouaceur,
        # Casablanca à 900 (23 km).
        self.assertEqual(prix_transport_ht('Nouaceur'), PLANCHER_HT)
        self.assertEqual(prix_transport_ht('Casablanca'), 900)

    def test_sahara_couvert_par_le_supplement(self):
        self.assertEqual(prix_transport_ht('Laâyoune'), 4150)
        self.assertEqual(prix_transport_ht('Dakhla'), 5950)

    def test_ville_inconnue_rend_None(self):
        self.assertIsNone(prix_transport_ht('Atlantis'))
        self.assertIsNone(prix_transport_ht(''))
        self.assertIsNone(prix_transport_ht(None))

    def test_ttc_est_le_ht_a_20_pourcent(self):
        self.assertEqual(prix_transport_ttc('Fès'), 2400)

    def test_ville_dans_un_texte_d_adresse(self):
        # Même tolérance que le gazetier : la ville en séquence de mots.
        self.assertEqual(prix_transport_ht('Quartier X, Fès'), 2000)


class RepricerLignesDictTests(TestCase):
    def _lignes(self):
        return [
            {'role': 'panneau', 'designation': 'Panneau 710W',
             'prix_unitaire_ht': '1000.00', 'prix_unitaire_ttc': '1200.00',
             'taux_tva': '20'},
            {'role': 'transport', 'designation': 'Transport',
             'prix_unitaire_ht': '833.33', 'prix_unitaire_ttc': '1000.00',
             'taux_tva': '20'},
        ]

    def test_seule_la_ligne_transport_est_repricee(self):
        lignes = self._lignes()
        n = repricer_transport_lignes_dict(lignes, 'Fès')
        self.assertEqual(n, 1)
        self.assertEqual(lignes[1]['prix_unitaire_ht'], '2000.00')
        self.assertEqual(lignes[1]['prix_unitaire_ttc'], '2400.00')
        self.assertEqual(lignes[0]['prix_unitaire_ht'], '1000.00')

    def test_ville_inconnue_ne_touche_rien(self):
        lignes = self._lignes()
        self.assertEqual(repricer_transport_lignes_dict(lignes, 'Atlantis'), 0)
        self.assertEqual(lignes[1]['prix_unitaire_ht'], '833.33')


class RepricerDevisTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='transport-bareme', defaults={'nom': 'transport-bareme'})
        self.user = User.objects.create_user(
            username='transport-u', password='x', company=self.company)
        from apps.crm.models import Client, Lead
        self.lead = Lead.objects.create(
            company=self.company, nom='Client Fès', ville='Fès',
            owner=self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client Fès',
            email='transport-bareme@example.com')
        self.devis = Devis.objects.create(
            company=self.company, reference='DEV-TRANS-0001',
            client=self.client_obj, lead=self.lead,
            taux_tva=Decimal('20.00'))
        self.transport = LigneDevis.objects.create(
            devis=self.devis, designation='Transport', quantite=1,
            prix_unitaire=Decimal('833.33'))
        self.panneau = LigneDevis.objects.create(
            devis=self.devis, designation='Panneau 710W', quantite=10,
            prix_unitaire=Decimal('1000.00'))

    def test_le_devis_prend_le_prix_de_la_ville_du_lead(self):
        self.assertEqual(repricer_transport_devis(self.devis), 1)
        self.transport.refresh_from_db()
        self.panneau.refresh_from_db()
        self.assertEqual(self.transport.prix_unitaire, Decimal('2000'))
        self.assertEqual(self.panneau.prix_unitaire, Decimal('1000.00'))

    def test_sans_lead_ou_ville_inconnue_rien_ne_bouge(self):
        self.lead.ville = 'Atlantis'
        self.lead.save(update_fields=['ville'])
        self.assertEqual(repricer_transport_devis(self.devis), 0)
        self.transport.refresh_from_db()
        self.assertEqual(self.transport.prix_unitaire, Decimal('833.33'))
