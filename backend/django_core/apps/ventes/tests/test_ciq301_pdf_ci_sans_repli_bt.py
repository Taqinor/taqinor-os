"""CIQ301 — les gabarits commercial et industriel ne reprennent plus JAMAIS le
chiffre résidentiel/BT de ``calculate_savings_roi``.

Constats (C3-09, C3-VB-05, C3-VA-01) :
  * l'écran n'envoie jamais ``etude.economies_annuelles`` ; faute de cette
    clé, ``commercial/renderer.py`` et ``industriel/renderer.py`` reprenaient
    ``eco_s_ann`` (et ``roi_s``) — barème BT résidentiel × ``AUTOCONSO_SANS``
    0,60 ;
  * ``industriel/renderer.py`` servait ``cashflow_sans/avec`` et
    ``cashflow_assumptions`` (dont « le surplus injecté n'est pas rémunéré ») ;
  * le builder appliquait au C&I la branche « étude saisie » et ses fractions
    mensuelles RÉSIDENTIELLES ;
  * les jeux d'essai C&I injectaient ``economies_annuelles``.

Après : tuiles argent, cashflow et TRI OMIS (jamais un 0, QJR119) jusqu'à ce
que ``synthese_ci.argent`` les serve (CIQ307). Pages : commercial 3,
industriel 4. Aucun ancien devis n'est réparé (D-CIQ-21) — rendu seulement.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_ciq301_pdf_ci_sans_repli_bt -v 2
"""
import re

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.quote_engine.commercial import (
    render as c_render, renderer as c_renderer, sample_data as c_sample)
from apps.ventes.quote_engine.industriel import (
    render as i_render, renderer as i_renderer, sample_data as i_sample)
from apps.ventes.quote_engine.pricing import (
    CLE_SOLAIRE_MENSUELLE, repartir_annuel)

try:  # PyMuPDF — déjà une dépendance du backend ; jamais requis à l'import
    import fitz
except Exception:  # pragma: no cover - environnement sans PyMuPDF
    fitz = None


#: Fractions mensuelles RÉSIDENTIELLES de la branche « étude saisie ».
_SF_RESIDENTIEL = list(CLE_SOLAIRE_MENSUELLE)

#: Ce que le générateur persiste pour un C&I (``etudeMarcheBloc.js``) :
#: JAMAIS ``economies_annuelles`` ; un ``payback`` calculé côté écran.
_ETUDE_ECRAN = {
    'taux_autoconso': 74, 'taux_couverture': 52, 'payback': 3.6,
    'conso_annuelle': 160000, 'tension_raccordement': 'BT',
}

_LIGNES = [
    ('Panneau Canadien Solar 710W', '100', '1150', '10'),
    ('Onduleur réseau Huawei 50kW Triphasé', '1', '60000'),
    ('Structures acier', '100', '400'),
    ('Installation', '1', '60000'),
]


def _visible(html):
    txt = re.sub(r"<style>.*?</style>", " ", html, flags=re.S)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = txt.replace("&nbsp;", " ").replace(" ", " ")
    txt = txt.replace("&amp;", "&").replace("&#8217;", "'")
    return re.sub(r"[\s  ]+", " ", txt)


def _avec_repli_bt(sample_mod):
    """Charge utile C&I portant les clés BT que le builder sert toujours."""
    data = sample_mod.build()
    data.update({
        'eco_s_ann': 98765, 'eco_a_ann': 98765, 'roi_s': 3.2, 'roi_a': 3.2,
        'eco_s_monthly': [8000] * 12, 'eco_a_monthly': [8000] * 12,
        'cashflow_sans': [-1000000.0 + 98765 * t for t in range(1, 26)],
        'cashflow_avec': [-1000000.0 + 98765 * t for t in range(1, 26)],
        'cashflow_assumptions': {'notes': [
            "Loi 82-21 : le surplus injecté n'est pas rémunéré."]},
    })
    data['etude'] = dict(data.get('etude') or {}, payback=3.6)
    return data


