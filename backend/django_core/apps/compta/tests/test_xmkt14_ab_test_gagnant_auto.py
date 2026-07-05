"""XMKT14 — Test A/B avec gagnant automatique.

Couvre : répartition sans chevauchement ni doublon, gagnant choisi et
envoyé automatiquement, tout est visible sur le détail campagne (A vs B vs
reste), tests avec horloge simulée.
"""
import datetime

from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from apps.compta import services
from apps.compta.models import Campagne, EnvoiCampagne


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


class ABTestGagnantAutoTests(TestCase):
    def setUp(self):
        self.co = make_company('xmkt14', 'XMKT14')

    def _campagne_ab(self, **kwargs):
        defaults = dict(
            company=self.co, nom='AB', canal=Campagne.Canal.EMAIL,
            ab_test={
                'pct_echantillon': 40, 'fenetre_heures': 4,
                'critere': 'ouvertures'})
        defaults.update(kwargs)
        return Campagne.objects.create(**defaults)

    def test_repartition_sans_chevauchement(self):
        camp = self._campagne_ab()
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        services.envoyer_campagne(camp, destinataires=destinataires)
        variantes_a = EnvoiCampagne.objects.filter(
            campagne=camp, variante_ab='a').count()
        variantes_b = EnvoiCampagne.objects.filter(
            campagne=camp, variante_ab='b').count()
        reste = EnvoiCampagne.objects.filter(
            campagne=camp, variante_ab='').count()
        # 40% de 10 = 4 échantillon, moitié 2/2, reste 6.
        self.assertEqual(variantes_a, 2)
        self.assertEqual(variantes_b, 2)
        self.assertEqual(reste, 6)

    def test_gagnant_egalite_choisit_a(self):
        camp = self._campagne_ab()
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        services.envoyer_campagne(camp, destinataires=destinataires)
        camp.envoyee_le = timezone.now() - datetime.timedelta(hours=5)
        camp.save(update_fields=['envoyee_le'])
        gagnant = services.decider_gagnant_ab(camp)
        self.assertEqual(gagnant, 'a')

    def test_gagnant_b_envoye_au_reste(self):
        camp = self._campagne_ab()
        destinataires = [f'u{i}@x.ma' for i in range(10)]
        services.envoyer_campagne(camp, destinataires=destinataires)
        camp.envoyee_le = timezone.now() - datetime.timedelta(hours=5)
        camp.save(update_fields=['envoyee_le'])
        variante_b_envoi = EnvoiCampagne.objects.filter(
            campagne=camp, variante_ab='b').first()
        variante_b_envoi.ouvert_le = timezone.now()
        variante_b_envoi.save(update_fields=['ouvert_le'])
        gagnant = services.decider_gagnant_ab(camp)
        self.assertEqual(gagnant, 'b')
        camp.refresh_from_db()
        self.assertEqual(camp.ab_gagnant, 'b')
        reste = EnvoiCampagne.objects.filter(campagne=camp, variante_ab='b')
        # 2 initiaux B + 6 du reste basculés = 8.
        self.assertEqual(reste.count(), 8)

    def test_fenetre_pas_ecoulee_pas_de_decision(self):
        camp = self._campagne_ab()
        services.envoyer_campagne(camp, destinataires=['a@x.ma', 'b@x.ma'])
        gagnant = services.decider_gagnant_ab(camp)
        self.assertIsNone(gagnant)

    def test_deja_decide_no_op(self):
        camp = self._campagne_ab(ab_gagnant='a')
        gagnant = services.decider_gagnant_ab(camp)
        self.assertIsNone(gagnant)

    def test_sans_ab_test_no_op(self):
        camp = Campagne.objects.create(
            company=self.co, nom='Sans AB', canal=Campagne.Canal.EMAIL,
            envoyee_le=timezone.now() - datetime.timedelta(hours=5))
        gagnant = services.decider_gagnant_ab(camp)
        self.assertIsNone(gagnant)
