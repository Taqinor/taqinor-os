"""QJR23 — L'API publique « salle de vente » cesse de servir un total brut.

Avant ce correctif, ``_item_payload`` (``crm/public_views.py``) servait
``devis.total_ttc`` — le total BRUT (remise globale ignorée, et sur un devis
à deux options, les DEUX options sommées, un chiffre qui ne correspond à
aucun document réel). Origine : R4-B2.2.

Décisions fondateur D2 (les totaux du devis passent au NET) et D9 (un devis
à deux options suit le TOTAL AFFICHÉ, jamais la somme des deux) du 29/08 :
la charge publique route désormais sur ``display_totals`` — la MÊME chaîne
canonique par option que la liste des devis et le Kanban
(``DevisSerializer.total_affiche``). Ce module prouve : (1) sur un devis
remisé à deux options, la charge utile publique porte le même chiffre que
``total_affiche`` ; (2) aucun autre champ de la réponse ne bouge.

NOTE — ce fichier vit à plat dans ``apps/crm/`` (comme
``test_qjr_commission_apporteur.py`` — voir sa note : un sous-paquet
``apps/crm/tests/`` entrerait en collision avec ``apps/crm/tests.py``,
masquant silencieusement ``TestLeadModel``).

Run:
    docker compose exec django_core python manage.py test \
        apps.crm.test_qjr_salle_de_vente_total -v 2
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company
from apps.crm.models import Client, SalleVente, SalleVenteItem
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.quote_engine.builder import display_totals

# Composition à deux VRAIES options (réseau ET hybride+batterie), miroir de
# ``test_qj30_multivilla_render.py::FULL_LINES`` — la même fixture qui rend
# déjà nb_options == 2 dans ce moteur.
FULL_LINES = [
    ('Onduleur réseau 10kW', '1', '11700'),
    ('Onduleur hybride 5kW', '1', '24000'),
    ('Panneau mono 550W', '14', '1100'),
    ('Batterie 5 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Installation', '1', '4000'),
]


class SalleVenteTotalAfficheTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            nom='Taqinor QJR23', slug='taqinor-qjr23')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR23')

    def _devis_deux_options_remise(self, reference):
        devis = Devis.objects.create(
            company=self.company, client=self.client_obj, reference=reference,
            statut=Devis.Statut.ENVOYE, remise_globale=Decimal('10.00'),
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        for desig, qty, pu in FULL_LINES:
            LigneDevis.objects.create(
                devis=devis, designation=desig, quantite=Decimal(qty),
                prix_unitaire=Decimal(pu), remise=Decimal('0'))
        return devis

    def test_charge_publique_porte_le_total_affiche_pas_le_brut(self):
        devis = self._devis_deux_options_remise('DEV-QJR23-2OPT')
        attendu = display_totals(devis)
        self.assertEqual(attendu['nb_options'], 2)

        salle = SalleVente.objects.create(
            company=self.company, client=self.client_obj, titre='Salle QJR23')
        item = SalleVenteItem.objects.create(
            salle=salle, type=SalleVenteItem.TypeItem.DEVIS,
            reference=str(devis.pk))

        public_api = APIClient()
        resp = public_api.get(f'/api/django/crm/salle-vente/{salle.token}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        body = resp.data['items'][0]

        # (1) le total publié == total_affiche (chaîne canonique par option).
        self.assertEqual(body['total_ttc'], str(attendu['total']))
        # Le brut de l'ancien code (devis.total_ttc, remise ignorée, deux
        # options sommées) est un chiffre DIFFÉRENT — la preuve que le
        # correctif change réellement la valeur servie, pas seulement sa
        # source.
        self.assertNotEqual(body['total_ttc'], str(devis.total_ttc))

        # (2) aucun autre champ de la réponse ne bouge.
        self.assertEqual(body['id'], item.id)
        self.assertEqual(body['type'], SalleVenteItem.TypeItem.DEVIS)
        self.assertEqual(body['reference'], devis.reference)
        self.assertEqual(body['statut'], devis.statut)
        self.assertEqual(
            body['proposal_path'],
            f'/api/django/ventes/devis/{devis.pk}/proposal/')

    def test_devis_mono_option_sans_remise_inchange(self):
        """Un devis mono-option sans remise (chemin historique) sert le même
        chiffre qu'avant : total_affiche == total_ttc brut quand il n'y a
        rien à corriger."""
        devis = Devis.objects.create(
            company=self.company, client=self.client_obj,
            reference='DEV-QJR23-MONO', statut=Devis.Statut.ENVOYE)
        LigneDevis.objects.create(
            devis=devis, designation='Onduleur réseau 5kW', quantite=1,
            prix_unitaire=Decimal('10000.00'), remise=Decimal('0'))

        salle = SalleVente.objects.create(
            company=self.company, client=self.client_obj, titre='Salle mono')
        SalleVenteItem.objects.create(
            salle=salle, type=SalleVenteItem.TypeItem.DEVIS,
            reference=str(devis.pk))

        public_api = APIClient()
        resp = public_api.get(f'/api/django/crm/salle-vente/{salle.token}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        body = resp.data['items'][0]
        self.assertEqual(body['total_ttc'], str(display_totals(devis)['total']))
