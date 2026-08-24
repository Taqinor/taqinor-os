"""L-NIV — l'agrégation « kit » du niveau standard s'applique AUSSI au PDF.

La fuite colmatée ici : ``ShareLink.niveau = 'standard'`` agrégeait la
nomenclature fixation/câblage/protection dans la charge utile JSON de la
proposition, mais le PDF servi PAR LE MÊME JETON (``proposal_pdf`` et
``public_document``) la publiait en entier — désignation, quantité, P.U.,
ligne à ligne, sur tous les formats. Le comparatif de gammes la republiait de
son côté.

Couvert ici :
  (a) données du moteur — ``kit_agrege`` agrège ``sans_items``/``avec_items``/
      ``all_items`` (donc les 3-pages résidentiel, le une-page et les
      renderers industriel/commercial/agricole) ;
  (b) PDF RÉEL — extraction de texte : le PDF « standard » ne contient plus
      AUCUNE désignation de ligne kit, le PDF « confiance » les contient
      toutes (témoin positif — sans lui, une extraction muette passerait) ;
  (c) totaux INCHANGÉS entre les deux niveaux, et sous-total du kit égal à la
      somme EXACTE des lignes regroupées (zéro chiffre inventé) ;
  (d) pagination inchangée (les 3 pages restent 3 pages) ;
  (e) câblage des vues — ``public_document`` applique EXACTEMENT le même
      gating que ``proposal_pdf`` (filigrane + kit agrégé au standard) ;
  (f) comparatif de gammes — agrégé au standard, intact en confiance.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_l_niv_kit_agrege_pdf -v 2
"""
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.test import Client as DjangoClient, TestCase, tag
from django.urls import reverse

from apps.ventes.models import ShareLink
from apps.ventes.quote_engine.builder import (
    build_quote_data, clean_pdf_options,
)
from apps.ventes.utils.anticopie import LIBELLE_KIT

from .test_l_niv_niveau import (
    add_kit_lines, make_client, make_company, make_devis, make_user,
)

#: Fragments COURTS des trois désignations kit (cf. ``add_kit_lines``) —
#: courts pour survivre à la césure d'un tableau PDF, mais assez distinctifs
#: pour qu'aucun autre libellé du document ne les porte.
FRAGMENTS_KIT = ('Rail de fixation', 'Câble DC', 'Disjoncteur')
DESIGNATIONS_KIT = {
    'Rail de fixation aluminium',
    'Câble DC 6mm² rouge/noir',
    'Disjoncteur AC 20A tétrapolaire',
}


def _designations(items):
    return {(it.get('designation') or '') for it in (items or [])}


def _somme_ht(items):
    return sum(
        Decimal(str(it.get('quantite') or 0))
        * Decimal(str(it.get('prix_unit_ht') or 0))
        for it in (items or []))


class _Base(TestCase):
    def setUp(self):
        self.company = make_company(f'lnivkit-{uuid.uuid4().hex[:8]}')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = add_kit_lines(make_devis(
            self.company, self.user, self.client_obj,
            f'DEV-LNIVKIT-{uuid.uuid4().hex[:4]}'))

    def _data(self, standard, **extra):
        opts = clean_pdf_options(dict(extra))
        if standard:
            opts['kit_agrege'] = True
        return build_quote_data(self.devis, opts)


# ═══════════════════════════════════════════════════════════════════════════
# (a) + (c) — données du moteur : agrégation, et pas un centime de bougé
# ═══════════════════════════════════════════════════════════════════════════

