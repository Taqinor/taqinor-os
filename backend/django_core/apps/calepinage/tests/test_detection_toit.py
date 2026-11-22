"""ACAL485 (D-ACAL-33) — détection du toit par IA : une PROPOSITION à confirmer.

Nouveau fichier car : première route d'IA du module, aucun module de test hôte.

Le fournisseur est un DOUBLE enregistré ici (``ClaudeVisionToitProvider`` réel,
transport ``httpx.MockTransport``) qui rejoue une réponse ENREGISTRÉE
(``fixtures/detection_toit_reponse.json``) : aucun appel réseau, jamais en CI.
Test-du-test : passer l'identifiant du lead au fournisseur ⇒
``test_seuls_les_octets_de_l_image_partent`` rougit ; retirer ``usage_context``
⇒ ``test_proposition_convertie_en_lnglat_et_journalisee`` rougit.
"""
from __future__ import annotations

import json
import pathlib
import struct

import httpx
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.calepinage.models import Calepinage
from apps.calepinage.services.detection_toit import DETAIL_INDISPONIBLE, MOTIF_NON_CONFIGUREE
from core.ai.fournisseurs_claude import ClaudeVisionToitProvider
from core.ai.registry import register_provider
from core.ai.usage import register_usage_sink, unregister_usage_sink

from ._m0_en_attente import affirmer_non_servies, sans
from .test_api_liste import BaseApiCalepinage, url_detail

REPONSE = json.loads((pathlib.Path(__file__).parent / 'fixtures' / 'detection_toit_reponse.json')
                     .read_text(encoding='utf-8'))
CONTRAT = json.loads((pathlib.Path(__file__).resolve().parent.parent / 'contract_samples'
                      / 'calepinage_detection_toit.json').read_text(encoding='utf-8'))
# ACAL530 : clé posée avant son producteur (ACAL1049), retirée par lui.
EN_ATTENTE = {'propositions.obstacles': 'ACAL1049'}
EMPRISE = {'ouest': -7.6001, 'sud': 33.5699, 'est': -7.5997, 'nord': 33.5703}
ENVOIS = []


@register_provider
class DoubleVisionToit(ClaudeVisionToitProvider):
    key = 'double_acal485'

    def _repondre(requete):
        ENVOIS.append(requete.content)
        return httpx.Response(200, json=REPONSE)
    transport = httpx.MockTransport(_repondre)


ACTIVE = override_settings(AI_PROVIDERS={'vision_toit': 'double_acal485'},
                           VISION_TOIT_CLE_API='cle-de-test', VISION_TOIT_MODELE='modele-de-test')


def _png():
    return (b'\x89PNG\r\n\x1a\n' + struct.pack('>I', 13) + b'IHDR'
            + struct.pack('>II', 64, 48) + b'\x08\x06\x00\x00\x00')


class DetectionToitTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        ENVOIS.clear()
        self.calepinage = Calepinage.objects.create(company=self.company, lead_id=self.lead.pk,
                                                    titre='QA-ACAL485')
        self.url = f'{url_detail(self.calepinage.pk)}detection-toit/'

    def _poster(self, contenu=None, origine='importee', emprise=None, api=None):
        corps = {'origine': origine, 'emprise': json.dumps(emprise or EMPRISE)}
        if contenu is not None:
            corps['image'] = SimpleUploadedFile('toit.png', contenu)
        return (api or self.api).post(self.url, corps, format='multipart')

    def test_sans_cle_get_indisponible_et_post_503(self):
        reponse = self.api.get(self.url)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple_disponibilite']))
        self.assertEqual(reponse.data, {'disponible': False, 'motif': MOTIF_NON_CONFIGUREE,
                                        'origines_acceptees': ['importee']})
        poste = self._poster(_png())
        self.assertEqual(poste.status_code, 503, poste.data)
        self.assertEqual(poste.data, {'detail': DETAIL_INDISPONIBLE})
        self.assertEqual(ENVOIS, [])

    @ACTIVE
    def test_proposition_convertie_en_lnglat_et_journalisee(self):
        journal = []

        def puits(**charge):
            journal.append(charge)
        register_usage_sink(puits)
        self.addCleanup(unregister_usage_sink, puits)
        avant = (self.calepinage.roof_layout, self.calepinage.updated_at)
        self.assertTrue(self.api.get(self.url).data['disponible'])

        reponse = self._poster(_png())
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        self.assertEqual((reponse.data['provenance'], reponse.data['a_confirmer']), ('ia', True))
        propositions = reponse.data['propositions']
        attendu = sans(CONTRAT['exemple'], EN_ATTENTE)['propositions']
        self.assertEqual(sorted(propositions), sorted(attendu))
        affirmer_non_servies(self, reponse.data, EN_ATTENTE)
        premier = propositions['pans'][0]
        self.assertEqual(sorted(premier), sorted(CONTRAT['exemple']['propositions']['pans'][0]))
        # Fraction (0.1, 0.2) : 0.1 de l'ouest vers l'est, 0.2 du nord vers le sud.
        self.assertAlmostEqual(premier['contour_lnglat'][0][0], -7.6001 + 0.1 * 0.0004, places=9)
        self.assertAlmostEqual(premier['contour_lnglat'][0][1], 33.5703 - 0.2 * 0.0004, places=9)
        self.assertEqual(premier['confiance'], 0.8)
        self.assertIsNone(propositions['pans'][1]['confiance'])
        self.assertEqual(len(propositions['contour_lnglat']), 4)  # enveloppe des deux pans
        self.assertEqual([(j['company_id'], j['feature_key'], j['capability']) for j in journal],
                         [(self.company.pk, 'calepinage.detection_toit', 'vision_toit')])
        self.calepinage.refresh_from_db()
        self.assertEqual((self.calepinage.roof_layout, self.calepinage.updated_at), avant)

    @ACTIVE
    def test_seuls_les_octets_de_l_image_partent(self):
        self.lead.nom = 'Client Secret Anfa'
        self.lead.save(update_fields=['nom'])
        self.assertEqual(self._poster(_png()).status_code, 200)
        self.assertEqual(len(ENVOIS), 1)
        envoye = ENVOIS[0].decode('utf-8')
        for interdit in ('Client Secret Anfa', 'QA-ACAL485', '-7.6001', '33.5703', 'toit.png',
                         f'"lead": {self.lead.pk}', f'lead_{self.lead.pk}'):
            self.assertNotIn(interdit, envoye)
        corps = json.loads(envoye)
        self.assertEqual([b['type'] for b in corps['messages'][0]['content']], ['image'])

    @ACTIVE
    def test_refus_nommes(self):
        # 400 = la FORME viole le schéma publié ; 409 = refus que le schéma ne
        # peut pas dire (origine connue mais fermée, ouest >= est) — api-fuzz #1512.
        cas = (({'contenu': None}, 'image', 400), ({'contenu': b''}, 'image', 400),
               ({'contenu': b'%PDF-1.4 plan'}, 'image', 400),
               ({'contenu': _png(), 'origine': 'satellite'}, 'origine', 400),
               ({'contenu': _png(), 'emprise': {'ouest': 1, 'sud': 2, 'est': 0}}, 'emprise', 400),
               ({'contenu': _png(), 'emprise': {'ouest': 1, 'sud': 2, 'est': 3, 'nord': 91}}, 'emprise', 400),
               ({'contenu': _png(), 'origine': 'carte'}, 'origine', 409),
               ({'contenu': _png(), 'emprise': {'ouest': 1, 'sud': 2, 'est': 0, 'nord': 3}}, 'emprise', 409))
        for kwargs, champ, code in cas:
            reponse = self._poster(**kwargs)
            self.assertEqual(reponse.status_code, code, (kwargs, reponse.data))
            self.assertIn(champ, reponse.data)
        self.assertEqual(ENVOIS, [])

    @ACTIVE
    @override_settings(DETECTION_TOIT_CAPTURE_CARTE=True)
    def test_origine_carte_ouverte_par_le_reglage(self):
        self.assertEqual(self.api.get(self.url).data['origines_acceptees'], ['importee', 'carte'])
        self.assertEqual(self._poster(_png(), origine='carte').status_code, 200)

    @ACTIVE
    def test_fournisseur_en_erreur_503(self):
        DoubleVisionToit.transport = httpx.MockTransport(lambda r: httpx.Response(500, json={}))
        self.addCleanup(setattr, DoubleVisionToit, 'transport',
                        httpx.MockTransport(DoubleVisionToit.__dict__['_repondre']))
        reponse = self._poster(_png())
        self.assertEqual(reponse.status_code, 503, reponse.data)
        self.assertEqual(reponse.data, {'detail': DETAIL_INDISPONIBLE})

    @ACTIVE
    def test_autre_societe_404(self):
        self.assertEqual(self.api_autre.get(self.url).status_code, 404)
        self.assertEqual(self._poster(_png(), api=self.api_autre).status_code, 404)
        self.assertEqual(ENVOIS, [])
