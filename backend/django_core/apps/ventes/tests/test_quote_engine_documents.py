"""Moteur premium — libellés du document, flux générateur, layout v2.

Scindé de `test_quote_engine` le 2026-08-19 (voir ce module).

Littéraux historiques et gabarits éditables, devis créé par l'API puis
rendu en PDF premium, site du locataire dans le rendu, et la garde « le
layout toiture v2 ne bouge NI le document NI les totaux NI les statuts ».

Fixtures partagées : `apps.ventes.tests._quote_engine_common`.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine_documents -v 2
"""

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.models import Devis
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.quote_engine.clauses_cgv import cgv_imprimees
from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_produit,
    make_user,
)


class TestDocLiteralTemplates(TestCase):
    """D2/N60/N67/N26/N59 — textes éditables du devis (couche éditoriale).

    Garantit que (1) avec des réglages PAR DÉFAUT le HTML premium contient
    EXACTEMENT les littéraux historiques (validité, puces CGV, « Bon pour
    accord », garanties en entités HTML), donc le PDF est byte-identique ;
    (2) éditer ``DocumentTemplates`` change réellement le rendu ; (3) le tampon
    d'acceptation N26 n'apparaît QUE lorsque le devis est accepté.
    """

    FULL_LINES = [
        ('Onduleur réseau 10kW', '1', '11700'),
        ('Onduleur hybride 5kW', '1', '24000'),
        ('Panneau mono 550W', '14', '1100'),
        ('Batterie 5 kWh', '1', '14000'),
        ('Structures acier', '14', '375'),
        ('Socles', '30', '67'),
        ('Accessoires', '1', '1667'),
        ('Tableau De Protection AC/DC', '1', '1667'),
        ('Installation', '1', '4000'),
        ('Transport', '1', '1000'),
    ]

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.FULL_LINES)

    def _render(self, pdf_options=None, devis=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G
        data = build_quote_data(devis or self.devis, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_doclit_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html']

    def _echeance(self):
        """Date d'échéance RÉELLE du devis, lue à LA source du backend.

        Jamais ``date.today()`` : le rendu la dérive de ``date_creation`` du
        devis, donc la recalculer autrement ferait passer ce test au rouge une
        nuit sur deux (dérive d'horloge)."""
        from apps.ventes.utils.expiry import date_expiration
        return date_expiration(self.devis).strftime('%d/%m/%Y')

    def test_default_settings_keep_exact_historical_literals(self):
        """Réglages par défaut → littéraux du gabarit ACTUEL, au caractère et à
        l'entité HTML près.

        Ce test prouve qu'aucun réglage vide ne change le rendu ; il suit donc
        les décisions qui ont changé le gabarit lui-même :

        * M7 — la validité n'est plus « 30 jours » mais l'ÉCHÉANCE RÉELLE du
          devis (``date_validite``, sinon création + ``quote_validity_days``) :
          le portail client l'affichait déjà, le PDF affichait une durée.
        * Q5 — le délai d'installation a QUITTÉ la boîte « Conditions », où il
          voisinait la validité, l'échéancier et la TVA et se lisait donc comme
          contractuel ; il est aux « prochaines étapes », suivi de
          « (indicatif) », et vient d'un réglage société.
        * M6 — les garanties ne sont plus des littéraux : sans garantie saisie
          sur les produits de ce montage, le bloc reste sobre et AUCUNE durée
          n'est affirmée (le « 87,4 % », spec Canadian Solar, ne s'imprime plus
          sous un libellé générique).
        """
        # Classe #72 (miroir backend) — le gabarit mélange entités HTML
        # (&#233;, &#160;, &#8217;) et caractères bruts selon la source du
        # fragment : épingler l'échappement EXACT rend le test rouge au
        # moindre déplacement d'un littéral entre gabarits. On épingle le
        # CONTENU : document déséchappé, espaces insécables (U+00A0/U+202F)
        # et apostrophe typographique normalisés.
        import html as html_module
        doc = html_module.unescape(self._render())
        doc = (doc.replace(' ', ' ').replace(' ', ' ')
                  .replace('’', "'"))
        echeance = self._echeance()
        # Validité (badge page 1) — la VRAIE date, pas une durée (M7).
        self.assertIn(f"Validité : jusqu'au {echeance}", doc)
        self.assertNotIn('Validité : 30 jours', doc)
        # Conditions générales — titre + puces.
        self.assertIn('Conditions générales du devis', doc)
        self.assertIn(f"Validité de l'offre : jusqu'au {echeance}", doc)
        self.assertIn('Acompte à la commande : 30%', doc)
        self.assertIn('60% à la réception du matériel', doc)
        self.assertIn('10% après la mise en marche', doc)
        self.assertIn('Tarifs de référence : barème ONEE/SRM', doc)
        # Q5 — le délai est INDICATIF et hors des Conditions.
        self.assertNotIn("Délai d'installation :", doc)
        self.assertIn('7-14 jours ouvrés (indicatif)', doc)
        self.assertIn('Sous 48-72 h (indicatif)', doc)
        # M6 — aucune garantie saisie sur ce montage : rien n'est affirmé.
        self.assertIn('Nos garanties', doc)
        self.assertNotIn('Garanties jusqu', doc)
        self.assertNotIn('87,4', doc)
        # Bon pour accord — titre + mention manuscrite (espaces insécables)
        self.assertIn('Bon pour accord', doc)
        self.assertIn(
            'Lu et approuvé — Signature précédée de « Bon pour accord »',
            doc)

    def test_onepage_default_validity_literal_preserved(self):
        """M7 — le format une page porte la MÊME échéance réelle que les trois
        pages : deux documents du même devis ne peuvent plus annoncer deux
        dates différentes."""
        html = self._render({'pdf_mode': 'onepage'})
        echeance = self._echeance()
        # APDF13 — la validité du une-page est la puce CGV « Validité de
        # l'offre » (cgv_imprimees) ; la ligne « · Validité : jusqu'au … »
        # ne la double plus : la date réelle est imprimée UNE fois.
        self.assertIn(
            '&#183; Validit&#233; de l&#8217;offre&#160;: '
            f'jusqu&#8217;au {echeance}', html)
        self.assertEqual(html.count(f'jusqu&#8217;au {echeance}'), 1)
        self.assertNotIn('Validit&#233;&#160;: 30 jours', html)

    def test_editing_templates_changes_rendered_html(self):
        from apps.parametres.models_documents import DocumentTemplates
        tpl = DocumentTemplates.get(company=self.company)
        tpl.validite_badge_p1 = 'Validité : 45 jours'
        tpl.cgv_titre = 'MES CONDITIONS'
        tpl.cgv_bullets = ['Première puce', 'Acompte {acompte}&#37; à régler']
        tpl.garantie_titre = 'Garanties étendues'
        tpl.bpa_titre = 'ACCORD CLIENT'
        tpl.save()
        html = self._render()
        self.assertIn('Validité : 45 jours', html)
        self.assertIn('MES CONDITIONS', html)
        self.assertIn('Première puce', html)
        self.assertIn('Acompte 30&#37; à régler', html)
        self.assertIn('Garanties étendues', html)
        self.assertIn('ACCORD CLIENT', html)
        # Les littéraux remplacés ne subsistent pas
        self.assertNotIn('Validit&#233;&#160;: 30 jours', html)
        self.assertNotIn('Conditions générales du devis', html)

    def test_empty_template_falls_back_to_literal(self):
        """Un enregistrement existant mais VIDE = aucun changement.

        M6 — le repli n'est plus un LITTÉRAL de garantie (« jusqu'à 30 ans »
        s'imprimait quels que soient les produits) : sans garantie saisie sur
        les produits de ce montage, le bloc reste sobre. Ce que ce test
        protège est intact : une surcharge société vide se comporte comme une
        absence de surcharge.
        """
        from apps.parametres.models_documents import DocumentTemplates
        DocumentTemplates.get(company=self.company)  # crée la ligne, tout vide
        html = self._render()
        self.assertIn('Conditions générales du devis', html)
        self.assertIn('Nos garanties', html)
        self.assertNotIn('Garanties jusqu', html)
        # Le rendu est le MÊME qu'avec aucune ligne DocumentTemplates.
        DocumentTemplates.objects.filter(company=self.company).delete()
        self.assertEqual(len(self._render()), len(html))

    def test_acceptance_stamp_only_when_accepted(self):
        # Non accepté → aucun tampon
        html = self._render()
        self.assertNotIn('Accepté le', html)
        # Accepté (nom + date) → tampon visible avec date FR
        import datetime
        self.devis.accepte_par_nom = 'Reda Kasri'
        self.devis.date_acceptation = datetime.date(2026, 6, 15)
        self.devis.save(update_fields=['accepte_par_nom', 'date_acceptation'])
        html2 = self._render()
        self.assertIn('Accepté le 15/06/2026 par Reda Kasri', html2)
        # Statuts du devis JAMAIS modifiés par le rendu (le moteur ne fait que
        # rendre) — le statut reste « brouillon ».
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')

    def test_acceptance_stamp_absent_when_only_one_field_set(self):
        self.devis.accepte_par_nom = 'Reda Kasri'
        self.devis.save(update_fields=['accepte_par_nom'])
        html = self._render()
        self.assertNotIn('Accepté le', html)

    def test_acceptance_stamp_label_is_editable(self):
        import datetime
        from apps.parametres.models_documents import DocumentTemplates
        tpl = DocumentTemplates.get(company=self.company)
        tpl.acceptance_stamp = 'Signé le {date} — {nom}'
        tpl.save()
        self.devis.accepte_par_nom = 'Karim'
        self.devis.date_acceptation = datetime.date(2026, 1, 2)
        self.devis.save(update_fields=['accepte_par_nom', 'date_acceptation'])
        html = self._render()
        self.assertIn('Signé le 02/01/2026 — Karim', html)


class TestGeneratorQuoteFlow(TestCase):
    """End-to-end flow of the solar generator screen (/ventes/devis/nouveau):
    the screen creates a plain Devis via the REST API, then posts its lines via
    devis-lignes — exactly as exercised here. The created quote must get an
    auto-generated reference and must render the premium PDF in exactly 3 pages.
    """

    def setUp(self):
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import AccessToken
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.api = APIClient()
        token = str(AccessToken.for_user(self.user))
        self.api.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def _create_via_api(self, lignes):
        resp = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis_id = resp.data['id']
        for desig, qty, pu in lignes:
            produit = make_produit(self.company, desig, desig[:20], pu)
            line_resp = self.api.post('/api/django/ventes/devis-lignes/', {
                'devis': devis_id,
                'produit': produit.id,
                'designation': desig,
                'quantite': qty,
                'prix_unitaire': pu,
                'remise': '0',
            }, format='json')
            self.assertEqual(line_resp.status_code, 201, line_resp.data)
        return resp.data

    def test_api_created_devis_gets_auto_reference(self):
        from apps.ventes.models import Devis
        first = self._create_via_api([('Panneau mono 550W', '4', '1100')])
        ref1 = Devis.objects.get(pk=first['id']).reference
        self.assertRegex(ref1, r'^DEV-\d{6}-0001$')
        # Second create must not collide (regression: reference used to be '').
        resp = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        ref2 = Devis.objects.get(pk=resp.data['id']).reference
        self.assertRegex(ref2, r'^DEV-\d{6}-0002$')
        self.assertNotEqual(ref1, ref2)

    def test_generator_created_quote_renders_three_page_premium_pdf(self):
        """A quote shaped exactly like the generator's catalogue auto-fill
        (14 panels, both inverters, battery, structures, socles, power-priced
        accessories) must produce the premium PDF in exactly 3 pages."""
        from weasyprint import HTML
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        created = self._create_via_api([
            ('Panneau mono 550W', '14', '1100'),
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '2', '14000'),
            ('Structures acier', '14', '375'),
            ('Socles', '28', '67'),
            ('Accessoires', '1', '1666.67'),
            ('Tableau De Protection AC/DC', '1', '2500'),
            ('Installation', '1', '6000'),
            ('Transport', '1', '1000'),
        ])

        devis = Devis.objects.get(pk=created['id'])
        data = build_quote_data(devis)

        # Power must come from the panel line the generator wrote.
        self.assertEqual(data['nb_panneaux'], 14)
        self.assertEqual(data['watt_par_panneau'], 550)

        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_generator_flow_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig

        doc = HTML(string=cap['html']).render()
        self.assertEqual(
            len(doc.pages), 3,
            f'generator-created quote must render exactly 3 pages, got {len(doc.pages)}',
        )

    def test_catalogue_quote_renders_three_page_premium_pdf(self):
        """A quote composed from the seeded simulator catalogue (exactly what
        the generator's auto-fill produces for 14 panels x 710 W) must render
        the premium PDF in exactly 3 pages. Prices are the screen's TTC
        converted back to HT, as the save path does."""
        from django.core.management import call_command
        from weasyprint import HTML
        from apps.stock.models import Produit
        from apps.ventes.models import Devis
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        call_command('seed_catalogue', company_slug=self.company.slug)

        # Auto-fill output for 14 x 710 W (9.94 kWc), as saved by the screen:
        # (sku, qty, prix HT = TTC simulateur / 1.2)
        lines = [
            ('OND-R-HUA-10T', '1', None),       # 20 000 TTC
            ('OND-H-DEY-10T', '1', None),       # 28 000 TTC
            ('SMART-MET', '1', None),           # 1 800 TTC
            ('WIFI-DON', '1', None),            # 1 200 TTC
            ('PAN-CS-710', '14', None),         # 1 400 TTC
            ('BAT-DEY-10', '1', None),          # 30 000 TTC
            ('STR-ACIER', '14', None),          # 500 TTC
            ('SOC-BET', '28', None),            # 80 TTC
            # L-FORFAIT (ordre fondateur du 24/08/2026) — ces trois lignes se
            # cotent AU PANNEAU, plus « au bloc ». Les prix ci-dessous sont le
            # barème du stock (`seed_catalogue.BAREMES_FORFAIT`) pour 14
            # panneaux, c'est-à-dire EXACTEMENT ce que l'écran envoie (miroir
            # TTC dans `solar.js` : accessoires 62,5/panneau, tableau
            # 243,75/panneau, installation 2 400 + 300/panneau) :
            ('ACC-CAT', '1', '729.17'),         # 52,0833 x 14 —   875,00 TTC
            ('TAB-PROT', '1', '2843.75'),       # 203,125 x 14 — 3 412,50 TTC
            ('INST-CAT', '1', '5500.00'),       # 2000 + 250 x 14 — 6 600 TTC
            ('TRANS-CAT', '1', None),           # 1 000 TTC
        ]

        resp = self.api.post('/api/django/ventes/devis/', {
            'client': self.client_obj.id,
            'statut': 'brouillon',
            'taux_tva': '20.00',
            'remise_globale': '0',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        devis_id = resp.data['id']

        for sku, qty, prix_ht in lines:
            produit = Produit.objects.get(company=self.company, sku=sku)
            line_resp = self.api.post('/api/django/ventes/devis-lignes/', {
                'devis': devis_id,
                'produit': produit.id,
                'designation': produit.nom,
                'quantite': qty,
                'prix_unitaire': prix_ht or str(produit.prix_vente),
                'remise': '0',
            }, format='json')
            self.assertEqual(line_resp.status_code, 201, line_resp.data)

        devis = Devis.objects.get(pk=devis_id)
        # PV86 — comme les 13 autres fixtures « document à deux options » : le
        # générateur DÉCLARE toujours son scénario (garantie QF7) ; sans la
        # déclaration, deux onduleurs non optionnels = artefact mono-option et
        # le split sans/avec n'existe plus.
        devis.etude_params = {**(devis.etude_params or {}), **DEUX_OPTIONS}
        devis.save(update_fields=['etude_params'])
        data = build_quote_data(devis)

        # Power from the catalogue panel line; both options split correctly.
        self.assertEqual(data['nb_panneaux'], 14)
        self.assertEqual(data['watt_par_panneau'], 710)
        sans = [it['designation'] for it in data['sans_items']]
        avec = [it['designation'] for it in data['avec_items']]
        self.assertIn('Onduleur réseau Huawei 10kW Triphasé', sans)
        self.assertNotIn('Onduleur réseau Huawei 10kW Triphasé', avec)
        self.assertIn('Onduleur hybride Deye 10kW Triphasé', avec)
        self.assertIn('Batterie Dyness 10 kWh', avec)
        self.assertNotIn('Batterie Dyness 10 kWh', sans)
        # QF9 — Smart Meter + Wifi Dongle (accessoires Huawei) restent sur
        # l'option réseau Huawei (sans) mais sont retirés de l'option hybride
        # Deye (avec).
        self.assertIn('Smart Meter', sans)
        self.assertIn('Wifi Dongle', sans)
        self.assertNotIn('Smart Meter', avec)
        self.assertNotIn('Wifi Dongle', avec)
        # Option totals match the simulator for the same inputs (±1 MAD rounding).
        # total_avec = ancien 103 040 − Smart Meter (1 800) − Wifi (1 200) Huawei.
        # L-FORFAIT (24/08/2026) : les trois forfaits au panneau valent 1 093,75
        # HT de MOINS qu'au barème « au bloc » d'avant, sur les DEUX options (ce
        # sont des lignes communes) — d'où 65 040 → 63 728 et 100 040 → 98 728.
        # QJR220 (31/08/2026) a rendu la divergence VISIBLE : le viewset de
        # lignes re-tarife désormais ces forfaits comme le faisaient déjà l'écran
        # et la composition, donc un prix « au bloc » posté ici ne survivait plus
        # à l'enregistrement.
        # ARRONDI-100 (02/10/2026) : chaque total d'option est ramené au
        # palier de 100 MAD inférieur — 63 727,71 → 63 700,00 et
        # 98 727,72 → 98 700,00 (les prix des lignes ne bougent pas).
        self.assertAlmostEqual(data['total_sans'], 63700.0, delta=1)
        self.assertAlmostEqual(data['total_avec'], 98700.0, delta=1)

        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_catalogue_quote_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig

        doc = HTML(string=cap['html']).render()
        self.assertEqual(
            len(doc.pages), 3,
            f'catalogue quote must render exactly 3 pages, got {len(doc.pages)}',
        )


@tag('pdf')
class TestBuilderTenantSiteRendered(TestCase):
    """SCA27 (complément, rendu réel) — un devis résidentiel d'un tenant #2 avec
    site rempli produit un PDF SANS aucune trace de ``taqinor.ma`` (ligne site du
    pied de page + liens fiches). Rendu WeasyPrint lourd → ``@tag('pdf')``."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def test_no_taqinor_anywhere_when_tenant_fills_site(self):
        from apps.ventes.quote_engine import build_quote_data
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.parametres.models import CompanyProfile
        p = CompanyProfile.get(company=self.company)
        p.nom = 'Helios SARL'
        p.email = 'hello@helios.ma'
        p.telephone = '+212 5 22 00 00 00'
        p.site_web = 'helios.ma'
        p.save()
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau mono 550W', '14', '1100'),
            ('Onduleur réseau 10kW', '1', '11700'),
            ('Onduleur hybride 5kW', '1', '24000'),
            ('Batterie 5 kWh', '1', '14000'),
        ], reference='DEV-SCA27-REND', etude_params={
            **DEUX_OPTIONS,
            # M1 — plus de facture proxy : le renderer résidentiel exige des
            # factures RÉELLES pour ne pas lever Unsupported dans _augment.
            'factures_mensuelles_reelles': [
                1200, 1200, 1300, 1400, 1600, 1800,
                1900, 1900, 1700, 1500, 1300, 1200],
        })
        data = build_quote_data(devis)
        d = renderer._augment(data)
        html = render.build_html(d)
        # SON site partout, ZÉRO taqinor.ma.
        self.assertIn('helios.ma', html)
        self.assertNotIn('taqinor.ma', html)
        # Le pied de page porte SES coordonnées (identité DC1 déjà câblée).
        self.assertIn('hello@helios.ma', html)
        self.assertNotIn('contact@taqinor.com', html)


class TestLayoutV2NeBougePasLeDocument(TestCase):
    """PV24 — le layout v2 allume un chemin du builder : on le VERROUILLE.

    ``build_quote_data`` écrase ``puissance_kwc`` avec ``roof_layout['result']
    ['kwc']`` (builder.py, bloc « Q5 — Toiture 3D »). Ce chemin est resté
    THÉORIQUE tant que l'outil 3D sérialisait en v1 : le blob v1 ne porte
    AUCUN bloc ``result``, donc la condition n'était jamais vraie. Depuis PV13
    la sérialisation est en v2 et le bloc ``result`` est TOUJOURS là — ce
    chemin s'allume donc en production, sur tous les devis venus de la 3D.

    Règle #4 : la puissance affichée peut suivre le calepinage réel (c'est le
    but), mais le DOCUMENT lui-même ne bouge pas — mêmes pages, mêmes totaux.
    Les totaux naissent des LIGNES et d'elles seules ; aucun champ de layout
    n'a le droit de s'inviter dans la chaîne
    Sous-total HT → Remise → Total HT → TVA → Total TTC.
    """

    #: Clés de TOTAUX de ``build_quote_data`` — la chaîne monétaire complète.
    CLES_TOTAUX = ('total_sans', 'total_avec', 'total_sans_before',
                   'total_avec_before', 'totaux_sans', 'totaux_avec',
                   'totaux_all', 'discount_pct', 'per_line_tva')

    @staticmethod
    def _layout_v1():
        """Le blob HISTORIQUE : géométrie de zones, AUCUN bloc ``result``."""
        return {
            'version': 1,
            'pin': {'lat': 33.57, 'lng': -7.58},
            'outline': [[33.57, -7.58], [33.58, -7.58], [33.58, -7.57]],
            'billKwh': 900,
            'activeAreaId': 'z1',
            'zones': [{
                'id': 'z1', 'label': 'Pan Sud',
                'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
                'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
                'facingAzimuthDeg': 0, 'neededPanels': 14,
            }],
        }

    @classmethod
    def _layout_v2(cls):
        """Le MÊME toit, sérialisé en v2 (PV13) : + result/scenario/panelWatt."""
        layout = cls._layout_v1()
        layout.update({
            'version': 2,
            'result': {'panels': 14, 'kwc': 8.4, 'annualKwh': 13000,
                       'savings': 11000},
            'scenario': 'reseau',
            'panelWatt': 600,
            'battery': None,
            'source': 'devis',
            'devisId': 4242,
        })
        layout['zones'][0]['geometry'] = {
            'azimuthDeg': 0, 'tiltDeg': 30, 'family': 'portrait',
            'flush': True, 'kwc': 8.4, 'count': 14, 'origin': [0, 0],
            'panels': [],
        }
        return layout

    def setUp(self):
        from apps.ventes.tests.test_quote_engine_formats import TestPdfFormats

        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        # MÊME fixture golden que les garde-fous de pagination existants
        # (``TestPdfFormats``) : le nombre de pages testé ici est donc bien
        # celui du document de référence, pas celui d'un devis inventé.
        self.devis = make_devis(
            self.company, self.user, self.client_obj,
            TestPdfFormats.FULL_LINES, reference='DEV-PV24-001')

    def _data(self, layout, pdf_options=None, devis=None):
        from apps.ventes.quote_engine.builder import build_quote_data

        devis = devis or self.devis
        Devis.objects.filter(pk=devis.pk).update(roof_layout=layout)
        devis.refresh_from_db()
        return build_quote_data(devis, pdf_options)

    def _pages(self, layout, pdf_options=None):
        from weasyprint import HTML
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = self._data(layout, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_pv24_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return len(HTML(string=cap['html']).render().pages)

    def test_le_chemin_v2_s_allume_vraiment(self):
        """Sans cette divergence, tout le reste du module serait vide de sens.

        PVUNI (fondateur 18/08/2026) — ce qui diverge a CHANGÉ de nature. Le
        chemin v2 apportait la PUISSANCE (``v2['puissance_kwc'] == 8.4``, le
        kWc du calepinage) alors que les lignes disent 14 × 550 W = 7,7 kWc :
        deux bases de puissance dans un même document, le défaut exact de
        l'incident DEV-202608-0007. Les LIGNES sont désormais la source unique
        de la puissance ; le chemin v2 s'allume toujours, mais sur ce qu'il est
        seul à savoir — la PRODUCTION du site, recalée sur la taille vendue
        (13 000 × 7,7 / 8,4 = 11 917).

        AMOT15 (D-ACAL-6, « la production montrée au client = celle du moteur
        devis ») — la production du calepinage, même recalée, n'est plus
        imprimée : v1 et v2 servent la MÊME production, celle du moteur. Le
        chemin v2 s'allume désormais sur l'ÉCONOMIE du calepinage, recalée sur
        la taille vendue (11 000 × 7,7 / 8,4 = 10 083) et passée à LA chaîne
        de calcul (``economie_imposee``).
        """
        v1 = self._data(self._layout_v1())
        v2 = self._data(self._layout_v2())
        # La puissance ne bouge plus : elle vient des lignes, des deux côtés.
        self.assertEqual(v2['puissance_kwc'], 7.7)
        self.assertEqual(v1['puissance_kwc'], v2['puissance_kwc'])
        self.assertEqual(
            round(v2['puissance_kwc'] * 1000),
            v2['nb_panneaux'] * v2['watt_par_panneau'])
        # AMOT15 (D-ACAL-6) — la production est celle du moteur devis des deux
        # côtés, jamais la production recalée du calepinage (11 917).
        self.assertEqual(v2['prod_kwh'], v1['prod_kwh'])
        self.assertNotEqual(v2['prod_kwh'], 13000)
        if v1['prod_kwh'] != 11917:
            self.assertNotEqual(v2['prod_kwh'], 11917)
        # Mais le chemin v2 s'allume bel et bien : son économie recalée entre
        # dans le document, là où v1 (aucun bloc ``result``) n'apporte rien.
        self.assertEqual(v2['eco_s_ann'], 10083)
        self.assertNotEqual(v1['eco_s_ann'], v2['eco_s_ann'])

    def test_les_totaux_sont_identiques_au_centime(self):
        v1 = self._data(self._layout_v1())
        v2 = self._data(self._layout_v2())
        for cle in self.CLES_TOTAUX:
            self.assertEqual(v1[cle], v2[cle],
                             'le layout v2 a bougé le total « %s »' % cle)

    def test_les_totaux_remises_sont_identiques(self):
        """La remise globale est le maillon fragile de la chaîne : verrouillé.

        Un devis REMISÉ fait vivre les trois maillons intermédiaires
        (``ht_brut`` → ``remise`` → ``ht_net``) que le devis golden, sans
        remise, laisse au repos.
        """
        from apps.ventes.tests.test_quote_engine_formats import TestPdfFormats

        remise = make_devis(
            self.company, self.user, self.client_obj,
            TestPdfFormats.FULL_LINES, remise_globale='12',
            reference='DEV-PV24-002')
        v1 = self._data(self._layout_v1(), devis=remise)
        v2 = self._data(self._layout_v2(), devis=remise)
        self.assertGreater(v1['totaux_all']['remise'], 0)
        for cle in self.CLES_TOTAUX:
            self.assertEqual(v1[cle], v2[cle],
                             'le layout v2 a bougé le total « %s »' % cle)

    def test_les_totaux_ignorent_aussi_un_layout_absent(self):
        """Aucun layout, v1, v2 : la chaîne monétaire est la MÊME partout."""
        sans = self._data(None)
        for layout in (self._layout_v1(), self._layout_v2()):
            avec = self._data(layout)
            for cle in self.CLES_TOTAUX:
                self.assertEqual(sans[cle], avec[cle],
                                 'le layout a bougé le total « %s »' % cle)

    def test_le_premium_reste_a_trois_pages(self):
        self.assertEqual(self._pages(self._layout_v1()), 3)
        self.assertEqual(self._pages(self._layout_v2()), 3)

    def test_la_une_page_reste_a_une_page(self):
        options = {'pdf_mode': 'onepage'}
        self.assertEqual(self._pages(self._layout_v1(), options), 1)
        self.assertEqual(self._pages(self._layout_v2(), options), 1)

    def test_le_layout_v2_n_ecrit_aucun_statut(self):
        """Règle #4 — le builder REND, il ne change jamais un statut."""
        self._data(self._layout_v2())
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.statut, 'brouillon')


# APDF12-APDF14 (C-APDF-005, C-APDF-006) — les conditions générales
# imprimées ont UNE source : ``clauses_cgv.cgv_imprimees(data)``.
#
# APDF12 — ``CgvImprimeesTests`` : la variante C&I (gelée à l'envoi ou vive)
# garde SON titre, ses marqueurs {echeancier}/{retenue} sont substitués dans les
# deux états, et son gel n'est plus recopié dans ``doc_texts['cgv_bullets']``.
# Moteur réel (``build_quote_data``, envoi réel ``mark_devis_sent``), aucune
# doublure. Test-du-test : rétablir la boucle ERR-QJR668 qui recopie TOUTE
# entrée ``cgv_gelees`` dans ``doc_texts['cgv_bullets']`` (builder) ⇒
# ``test_gel_ci_pas_recopie_dans_cgv_bullets`` échoue.
#
# APDF13 — ``CgvTousFormatsTests`` : le résidentiel premium (page 3, à la place
# du bloc « Conditions » composé en dur), l'agricole 3 pages et le une-page
# impriment ``cgv_imprimees(data)``, sans changer les nombres de pages.
# Test-du-test : remettre le bloc « Conditions » en dur de
# ``residential/trust.py`` ⇒ ``test_puces_societe_imprimees[residentiel]``
# échoue.
#
# APDF14 — ``GelCompletLectureTests`` : un devis envoyé ou signé imprime
# l'ENSEMBLE des textes contractuels gelés à l'envoi (``doc_texts_geles``,
# APDF20) ; un brouillon lit les textes vifs ; un envoyé d'avant ce gel garde
# le comportement d'hier.

TITRE_IND = 'CGV INDUSTRIEL SPECIFIQUES'
PUCES_IND = ['Echeancier {echeancier}', 'Retenue {retenue}',
             'Clause industrielle XYZ']


class CgvImprimeesFormeTests(SimpleTestCase):
    """APDF12 — la forme ``{titre, puces}`` (contrat d'APDF19 / APDF35)."""

    def test_variante_ci_titre_et_puces(self):
        sortie = cgv_imprimees({'cgv_ci': ['A', ' ', 'B'],
                                'cgv_ci_titre': 'T'})
        self.assertEqual(sortie, {'titre': 'T', 'puces': ['A', 'B']})

    def test_sans_variante_puces_societe_et_titre_par_defaut(self):
        sortie = cgv_imprimees({'doc_texts': {
            'cgv_bullets': ['Perso {acompte}&#37;']},
            'payment_terms': {'acompte': 40}})
        self.assertEqual(set(sortie), {'titre', 'puces'})
        self.assertEqual(sortie['puces'], ['Perso 40&#37;'])
        self.assertEqual(sortie['titre'], 'Conditions générales du devis')
        self.assertEqual(
            cgv_imprimees({'langue_sortie': 'en'})['titre'],
            'General terms of the quote')


class CgvImprimeesTests(TestCase):
    """APDF12 — variante C&I industrielle, brouillon puis envoyé."""

    def setUp(self):
        from apps.parametres.models_documents import DocumentTemplates
        self.company = make_company(slug='apdf12-co', nom='APDF12')
        modele = DocumentTemplates.get(company=self.company)
        modele.cgv_par_mode = {'industriel': {
            'titre': TITRE_IND, 'bullets': list(PUCES_IND)}}
        modele.save()
        self.devis = make_devis(
            self.company, make_user(self.company), make_client(self.company),
            [('Panneau mono 450W', '40', '1500'),
             ('Onduleur réseau 20 kW', '1', '30000')],
            reference='DEV-APDF12-1')
        self.devis.mode_installation = 'industriel'
        self.devis.save(update_fields=['mode_installation'])

    def _envoyer(self):
        from apps.ventes.domain.envoi import mark_devis_sent
        mark_devis_sent(devis=self.devis)
        self.devis.refresh_from_db()

    def _etats(self):
        yield 'brouillon', build_quote_data(self.devis, {})
        self._envoyer()
        yield 'envoye', build_quote_data(self.devis, {})

    def test_titre_variante_imprime(self):
        for etat, data in self._etats():
            with self.subTest(etat=etat):
                self.assertEqual(cgv_imprimees(data)['titre'], TITRE_IND)

    def test_marqueurs_substitues_brouillon_et_envoye(self):
        for etat, data in self._etats():
            with self.subTest(etat=etat):
                puces = cgv_imprimees(data)['puces']
                self.assertIn('Clause industrielle XYZ', puces)
                texte = ' '.join(puces)
                self.assertNotIn('{echeancier}', texte)
                self.assertNotIn('{retenue}', texte)
                echeancier = [p for p in puces if p.startswith('Echeancier')]
                self.assertEqual(len(echeancier), 1)
                self.assertIn('%', echeancier[0])

    def test_gel_ci_pas_recopie_dans_cgv_bullets(self):
        self._envoyer()
        gels = [c for c in self.devis.clauses_appliquees or []
                if isinstance(c, dict) and c.get('type') == 'cgv_gelees']
        self.assertTrue(gels and gels[0].get('mode') == 'industriel')
        data = build_quote_data(self.devis, {})
        puces = (data.get('doc_texts') or {}).get('cgv_bullets') or []
        self.assertNotIn('Clause industrielle XYZ', ' '.join(map(str, puces)))
        self.assertIn('Clause industrielle XYZ', cgv_imprimees(data)['puces'])

    @tag('pdf')
    def test_titre_variante_dans_le_pdf(self):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            rendre_pdf, texte_pdf)
        for etat in ('brouillon', 'envoye'):
            if etat == 'envoye':
                self._envoyer()
            with self.subTest(etat=etat):
                texte = texte_pdf(rendre_pdf(self.devis))
                self.assertIn(TITRE_IND, texte)
                self.assertNotIn('{echeancier}', texte)


