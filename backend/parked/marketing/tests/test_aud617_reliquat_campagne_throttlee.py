"""AUD617 — une campagne throttlée doit envoyer son RELIQUAT.

Constat d'origine : ``envoyer_campagnes_planifiees`` tronquait la liste au
``debit_max_par_heure`` puis appelait ``envoyer_campagne``, qui forçait le
statut à ``ENVOYEE`` quel que soit le nombre de destinataires réellement
couverts. La campagne était donc « envoyée » dès le premier lot partiel et le
reliquat n'était JAMAIS envoyé — alors que la docstring du beat promettait
déjà l'inverse (« le reliquat repart en file au prochain passage beat »).

Test ROUGE d'abord : ``test_lot_partiel_ne_passe_pas_envoyee`` voyait
``ENVOYEE`` après le premier lot ; ``test_reliquat_part_aux_ticks_suivants``
voyait 2 destinataires couverts sur 5, définitivement.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.marketing.models import (
    AbonnementListe, Campagne, EnvoiCampagne, ListeDiffusion,
)


class ReliquatCampagneThrottleeTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aud617', nom='AUD617')
        self.liste = ListeDiffusion.objects.create(company=self.co, nom='L')
        for i in range(5):
            AbonnementListe.objects.create(
                company=self.co, liste=self.liste, destinataire=f'u{i}@x.ma',
                statut=AbonnementListe.Statut.INSCRIT)
        self.camp = Campagne.objects.create(
            company=self.co, nom='Throttlée', canal=Campagne.Canal.EMAIL,
            planifiee_le=timezone.now() - datetime.timedelta(minutes=1),
            debit_max_par_heure=2)
        self.camp.listes.add(self.liste)

    def _destinataires_touches(self):
        return set(EnvoiCampagne.objects.filter(
            campagne=self.camp).values_list('destinataire', flat=True))

    def test_lot_partiel_ne_passe_pas_envoyee(self):
        """ROUGE avant correctif : ENVOYEE dès le premier lot."""
        services.envoyer_campagnes_planifiees(self.co)
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.statut, Campagne.Statut.EN_FILE)
        self.assertIsNone(self.camp.envoyee_le)
        self.assertEqual(len(self._destinataires_touches()), 2)

    def test_reliquat_part_aux_ticks_suivants(self):
        """ROUGE avant correctif : 2 destinataires sur 5, définitivement."""
        services.envoyer_campagnes_planifiees(self.co)  # 2
        services.envoyer_campagnes_planifiees(self.co)  # 2
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.statut, Campagne.Statut.EN_FILE)

        services.envoyer_campagnes_planifiees(self.co)  # le dernier
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.statut, Campagne.Statut.ENVOYEE)
        self.assertIsNotNone(self.camp.envoyee_le)
        self.assertEqual(
            self._destinataires_touches(),
            {f'u{i}@x.ma' for i in range(5)})

    def test_aucun_destinataire_nest_re_sollicite(self):
        """Le beat relit la liste COMPLÈTE à chaque tick : sans filtre, le
        premier lot serait re-ciblé à chaque passage."""
        for _ in range(3):
            services.envoyer_campagnes_planifiees(self.co)
        lignes = EnvoiCampagne.objects.filter(campagne=self.camp)
        self.assertEqual(lignes.count(), 5)
        self.assertEqual(
            len({ligne.destinataire for ligne in lignes}), 5)

    def test_compteurs_cumulent_au_lieu_decraser(self):
        services.envoyer_campagnes_planifiees(self.co)
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.nb_destinataires, 2)
        services.envoyer_campagnes_planifiees(self.co)
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.nb_destinataires, 4)
        services.envoyer_campagnes_planifiees(self.co)
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.nb_destinataires, 5)

    def test_echeance_conservee_entre_les_lots(self):
        """La campagne reste reprenable : ``planifiee_le`` ne bouge pas."""
        echeance = self.camp.planifiee_le
        services.envoyer_campagnes_planifiees(self.co)
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.planifiee_le, echeance)

    def test_campagne_terminee_nest_plus_reprise(self):
        for _ in range(3):
            services.envoyer_campagnes_planifiees(self.co)
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.statut, Campagne.Statut.ENVOYEE)
        # Un tick de plus ne doit ni la reprendre ni recréer de ligne.
        services.envoyer_campagnes_planifiees(self.co)
        self.assertEqual(
            EnvoiCampagne.objects.filter(campagne=self.camp).count(), 5)


class SansThrottleComportementInchangeTests(TestCase):
    """Une campagne SANS débit horaire garde exactement l'ancien
    comportement : un seul lot, ``ENVOYEE`` immédiatement."""

    def setUp(self):
        self.co = Company.objects.create(slug='aud617b', nom='AUD617B')
        liste = ListeDiffusion.objects.create(company=self.co, nom='L')
        for i in range(3):
            AbonnementListe.objects.create(
                company=self.co, liste=liste, destinataire=f'v{i}@x.ma',
                statut=AbonnementListe.Statut.INSCRIT)
        self.camp = Campagne.objects.create(
            company=self.co, nom='Complète', canal=Campagne.Canal.EMAIL,
            planifiee_le=timezone.now() - datetime.timedelta(minutes=1))
        self.camp.listes.add(liste)

    def test_envoi_complet_en_un_lot(self):
        services.envoyer_campagnes_planifiees(self.co)
        self.camp.refresh_from_db()
        self.assertEqual(self.camp.statut, Campagne.Statut.ENVOYEE)
        self.assertEqual(self.camp.nb_destinataires, 3)

    def test_envoi_direct_dun_brouillon_inchange(self):
        camp = Campagne.objects.create(
            company=self.co, nom='Directe', canal=Campagne.Canal.EMAIL)
        services.envoyer_campagne(camp, destinataires=['w@x.ma'])
        camp.refresh_from_db()
        self.assertEqual(camp.statut, Campagne.Statut.ENVOYEE)
        self.assertEqual(camp.nb_destinataires, 1)
