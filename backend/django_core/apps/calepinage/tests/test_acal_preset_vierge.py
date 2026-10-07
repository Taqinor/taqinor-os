# -*- coding: utf-8 -*-
"""ACAL186 (D-ACAL-20, C-ACAL-008) — un jeu de réglages choisi sur un
calepinage VIERGE est MÉMORISÉ dans le document (``jeuReglages``), au lieu
d'être validé puis jeté ; avec un modèle, il s'applique aux pans ET se
mémorise.

HTTP réel (POST depuis-modele/, GET layout/, GET chatter), base réelle ; les
réglages société sont ÉCRITS en base (``enregistrer_parametres``).
"""
from __future__ import annotations

import copy

from apps.calepinage.models import Calepinage
from apps.calepinage.services.modeles import marquer_modele
from apps.calepinage.services.parametres import enregistrer_parametres

from .test_api_liste import URL, BaseApiCalepinage, url_detail

JEU = {'id': 'villa', 'nom': 'Villa tuiles', 'roofType': 'tuiles',
       'pitchDeg': 22, 'marge_m': 0.3}
DOCUMENT = {
    'version': 2,
    'zones': [{'id': 'z1', 'label': 'Pan Sud', 'pitchDeg': 10,
               'vertices': [[-7.6, 33.5], [-7.5999, 33.5],
                            [-7.5999, 33.5001]],
               'geometry': {'count': 2, 'panels': [{'cx': 1, 'cy': 1}]}}],
}
MEMORISE = {'presetId': 'villa', 'libelle': 'Villa tuiles',
            'valeurs': {'roofType': 'tuiles', 'pitchDeg': 22,
                        'marge_m': 0.3}}


class PresetVierge(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        enregistrer_parametres(self.company,
                               {'presets': {'jeux': [dict(JEU)]}})

    def _creer(self, corps, api=None):
        return (api or self.api).post(f'{URL}depuis-modele/', corps,
                                      format='json')

    def _chatter(self, pk):
        reponse = self.api.get(f'{url_detail(pk)}chatter/historique/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return [entree.get('body') or '' for entree in reponse.data]

    def test_preset_sans_modele_memorise_le_jeu(self):
        reponse = self._creer({'lead_id': self.lead.pk, 'preset_id': 'villa'})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        pk = reponse.data['id']
        layout = self.api.get(f'{url_detail(pk)}layout/')
        self.assertEqual(layout.status_code, 200, layout.data)
        document = layout.data.get('roof_layout', layout.data)
        self.assertEqual(document['jeuReglages'], MEMORISE)
        self.assertIn('Jeu de réglages « Villa tuiles » mémorisé : appliqué '
                      'à chaque nouveau pan.', self._chatter(pk))
        # Instantané, jamais une référence vivante : changer le jeu société
        # ensuite ne change pas le calepinage.
        enregistrer_parametres(self.company, {'presets': {'jeux': [
            dict(JEU, pitchDeg=35)]}})
        relu = Calepinage.objects.get(pk=pk)
        self.assertEqual(relu.roof_layout['jeuReglages'], MEMORISE)

    def test_preset_avec_modele_s_applique_et_memorise(self):
        modele = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Modèle villa',
            roof_layout=copy.deepcopy(DOCUMENT))
        marquer_modele(modele, user=self.user)
        self.lead_2.roof_point = {'lat': 33.59, 'lng': -7.62}
        self.lead_2.save(update_fields=['roof_point'])
        reponse = self._creer({'modele_id': modele.pk,
                               'lead_id': self.lead_2.pk,
                               'preset_id': 'villa'})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        copie = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(copie.roof_layout['zones'][0]['pitchDeg'], 22)
        self.assertEqual(copie.roof_layout['jeuReglages'], MEMORISE)
        self.assertTrue(any('appliqué à 1 pan(s)' in note
                            for note in self._chatter(copie.pk)))
        modele.refresh_from_db()
        self.assertNotIn('jeuReglages', modele.roof_layout)

    def test_preset_autre_societe_meme_message_qu_absent(self):
        enregistrer_parametres(self.autre, {'presets': {'jeux': [
            {'id': 'voisin', 'nom': 'Jeu voisin', 'pitchDeg': 30}]}})
        avant = Calepinage.objects.count()
        etranger = self._creer({'lead_id': self.lead.pk,
                                'preset_id': 'voisin'})
        absent = self._creer({'lead_id': self.lead.pk,
                              'preset_id': 'inexistant'})
        self.assertEqual(etranger.status_code, 400, etranger.data)
        self.assertEqual(absent.status_code, 400, absent.data)
        self.assertEqual(
            str(etranger.data['preset_id']).replace('voisin', '<id>'),
            str(absent.data['preset_id']).replace('inexistant', '<id>'))
        self.assertEqual(Calepinage.objects.count(), avant)
