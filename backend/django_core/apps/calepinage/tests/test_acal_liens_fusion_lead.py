"""ACAL176 — les calepinages d'un lead absorbé suivent le survivant.

Constat C-ACAL-001 (audit 2026-10-04) : ``crm.merge_leads`` déplaçait devis,
chantiers, activités et relances — pas un seul calepinage. Le dessin restait
accroché à une fiche archivée et « Ouvrir dans le module Calepinage » sur le
survivant en recréait un vide.

Ce qui est tenu ici, sur le service RÉEL et deux leads RÉELS (aucun mock) :
  * TOUS les calepinages de l'absorbé (archivés en corbeille compris) passent
    au survivant, leur client devient celui du survivant quand ils n'en
    avaient pas ou portaient celui de l'absorbé, une ligne de chatter le dit ;
  * conception, empreinte et statut restent identiques ;
  * ``depuis-lead`` sur le survivant rend le calepinage déplacé (cree:false) ;
  * un lead d'une autre société ne déplace rien.

Run :
    python manage.py test apps.calepinage.tests.test_acal_liens_fusion_lead -v2
"""
from __future__ import annotations

from django.contrib.contenttypes.models import ContentType

from apps.calepinage.models import Calepinage
from apps.calepinage.services.archivage import archiver, est_archive
from apps.calepinage.services.liens import transferer_lead
from apps.crm.models import Client, Lead
from apps.records.models import Activity
from apps.ventes.models import Devis

from .test_api_liste import URL, BaseApiCalepinage

LAYOUT = {'schema_version': 2, 'result': {'panels': 4}}


def _notes(calepinage):
    return list(Activity.objects.filter(
        content_type=ContentType.objects.get_for_model(Calepinage),
        object_id=calepinage.pk, kind=Activity.Kind.NOTE,
    ).values_list('body', flat=True))


class TransfererLeadTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.client_l1 = Client.objects.create(company=self.company,
                                               nom='Client survivant')
        self.client_l2 = Client.objects.create(company=self.company,
                                               nom='Client absorbé')
        self.l1 = Lead.objects.create(company=self.company, nom='Survivant',
                                      client=self.client_l1)
        self.l2 = Lead.objects.create(company=self.company, nom='Absorbé',
                                      client=self.client_l2)
        # c : dessiné sur L2, porte le client de L2.
        self.c = Calepinage.objects.create(
            company=self.company, lead_id=self.l2.pk, client=self.client_l2,
            titre='Toiture absorbée', roof_layout=LAYOUT,
            layout_hash='a' * 64)
        # c2 : le calepinage-miroir d'un devis de L2 (archivé en corbeille).
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_l2, lead=self.l2,
            reference='DEV-202610-0176')
        self.c2 = Calepinage.objects.create(
            company=self.company, lead_id=self.l2.pk, devis=self.devis,
            titre='Miroir du devis')
        archiver(self.c2)

    def test_transferer_lead_deplace_tous_les_calepinages_et_leur_client(self):
        self.assertTrue(est_archive(self.c2))
        deplaces = transferer_lead(self.company, de_lead_id=self.l2.pk,
                                   vers_lead_id=self.l1.pk, user=self.user)
        self.assertCountEqual(deplaces, [self.c.pk, self.c2.pk])
        for calepinage in (self.c, self.c2):
            calepinage.refresh_from_db()
            self.assertEqual(calepinage.lead_id, self.l1.pk)
            self.assertEqual(calepinage.client_id, self.client_l1.pk)
            self.assertIn(
                f'Rattaché au lead #{self.l1.pk} (fusion avec #{self.l2.pk}).',
                ' '.join(_notes(calepinage)))
        # Rouvrir : la fiche et la liste filtrée par le survivant le rendent.
        detail = self.api.get(f'{URL}{self.c.pk}/')
        self.assertEqual(detail.status_code, 200, detail.data)
        lead_servi = detail.data.get('lead')
        if isinstance(lead_servi, dict):
            lead_servi = lead_servi.get('id')
        self.assertEqual(lead_servi, self.l1.pk)
        liste = self.api.get(URL, {'lead': self.l1.pk})
        self.assertEqual(liste.status_code, 200)
        self.assertIn(self.c.pk, [ligne['id'] for ligne in self._lignes(liste)])
        # depuis-lead sur le survivant : le MÊME calepinage, rien de créé.
        reponse = self.api.post(f'{URL}depuis-lead/', {'lead': self.l1.pk},
                                format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertFalse(reponse.data['cree'])
        self.assertEqual(reponse.data['calepinage'], self.c.pk)

    def test_transfert_ne_touche_ni_layout_ni_statut(self):
        avant = Calepinage.objects.get(pk=self.c.pk)
        transferer_lead(self.company, de_lead_id=self.l2.pk,
                        vers_lead_id=self.l1.pk, user=self.user)
        apres = Calepinage.objects.get(pk=self.c.pk)
        self.assertEqual(apres.roof_layout, avant.roof_layout)
        self.assertEqual(apres.layout_hash, avant.layout_hash)
        self.assertEqual(apres.statut, avant.statut)

    def test_lead_d_une_autre_societe_ne_deplace_rien(self):
        etranger = Lead.objects.create(company=self.autre, nom='Voisin')
        # Absorbé d'une autre société : rien ne bouge.
        self.assertEqual(
            transferer_lead(self.company, de_lead_id=etranger.pk,
                            vers_lead_id=self.l1.pk, user=self.user), [])
        # Survivant d'une autre société : rien ne bouge non plus.
        self.assertEqual(
            transferer_lead(self.company, de_lead_id=self.l2.pk,
                            vers_lead_id=etranger.pk, user=self.user), [])
        # Société de l'appelant différente de celle des calepinages.
        self.assertEqual(
            transferer_lead(self.autre, de_lead_id=self.l2.pk,
                            vers_lead_id=etranger.pk, user=self.user), [])
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l2.pk)
        self.assertEqual(self.c.client_id, self.client_l2.pk)

    def test_survivant_deja_ouvert_les_deux_restent_ouverts(self):
        existant = Calepinage.objects.create(
            company=self.company, lead_id=self.l1.pk, client=self.client_l1,
            titre='Toiture survivante')
        transferer_lead(self.company, de_lead_id=self.l2.pk,
                        vers_lead_id=self.l1.pk, user=self.user)
        self.c.refresh_from_db()
        self.assertEqual(self.c.lead_id, self.l1.pk)
        self.assertFalse(est_archive(self.c))
        self.assertFalse(est_archive(existant))
        self.assertIn(f'#{existant.pk}', ' '.join(_notes(self.c)))
        self.assertIn('les deux restent ouverts', ' '.join(_notes(self.c)))
