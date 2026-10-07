# -*- coding: utf-8 -*-
"""ACAL187 (D-ACAL-12, C-ACAL-007) — Dupliquer un calepinage OUVERT exige une
cible (autre lead ou client) ; la copie se journalise (création +
provenance).

HTTP réel (POST dupliquer/, GET détail, GET chatter), base réelle.
"""
from __future__ import annotations

from apps.calepinage.models import Calepinage
from apps.calepinage.services.archivage import archiver
from apps.calepinage.services.modeles import marquer_modele
from apps.calepinage.services.variantes import MESSAGE_SOURCE_OUVERTE
from apps.crm.models import Lead

from .test_api_liste import BaseApiCalepinage, url_detail

LAYOUT = {'zones': [{'id': 'z1', 'label': 'Pan Sud',
                     'vertices': [[0, 0], [10, 0], [10, 6]],
                     'geometry': {'count': 10, 'azimuthDeg': 180,
                                  'tiltDeg': 15}}]}


def _url(pk, suffixe=''):
    return f'{url_detail(pk)}{suffixe}'


class DupliquerCible(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.source = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Villa Anfa',
            roof_layout=LAYOUT)

    def _dupliquer(self, source, corps=None, api=None):
        return (api or self.api).post(_url(source.pk, 'dupliquer/'),
                                      corps or {}, format='json')

    def test_dupliquer_sans_cible_sur_source_ouverte_409(self):
        avant = Calepinage.objects.count()
        reponse = self._dupliquer(self.source)
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data, {'lead': MESSAGE_SOURCE_OUVERTE})
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_dupliquer_vers_un_autre_lead_cree_et_journalise(self):
        cible = Lead.objects.create(company=self.company, nom='Toiture Oasis',
                                    client=self.client_a)
        reponse = self._dupliquer(self.source, {'lead': cible.pk})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        copie_id = reponse.data['calepinage']
        detail = self.api.get(_url(copie_id))
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertEqual(detail.data['lead']['id'], cible.pk)
        self.assertEqual(detail.data['client']['id'], self.client_a.pk)
        chatter = self.api.get(_url(copie_id, 'chatter/historique/'))
        self.assertEqual(chatter.status_code, 200, chatter.data)
        corps = [entree.get('body') or '' for entree in chatter.data]
        self.assertTrue(any(str(entree.get('kind') or '').upper()
                            == 'CREATION' for entree in chatter.data),
                        chatter.data)
        self.assertIn(f'Dupliqué depuis #{self.source.pk} (« Villa Anfa »)',
                      corps)
        # La source est inchangée.
        self.source.refresh_from_db()
        self.assertEqual(self.source.lead_id, self.lead.pk)

    def test_cible_deja_ouverte_409_nomme_l_existant(self):
        existant = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk, titre='Maârif')
        reponse = self._dupliquer(self.source, {'lead': self.lead_2.pk})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['calepinage_existant'], existant.pk)

    def test_modele_se_duplique_sans_cible(self):
        marquer_modele(self.source, user=self.user)
        reponse = self._dupliquer(self.source)
        self.assertEqual(reponse.status_code, 201, reponse.data)

    def test_source_archivee_se_duplique_sans_cible(self):
        # Un archivé garde ses routes de détail (ACAL119 : jamais 404) et
        # « Dupliquer » y est admis (crée une copie, la source n'est pas
        # écrite) : la route le duplique sans cible, sur le lead source.
        archiver(self.source, user=self.user)
        reponse = self._dupliquer(self.source)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        copie = Calepinage.objects.get(pk=reponse.data['calepinage'])
        self.assertEqual(copie.lead_id, self.lead.pk)

    def test_cible_d_une_autre_societe_introuvable(self):
        etranger = Lead.objects.create(company=self.autre, nom='Ailleurs')
        avant = Calepinage.objects.count()
        reponse = self._dupliquer(self.source, {'lead': etranger.pk})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('lead', reponse.data)
        self.assertIn('introuvable', str(reponse.data['lead']))
        self.assertEqual(Calepinage.objects.count(), avant)
