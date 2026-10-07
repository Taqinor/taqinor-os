"""CAL185 / ACAL108 — un calepinage se chiffre par SON « Générer le devis ».

ACAL108 (D-ACAL-2) a RETIRÉ la porte jumelle ``from-layout {calepinage}`` et
``build_devis_depuis_calepinage_retenu`` : retenir une variante l'écrit comme
conception courante, que ``generer-devis`` du calepinage chiffre. Ce qui est
prouvé ici :

* ``POST from-layout {calepinage}`` sans ``layout`` ⇒ 422 ``{detail, champ}``
  NOMMÉ, et AUCUN devis ni AUCUN calepinage créé (comptage) — même avec une
  variante retenue ;
* un ``layout`` explicite garde la réponse historique (aucune clé CAL185) ;
* ``produits_a_renseigner`` (liste « à renseigner » du kit) reste sans
  montant et borné société.

Run :
    python manage.py test apps.ventes.tests.test_cal185_bom_vers_devis -v2
"""
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.variantes import creer_variante
from apps.crm.models import Client
from apps.roles.models import Role
from apps.roles.permissions_registre import DIRECTEUR_PERMISSIONS
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import produits_a_renseigner
from authentication.models import Company, CustomUser

#: Une conception RÉELLE, minimale : un contour, un pan, des modules posés.
#: Le ``result`` est ce que l'atelier 3D stocke et ce que la composition lit.
LAYOUT_RETENU = {
    'version': 2,
    'outline': [[33.5, -7.6], [33.5, -7.5990], [33.5009, -7.5990],
                [33.5009, -7.6]],
    'panelWatt': 550,
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10200, 'savings': 9000},
    'zones': [{
        'id': 'z1', 'label': 'Pan Sud',
        'vertices': [[-7.6, 33.5], [-7.5990, 33.5], [-7.5990, 33.5009],
                     [-7.6, 33.5009]],
        'geometry': {
            'azimuthDeg': 180.0, 'tiltDeg': 15.0, 'count': 12,
            'origin': [-7.6, 33.5],
            'panels': [{'cx': 1.0 + 2.0 * i, 'cy': 1.0} for i in range(12)],
        },
    }],
}

#: La conception du calepinage PARENT — volontairement DIFFÉRENTE (4 modules).
#: Si le chiffrage retombait dessus, le compte de panneaux le dirait.
LAYOUT_PARENT = dict(
    LAYOUT_RETENU,
    result={'panels': 4, 'kwc': 2.2, 'annualKwh': 3400, 'savings': 3000})


class Cal185BomVersDevisTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Cal185 Co',
                                              slug='cal185-co')
        self.user = CustomUser.objects.create_user(
            username='cal185', password='x', company=self.company)
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Atlas 185')
        self._seed_catalogue()
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj,
            titre='Villa Anfa', roof_layout=LAYOUT_PARENT)

    def _produit(self, nom, prix_vente, **extra):
        return Produit.objects.create(
            company=self.company, nom=nom,
            prix_vente=Decimal(str(prix_vente)),
            prix_achat=Decimal('1'), quantite_stock=100,
            seuil_alerte=0, **extra)

    def _seed_catalogue(self):
        """Le strict nécessaire pour qu'un toit résidentiel se compose."""
        self._produit('Panneau mono 550W', '1100')
        self._produit('Onduleur réseau 10kW', '11700')
        self._produit('Structures acier', '375')
        self._produit('Socles', '67')
        self._produit('Accessoires', '1667')
        self._produit('Tableau De Protection AC/DC', '1667')
        self._produit('Installation', '4000')
        self._produit('Transport', '1000')

    def test_a_renseigner_ne_porte_aucun_montant(self):
        self._produit('Batterie 5 kWh', '0')
        for item in produits_a_renseigner(self.company):
            self.assertEqual(set(item),
                             {'produit', 'designation', 'famille'})

    def test_un_catalogue_entierement_tarife_ne_signale_rien(self):
        self.assertEqual(produits_a_renseigner(self.company), [])

    def test_a_renseigner_ignore_ce_qui_n_est_pas_du_kit(self):
        """Un service ou un accessoire sans prix n'a jamais été attendu du
        chiffrage automatique : le signaler serait du bruit."""
        self._produit('Prestation de nettoyage', '0')
        self.assertEqual(produits_a_renseigner(self.company), [])

    def test_le_catalogue_d_une_autre_societe_ne_fuite_pas(self):
        autre = Company.objects.create(nom='Voisine 185b', slug='voisine-185b')
        Produit.objects.create(company=autre, nom='Panneau mono 400W',
                               prix_vente=Decimal('0'),
                               prix_achat=Decimal('1'), quantite_stock=1,
                               seuil_alerte=0)
        self.assertEqual(produits_a_renseigner(self.company), [])


