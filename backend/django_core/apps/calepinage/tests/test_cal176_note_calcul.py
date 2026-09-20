"""CAL176 — la note de calcul lit le moteur, source ses hypothèses, ou refuse.

Essais PURS (ni base, ni WeasyPrint) : la note se construit depuis le
dictionnaire ``Calepinage.resultat``, dont la forme est FIGÉE par
``contract_samples/calepinage_resultat.json`` — c'est ce fichier qui sert de
donnée d'essai, jamais un dictionnaire réécrit à la main (PACT13 : un mock
écrit à la main est une seconde source de vérité).

Ce qui est prouvé :

* la note se rend depuis un résultat complet ;
* RETIRER LA SOURCE D'IRRADIANCE fait échouer le rendu en NOMMANT la grandeur
  — jamais un zéro, jamais un blanc ;
* chaque hypothèse paraît avec sa source, et une source absente est AVOUÉE
  plutôt qu'inventée ;
* aucune grandeur de coût (``prix_achat``, marge…) ne franchit la fabrique ;
* l'empreinte d'entrée et la version du moteur sont dans la marge de CHAQUE
  page, pas seulement sur la première.

Run :
    python manage.py test apps.calepinage.tests.test_cal176_note_calcul -v2
"""
import copy
import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.note_calcul import (
    NoteRefusee, construire_note_calcul, html_de_note_calcul,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
ECHANTILLON = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))


def resultat():
    """Le résultat du CONTRAT, copié — jamais un dictionnaire réécrit."""
    return copy.deepcopy(ECHANTILLON['exemple'])


SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle',
        'source': 'roof_point', 'pin': None, 'outline': None}


class ConstructionTest(SimpleTestCase):
    def test_la_note_se_construit_depuis_un_resultat_complet(self):
        note = construire_note_calcul(resultat(), site=SITE)
        self.assertEqual(note['pose']['total_modules'], 12)
        self.assertEqual(note['site']['ville'], 'Bouskoura')
        self.assertEqual(note['site']['source_irradiance'], 'PVGIS')
        self.assertEqual(len(note['pose']['pans']), 2)
        self.assertTrue(note['provenance']['hash_entree'])

    def test_sans_resultat_la_note_refuse(self):
        for vide in (None, {}, []):
            with self.assertRaises(NoteRefusee) as capture:
                construire_note_calcul(vide, site=SITE)
            self.assertEqual(capture.exception.champ, 'resultat')

    def test_retirer_la_source_d_irradiance_fait_echouer_le_rendu(self):
        donnees = resultat()
        donnees['production']['base'].pop('source')
        with self.assertRaises(NoteRefusee) as capture:
            construire_note_calcul(donnees, site=SITE)
        message = str(capture.exception)
        self.assertIn("source de l'irradiance", message)
        self.assertEqual(capture.exception.champ, 'production.base.source')

    def test_chaque_grandeur_indispensable_est_nommee_quand_elle_manque(self):
        for chemin, sous_cle in (('pose', 'total_modules'),
                                 ('pose', 'kwc'),
                                 ('production.total', 'p50_kwh')):
            donnees = resultat()
            noeud = donnees
            for cle in chemin.split('.'):
                noeud = noeud[cle]
            noeud.pop(sous_cle)
            with self.assertRaises(NoteRefusee) as capture:
                construire_note_calcul(donnees, site=SITE)
            self.assertIn(sous_cle, capture.exception.champ)

    def test_une_source_de_perte_absente_est_avouee_jamais_inventee(self):
        note = construire_note_calcul(resultat(), site=SITE)
        sources = {p['poste']: p['source'] for p in note['pertes']}
        # `availability` porte `source: null` dans le contrat : on l'avoue.
        self.assertEqual(sources['availability'], 'source non renseignée')
        self.assertEqual(sources['temperature'], 'hypothèse société')
        self.assertEqual(sources['inverter'], 'fiche produit')


class EtancheiteTest(SimpleTestCase):
    def test_une_grandeur_de_cout_est_refusee_a_l_entree(self):
        donnees = resultat()
        donnees['pose']['prix_achat_total'] = 12345
        with self.assertRaises(NoteRefusee) as capture:
            construire_note_calcul(donnees, site=SITE)
        self.assertIn('prix_achat', str(capture.exception))

    def test_aucune_mention_de_prix_dans_la_note_rendue(self):
        html = html_de_note_calcul(construire_note_calcul(resultat(),
                                                          site=SITE))
        # « marge » tout court n'est PAS un mot interdit dans une pièce
        # technique : les marges du moteur sont des jeux GÉOMÉTRIQUES mesurés
        # (CAL177). Ce qui est interdit, c'est l'argent.
        for interdit in ('prix_achat', 'prix d\'achat', 'marge brute',
                         'coût de revient', 'MAD', 'DH HT'):
            self.assertNotIn(interdit, html)


class MiseEnPageTest(SimpleTestCase):
    def setUp(self):
        self.html = html_de_note_calcul(
            construire_note_calcul(resultat(), site=SITE))

    def test_la_provenance_est_dans_la_marge_de_chaque_page(self):
        self.assertIn('@bottom-left', self.html)
        self.assertIn('entrée abababababab', self.html)
        self.assertIn('counter(page)', self.html)

    def test_les_sources_paraissent_a_cote_des_hypotheses(self):
        self.assertIn('PVGIS', self.html)
        self.assertIn('hypothèse société', self.html)

    def test_le_document_est_autonome(self):
        for interdit in ('http://', 'https://', '<img', '@import'):
            self.assertNotIn(interdit, self.html)

    def test_une_grandeur_absente_s_affiche_en_tiret_jamais_en_zero(self):
        donnees = resultat()
        donnees['production']['total'].pop('p90_kwh')
        html = html_de_note_calcul(construire_note_calcul(donnees, site=SITE))
        self.assertIn('<th>Production annuelle P90</th><td>—</td>', html)
