"""CAL185 — la nomenclature de la VARIANTE RETENUE devient des lignes de devis.

Ce qui est prouvé ici :

* un calepinage dont une variante est RETENUE produit un devis dont CHAQUE
  ligne produit pointe un ``stock.Produit`` réel du catalogue ;
* c'est la conception de la VARIANTE qui est chiffrée — jamais un repli
  silencieux sur celle du calepinage parent (ce serait chiffrer autre chose
  que ce que le commercial a retenu) ;
* aucune variante retenue ⇒ refus NOMMÉ, jamais un devis approximatif ;
* un produit du kit SANS prix de vente n'est jamais chiffré (garde existante)
  et il est désormais LISTÉ « à renseigner » au lieu de disparaître en
  silence ;
* aucun second chemin de création de lignes : la fonction délègue à
  ``build_devis_from_layout`` ;
* ``apps.ventes`` n'importe aucun modèle de ``apps.calepinage``.

Run :
    python manage.py test apps.ventes.tests.test_cal185_bom_vers_devis -v2
"""
import inspect
from decimal import Decimal

from django.test import TestCase

from apps.calepinage.models import Calepinage, CalepinageVariante
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.services import (
    build_devis_depuis_calepinage_retenu, produits_a_renseigner,
)
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

    def _retenir(self, layout=LAYOUT_RETENU, nom='Option A'):
        return CalepinageVariante.objects.create(
            calepinage=self.calepinage, nom=nom, roof_layout=layout,
            layout_hash='cal185cal185cal1' * 4, retenue=True)

    # ── le chiffrage ──────────────────────────────────────────────────────
    def test_chaque_ligne_pointe_un_produit_du_catalogue(self):
        self._retenir()
        devis, rapport = build_devis_depuis_calepinage_retenu(
            calepinage_id=self.calepinage.pk, user=self.user,
            company=self.company, client=self.client_obj)

        lignes = list(devis.lignes.filter(type_ligne='produit'))
        self.assertTrue(lignes, 'le devis doit porter des lignes produit')
        catalogue = set(Produit.objects.filter(company=self.company)
                        .values_list('pk', flat=True))
        for ligne in lignes:
            self.assertIsNotNone(ligne.produit_id, ligne.designation)
            self.assertIn(ligne.produit_id, catalogue, ligne.designation)
        self.assertEqual(rapport['variante'],
                         self.calepinage.variantes.get().pk)

    def test_c_est_la_variante_retenue_qui_est_chiffree(self):
        """Et JAMAIS un repli silencieux sur la conception du parent."""
        self._retenir()
        devis, _ = build_devis_depuis_calepinage_retenu(
            calepinage_id=self.calepinage.pk, user=self.user,
            company=self.company, client=self.client_obj)
        panneaux = devis.lignes.filter(designation__icontains='panneau').first()
        self.assertIsNotNone(panneaux)
        # 12 modules (la variante), pas 4 (le parent).
        self.assertEqual(int(panneaux.quantite), 12)

    def test_le_devis_porte_l_empreinte_de_la_variante(self):
        variante = self._retenir()
        devis, rapport = build_devis_depuis_calepinage_retenu(
            calepinage_id=self.calepinage.pk, user=self.user,
            company=self.company, client=self.client_obj)
        devis.refresh_from_db()
        self.assertEqual(devis.layout_hash, variante.layout_hash)
        self.assertEqual(rapport['layout_hash'], variante.layout_hash)

    def test_aucune_variante_retenue_refus_nomme(self):
        CalepinageVariante.objects.create(
            calepinage=self.calepinage, nom='Option A',
            roof_layout=LAYOUT_RETENU, retenue=False)
        with self.assertRaises(ValueError) as capture:
            build_devis_depuis_calepinage_retenu(
                calepinage_id=self.calepinage.pk, user=self.user,
                company=self.company, client=self.client_obj)
        self.assertIn('retenue', str(capture.exception).lower())

    def test_variante_sans_conception_ne_chiffre_rien(self):
        CalepinageVariante.objects.create(
            calepinage=self.calepinage, nom='Esquisse', roof_layout=None,
            retenue=True)
        with self.assertRaises(ValueError):
            build_devis_depuis_calepinage_retenu(
                calepinage_id=self.calepinage.pk, user=self.user,
                company=self.company, client=self.client_obj)

    def test_un_calepinage_d_une_autre_societe_n_est_jamais_chiffre(self):
        autre = Company.objects.create(nom='Voisine 185', slug='voisine-185')
        self._retenir()
        with self.assertRaises(ValueError):
            build_devis_depuis_calepinage_retenu(
                calepinage_id=self.calepinage.pk, user=self.user,
                company=autre, client=self.client_obj)

    # ── la garde « produit sans prix » ────────────────────────────────────
    def test_un_produit_sans_prix_est_liste_a_renseigner_pas_chiffre(self):
        sans_prix = self._produit('Batterie 5 kWh', '0')
        self._retenir()
        devis, rapport = build_devis_depuis_calepinage_retenu(
            calepinage_id=self.calepinage.pk, user=self.user,
            company=self.company, client=self.client_obj)

        # JAMAIS chiffré...
        self.assertFalse(
            devis.lignes.filter(produit_id=sans_prix.pk).exists(),
            'un produit sans prix de vente ne doit jamais être chiffré')
        # ...mais NOMMÉ, au lieu de disparaître en silence.
        listes = {item['produit']: item for item in rapport['a_renseigner']}
        self.assertIn(sans_prix.pk, listes)
        self.assertEqual(listes[sans_prix.pk]['designation'], 'Batterie 5 kWh')
        self.assertEqual(listes[sans_prix.pk]['famille'], 'batterie')

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

    # ── aucun second chemin ───────────────────────────────────────────────
    def test_aucun_second_chemin_de_creation_de_lignes(self):
        source = inspect.getsource(build_devis_depuis_calepinage_retenu)
        self.assertIn('build_devis_from_layout', source)
        # Elle n'écrit aucune ligne elle-même.
        for interdit in ('creer_ligne', 'LigneDevis'):
            self.assertNotIn(interdit, source)

    def test_la_lecture_cross_app_passe_par_les_selecteurs(self):
        source = inspect.getsource(build_devis_depuis_calepinage_retenu)
        self.assertIn('apps.calepinage.selectors', source)
        self.assertNotIn('apps.calepinage.models', source)


