"""Moteur premium — proposition RÉSIDENTIELLE redessinée.

Scindé de `test_quote_engine` le 2026-08-19 (voir ce module).

Rendu de `quote_engine/residential/` : pagination jamais débordée, fiches
produits, cache du chemin chaud, lien de signature + numérotation des
pages, devis mono-option, pied de page et marque blanche du locataire.

Fixtures partagées : `apps.ventes.tests._quote_engine_common`.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_quote_engine_residential -v 2
"""

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, _residential_sample_data, make_client, make_company,
    make_devis, make_user,
)


@tag('pdf')
class TestResidentialRenderer(TestCase):
    """The redesigned residential 3-page proposal (the engine that renders a
    real residentiel quote). The legacy-engine page-count tests above don't
    exercise this renderer, so guard its layout + display polish here."""

    def _html_and_doc(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        d = renderer._augment(_residential_sample_data())
        html = render.build_html(d)
        return html, HTML(string=html).render()

    def test_residential_proposal_is_exactly_three_pages(self):
        _, doc = self._html_and_doc()
        self.assertEqual(
            len(doc.pages), 3,
            f'residential proposal must render exactly 3 pages, got {len(doc.pages)}')

    def test_render_pdf_bytes_smoke(self):
        from apps.ventes.quote_engine.residential import renderer
        pdf = renderer.render_pdf_bytes(_residential_sample_data())
        self.assertEqual(pdf[:4], b'%PDF')
        self.assertGreater(len(pdf), 5000)

    def test_client_name_is_display_cased_everywhere(self):
        """'meryem hida' is shown 'Meryem Hida' on the cover greeting and the
        signature block — never the raw lower-case input."""
        html, _ = self._html_and_doc()
        self.assertIn('Bonjour Meryem,', html)
        self.assertIn('Meryem Hida', html)
        self.assertNotIn('Bonjour meryem', html)

    def test_no_dangling_comma_when_address_empty(self):
        """An empty address must not leave a stray ', Casablanca' on the cover."""
        html, _ = self._html_and_doc()
        self.assertNotIn(', Casablanca', html)
        self.assertIn('Casablanca', html)

    def test_tangible_monthly_and_impact_framing_present(self):
        """Cover carries the per-month framing and the derived CO₂ impact line."""
        html, _ = self._html_and_doc()
        self.assertIn('MAD/mois', html)
        self.assertIn('CO', html)        # CO₂ impact strip
        self.assertIn('arbres', html)

    def test_equipment_lines_deep_link_to_fiche_pages(self):
        """Panels/inverters/battery/meter/dongle link to their /produits/<slug>
        fiche-technique page (slugs match docs/WEB_PLAN.md W141–W145); TAQINOR's
        own lines (structures, socles, installation…) stay plain text."""
        html, _ = self._html_and_doc()
        for slug in ('canadian-solar-710', 'onduleur-huawei-reseau',
                     'onduleur-deye-hybride', 'batterie-dyness',
                     'smart-meter-huawei', 'wifi-dongle-huawei'):
            self.assertIn(f'/produits/{slug}', html)
        # Découpage fondateur 2026-08-18 : la structure a désormais SA fiche
        # explicative (`structure-fixation`, scindée de `socles-lestage` le
        # 18/08) — mais aucune URL de fiche n'est inventée à partir du libellé
        # de la ligne (« produits/structures » n'existe pas et ne doit jamais
        # apparaître).
        self.assertNotIn('produits/structures/', html)
        self.assertNotIn('produits/structures-acier', html)

    def test_fiche_slug_mapping(self):
        """CONTRAT UNIQUE « ligne → fiche » — la moitié DJANGO (PACT10).

        Le fichier partagé ``contract_samples/ligne_fiche_mapping.json`` est LE
        porteur de l'obligation : la moitié web (apps/web/tests/
        ficheMatcherWJ131.test.ts) lit EXACTEMENT le même fichier et vérifie son
        propre matcher dessus. Si les deux tests passent, le PDF et la page
        proposition envoient forcément le client sur la MÊME fiche — c'est ce
        lien-là qui manquait le 03/08/2026.
        """
        import json
        import os

        from apps.ventes.quote_engine.residential import theme

        contrat_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'contract_samples', 'ligne_fiche_mapping.json')
        with open(contrat_path, encoding='utf-8') as fh:
            contrat = json.load(fh)

        for designation, attendu in contrat['exemple'].items():
            self.assertEqual(theme.fiche_slug(designation), attendu,
                             f'contrat rompu sur « {designation} »')

        # Le découpage fondateur du 18/08 : 8 familles résidentielles + 3
        # postes de grands projets. Un ajout silencieux casse ici.
        decoupage = contrat['decoupage']
        self.assertEqual(len(decoupage['residentiel']), 8)
        self.assertEqual(len(decoupage['grands_projets']), 3)

        # Les postes qui ne sont pas du MATÉRIEL n'ont pas de fiche : pose,
        # étude, transport, services.
        for designation in ('Installation', 'Transport',
                            'Main-d’œuvre et mise en service',
                            'Étude technique'):
            self.assertEqual(theme.fiche_slug(designation), '', designation)

    def test_fiche_slug_scinde_protection_dc_et_ac(self):
        """Le continu et l'alternatif ne se coupent pas de la même façon : leurs
        deux fiches sont distinctes, et un coffret combiné va du côté DC (la
        moitié spécifiquement photovoltaïque, cible de l'alias de l'ancien
        slug `tableau-protection-ac-dc`)."""
        from apps.ventes.quote_engine.residential import theme
        for designation in ('Tableau De Protection AC/DC', 'Coffret DC 2 strings',
                            'Parafoudre DC type 2 1000 V',
                            'Sectionneur DC 1000 V 25 A',
                            'Fusible gPV 1000 VDC 15 A'):
            self.assertEqual(theme.fiche_slug(designation), 'protection-dc',
                             designation)
        for designation in ('Coffret AC', 'Parafoudre AC type 2',
                            'Disjoncteur AC courbe C 16 A monophasé',
                            'Différentiel (DDR) type A 300 mA 40 A'):
            self.assertEqual(theme.fiche_slug(designation), 'protection-ac',
                             designation)

    def test_fiche_slug_separe_cablage_et_accessoires_de_pose(self):
        """Le CÂBLE d'un côté, ce qui le porte de l'autre — le client payait les
        deux sur une seule ligne « Accessoires » sans savoir ce qu'elle
        contenait."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(
            theme.fiche_slug('Câble solaire H1Z2Z2-K 6 mm² (au mètre)'),
            'cablage')
        self.assertEqual(theme.fiche_slug('Connecteurs MC4'), 'cablage')
        self.assertEqual(theme.fiche_slug('Accessoires'), 'accessoires-pose')
        self.assertEqual(theme.fiche_slug('Presse-étoupes'), 'accessoires-pose')
        self.assertEqual(theme.fiche_slug('Structures aluminium'),
                         'structure-fixation')

    def test_fiche_slug_separe_la_structure_de_ses_socles(self):
        """Ordre fondateur du 18/08/2026 (« a page for each ») : le CHÂSSIS et
        les SOCLES béton qui le lestent sont deux fiches, donc deux slugs. Le
        jumeau web (apps/web/tests/ficheMatcherWJ131.test.ts) épingle les mêmes
        libellés — si les deux moitiés divergeaient ici, le PDF enverrait le
        client sur `structure-fixation` pendant que la page proposition
        l'enverrait sur `socles-lestage` (incident PACT10 rejoué)."""
        from apps.ventes.quote_engine.residential import theme
        for designation in ('Socles', 'Socles béton',
                            'Plots de lestage béton 30x30x20',
                            'Lestage toiture-terrasse',
                            # Un libellé qui nomme les DEUX parle du socle.
                            'Socles béton pour structure'):
            self.assertEqual(theme.fiche_slug(designation), 'socles-lestage',
                             designation)
        for designation in ('Structures acier', 'Structures aluminium',
                            'Rails de fixation',
                            'Structure de fixation en aluminium'):
            self.assertEqual(theme.fiche_slug(designation),
                             'structure-fixation', designation)

    def test_fiche_slug_jamais_la_mauvaise_marque(self):
        """La moitié DJANGO du garde-fou du contrat (bloc ``sans_lien``).

        Avant le 18/08 elle n'existait pas : le PDF envoyait le client sur la
        fiche DEYE sous un onduleur Growatt, sur la fiche Schneider sous un
        coffret Legrand, et sur la fiche d'une batterie LFP Dyness sous une
        batterie plomb-gel. Le jumeau web renvoyait ``null`` sur exactement les
        mêmes chaînes : le contrat existait, il ne liait rien."""
        from apps.ventes.quote_engine.residential import theme
        for designation in (
                'Onduleur hybride Growatt 10 kW',
                'Onduleur réseau 10 kW SMA Sunny Boy',
                'Panneau monocristallin 710W Longi',
                'Batterie LFP 5 kWh Pylontech',
                'Coffret AC Legrand 4 modules',
                'Coffret AC Hager',
                'Câble solaire Prysmian 6 mm²'):
            self.assertEqual(theme.fiche_slug(designation), '', designation)
        # La marque peut arriver par le CHAMP marque, pas seulement le libellé.
        self.assertEqual(
            theme.fiche_slug('Onduleur hybride 8 kW', 'Growatt'), '')
        # protection-dc ne nomme AUCUNE marque : elle reste liée.
        self.assertEqual(
            theme.fiche_slug('Coffret DC Hager 2 strings'), 'protection-dc')

    def test_fiche_slug_exige_le_qualificatif_de_marque(self):
        """Un panneau/une batterie sans marque ATTENDUE ne reçoit aucun lien —
        exactement comme le jumeau web. « Batterie Gel 2.2 kWh » (BAT-GEL-22,
        plomb-gel 12 V) et « Batterie Lithium 5 kWh » (BAT-LIT-5) sont des
        références RÉELLES du catalogue seedé, et ne sont pas la LFP Dyness que
        la fiche décrit."""
        from apps.ventes.quote_engine.residential import theme
        for designation in ('Panneau photovoltaïque 710 Wc',
                            'Panneau 710 Wc',
                            'Batterie Gel 2.2 kWh',
                            'Batterie Lithium 5 kWh',
                            'Batterie lithium 5,12 kWh'):
            self.assertEqual(theme.fiche_slug(designation), '', designation)

    def test_fiche_slug_accepte_l_orthographe_reelle_du_catalogue(self):
        """Le catalogue écrit « Canadien Solar » (seed_catalogue.py:45/354), la
        fiche publiée « Canadian Solar » : les DEUX graphies lient."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(theme.fiche_slug('Panneau Canadien Solar 710W'),
                         'canadian-solar-710')
        self.assertEqual(
            theme.fiche_slug('Panneau photovoltaïque 710 Wc', 'Canadien Solar'),
            'canadian-solar-710')
        self.assertEqual(
            theme.fiche_slug('Panneau CANADIAN SOLAR 710W bifacial'),
            'canadian-solar-710')

    def test_fiche_slug_ne_confond_pas_sma_et_smart_meter(self):
        """Le garde-fou teste des FRONTIÈRES DE MOT : « sma » (marque) ne doit
        jamais être trouvé dans « smart meter »."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(theme.fiche_slug('Smart Meter Huawei'),
                         'smart-meter-huawei')

    def test_le_pourcentage_de_performance_reste_a_sa_marque(self):
        """« 87,4 % garanti » est une spec Canadian Solar (TOPHiKu7).

        Un panneau Longi est lui aussi garanti 30 ans — mais à 88,9 %. Ne
        comparer que le NOMBRE D'ANNÉES réattachait le pourcentage d'une AUTRE
        marque à un document client."""
        from apps.ventes.quote_engine.residential import theme

        def _bande(designation, marque):
            d = {'items': [{
                'designation': designation, 'marque': marque,
                '_produit_nom': designation,
                'garantie_mois': 144, 'garantie_production_mois': 360}]}
            return {w[2]: w for w in theme.warranties_for(d)}

        longi = _bande('Panneau Longi Hi-MO 585W', 'Longi')['Performance']
        self.assertEqual(longi[0], '30')
        self.assertEqual(longi[3], 'performance linéaire')
        self.assertNotIn('87,4', longi[3])

        # Le panneau PAR DÉFAUT, lui, garde son sous-libellé chiffré — et il
        # le garde dans les DEUX graphies du catalogue.
        for designation, marque in (
                ('Panneau Canadien Solar 710W', 'Canadien Solar'),
                ('Panneau Canadian Solar 710W', 'Canadian Solar')):
            perf = _bande(designation, marque)['Performance']
            self.assertEqual(perf[0], '30')
            self.assertEqual(perf[3], '87,4 % garanti')

    def test_scan_to_sign_qr_when_qrcode_available(self):
        """The premium scan-to-sign QR renders on page 3 (qrcode is a pinned
        dep). The renderer guards the import so a missing wheel degrades to the
        text link rather than breaking the PDF — so only assert when qrcode is
        importable."""
        html, _ = self._html_and_doc()
        # The textual sign link is ALWAYS present.
        self.assertIn('Signez en ligne', html)
        try:
            import qrcode  # noqa: F401
        except Exception:
            self.skipTest('qrcode not installed in this environment')
        self.assertIn('Scannez', html)
        self.assertIn('data:image/png', html)


