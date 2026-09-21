"""NTSCM3 — Événements de demande (promotions, chantiers planifiés, ruptures
fournisseur connues).

Critère d'acceptation : un événement +50% sur un mois donné augmente la
``quantite_prevue`` du mois correspondant de 50% par rapport à la prévision
sans événement, vérifié par test.

``MouvementStock``/``Produit`` créés directement via ``apps.stock.models``
UNIQUEMENT pour construire la fixture de test (frontière cross-app,
CLAUDE.md — voir ``test_ntscm2_demand_forecast.py``)."""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.scm.models import EvenementDemande
from apps.scm.services import generer_previsions
from apps.stock.models import Categorie, MouvementStock, Produit

from .helpers import make_company

MONTHLY_FACTOR = [0.5, 0.5, 0.7, 0.9, 1.0, 1.4, 1.8, 1.7, 1.1, 0.8, 0.6, 0.5]
BASE_LEVEL = 100


def _seed_24_months_ending_last_month(company, produit):
    today = timezone.localdate()
    idx_dernier = today.year * 12 + (today.month - 1) - 1
    qty_restante = 10000
    for offset in range(23, -1, -1):
        idx = idx_dernier - offset
        y, m0 = divmod(idx, 12)
        qty = int(BASE_LEVEL * MONTHLY_FACTOR[m0])
        mvt = MouvementStock.objects.create(
            company=company, produit=produit,
            type_mouvement=MouvementStock.TypeMouvement.SORTIE,
            quantite=qty, quantite_avant=qty_restante,
            quantite_apres=qty_restante - qty)
        qty_restante -= qty
        mvt.date = timezone.make_aware(timezone.datetime(y, m0 + 1, 15))
        mvt.save(update_fields=['date'])


class EvenementDemandeImpactTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-evt', 'Supply Événements')
        self.categorie = Categorie.objects.create(
            company=self.company, nom='Batteries')
        self.produit = Produit.objects.create(
            company=self.company, nom='Batterie 5kWh', prix_vente=15000,
            quantite_stock=200, categorie=self.categorie)
        _seed_24_months_ending_last_month(self.company, self.produit)

    def _baseline_par_periode(self):
        baseline = generer_previsions(self.produit, 3, self.company)
        return {p.periode: p.quantite_prevue for p in baseline}

    def test_event_plus_50_pct_increases_target_month_by_50_pct(self):
        baseline = self._baseline_par_periode()
        periode_cible = sorted(baseline)[0]
        periode_hors_fenetre = sorted(baseline)[1]
        quantite_sans_evenement = baseline[periode_cible]
        self.assertGreater(quantite_sans_evenement, 0)

        y, m = int(periode_cible[:4]), int(periode_cible[5:7])
        EvenementDemande.objects.create(
            company=self.company, produit=self.produit,
            date_debut=f'{y:04d}-{m:02d}-01', date_fin=f'{y:04d}-{m:02d}-28',
            impact_pct=Decimal('50'), libelle='Promotion test',
            type_evenement=EvenementDemande.TypeEvenement.PROMOTION,
        )

        avec_evenement = {
            p.periode: p.quantite_prevue
            for p in generer_previsions(self.produit, 3, self.company)
        }
        attendu = (quantite_sans_evenement * Decimal('1.5')).quantize(Decimal('0.01'))
        self.assertEqual(avec_evenement[periode_cible], attendu)

        # Un mois HORS fenêtre événement reste STRICTEMENT inchangé.
        self.assertEqual(
            avec_evenement[periode_hors_fenetre], baseline[periode_hors_fenetre])

    def test_rupture_event_zeroes_out_the_month(self):
        periode_cible = sorted(self._baseline_par_periode())[0]
        y, m = int(periode_cible[:4]), int(periode_cible[5:7])
        EvenementDemande.objects.create(
            company=self.company, produit=self.produit,
            date_debut=f'{y:04d}-{m:02d}-01', date_fin=f'{y:04d}-{m:02d}-28',
            impact_pct=Decimal('-100'), libelle='Rupture fournisseur connue',
            type_evenement=EvenementDemande.TypeEvenement.RUPTURE_FOURNISSEUR,
        )
        previsions = generer_previsions(self.produit, 3, self.company)
        row = next(p for p in previsions if p.periode == periode_cible)
        self.assertEqual(row.quantite_prevue, Decimal('0.00'))

    def test_category_wide_event_applies_without_explicit_produit(self):
        baseline = self._baseline_par_periode()
        periode_cible = sorted(baseline)[0]
        quantite_sans_evenement = baseline[periode_cible]
        y, m = int(periode_cible[:4]), int(periode_cible[5:7])
        EvenementDemande.objects.create(
            company=self.company, produit=None, categorie=self.produit.categorie,
            date_debut=f'{y:04d}-{m:02d}-01', date_fin=f'{y:04d}-{m:02d}-28',
            impact_pct=Decimal('20'), libelle='Chantier majeur région',
            type_evenement=EvenementDemande.TypeEvenement.CHANTIER_MAJEUR,
        )
        previsions = generer_previsions(self.produit, 3, self.company)
        row = next(p for p in previsions if p.periode == periode_cible)
        attendu = (quantite_sans_evenement * Decimal('1.2')).quantize(Decimal('0.01'))
        self.assertEqual(row.quantite_prevue, attendu)

    def test_evenement_demande_endpoint_crud(self):
        from .helpers import auth, make_user

        admin = make_user(self.company, 'scm-evt-admin', 'admin')
        api = auth(admin)
        resp = api.post('/api/django/scm/evenements-demande/', {
            'produit': self.produit.id, 'date_debut': '2026-06-01',
            'date_fin': '2026-08-31', 'impact_pct': '30',
            'libelle': 'Été fort', 'type_evenement': 'saisonnalite_locale',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            EvenementDemande.objects.filter(company=self.company).count(), 1)

    def test_evenement_demande_rejects_date_fin_before_date_debut(self):
        with self.assertRaises(ValueError):
            EvenementDemande.objects.create(
                company=self.company, produit=self.produit,
                date_debut='2026-06-10', date_fin='2026-06-01',
                impact_pct=Decimal('10'), libelle='Invalide',
            )