class Cal185FromLayoutTest(TestCase):
    """CAL185 — ``from-layout`` consomme la variante retenue, par LA porte.

    Le corps ``{"calepinage": <id>}`` (sans ``layout``) est une DEUXIÈME
    ENTRÉE sur le MÊME chemin de création de lignes ; un corps qui porte un
    ``layout`` explicite reste byte-identique.
    """

    def setUp(self):
        from rest_framework.test import APIClient

        self.company = Company.objects.create(nom='Cal185 API',
                                              slug='cal185-api')
        self.user = CustomUser.objects.create_user(
            username='cal185api', password='x', company=self.company,
            role='admin')
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

    def test_sans_variante_retenue_le_refus_nomme_le_champ(self):
        reponse = self._poster({'calepinage': self.calepinage.pk,
                                'client': self.client_obj.pk})
        self.assertEqual(reponse.status_code, 422, reponse.data)
        self.assertEqual(reponse.data['champ'], 'calepinage')

    def test_la_variante_retenue_produit_un_devis_et_la_liste_a_renseigner(self):
        variante = CalepinageVariante.objects.create(
            calepinage=self.calepinage, nom='Option A',
            roof_layout=LAYOUT_RETENU, layout_hash='cal185cal185cal1' * 4,
            retenue=True)
        reponse = self._poster({'calepinage': self.calepinage.pk,
                                'client': self.client_obj.pk})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(reponse.data['variante'], variante.pk)
        self.assertEqual(reponse.data['calepinage'], self.calepinage.pk)
        listes = {item['produit'] for item in reponse.data['a_renseigner']}
        self.assertIn(self.sans_prix.pk, listes)

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
