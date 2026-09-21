"""CALX46 — le calepinage d'un devis est PUBLIÉ, et il l'est SUR LE CONTRAT.

POURQUOI CE FICHIER EXISTE À CÔTÉ DE ``test_selector_calepinage.py``
--------------------------------------------------------------------
Ce dernier prouve que le sélecteur et le sérialiseur rendent bien
``{id, titre, layout_hash, a_jour}`` — mais il l'affirme AVEC SES PROPRES
MOTS. C'est exactement la deuxième source de vérité qui a tué l'écran « AO
Tableau de bord » le 03/08/2026 : deux suites vertes, chacune vérifiant sa
propre hypothèse, personne ne vérifiant le LIEN.

Ici, la forme attendue n'est pas retapée : elle est LUE dans le document
partagé ``apps/calepinage/contract_samples/calepinage_du_devis.json``
(CALX45), le MÊME fichier que le test d'écran
``frontend/src/features/ventes/BlocCalepinageDevis.test.jsx`` importe. Si le
serveur change de forme, l'exemple doit changer, et les DEUX suites cassent
ensemble — sans réunion, sans discipline humaine.

Ce qui est prouvé :

* les quatre états du contrat (à jour / à rejouer / inconnu / aucun) portent
  EXACTEMENT les clés que le serveur sert ;
* un devis SANS calepinage publie la clé ``calepinage`` à ``None`` — clé
  PRÉSENTE, jamais absente, jamais un objet vide (le bloc disparaît alors de
  l'écran au lieu d'afficher un cadre creux) ;
* un calepinage PÉRIMÉ publie ``a_jour: False`` — le badge « à rejouer » ;
* une empreinte manquante d'un côté publie ``a_jour: None`` (INCONNU), jamais
  ``False`` : on ne déclare pas « périmé » ce qu'on n'a pas mesuré ;
* le calepinage d'une AUTRE société n'est jamais servi (multi-tenant) ;
* le champ est en LECTURE SEULE — la donnée appartient à ``apps.calepinage``.

Run :
    python manage.py test apps.ventes.tests.test_calx46_calepinage_du_devis -v2
"""
import json
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from apps.calepinage.models import Calepinage
from apps.ventes.selectors import calepinage_du_devis
from apps.ventes.serializers import DevisSerializer
from testkit.factories import ClientFactory, CompanyFactory, DevisFactory

#: Le document PARTAGÉ (PACT10) — jamais une charge utile retapée ici.
CONTRAT = (Path(__file__).resolve().parents[2] / 'calepinage'
           / 'contract_samples' / 'calepinage_du_devis.json')

#: Les empreintes d'essai : visiblement factices, jamais un vrai hash client.
EMPREINTE = 'a' * 64
EMPREINTE_AUTRE = 'b' * 64


def document():
    return json.loads(CONTRAT.read_text(encoding='utf-8'))


def bloc_du_contrat(variante='exemple'):
    """Le bloc ``calepinage`` d'un état du contrat committé."""
    return document()[variante]['calepinage']


class ContratCalepinageDuDevisTest(SimpleTestCase):
    """Le document partagé est complet et dit bien ce qu'il prétend dire."""

    def test_le_document_porte_les_trois_cles_du_format(self):
        doc = document()
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(cle, doc, f'clé « {cle} » absente du contrat.')

    def test_l_endpoint_est_le_detail_d_un_devis(self):
        self.assertEqual(document()['endpoint'],
                         'GET /api/django/ventes/devis/<int:pk>/')

    def test_les_quatre_etats_existent_et_partagent_la_meme_forme(self):
        doc = document()
        attendues = {'id', 'titre', 'layout_hash', 'a_jour'}
        for variante, a_jour in (('exemple', True),
                                 ('exemple_a_rejouer', False),
                                 ('exemple_inconnu', None)):
            self.assertIn(variante, doc, variante)
            bloc = doc[variante]['calepinage']
            self.assertEqual(set(bloc), attendues, variante)
            self.assertIs(bloc['a_jour'], a_jour, variante)

    def test_l_etat_vide_garde_la_cle_a_none_jamais_un_objet_creux(self):
        vide = document()['exemple_vide']
        self.assertIn('calepinage', vide)
        self.assertIsNone(vide['calepinage'])

    def test_l_etat_inconnu_n_invente_aucune_empreinte(self):
        self.assertIsNone(bloc_du_contrat('exemple_inconnu')['layout_hash'])


