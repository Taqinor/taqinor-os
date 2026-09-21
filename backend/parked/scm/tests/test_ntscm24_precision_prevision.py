"""NTSCM24 — Précision de prévision auto-mesurée (forecast accuracy / MAPE).

Critère d'acceptation : un produit à demande parfaitement stable et prévue
correctement affiche un MAPE proche de 0%, vérifié par test synthétique."""
from django.test import TestCase
from django.utils import timezone

from apps.scm.models import PrevisionDemande
from apps.scm.selectors import precision_prevision
from apps.stock.models import MouvementStock, Produit

from .helpers import auth, make_company, make_user


class PrecisionPrevisionTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-precision', 'Supply Précision')
        self.admin = make_user(self.company, 'scm-precision-admin', 'admin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', prix_vente=15000,
            quantite_stock=200)

    def _periode(self, offset_mois):
        today = timezone.localdate()
        idx = today.year * 12 + (today.month - 1) - offset_mois
        y, m0 = divmod(idx, 12)
        return y, m0 + 1, f'{y:04d}-{m0 + 1:02d}'

    def _seed_mouvement(self, y, m, quantite):
        mvt = MouvementStock.objects.create(
            company=self.company, produit=self.produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=quantite, quantite_avant=1000, quantite_apres=1000 - quantite)
        mvt.date = timezone.make_aware(timezone.datetime(y, m, 15))
        mvt.save(update_fields=['date'])

    def test_prevision_parfaite_donne_un_mape_proche_de_zero(self):
        for offset in (2, 1):
            y, m, periode = self._periode(offset)
            self._seed_mouvement(y, m, 50)
            PrevisionDemande.objects.create(
                company=self.company, produit=self.produit, segment='',
                periode=periode, quantite_prevue=50)

        resultat = precision_prevision(
            self.company, produit=self.produit, fenetre_mois=6)
        self.assertIsNotNone(resultat['mape_global_pct'])
        self.assertLess(resultat['mape_global_pct'], 1.0)
        self.assertEqual(resultat['nb_mois_couverts'], 2)

    def test_prevision_tres_erronee_donne_un_mape_eleve(self):
        y, m, periode = self._periode(1)
        self._seed_mouvement(y, m, 100)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=periode, quantite_prevue=10)

        resultat = precision_prevision(
            self.company, produit=self.produit, fenetre_mois=6)
        self.assertGreater(resultat['mape_global_pct'], 50)

    def test_mois_sans_prevision_prend_zero_comme_reference(self):
        # Aucune PrevisionDemande créée : `quantite_prevue` implicite = 0,
        # écart maximal (100%) — jamais une exception ni un mois ignoré.
        y, m, _periode = self._periode(1)
        self._seed_mouvement(y, m, 40)

        resultat = precision_prevision(
            self.company, produit=self.produit, fenetre_mois=6)
        self.assertEqual(resultat['nb_mois_couverts'], 1)
        self.assertAlmostEqual(resultat['mape_global_pct'], 100.0, places=1)

    def test_endpoint_precision_previsions(self):
        y, m, periode = self._periode(1)
        self._seed_mouvement(y, m, 50)
        PrevisionDemande.objects.create(
            company=self.company, produit=self.produit, segment='',
            periode=periode, quantite_prevue=50)

        resp = auth(self.admin).get('/api/django/scm/precision-previsions/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn('mape_global_pct', resp.data)
