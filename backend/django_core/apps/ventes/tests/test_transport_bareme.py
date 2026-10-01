"""Barème transport par ville (fondateur 07/09/2026) — départ Nouaceur.

Verrouille : les cinq ANCRES rendent exactement le prix fondateur ; la zone
proche part du plancher validé (800 HT) ; le Sahara est couvert (supplément
GeoNames EH) ; une ville inconnue ne reprice JAMAIS rien (zéro chiffre
inventé) ; et — QJR604 — le barème est appliqué DANS l'étape ``composer`` du
pipeline : toutes les origines (devis auto, calepinage, dry-run de l'écran)
rendent le même prix HT de Transport pour le même lead, et le cliché de
marge est calculé APRÈS ce prix, jamais au prix catalogue.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.parametres.transport_bareme import (
    PLANCHER_HT, prix_transport_ht, prix_transport_ttc)
from apps.ventes.domain.composition import CompositionLignes, LigneKit
from apps.ventes.domain.transport import (
    appliquer_bareme_transport, ville_du_lead)
from apps.ventes.models import Devis

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


class AppliquerBaremeCompositionTests(TestCase):
    """L'application PURE du barème à une composition (étape ``composer``)."""

    def _compo(self):
        lignes = CompositionLignes([
            LigneKit(produit=None, designation='Panneau 710W', quantite=10,
                     prix_unitaire=Decimal('1000.00')),
            LigneKit(produit=None, designation='Forfait livraison',
                     quantite=1, prix_unitaire=Decimal('833.33')),
        ])
        lignes.roles = ['panneau', 'transport']
        lignes.nb_panneaux = 10
        return lignes

    def test_seule_la_ligne_de_role_transport_est_repricee(self):
        lignes = appliquer_bareme_transport(self._compo(), 'Fès')
        self.assertEqual(lignes[1].prix_unitaire, Decimal('2000.00'))
        self.assertEqual(lignes[0].prix_unitaire, Decimal('1000.00'))
        # Les métadonnées de la composition survivent.
        self.assertEqual(lignes.nb_panneaux, 10)
        self.assertEqual(list(lignes.roles), ['panneau', 'transport'])

    def test_ville_inconnue_ne_touche_rien(self):
        compo = self._compo()
        self.assertIs(appliquer_bareme_transport(compo, 'Atlantis'), compo)
        self.assertIs(appliquer_bareme_transport(compo, ''), compo)

    def test_sans_roles_repli_historique_sur_le_mot_cle(self):
        compo = CompositionLignes([
            LigneKit(produit=None, designation='TRANSPORT et logistique',
                     quantite=1, prix_unitaire=Decimal('833.33'))])
        lignes = appliquer_bareme_transport(compo, 'Fès')
        self.assertEqual(lignes[0].prix_unitaire, Decimal('2000.00'))


#: Catalogue minimal d'un kit résidentiel complet, ligne Transport comprise
#: (prix catalogue 1000 HT, que le barème de Fès — 2000 HT — doit remplacer).
CATALOGUE = [
    ('Panneau Canadien Solar 710W', 'PAN710', '1450'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'ONDR5', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', 'ONDH5', '17000'),
    ('Batterie Dyness 5 kWh', 'BAT5', '16000'),
    ('Structures acier', 'STR-ACIER', '500'),
    ('Socles', 'SOC', '80'),
    ('Accessoires', 'ACC', '2000'),
    ('Tableau De Protection AC/DC', 'TAB', '2000'),
    ('Installation', 'INST', '4800'),
    ('Transport', 'TRANS', '1000'),
]

LAYOUT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [], 'roofType': 'flat', 'pitch': 10, 'azimuth': 180,
    }],
    'scenario': 'reseau',
    'result': {'panels': 8, 'kwc': 5.68, 'annualKwh': 9000, 'savings': 8000},
    'renderPlan': {'cells': 8},
}

AUTO_URL = '/api/django/ventes/devis/auto/'
LAYOUT_URL = '/api/django/ventes/devis/from-layout/'
COMPO_URL = '/api/django/ventes/devis/composition/'


