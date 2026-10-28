"""CIQ314 — O&M, suivi de production et garanties : le document C&I ne
promet que ce que le devis porte (D-CIQ-12).

Rendu RÉEL des deux gabarits sur la charge utile du builder
(``build_quote_data`` → ``echapper_textes_client`` → ``_augment`` →
``build_html``), devis créés en base avec ou sans ligne au rôle ``om_ci``.
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

LIGNES = [
    ('Panneau mono 450W', '40', '1500'),
    ('Onduleur réseau 20 kW', '1', '30000'),
]
INTERDITS = ('O&amp;M', 'O&M', 'upervision', 'performance garantie',
             'engagement de performance')


def _module(mode):
    if mode == 'commercial':
        from apps.ventes.quote_engine.commercial import render, renderer
    else:
        from apps.ventes.quote_engine.industriel import render, renderer
    return render, renderer


def _page_confiance(html, mode):
    racine = 'c3-root' if mode == 'commercial' else 'i3-root'
    return html[html.index(f'class="{racine}"'):]


class ServicesCi(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self._n = 0

    def _devis(self, mode, om=None):
        from apps.stock.models import Produit
        from apps.ventes.models import LigneDevis
        self._n += 10
        devis = make_devis(self.company, self.user, self.client_obj, LIGNES,
                           reference=f'DEV-CIQ314-{self._n:04d}')
        devis.mode_installation = mode
        devis.save(update_fields=['mode_installation'])
        if om is not None:
            produit = Produit.objects.create(
                company=self.company, nom='Contrat O&M annuel',
                sku=f'OM-{self._n}', prix_vente=Decimal(om),
                prix_achat=Decimal('0'), quantite_stock=0, role_ci='om_ci')
            LigneDevis.objects.create(
                devis=devis, produit=produit,
                designation='Contrat O&M : nettoyages, inspection',
                quantite=Decimal('1'), prix_unitaire=Decimal(om),
                remise=Decimal('0'), ordre=99)
        return devis

    def _rendu(self, devis, mode):
        from apps.ventes.quote_engine.builder import (
            build_quote_data, echapper_textes_client,
        )
        render, renderer = _module(mode)
        data = build_quote_data(devis, {'pdf_mode': 'full'})
        d = renderer._augment(echapper_textes_client(data))
        return d, render.build_html(d)

    def test_sans_ligne_om_aucune_promesse(self):
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                d, html = self._rendu(self._devis(mode), mode)
                page = _page_confiance(html, mode)
                for mot in INTERDITS:
                    self.assertNotIn(mot, page)
                synthese = d.get('com_synthese') or d.get('ind_synthese')
                self.assertNotIn('om_option', synthese['services'])
                # AMOT83 (D-ACI-12=a) — le suivi est NOMMÉ, sans délai inventé.
                self.assertEqual(synthese['services']['suivi_production'],
                                 {'delai_intervention': None})

    def test_ligne_om_sans_prix_a_renseigner(self):
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode):
                d, html = self._rendu(self._devis(mode, om='0'), mode)
                page = _page_confiance(html, mode)
                # AMOT98 (D-ACI-17=a) — côté client : « tarif sur demande ».
                self.assertIn('tarif sur demande', page)
                self.assertNotIn('prix à renseigner', page)
                self.assertIn('Contrat O&amp;M : nettoyages, inspection',
                              page)
                synthese = d.get('com_synthese') or d.get('ind_synthese')
                self.assertEqual(synthese['services']['om_option']['statut'],
                                 'tarif_a_renseigner')

    def test_ligne_om_prix_saisi(self):
        d, html = self._rendu(self._devis('commercial', om='4800'),
                              'commercial')
        page = _page_confiance(html, 'commercial')
        self.assertIn('MAD HT', page)
        self.assertNotIn('prix à renseigner', page)
        self.assertNotIn('tarif sur demande', page)
        self.assertEqual(
            d['com_synthese']['services']['om_option']['statut'], 'souscrit')

    def test_delai_saisi_imprime_sinon_omis(self):
        from apps.parametres.models_company import CompanyProfile
        profil, _ = CompanyProfile.objects.get_or_create(company=self.company)
        for mode in ('commercial', 'industriel'):
            with self.subTest(mode=mode, delai=None):
                profil.delai_intervention_suivi_heures = None
                profil.save()
                _d, html = self._rendu(self._devis(mode), mode)
                self.assertNotIn('intervention sous', html)
            with self.subTest(mode=mode, delai=48):
                profil.delai_intervention_suivi_heures = 48
                profil.save()
                _d, html = self._rendu(self._devis(mode), mode)
                self.assertIn('intervention sous 48&#160;h', html)

    def test_garanties_du_fabricant(self):
        d, _html = self._rendu(self._devis('industriel'), 'industriel')
        for garantie in d['ind_synthese']['services']['garanties']:
            self.assertEqual(garantie['source'], 'garantie du fabricant')
            self.assertNotEqual(garantie['composant'], 'installation')


class Amot83ServicesNommes(SimpleTestCase):
    """AMOT83 (D-ACI-12=a) — sans ligne ``om_ci`` ni délai saisi : l'option
    O&M NOMMÉE par la composition (« prix à renseigner ») et « Suivi de
    production inclus » sans délai ; un délai saisi est imprimé."""

    def _services(self, **surcharges):
        from apps.ventes.quote_engine.ci import blocs
        from apps.ventes.quote_engine.ci.synthese import synthese_ci
        from apps.ventes.tests.test_ciq303_synthese_ci_coeur import _data
        from apps.ventes.tests.test_ciq331_pdf_commercial_complet import (
            ETUDE_CI)
        import copy
        data = _data(copy.deepcopy(ETUDE_CI["exemple"]), **surcharges)
        s = synthese_ci(data)
        return s["services"], blocs.bloc_services(s, "c3", "#000", "#111",
                                                  doc=data)

    def test_sans_om_ni_delai_option_nommee_et_suivi_sans_delai(self):
        services, html = self._services()
        self.assertEqual(services["om_option"]["statut"], "tarif_a_renseigner")
        self.assertIn("Contrat O&amp;M (nettoyages, inspection, thermographie, "
                      "test des protections) — tarif sur demande", html)
        self.assertEqual(services["suivi_production"],
                         {"delai_intervention": None})
        self.assertIn("Suivi de production inclus", html)
        self.assertNotIn("intervention sous", html)

    def test_delai_saisi_imprime(self):
        services, html = self._services(delai_intervention_suivi_heures=48)
        self.assertEqual(services["suivi_production"],
                         {"delai_intervention": 48})
        self.assertIn("Suivi de production&#160;: intervention sous "
                      "48&#160;h", html)
        self.assertNotIn("Suivi de production inclus", html)

    def test_ligne_om_du_devis_prime_sur_la_composition(self):
        services, html = self._services(om_ci_lignes=[
            {"designation": "Contrat O&M annuel", "ht": 4800.0,
             "ttc": 5760.0, "optionnelle": False}])
        self.assertEqual(services["om_option"]["statut"], "souscrit")
        self.assertIn("Contrat O&M annuel — 4", html)
        self.assertNotIn("prix à renseigner", html)

    def test_designation_standard_sans_redite_ni_jargon(self):
        """CPDF16 — « Maintenance (O&M) : Exploitation et maintenance (O&M)
        C&I — … » se lisait deux fois et disait « C&I » : le prix seul."""
        _services, html = self._services(om_ci_lignes=[
            {"designation": "Exploitation et maintenance (O&M) C&I",
             "ht": None, "ttc": None, "optionnelle": True}])
        self.assertIn("Maintenance (O&amp;M)&#160;: tarif sur demande", html)
        self.assertNotIn("Exploitation et maintenance", html)
        self.assertNotIn("C&I", html)

    def test_designation_client_sans_c_et_i(self):
        from apps.ventes.quote_engine.ci.installation import (
            designation_client, lignes_client)
        self.assertEqual(designation_client("Coffret DC C&I"), "Coffret DC")
        self.assertEqual(designation_client(
            "Disjoncteur AC 250 A tétrapolaire (C&amp;I)"),
            "Disjoncteur AC 250 A tétrapolaire")
        items = [{"designation": "Coffret AC C&I", "quantite": 1}]
        self.assertEqual(lignes_client(items, {"mode_installation":
                                               "industriel"})[0]
                         ["designation"], "Coffret AC")
        self.assertIs(lignes_client(items, {"mode_installation":
                                            "residentiel"}), items)
        self.assertEqual(items[0]["designation"], "Coffret AC C&I")
