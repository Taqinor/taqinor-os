"""APDF49 (C-APDF-007) — garde de CLASSE « option PDF sans relais » : chaque
clé publique de ``quote_engine.DEFAULT_PDF_OPTIONS`` est soit RELAYÉE par la
vue ``/proposal`` (le seul chemin du PDF client, règle #4), soit EXCLUE avec
sa raison. Une clé ajoutée au moteur sans relais ni exclusion fait échouer
le test.

Vrai GET ``/proposal`` par clé (valeur non défaut), moteur RÉEL enveloppé
(``wraps``) pour lire les options qu'il reçoit ; seul MinIO est doublé.

Test-du-test : retirer le relais ``include_note_calcul`` de la vue ⇒ le
test échoue sur cette clé.
"""
from unittest import mock

from django.test import TestCase
from rest_framework.test import APIClient

from apps.ventes import quote_engine
from apps.ventes.quote_engine.builder import DEFAULT_PDF_OPTIONS
from apps.ventes.tests._quote_engine_common import (
    make_client, make_company, make_devis, make_user,
)

#: clé du moteur → (paramètre de requête, valeur envoyée, valeur attendue).
RELAIS = {
    'pdf_mode': ('pdf_mode', 'onepage', 'onepage'),
    'show_monthly': ('show_monthly', '0', False),
    'devis_final': ('devis_final', '1', True),
    'include_etude': ('include_etude', '1', True),
    'include_calepinage': ('include_calepinage', '0', False),
    'include_note_calcul': ('include_note_calcul', '1', True),
    'langue_sortie': ('langue', 'en', 'en'),
}

#: Clés volontairement NON relayées par ``/proposal`` — chacune avec sa raison.
EXCLUES_DE_PROPOSAL = {
    # AUTO par défaut (présente dès que le devis porte une conception) ;
    # l'opt-in/out explicite passe par le dialogue interne (generer-pdf).
    'include_annexe_technique': 'auto moteur ; choix explicite via generer-pdf',
    # L-NIV — dégradation anticopie posée par le serveur selon le niveau du
    # lien public, jamais un choix du lecteur.
    'kit_agrege': 'flag serveur (niveau du lien public)',
    # L-VAR — variante téléchargée depuis la page publique, pas /proposal.
    'variante_option': 'flag serveur (page publique, variante choisie)',
    # QRP1/A5 — jeton du lien qui sert le PDF : posé par le chemin public.
    'share_token': 'flag serveur (chemin public tokenisé)',
}


class OptionsRelayeesTests(TestCase):
    def setUp(self):
        self.company = make_company(slug='apdf49-co', nom='APDF49')
        self.user = make_user(self.company)
        self.devis = make_devis(
            self.company, self.user, make_client(self.company), [
                ('Panneau mono 450W', '12', '1500'),
                ('Onduleur hybride', '1', '12000'),
                ('Structures acier', '12', '450'),
            ], reference='DEV-APDF49-1')
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def _options_recues(self, param, valeur):
        captures = {}

        def _upload(pdf_bytes, key, *a, **k):
            captures[key] = pdf_bytes
            return key
        with mock.patch('apps.ventes.quote_engine.builder._ensure_pdf_bucket'), \
                mock.patch('apps.ventes.utils.pdf._upload_pdf',
                           side_effect=_upload), \
                mock.patch('apps.ventes.utils.pdf.download_pdf',
                           side_effect=lambda key: captures.get(key, b'')), \
                mock.patch.object(
                    quote_engine, 'generate_premium_devis_pdf',
                    wraps=quote_engine.generate_premium_devis_pdf) as moteur:
            resp = self.api.get(
                '/api/django/ventes/devis/%s/proposal/' % self.devis.pk,
                {param: valeur})
        self.assertEqual(resp.status_code, 200, (param, resp.content[:200]))
        return moteur.call_args.args[1]

    def test_chaque_cle_relayee_ou_exclue(self):
        cles = set(DEFAULT_PDF_OPTIONS)
        self.assertEqual(set(RELAIS) & set(EXCLUES_DE_PROPOSAL), set())
        self.assertEqual(
            cles - set(RELAIS) - set(EXCLUES_DE_PROPOSAL), set(),
            'clé du moteur ni relayée par /proposal ni exclue avec raison')
        for raison in EXCLUES_DE_PROPOSAL.values():
            self.assertTrue(raison.strip())

    def test_chaque_option_relayee(self):
        for cle, (param, valeur, attendu) in RELAIS.items():
            with self.subTest(cle=cle):
                self.assertNotEqual(DEFAULT_PDF_OPTIONS[cle], attendu,
                                    'la valeur testée doit différer du défaut')
                options = self._options_recues(param, valeur)
                self.assertEqual(options[cle], attendu)