class BaremeDansLePipelineTests(TestCase):
    """QJR604 — même lead, trois origines, même prix HT de Transport."""

    def setUp(self):
        from apps.crm.models import Lead
        from apps.stock.models import Produit
        self.company, _ = Company.objects.get_or_create(
            slug='qjr604-transport', defaults={'nom': 'qjr604-transport'})
        self.user = User.objects.create_user(
            username='qjr604-u', password='x', company=self.company,
            role_legacy='admin')
        for nom, sku, prix in CATALOGUE:
            Produit.objects.create(
                company=self.company, nom=nom,
                sku='%s-%s' % (sku, self.company.pk),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=1000)
        # VREF — douar hors gazetier rattaché à Fès : le barème suit Fès.
        self.lead = Lead.objects.create(
            company=self.company, nom='Transport', prenom='Fès',
            email='qjr604@example.com', ville='Douar X',
            ville_reference='Fès', taille_souhaitee_kwc=Decimal('5'),
            owner=self.user)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION='Bearer %s' % AccessToken.for_user(self.user))

    @staticmethod
    def _prix_transport_devis(devis):
        return {li.prix_unitaire for li in devis.lignes.all()
                if 'transport' in li.designation.lower()}

    def test_ville_du_lead_reference_prime(self):
        self.assertEqual(ville_du_lead(self.lead), 'Fès')
        self.assertEqual(ville_du_lead(None), '')

    def test_auto_layout_et_dry_run_meme_prix_transport(self):
        auto = self.api.post(AUTO_URL, {'lead': self.lead.id}, format='json')
        self.assertEqual(auto.status_code, 201, auto.data)
        devis_auto = Devis.objects.get(pk=auto.data['id'])
        self.assertEqual(self._prix_transport_devis(devis_auto),
                         {Decimal('2000.00')})

        layout = self.api.post(LAYOUT_URL,
                               {'layout': LAYOUT, 'lead': self.lead.id},
                               format='json')
        self.assertEqual(layout.status_code, 201, layout.data)
        devis_layout = Devis.objects.get(pk=layout.data['id'])
        self.assertEqual(self._prix_transport_devis(devis_layout),
                         {Decimal('2000.00')})

        blanc = self.api.post(COMPO_URL, {'kwc': 5, 'panel_watt': 710,
                                          'lead': self.lead.id},
                              format='json')
        self.assertEqual(blanc.status_code, 200, blanc.data)
        transport = [li for li in blanc.data['lignes']
                     if li['role'] == 'transport']
        self.assertEqual(len(transport), 1)
        self.assertEqual(Decimal(transport[0]['prix_unitaire_ht']),
                         Decimal('2000.00'))

    def test_marge_snapshot_calculee_apres_le_bareme(self):
        from apps.ventes.domain.etudes import compute_marge_snapshot
        auto = self.api.post(AUTO_URL, {'lead': self.lead.id}, format='json')
        self.assertEqual(auto.status_code, 201, auto.data)
        devis = Devis.objects.get(pk=auto.data['id'])
        self.assertIsNotNone(devis.marge_snapshot)
        self.assertEqual(devis.marge_snapshot, compute_marge_snapshot(devis))

    def test_dry_run_lead_d_une_autre_societe_404(self):
        from apps.crm.models import Lead
        autre, _ = Company.objects.get_or_create(
            slug='qjr604-autre', defaults={'nom': 'qjr604-autre'})
        etranger = Lead.objects.create(
            company=autre, nom='Etranger', ville='Fès')
        reponse = self.api.post(COMPO_URL, {'kwc': 5, 'panel_watt': 710,
                                            'lead': etranger.id},
                                format='json')
        self.assertEqual(reponse.status_code, 404, reponse.data)

    def test_dry_run_ville_texte_libre_n_est_plus_lue(self):
        blanc = self.api.post(COMPO_URL, {'kwc': 5, 'panel_watt': 710,
                                          'ville': 'Fès'}, format='json')
        self.assertEqual(blanc.status_code, 200, blanc.data)
        transport = [li for li in blanc.data['lignes']
                     if li['role'] == 'transport']
        self.assertEqual(Decimal(transport[0]['prix_unitaire_ht']),
                         Decimal('1000.00'))
