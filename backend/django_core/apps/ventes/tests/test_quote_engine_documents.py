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

from django.test import TestCase, tag

from apps.ventes.models import Devis
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
        self.assertNotIn('87,4', html)
        # Bon pour accord — titre + mention manuscrite (espaces insécables)
        self.assertIn('Bon pour accord', html)
        self.assertIn(
            'Lu et approuvé — Signature précédée de « Bon pour accord »',
            html)

    def test_onepage_default_validity_literal_preserved(self):
        """M7 — le format une page porte la MÊME échéance réelle que les trois
        pages : deux documents du même devis ne peuvent plus annoncer deux
        dates différentes."""
        html = self._render({'pdf_mode': 'onepage'})
        self.assertIn(
            f'&#183; Validit&#233;&#160;: jusqu&#8217;au {self._echeance()}',
            html)
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
            ('ACC-CAT', '1', '1666.67'),        # formule : 2 blocs x 1000 TTC
            ('TAB-PROT', '1', '2500.00'),       # formule : 2 blocs x 1500 TTC
            ('INST-CAT', '1', '6000.00'),       # formule : 3 x 2400 TTC
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
        self.assertAlmostEqual(data['total_sans'], 65040, delta=1)
        self.assertAlmostEqual(data['total_avec'], 100040, delta=1)

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
        """
        v1 = self._data(self._layout_v1())
        v2 = self._data(self._layout_v2())
        # La puissance ne bouge plus : elle vient des lignes, des deux côtés.
        self.assertEqual(v2['puissance_kwc'], 7.7)
        self.assertEqual(v1['puissance_kwc'], v2['puissance_kwc'])
        self.assertEqual(
            round(v2['puissance_kwc'] * 1000),
            v2['nb_panneaux'] * v2['watt_par_panneau'])
        # Mais le chemin v2 s'allume bel et bien : sa production recalée entre
        # dans le document, là où v1 (aucun bloc ``result``) n'apporte rien.
        self.assertEqual(v2['prod_kwh'], 11917)
        self.assertNotEqual(v1['prod_kwh'], v2['prod_kwh'])

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