# ── APDF13 — cgv_imprimees imprimé par le résidentiel, l'agricole, le une-page

MARQUEUR = 'PENALITE-X4 de retard 1 % par mois'
PUCES_SOCIETE = ['{validite_offre}', MARQUEUR,
                 'Acompte à la commande&#160;: {acompte}&#37;']


def _html_formats(**surcharges):
    """HTML des trois gabarits qui n'imprimaient pas les CGV (données
    d'échantillon, sans base) : résidentiel premium, une-page, agricole."""
    import copy
    from apps.ventes.quote_engine import generate_devis_premium as G
    from apps.ventes.quote_engine.agricole import pages as a_pages
    from apps.ventes.quote_engine.agricole import renderer as a_renderer
    from apps.ventes.quote_engine.residential import render as r_render
    from apps.ventes.quote_engine.residential import renderer as r_renderer
    from apps.ventes.quote_engine.residential import sample_data
    from apps.ventes.tests import _moteur_fixtures as mf
    from apps.ventes.tests.test_agr310_renderer_agricole import data_complete
    s = copy.deepcopy(surcharges)
    return {
        'residentiel': r_render.build_html(r_renderer._augment(
            dict(copy.deepcopy(sample_data.build('deux')), **s))),
        'une_page': G.render_html_for(mf.donnees_legacy(
            'deux', pdf_mode='onepage', **copy.deepcopy(s))),
        'agricole': a_pages.build_html(a_renderer._augment(
            dict(data_complete(), **copy.deepcopy(s)))),
    }


