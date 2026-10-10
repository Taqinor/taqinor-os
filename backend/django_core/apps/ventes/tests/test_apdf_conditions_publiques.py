"""APDF19 (C-APDF-005) — la page publique de signature sert les conditions
générales du PDF de CE devis, brouillon comme envoyé.

``_conditions_publiques`` lit ``generate_devis_premium.cgv_imprimees(data)``
(APDF12), la source que le PDF imprime. Vrai GET
``/api/django/public/proposal/<jeton>/data/`` (client Django, jeton d'aperçu
interne pour le brouillon — ADEV11 ne sert pas un brouillon au jeton client —,
jeton client une fois le devis envoyé par ``mark_devis_sent``) ; texte du PDF
réel lu par PyMuPDF (``test_pdf_apdf_identite.rendre_pdf``, MinIO en
mémoire). Aucune doublure du moteur.

Test-du-test : faire revenir ``_conditions_publiques`` à
``cgv_bullets_remplies`` ⇒ ``test_brouillon_industriel`` échoue (la page
servait les puces résidentielles par défaut au lieu de la variante C&I).
"""
import html
import re

from django.test import TestCase, tag
from rest_framework.test import APIClient

from apps.ventes.models import ShareLink
from apps.ventes.quote_engine.builder import build_quote_data
from apps.ventes.quote_engine.generate_devis_premium import cgv_imprimees
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

TITRE_IND = 'CGV INDUSTRIEL SPECIFIQUES'
PUCES_IND = ['Echeancier {echeancier}', 'Retenue {retenue}',
             'Clause industrielle XYZ']
LIGNES_IND = [('Panneau mono 450W', '40', '1500'),
              ('Onduleur réseau 20 kW', '1', '30000')]


def _compact(texte):
    """Texte sans AUCUN blanc : le PDF coupe ses lignes où il veut (après
    « ONEE/ », avant « : »…) ; mot pour mot = mêmes caractères visibles."""
    return re.sub(r'\s+', '', str(texte))


#: Renvoi DÉCLARÉ de la page 3 résidentielle quand ses CGV dépassent le
#: budget (``residential.trust.puces_cgv_bornees``, libellé ``ci_cgv_suite``).
RENVOI = 'Suite des conditions : proposition en ligne'


def puces_attendues(devis):
    """Les puces du PDF de CE devis (``cgv_imprimees``), en texte."""
    return [html.unescape(str(p)).strip()
            for p in cgv_imprimees(build_quote_data(devis, {}))['puces']
            if str(p).strip()]


class ConditionsPubliquesParitePdfTests(TestCase):

    def setUp(self):
        from apps.parametres.models_documents import DocumentTemplates
        self.company = make_company(slug='apdf19-co', nom='APDF19')
        modele = DocumentTemplates.get(company=self.company)
        modele.cgv_par_mode = {'industriel': {
            'titre': TITRE_IND, 'bullets': list(PUCES_IND)}}
        modele.save()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)
        self.devis = make_devis(self.company, self.user, self.client_obj,
                                LIGNES_IND, reference='DEV-APDF19-IND')
        self.devis.mode_installation = 'industriel'
        self.devis.save(update_fields=['mode_installation'])
        self.lien = ShareLink.for_devis(self.devis)
        self.api = APIClient()

    def _conditions(self, jeton):
        reponse = self.api.get(f'/api/django/public/proposal/{jeton}/data/')
        self.assertEqual(reponse.status_code, 200, reponse.content[:300])
        return reponse.json().get('conditions')

    def _envoyer(self, devis):
        from apps.ventes.domain.envoi import mark_devis_sent
        mark_devis_sent(devis=devis)
        devis.refresh_from_db()

    def test_brouillon_industriel(self):
        conditions = self._conditions(self.lien.token_interne)
        self.assertIn('Clause industrielle XYZ', conditions)
        self.assertEqual(conditions, puces_attendues(self.devis))
        # Plus les puces résidentielles par défaut du moteur.
        self.assertFalse([p for p in conditions
                          if p.startswith('Acompte à la commande')])

    def test_envoye_industriel_marqueurs_substitues(self):
        self._envoyer(self.devis)
        conditions = self._conditions(self.lien.token)
        self.assertEqual(conditions, puces_attendues(self.devis))
        texte = ' '.join(conditions)
        self.assertNotIn('{echeancier}', texte)
        self.assertNotIn('{retenue}', texte)
        echeancier = [p for p in conditions if p.startswith('Echeancier')]
        self.assertEqual(len(echeancier), 1)
        self.assertIn('%', echeancier[0])

    def test_residentiel(self):
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel)
        devis = devis_residentiel(self.company, 'DEV-APDF19-RES',
                                  user=self.user, client=self.client_obj)
        self._envoyer(devis)
        lien = ShareLink.for_devis(devis)
        conditions = self._conditions(lien.token)
        self.assertTrue(conditions)
        self.assertEqual(conditions, puces_attendues(devis))

    @tag('pdf')
    def test_pdf_imprime_les_memes_puces(self):
        """Parité PDF ⊂ page publique, mot pour mot : la page sert la liste
        COMPLÈTE ; le PDF imprime ce qui tient — tout en C&I, le budget de la
        page 3 en résidentiel (``puces_cgv_bornees``) avec le renvoi déclaré
        quand il tronque. Chaque puce IMPRIMÉE est dans la liste servie, la
        première servie est la première imprimée, et sans troncature aucun
        renvoi n'est imprimé (donc toutes les puces servies le sont)."""
        from apps.ventes.quote_engine.residential import trust
        from apps.ventes.tests.test_pdf_apdf_identite import (
            devis_residentiel, rendre_pdf, texte_pdf)
        residentiel = devis_residentiel(self.company, 'DEV-APDF19-RES2',
                                        user=self.user, client=self.client_obj)

        def verifier(devis, jeton, borne):
            servies = self._conditions(jeton)
            self.assertTrue(servies)
            pdf = _compact(texte_pdf(rendre_pdf(devis)))
            imprimees = (trust.puces_cgv_bornees({}, servies) if borne
                         else list(servies))
            tronque = bool(imprimees) and imprimees[-1] == RENVOI
            if tronque:
                imprimees = imprimees[:-1]
            self.assertTrue(imprimees)
            self.assertEqual(imprimees[0], servies[0])
            self.assertEqual(imprimees, servies[:len(imprimees)])
            for puce in imprimees:
                self.assertIn(_compact(puce), pdf)
            self.assertEqual(_compact(RENVOI) in pdf, tronque)
            return pdf

        with self.subTest(etat='brouillon'):
            pdf = verifier(self.devis, self.lien.token_interne, borne=False)
            self.assertIn(_compact(TITRE_IND), pdf)
        self._envoyer(self.devis)
        self._envoyer(residentiel)
        with self.subTest(etat='envoye'):
            verifier(self.devis, self.lien.token, borne=False)
        with self.subTest(etat='residentiel'):
            verifier(residentiel, ShareLink.for_devis(residentiel).token,
                     borne=True)
