"""ACAL180 — changer lead, client et responsable d'un calepinage côté serveur.

Constat C-ACAL-013 (audit 2026-10-04) : le PATCH écrivait ``lead_id`` et
``client`` directement par le sérialiseur — sans regarder le devis lié, sans
la règle « un seul calepinage ouvert par lead » (D-ACAL-12) et sans une ligne
de chatter.

Ce qui est tenu ici, par le PATCH HTTP réel et ``liens.changer_rattachement``
(aucun mock) :
  * sans devis, le lead change, le client suit le lead, le chatter le dit ;
  * devis BROUILLON : permis ; devis ENVOYÉ : 409 « utilisez Réviser » ;
  * devis brouillon d'un AUTRE lead : 409 {lead} ;
  * lead qui a déjà un calepinage ouvert : 409 {lead, calepinage_existant} ;
  * responsable d'une autre société : 400 nommant ``responsable``.

Run :
    python manage.py test apps.calepinage.tests.test_acal_rattachement_edition -v2
"""
from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import Calepinage
from apps.crm.models import Client, Lead
from apps.records.models import Activity
from apps.ventes.models import Devis

from .test_api_liste import BaseApiCalepinage, url_detail


def _entrees(calepinage, champ):
    return list(Activity.objects.filter(
        content_type=ContentType.objects.get_for_model(Calepinage),
        object_id=calepinage.pk, field=champ,
    ).values_list('old_value', 'new_value'))


class RattachementEditionTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_1 = Client.objects.create(company=self.company,
                                              nom='Client un')
        self.client_2 = Client.objects.create(company=self.company,
                                              nom='Client deux')
        self.l1 = Lead.objects.create(company=self.company, nom='Lead un',
                                      client=self.client_1)
        self.l2 = Lead.objects.create(company=self.company, nom='Lead deux',
                                      client=self.client_2)
        self.c = Calepinage.objects.create(
            company=self.company, lead_id=self.l1.pk, client=self.client_1,
            titre='Toiture un')

    def _lier(self, statut, lead=None):
        devis = Devis.objects.create(
            company=self.company, client=self.client_1,
            lead=lead or self.l1, reference=f'DEV-202610-18{statut[:2]}',
            statut=statut)
        Calepinage.objects.filter(pk=self.c.pk).update(devis=devis)
        self.c.refresh_from_db()
        return devis

    def _patch(self, corps):
        return self.api.patch(url_detail(self.c.pk), corps, format='json')

    def test_changer_le_lead_d_un_calepinage_sans_devis(self):
        reponse = self._patch({'lead': self.l2.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        relu = self.api.get(url_detail(self.c.pk))
        self.assertEqual(relu.status_code, 200, relu.data)
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l2.pk)
        self.assertEqual(self.c.client_id, self.client_2.pk)

    def test_devis_brouillon_permis_devis_envoye_refuse_409(self):
        devis = self._lier('brouillon')
        reponse = self._patch({'responsable': self.user.pk,
                               'titre': 'Renommé'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        # Brouillon : le client se change (même lead, client cohérent).
        Lead.objects.filter(pk=self.l1.pk).update(client=self.client_2)
        reponse = self._patch({'client': self.client_2.pk})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.c.refresh_from_db()
        self.assertEqual(self.c.client_id, self.client_2.pk)
        # Envoyé : 409, rien n'est écrit.
        Devis.objects.filter(pk=devis.pk).update(statut='envoye')
        Lead.objects.filter(pk=self.l1.pk).update(client=self.client_1)
        reponse = self._patch({'client': self.client_1.pk,
                               'titre': 'Jamais'})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('utilisez Réviser', reponse.data['detail'])
        self.c.refresh_from_db()
        self.assertEqual(self.c.client_id, self.client_2.pk)
        self.assertNotEqual(self.c.titre, 'Jamais')
        devis.refresh_from_db()
        self.assertEqual(devis.statut, 'envoye')

    def test_devis_brouillon_lead_different_refuse_409(self):
        devis = self._lier('brouillon')
        reponse = self._patch({'lead': self.l2.pk})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('son lead doit rester celui du devis',
                      reponse.data['lead'])
        self.assertIn(devis.reference, reponse.data['lead'])
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l1.pk)

    def test_lead_deja_ouvert_refuse_409_avec_calepinage_existant(self):
        existant = Calepinage.objects.create(
            company=self.company, lead_id=self.l2.pk, client=self.client_2,
            titre='Toiture deux')
        reponse = self._patch({'lead': self.l2.pk})
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertIn('lead', reponse.data)
        self.assertEqual(reponse.data['calepinage_existant'], existant.pk)
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l1.pk)

    def test_responsable_autre_societe_refuse(self):
        reponse = self._patch({'responsable': self.user_autre.pk})
        self.assertEqual(reponse.status_code, 400, reponse.data)
        self.assertIn('responsable', reponse.data)
        self.c.refresh_from_db()
        self.assertIsNone(self.c.responsable_id)

    def test_chatter_ancien_vers_nouveau(self):
        self._patch({'lead': self.l2.pk, 'responsable': self.user.pk})
        self.assertEqual(_entrees(self.c, 'lead'),
                         [(f'#{self.l1.pk}', f'#{self.l2.pk}')])
        clients = _entrees(self.c, 'client')
        self.assertEqual(len(clients), 1)
        self.assertIn(f'#{self.client_1.pk}', clients[0][0])
        self.assertIn(f'#{self.client_2.pk}', clients[0][1])
        responsables = _entrees(self.c, 'responsable')
        self.assertEqual(len(responsables), 1)
        self.assertEqual(responsables[0][0], '')
        # Un PATCH qui ne change rien n'écrit aucune ligne de plus.
        self._patch({'lead': self.l2.pk})
        self.assertEqual(len(_entrees(self.c, 'lead')), 1)
