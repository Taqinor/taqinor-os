"""ACAL176 — les calepinages d'un lead absorbé suivent le survivant.

Constat C-ACAL-001 (audit 2026-10-04) : la fusion de leads déplaçait devis,
chantiers et chatter vers le survivant, mais PAS les calepinages — le dessin
restait accroché à un lead archivé, et « Ouvrir dans le module Calepinage »
depuis le survivant en créait un second, vierge.

Ce qui est tenu ici, sur le service réel (``liens.transferer_lead``), deux
leads réels, un calepinage archivé par la corbeille réelle (``apps.trash``),
sans aucun mock :
  * TOUS les calepinages du lead absorbé (archivés compris) passent au
    survivant, avec son client quand ils n'en avaient pas ou portaient celui
    de l'absorbé, et une ligne de chatter chacun ;
  * ni le document, ni l'empreinte, ni le statut ne bougent ;
  * un lead d'une autre société ne déplace rien.

Run :
    python manage.py test apps.calepinage.tests.test_acal_liens_fusion_lead -v2
"""
from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.services.archivage import archiver, est_archive
from apps.calepinage.services.liens import transferer_lead
from apps.crm.models import Client, Lead
from apps.records.models import Activity
from authentication.models import Company

DOCUMENT = {'version': 2, 'zones': [{'id': 'z1', 'pitchDeg': 30}],
            'result': {'panels': 12}}


class TransfererLeadTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Fusion Co',
                                              slug='acal176-fusion')
        self.autre = Company.objects.create(nom='Voisine Co',
                                            slug='acal176-voisine')
        self.client_1 = Client.objects.create(company=self.company,
                                              nom='Client survivant')
        self.client_2 = Client.objects.create(company=self.company,
                                              nom='Client absorbé')
        self.client_tiers = Client.objects.create(company=self.company,
                                                  nom='Client posé à la main')
        self.survivant = Lead.objects.create(company=self.company,
                                             nom='Villa Anfa',
                                             client=self.client_1)
        self.absorbe = Lead.objects.create(company=self.company,
                                           nom='Villa Anfa (doublon)',
                                           client=self.client_2)
        self.dessine = Calepinage.objects.create(
            company=self.company, lead_id=self.absorbe.pk,
            client_id=self.client_2.pk, titre='Toiture dessinée',
            roof_layout=DOCUMENT, layout_hash='h-dessine',
            statut=Calepinage.Statut.VALIDE)
        self.miroir = Calepinage.objects.create(
            company=self.company, lead_id=self.absorbe.pk,
            titre='Miroir du devis', roof_layout={}, layout_hash='')
        self.archive = Calepinage.objects.create(
            company=self.company, lead_id=self.absorbe.pk,
            client_id=self.client_tiers.pk, titre='Ancienne étude')
        archiver(self.archive)

    def _notes(self, calepinage):
        return list(Activity.objects.filter(
            content_type=ContentType.objects.get_for_model(Calepinage),
            object_id=calepinage.pk, kind=Activity.Kind.NOTE)
            .values_list('body', flat=True))

    def test_transferer_lead_deplace_tous_les_calepinages_et_leur_client(self):
        self.assertTrue(est_archive(self.archive))
        deplaces = transferer_lead(self.company,
                                   de_lead_id=self.absorbe.pk,
                                   vers_lead_id=self.survivant.pk)

        self.assertEqual(sorted(deplaces), sorted(
            [self.dessine.pk, self.miroir.pk, self.archive.pk]))
        for cal in (self.dessine, self.miroir, self.archive):
            cal.refresh_from_db()
            self.assertEqual(cal.lead_id, self.survivant.pk)
        # Client de l'absorbé ou aucun client ⇒ client du survivant.
        self.assertEqual(self.dessine.client_id, self.client_1.pk)
        self.assertEqual(self.miroir.client_id, self.client_1.pk)
        # Un client posé à la main, différent, n'est jamais écrasé.
        self.assertEqual(self.archive.client_id, self.client_tiers.pk)
        self.assertTrue(est_archive(self.archive))
        self.assertFalse(Calepinage.objects.filter(
            lead_id=self.absorbe.pk).exists())
        for cal in (self.dessine, self.miroir, self.archive):
            notes = self._notes(cal)
            self.assertEqual(len(notes), 1, notes)
            self.assertIn(f'Rattaché au lead #{self.survivant.pk}', notes[0])
            self.assertIn(f'fusion avec #{self.absorbe.pk}', notes[0])

    def test_transfert_ne_touche_ni_layout_ni_statut(self):
        avant = Calepinage.objects.values(
            'roof_layout', 'layout_hash', 'statut').get(pk=self.dessine.pk)
        transferer_lead(self.company, de_lead_id=self.absorbe.pk,
                        vers_lead_id=self.survivant.pk)
        apres = Calepinage.objects.values(
            'roof_layout', 'layout_hash', 'statut').get(pk=self.dessine.pk)
        self.assertEqual(apres, avant)

    def test_survivant_deja_ouvert_les_deux_restent_ouverts(self):
        existant = Calepinage.objects.create(
            company=self.company, lead_id=self.survivant.pk,
            client_id=self.client_1.pk, titre='Étude du survivant')
        transferer_lead(self.company, de_lead_id=self.absorbe.pk,
                        vers_lead_id=self.survivant.pk)
        existant.refresh_from_db()
        self.dessine.refresh_from_db()
        self.assertEqual(existant.lead_id, self.survivant.pk)
        self.assertEqual(self.dessine.lead_id, self.survivant.pk)
        self.assertFalse(est_archive(existant))
        self.assertFalse(est_archive(self.dessine))
        self.assertIn(f'#{existant.pk}', self._notes(self.dessine)[0])
        self.assertIn('les deux restent ouverts', self._notes(self.dessine)[0])

    def test_lead_d_une_autre_societe_ne_deplace_rien(self):
        etranger = Lead.objects.create(company=self.autre, nom='Ailleurs')
        # Survivant étranger : rien ne bouge.
        self.assertEqual(transferer_lead(
            self.company, de_lead_id=self.absorbe.pk,
            vers_lead_id=etranger.pk), [])
        # Calepinages d'un lead étranger appelés depuis la mauvaise société.
        cal_etranger = Calepinage.objects.create(
            company=self.autre, lead_id=etranger.pk, titre='Étranger')
        self.assertEqual(transferer_lead(
            self.company, de_lead_id=etranger.pk,
            vers_lead_id=self.survivant.pk), [])
        cal_etranger.refresh_from_db()
        self.assertEqual(cal_etranger.lead_id, etranger.pk)
        self.assertEqual(Calepinage.objects.filter(
            lead_id=self.absorbe.pk).count(), 3)