class CgvTousFormatsHtmlTests(SimpleTestCase):
    """APDF13 — les puces de ``cgv_imprimees`` dans chaque gabarit (pur)."""

    def test_puces_societe_imprimees(self):
        for nom, html in _html_formats(
                doc_texts={'cgv_bullets': PUCES_SOCIETE}).items():
            with self.subTest(gabarit=nom):
                self.assertIn(MARQUEUR, html)

    def test_defaut_tarifs_de_reference(self):
        for nom, html in _html_formats().items():
            with self.subTest(gabarit=nom):
                if nom == 'agricole':
                    # AGR310 — aucun barème ONEE/SRM sur un devis agricole.
                    self.assertNotIn('ONEE', html)
                else:
                    self.assertIn('Tarifs de référence', html)

    def test_residentiel_plus_de_ligne_paiement_composee(self):
        html = _html_formats()['residentiel']
        self.assertNotIn('à la mise en service</span>', html)
        self.assertNotIn('Selon barème en vigueur', html)


@tag('pdf')
class CgvTousFormatsTests(TestCase):
    """APDF13 — PDF RÉEL : marché × format, puce société imprimée, pages
    inchangées (``test_quote_engine`` : 3 / 1, industriel 4 / 1)."""

    PAGES = {'residentiel': (3, 1), 'agricole': (3, 1),
             'commercial': (3, 1), 'industriel': (4, 1)}

    def setUp(self):
        from apps.parametres.models_documents import DocumentTemplates
        from apps.ventes.tests.test_pdf_apdf_identite import MARCHES
        self.company = make_company(slug='apdf13-co', nom='APDF13')
        modele = DocumentTemplates.get(company=self.company)
        modele.cgv_bullets = list(PUCES_SOCIETE)
        modele.save()
        user, client = make_user(self.company), make_client(self.company)
        self.devis = {}
        for marche, (lignes, etude, mode) in MARCHES.items():
            devis = make_devis(self.company, user, client, lignes,
                               reference=f'DEV-APDF13-{marche[:4].upper()}',
                               etude_params=dict(etude) if etude else None)
            devis.mode_installation = mode
            devis.save(update_fields=['mode_installation'])
            self.devis[marche] = devis

    def _lire(self, devis, options):
        import fitz
        from apps.ventes.tests.test_pdf_apdf_identite import rendre_pdf
        doc = fitz.open(stream=rendre_pdf(devis, options), filetype='pdf')
        try:
            return ('\n'.join(p.get_text() for p in doc).replace('\xa0', ' '),
                    len(doc))
        finally:
            doc.close()

    def test_marqueur_imprime(self):
        for marche, devis in self.devis.items():
            for nom, options in (('defaut', {}),
                                 ('onepage', {'pdf_mode': 'onepage'}),
                                 ('include_etude', {'include_etude': True})):
                with self.subTest(marche=marche, format=nom):
                    texte, _pages = self._lire(devis, options)
                    self.assertIn('PENALITE-X4', texte)

    def test_pages_inchangees(self):
        for marche, devis in self.devis.items():
            attendu = self.PAGES[marche]
            with self.subTest(marche=marche):
                self.assertEqual(
                    (self._lire(devis, {})[1],
                     self._lire(devis, {'pdf_mode': 'onepage'})[1]),
                    attendu)


