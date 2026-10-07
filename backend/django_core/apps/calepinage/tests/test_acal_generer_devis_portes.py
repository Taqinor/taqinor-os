"""ACAL89 (C-ACAL-104/106/009) — les portes de « Générer le devis » du module.

* la COPIE d'un calepinage lié ne réutilise jamais le brouillon de
  l'original : un NOUVEAU devis lui est créé (porte PUB-10 : 500 avant) ;
* un double clic rend le MÊME devis (200, ``deduplique``), client seul compris ;
* un calepinage déjà lié à un devis non réutilisable (envoyé, ou brouillon
  d'une autre empreinte) répond 409 NOMMÉ ``{detail, devis, reference,
  revision_possible}`` sans créer de devis ni re-pointer le lien ;
* un lead agricole est refusé 422 ``{type_installation}`` ;
* la réponse porte ``avertissements`` / ``marques_manquantes`` (contrat
  ``calepinage_publication.json``).

Source réelle : ``build_devis_from_layout``, ``lier_devis``,
``devis_brouillon_pour_layout`` et ``devis_modifiabilite`` — aucun mock ;
catalogue semé comme les tests ventes (``seed_catalogue``).
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from apps.calepinage.models import Calepinage
from apps.calepinage.services.layout import enregistrer_layout
from apps.calepinage.services.variantes import dupliquer
from apps.crm.models import Client, Lead
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail

CONTRAT = json.loads(
    (Path(__file__).resolve().parent.parent / 'contract_samples'
     / 'calepinage_publication.json').read_text(encoding='utf-8'))

TOIT = {
    'areas': [{
        'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
        'obstacles': [],
        'roofType': 'flat',
        'pitch': 10,
        'azimuth': 180,
    }],
    'scenario': 'reseau',
    'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10800, 'savings': 9200},
}


def url_generer(pk):
    return f'{url_detail(pk)}generer-devis/'


class GenererDevisPortesTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        from apps.ventes.tests.test_from_layout_endpoint import seed_catalogue

        seed_catalogue(self.company)
        self.original = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='QA-ACAL89-A')
        enregistrer_layout(self.original, copy.deepcopy(TOIT), user=self.user)

    def _generer(self, calepinage):
        return self.api.post(url_generer(calepinage.pk), {}, format='json')

    def test_copie_genere_nouveau_devis_sans_500(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        # ACAL187 — source OUVERTE : la copie vise un autre lead.
        copie = dupliquer(self.original, user=self.user,
                          lead_id=self.lead_2.pk)
        self.original.refresh_from_db()
        self.assertEqual(copie.layout_hash, self.original.layout_hash)

        reponse = self._generer(copie)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertNotEqual(reponse.data['devis'], premier.data['devis'])
        copie.refresh_from_db()
        self.original.refresh_from_db()
        self.assertEqual(copie.devis_id, reponse.data['devis'])
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_double_clic_dedup_meme_devis(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        avant = Devis.objects.filter(company=self.company).count()
        second = self._generer(self.original)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data['deduplique'])
        self.assertEqual(second.data['devis'], premier.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_client_seul_deux_clics_un_devis(self):
        client = Client.objects.create(company=self.company,
                                       nom='Client seul ACAL89')
        seul = Calepinage.objects.create(company=self.company,
                                         client=client, titre='QA-ACAL89-C')
        enregistrer_layout(seul, copy.deepcopy(TOIT), user=self.user)
        premier = self._generer(seul)
        self.assertEqual(premier.status_code, 201, premier.data)
        avant = Devis.objects.filter(company=self.company).count()
        second = self._generer(seul)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data['devis'], premier.data['devis'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)

    def test_lie_envoye_409_nomme_sans_nouveau_devis(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        Devis.objects.filter(pk=premier.data['devis']).update(
            statut=Devis.Statut.ENVOYE)
        avant = Devis.objects.filter(company=self.company).count()

        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(sorted(reponse.data),
                         sorted(CONTRAT['exemple_409_deja_rattache']))
        self.assertEqual(reponse.data['devis'], premier.data['devis'])
        self.assertIn(premier.data['reference'], reponse.data['detail'])
        self.assertIn('Resynchroniser le devis', reponse.data['detail'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_lie_brouillon_autre_empreinte_409_sans_re_liaison(self):
        premier = self._generer(self.original)
        self.assertEqual(premier.status_code, 201, premier.data)
        autre = copy.deepcopy(TOIT)
        autre['result'] = dict(autre['result'], panels=10, kwc=5.5)
        autre['areas'][0]['azimuth'] = 170
        enregistrer_layout(self.original, autre, user=self.user)
        avant = Devis.objects.filter(company=self.company).count()

        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['devis'], premier.data['devis'])
        self.assertIn('revision_possible', reponse.data)
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        self.original.refresh_from_db()
        self.assertEqual(self.original.devis_id, premier.data['devis'])

    def test_lead_agricole_422(self):
        agricole = Lead.objects.create(company=self.company,
                                       nom='Ferme Souss',
                                       type_installation='agricole')
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=agricole.pk, titre='QA-ACAL89-AGR')
        enregistrer_layout(calepinage, copy.deepcopy(TOIT), user=self.user)
        avant = Devis.objects.filter(company=self.company).count()
        reponse = self._generer(calepinage)
        self.assertEqual(reponse.status_code, 422, reponse.data)
        self.assertEqual(reponse.data,
                         CONTRAT['exemple_422_lead_agricole'])
        self.assertEqual(Devis.objects.filter(company=self.company).count(),
                         avant)
        calepinage.refresh_from_db()
        self.assertIsNone(calepinage.devis_id)

    def test_reponse_porte_avertissements(self):
        reponse = self._generer(self.original)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(sorted(reponse.data), sorted(CONTRAT['exemple']))
        self.assertIsInstance(reponse.data['avertissements'], list)
        self.assertIsInstance(reponse.data['marques_manquantes'], list)
        second = self._generer(self.original)
        self.assertEqual(sorted(second.data),
                         sorted(CONTRAT['exemple_deduplique']))
