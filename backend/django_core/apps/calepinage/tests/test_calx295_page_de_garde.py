"""CALX295 — la page de garde : identité société et projet.

Ce qui est prouvé ici :

* une identité VIDE produit une garde sans aucun « None » et sans aucune
  balise vide : chaque valeur absente est imprimée avec son libellé BARRÉ et
  « non renseigné », jamais remplacée ;
* une identité COMPLÈTE produit exactement un ``<h1>`` et la mention
  d'empreinte (empreinte d'entrée COURTE + version du moteur) ;
* la note de calcul s'ouvre désormais sur cette garde (``garde=False`` rend
  la note d'avant) ;
* ``@tag('pdf')`` : le PDF de la note gagne EXACTEMENT une page
  (``pack_technique.compter_pages`` avant/après) ;
* en base (CI) : le client est LU par les sélecteurs du CRM, borné société.

Run (essais purs) :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx295_page_de_garde.py -q
"""
import copy
import datetime
import json
import pathlib
import re
import unittest
from html import escape

from django.test import TestCase, tag

from apps.calepinage.services.documents.gabarit_document import (
    LIBELLES_GARDE_FR, identite_du_calepinage, page_de_garde_html,
)
from apps.calepinage.services.note_calcul import (
    construire_note_calcul, html_de_note_calcul,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
RESULTAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']

IDENTITE = {'titre_document': "Rapport d'étude", 'projet': 'Villa Anfa',
            'client': 'Mme Bennani', 'produit_le': '23/09/2026'}
SITE = {'ville': 'Bouskoura', 'adresse': 'Zone industrielle, lot 12',
        'source': 'roof_point'}
PROVENANCE = {'hash_entree': 'ab' * 32, 'version_moteur': 'calepinage-1.0.0'}
STYLES = {'nom_affiche': 'Soleil Atlas', 'logo_url': '',
          'couleur_primaire': '', 'couleur_secondaire': ''}

#: Une balise ouverte puis refermée sans rien entre les deux.
BALISE_VIDE = re.compile(r'<(\w+)(?:\s[^>]*)?>\s*</\1>')


class GardeVideTest(unittest.TestCase):
    def setUp(self):
        self.html = page_de_garde_html({}, {}, {}, {})

    def test_aucun_none_ni_balise_vide(self):
        self.assertNotIn('None', self.html)
        self.assertIsNone(BALISE_VIDE.search(self.html),
                          'balise vide dans la garde : %r'
                          % (BALISE_VIDE.search(self.html) or [''])[0])

    def test_chaque_valeur_absente_est_barree_et_dite(self):
        for champ in ('societe', 'client', 'adresse', 'produit_le',
                      'empreinte', 'version_moteur'):
            with self.subTest(champ=champ):
                self.assertIn('<s>%s</s>' % escape(LIBELLES_GARDE_FR[champ]),
                              self.html)
        self.assertEqual(self.html.count(LIBELLES_GARDE_FR['non_renseigne']),
                         8)

    def test_le_titre_n_est_jamais_vide(self):
        self.assertEqual(self.html.count('<h1>'), 1)
        self.assertIn(escape(LIBELLES_GARDE_FR['titre_defaut']), self.html)

    def test_des_entrees_illisibles_ne_font_pas_tomber_la_garde(self):
        html = page_de_garde_html(None, None, None, None)
        self.assertNotIn('None', html)


class GardeCompleteTest(unittest.TestCase):
    def setUp(self):
        self.html = page_de_garde_html(IDENTITE, SITE, PROVENANCE, STYLES)

    def test_exactement_un_h1_et_la_mention_d_empreinte(self):
        self.assertEqual(len(re.findall(r'<h1[\s>]', self.html)), 1)
        self.assertIn(escape(LIBELLES_GARDE_FR['empreinte']), self.html)
        self.assertIn('abababababab', self.html)        # empreinte COURTE
        self.assertNotIn('ab' * 32, self.html)          # jamais l'entière
        self.assertIn('calepinage-1.0.0', self.html)

    def test_l_identite_est_imprimee_telle_que_lue(self):
        for attendu in ('Soleil Atlas', 'Villa Anfa', 'Mme Bennani',
                        'Zone industrielle, lot 12', 'Bouskoura',
                        '23/09/2026'):
            with self.subTest(valeur=attendu):
                self.assertIn(escape(attendu), self.html)
        self.assertNotIn(LIBELLES_GARDE_FR['non_renseigne'], self.html)
        self.assertIsNone(BALISE_VIDE.search(self.html))

    def test_la_garde_se_termine_par_un_saut_de_page(self):
        self.assertIn('break-after:page', self.html)

    def test_un_logo_saisi_est_pose_un_logo_libre_ne_l_est_pas(self):
        avec = page_de_garde_html(IDENTITE, SITE, PROVENANCE, dict(
            STYLES, logo_url='https://cdn.exemple.test/logo.png'))
        self.assertIn('src="https://cdn.exemple.test/logo.png"', avec)
        sans = page_de_garde_html(IDENTITE, SITE, PROVENANCE, dict(
            STYLES, logo_url='javascript:alert(1)'))
        self.assertNotIn('<img', sans)

    def test_une_autre_langue_remplace_les_libelles_cle_par_cle(self):
        html = page_de_garde_html({}, {}, {}, {}, libelles={
            'client': 'Customer', 'non_renseigne': 'not provided'})
        self.assertIn('<s>Customer</s>', html)
        self.assertIn('not provided', html)
        # Une clé non traduite garde son libellé français, jamais un vide.
        self.assertIn('<s>%s</s>' % escape(LIBELLES_GARDE_FR['ville']), html)


class NoteAvecGardeTest(unittest.TestCase):
    def _note(self, **options):
        return construire_note_calcul(copy.deepcopy(RESULTAT), site=SITE,
                                      **options)

    def test_la_note_s_ouvre_sur_sa_garde(self):
        html = html_de_note_calcul(self._note(identite=IDENTITE,
                                              styles=STYLES))
        self.assertIn('page-de-garde', html)
        self.assertLess(html.index('page-de-garde'),
                        html.index('<h1>Note de calcul — calepinage</h1>'))
        self.assertIn('Mme Bennani', html)
        self.assertIn('Soleil Atlas', html)

    def test_sans_identite_le_titre_de_la_note_est_celui_de_la_garde(self):
        html = html_de_note_calcul(self._note())
        self.assertIn('<h1>Note de calcul</h1>', html)
        self.assertNotIn('None', html)

    def test_garde_false_rend_la_note_d_avant(self):
        html = html_de_note_calcul(self._note(), garde=False)
        self.assertNotIn('page-de-garde', html)
        self.assertEqual(html.count('<h1>'), 1)

    def test_la_note_reste_autonome_et_sans_montant(self):
        html = html_de_note_calcul(self._note(identite=IDENTITE,
                                              styles=STYLES))
        for interdit in ('http://', 'https://', '@import', 'MAD', 'prix'):
            self.assertNotIn(interdit, html)


@tag('pdf')
class LaNoteGagneUnePageTest(unittest.TestCase):
    """WeasyPrint + PyMuPDF — étiqueté ``pdf`` (hors du palier CI courant)."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    def test_le_pdf_de_la_note_gagne_exactement_une_page(self):
        from core.pdf import render_pdf

        from apps.calepinage.services.pack_technique import compter_pages

        note = construire_note_calcul(copy.deepcopy(RESULTAT), site=SITE,
                                      identite=IDENTITE, styles=STYLES)
        avant = compter_pages(render_pdf(html=html_de_note_calcul(
            note, garde=False)))
        apres = compter_pages(render_pdf(html=html_de_note_calcul(note)))
        self.assertGreater(avant, 0)
        self.assertEqual(apres, avant + 1)


class IdentiteEnBaseTest(TestCase):
    """Le client est LU par le CRM, borné à la société du calepinage (CI)."""

    def setUp(self):
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from authentication.models import Company

        self.company = Company.objects.create(nom='Garde Co',
                                              slug='garde-co-calx295')
        client = Client.objects.create(company=self.company,
                                       nom='Bâtiment Atlas')
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=client, titre='Toiture atelier')

    def test_l_identite_porte_projet_client_et_date(self):
        moment = datetime.datetime(2026, 9, 23, 10, 0,
                                   tzinfo=datetime.timezone.utc)
        identite = identite_du_calepinage(self.calepinage,
                                          titre_document='Note de calcul',
                                          moment=moment)
        self.assertEqual(identite['projet'], 'Toiture atelier')
        self.assertEqual(identite['client'], 'Bâtiment Atlas')
        self.assertEqual(identite['produit_le'], '23/09/2026')
        self.assertEqual(identite['titre_document'], 'Note de calcul')


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