# ── APDF14 — lecture du gel COMPLET des textes contractuels ────────────────
# Test-du-test : ignorer l'entrée ``doc_texts_geles`` dans
# ``build_quote_data`` ⇒ ``test_envoye_imprime_textes_A_apres_edition``
# échoue.

TEXTES_A = {'cgv_bullets': ['CGV-A puce'], 'cgv_titre': 'TITRE-A',
            'bpa_mention': 'BPA-A', 'garantie_detail': 'GARANTIE-A'}
TEXTES_B = {'cgv_bullets': ['CGV-B puce'], 'cgv_titre': 'TITRE-B',
            'bpa_mention': 'BPA-B', 'garantie_detail': 'GARANTIE-B'}


class GelCompletLectureTests(TestCase):
    """APDF14 — devis envoyé : textes A gelés, édités en B ensuite."""

    def setUp(self):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel)
        self.company = make_company(slug='apdf14-co', nom='APDF14')
        self._textes(TEXTES_A)
        self.devis = devis_residentiel(self.company, 'DEV-APDF14-1')

    def _textes(self, textes):
        from apps.parametres.models_documents import DocumentTemplates
        modele = DocumentTemplates.get(company=self.company)
        for cle, valeur in textes.items():
            setattr(modele, cle, valeur)
        modele.save()

    def _envoyer(self):
        from apps.ventes.domain.envoi import mark_devis_sent
        mark_devis_sent(devis=self.devis)
        self.devis.refresh_from_db()

    def _legacy_etude(self):
        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine.builder import clean_pdf_options
        return G.render_html_for(build_quote_data(
            self.devis, clean_pdf_options({'include_etude': True})))

    def test_envoye_imprime_textes_A_apres_edition(self):
        self._envoyer()
        avant = list(self.devis.clauses_appliquees)
        self._textes(TEXTES_B)
        data = build_quote_data(self.devis, {})
        self.assertEqual(cgv_imprimees(data),
                         {'titre': 'TITRE-A', 'puces': ['CGV-A puce']})
        self.assertEqual(data['doc_texts']['bpa_mention'], 'BPA-A')
        html = self._legacy_etude()
        for attendu in ('TITRE-A', 'BPA-A', 'GARANTIE-A', 'CGV-A puce'):
            self.assertIn(attendu, html)
        for interdit in ('TITRE-B', 'BPA-B', 'GARANTIE-B', 'CGV-B'):
            self.assertNotIn(interdit, html)
        # CLAUSE PERSISTANCE — le rendu ne touche pas au gel.
        self.devis.refresh_from_db()
        self.assertEqual(self.devis.clauses_appliquees, avant)

    def test_brouillon_lit_vif(self):
        self._textes(TEXTES_B)
        data = build_quote_data(self.devis, {})
        self.assertEqual(cgv_imprimees(data),
                         {'titre': 'TITRE-B', 'puces': ['CGV-B puce']})
        self.assertEqual(data['doc_texts']['bpa_mention'], 'BPA-B')

    def test_ancien_envoye_sans_gel(self):
        from apps.ventes.models import Devis
        self._envoyer()
        sans_gel = [c for c in self.devis.clauses_appliquees
                    if not (isinstance(c, dict)
                            and c.get('type') == 'doc_texts_geles')]
        Devis.objects.filter(pk=self.devis.pk).update(
            clauses_appliquees=sans_gel)
        self.devis.refresh_from_db()
        self._textes(TEXTES_B)
        data = build_quote_data(self.devis, {})
        # Comportement d'avant APDF20 : puces gelées (ERR-QJR668), le reste vif.
        self.assertEqual(cgv_imprimees(data)['puces'], ['CGV-A puce'])
        self.assertEqual(data['doc_texts']['cgv_titre'], 'TITRE-B')
        self.assertEqual(data['doc_texts']['bpa_mention'], 'BPA-B')

    def test_correction_ancien_envoye_garde_les_cgv_recues(self):
        """Envoyé d'avant APDF20 (CGV A gelées seules), CGV éditées en B,
        puis correction sur place : ``figer_clauses_devis`` pose un
        ``doc_texts_geles`` aux CGV B — le rendu imprime toujours A.
        Test-du-test : rappliquer ``cgv_gelees`` AVANT le choix de
        ``_doc_texts_geles`` (builder) ⇒ ce test échoue."""
        from apps.ventes.domain.envoi import figer_clauses_devis
        self._envoyer()
        Devis.objects.filter(pk=self.devis.pk).update(clauses_appliquees=[
            c for c in self.devis.clauses_appliquees
            if c.get('type') != 'doc_texts_geles'])
        self.devis.refresh_from_db()
        self._textes(TEXTES_B)
        self.assertTrue(figer_clauses_devis(self.devis))
        geles = [c['textes'] for c in self.devis.clauses_appliquees
                 if c.get('type') == 'doc_texts_geles']
        self.assertEqual(geles[0]['cgv_bullets'], ['CGV-B puce'])
        data = build_quote_data(self.devis, {})
        self.assertEqual(data['doc_texts']['cgv_bullets'], ['CGV-A puce'])
        self.assertEqual(cgv_imprimees(data)['puces'], ['CGV-A puce'])

    @tag('pdf')
    def test_defaut_premium_imprime_textes_A(self):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            rendre_pdf, texte_pdf)
        self._envoyer()
        self._textes(TEXTES_B)
        texte = texte_pdf(rendre_pdf(self.devis))
        self.assertIn('CGV-A puce', texte)
        self.assertNotIn('CGV-B', texte)


