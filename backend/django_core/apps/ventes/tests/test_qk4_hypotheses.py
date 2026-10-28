"""QK4 — Client-facing « Nos hypothèses » transparency block.

Surfaces on the premium PDF + proposal payload the assumptions behind the
savings: tarif MAD/kWh used, tranche source (ONEE/Lydec/Redal, flagged
approximate for private distributors), self-consumption-first (loi 82-21,
surplus injection OFF), production/degradation basis. Degrades cleanly.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qk4_hypotheses -v 2
"""
import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, tag

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis

User = get_user_model()


# Compteur de tenants : une société NEUVE à chaque appel sans slug.
_company_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    """Une société neuve par appel — passer ``slug`` pour la nommer.

    Sans compteur, ce helper faisait un ``get_or_create`` sur un slug
    FIXE ('test-qk4-co') : deux appels rendaient la MÊME société, et un
    test cross-tenant écrivant ``other = make_company()`` ne testait rien.
    """
    from authentication.models import Company
    n = next(_company_seq)
    c, _ = Company.objects.get_or_create(
        slug=slug or f'test-qk4-co-{n}',
        defaults={'nom': nom or f'Test QK4 Co {n}'})
    return c


def make_user(company):
    return User.objects.create_user(
        username='qk4user', password='x', role_legacy='responsable',
        company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='Alami', prenom='Rania',
        email='r@example.com', telephone='+212600000005')


LINES = [
    ('Onduleur réseau 8kW', '1', '14000'),
    ('Panneau mono 550W', '12', '1400'),
    ('Installation', '1', '4000'),
]


def make_devis(company, user, client, etude_params=None, reference='DEV-QK4-1'):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, etude_params=etude_params)
    for desig, qty, pu in LINES:
        produit = Produit.objects.create(
            company=company, nom=desig, sku=f'{reference[-6:]}-{desig[:10]}',
            prix_vente=Decimal(pu), prix_achat=Decimal('1'), quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=desig,
            quantite=Decimal(qty), prix_unitaire=Decimal(pu),
            remise=Decimal('0'))
    return devis


