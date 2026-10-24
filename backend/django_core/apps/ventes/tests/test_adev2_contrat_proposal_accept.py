"""ADEV2 — contrat d'abord (PACT10) de la page publique : `proposal_accept.json`
(corps, réponse 200, 409 aux codes FERMÉS, 409 `aucun_canal` de l'OTP) et les
cinq clés ADDITIVES de `proposal_data.json` (fragment `exemple_adev2`), en
copies JSON-égales backend ET `apps/web`.

Contrat seul : aucune vue n'est appelée ici.

Run :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_adev2_contrat_proposal_accept -v 2
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

ECHANTILLONS = Path(__file__).resolve().parent.parent / 'contract_samples'
DEPOT = Path(__file__).resolve().parents[5]
WEB = DEPOT / 'apps' / 'web' / 'src' / 'contract_samples'

CODES_409 = [
    'version_remplacee', 'inactive', 'expiree', 'brouillon',
    'empreinte_perimee', 'validation_requise', 'statut',
    'vente_active_existante', 'ice_divergent',
]
CLES_ADDITIVES = {
    'economies_cumul_25_ans', 'empreinte_contenu', 'offre_expiree',
    'date_expiration', 'pdf_disponible',
}


def _lire(chemin):
    return json.loads(chemin.read_text(encoding='utf-8'))


class ContratProposalAcceptTests(SimpleTestCase):

    def setUp(self):
        self.accept = _lire(ECHANTILLONS / 'proposal_accept.json')
        self.data = _lire(ECHANTILLONS / 'proposal_data.json')

    def test_codes_409_fermes_et_corps(self):
        doc = self.accept
        self.assertEqual(
            doc['endpoint'], 'POST /api/django/public/proposal/<token>/accept/')
        # Corps : l'empreinte du contenu lu est déclarée et documentée.
        self.assertIn('empreinte_contenu', doc['exemple'])
        self.assertIsInstance(doc['exemple']['empreinte_contenu'], str)
        self.assertTrue(doc['exemple']['empreinte_contenu'])
        self.assertIn('empreinte_contenu', doc['corps'])
        # Réponse 200 : porte `paiement`.
        self.assertIn('paiement', doc['reponse_200'])
        self.assertEqual(doc['reponse_200']['statut'], 'accepte')
        # 409 : liste FERMÉE, chaque code a sa réponse {detail, code} exacte.
        self.assertEqual(doc['codes_409'], CODES_409)
        reponses = {k: v for k, v in doc['reponses_409'].items()
                    if k != 'forme'}
        self.assertEqual(set(reponses), set(CODES_409))
        for code, corps in reponses.items():
            with self.subTest(code=code):
                self.assertEqual(set(corps), {'detail', 'code'})
                self.assertEqual(corps['code'], code)
                self.assertTrue(corps['detail'].strip())

    def test_recu_nomme_deux_empreintes_adev104(self):
        """ADEV104 (C-L3-LIEN-10) — le reçu distingue le DÉFI envoyé par la
        page (``empreinte_lue``) du SCEAU stocké (``empreinte_scellee`` =
        ``DevisSignature.content_hash``) ; ``empreinte_contenu`` reste servie
        un cycle comme alias documenté de ``empreinte_scellee``."""
        recu = self.accept['reponse_200']['recu']
        self.assertEqual(set(recu), {'signe_le', 'empreinte_lue',
                                     'empreinte_scellee', 'empreinte_contenu',
                                     'empreinte_pdf'})
        self.assertEqual(recu['empreinte_lue'],
                         self.accept['exemple']['empreinte_contenu'])
        self.assertEqual(recu['empreinte_contenu'], recu['empreinte_scellee'])
        self.assertNotEqual(recu['empreinte_lue'], recu['empreinte_scellee'])
        for cle in ('empreinte_lue', 'empreinte_scellee', 'alias'):
            with self.subTest(cle=cle):
                self.assertIn(cle, self.accept['corps']['recu'])

    def test_recu_servi_a_la_forme_du_contrat_adev104(self):
        """La sortie RÉELLE de ``recu_signature`` porte exactement les clés
        du contrat : défi relayé, sceau stocké, alias égal au sceau."""
        from types import SimpleNamespace
        from unittest import mock
        from apps.ventes.models import DevisSignature
        from apps.ventes.public.signature_views import recu_signature
        sig = SimpleNamespace(signed_at=None, content_hash='c' * 64,
                              signed_pdf_sha256='')
        objets = mock.Mock()
        objets.filter.return_value.first.return_value = sig
        with mock.patch.object(DevisSignature, 'objects', objets):
            recu = recu_signature(object(), 'a' * 64)
        self.assertEqual(set(recu), set(self.accept['reponse_200']['recu']))
        self.assertEqual(recu['empreinte_lue'], 'a' * 64)
        self.assertEqual(recu['empreinte_scellee'], 'c' * 64)
        self.assertEqual(recu['empreinte_contenu'], recu['empreinte_scellee'])

    def test_otp_409_aucun_canal(self):
        otp = self.accept['otp']
        self.assertEqual(otp['reponse_409']['code'], 'aucun_canal')
        self.assertEqual(set(otp['reponse_409']), {'detail', 'code'})
        self.assertEqual(otp['reponse_200'], {'detail': 'Code envoyé.'})

    def test_aucun_statut_nouveau(self):
        """Règle #4 : la réponse ne connaît que les statuts Devis existants."""
        from apps.ventes.models import Devis
        self.assertIn(self.accept['reponse_200']['statut'],
                      set(Devis.Statut.values))

    def test_cles_additives_de_proposal_data(self):
        fragment = self.data['exemple_adev2']
        self.assertEqual(set(fragment), CLES_ADDITIVES)
        # Additives : jamais `null` dans le contrat (bloc additif_vs_null).
        for cle, valeur in fragment.items():
            with self.subTest(cle=cle):
                self.assertIsNotNone(valeur)
        self.assertEqual(
            fragment['economies_cumul_25_ans'],
            {'sans_batterie': 342314, 'avec_batterie': 346653})
        self.assertIsInstance(fragment['offre_expiree'], bool)
        self.assertIsInstance(fragment['pdf_disponible'], bool)
        self.assertEqual(
            fragment['empreinte_contenu'],
            self.accept['exemple']['empreinte_contenu'])
        for cle in CLES_ADDITIVES:
            self.assertIn(cle, self.data['notes_adev2'])
        # `exemple` (forme_serveur: complete) ne porte une de ces clés que
        # lorsque la vue l'émet (moitié serveur ADEV49-ADEV52, PACT11).
        vue = (ECHANTILLONS.parent / 'public_views.py').read_text(
            encoding='utf-8')
        for cle in CLES_ADDITIVES:
            if cle in self.data['exemple']:
                with self.subTest(cle=cle):
                    self.assertIn(f"payload['{cle}']", vue)
                    self.assertEqual(self.data['exemple'][cle], fragment[cle])

    def test_avenant_vnt2(self):
        """VNT2 : réponse `avenant_signe` et clé `avenant` (fragments)."""
        rep = self.accept['avenant_signe']['reponse_200']
        self.assertIn('signe_le', rep['avenant_signe'])
        self.assertEqual(rep['statut'], 'accepte')
        for nom, a_signer in (('exemple_avenant_a_signer', True),
                              ('exemple_avenant_signe', False)):
            with self.subTest(nom=nom):
                avenant = self.data[nom]['avenant']
                self.assertEqual(set(avenant),
                                 {'a_signer', 'remplace', 'signe_le'})
                self.assertIs(avenant['a_signer'], a_signer)
                self.assertIn('reference', avenant['remplace'])
        # Additive : `avenant` n'est déclaré que dans `exemple` (VNT61, la
        # page publique le lit) et dans les deux exemples dédiés — jamais
        # dans les autres exemples existants.
        self.assertEqual(set(self.data['exemple']['avenant']),
                         {'a_signer', 'remplace', 'signe_le'})
        for nom, exemple in self.data.items():
            if (nom.startswith('exemple') and isinstance(exemple, dict)
                    and nom not in ('exemple', 'exemple_avenant_a_signer',
                                    'exemple_avenant_signe')):
                with self.subTest(nom=nom):
                    self.assertNotIn('avenant', exemple)

    def test_copies_web_json_egales(self):
        if not WEB.is_dir():  # pragma: no cover — image backend sans apps/web
            self.skipTest('apps/web absent de cet environnement')
        for nom in ('proposal_accept.json', 'proposal_data.json'):
            with self.subTest(nom=nom):
                self.assertEqual(_lire(WEB / nom), _lire(ECHANTILLONS / nom))