class DocTextsGelesFiltreTests(SimpleTestCase):
    """APDF14 — seules les vraies surcharges du gel sont reprises."""

    def test_defauts_geles_ignores(self):
        from types import SimpleNamespace
        from apps.ventes.quote_engine.builder import _doc_texts_geles
        from apps.ventes.quote_engine.generate_devis_premium import (
            DEFAULT_DOC_TEXTS)
        entree = {'type': 'doc_texts_geles', 'version': 2, 'textes': {
            'cgv_bullets': list(DEFAULT_DOC_TEXTS['cgv_bullets']),
            'cgv_titre': 'TITRE-A', 'garantie_titre': ''}}
        envoye = SimpleNamespace(statut='envoye', clauses_appliquees=[entree])
        self.assertEqual(_doc_texts_geles(envoye), {'cgv_titre': 'TITRE-A'})
        brouillon = SimpleNamespace(statut='brouillon',
                                    clauses_appliquees=[entree])
        self.assertIsNone(_doc_texts_geles(brouillon))
        self.assertIsNone(_doc_texts_geles(
            SimpleNamespace(statut='envoye', clauses_appliquees=[])))


class CgvPage3BorneeTests(SimpleTestCase):
    """APDF13 (fix) — la boîte « Conditions » de la page 3 a un budget : la
    page ne grandit jamais à cause des CGV, la bande légale reste dans le
    cadre A4 (``test_bottom_content_never_silently_clipped``)."""

    def test_defaut_entier(self):
        from apps.ventes.quote_engine.residential import trust
        puces = ['Validité', 'Acompte à la commande&#160;: 30&#37;', 'TVA']
        self.assertEqual(trust.puces_cgv_bornees({}, puces), puces)

    def test_cgv_longues_suite_declaree(self):
        from apps.ventes.quote_engine.residential import trust
        puces = [f'Clause n° {n} : ' + 'texte contractuel long ' * 6
                 for n in range(1, 9)]
        bornees = trust.puces_cgv_bornees({}, puces)
        self.assertLess(len(bornees), len(puces) + 1)
        self.assertEqual(bornees[-1],
                         'Suite des conditions : proposition en ligne')
        visible = sum(len(trust._visible(p)) + 3 for p in bornees[:-1])
        self.assertLessEqual(visible, trust.CGV_MAX_CARACTERES)
        unique = trust.puces_cgv_bornees({}, ['mot ' * 300])
        self.assertTrue(unique[0].endswith('&#8230;'))
        self.assertLessEqual(len(trust._visible(unique[0])),
                             trust.CGV_MAX_CARACTERES + 1)

    def test_bande_legale_de_l_echantillon_lue_du_profil(self):
        """Le profil TAQINOR de la démonstration est renseigné (D-APDF-1) : sa
        bande porte « SARLAU » + RC/ICE et la clause non contractuelle."""
        import re
        html = _html_formats()['residentiel']
        bande = re.search(r'<div class="p3-legal">(.*?)</div>', html,
                          re.S).group(1)
        for attendu in ('SARLAU', 'RC 691213', 'ICE 003799642000067',
                        'non contractuelles'):
            self.assertIn(attendu, bande)
