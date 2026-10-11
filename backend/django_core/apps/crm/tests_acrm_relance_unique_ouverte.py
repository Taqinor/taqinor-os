"""ACRM55 (C-ACRM-030) — une seule touche À FAIRE par barreau, en BASE.

Sonde V_VB LSVC1-2 : une création double d'une touche (contact, 1) ouverte
était acceptée — l'idempotence n'était qu'applicative (ACRM35 verrouille).
La contrainte partielle ``crm_relance_une_ouverte_par_barreau`` est le filet
structurel ; ``initialiser_plan_relance`` et ``materialiser_touche_suivante``
rattrapent l'``IntegrityError`` dans un point de sauvegarde.

Test-du-test : retirer la contrainte de la migration 0136 ⇒
test_seconde_ouverte_refusee échoue.
"""
import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from authentication.models import Company

from apps.crm.models import Lead, RelanceEtape

JOUR = datetime.date(2026, 10, 20)


class RelanceUniqueOuverteTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(
            nom='ACRM55 Solaire', slug='acrm55-unique')
        self.lead = Lead.objects.create(
            company=self.company, nom='Barreau', telephone='+212661555555')

    def _touche(self, **kw):
        valeurs = dict(company=self.company, lead=self.lead, cadence='contact',
                       ordre=1, due_date=JOUR, canal=RelanceEtape.Canal.APPEL)
        valeurs.update(kw)
        return RelanceEtape.objects.create(**valeurs)

    def test_seconde_ouverte_refusee(self):
        self._touche()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self._touche()
        # Persistance : une seule touche ouverte au barreau.
        self.assertEqual(RelanceEtape.objects.filter(
            lead=self.lead, cadence='contact', ordre=1,
            statut=RelanceEtape.Statut.A_FAIRE).count(), 1)

    def test_apres_cloture_acceptee(self):
        premiere = self._touche()
        premiere.statut = RelanceEtape.Statut.FAIT
        premiere.save(update_fields=['statut'])
        self._touche()
        self.assertEqual(RelanceEtape.objects.filter(
            lead=self.lead, cadence='contact', ordre=1).count(), 2)

    def test_filet_hors_contrainte(self):
        # Filet / geste (``cle`` posée) et cadence générique : jamais bloqués.
        self._touche()
        self._touche(cle='filet_acrm55')
        self._touche(cadence='generique')
        self._touche(cadence='generique')
        self.assertEqual(RelanceEtape.objects.filter(
            lead=self.lead, statut=RelanceEtape.Statut.A_FAIRE).count(), 4)
