"""ACAL35 — un devis né pour un lead ADOPTE le calepinage ouvert de ce lead.

D-ACAL-1 : le calepinage est l'unique conception d'un devis. Ce qui est
prouvé ici, par les vraies routes HTTP et le vrai bus d'événements :

* ``POST /ventes/devis/from-layout/ {layout, lead: L}`` (miroir
  ``layout_finalise``) et ``POST calepinages/depuis-modele/ {devis_id}``
  rattachent le calepinage OUVERT du lead (sans devis) au devis — aucun
  second calepinage n'est créé ;
* l'adoption n'écrit PAS le document : ``roof_layout`` et ``layout_hash``
  relus en base sont identiques avant/après, aucune version n'est déposée ;
* ``depuis-lead`` rend ensuite ce même calepinage ;
* un calepinage CRÉÉ pour un devis ne recopie jamais les clés privées du
  devis (``_pans_geometry``, ``_origine_calepinage``) ;
* plusieurs ouverts sans devis ⇒ aucun choix silencieux : création, et un
  avertissement qui les nomme.

Run :
    python manage.py test apps.calepinage.tests.test_acal_adoption_devis -v2
"""
from __future__ import annotations

import copy

from core import events

from apps.calepinage.models import Calepinage
from apps.calepinage.selectors import calepinage_du_devis
from apps.calepinage.services.creation import creer_pour_lead
from apps.ventes.models import Devis
from apps.ventes.tests.test_from_layout_endpoint import (
    FROM_LAYOUT_URL, SAMPLE_LAYOUT, seed_catalogue,
)

from .test_api_liste import URL, BaseApiCalepinage

URL_DEPUIS_MODELE = f'{URL}depuis-modele/'
URL_DEPUIS_LEAD = f'{URL}depuis-lead/'

#: La conception du module : fond calé, surfaces de pose, module choisi —
#: les clés que le devis ne porte pas et qu'une réécriture perdrait.
CONCEPTION_DU_MODULE = {
    'schema_version': 2,
    'underlay': {'url': 'photo-toit.jpg', 'echelle': 0.05},
    'poseSurfaces': [{'id': 's1', 'zoneId': 'z1'}],
    'modules': [{'id': 'produit-550', 'watt': 550}],
    'zones': [{'id': 'z1', 'geometry': {'moduleId': 'produit-550'}}],
    'result': {'panels': 10, 'kwc': 5.5},
}


