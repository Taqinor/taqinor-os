# -*- coding: utf-8 -*-
"""ACAL184 (D-ACAL-12, C-ACAL-007) — « depuis un modèle » n'a qu'UNE porte :
``POST calepinages/depuis-modele/``. La copie reprend le client du lead, un
couple lead/client incohérent est refusé, un lead déjà ouvert répond 409 ;
``creer-depuis-modele`` n'existe plus.

HTTP réel, base réelle ; le modèle est MARQUÉ par le service réel.
"""
from __future__ import annotations

from apps.calepinage.models import Calepinage
from apps.calepinage.services.modeles import marquer_modele
from apps.crm.models import Client, Lead

from .test_api_liste import URL, BaseApiCalepinage, url_detail

CASA = {'lat': 33.5731, 'lng': -7.5898}
DOCUMENT = {
    'version': 2,
    'pin': dict(CASA),
    'zones': [{'id': 'z1', 'label': 'Pan Sud',
               'vertices': [[CASA['lng'], CASA['lat']],
                            [CASA['lng'] + 0.0001, CASA['lat']],
                            [CASA['lng'] + 0.0001, CASA['lat'] + 0.0001]],
               'geometry': {'count': 12, 'azimuthDeg': 180,
                            'tiltDeg': 15}}],
}


class PorteUniqueModele(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        self.modele = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Villa type',
            roof_layout=DOCUMENT)
        marquer_modele(self.modele, user=self.user)
        self.client_k = Client.objects.create(company=self.company,
                                              nom='Client K')
        self.lead_l = Lead.objects.create(
            company=self.company, nom='Toiture L', client=self.client_k,
            roof_point={'lat': 33.6, 'lng': -7.6})

    def _depuis_modele(self, corps):
        return self.api.post(f'{URL}depuis-modele/',
                             dict({'modele_id': self.modele.pk}, **corps),
                             format='json')

    def test_depuis_modele_reprend_le_client_du_lead(self):
        reponse = self._depuis_modele({'lead_id': self.lead_l.pk})
        self.assertEqual(reponse.status_code, 201, reponse.data)
        copie = Calepinage.objects.get(pk=reponse.data['id'])
        self.assertEqual(copie.lead_id, self.lead_l.pk)
        self.assertEqual(copie.client_id, self.client_k.pk)
        # Relu par la liste filtrée sur le client et par le détail.
        liste = self.api.get(URL, {'client': self.client_k.pk})
        self.assertEqual(liste.status_code, 200, liste.data)
        self.assertIn(copie.pk, [ligne['id'] for ligne in self._lignes(liste)])
        detail = self.api.get(url_detail(copie.pk))
        self.assertEqual(detail.data['lead']['id'], self.lead_l.pk)
        self.assertEqual(detail.data['client']['id'], self.client_k.pk)

    def test_couple_lead_client_incoherent_refuse(self):
        avant = Calepinage.objects.count()
        reponse = self._depuis_modele({'lead_id': self.lead_l.pk,
                                       'client_id': self.client_a.pk})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('client_id', reponse.data)
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_lead_deja_ouvert_409(self):
        existant = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_l.pk, titre='Déjà là')
        avant = Calepinage.objects.count()
        reponse = self._depuis_modele({'lead_id': self.lead_l.pk})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['calepinage_existant'], existant.pk)
        self.assertEqual(Calepinage.objects.count(), avant)

    def test_creer_depuis_modele_n_existe_plus(self):
        reponse = self.api.post(f'{URL}creer-depuis-modele/',
                                {'modele': self.modele.pk,
                                 'lead': self.lead_l.pk}, format='json')
        self.assertIn(reponse.status_code, (404, 405), reponse.data)
        self.assertFalse(Calepinage.objects.filter(
            lead_id=self.lead_l.pk).exists())
