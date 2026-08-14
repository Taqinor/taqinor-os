"""NTWMS13 — comptage tournant ABC récurrent (cycle counting).

Critère d'acceptation testé : les produits de classe A sont recomptés au moins
tous les 30 jours SANS intervention manuelle — une session d'inventaire ciblée
est proposée automatiquement dès que la date est due.

Toutes les dates sont FIXES et injectées (`aujourd_hui=`, `depuis=`) : la suite
ne lit jamais l'horloge, donc ne bascule pas à minuit.

Run :
    python manage.py test apps.stock.test_ntwms13_comptage_tournant -v 2
"""
import datetime
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.stock.models import (
    InventaireSession, MouvementStock, PlanComptageTournant, Produit,
)
from apps.stock.selectors import classe_abc_produit, classes_abc_produits
from apps.stock.services import (
    assurer_plans_comptage_tournant, generer_comptages_tournants,
)

User = get_user_model()

AUJOURD_HUI = datetime.date(2026, 6, 15)
DEBUT_FENETRE = AUJOURD_HUI - datetime.timedelta(days=365)


def make_company(slug, nom):
    from authentication.models import Company
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class Ntwms13Base(TestCase):
    def setUp(self):
        self.company = make_company('ntwms13-co', 'NTWMS13 Co')
        self.autre = make_company('ntwms13-autre', 'NTWMS13 Autre')
        self.admin = User.objects.create_user(
            username='ntwms13_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)

    def _produit(self, nom, sku, prix_achat, sorties=0):
        """Produit + (optionnel) une SORTIE horodatée à une date FIXE.

        ``MouvementStock.date`` est ``auto_now_add`` : sans ce forçage, le
        mouvement porterait la date RÉELLE du run et sortirait de la fenêtre
        d'analyse fixe des tests (rouge un jour, vert le lendemain)."""
        from django.utils import timezone

        produit = Produit.objects.create(
            company=self.company, nom=nom, sku=sku,
            prix_achat=Decimal(str(prix_achat)),
            prix_vente=Decimal(str(prix_achat)) * 2, quantite_stock=100)
        if sorties:
            mouvement = MouvementStock.objects.create(
                company=self.company, produit=produit,
                type_mouvement=MouvementStock.TypeMouvement.SORTIE,
                quantite=sorties, quantite_avant=100,
                quantite_apres=100 - sorties, reference='NTWMS13')
            MouvementStock.objects.filter(pk=mouvement.pk).update(
                date=timezone.make_aware(
                    datetime.datetime(2026, 6, 1, 10, 0),
                    timezone.get_default_timezone()))
        return produit


class TestClassificationAbc(Ntwms13Base):
    def setUp(self):
        super().setUp()
        # Valeurs de rotation : 8000 / 1500 / 400 / 100 (total 10 000).
        # Pareto : le 1er couvre 80 % → A ; le 2e démarre à 80 % → C.
        self.gros = self._produit('Onduleur', 'OND-NTWMS13', 800, sorties=10)
        self.moyen = self._produit('Panneau', 'PAN-NTWMS13', 150, sorties=10)
        self.petit = self._produit('Câble', 'CAB-NTWMS13', 40, sorties=10)
        self.dormant = self._produit('Vis', 'VIS-NTWMS13', 10, sorties=0)

    def test_le_plus_gros_rotateur_est_classe_a(self):
        classes = classes_abc_produits(
            self.company, depuis=DEBUT_FENETRE, jusqu_a=AUJOURD_HUI)
        self.assertEqual(classes[self.gros.id], 'A')

    def test_produit_sans_sortie_est_classe_c(self):
        classes = classes_abc_produits(
            self.company, depuis=DEBUT_FENETRE, jusqu_a=AUJOURD_HUI)
        self.assertEqual(classes[self.dormant.id], 'C')

    def test_selecteur_unitaire(self):
        self.assertEqual(
            classe_abc_produit(self.gros, depuis=DEBUT_FENETRE,
                               jusqu_a=AUJOURD_HUI), 'A')

    def test_repartition_pareto_complete(self):
        """Sur une rotation ÉTALÉE, on retrouve bien les trois classes."""
        for index in range(10):
            self._produit(f'Article {index}', f'ART{index}-NTWMS13',
                          100, sorties=10)
        classes = classes_abc_produits(
            self.company, depuis=DEBUT_FENETRE, jusqu_a=AUJOURD_HUI)
        self.assertIn('A', classes.values())
        self.assertIn('B', classes.values())
        self.assertIn('C', classes.values())

    def test_societe_sans_rotation_tout_en_c(self):
        Produit.objects.create(
            company=self.autre, nom='Rien', sku='RIEN-NTWMS13',
            prix_achat=Decimal('5'), prix_vente=Decimal('9'))
        classes = classes_abc_produits(
            self.autre, depuis=DEBUT_FENETRE, jusqu_a=AUJOURD_HUI)
        self.assertEqual(set(classes.values()), {'C'})

    def test_isolation_societe(self):
        classes = classes_abc_produits(
            self.autre, depuis=DEBUT_FENETRE, jusqu_a=AUJOURD_HUI)
        self.assertNotIn(self.gros.id, classes)

    def test_endpoint_classe_abc(self):
        resp = self.api.get(
            f'/api/django/stock/produits/{self.gros.id}/classe-abc/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(resp.data['classe_abc'], ['A', 'B', 'C'])


class TestPlansEtGeneration(Ntwms13Base):
    def setUp(self):
        super().setUp()
        self.gros = self._produit('Onduleur', 'OND-NTWMS13', 800, sorties=10)
        self.plans = {
            plan.classe_abc: plan
            for plan in assurer_plans_comptage_tournant(self.company)
        }

    def test_plans_par_defaut_idempotents(self):
        assurer_plans_comptage_tournant(self.company)
        self.assertEqual(
            PlanComptageTournant.objects.filter(company=self.company).count(),
            3)
        self.assertEqual(self.plans['A'].frequence_jours, 30)
        self.assertEqual(self.plans['B'].frequence_jours, 90)
        self.assertEqual(self.plans['C'].frequence_jours, 180)

    def test_amorcage_n_ecrase_pas_une_frequence_personnalisee(self):
        self.plans['A'].frequence_jours = 7
        self.plans['A'].save(update_fields=['frequence_jours'])
        assurer_plans_comptage_tournant(self.company)
        self.plans['A'].refresh_from_db()
        self.assertEqual(self.plans['A'].frequence_jours, 7)

    def test_premiere_generation_cree_une_session_par_classe_peuplee(self):
        resultat = generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        self.assertEqual(resultat['plans_dus'], 3)
        self.assertTrue(resultat['sessions'])
        session = InventaireSession.objects.filter(
            company=self.company).first()
        self.assertEqual(session.statut, InventaireSession.Statut.BROUILLON)
        self.assertIn('Comptage tournant', session.motif)

    def test_lignes_pre_remplies_au_theorique(self):
        generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        ligne = InventaireSession.objects.filter(
            company=self.company).first().lignes.first()
        self.assertEqual(ligne.quantite_comptee, ligne.quantite_theorique)
        self.assertEqual(ligne.ecart, 0)

    def test_generation_idempotente_le_meme_jour(self):
        generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        nb = InventaireSession.objects.filter(company=self.company).count()
        second = generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        self.assertEqual(second['sessions'], [])
        self.assertEqual(
            InventaireSession.objects.filter(company=self.company).count(), nb)

    def test_classe_a_recomptee_au_bout_de_30_jours(self):
        """Le cœur du critère : à J+30, la classe A est de nouveau due — sans
        intervention manuelle."""
        generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        plan_a = PlanComptageTournant.objects.get(
            company=self.company, classe_abc='A')
        self.assertEqual(plan_a.date_dernier_comptage, AUJOURD_HUI)
        self.assertFalse(plan_a.est_du(AUJOURD_HUI + datetime.timedelta(29)))
        self.assertTrue(plan_a.est_du(AUJOURD_HUI + datetime.timedelta(30)))

        resultat = generer_comptages_tournants(
            company=self.company,
            aujourd_hui=AUJOURD_HUI + datetime.timedelta(days=30))
        self.assertTrue(resultat['sessions'])

    def test_plan_inactif_jamais_declenche(self):
        for plan in PlanComptageTournant.objects.filter(company=self.company):
            plan.actif = False
            plan.save(update_fields=['actif'])
        resultat = generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        self.assertEqual(resultat['plans_dus'], 0)
        self.assertEqual(resultat['sessions'], [])

    def test_autre_societe_non_touchee(self):
        assurer_plans_comptage_tournant(self.autre)
        generer_comptages_tournants(
            company=self.company, aujourd_hui=AUJOURD_HUI)
        self.assertEqual(
            InventaireSession.objects.filter(company=self.autre).count(), 0)

    def test_endpoint_generer(self):
        resp = self.api.post(
            '/api/django/stock/plans-comptage-tournant/generer/', {},
            format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertIn('sessions', resp.data)

    def test_endpoint_liste_amorce_les_plans(self):
        PlanComptageTournant.objects.filter(company=self.company).delete()
        resp = self.api.get('/api/django/stock/plans-comptage-tournant/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            PlanComptageTournant.objects.filter(company=self.company).count(),
            3)


class TestCommandeComptage(Ntwms13Base):
    """La commande lit l'horloge réelle (c'est son rôle en production). Ces
    tests utilisent donc UNIQUEMENT des produits SANS rotation — toujours
    classés C, quelle que soit la date du run : aucune dépendance à la date."""

    def test_commande_cree_les_plans_puis_genere(self):
        self._produit('Onduleur', 'OND-NTWMS13', 800)
        sortie = StringIO()
        call_command('generer_comptages_tournants', '--creer-plans',
                     '--company', str(self.company.id), stdout=sortie)
        self.assertIn('Plans A/B/C assurés', sortie.getvalue())
        self.assertEqual(
            PlanComptageTournant.objects.filter(company=self.company).count(),
            3)
        self.assertTrue(
            InventaireSession.objects.filter(company=self.company).exists())

    def test_commande_idempotente(self):
        self._produit('Onduleur', 'OND-NTWMS13', 800)
        call_command('generer_comptages_tournants', '--creer-plans',
                     '--company', str(self.company.id), stdout=StringIO())
        nb = InventaireSession.objects.filter(company=self.company).count()
        call_command('generer_comptages_tournants',
                     '--company', str(self.company.id), stdout=StringIO())
        self.assertEqual(
            InventaireSession.objects.filter(company=self.company).count(), nb)