class TestBuilderKitAgrege(_Base):
    def test_defaut_confiance_garde_les_lignes_kit(self):
        """Le défaut (chemin ERP authentifié, lien « confiance ») ne dégrade
        RIEN : c'est la garantie de non-régression du PDF interne."""
        data = self._data(False)
        self.assertFalse(clean_pdf_options({})['kit_agrege'])
        for cle in ('sans_items', 'all_items'):
            noms = _designations(data[cle])
            self.assertTrue(
                DESIGNATIONS_KIT <= noms,
                f'{cle} : les lignes kit doivent rester détaillées')
            self.assertNotIn(LIBELLE_KIT, noms)

    def test_standard_agrege_toutes_les_listes_de_lignes(self):
        """sans_items/avec_items alimentent le 3-pages résidentiel,
        all_items le une-page ET les renderers industriel/commercial/
        agricole : les trois doivent être dégradés, sinon un format fuit."""
        data = self._data(True)
        for cle in ('sans_items', 'avec_items', 'all_items'):
            noms = _designations(data[cle])
            if not noms:
                continue
            self.assertIn(LIBELLE_KIT, noms, cle)
            self.assertFalse(
                noms & DESIGNATIONS_KIT,
                f'{cle} : nomenclature kit encore publiée au standard')

    def test_standard_agrege_aussi_le_format_une_page(self):
        data = self._data(True, pdf_mode='onepage')
        noms = _designations(data['all_items'])
        self.assertIn(LIBELLE_KIT, noms)
        self.assertFalse(noms & DESIGNATIONS_KIT)

    def test_standard_agrege_aussi_le_format_etude(self):
        data = self._data(True, include_etude=True)
        noms = _designations(data['sans_items'])
        self.assertIn(LIBELLE_KIT, noms)
        self.assertFalse(noms & DESIGNATIONS_KIT)

    def test_sous_total_du_kit_egal_a_la_somme_exacte(self):
        """Zéro chiffre inventé : la ligne agrégée vaut la somme des lignes
        qu'elle remplace, à la décimale près."""
        avant = self._data(False)['sans_items']
        apres = self._data(True)['sans_items']
        attendu = _somme_ht(
            [it for it in avant if it['designation'] in DESIGNATIONS_KIT])
        ligne = next(it for it in apres if it['designation'] == LIBELLE_KIT)
        self.assertEqual(
            Decimal(str(ligne['prix_unit_ht'])).quantize(Decimal('0.01')),
            attendu.quantize(Decimal('0.01')))
        self.assertEqual(float(ligne['quantite']), 1.0)

    def test_totaux_identiques_avant_et_apres_agregation(self):
        """Les totaux sont figés AVANT la dégradation : ils ne peuvent pas
        bouger, ni la somme ligne à ligne du panier."""
        avant, apres = self._data(False), self._data(True)
        for cle in ('totaux_sans', 'totaux_avec', 'totaux_all'):
            self.assertEqual(avant[cle], apres[cle], cle)
        self.assertEqual(avant['display_total'], apres['display_total'])
        self.assertEqual(
            _somme_ht(avant['sans_items']).quantize(Decimal('0.01')),
            _somme_ht(apres['sans_items']).quantize(Decimal('0.01')),
            'la somme des lignes doit survivre au regroupement')

    def test_donnees_techniques_non_touchees(self):
        """La dégradation est un choix d'AFFICHAGE : les dérivations
        techniques publiées (kWc, kWh batterie) restent identiques."""
        avant, apres = self._data(False), self._data(True)
        for cle in ('puissance_kwc', 'batterie_kwh_total', 'nb_panneaux'):
            self.assertEqual(avant.get(cle), apres.get(cle), cle)


# ═══════════════════════════════════════════════════════════════════════════
# (b) + (d) — LE PDF RÉEL : extraction de texte + pagination
# ═══════════════════════════════════════════════════════════════════════════

