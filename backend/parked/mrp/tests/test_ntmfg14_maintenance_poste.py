"""NTMFG14 — Maintenance préventive des postes de charge (machines/lignes
internes).

Critère : échéances générées depuis le plan, alerte visible sur Gantt +
terminal, clôture d'entretien remet le compteur à zéro."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.mrp.models import (
    EcheanceEntretienPoste, Gamme, OperationGamme, OrdreFabrication,
    PlanEntretienPoste, PosteDeCharge,
)
from apps.mrp.selectors import charge_postes, postes_en_alerte_maintenance
from apps.mrp.services import (
    cloturer_echeance_entretien, confirmer_of, demarrer_operation,
    generer_echeances_entretien, generer_echeances_poste, terminer_operation,
)
from apps.stock.models import Produit

from ._fixtures import make_company, make_user


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def make_produit(company, nom='Produit'):
    return Produit.objects.create(company=company, nom=nom, prix_vente=0, tva=20)


class GenerationEcheancesTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-ent-1', 'MRP Entretien 1')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-ENT', nom='Compresseur')

    def test_generation_par_intervalle_jours_premiere_fois(self):
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Vidange', intervalle_jours=30)
        echeance = generer_echeances_poste(plan)
        self.assertIsNotNone(echeance)
        self.assertEqual(echeance.statut, 'a_faire')

    def test_generation_idempotente_tant_qu_echeance_ouverte(self):
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Vidange', intervalle_jours=30)
        generer_echeances_poste(plan)
        self.assertEqual(plan.echeances.count(), 1)
        generer_echeances_poste(plan)  # Rejoué -> pas de doublon.
        self.assertEqual(plan.echeances.count(), 1)

    def test_generation_par_intervalle_jours_apres_derniere_realisee(self):
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Vidange', intervalle_jours=30)
        today = timezone.localdate()
        ancienne = EcheanceEntretienPoste.objects.create(
            plan=plan, date_prevue=today - timedelta(days=40),
            statut='fait', date_realisee=today - timedelta(days=40))
        # 40 jours après la dernière réalisation (>= 30) -> nouvelle échéance.
        echeance = generer_echeances_poste(plan, today=today)
        self.assertIsNotNone(echeance)
        self.assertNotEqual(echeance.id, ancienne.id)

    def test_pas_de_generation_avant_intervalle(self):
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Vidange', intervalle_jours=30)
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=plan, date_prevue=today - timedelta(days=5),
            statut='fait', date_realisee=today - timedelta(days=5))
        echeance = generer_echeances_poste(plan, today=today)
        self.assertIsNone(echeance)

    def test_generation_par_heures_usage(self):
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Étalonnage', intervalle_heures_usage=Decimal('1'))
        # Fabrique une opération TERMINÉE de 90 min (>= 60 min = 1h) sur CE poste.
        produit = make_produit(self.company)
        gamme = Gamme.objects.create(
            company=self.company, nom='Gamme ent', produit=produit)
        OperationGamme.objects.create(
            gamme=gamme, ordre=1, poste_charge=self.poste, libelle='Op',
            temps_unitaire_min=Decimal('1'))
        of = OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1, gamme=gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()
        demarrer_operation(op)
        op.demarree_le = timezone.now() - timedelta(minutes=90)
        op.save(update_fields=['demarree_le'])
        terminer_operation(op, quantite_bonne=1)

        echeance = generer_echeances_poste(plan)
        self.assertIsNotNone(echeance)

    def test_generer_echeances_entretien_isolation_tenant(self):
        autre_company = make_company('mrp-ent-2', 'MRP Entretien 2')
        PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Vidange', intervalle_jours=1)
        creees = generer_echeances_entretien(autre_company)
        self.assertEqual(creees, [])
        creees = generer_echeances_entretien(self.company)
        self.assertEqual(len(creees), 1)


class AlerteMaintenanceTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-alerte-1', 'MRP Alerte 1')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-ALERTE', nom='Sertisseuse')
        self.plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Contrôle', intervalle_jours=30)

    def test_echeance_en_retard_signalee(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today - timedelta(days=3))
        alertes = postes_en_alerte_maintenance(self.company)
        self.assertIn(self.poste.id, alertes)

    def test_echeance_future_pas_signalee(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today + timedelta(days=3))
        alertes = postes_en_alerte_maintenance(self.company)
        self.assertNotIn(self.poste.id, alertes)

    def test_badge_visible_sur_gantt(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today - timedelta(days=1))
        produit = make_produit(self.company)
        gamme = Gamme.objects.create(
            company=self.company, nom='Gamme alerte', produit=produit)
        OperationGamme.objects.create(
            gamme=gamme, ordre=1, poste_charge=self.poste, libelle='Op',
            temps_unitaire_min=Decimal('1'))
        of = OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1, gamme=gamme)
        confirmer_of(of)
        of.refresh_from_db()
        jour = of.operations.first().date_planifiee
        resultats = charge_postes(self.company, jour, jour)
        self.assertEqual(len(resultats), 1)
        self.assertTrue(resultats[0]['alerte_maintenance'])

    def test_avertissement_sur_terminal_au_demarrage(self):
        today = timezone.localdate()
        EcheanceEntretienPoste.objects.create(
            plan=self.plan, date_prevue=today - timedelta(days=1))
        produit = make_produit(self.company)
        gamme = Gamme.objects.create(
            company=self.company, nom='Gamme term', produit=produit)
        OperationGamme.objects.create(
            gamme=gamme, ordre=1, poste_charge=self.poste, libelle='Op',
            temps_unitaire_min=Decimal('1'))
        of = OrdreFabrication.objects.create(
            company=self.company, produit=produit, quantite=1, gamme=gamme)
        confirmer_of(of)
        of.refresh_from_db()
        op = of.operations.first()

        user = make_user(self.company, 'mrp-alerte-user')
        api = auth(user)
        resp = api.post(f'/api/django/mrp/operations-of/{op.id}/demarrer/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['avertissement_maintenance'])


class ClotureEcheanceTests(TestCase):
    def setUp(self):
        self.company = make_company('mrp-cloture-1', 'MRP Cloture 1')
        self.poste = PosteDeCharge.objects.create(
            company=self.company, code='P-CLOT', nom='Banc de test')

    def test_cloture_remet_compteur_usage_a_zero(self):
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Étalonnage', intervalle_heures_usage=Decimal('1'))
        echeance = EcheanceEntretienPoste.objects.create(
            plan=plan, date_prevue=timezone.localdate())
        self.assertIsNone(self.poste.usage_reinitialise_le)

        cloturer_echeance_entretien(echeance)
        echeance.refresh_from_db()
        self.poste.refresh_from_db()
        self.assertEqual(echeance.statut, 'fait')
        self.assertIsNotNone(echeance.date_realisee)
        self.assertIsNotNone(self.poste.usage_reinitialise_le)

    def test_cloture_sans_intervalle_usage_ne_touche_pas_compteur(self):
        plan = PlanEntretienPoste.objects.create(
            company=self.company, poste_charge=self.poste,
            description='Contrôle visuel', intervalle_jours=7)
        echeance = EcheanceEntretienPoste.objects.create(
            plan=plan, date_prevue=timezone.localdate())
        cloturer_echeance_entretien(echeance)
        self.poste.refresh_from_db()
        self.assertIsNone(self.poste.usage_reinitialise_le)
