"""AOF144 — marque blanche de premier rang : soumissionnaire ≠ bureau.

Ce qui est prouvé ici :

* **aucun rendu client ne nomme le bureau** — test BINAIRE sur les artefacts
  réellement produits (mémoire, simulation, cartouche de planche) ;
* la bascule marque blanche ON/OFF est testée sur une pièce témoin ;
* **aucun champ d'identité n'est dupliqué** avec ``authentication.Company``
  (ni avec ``parametres.CompanyProfile``, lu par selector) ;
* le bureau sans identité déclarée est LU par
  ``parametres.selectors.company_identity``, jamais recopié.

Run :
    python manage.py test apps.ao.tests.test_aof_marque_blanche -v2
"""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.fabrique import identite as fabrique_identite
from apps.ao.fabrique.rendus import memoire as rendu_memoire
from apps.ao.fabrique.rendus import simulation as rendu_simulation
from apps.ao.models import (
    AppelOffre, BatimentAO, BordereauPrix, IdentiteAO, SimulationRentabilite,
    ToitureAO, VarianteCalepinage,
)
from authentication.models import Company

BUREAU = 'BUREAU ETUDES INTERNE SARL'
PARTENAIRE = 'ACCORDIA PARTENAIRE SA'


class TestAucuneDuplicationDIdentite(SimpleTestCase):
    def test_company_ne_porte_pas_ces_champs(self):
        champs_company = {f.name for f in Company._meta.get_fields()}
        for champ in ('ice', 'identifiant_fiscal', 'registre_commerce',
                      'rib', 'signataire_nom', 'raison_sociale'):
            self.assertNotIn(champ, champs_company, champ)

    def test_les_deux_roles_sont_declares(self):
        self.assertEqual(
            {v for v, _ in IdentiteAO.Role.choices},
            {'soumissionnaire', 'bureau_execution'})

    def test_le_logo_passe_par_records_attachment(self):
        champ = IdentiteAO._meta.get_field('logo')
        self.assertEqual(champ.related_model._meta.label, 'records.Attachment')


class BaseMarqueBlanche(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom=BUREAU, slug='aof144-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-144-1',
            objet='Centrale photovoltaïque', maitre_ouvrage='Fondation',
            marque_blanche=True)
        IdentiteAO.objects.create(
            company=self.company, appel_offre=self.ao,
            role=IdentiteAO.Role.SOUMISSIONNAIRE, raison_sociale=PARTENAIRE,
            ice='001234567000089', signataire_nom='M. Le Gérant')
        batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=batiment, code_document='05')
        self.variante = VarianteCalepinage.objects.create(
            company=self.company, toiture=self.toiture, appel_offre=self.ao,
            nom='Retenue', est_retenue=True,
            resultat={'total_modules': 314, 'kwc': '196.250'})


class TestResolutionDIdentite(BaseMarqueBlanche):
    def test_le_rendu_client_prend_le_soumissionnaire(self):
        self.assertEqual(
            fabrique_identite.identite_client(self.ao)['raison_sociale'],
            PARTENAIRE)

    def test_le_bureau_est_lu_par_selector_sans_identite_declaree(self):
        bureau = fabrique_identite.identite_bureau(self.ao)
        self.assertEqual(bureau['raison_sociale'], BUREAU)

    def test_une_identite_de_bureau_declaree_prime(self):
        IdentiteAO.objects.create(
            company=self.company, appel_offre=self.ao,
            role=IdentiteAO.Role.BUREAU_EXECUTION,
            raison_sociale='BUREAU DECLARE SARL', ice='X')
        self.assertEqual(
            fabrique_identite.identite_bureau(self.ao)['raison_sociale'],
            'BUREAU DECLARE SARL')

    def test_sans_marque_blanche_rien_n_est_a_masquer(self):
        self.ao.marque_blanche = False
        self.ao.save(update_fields=['marque_blanche'])
        self.assertEqual(fabrique_identite.noms_a_masquer(self.ao), [])

    def test_avec_marque_blanche_le_bureau_est_a_masquer(self):
        self.assertIn(BUREAU, fabrique_identite.noms_a_masquer(self.ao))

    def test_un_depot_en_nom_propre_confond_les_deux_roles(self):
        ao = AppelOffre.objects.create(
            company=self.company, reference='AO-144-PROPRE',
            objet='Nom propre')
        self.assertEqual(
            fabrique_identite.identite_client(ao)['raison_sociale'], BUREAU)


class TestControleBinaire(BaseMarqueBlanche):
    def test_un_artefact_qui_nomme_le_bureau_est_detecte(self):
        trouves = fabrique_identite.controler_absence_du_bureau(
            f'Réalisé par {BUREAU} pour le compte du partenaire.', self.ao)
        self.assertEqual(trouves, [BUREAU])

    def test_un_artefact_propre_passe(self):
        self.assertEqual(
            fabrique_identite.controler_absence_du_bureau(
                f'Le soumissionnaire {PARTENAIRE} propose…', self.ao), [])

    def test_marque_blanche_OFF_le_bureau_peut_etre_nomme(self):
        self.ao.marque_blanche = False
        self.ao.save(update_fields=['marque_blanche'])
        self.assertEqual(
            fabrique_identite.controler_absence_du_bureau(
                f'Réalisé par {BUREAU}.', self.ao), [])


class TestArtefactsReels(BaseMarqueBlanche):
    """La pièce TÉMOIN : le mémoire, produit pour de vrai, ON puis OFF."""

    def setUp(self):
        super().setUp()
        call_command('seed_sections_memoire', company='aof144-co',
                     stdout=StringIO())

    def test_le_memoire_ne_nomme_jamais_le_bureau(self):
        html = rendu_memoire.rendre_memoire_html(self.ao)
        self.assertIn(PARTENAIRE, html)
        self.assertEqual(
            fabrique_identite.controler_absence_du_bureau(html, self.ao), [])
        self.assertNotIn(BUREAU, html)

    def test_bascule_ON_OFF_sur_la_piece_temoin(self):
        html_on = rendu_memoire.rendre_memoire_html(self.ao)
        self.assertIn(PARTENAIRE, html_on)
        self.assertNotIn(BUREAU, html_on)
        # OFF : le soumissionnaire déclaré reste prioritaire (c'est bien LUI
        # qui dépose), mais plus rien n'est « à masquer ».
        self.ao.marque_blanche = False
        self.ao.save(update_fields=['marque_blanche'])
        self.assertEqual(fabrique_identite.noms_a_masquer(self.ao), [])

    def test_le_cartouche_de_planche_porte_le_soumissionnaire(self):
        planche, _ = services.generer_indice_planche(
            self.ao, '05', empreinte='abc', variante=self.variante,
            toiture=self.toiture)
        self.assertEqual(planche.cartouche['soumissionnaire'], PARTENAIRE)
        self.assertNotIn(BUREAU, str(planche.cartouche))

    def test_la_simulation_client_porte_le_soumissionnaire(self):
        bordereau = BordereauPrix.objects.create(
            company=self.company, appel_offre=self.ao,
            clause_reserve='Prix unitaires.')
        simulation = SimulationRentabilite.objects.create(
            company=self.company, appel_offre=self.ao, bordereau=bordereau,
            productible_kwh_par_kwc_an=Decimal('1600.00'),
            tarif_kwh=Decimal('1.1405'))
        contexte = rendu_simulation.contexte_simulation(simulation)
        self.assertEqual(contexte['soumissionnaire'], PARTENAIRE)
        html = rendu_simulation.html_simulation(simulation)
        self.assertEqual(
            fabrique_identite.controler_absence_du_bureau(html, self.ao), [])
