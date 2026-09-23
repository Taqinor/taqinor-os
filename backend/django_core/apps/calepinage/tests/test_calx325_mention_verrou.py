"""CALX325 — la pièce dit qu'elle vient d'une conception verrouillée ou archivée.

Ce qui est prouvé ici :

* conception COURANTE ⇒ aucune mention, et le HTML du gabarit est IDENTIQUE
  à celui d'avant la tâche (``pied_html``/``document_html`` sans ``etat``) ;
* verrouillée ⇒ la mention et sa date (ou « date non enregistrée », jamais
  une date inventée) ; archivée ET verrouillée ⇒ les DEUX mentions, sans
  doublon ;
* l'état est LU par ``services.verrou.est_verrouille`` et
  ``services.archivage.est_archive`` — jamais un drapeau recopié ; un
  calepinage non enregistré est courant sans lecture en base ;
* la mention part dans le pied COURANT du rapport d'étude (répété sur chaque
  page) et aucune pièce n'est refusée pour autant ;
* ``@tag('pdf')`` : la mention figure sur CHAQUE page du PDF (texte extrait) ;
* en base (CI) : un devis lié envoyé verrouille, l'archivage archive.

Run :
    python manage.py test apps.calepinage.tests.test_calx325_mention_verrou -v2
"""
import copy
import datetime
import json
import pathlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, tag

from apps.calepinage.services.documents.gabarit_document import (
    DATE_NON_ENREGISTREE, ETAT_COURANT, document_html, etat_de_conception,
    mentions_d_etat, pied_html,
)
from apps.calepinage.services.rapport import (
    construire_rapport, html_de_rapport, rendre_rapport,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
RESULTAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_resultat.json')
    .read_text(encoding='utf-8'))['exemple']
PROVENANCE = {'hash_entree': 'ab' * 32, 'version_moteur': 'calepinage-1.0.0'}
VERROUILLE = dict(ETAT_COURANT, verrouille=True, verrouille_le='12/09/2026')
ARCHIVE = dict(ETAT_COURANT, archive=True, archive_le='20/09/2026')
LES_DEUX = dict(VERROUILLE, archive=True, archive_le='20/09/2026')
NU = SimpleNamespace(company=None, client_id=None, lead_id=None,
                     titre='Villa', resultat=None, pk=None)


def rapport(etat):
    return construire_rapport(NU, resultat=copy.deepcopy(RESULTAT), site={},
                              identite={}, styles={}, etat=etat)


class MentionsTest(SimpleTestCase):
    def test_une_conception_courante_n_a_aucune_mention(self):
        self.assertEqual(mentions_d_etat(ETAT_COURANT), [])
        self.assertEqual(mentions_d_etat(None), [])
        self.assertEqual(mentions_d_etat({}), [])

    def test_verrouillee_la_mention_porte_sa_date(self):
        mentions = mentions_d_etat(VERROUILLE)
        self.assertEqual(len(mentions), 1)
        self.assertIn('verrouillée', mentions[0])
        self.assertIn('12/09/2026', mentions[0])

    def test_une_date_absente_est_dite_jamais_inventee(self):
        mentions = mentions_d_etat(dict(ETAT_COURANT, verrouille=True))
        self.assertIn(DATE_NON_ENREGISTREE, mentions[0])

    def test_archivee_et_verrouillee_les_deux_mentions_sans_doublon(self):
        mentions = mentions_d_etat(LES_DEUX)
        self.assertEqual(len(mentions), 2)
        pied = pied_html(PROVENANCE, mentions=mentions, etat=LES_DEUX)
        self.assertEqual(pied.count('verrouillée'), 1)
        self.assertEqual(pied.count('archivée'), 1)

    def test_courante_le_html_est_identique_a_celui_d_avant(self):
        self.assertEqual(pied_html(PROVENANCE, etat=ETAT_COURANT),
                         pied_html(PROVENANCE))
        avant = document_html('<p>x</p>', titre='Note', provenance=PROVENANCE)
        self.assertEqual(document_html('<p>x</p>', titre='Note',
                                       provenance=PROVENANCE,
                                       etat=ETAT_COURANT), avant)
        self.assertEqual(html_de_rapport(rapport(ETAT_COURANT)),
                         html_de_rapport(rapport({})))