class CalepinageDuDevisServiTest(TestCase):
    """Ce que le serveur SERT, comparé clé pour clé à l'exemple committé."""

    @classmethod
    def setUpTestData(cls):
        cls.company = CompanyFactory()
        cls.voisine = CompanyFactory()
        cls.client_a = ClientFactory(company=cls.company)

    def _devis(self, empreinte=EMPREINTE):
        return DevisFactory(company=self.company, client=self.client_a,
                            layout_hash=empreinte)

    def _calepinage(self, devis, empreinte=EMPREINTE, company=None):
        # CALX46 — la contrainte `calepinage_lead_ou_client` exige un lead OU un
        # client : la société voisine reçoit SON propre client (jamais `None`).
        societe = company or self.company
        client = self.client_a if company is None else ClientFactory(company=societe)
        return Calepinage.objects.create(
            company=societe, client=client,
            devis=devis, titre="Toiture d'essai", layout_hash=empreinte)

    def _servi(self, devis):
        return DevisSerializer(devis).data['calepinage']

    def _comparer_au_contrat(self, servi, variante):
        attendu = bloc_du_contrat(variante)
        self.assertEqual(
            sorted(set(attendu) - set(servi)), [],
            f"{variante} : le serveur ne sert PAS la ou les clés "
            f"{sorted(set(attendu) - set(servi))} que le contrat promet.")
        self.assertEqual(
            sorted(set(servi) - set(attendu)), [],
            f"{variante} : le serveur sert la ou les clés "
            f"{sorted(set(servi) - set(attendu))} que le contrat ignore.")

    def test_a_jour_vrai_la_forme_est_celle_du_contrat(self):
        devis = self._devis()
        self._calepinage(devis)
        servi = self._servi(devis)
        self._comparer_au_contrat(servi, 'exemple')
        self.assertIs(servi['a_jour'], True)
        self.assertEqual(servi['titre'], "Toiture d'essai")
        self.assertEqual(servi['layout_hash'], EMPREINTE)

    def test_calepinage_perime_le_badge_a_rejouer(self):
        devis = self._devis()
        self._calepinage(devis, empreinte=EMPREINTE_AUTRE)
        servi = self._servi(devis)
        self._comparer_au_contrat(servi, 'exemple_a_rejouer')
        self.assertIs(servi['a_jour'], False)

    def test_empreinte_manquante_a_jour_inconnu_jamais_faux(self):
        devis = self._devis(empreinte='')
        self._calepinage(devis)
        servi = self._servi(devis)
        self._comparer_au_contrat(servi, 'exemple_inconnu')
        self.assertIsNone(servi['a_jour'])

    def test_calepinage_sans_empreinte_publie_layout_hash_none(self):
        devis = self._devis()
        self._calepinage(devis, empreinte='')
        servi = self._servi(devis)
        self._comparer_au_contrat(servi, 'exemple_inconnu')
        self.assertIsNone(servi['a_jour'])
        self.assertIsNone(servi['layout_hash'])

    def test_devis_sans_calepinage_la_cle_est_presente_et_nulle(self):
        devis = self._devis()
        donnees = DevisSerializer(devis).data
        self.assertIn('calepinage', donnees)
        self.assertIsNone(donnees['calepinage'])
        self.assertIsNone(document()['exemple_vide']['calepinage'])

    def test_calepinage_d_une_autre_societe_jamais_servi(self):
        devis = self._devis()
        self._calepinage(devis, company=self.voisine)
        self.assertIsNone(self._servi(devis))
        self.assertIsNone(calepinage_du_devis(devis))

    def test_le_selecteur_et_le_serialiseur_rendent_le_meme_bloc(self):
        devis = self._devis()
        self._calepinage(devis)
        self.assertEqual(self._servi(devis), calepinage_du_devis(devis))

    def test_en_liste_la_cle_vaut_none_pas_une_requete_par_devis(self):
        devis = self._devis()
        self._calepinage(devis)
        lignes = DevisSerializer([devis], many=True).data
        self.assertIsNone(lignes[0]['calepinage'])

    def test_le_champ_est_en_lecture_seule(self):
        self.assertTrue(DevisSerializer().fields['calepinage'].read_only)
