"""CAL208 — archiver un calepinage, réversible, par la corbeille plateforme.

Ce qui est prouvé ici :

* ``archiver`` journalise une entrée de corbeille (``apps.trash.
  ElementSupprime``) — AUCUNE suppression physique du calepinage ;
* un calepinage archivé sort de ``selectors.liste_calepinages`` par défaut,
  mais reste lisible directement (``calepinage_detail``) ;
* ``restaurer`` le fait réapparaître à l'identique (même ``pk``, mêmes
  données) ;
* un calepinage lié à un devis ENVOYÉ s'archive sans toucher au devis
  (règle #4) ;
* restaurer un calepinage non archivé refuse, en nommant le champ.

Run :
    python manage.py test apps.calepinage.tests.test_cal208_archiver -v2
"""
from django.test import TestCase

from apps.calepinage import selectors
from apps.calepinage.models import Calepinage
from apps.calepinage.services.archivage import (
    ArchivageInvalide, archiver, est_archive, restaurer,
)
from apps.crm.models import Client
from apps.trash.models import ElementSupprime
from apps.ventes.models import Devis
from authentication.models import Company


class ArchiverTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Archive Co',
                                              slug='archive-co-208')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Client Archive')
        self.calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Villa Anfa')

    def test_archiver_cree_une_entree_de_corbeille(self):
        archiver(self.calepinage)
        self.assertTrue(est_archive(self.calepinage))
        self.assertEqual(
            ElementSupprime.objects.filter(
                content_type__app_label='calepinage',
                content_type__model='calepinage',
                object_id=self.calepinage.pk, restaure_le__isnull=True
            ).count(), 1)

    def test_aucune_suppression_physique(self):
        archiver(self.calepinage)
        self.assertTrue(
            Calepinage.objects.filter(pk=self.calepinage.pk).exists())

    def test_sort_de_la_liste_par_defaut(self):
        archiver(self.calepinage)
        ids = list(selectors.liste_calepinages(self.company)
                   .values_list('pk', flat=True))
        self.assertNotIn(self.calepinage.pk, ids)

    def test_reste_lisible_par_calepinage_detail(self):
        archiver(self.calepinage)
        trouve = selectors.calepinage_detail(self.calepinage.pk, self.company)
        self.assertIsNotNone(trouve)

    def test_restaurer_reapparait_a_l_identique(self):
        archiver(self.calepinage)
        restaurer(self.calepinage)
        self.assertFalse(est_archive(self.calepinage))
        ids = list(selectors.liste_calepinages(self.company)
                   .values_list('pk', flat=True))
        self.assertIn(self.calepinage.pk, ids)
        self.calepinage.refresh_from_db()
        self.assertEqual(self.calepinage.titre, 'Villa Anfa')

    def test_restaurer_non_archive_refuse(self):
        with self.assertRaises(ArchivageInvalide) as ctx:
            restaurer(self.calepinage)
        self.assertEqual(ctx.exception.champ, 'calepinage')

    def test_archiver_calepinage_lie_a_devis_envoye_ne_touche_pas_le_devis(self):
        devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-CAL208-1', statut=Devis.Statut.ENVOYE)
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, devis=devis)
        archiver(calepinage)
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.ENVOYE)
        self.assertTrue(est_archive(calepinage))

    def test_isolation_multi_societe(self):
        autre = Company.objects.create(nom='Autre Co', slug='autre-co-208')
        archiver(self.calepinage)
        ids_autre = list(selectors.liste_calepinages(
            autre, inclure_archives=True).values_list('pk', flat=True))
        self.assertNotIn(self.calepinage.pk, ids_autre)
