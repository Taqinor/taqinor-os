"""APDF12-APDF14 (C-APDF-005, C-APDF-006) — les conditions générales
imprimées ont UNE source : ``generate_devis_premium.cgv_imprimees(data)``.

APDF12 — ``CgvImprimeesTests`` : la variante C&I (gelée à l'envoi ou vive)
garde SON titre, ses marqueurs {echeancier}/{retenue} sont substitués dans les
deux états, et son gel n'est plus recopié dans ``doc_texts['cgv_bullets']``.
Moteur réel (``build_quote_data``, envoi réel ``mark_devis_sent``), aucune
doublure. Test-du-test : rétablir la boucle ERR-QJR668 qui recopie TOUTE
entrée ``cgv_gelees`` dans ``doc_texts['cgv_bullets']`` (builder) ⇒
``test_gel_ci_pas_recopie_dans_cgv_bullets`` échoue.
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
