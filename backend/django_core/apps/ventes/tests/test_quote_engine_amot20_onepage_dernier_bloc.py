"""AMOT20 (C-AMOT-018) — le une-page prouve sa postcondition sur le DERNIER
bloc de la zone (ligne Validité/Acompte/TVA) et sur le HTML RENDU : une note
×60 et trois clauses ×20 ne font plus disparaître en silence les conditions ;
au-delà, note et clauses sont tronquées avec renvoi déclaré « texte intégral
sur la proposition en ligne ». La page reste unique.

Oracle = positions des boîtes composées par WeasyPrint RÉEL (sauté sans
WeasyPrint). Test-du-test : ré-ancrer la mesure sur ``_formes_total_ttc``
seul (retirer ``_bas_bloc_fin`` de ``_mesure_onepage``) ⇒
``test_conditions_visibles`` échoue (« Acompte » hors de la zone).
"""
import unittest

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.models import Devis
from apps.ventes.quote_engine import generate_devis_premium as G
from apps.ventes.quote_engine.builder import build_quote_data, clean_pdf_options
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

try:
    __import__('weasyprint')
    _WEASY = True
except (ImportError, OSError):  # bibliothèques natives absentes
    _WEASY = False


def _plat(texte):
    """Espaces normalisées (fin de ligne, insécables) : un libellé se lit
    pareil qu'il tienne sur une ligne ou se coupe sur deux."""
    return ' '.join(texte.split())


@unittest.skipUnless(_WEASY, "WeasyPrint absent : mesure impossible")
@tag('pdf')
class OnepageDernierBlocTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='amot20-co', nom='AMOT20')
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, [
                ('Panneau mono 550W', '10', '1100'),
                ('Onduleur réseau Huawei 5kW', '1', '8000'),
                ('Structure acier', '10', '300'),
                ('Installation et mise en service', '1', '4000'),
            ], reference='DEV-AMOT20-1')
        Devis.objects.filter(pk=self.devis.pk).update(
            note=('Note longue du commercial pour le client. ' * 60).strip(),
            clauses_appliquees=[
                {'type': 'clause', 'nom': f'Clause {i}',
                 'corps_texte': ('Texte contractuel de la clause. ' * 20)}
                for i in (1, 2, 3)])
        self.devis.refresh_from_db()

    def _rendu(self, langue):
        from weasyprint import HTML
        with G._RENDER_LOCK:
            data = build_quote_data(self.devis, clean_pdf_options(
                {'pdf_mode': 'onepage', 'langue_sortie': langue}))
            html = G.render_html_for({**data, 'pdf_mode': 'onepage'})
            formes_fin = G._formes_bloc_fin()
            formes_ttc = G._formes_total_ttc()
            renvoi = G._renvoi_texte_integral()
        pages = HTML(string=html).render().pages
        return html, pages, formes_fin, formes_ttc, renvoi

    def _boites_visibles(self, page):
        limite = page.height - G.ONEPAGE_FOOTER_PX
        return [b for b in G._boites_texte_onepage(page)
                if b.position_y + b.height <= limite + 0.5]

    def test_conditions_visibles(self):
        for langue in ('fr', 'en', 'ar'):
            with self.subTest(langue=langue):
                html, pages, formes_fin, formes_ttc, renvoi = self._rendu(
                    langue)
                self.assertEqual(len(pages), 1)
                # Boîtes jointes par une ESPACE (ordre de composition) : un
                # libellé de plusieurs mots coupé en fin de ligne reste
                # visible. Nocturnes 25→28/10/2026 : depuis le titre des CGV
                # en tête de ligne (ERR-APDF48, acb748acd), la puce arabe se
                # compose « · 10% بعد » / « التشغيل » sur deux lignes, toutes
                # deux DANS la zone — la jointure « | » y voyait une absence.
                # Chaque boîte reste filtrée sur la zone visible.
                visibles = _plat(' '.join(
                    b.text for b in self._boites_visibles(pages[0])))
                for forme in formes_fin:
                    if forme in html:
                        self.assertIn(_plat(forme), visibles, (langue, forme))
                self.assertTrue(any(f in visibles for f in formes_ttc))

    def test_renvoi_declare(self):
        # Nocturne 38870650403 (12→16/10) : avec la note ×60, le une-page FR
        # tient désormais sans rien tronquer (ligne de conditions mesurée à
        # 928 px pour une limite de 1 050 px) — la troncature déclarée n'était
        # plus exercée. Le cas « au-delà » du module est donc rejoué avec une
        # note ×200 : elle NE PEUT PAS tenir, le renvoi doit être déclaré.
        Devis.objects.filter(pk=self.devis.pk).update(
            note=('Note longue du commercial pour le client. ' * 200).strip())
        self.devis.refresh_from_db()
        html, pages, _f, _t, renvoi = self._rendu('fr')
        self.assertEqual(len(pages), 1)
        visibles = ' | '.join(b.text for b in self._boites_visibles(pages[0]))
        # La clause 2 est imprimée dans la zone visible, ou le texte long a
        # été remplacé par le renvoi déclaré.
        self.assertTrue('Clause 2' in visibles
                        or 'proposition en ligne' in visibles, visibles)
        self.assertIn('texte int&#233;gral sur la proposition en ligne', html)
        # Garde : l'ajustement ne laisse pas l'état tronqué derrière lui.
        self.assertFalse(G.ONEPAGE_TEXTES_TRONQUES)


