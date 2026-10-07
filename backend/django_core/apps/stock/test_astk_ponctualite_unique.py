"""ASTK186 — le facteur « ponctualité » du score de risque lit ``otd_stats``.

Une seule définition de la ponctualité (réception confirmée vs date confirmée
sinon prévue), partagée par la fiche 360, le portail et le score de risque.

Run :
    python manage.py test apps.stock.test_astk_ponctualite_unique -v 2
"""
import datetime

from django.test import TestCase

from apps.achats.models import BonCommandeFournisseur, ReceptionFournisseur
from apps.stock import selectors as stock_selectors
from apps.stock.models import Fournisseur
from apps.stock.services import otd_stats
from authentication.models import Company


def _bcf(company, fournisseur, ref, *, prevue, confirmee=None, recue=None):
    bcf = BonCommandeFournisseur.objects.create(
        company=company, fournisseur=fournisseur, reference=ref,
        date_livraison_prevue=prevue, date_confirmee_fournisseur=confirmee)
    if recue:
        ReceptionFournisseur.objects.create(
            company=company, reference=f'REC-{ref}', bon_commande=bcf,
            statut=ReceptionFournisseur.Statut.CONFIRME, date_reception=recue)
    return bcf


class PonctualiteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='astk186-co', defaults={'nom': 'ASTK186 Co'})
        self.fournisseur = Fournisseur.objects.create(
            company=self.company, nom='Four ASTK186')

    def _facteur(self):
        res = stock_selectors.score_risque_fournisseur(
            self.company, self.fournisseur.pk)
        return next(f for f in res['facteurs'] if f['code'] == 'ponctualite')

    def test_score_risque_lit_otd_stats(self):
        # Prévu le 01/10, jamais confirmé, reçu le 20/10 : +19 j.
        _bcf(self.company, self.fournisseur, 'BCF-186-1',
             prevue=datetime.date(2026, 10, 1),
             recue=datetime.date(2026, 10, 20))
        stats = otd_stats(self.company, self.fournisseur)
        self.assertEqual(stats['otd_ecart_moyen_jours'], 19.0)
        facteur = self._facteur()
        self.assertGreater(facteur['penalite'], 0)
        self.assertEqual(facteur['detail']['otd_ecart_moyen_jours'], 19.0)
        self.assertEqual(facteur['detail']['otd_a_lheure_pct'], 0.0)

    def test_confirmation_tardive_non_penalisee(self):
        # Date confirmée plus tardive que la prévue, mais livré à l'heure
        # par rapport à la date confirmée : pas pénalisé.
        _bcf(self.company, self.fournisseur, 'BCF-186-2',
             prevue=datetime.date(2026, 10, 1),
             confirmee=datetime.date(2026, 10, 10),
             recue=datetime.date(2026, 10, 10))
        facteur = self._facteur()
        self.assertEqual(facteur['penalite'], 0)
        self.assertEqual(facteur['detail']['otd_a_lheure_pct'], 100.0)