@tag('pdf')
class TestResidentialQRESRound(TestCase):
    """QRES — corrections du rendu résidentiel (audit fondateur 2026-07-17) :
    pagination JAMAIS débordée (le vrai devis DEV-202607-0021 rendait 4 pages
    physiques étiquetées « Page 3 / 3 »), lien de signature court, plus de
    scénario batterie fantôme sur un devis mono-option, garanties à source
    unique, bande légale alignée sur le pied de page, méta client dédoublonnée."""

    def _render(self, variant):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import (
            renderer, render, sample_data)
        d = renderer._augment(sample_data.build(variant))
        html = render.build_html(d)
        return html, HTML(string=html).render()

    # QRES17/49/57 — nombre de pages ATTENDU par fixture : un devis de la
    # taille réelle du fondateur (« plus5 », ~13 lignes) tient en 3 pages AVEC
    # la grande courbe (cartes badges et ligne fiches retirées de la page 2) ;
    # seuls les très gros devis (« plus10 ») passent en 4 pages (tableau à
    # l'aise + page rentabilité dédiée).
    EXPECTED_PAGES = {"deux": 3, "sans": 3, "long": 3, "plus5": 3,
                      "plus10": 4}

    def test_page_count_per_variant_never_overflows_dirty(self):
        """La garde anti-débordement : chaque fixture rend EXACTEMENT le
        nombre de pages prévu — le bloc signature ne bascule plus jamais sur
        une page orpheline, et un devis chargé AJOUTE une page proprement."""
        from apps.ventes.quote_engine.residential import sample_data
        for variant in sample_data.keys():
            _, doc = self._render(variant)
            self.assertEqual(
                len(doc.pages), self.EXPECTED_PAGES[variant],
                f'variant {variant!r}: expected '
                f'{self.EXPECTED_PAGES[variant]} pages, got {len(doc.pages)}')

    def test_overflow_quote_paginates_cleanly(self):
        """Devis très chargé (« plus10 ») : 4 pages numérotées « / 4 »,
        TOUTES les lignes du devis présentes (aucune avalée par le
        découpage), la page rentabilité dédiée existe et porte la bande de
        financement (QRES50)."""
        import fitz
        from apps.ventes.quote_engine.residential import renderer, sample_data
        for variant in ("plus10",):
            data = sample_data.build(variant)
            pdf = renderer.render_pdf_bytes(data)
            doc = fitz.open(stream=pdf, filetype='pdf')
            self.assertEqual(len(doc), 4, variant)
            all_text = "\n".join(p.get_text() for p in doc)
            for it in data["sans_items"]:
                frag = it["designation"].split(" (")[0][:25]
                self.assertIn(frag, all_text,
                              f'{variant}: ligne perdue par le découpage : '
                              f'{frag!r}')
            self.assertIn("Page 2 / 4", all_text)
            self.assertIn("Page 4 / 4", all_text)
            self.assertIn("Rentabilité de votre investissement", all_text)
            self.assertIn("Dans votre poche", all_text)

    def test_bottom_content_never_silently_clipped(self):
        """Le cadre .page (A4 fixe, overflow:hidden) peut ROGNER sans faire de
        4ᵉ page : une page 3 trop haute perdait silencieusement la bande légale
        (SARLAU/RC/ICE). On rastérise le VRAI PDF (chemin complet, distribution
        élastique QRES62 incluse) et on exige la bande légale + la clause
        non-contractuelle physiquement sur la dernière page."""
        import fitz
        from apps.ventes.quote_engine.residential import renderer, sample_data
        for variant in sample_data.keys():
            pdf = renderer.render_pdf_bytes(sample_data.build(variant))
            doc = fitz.open(stream=pdf, filetype='pdf')
            last = doc[-1].get_text()
            self.assertIn('SARLAU', last,
                          f'variant {variant!r}: legal band clipped off page 3')
            self.assertIn('non contractuelles', last,
                          f'variant {variant!r}: disclaimer clause clipped')

    def test_no_page_ends_with_a_large_void(self):
        """QRES62 — distribution dynamique de l'espace : après le second
        passage (mesure du PDF réel → joints élastiques), plus AUCUNE page ne
        garde un vide résiduel exploitable > 12 mm — le « petit espace en bas »
        signalé par le fondateur ne peut pas revenir, quel que soit le nombre
        de pages du devis."""
        from apps.ventes.quote_engine.residential import renderer, sample_data
        for variant in sample_data.keys():
            pdf = renderer.render_pdf_bytes(sample_data.build(variant))
            residual = renderer._measure_page_slack(pdf)
            self.assertTrue(
                all(v <= 12 for v in residual.values()),
                f'variant {variant!r}: residual voids {residual}')

    def test_hypotheses_live_on_the_web_proposal_not_the_pdf(self):
        """QRES61 (fondateur) — les hypothèses de calcul quittent le papier :
        plus de bande « Nos hypothèses » dans le PDF (la proposition en ligne
        les porte, WJ32/W359) ; le papier garde UNE clause non-contractuelle
        qui y renvoie."""
        html, _ = self._render("deux")
        self.assertNotIn("p3-hyp", html)
        self.assertNotIn("Nos hypothèses", html)
        self.assertIn("Estimations non contractuelles", html)
        self.assertIn("proposition en ligne", html)

    def test_row_has_two_boxes_equal_by_construction_method_flat_below(self):
        """QRES65 + QRES66 (fondateur, 2026-08-18) — la rangée « Conditions /
        Prochaines étapes » de la page 3 porte DEUX boîtes, et RIEN d'autre :
        le bloc « Financement possible » est SUPPRIMÉ (ordre fondateur du
        18/08, demandé plusieurs fois — ni bande de pied .p3-finsec, ni carte,
        ni mensualité ; ne pas le réintroduire sous une autre forme). Les deux
        boîtes sont deux cellules d'une MÊME ligne de tableau : leurs hauteurs
        s'égalisent par construction (la plus courte est étirée sur la hauteur
        commune de la ligne). Le texte de la méthode reste posé À PLAT sous la
        rangée, sans boîte."""
        html, _ = self._render("deux")
        # exactement deux boîtes, dans UNE ligne de tableau (plus de rowspan
        # qui répartissait la surhauteur entre trois lignes)
        self.assertEqual(html.count('class="p3-tdcard"'), 2)
        self.assertNotIn('rowspan', html)
        self.assertNotIn('p3-tdfin', html)
        self.assertNotIn('p3-rgap', html)
        # QRES66 — plus AUCUNE trace du financement en page 3 (classes p3-fin*,
        # bande de pied, variante .p3-cols-fin) même quand la fixture porte des
        # données de financement.
        self.assertNotIn('p3-finsec', html)
        self.assertNotIn('p3-fin', html)
        self.assertNotIn('p3-cols-fin', html)
        # la méthode a quitté la carte Conditions pour un texte plat sous la
        # rangée (aucune boîte : ni p3-tdcard, ni p3-card, ni fond/bordure)
        self.assertNotIn('p3-cond-k">Comment nous calculons', html)
        i_row = html.index('class="p3-cols')
        i_flat = html.index('class="p3-method"')
        self.assertLess(html.index('</table>', i_row), i_flat)

    def test_sign_link_token_never_displayed_as_text(self):
        """Le lien tokenisé vit dans le href et le QR ; le bouton n'affiche que
        « hôte/segment » (l'URL complète débordait sous le QR)."""
        html, _ = self._render("deux")
        token_tail = "rKJtbjsY-qTML35ZnjQ9Lt_v4_demo"
        self.assertEqual(html.count(token_tail), 1)          # href uniquement
        self.assertIn("Signez en ligne", html)
        self.assertIn("taqinor.ma/proposition</a>", html)

    def test_mono_option_has_no_phantom_battery_scenario(self):
        """Un devis réseau seul ne mentionne plus « Avec batterie » ni « deux
        scénarios » nulle part (cartes, sous-titre du graphe, accord)."""
        html, _ = self._render("sans")
        self.assertNotIn("deux scénarios", html)
        self.assertNotIn("Avec batterie", html)

    def test_warranties_single_source(self):
        """theme.WARRANTIES est LA source : badges en page 2, bande de
        crédibilité page 1 alignée (30 ans performance — plus aucun
        « Garantie 25 ans » contradictoire)."""
        from apps.ventes.quote_engine.residential import theme
        html, _ = self._render("deux")
        for _n, _u, label, _sub in theme.WARRANTIES:
            self.assertIn(label, html)
        self.assertIn("Performance garantie 30 ans", html)
        self.assertNotIn("Garantie 25 ans", html)
        self.assertNotIn("garantie sur 25 ans", html)

    def test_legal_band_contact_matches_footer(self):
        """La bande légale lit l'identité résolue : même email que le pied de
        page (le PDF réel imprimait .ma en pied et .com dans la bande)."""
        html, _ = self._render("deux")   # profil TAQINOR avec contact@taqinor.ma
        self.assertNotIn("contact@taqinor.com", html)
        self.assertGreaterEqual(html.count("contact@taqinor.ma"), 2)

    def test_hypotheses_deduplicated_by_builder_shape(self):
        """La fixture (miroir du builder corrigé) ne porte plus qu'UNE mention
        de la loi 82-21 dans les hypothèses — servies à la proposition EN
        LIGNE (le PDF ne les rend plus, QRES61)."""
        from apps.ventes.quote_engine.residential import sample_data
        items = sample_data.build("deux")["hypotheses"]["items"]
        self.assertEqual(sum("82-21" in i for i in items), 1)

    def test_join_meta_dedups_repeated_fragments(self):
        """« casablanca, casablanca · casablanca » → « casablanca » (l'adresse
        saisie contient souvent déjà la ville)."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(
            theme.join_meta("casablanca, casablanca", "casablanca",
                            "+212661850412"),
            "casablanca · +212661850412")
        self.assertEqual(
            theme.join_meta("12 rue des Orangers", "Casablanca",
                            "+212600000000"),
            "12 rue des Orangers · Casablanca · +212600000000")

    def test_builder_hypotheses_mention_8221_once(self):
        """Le builder réel dédoublonne : une seule formulation 82-21 dans le
        bloc hypothèses (il en cumulait deux, plus celle de la méthode)."""
        from apps.ventes.quote_engine.pricing import cashflow_assumptions
        notes = cashflow_assumptions()["notes"]
        self.assertTrue(any("82-21" in n for n in notes))
        self.assertTrue(any("injection" in n.lower() for n in notes))
        # plus de décimale anglaise dans les notes rendues au client
        joined = " ".join(notes)
        self.assertNotIn("0.5", joined)
        self.assertNotIn("2.0", joined)


@tag('pdf')
class TestResidentialWarmPathCache(TestCase):
    """QX8 — chemin chaud : polices/logo/graphiques + octets PDF sont mis en
    cache. Un second rendu du MÊME devis inchangé réutilise le travail (aucun
    recalcul de graphiques) et produit des octets byte-identiques.
    """

    def test_font_and_logo_helpers_are_cached_pure(self):
        from apps.ventes.quote_engine.residential import theme
        # lru_cache présent → cache_info() disponible et effectif
        theme.font_face_css.cache_clear()
        theme.logo_dark_b64.cache_clear()
        theme.logo_color_b64.cache_clear()
        a = theme.font_face_css()
        b = theme.font_face_css()
        self.assertEqual(a, b)
        self.assertEqual(theme.font_face_css.cache_info().misses, 1)
        self.assertGreaterEqual(theme.font_face_css.cache_info().hits, 1)
        # le logo recoloré (boucle par pixel) n'est calculé qu'une fois
        theme.logo_dark_b64()
        theme.logo_dark_b64()
        self.assertEqual(theme.logo_dark_b64.cache_info().misses, 1)

    # 2026-08-14 — POURQUOI ON COMPTE UN ÉCART ET PLUS UN NOMBRE ABSOLU.
    # Ces deux gardes exigeaient littéralement 1 et 2 appels à ``charts.build_all``.
    # QRES62 (commit 307575f7) a introduit le rendu EN DEUX PASSES dans
    # ``renderer.render_pdf_bytes`` (passe 1 → mesure du vide résiduel réel du
    # PDF → passe 2 avec les joints élastiques dimensionnés), et chaque passe
    # rappelle ``render.build_html`` → ``build_ctx`` → ``charts.build_all``.
    # Un rendu À FROID coûte donc 2 appels au lieu de 1 : la CI observait 2 != 1
    # et 4 != 2 — soit EXACTEMENT le double, la preuve que le cache marche
    # toujours. Le nombre de passes est un détail de mise en page (il retombe
    # même à 1 si PyMuPDF est absent : ``_measure_page_slack`` renvoie {}) ;
    # l'EXIGENCE QX8, elle, est un ÉCART : un second rendu du même devis ne
    # coûte RIEN, un devis édité recoûte un vrai rendu. C'est ce qu'on mesure
    # maintenant — la garde mord donc quel que soit le nombre de passes.
    def test_second_render_reuses_bytes_and_skips_chart_work(self):
        from unittest.mock import patch
        from apps.ventes.quote_engine.residential import renderer
        from apps.ventes.quote_engine.residential import charts as charts_mod
        data = _residential_sample_data()

        # vide le cache PDF pour un décompte déterministe
        renderer._PDF_CACHE.clear()

        real_build_all = charts_mod.build_all
        with patch.object(charts_mod, 'build_all',
                          side_effect=real_build_all) as spy:
            pdf1 = renderer.render_pdf_bytes(data)
            apres_froid = spy.call_count
            pdf2 = renderer.render_pdf_bytes(data)
            apres_chaud = spy.call_count
        # le rendu à froid calcule bien les graphiques…
        self.assertGreaterEqual(apres_froid, 1)
        # … et le second rendu est servi depuis le cache : ZÉRO travail de
        # graphique en plus (si le cache régressait, apres_chaud doublerait).
        self.assertEqual(apres_chaud, apres_froid)
        # octets byte-identiques
        self.assertEqual(pdf1, pdf2)
        self.assertEqual(pdf1[:4], b'%PDF')

    def test_edited_devis_forces_a_real_rerender(self):
        from unittest.mock import patch
        from apps.ventes.quote_engine.residential import renderer
        from apps.ventes.quote_engine.residential import charts as charts_mod
        renderer._PDF_CACHE.clear()
        data = _residential_sample_data()
        data2 = _residential_sample_data()
        data2["ref"] = "DEV-202606-9999"   # une édition change l'empreinte
        real = charts_mod.build_all
        with patch.object(charts_mod, 'build_all', side_effect=real) as spy:
            renderer.render_pdf_bytes(data)
            apres_froid = spy.call_count
            renderer.render_pdf_bytes(data2)
            apres_edition = spy.call_count
        # empreintes différentes → un VRAI second rendu, du même coût que le
        # premier (jamais un PDF périmé servi depuis le cache).
        self.assertGreaterEqual(apres_froid, 1)
        self.assertEqual(apres_edition, 2 * apres_froid)


class TestQuoteSignLinkAndPageNumbers(TestCase):
    """QX6 — le CTA de signature pointe vers la VRAIE proposition tokenisée
    (ShareLink), plus l'ancien /signer/<ref> 404 ; le pied de page n'a plus de
    « / 3 » codé en dur (il lit le nombre réel de pages rendues)."""

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _resid_devis(self):
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
            ('Batterie Dyness 10 kWh', '1', '25000'),
            ('Installation', '1', '4000'),
        ], reference='DEV-QX6-1', etude_params=DEUX_OPTIONS)

    def test_builder_mints_tokenized_signer_link(self):
        from apps.ventes.models import ShareLink
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._resid_devis()
        data = build_quote_data(devis)
        signer = (data.get("links") or {}).get("signer", "")
        self.assertIn('/proposition/', signer)
        # le lien porte le token d'un vrai ShareLink de ce devis
        link = ShareLink.for_devis(devis)
        self.assertIn(link.token, signer)
        # plus jamais l'ancien chemin inventé /signer/<ref>
        self.assertNotIn('/signer/', signer)

    def test_signer_link_reused_not_duplicated(self):
        from apps.ventes.models import ShareLink
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._resid_devis()
        build_quote_data(devis)
        build_quote_data(devis)
        # un seul ShareLink valide par devis (réutilisé, pas dupliqué)
        self.assertEqual(
            ShareLink.objects.filter(devis=devis).count(), 1)

    @tag('pdf')
    def test_rendered_pdf_qr_points_at_live_proposal(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.models import ShareLink
        devis = self._resid_devis()
        data = build_quote_data(devis)
        html = render.build_html(renderer._augment(data))
        link = ShareLink.for_devis(devis)
        # le lien texte « Signez en ligne » pointe vers la proposition tokenisée
        # PV84 — chemin partagé : slug du client ('Alaoui Karim', make_client)
        # devant le token.
        self.assertIn(f'/proposition/alaoui-karim/{link.token}', html)
        self.assertNotIn('taqinor.ma/signer/', html)

    @tag('pdf')
    def test_footer_page_total_matches_real_pages(self):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = self._resid_devis()
        html = render.build_html(renderer._augment(build_quote_data(devis)))
        # le pied affiche « Page N / 3 » = nombre RÉEL de pages (résidentiel = 3)
        self.assertIn('Page 1 / 3', html)
        self.assertIn('Page 3 / 3', html)


@tag('pdf')
class TestResidentialSingleOptionGate(TestCase):
    """QX5 — jamais d'option fantôme : un devis résidentiel mono-option rend
    UNE seule carte partout (page 1 pleine largeur, page 2 sans découpage
    delta, en-tête « commun aux deux options » renommé). Un devis à deux
    options reste inchangé (les tests de nombre de pages ci-dessus le prouvent).
    """

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _resid_html(self, devis):
        from apps.ventes.quote_engine.residential import renderer, render
        from apps.ventes.quote_engine.builder import build_quote_data
        data = build_quote_data(devis)
        # mode résidentiel par défaut → renderer résidentiel
        d = renderer._augment(data)
        return render.build_html(d)

    def _avec_only_devis(self):
        # hybride + batterie + panneaux, AUCUN onduleur réseau → une seule
        # option réelle (« Avec batterie »).
        return make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '12', '1272.73'),
            ('Onduleur hybride Deye 5kW', '1', '24000'),
            ('Batterie Dyness 10 kWh', '1', '25000'),
            ('Structures acier', '12', '417'),
            ('Installation', '1', '5000'),
        ], reference='DEV-QX5-AVEC')

    def test_battery_only_quote_shows_single_option_everywhere(self):
        from weasyprint import HTML
        devis = self._avec_only_devis()
        html = self._resid_html(devis)
        doc = HTML(string=html).render()
        # toujours 3 pages (le format n'a pas changé)
        self.assertEqual(len(doc.pages), 3)
        # page 1 : PAS de carte « Option 1 » / « Option 2 » fabriquée
        self.assertNotIn('Option 1', html)
        self.assertNotIn('Option 2', html)
        # page 2 : l'en-tête « commun aux deux options » est renommé
        self.assertNotIn('Équipement commun aux deux options', html)
        self.assertIn('Votre équipement', html)
        # page 2 : aucun bloc delta (cf. note d'ancrage sur le test à deux
        # options ci-dessous — cette assertion était devenue VIDE DE SENS,
        # elle interdisait un marqueur que le moteur ne rend plus depuis
        # QRES27 ; elle mord de nouveau sur le bloc réellement rendu).
        self.assertNotIn('<div class="p2-deltas">', html)
        self.assertNotIn('Spécifique à l&rsquo;option 1', html)
        # aucune option « Sans batterie » fantôme (dépourvue d'onduleur)
        self.assertNotIn('Sans batterie', html)
        # l'option réelle est bien présente
        self.assertIn('Avec batterie', html)

    def test_two_option_quote_keeps_both_cards(self):
        devis = make_devis(self.company, self.user, self.client_obj, [
            ('Panneau Canadien Solar 710W', '14', '1272.73'),
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '16666.67'),
            ('Onduleur hybride Deye 10kW Triphasé', '1', '23333.33'),
            ('Batterie Dyness 10 kWh', '1', '25000'),
            ('Installation', '1', '4000'),
        ], reference='DEV-QX5-DEUX', etude_params=DEUX_OPTIONS)
        html = self._resid_html(devis)
        # deux options → les deux cartes + le découpage delta subsistent
        self.assertIn('Option 1', html)
        self.assertIn('Option 2', html)
        self.assertIn('Équipement commun aux deux options', html)
        # 2026-08-14 — l'ancien marqueur ``<small>ajoute</small>`` a disparu du
        # moteur avec QRES27 (commit db7ff60f) : les en-têtes des deux cartes
        # delta ont été recomposés en « Spécifique à l'option N — … » (le mot
        # « ajoute » pendait sous la barre or et le contraste blanc-sur-#F5A623
        # était mauvais). La garde QX5 épinglait ce marqueur mort ; elle est
        # ré-ancrée sur le bloc réellement rendu — ``<div class="p2-deltas">``
        # n'existe dans le corps QUE quand ``deux_options`` est vrai (le sélecteur
        # CSS ``.p2-deltas {`` de la feuille de style ne matche pas cette chaîne).
        self.assertIn('<div class="p2-deltas">', html)
        self.assertIn('Spécifique à l&rsquo;option 1 — Sans batterie', html)
        self.assertIn('Spécifique à l&rsquo;option 2 — Avec batterie', html)


# ─── SCA27 — pied de page + liens du PDF résidentiel pilotés par CompanyProfile ─


class TestResidentialFooterBranding(SimpleTestCase):
    """SCA27 — le pied de page résidentiel et les liens fiches ne gravent plus
    « TAQINOR · contact@taqinor.com · +212 6 61 85 04 10 » ni taqinor.ma pour
    tout tenant : ils sont pilotés par ``data["entreprise"]`` (CompanyProfile).
    Fonctions pures : aucune DB, aucun rendu PDF."""

    # La chaîne EXACTE gravée aujourd'hui (référence byte-à-byte fondateur).
    FOUNDER_FOOTER = ('<b>TAQINOR</b> &nbsp;·&nbsp; contact@taqinor.com '
                      '&nbsp;·&nbsp; +212 6 61 85 04 10')

    def test_footer_default_is_exact_founder_string(self):
        """Sans ``entreprise`` (forme des données d'échantillon), le pied de page
        reproduit EXACTEMENT la chaîne fondateur historique."""
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer({'ref': 'DEV-1'})
        self.assertIn(self.FOUNDER_FOOTER, foot)

    def test_footer_founder_profile_is_char_for_char_identical(self):
        """Quand le profil porte les valeurs fondateur, la ligne est identique."""
        from apps.ventes.quote_engine.residential import theme
        data = {'ref': 'DEV-1', 'entreprise': {
            'nom': 'TAQINOR', 'email': 'contact@taqinor.com',
            'telephone': '+212 6 61 85 04 10'}}
        self.assertIn(self.FOUNDER_FOOTER, theme.page_footer(data))

    def test_footer_tenant_carries_its_own_coordinates(self):
        """Un tenant #2 : SES coordonnées, jamais celles du fondateur."""
        from apps.ventes.quote_engine.residential import theme
        data = {'ref': 'DEV-2', 'entreprise': {
            'nom': 'Helios SARL', 'email': 'hello@helios.ma',
            'telephone': '+212 5 22 00 00 00'}}
        foot = theme.page_footer(data)
        self.assertIn('<b>Helios SARL</b>', foot)
        self.assertIn('hello@helios.ma', foot)
        self.assertIn('+212 5 22 00 00 00', foot)
        self.assertNotIn('TAQINOR', foot)
        self.assertNotIn('contact@taqinor.com', foot)

    def test_footer_nom_only_keeps_founder_contact_line(self):
        """Nom fourni sans contact → contact fondateur préservé (comme DC1)."""
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer(
            {'ref': 'DEV-3', 'entreprise': {'nom': 'Helios SARL'}})
        self.assertIn('<b>Helios SARL</b>', foot)
        self.assertIn('contact@taqinor.com &nbsp;·&nbsp; +212 6 61 85 04 10',
                      foot)

    def test_footer_html_escapes_tenant_name(self):
        from apps.ventes.quote_engine.residential import theme
        foot = theme.page_footer(
            {'ref': 'DEV-4', 'entreprise': {'nom': 'A & B <Co>'}})
        self.assertIn('A &amp; B &lt;Co&gt;', foot)
        self.assertNotIn('<Co>', foot)

    def test_fiche_href_kept_for_taqinor_base(self):
        """Base taqinor.ma (fondateur) → lien fiche conservé (byte-identique)."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(
            theme.fiche_href('Panneau Jinko 710W', 'Jinko'),
            'https://taqinor.ma/produits/jinko-710')

    def test_fiche_href_omitted_for_non_taqinor_base(self):
        """Base d'un autre site → aucun lien fiche (omis) : le PDF d'un tenant
        ne pointe pas vers les fiches produits du fondateur."""
        from apps.ventes.quote_engine.residential import theme
        self.assertEqual(
            theme.fiche_href('Panneau Jinko 710W', 'Jinko',
                             produits_base='helios.ma/produits'),
            '')


@tag('pdf')
class TestResidentialFooterBrandingRendered(TestCase):
    """SCA27 (harnais rendu) — un devis résidentiel d'un tenant #2 porte SES
    coordonnées dans le pied de page des 3 pages, jamais celles du fondateur."""

    def test_tenant_footer_and_no_founder_datasheet_links(self):
        from weasyprint import HTML
        from apps.ventes.quote_engine.residential import renderer, render
        data = _residential_sample_data()
        # Identité d'un tenant #2 + base produits de SON site.
        data['entreprise'] = {
            'nom': 'Helios SARL', 'email': 'hello@helios.ma',
            'telephone': '+212 5 22 00 00 00'}
        data['links'] = {'produits': 'helios.ma/produits',
                         'realisations': 'helios.ma/realisations',
                         'avis': 'helios.ma/realisations',
                         'garanties': 'helios.ma/garanties',
                         'signer': 'helios.ma/signer'}
        data['site_url'] = 'helios.ma'
        d = renderer._augment(data)
        html = render.build_html(d)
        # Pied de page : coordonnées du tenant, aucune trace fondateur.
        self.assertIn('Helios SARL', html)
        self.assertIn('hello@helios.ma', html)
        self.assertNotIn('contact@taqinor.com', html)
        self.assertNotIn('<b>TAQINOR</b>', html)
        # Liens fiches produits du fondateur omis (base non-taqinor.ma).
        self.assertNotIn('taqinor.ma/produits/', html)
        # Le PDF se rend (octets valides).
        doc = HTML(string=html).render()
        self.assertEqual(len(doc.pages), 3)

    def test_founder_render_unchanged_when_no_entreprise(self):
        """Sans ``entreprise`` (rendu fondateur historique), le pied de page
        garde la chaîne exacte et les liens fiches taqinor.ma."""
        from apps.ventes.quote_engine.residential import renderer, render
        d = renderer._augment(_residential_sample_data())
        html = render.build_html(d)
        self.assertIn('<b>TAQINOR</b> &nbsp;·&nbsp; contact@taqinor.com '
                      '&nbsp;·&nbsp; +212 6 61 85 04 10', html)
        self.assertIn('taqinor.ma/produits/', html)


# ─── SCA27 — pied de page ÉTUDE (page 4) piloté par CompanyProfile ─────────────


@tag('pdf')
class TestEtudeFooterBranding(TestCase):
    """SCA27 (page étude) — le pied de page de la page d'étude
    d'autoconsommation (premium full + include_etude, industriel) ne grave plus
    ``contact@taqinor.com`` / ``www.taqinor.ma`` (le contact fondateur) pour un
    tenant qui n'a qu'un téléphone (email et site vides) : la ligne est
    reconstruite dès qu'un contact quelconque est fourni. Le rendu fondateur
    (email + tél + site) reste byte-identique."""

    FULL_LINES = [
        ('Onduleur réseau 10kW', '1', '11700'),
        ('Panneau mono 550W', '14', '1100'),
        ('Structures acier', '14', '375'),
        ('Installation', '1', '4000'),
    ]

    ETUDE_PARAMS = {
        'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
        'taux_autoconso': 100, 'taux_couverture': 10.4,
        'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
        'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
    }

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(
            self.company, self.user, self.client_obj, self.FULL_LINES,
            reference='DEV-QE-ETUDE')
        self.devis.mode_installation = 'industriel'
        self.devis.etude_params = self.ETUDE_PARAMS
        self.devis.save()

    def _etude_page_html(self, entreprise):
        """Rend le PDF premium+étude en injectant ``entreprise`` et renvoie le
        fragment HTML de la page d'étude (à partir du titre « Étude
        d'autoconsommation ») — la seule page portant ``ENT_ETUDE_CONTACT``."""
        from apps.ventes.quote_engine.builder import build_quote_data
        from apps.ventes.quote_engine import generate_devis_premium as G

        data = build_quote_data(self.devis, {'include_etude': True})
        data['entreprise'] = entreprise
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_etude_footer_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        html = cap['html']
        marker = "Étude d'autoconsommation"
        idx = html.rfind(marker)
        self.assertNotEqual(idx, -1, "la page d'étude doit être rendue")
        return html[idx:]

    def test_tel_only_tenant_no_founder_contact_on_etude_page(self):
        """Tenant nom + téléphone, email et site VIDES → la page d'étude ne
        montre NI l'email NI le site du fondateur (elle porte SON téléphone)."""
        etude = self._etude_page_html({
            'nom': 'Helios SARL', 'email': '', 'site_web': '',
            'telephone': '+212 5 22 00 00 00'})
        self.assertNotIn('contact@taqinor.com', etude)
        self.assertNotIn('www.taqinor.ma', etude)
        # Repli gracieux : à défaut d'email/site, SON téléphone est affiché.
        self.assertIn('+212 5 22 00 00 00', etude)

    def test_founder_full_profile_etude_footer_byte_identical(self):
        """Profil fondateur (email + tél + site) → le pied de page d'étude
        reste EXACTEMENT la chaîne historique (byte-identique)."""
        etude = self._etude_page_html({
            'nom': 'TAQINOR', 'email': 'contact@taqinor.com',
            'telephone': '+212 6 61 85 04 10', 'site_web': 'www.taqinor.ma'})
        self.assertIn('contact@taqinor.com &nbsp;·&nbsp; www.taqinor.ma', etude)