@tag('pdf')
class TestPdfStandardSansNomenclature(_Base):
    def _rendu(self, standard, **extra):
        """(texte du PDF, nb de pages) — rendu par le chemin COMPLET
        (``generate_premium_devis_pdf``), MinIO bouchonné."""
        import fitz
        from apps.ventes.quote_engine import generate_premium_devis_pdf
        opts = clean_pdf_options(dict(extra))
        if standard:
            opts['kit_agrege'] = True
            opts['watermark'] = True
        with patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                patch('apps.ventes.utils.pdf._upload_pdf') as upload:
            generate_premium_devis_pdf(self.devis.id, opts, persist=False)
        pdf_bytes = upload.call_args[0][0]
        doc = fitz.open(stream=pdf_bytes, filetype='pdf')
        return '\n'.join(p.get_text() for p in doc), len(doc)

    def test_confiance_imprime_bien_la_nomenclature(self):
        """TÉMOIN POSITIF — sans lui, une extraction muette ferait passer le
        test « standard » ci-dessous sans rien prouver."""
        texte, _ = self._rendu(False)
        for frag in FRAGMENTS_KIT:
            self.assertIn(frag, texte,
                          f'{frag!r} absent du PDF confiance : le témoin '
                          f'positif ne prouve plus rien')

    def test_standard_ne_liste_plus_aucune_ligne_kit(self):
        texte, _ = self._rendu(True)
        for frag in FRAGMENTS_KIT:
            self.assertNotIn(
                frag, texte,
                f'FUITE : {frag!r} imprimé dans le PDF niveau standard')
        self.assertIn('Kit de fixation', texte,
                      'la ligne agrégée doit rester visible (le client doit '
                      'savoir ce qu\'il achète, au sous-total exact)')

    def test_standard_une_page_ne_liste_plus_aucune_ligne_kit(self):
        texte, pages = self._rendu(True, pdf_mode='onepage')
        self.assertEqual(pages, 1)
        for frag in FRAGMENTS_KIT:
            self.assertNotIn(frag, texte, frag)

    def test_pagination_inchangee(self):
        """« les 3 pages restent 3 pages » — la dégradation ne peut pas
        déplacer une page."""
        _, pages_confiance = self._rendu(False)
        _, pages_standard = self._rendu(True)
        self.assertGreaterEqual(pages_confiance, 1)
        self.assertEqual(
            pages_standard, pages_confiance,
            "l'agrégation ne doit JAMAIS déplacer une page : les gardes de "
            "pagination existants (test_quote_engine_formats) valent pour "
            "les deux niveaux")


# ═══════════════════════════════════════════════════════════════════════════
# (e) — câblage des DEUX flux PDF publics (mocké, léger)
# ═══════════════════════════════════════════════════════════════════════════

class TestFluxPublicsMemeGating(_Base):
    def _link(self, niveau):
        return ShareLink.objects.create(
            company=self.company, devis=self.devis,
            token=str(uuid.uuid4()), niveau=niveau)

    @patch('apps.ventes.public_views.download_pdf', return_value=b'%PDF-fake')
    @patch('apps.ventes.public_views.generate_premium_devis_pdf',
           return_value='k')
    def _opts_servies(self, url, niveau, mock_gen, mock_dl):
        """Les options RÉELLEMENT passées au moteur par la vue publique."""
        link = self._link(niveau)
        resp = DjangoClient().get(reverse(url, args=[link.token]))
        self.assertEqual(resp.status_code, 200)
        return mock_gen.call_args[0][1]

    URL_PROPOSAL = 'public-proposal-pdf'
    URL_DOCUMENT = 'public-document'

    def test_public_document_standard_degrade_comme_proposal_pdf(self):
        """La fuite historique : ``public_document`` ne lisait même pas
        ``link.niveau``. Les deux flux servent le MÊME document au MÊME
        client — ils doivent dégrader à l'identique."""
        a = self._opts_servies(self.URL_DOCUMENT, ShareLink.NIVEAU_STANDARD)
        b = self._opts_servies(self.URL_PROPOSAL, ShareLink.NIVEAU_STANDARD)
        self.assertTrue(a.get('kit_agrege'))
        self.assertTrue(a.get('watermark'))
        self.assertEqual(a, b)

    def test_confiance_ne_degrade_aucun_des_deux_flux(self):
        for url in (self.URL_DOCUMENT, self.URL_PROPOSAL):
            opts = self._opts_servies(url, ShareLink.NIVEAU_CONFIANCE)
            self.assertFalse(opts.get('kit_agrege'), url)
            self.assertFalse(opts.get('watermark'), url)


# ═══════════════════════════════════════════════════════════════════════════
# (f) — comparatif de gammes (la porte de côté)
# ═══════════════════════════════════════════════════════════════════════════

class TestComparatifGammes(_Base):
    def test_standard_publie_le_kit_agrege(self):
        from apps.ventes.public_views import _gamme_lignes_publiques
        lignes = _gamme_lignes_publiques(self.devis, est_standard=True)
        noms = _designations(lignes)
        self.assertIn(LIBELLE_KIT, noms)
        self.assertFalse(noms & DESIGNATIONS_KIT,
                         'FUITE : le comparatif republie la nomenclature')

    def test_confiance_garde_la_composition_detaillee(self):
        from apps.ventes.public_views import _gamme_lignes_publiques
        noms = _designations(_gamme_lignes_publiques(self.devis))
        self.assertTrue(DESIGNATIONS_KIT <= noms)
        self.assertNotIn(LIBELLE_KIT, noms)
