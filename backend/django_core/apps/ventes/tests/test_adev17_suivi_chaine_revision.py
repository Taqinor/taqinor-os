# -*- coding: utf-8 -*-
"""ADEV17 (C-ADEV-009) — la réception du chantier referme les liens de suivi
prolongés de TOUTES les versions de la chaîne de révision.

Rejoue la sonde VA p5 : V1 acceptée (lien prolongé « jusqu'à la réception »),
révisée, V2 acceptée, chantier rattaché à V2. Avant : à la réception, le lien
de V1 restait ``valide: True`` sans limite. Le signal réel
``core.events.chantier_receptionne`` est émis (récepteur branché dans
``VentesConfig.ready``) avec un payload minimal (``devis_id``,
``date_reception``) — c'est tout ce que lit le récepteur.

Test-du-test : retirer l'itération sur les prédécesseurs dans
``fermer_suivi_a_reception`` ⇒ ``test_reception_ferme_lien_v1`` échoue.
"""
import datetime
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.crm.models import Client
from apps.ventes.domain.suivi import ouvrir_suivi
from apps.ventes.models import Devis, ShareLink
from authentication.models import Company
from core.events import chantier_receptionne

User = get_user_model()


class SuiviChaineRevisionTests(TestCase):

    def setUp(self):
        self.company = Company.objects.create(nom='ADEV17 Co')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='ADEV17',
            telephone='+212600000017')
        self.v1 = Devis.objects.create(
            company=self.company, reference='DEV-ADEV17-V1',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        self.lien_v1 = ShareLink.for_devis(self.v1)
        # V1 acceptée : prolongation posée par l'acceptation.
        ouvrir_suivi(self.v1)
        self.v2 = Devis.objects.create(
            company=self.company, reference='DEV-ADEV17-V2',
            client=self.client_obj, statut=Devis.Statut.ACCEPTE,
            taux_tva=Decimal('20'))
        Devis.objects.filter(pk=self.v1.pk).update(superseded_by=self.v2)
        self.lien_v2 = ShareLink.for_devis(self.v2)

    def _recharger(self):
        self.lien_v1.refresh_from_db()
        self.lien_v2.refresh_from_db()

    def _receptionner(self, devis, date_reception):
        chantier_receptionne.send(
            sender=self.__class__,
            installation=SimpleNamespace(
                devis_id=devis.pk, date_reception=date_reception))

    def test_reception_ferme_lien_v1(self):
        # La prolongation de V1 survit (sonde : elle n'était jamais levée)
        # — on la remet explicitement pour isoler la fermeture à réception.
        ShareLink.objects.filter(pk=self.lien_v1.pk).update(
            suivi_prolonge_le=timezone.now())
        ShareLink.objects.filter(pk=self.lien_v2.pk).update(
            suivi_prolonge_le=timezone.now())
        date_reception = timezone.localdate()
        self._receptionner(self.v2, date_reception)
        self._recharger()
        # V1 : fermé, persisté.
        self.assertIsNone(self.lien_v1.suivi_prolonge_le)
        self.assertFalse(self.lien_v1.is_valid)
        # V2 : règle actuelle (réception + 90 j), toujours valide.
        self.assertIsNone(self.lien_v2.suivi_prolonge_le)
        self.assertTrue(self.lien_v2.is_valid)
        self.assertEqual(
            timezone.localtime(self.lien_v2.expires_at).date(),
            date_reception + datetime.timedelta(days=91))
        # Côté client : le lien de V1 ne sert plus le suivi.
        rep = self.client.get(
            f'/api/django/ventes/suivi/{self.lien_v1.token}/')
        self.assertEqual(rep.status_code, 404)

    def test_ouvrir_suivi_v2_leve_prolongation_v1(self):
        self.lien_v1.refresh_from_db()
        self.assertIsNotNone(self.lien_v1.suivi_prolonge_le)
        ouvrir_suivi(self.v2)
        self._recharger()
        self.assertIsNone(self.lien_v1.suivi_prolonge_le)
        self.assertIsNotNone(self.lien_v2.suivi_prolonge_le)

    def test_chantier_non_receptionne_ne_ferme_rien(self):
        ouvrir_suivi(self.v2)
        self._recharger()
        avant = [(lien.expires_at, lien.revoque_le)
                 for lien in (self.lien_v1, self.lien_v2)]
        # Aucun signal de réception : rien n'est fermé.
        self._recharger()
        self.assertTrue(self.lien_v2.is_valid)
        self.assertIsNotNone(self.lien_v2.suivi_prolonge_le)
        self.assertEqual(
            [(lien.expires_at, lien.revoque_le)
             for lien in (self.lien_v1, self.lien_v2)], avant)