class TestHypothesesInData(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_hypotheses_present_and_autoconso_first(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj)
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertTrue(h['autoconso_first'])
        joined = ' '.join(h['items'])
        # AMOT25 — la mention sourcée unique (constants_82_21.MENTION_BT)
        # remplace « Loi 82-21 : … » ; l'autoconsommation d'abord reste dite.
        from apps.ventes.quote_engine.constants_82_21 import MENTION_BT
        self.assertIn(MENTION_BT, joined)
        self.assertIn('autoconsommation', joined.lower())
        # production basis present
        self.assertIsNotNone(h['productible_kwh_kwc'])

    def test_onee_source_labelled_public(self):
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(
            self.company, self.user, self.client_obj,
            etude_params={'distributeur': 'onee', 'conso_annuelle': 6000},
            reference='DEV-QK4-ONEE')
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertEqual(h['tranche_source'], 'ONEE')
        self.assertFalse(h['tranche_approximatif'])
        self.assertIn('ONEE', ' '.join(h['items']))

    def test_lydec_reste_un_libelle_et_n_est_plus_approximatif(self):
        """Q7 (décision fondateur du 20/08/2026) — le distributeur redevient un
        LIBELLÉ. Sa grille « approximative » (trois paliers ronds « à
        confirmer ») est supprimée : elle faisait diverger la facture d'un MÊME
        client selon un champ de formulaire, puis un drapeau « approximatif »
        avouait le problème sans le corriger. Le nom continue de s'AFFICHER —
        c'est bien son distributeur — mais le barème est le national, donc plus
        rien n'est à relativiser."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(
            self.company, self.user, self.client_obj,
            etude_params={'distributeur': 'lydec', 'conso_annuelle': 6000},
            reference='DEV-QK4-LYD')
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertEqual(h['tranche_source'], 'Lydec')
        self.assertFalse(h['tranche_approximatif'])
        self.assertNotIn('approximatif', ' '.join(h['items']).lower())

    def test_degrades_with_tarif_kwh_text(self):
        """No utility → QRES55 : le tarif interne n'est JAMAIS affiché en
        chiffres ; la ligne dit la méthode + le chemin vers l'exactitude
        (facture → recalcul par tranches). La valeur reste en métadonnée."""
        from apps.ventes.quote_engine import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj,
                           reference='DEV-QK4-EST')
        data = build_quote_data(devis)
        h = data['hypotheses']
        self.assertIsNone(h['tranche_source'])
        self.assertIsNotNone(h['tarif_kwh_txt'])
        joined = ' '.join(h['items'])
        self.assertNotIn('1,75', joined)
        self.assertIn('par tranches', joined)
        # Z3 (ORDRE FONDATEUR, 20/08/2026) — la garde QRES55 comparait le tarif
        # employé à ``constants.KWH_PRICE`` (1,75), un défaut HISTORIQUE que
        # ``pricing`` n'utilise plus : l'égalité n'arrivait jamais et c'est la
        # branche « personnalisé » qui s'imprimait, donc « Tarif électricité :
        # 1,20 MAD/kWh, personnalisé pour votre profil de consommation » — le
        # REPLI ``_FALLBACK_KWH_PRICE`` présenté au client comme SA donnée (sur
        # le PDF legacy comme sur la proposition en ligne, qui sert ce bloc tel
        # quel). Le signal juste est ``savings_estimated``.
        from apps.ventes.quote_engine.pricing import _FALLBACK_KWH_PRICE
        repli_txt = f"{_FALLBACK_KWH_PRICE:.2f}".replace('.', ',')
        self.assertTrue(data['savings_estimated'])
        self.assertNotIn(repli_txt, joined)
        self.assertNotIn('personnalisé', joined)


@tag('pdf')
class TestHypothesesRender(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _render(self, devis, pdf_options=None):
        from weasyprint import HTML
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = build_quote_data(devis, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_qk4.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_block_on_premium_pdf_three_pages(self):
        devis = make_devis(
            self.company, self.user, self.client_obj,
            etude_params={'distributeur': 'onee', 'conso_annuelle': 6000},
            reference='DEV-QK4-PDF')
        # needs a hybrid to render the full residential 2-option layout? No —
        # a réseau-only quote renders as single-option full on the legacy engine.
        html, doc = self._render(devis)
        self.assertIn('Nos hypoth', html)
        # AMOT25 : la note « Loi 82-21 … » est remplacée par la mention sourcée
        # unique MENTION_BT (qui ne cite plus « 82-21 » littéralement) — même
        # péremption que test_qk4 plus haut, corrigée pour le nocturne (CAD177).
        self.assertIn('Revente du surplus non ouverte en basse tension', html)
        self.assertEqual(len(doc.pages), 3)

    def test_residential_renderer_keeps_hypotheses_off_the_pdf(self):
        """QRES61 (fondateur, 2026-07-18) — le PDF résidentiel ne rend PLUS le
        bloc hypothèses (il vit sur la proposition en ligne, WJ32/W359) ; le
        papier garde une clause non-contractuelle qui y renvoie. Les données
        ``hypotheses`` restent servies (proposal-data) — elles ne changent
        rien au rendu papier."""
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.tests.test_quote_engine import _residential_sample_data
        data = _residential_sample_data()
        data['hypotheses'] = {
            'titre': 'Nos hypothèses',
            'items': ['Tarif électricité : barème ONEE par tranche (barème public)',
                      'Économies valorisées sur l\'autoconsommation (loi 82-21).'],
            'autoconso_first': True, 'tranche_source': 'ONEE',
            'tranche_approximatif': False, 'productible_kwh_kwc': 1600,
            'tarif_kwh': 1.2, 'tarif_kwh_txt': '1,20',
        }
        d = renderer._augment(data)
        html = render.build_html(d)
        doc = HTML(string=html).render()
        self.assertNotIn('Nos hypoth', html)
        self.assertIn('Estimations non contractuelles', html)
        self.assertIn('proposition en ligne', html)
        self.assertEqual(len(doc.pages), 3)


class TarifHypotheseModeleHoraireTest(SimpleTestCase):
    """RHOR7 (C-RHOR-007) — en modèle HORAIRE, chaque mois est valorisé au
    barème par tranche : au niveau de règles 3 la ligne « Tarif électricité »
    le dit (même phrase que le modèle « factures », catalogue AMOT52), au lieu
    d'un tarif plat « saisi pour ce devis » que le calcul n'a pas appliqué."""

    def _lignes(self, bareme_horaire, utility='onee'):
        from apps.ventes import etude_horaire as EH
        from apps.ventes.courbes_journalieres import OCCUPATION_PRESENCE
        from apps.ventes.horaire import conso as HC
        from apps.ventes.quote_engine.etude_restitution import restituer_etude
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        conso, _s, _d = HC.profil_depuis_factures(facture_hiver_mad=1500)
        bloc = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=conso, ville='Casablanca',
            occupation=OCCUPATION_PRESENCE, tranches=None,
            charges_fixes_mad=None)
        roi = calculate_savings_roi(6.0, 60000.0, 60000.0, etude_horaire=bloc,
                                    utility='onee', tarif_kwh_override=1.6)
        self.assertEqual(roi['savings_model'], 'horaire')
        sortie = restituer_etude(
            _client_city='Casablanca', _co_productible=None, _corrige=True,
            _utility=utility, _bareme_horaire=bareme_horaire, etude={},
            puissance_kwc=6.0, roi=roi, savings_model=roi['savings_model'],
            savings_model_avec=None, savings_model_sans=None,
            scenario='Sans batterie')
        textes = []

        def _collecter(v):
            if isinstance(v, str):
                textes.append(v)
            elif isinstance(v, dict):
                for x in v.values():
                    _collecter(x)
            elif isinstance(v, (list, tuple)):
                for x in v:
                    _collecter(x)
        _collecter(sortie)
        return [t for t in textes if t.startswith('Tarif électricité')]

    def test_niveau_3_dit_le_bareme_par_tranche(self):
        lignes = self._lignes(True)
        self.assertTrue(lignes)
        self.assertTrue(all('par tranche' in t for t in lignes), lignes)
        self.assertFalse(any('saisi pour ce devis' in t for t in lignes))

    def test_niveau_2_garde_la_ligne_d_origine(self):
        lignes = self._lignes(False)
        self.assertTrue(lignes)
        self.assertFalse(any('par tranche (barème national)' in t
                             for t in lignes), lignes)

    def test_sans_distributeur_niveau_3_bareme_national(self):
        """CE2E5 — lead sans distributeur, modèle horaire : « barème national
        par tranche », jamais « saisi pour ce devis » ; traduite (catalogue)."""
        from apps.ventes.quote_engine.residential.trust import hypothese_traduite
        lignes = self._lignes(True, utility=None)
        self.assertEqual(lignes, ['Tarif électricité : barème national par tranche'])
        self.assertEqual(hypothese_traduite('en', lignes[0]),
                         'Electricity tariff: national schedule by bracket')

    def _exemple(self, recommended):
        """CE2E9 — l'exemple « Comment nous calculons vos économies » d'un
        devis « les deux » au modèle horaire."""
        from apps.ventes import etude_horaire as EH
        from apps.ventes.courbes_journalieres import OCCUPATION_PRESENCE
        from apps.ventes.horaire import conso as HC
        from apps.ventes.quote_engine.etude_restitution import restituer_etude
        from apps.ventes.quote_engine.pricing import calculate_savings_roi
        conso, _s, _d = HC.profil_depuis_factures(facture_hiver_mad=1500)
        bloc = EH.calculer_etude_horaire(
            kwc=6.0, conso_kwh_mensuelles=conso, ville='Casablanca',
            occupation=OCCUPATION_PRESENCE, tranches=None, charges_fixes_mad=None)
        roi = calculate_savings_roi(6.0, 60000.0, 60000.0, etude_horaire=bloc, utility='onee')
        roi['facture_avec_a'] = roi['facture_avec_s'] - 1000  # l'option « avec » économise plus
        sortie = restituer_etude(
            _client_city='Casablanca', _co_productible=None, _corrige=True,
            _utility='onee', _bareme_horaire=True, etude={}, puissance_kwc=6.0, roi=roi,
            savings_model=roi['savings_model'], savings_model_avec=None,
            savings_model_sans=None, scenario='Les deux (Sans + Avec)',
            recommended=recommended)
        methode = sortie[-1]
        return methode['facture_avec_solaire'], roi

    def test_exemple_de_l_option_recommandee_avec_batterie(self):
        servie, roi = self._exemple('Avec batterie')
        self.assertEqual(servie, roi['facture_avec_a'])

    def test_exemple_sans_recommandation_option_sans_inchange(self):
        """Niveau 2 (``recommended`` non passé par le builder) ou option
        « sans » recommandée : l'exemple d'avant, l'option « sans »."""
        for recommended in (None, False, 'Sans batterie'):
            servie, roi = self._exemple(recommended)
            self.assertEqual(servie, roi['facture_avec_s'])

    def test_sans_distributeur_niveau_2_inchange(self):
        lignes = self._lignes(False, utility=None)
        self.assertNotIn('Tarif électricité : barème national par tranche', lignes)