class AdoptionDevisTest(BaseApiCalepinage):

    def setUp(self):
        super().setUp()
        seed_catalogue(self.company)
        self.c1 = creer_pour_lead(self.lead.pk, self.company, user=self.user)
        Calepinage.objects.filter(pk=self.c1.pk).update(
            roof_layout=copy.deepcopy(CONCEPTION_DU_MODULE),
            layout_hash='a' * 64)
        self.c1.refresh_from_db()

    def _du_lead(self, lead=None):
        return Calepinage.objects.filter(
            company=self.company, lead_id=(lead or self.lead).pk)

    def _from_layout(self, lead=None):
        reponse = self.api.post(
            FROM_LAYOUT_URL,
            {'layout': SAMPLE_LAYOUT, 'lead': (lead or self.lead).pk},
            format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        return Devis.objects.get(pk=reponse.data['id'])

    def test_from_layout_adopte_calepinage_ouvert_du_lead(self):
        devis = self._from_layout()
        self.assertEqual(calepinage_du_devis(devis.pk, self.company), self.c1)
        self.assertEqual(self._du_lead().count(), 1,
                         'aucun second calepinage pour le lead')

    def test_adoption_ne_reecrit_pas_le_document(self):
        avant = (self.c1.roof_layout, self.c1.layout_hash,
                 self.c1.versions.count())
        devis = self._from_layout()
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.devis_id, devis.pk)
        self.assertEqual((self.c1.roof_layout, self.c1.layout_hash,
                          self.c1.versions.count()), avant)
        for cle in ('underlay', 'poseSurfaces', 'modules'):
            self.assertIn(cle, self.c1.roof_layout)

    def test_depuis_modele_devis_adopte_200(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-3501',
            roof_layout={'schema_version': 2, 'result': {'panels': 4}})
        reponse = self.api.post(URL_DEPUIS_MODELE, {'devis_id': devis.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['id'], self.c1.pk)
        self.c1.refresh_from_db()
        self.assertEqual(self.c1.roof_layout, CONCEPTION_DU_MODULE)
        self.assertEqual(self._du_lead().count(), 1)

    def test_devis_tenu_par_un_archive_409_nomme(self):
        """Lot 2 critique #4 — le calepinage du devis est ARCHIVÉ (caché par
        ``calepinages_actifs``) : 409 nommé « restaurez-le » avec son id,
        jamais un IntegrityError (500), rien de créé."""
        from django.utils import timezone

        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-3502',
            roof_layout={'schema_version': 2, 'result': {'panels': 4}})
        Calepinage.objects.filter(pk=self.c1.pk).update(
            devis=devis, archive_le=timezone.now())
        avant = Calepinage.objects.filter(company=self.company).count()
        reponse = self.api.post(URL_DEPUIS_MODELE, {'devis_id': devis.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 409, reponse.data)
        self.assertEqual(reponse.data['calepinage_archive'], self.c1.pk)
        self.assertIn('restaurez-le', reponse.data['devis'])
        self.assertEqual(
            Calepinage.objects.filter(company=self.company).count(), avant)

    def test_depuis_lead_rend_le_calepinage_adopte(self):
        self._from_layout()
        reponse = self.api.post(URL_DEPUIS_LEAD, {'lead': self.lead.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['calepinage'], self.c1.pk)
        self.assertFalse(reponse.data['cree'])
        self.assertEqual(self._du_lead().count(), 1)

    def test_creation_sans_cles_privees(self):
        document = dict(copy.deepcopy(SAMPLE_LAYOUT),
                        _pans_geometry=[{'azimut_deg': 180}],
                        _origine_calepinage='contour_client')
        for chemin in ('depuis-modele', 'layout_finalise'):
            with self.subTest(chemin=chemin):
                devis = Devis.objects.create(
                    company=self.company, client=self.client_a,
                    reference=f'DEV-202610-35{len(chemin)}',
                    roof_layout=copy.deepcopy(document))
                if chemin == 'depuis-modele':
                    reponse = self.api.post(URL_DEPUIS_MODELE,
                                            {'devis_id': devis.pk},
                                            format='json')
                    self.assertEqual(reponse.status_code, 201, reponse.data)
                else:
                    events.layout_finalise.send(sender='test', devis=devis,
                                                user=self.user)
                cree = calepinage_du_devis(devis.pk, self.company)
                self.assertIsNotNone(cree)
                self.assertNotEqual(cree.pk, self.c1.pk)
                self.assertEqual(
                    [cle for cle in cree.roof_layout if cle.startswith('_')],
                    [])
                self.assertEqual(cree.roof_layout['result'],
                                 SAMPLE_LAYOUT['result'])

    def test_plusieurs_ouverts_aucun_choix_silencieux(self):
        c2 = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Second')
        devis = Devis.objects.create(
            company=self.company, client=self.client_a, lead=self.lead,
            reference='DEV-202610-3502',
            roof_layout={'schema_version': 2, 'result': {'panels': 4}})
        with self.assertLogs('apps.calepinage.services.creation',
                             level='WARNING') as journal:
            reponse = self.api.post(URL_DEPUIS_MODELE,
                                    {'devis_id': devis.pk}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertNotIn(reponse.data['id'], (self.c1.pk, c2.pk))
        message = ' '.join(journal.output)
        self.assertIn(f'#{self.c1.pk}', message)
        self.assertIn(f'#{c2.pk}', message)
        self.c1.refresh_from_db()
        c2.refresh_from_db()
        self.assertIsNone(self.c1.devis_id)
        self.assertIsNone(c2.devis_id)