class Cal185FromLayoutTest(TestCase):
    """ACAL108 — ``from-layout {calepinage}`` est REFUSÉ (porte jumelle
    retirée) ; un corps qui porte un ``layout`` explicite est inchangé."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.company = Company.objects.create(nom='Cal185 API',
                                              slug='cal185-api')
        # ``CustomUser.role`` est une FK vers ``roles.Role`` : un littéral
        # 'admin' n'est pas un rôle, il lève à la création.
        self.role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = CustomUser.objects.create_user(
            username='cal185api', password='x', company=self.company,
            role=self.role)
        self.client_obj = Client.objects.create(company=self.company,
                                                nom='Atlas API')
        for nom, prix in (('Panneau mono 550W', '1100'),
                          ('Onduleur réseau 10kW', '11700'),
                          ('Structures acier', '375'), ('Socles', '67'),
                          ('Accessoires', '1667'),
                          ('Tableau De Protection AC/DC', '1667'),
                          ('Installation', '4000'), ('Transport', '1000')):
            Produit.objects.create(
                company=self.company, nom=nom, prix_vente=Decimal(prix),
                prix_achat=Decimal('1'), quantite_stock=100, seuil_alerte=0)
        self.sans_prix = Produit.objects.create(
            company=self.company, nom='Batterie 5 kWh',
            prix_vente=Decimal('0'), prix_achat=Decimal('1'),
            quantite_stock=10, seuil_alerte=0)
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_obj,
            titre='Villa API', roof_layout=LAYOUT_PARENT)
        self.api = APIClient()
        self.api.force_authenticate(user=self.user)

    def _poster(self, corps):
        return self.api.post('/api/django/ventes/devis/from-layout/', corps,
                             format='json')

    def test_calepinage_sans_layout_refuse_sans_creer(self):
        creer_variante(self.calepinage, nom='Option A',
                       roof_layout=LAYOUT_RETENU, retenir=True)
        devis_avant = Devis.objects.count()
        calepinages_avant = Calepinage.objects.count()
        reponse = self._poster({'calepinage': self.calepinage.pk,
                                'client': self.client_obj.pk})
        self.assertEqual(reponse.status_code, 422, reponse.data)
        self.assertEqual(set(reponse.data) & {'detail', 'champ'},
                         {'detail', 'champ'})
        self.assertEqual(reponse.data['champ'], 'calepinage')
        self.assertIn('Générer le devis', reponse.data['detail'])
        self.assertEqual(Devis.objects.count(), devis_avant)
        self.assertEqual(Calepinage.objects.count(), calepinages_avant)

    def test_layout_explicite_inchange(self):
        reponse = self._poster({'layout': LAYOUT_RETENU,
                                'calepinage': self.calepinage.pk,
                                'client': self.client_obj.pk})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        for clef in ('calepinage', 'variante', 'a_renseigner'):
            self.assertNotIn(clef, reponse.data)

    def test_l_entree_historique_ne_porte_aucune_cle_nouvelle(self):
        reponse = self._poster({'layout': LAYOUT_RETENU,
                                'client': self.client_obj.pk})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        for clef in ('calepinage', 'variante', 'a_renseigner'):
            self.assertNotIn(clef, reponse.data)

    def test_sans_layout_ni_calepinage_le_refus_reste_celui_d_avant(self):
        reponse = self._poster({'client': self.client_obj.pk})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertEqual(reponse.data['detail'],
                         'Layout manquant ou invalide.')