class EtatLuParLesServicesTest(SimpleTestCase):
    def test_un_calepinage_non_enregistre_est_courant_sans_lecture(self):
        with mock.patch('apps.calepinage.services.verrou.est_verrouille') \
                as verrou:
            self.assertEqual(etat_de_conception(NU), ETAT_COURANT)
        verrou.assert_not_called()

    def test_l_etat_vient_du_verrou_et_de_la_corbeille(self):
        envoi = datetime.datetime(2026, 9, 12, 9, 0,
                                  tzinfo=datetime.timezone.utc)
        archivage = datetime.datetime(2026, 9, 20, 9, 0,
                                      tzinfo=datetime.timezone.utc)
        calepinage = SimpleNamespace(pk=7,
                                     devis=SimpleNamespace(date_envoi=envoi))
        with mock.patch('apps.calepinage.services.verrou.est_verrouille',
                        return_value=True), \
                mock.patch('apps.calepinage.services.archivage.est_archive',
                           return_value=True), \
                mock.patch('apps.trash.selectors.entree_active',
                           return_value=SimpleNamespace(
                               supprime_le=archivage)):
            etat = etat_de_conception(calepinage)
        self.assertTrue(etat['verrouille'])
        self.assertTrue(etat['archive'])
        self.assertTrue(etat['verrouille_le'].endswith('/09/2026'))
        self.assertTrue(etat['archive_le'].endswith('/09/2026'))

    def test_un_calepinage_ouvert_et_actif_est_courant(self):
        with mock.patch('apps.calepinage.services.verrou.est_verrouille',
                        return_value=False), \
                mock.patch('apps.calepinage.services.archivage.est_archive',
                           return_value=False):
            self.assertEqual(etat_de_conception(SimpleNamespace(pk=7)),
                             ETAT_COURANT)


class DansLeRapportTest(SimpleTestCase):
    def test_la_mention_part_dans_le_pied_courant_du_rapport(self):
        html = html_de_rapport(rapport(LES_DEUX))
        pied = html.split('<div class="gabarit-pied">', 1)[1].split(
            '</div></div>', 1)[0]
        self.assertIn('Conception verrouillée depuis le 12/09/2026', pied)
        self.assertIn('Conception archivée le 20/09/2026', pied)
        # Le pied COURANT est placé dans @bottom-left : il se répète sur
        # chaque page. Et la pièce n'est PAS refusée.
        self.assertIn('@bottom-left{content:element(gabarit-pied)', html)
        self.assertIn('data-section="pertes"', html)


@tag('pdf')
class MentionSurChaquePageTest(SimpleTestCase):
    """WeasyPrint + PyMuPDF réels — étiqueté ``pdf`` (hors du palier CI)."""

    def setUp(self):
        try:
            import fitz  # noqa: F401
            import weasyprint  # noqa: F401
        except Exception:  # noqa: BLE001 — bibliothèques natives absentes
            self.skipTest('WeasyPrint ou PyMuPDF indisponible sur ce poste')

    def test_la_mention_figure_sur_chaque_page(self):
        import fitz

        octets = rendre_rapport(NU, resultat=copy.deepcopy(RESULTAT), site={},
                                identite={}, styles={}, etat=VERROUILLE)
        document = fitz.open(stream=octets, filetype='pdf')
        try:
            pages = [page.get_text() for page in document]
        finally:
            document.close()
        self.assertGreater(len(pages), 1)
        for rang, texte in enumerate(pages, start=1):
            with self.subTest(page=rang):
                self.assertIn('verrouillée', ' '.join(texte.split()))


class EtatEnBaseTest(TestCase):
    """Le verrou et la corbeille RÉELS (CI)."""

    def setUp(self):
        from apps.calepinage.models import Calepinage
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        from authentication.models import Company

        self.company = Company.objects.create(nom='Verrou Co',
                                              slug='verrou-co-calx325')
        client = Client.objects.create(company=self.company, nom='Client')
        self.devis = Devis.objects.create(
            company=self.company, client=client, reference='DEV-CALX325-1',
            statut='envoye',
            date_envoi=datetime.datetime(2026, 9, 12, 9, 0,
                                         tzinfo=datetime.timezone.utc))
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=client, devis=self.devis,
            titre='Toiture')

    def test_un_devis_lie_envoye_verrouille_avec_la_date_d_envoi(self):
        etat = etat_de_conception(self.calepinage)
        self.assertTrue(etat['verrouille'])
        self.assertTrue(etat['verrouille_le'].endswith('/09/2026'))
        self.assertFalse(etat['archive'])

    def test_l_archivage_ajoute_la_mention_archivee(self):
        from apps.calepinage.services.archivage import archiver

        archiver(self.calepinage)
        etat = etat_de_conception(self.calepinage)
        self.assertTrue(etat['archive'])
        self.assertTrue(etat['archive_le'])
        self.assertEqual(len(mentions_d_etat(etat)), 2)