@tag('pdf')
class OnepageSansAncrageTests(TestCase):
    """ACAL1033 (D-ACAL-45, D-ACAL-40) — au niveau 15, sans facture ni
    consommation, le une-page n'imprime plus la vignette « Économie annuelle »
    ni son ancre ; avec une consommation, il est inchangé ; au niveau 14 (tout
    devis existant) il est rendu comme aujourd'hui, sans clé
    ``regles_pose_reelle`` ; le PDF complet ne bouge pas. Mutants : retirer
    ``ECONOMIES_SANS_ANCRAGE`` de ``page_onepage`` ⇒ rouge ; ignorer le niveau ⇒
    le cas « niveau 14 » rougit ; brancher le drapeau dans
    ``_sans_economies_publiees`` ⇒ le cas « PDF complet » rougit."""

    def setUp(self):
        self.company = make_company(slug='acal1033-co', nom='ACAL1033')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 550W', '10', '1100'),
                ('Onduleur réseau Huawei 5kW', '1', '8000'),
                ('Installation et mise en service', '1', '4000'),
            ], reference='DEV-ACAL1033-1')

    def _data(self, niveau, mode='onepage', **sur):
        Devis.objects.filter(pk=self.devis.pk).update(regles_calcul=niveau)
        self.devis.refresh_from_db()
        data = build_quote_data(self.devis, clean_pdf_options({'pdf_mode': mode}))
        # Le chiffre « sans ancrage » : tarif de repli, aucune donnée réelle.
        return {**data, 'savings_estimated': True, 'factures_reelles': None, 'conso_annuelle_kwh': None,
                'onepage_branche': data.get('onepage_branche') or 'sans', 'eco_s_ann': 7420, **sur}

    def _html(self, data, mode='onepage'):
        with G._RENDER_LOCK:
            return G.render_html_for({**data, 'pdf_mode': mode})

    def test_niveau_15_sans_ancrage_aucune_economie_annuelle(self):
        data = self._data(15)
        self.assertTrue(data.get('regles_pose_reelle'))
        html = self._html(data)
        self.assertNotIn('economie_annuelle', html)

    def test_niveau_15_avec_consommation_inchange(self):
        avec = self._html(self._data(15, conso_annuelle_kwh=6000))
        hier = self._html({k: v for k, v in self._data(15, conso_annuelle_kwh=6000).items()
                           if k != 'regles_pose_reelle'})
        self.assertIn('economie_annuelle', avec)
        self.assertEqual(avec, hier)

    def test_niveau_14_rendu_comme_aujourd_hui(self):
        data = self._data(14)
        self.assertNotIn('regles_pose_reelle', data)
        self.assertIn('economie_annuelle', self._html(data))

    def test_niveau_15_pdf_complet_identique(self):
        data = self._data(15, mode='full')
        sans_niveau = {k: v for k, v in data.items() if k != 'regles_pose_reelle'}
        self.assertEqual(self._html(data, 'full'), self._html(sans_niveau, 'full'))


class OnepageAdresseTelephoneAcal1217Tests(SimpleTestCase):
    """ACAL1217 (C-ACAL-REC-R1-19) — le une-page d'un devis neuf imprime
    l'adresse jointe à la ville SANS la répéter (« Agadir, Agadir » du devis
    72 ⇒ « Agadir ») et le téléphone formaté comme le premium ; un devis
    ENVOYÉ (drapeau ``regles_pdf_historique_lot10`` de la migration 0164)
    garde l'adresse et le téléphone bruts reçus. Mutant : retirer
    ``theme.join_meta`` de ``ci_onepage.adresse`` ⇒ « Agadir, Agadir », échec."""

    def _html(self, adresse, historique=False):
        from apps.ventes.quote_engine.ci.onepage import DRAPEAU_PDF_HISTORIQUE_LOT10
        from apps.ventes.tests import _moteur_fixtures as F
        etude = dict(F.donnees_legacy('deux').get('etude') or {'kwc': 5.5})
        if historique:
            etude[DRAPEAU_PDF_HISTORIQUE_LOT10] = True
        with G._RENDER_LOCK:
            return _plat(F.html_onepage(client_addr=adresse, client_city='Agadir', client_ville_libelle=None,
                                        client_phone='0612345678', etude=etude))

    def test_brouillon_adresse_sans_ville_repetee_et_telephone_formate(self):
        html = self._html('Agadir, Agadir')
        self.assertNotIn('Agadir, Agadir', html)
        self.assertIn('margin-top:2px;">Agadir</div>', html)
        self.assertIn('+212 6 12 34 56 78', html)
        self.assertNotIn('0612345678', html)
        self.assertIn('margin-top:2px;">Quartier Founty, Agadir</div>', self._html('Quartier Founty, Agadir'))

    def test_envoye_flagge_garde_le_texte_recu(self):
        html = self._html('Agadir, Agadir', historique=True)
        self.assertIn('margin-top:2px;">Agadir, Agadir</div>', html)
        self.assertIn('margin-top:1px;">0612345678</div>', html)
        self.assertNotIn('+212 6 12 34 56 78', html)
        # Rendre deux fois ⇒ même texte.
        self.assertEqual(html, self._html('Agadir, Agadir', historique=True))

    def test_migration_0164_marque_les_etudes_non_vides_seulement(self):
        import importlib
        mod = importlib.import_module('apps.ventes.migrations.0164_acal1217_pdf_historique_lot10')
        self.assertTrue(mod.doit_marquer({'kwc': 5}))
        self.assertFalse(mod.doit_marquer({}))
        self.assertFalse(mod.doit_marquer(None))
        self.assertFalse(mod.doit_marquer({'kwc': 5, mod.DRAPEAU: True}))