class TestRendererSansRepliBT(SimpleTestCase):
    """Le dict augmenté n'emprunte AUCUN chiffre au modèle résidentiel/BT."""

    def test_industriel_aucune_cle_argent(self):
        d = i_renderer._augment(_avec_repli_bt(i_sample))
        for cle in ('ind_economies', 'ind_payback', 'ind_cashflow',
                    'ind_cashflow_branche', 'ind_cashflow_hypotheses'):
            self.assertIsNone(d[cle], cle)

    def test_commercial_aucune_cle_argent(self):
        d = c_renderer._augment(_avec_repli_bt(c_sample))
        self.assertIsNone(d['com_economies'])
        self.assertIsNone(d['com_payback'])

    def test_industriel_html_sans_economie_ni_payback(self):
        txt = _visible(i_render.build_html(
            i_renderer._augment(_avec_repli_bt(i_sample))))
        self.assertNotIn('Économies / an', txt)
        self.assertNotIn('Payback', txt)
        self.assertNotIn('Cashflow cumulé', txt)
        self.assertNotIn("n'est pas rémunéré", txt)
        self.assertNotIn('98 765', txt)
        self.assertIn('Rentabilité non chiffrée sur ce dossier', txt)

    def test_commercial_html_sans_economie(self):
        txt = _visible(c_render.build_html(
            c_renderer._augment(_avec_repli_bt(c_sample))))
        self.assertNotIn('Économies / an', txt)
        self.assertNotIn('98 765', txt)
        self.assertNotIn("n'est pas rémunéré", txt)

    def test_pages_inchangees(self):
        ind = i_render.build_html(i_renderer._augment(_avec_repli_bt(i_sample)))
        com = c_render.build_html(c_renderer._augment(_avec_repli_bt(c_sample)))
        self.assertEqual(ind.count('class="page"'), 4)
        self.assertEqual(com.count('class="page"'), 3)


class TestJeuxDEssaiSansEconomieFabriquee(SimpleTestCase):
    """C3-VA-01 — les fixtures ne cachent plus le défaut."""

    def test_aucune_economie_injectee(self):
        for mod in (c_sample, i_sample):
            data = mod.build()
            with self.subTest(mod=mod.__name__):
                for cle in ('eco_s_ann', 'eco_a_ann', 'roi_s', 'roi_a',
                            'cashflow_sans', 'cashflow_avec',
                            'cashflow_assumptions'):
                    self.assertNotIn(cle, data)
                self.assertNotIn('economies_annuelles', data['etude'])
                self.assertNotIn('payback', data['etude'])


class _DevisCIMixin:
    def _devis(self, mode, reference, etude=None):
        from django.contrib.auth import get_user_model
        from apps.ventes.tests._quote_engine_common import (
            make_client, make_company, make_devis)
        company = make_company()
        # `make_user` pose un username FIXE : un second devis dans le même
        # test (subTest commercial puis industriel) heurtait l'unicité.
        user = get_user_model().objects.create_user(
            username=f'ciq301-{reference}', password='x',
            role_legacy='responsable', company=company)
        devis = make_devis(company, user, make_client(company), _LIGNES,
                           reference=reference,
                           etude_params=dict(etude or _ETUDE_ECRAN))
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        return devis

    def _data(self, devis):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, echapper_textes_client)
        return echapper_textes_client(
            build_quote_data(devis, {'pdf_mode': 'full'}))


