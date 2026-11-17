"""TCH13 — liens ERP vérifiés (`selectors/liens.py`).

Deux familles :
- `GabaritsSansBaseTests` (SimpleTestCase, sans base) : gabarits = `liens_cibles.json` = `CibleLiable`,
  adresses, refus d'une cible hors `CibleLiable` SANS aucune requête (une requête lèverait ici).
- `PortesTests` (TestCase, CI) : de vraies lignes `crm` et `ventes`, lues par les portes publiques
  `libelles_crm` / `libelles_ventes` ; un commercial hors portée reçoit la même réponse qu'un
  objet inexistant.
"""
import json
from decimal import Decimal

from django.apps import apps as registre
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.roles.models import Role
from apps.taches.choix import CibleLiable
from apps.taches.selectors import liens
from apps.taches.tests import fabriques

ADRESSES = {
    'crm.lead': '/crm/leads?lead=9',
    'crm.client': '/crm?id=9',
    'ventes.devis': '/ventes/devis?devis=9',
}


class GabaritsSansBaseTests(SimpleTestCase):
    def test_gabarits_recopies_du_contrat(self):
        document = json.loads(liens.FICHIER_GABARITS.read_text(encoding='utf-8'))
        self.assertEqual(liens.gabarits(), document['exemple'])

    def test_une_cle_par_cible_liable(self):
        self.assertEqual(set(liens.gabarits()), set(CibleLiable.values))

    def test_adresse_de_chaque_cible(self):
        for cible, attendue in ADRESSES.items():
            with self.subTest(cible=cible):
                self.assertEqual(liens.url_de_cible(cible, 9), attendue)

    def test_adresse_refusee_hors_gabarit_ou_id_invalide(self):
        for cible, pk in (('visites.visitetechnique', 9), ('crm.lead', 0), ('crm.lead', -3),
                          ('crm.lead', True), ('crm.lead', '9'), ('crm.lead', None),
                          ('crm.lead', liens.ID_MAX + 1), (None, 9)):
            with self.subTest(cible=cible, pk=pk):
                self.assertIsNone(liens.url_de_cible(cible, pk))

    def test_cible_hors_cible_liable_refusee_sans_requete(self):
        # SimpleTestCase : toute requête lèverait — le refus se décide avant les portes.
        compte = get_user_model()(pk=1, company_id=1)
        for cible in ('visites.visitetechnique', 'facturation.facture', 'crm', '', None):
            with self.subTest(cible=cible):
                self.assertFalse(liens.est_liable(cible))
                self.assertIsNone(liens.libelle_de_cible(compte, cible, 9))
                self.assertFalse(liens.cible_visible(compte, cible, 9))

    def test_id_invalide_refuse_sans_requete(self):
        compte = get_user_model()(pk=1, company_id=1)
        for pk in (0, -1, True, '12', None, 2.5):
            with self.subTest(pk=pk):
                self.assertFalse(liens.cible_visible(compte, 'crm.lead', pk))


def _role(societe, nom, permissions):
    return Role.objects.create(company=societe, nom=nom, permissions=permissions)


def _utilisateur(societe, nom, permissions):
    return get_user_model().objects.create_user(
        username=f'{nom}@{societe.slug}', password=None, company=societe,
        role=_role(societe, f'Rôle {nom}', permissions), first_name=nom)


class PortesTests(TestCase):
    """De vraies lignes : `crm.Lead`, `crm.Client`, `ventes.Devis` (lus par le registre
    d'applications, jamais importés : la frontière entre apps tient aussi dans les tests)."""

    @classmethod
    def setUpTestData(cls):
        Lead = registre.get_model('crm', 'Lead')
        Client = registre.get_model('crm', 'Client')
        Devis = registre.get_model('ventes', 'Devis')
        cls.a, cls.b = fabriques.societe('a'), fabriques.societe('b')
        droits = ['taches_voir', 'crm_voir', 'ventes_voir']
        cls.commercial = _utilisateur(cls.a, 'commercial', droits + ['records_scope_soi'])
        cls.collegue = _utilisateur(cls.a, 'collegue', droits + ['records_scope_soi'])
        cls.sans_crm = _utilisateur(cls.a, 'sanscrm', ['taches_voir'])
        cls.lead_a_lui = Lead.objects.create(
            company=cls.a, nom='Benali', prenom='Karim', ville='Casablanca', owner=cls.commercial)
        cls.lead_collegue = Lead.objects.create(company=cls.a, nom='Alami', owner=cls.collegue)
        cls.lead_autre_societe = Lead.objects.create(company=cls.b, nom='Ailleurs')
        cls.client_crm = Client.objects.create(
            company=cls.a, nom='Benali', prenom='Karim', email='karim.tch13@example.invalid')
        cls.devis_a_lui = Devis.objects.create(
            company=cls.a, reference='DEV-TCH13-0001', client=cls.client_crm,
            taux_tva=Decimal('20'), created_by=cls.commercial)
        cls.devis_collegue = Devis.objects.create(
            company=cls.a, reference='DEV-TCH13-0002', client=cls.client_crm,
            taux_tva=Decimal('20'), created_by=cls.collegue)

    def test_lead_en_portee_visible_avec_son_libelle(self):
        libelle = liens.libelle_de_cible(self.commercial, 'crm.lead', self.lead_a_lui.pk)
        self.assertEqual(libelle, 'Karim Benali — Casablanca')
        self.assertTrue(liens.cible_visible(self.commercial, 'crm.lead', self.lead_a_lui.pk))

    def test_commercial_hors_portee_refus_egal_introuvable(self):
        hors_portee = liens.libelle_de_cible(self.commercial, 'crm.lead', self.lead_collegue.pk)
        inexistant = liens.libelle_de_cible(self.commercial, 'crm.lead', 987654)
        self.assertIsNone(hors_portee)
        self.assertEqual(hors_portee, inexistant)
        self.assertFalse(liens.cible_visible(self.commercial, 'crm.lead', self.lead_collegue.pk))

    def test_autre_societe_introuvable(self):
        self.assertFalse(liens.cible_visible(self.commercial, 'crm.lead', self.lead_autre_societe.pk))

    def test_sans_droit_crm_rien_n_est_visible(self):
        self.assertFalse(liens.cible_visible(self.sans_crm, 'crm.lead', self.lead_a_lui.pk))
        self.assertFalse(liens.cible_visible(self.sans_crm, 'ventes.devis', self.devis_a_lui.pk))

    def test_devis_par_la_porte_des_ventes(self):
        self.assertTrue(liens.cible_visible(self.commercial, 'ventes.devis', self.devis_a_lui.pk))
        self.assertTrue(liens.libelle_de_cible(
            self.commercial, 'ventes.devis', self.devis_a_lui.pk).startswith('DEV-TCH13-0001'))
        self.assertFalse(liens.cible_visible(self.commercial, 'ventes.devis', self.devis_collegue.pk))

    def test_client_par_la_porte_du_crm(self):
        self.assertEqual(liens.libelle_de_cible(self.commercial, 'crm.client', self.client_crm.pk),
                         'Benali Karim')

    def test_cible_hors_cible_liable_refusee_meme_existante(self):
        self.assertFalse(liens.cible_visible(self.commercial, 'ventes.facture', self.devis_a_lui.pk))
