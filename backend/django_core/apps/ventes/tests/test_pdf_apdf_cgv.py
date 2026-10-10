"""APDF12-APDF14 (C-APDF-005, C-APDF-006) — les conditions générales
imprimées ont UNE source : ``generate_devis_premium.cgv_imprimees(data)``.

APDF12 — ``CgvImprimeesTests`` : la variante C&I (gelée à l'envoi ou vive)
garde SON titre, ses marqueurs {echeancier}/{retenue} sont substitués dans les
deux états, et son gel n'est plus recopié dans ``doc_texts['cgv_bullets']``.
Moteur réel (``build_quote_data``, envoi réel ``mark_devis_sent``), aucune
doublure. Test-du-test : rétablir la boucle ERR-QJR668 qui recopie TOUTE
entrée ``cgv_gelees`` dans ``doc_texts['cgv_bullets']`` (builder) ⇒
``test_gel_ci_pas_recopie_dans_cgv_bullets`` échoue.

APDF13 — ``CgvTousFormatsTests`` : le résidentiel premium (page 3, à la place
du bloc « Conditions » composé en dur), l'agricole 3 pages et le une-page
impriment ``cgv_imprimees(data)``, sans changer les nombres de pages.
Test-du-test : remettre le bloc « Conditions » en dur de
``residential/trust.py`` ⇒ ``test_puces_societe_imprimees[residentiel]``
échoue.

APDF14 — ``GelCompletLectureTests`` : un devis envoyé ou signé imprime
l'ENSEMBLE des textes contractuels gelés à l'envoi (``doc_texts_geles``,
APDF20) ; un brouillon lit les textes vifs ; un envoyé d'avant ce gel garde
le comportement d'hier.
"""
from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.quote_engine.generate_devis_premium import cgv_imprimees
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

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
        from apps.ventes.tests.test_pdf_apdf_garde_identite import MARCHES
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