class TestBuilderBrancheEtudeHorsCI(_DevisCIMixin, TestCase):
    """La branche « étude saisie » et ses fractions ``_sf`` résidentielles ne
    s'appliquent plus au C&I."""

    def test_economie_d_etude_jamais_reprise_en_ci(self):
        etude = dict(_ETUDE_ECRAN, production_annuelle=110000,
                     economies_annuelles=123456)
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                data = self._data(self._devis(mode, f'DEV-CIQ301-E{mode[:3]}',
                                              etude))
                self.assertNotEqual(data['eco_s_ann'], 123456)
                self.assertNotEqual(
                    data['eco_s_monthly'],
                    [round(123456 * f) for f in _SF_RESIDENTIEL])
                self.assertNotEqual(
                    (data.get('savings_method') or {}).get('model'), 'etude')

    def test_ci_mt_toujours_masque(self):
        etude = dict(_ETUDE_ECRAN, tension_raccordement='MT',
                     production_annuelle=110000, economies_annuelles=123456)
        data = self._data(self._devis('industriel', 'DEV-CIQ301-MT', etude))
        self.assertTrue(data['masquer_economies'])

    def test_residentiel_garde_sa_branche_etude(self):
        """Non-régression : un résidentiel avec étude saisie est inchangé."""
        etude = {'production_annuelle': 9000, 'economies_annuelles': 12000}
        data = self._data(self._devis('residentiel', 'DEV-CIQ301-RES', etude))
        self.assertEqual(data['eco_s_ann'], 12000)
        # AMOT27 — forme GHI, Σ = annuel au dirham.
        self.assertEqual(data['eco_s_monthly'], repartir_annuel(12000))


class TestRenduHtmlReelCI(_DevisCIMixin, TestCase):
    """Charge utile RÉELLE du générateur (``build_quote_data`` jamais mocké)."""

    def test_commercial_bt(self):
        data = self._data(self._devis('commercial', 'DEV-CIQ301-COM'))
        self.assertGreater(data['eco_s_ann'] or 0, 0)  # le chiffre BT EXISTE…
        d = c_renderer._augment(data)
        self.assertIsNone(d['com_economies'])          # …et n'est PAS repris
        self.assertIsNone(d['com_payback'])
        html = c_render.build_html(d)
        txt = _visible(html)
        self.assertNotIn('Économies / an', txt)
        self.assertNotIn("n'est pas rémunéré", txt)
        self.assertEqual(html.count('class="page"'), 3)

    def test_industriel_bt(self):
        data = self._data(self._devis('industriel', 'DEV-CIQ301-IND'))
        self.assertGreater(data['eco_s_ann'] or 0, 0)
        d = i_renderer._augment(data)
        for cle in ('ind_economies', 'ind_payback', 'ind_cashflow',
                    'ind_cashflow_hypotheses'):
            self.assertIsNone(d[cle], cle)
        html = i_render.build_html(d)
        txt = _visible(html)
        self.assertNotIn('Économies / an', txt)
        self.assertNotIn('Payback', txt)
        self.assertNotIn("n'est pas rémunéré", txt)
        self.assertEqual(html.count('class="page"'), 4)


@tag('pdf')
class TestRenduPdfReelCI(_DevisCIMixin, TestCase):
    """``render_pdf_bytes`` + texte extrait (WeasyPrint réel)."""

    def setUp(self):
        if fitz is None:  # pragma: no cover
            self.skipTest('PyMuPDF absent')

    def _pdf(self, renderer_mod, data):
        doc = fitz.open(stream=renderer_mod.render_pdf_bytes(data),
                        filetype='pdf')
        try:
            return len(doc), '\n'.join(p.get_text() for p in doc)
        finally:
            doc.close()

    def _verifier(self, texte):
        plat = re.sub(r'\s+', ' ', texte)
        self.assertNotIn('Économies / an', plat)
        self.assertNotIn("n'est pas rémunéré", plat)
        self.assertNotIn('Payback', plat)

    def test_commercial_bt_trois_pages(self):
        data = self._data(self._devis('commercial', 'DEV-CIQ301-PCOM'))
        n, texte = self._pdf(c_renderer, data)
        self.assertEqual(n, 3)
        self._verifier(texte)

    def test_industriel_bt_quatre_pages(self):
        data = self._data(self._devis('industriel', 'DEV-CIQ301-PIND'))
        n, texte = self._pdf(i_renderer, data)
        self.assertEqual(n, 4)
        self._verifier(texte)
