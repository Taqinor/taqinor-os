"""Tests NTSUB round 3 — relevé d'abonnement, rattachement de plan, réglages.

NTSUB20 : relevé d'abonnement imprimable (échéances, add-ons, compteurs
d'usage, paiements) — état RÉCAPITULATIF, jamais un devis (rule #4).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.contrats import selectors
from apps.contrats.models import (
    AbonnementAddOnLigne,
    AddOnAbonnement,
    CompteurUsage,
    Contrat,
    EcheancierContrat,
    LigneEcheance,
)

User = get_user_model()


def make_company(slug, nom=None):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom or slug})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ReleveAbonnementTests(TestCase):
    """NTSUB20 — le relevé liste EXACTEMENT la période demandée."""

    def setUp(self):
        self.co = make_company('ntsub20', 'NTSUB20 Co')
        self.user = User.objects.create_user(
            username='ntsub20-user', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.user)
        self.contrat = Contrat.objects.create(
            company=self.co, reference='CTR-2026-001',
            objet='Abonnement supervision', montant=Decimal('1200'),
            type_contrat='om', statut='actif')
        self.echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=self.contrat, libelle='Plan mensuel',
            periodicite=EcheancierContrat.Periodicite.MENSUELLE)

    def _echeance(self, numero, jour, montant, statut=None):
        return LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=numero,
            libelle=f'Échéance {numero}', date_echeance=jour,
            montant=Decimal(montant),
            statut=statut or LigneEcheance.Statut.A_VENIR)

    def test_seules_les_echeances_de_la_periode_sont_listees(self):
        self._echeance(1, date(2026, 1, 15), '100')
        self._echeance(2, date(2026, 2, 15), '200')
        self._echeance(3, date(2026, 3, 15), '300')
        releve = selectors.releve_abonnement(
            self.contrat, date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(len(releve['echeances']), 1)
        self.assertEqual(releve['echeances'][0]['numero'], 2)
        self.assertEqual(releve['total_echeances'], Decimal('200'))

    def test_addons_actifs_sur_la_periode_avec_leur_montant(self):
        addon = AddOnAbonnement.objects.create(
            company=self.co, code='SUP-AV', nom='Supervision avancée',
            prix_unitaire=Decimal('150'))
        AbonnementAddOnLigne.objects.create(
            company=self.co,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=self.contrat.id, addon=addon, quantite=2,
            actif_depuis=date(2026, 1, 1))
        # Add-on TERMINÉ avant la période : exclu.
        ancien = AddOnAbonnement.objects.create(
            company=self.co, code='OLD', nom='Ancienne option',
            prix_unitaire=Decimal('50'))
        AbonnementAddOnLigne.objects.create(
            company=self.co,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=self.contrat.id, addon=ancien, quantite=1,
            actif_depuis=date(2025, 1, 1), actif_jusqua=date(2025, 12, 31))
        releve = selectors.releve_abonnement(
            self.contrat, date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(len(releve['addons']), 1)
        self.assertEqual(releve['addons'][0]['addon'], 'Supervision avancée')
        self.assertEqual(releve['total_addons'], Decimal('300'))

    def test_compteurs_d_usage_de_la_periode(self):
        CompteurUsage.objects.create(
            company=self.co,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=self.contrat.id, code_compteur='interventions',
            periode_debut=date(2026, 2, 1), periode_fin=date(2026, 2, 28),
            quantite=Decimal('7'))
        CompteurUsage.objects.create(
            company=self.co,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=self.contrat.id, code_compteur='interventions',
            periode_debut=date(2026, 5, 1), periode_fin=date(2026, 5, 31),
            quantite=Decimal('3'))
        releve = selectors.releve_abonnement(
            self.contrat, date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(len(releve['compteurs']), 1)
        self.assertEqual(releve['compteurs'][0]['quantite'], Decimal('7'))

    def test_paiements_lus_via_le_selecteur_ventes(self):
        from apps.crm.models import Client
        from apps.ventes.models import Facture, Paiement

        client = Client.objects.create(
            company=self.co, nom='Client', prenom='NTSUB20',
            telephone='+212600000020')
        facture = Facture.objects.create(
            company=self.co, client=client, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20'), montant_ttc=Decimal('200'),
            date_echeance=date(2026, 2, 15))
        ligne = self._echeance(2, date(2026, 2, 15), '200')
        ligne.facture_id = facture.id
        ligne.save(update_fields=['facture_id'])
        Paiement.objects.create(
            company=self.co, facture=facture, montant=Decimal('120'),
            date_paiement=date(2026, 2, 20), mode='virement')
        # Paiement HORS période : jamais compté.
        Paiement.objects.create(
            company=self.co, facture=facture, montant=Decimal('80'),
            date_paiement=date(2026, 4, 2), mode='virement')

        releve = selectors.releve_abonnement(
            self.contrat, date(2026, 2, 1), date(2026, 2, 28))
        self.assertEqual(len(releve['paiements']), 1)
        self.assertEqual(releve['total_paiements'], Decimal('120'))

    def test_html_du_releve_n_est_ni_un_devis_ni_une_facture(self):
        from apps.contrats.pdf_location import render_releve_abonnement_html

        self._echeance(1, date(2026, 2, 15), '200')
        releve = selectors.releve_abonnement(
            self.contrat, date(2026, 2, 1), date(2026, 2, 28))
        html = render_releve_abonnement_html(self.contrat, releve)
        self.assertIn("RELEVÉ D'ABONNEMENT", html)
        self.assertIn('CTR-2026-001', html)
        self.assertIn('Échéances de la période', html)
        # Rien qui puisse le confondre avec le moteur de devis premium.
        self.assertNotIn('proposal', html.lower())
        # …et le document le DIT explicitement au lecteur.
        self.assertIn('ne vaut ni devis, ni facture', html)

    def test_endpoint_releve_pdf_ou_503_et_scope_societe(self):
        self._echeance(1, date(2026, 2, 15), '200')
        resp = self.api.get(
            f'/api/django/contrats/contrats/{self.contrat.id}/releve-pdf/'
            '?debut=2026-02-01&fin=2026-02-28')
        self.assertIn(resp.status_code, (200, 503))
        if resp.status_code == 200:
            self.assertEqual(resp['Content-Type'], 'application/pdf')

        autre = make_company('ntsub20-b', 'NTSUB20 B')
        user_b = User.objects.create_user(
            username='ntsub20-user-b', password='x', company=autre,
            role_legacy='admin')
        cross = auth(user_b).get(
            f'/api/django/contrats/contrats/{self.contrat.id}/releve-pdf/')
        self.assertEqual(cross.status_code, 404)

    def test_periode_invalide_refusee_en_francais(self):
        resp = self.api.get(
            f'/api/django/contrats/contrats/{self.contrat.id}/releve-pdf/'
            '?debut=pas-une-date')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('AAAA-MM-JJ', resp.data['detail'])


class RattacherPlanRetroactifTests(TestCase):
    """NTSUB23 — rattachement rétroactif : classement seul vs prix appliqué."""

    def setUp(self):
        from apps.contrats.models import PlanAbonnement

        self.co = make_company('ntsub23', 'NTSUB23 Co')
        self.user = User.objects.create_user(
            username='ntsub23-user', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.user)
        self.contrat = Contrat.objects.create(
            company=self.co, reference='CTR-OLD-1',
            objet='Contrat antérieur au catalogue', montant=Decimal('1000'),
            type_contrat='om', statut='actif')
        self.plan = PlanAbonnement.objects.create(
            company=self.co, code='PREMIUM', nom='Offre Premium',
            prix_base=Decimal('1500'))

    def test_sans_appliquer_le_prix_aucun_montant_ne_bouge(self):
        from apps.contrats import services
        from apps.contrats.models import Avenant

        resultat = services.rattacher_plan_retroactif(
            self.contrat, self.plan, False, auteur=self.user)
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.plan_abonnement_id, self.plan.id)
        self.assertEqual(self.contrat.montant, Decimal('1000'))
        self.assertFalse(resultat['prix_applique'])
        self.assertIsNone(resultat['avenant'])
        self.assertEqual(resultat['delta'], Decimal('500'))
        self.assertFalse(
            Avenant.objects.filter(contrat=self.contrat).exists())

    def test_appliquer_le_prix_cree_un_avenant_et_change_le_montant(self):
        from apps.contrats import services
        from apps.contrats.models import Avenant

        resultat = services.rattacher_plan_retroactif(
            self.contrat, self.plan, True, auteur=self.user)
        self.contrat.refresh_from_db()
        self.assertTrue(resultat['prix_applique'])
        self.assertEqual(self.contrat.montant, Decimal('1500'))
        self.assertEqual(self.contrat.plan_abonnement_id, self.plan.id)
        avenant = Avenant.objects.get(contrat=self.contrat)
        self.assertEqual(avenant.montant_delta, Decimal('500'))

    def test_plan_d_une_autre_societe_refuse(self):
        from apps.contrats import services
        from apps.contrats.models import PlanAbonnement

        autre = make_company('ntsub23-b', 'NTSUB23 B')
        plan_b = PlanAbonnement.objects.create(
            company=autre, code='AUTRE', nom='Offre B',
            prix_base=Decimal('900'))
        with self.assertRaises(services.ChangementPlanError):
            services.rattacher_plan_retroactif(self.contrat, plan_b, False)
        self.contrat.refresh_from_db()
        self.assertIsNone(self.contrat.plan_abonnement_id)

    def test_endpoint_par_defaut_ne_touche_pas_au_montant(self):
        resp = self.api.post(
            f'/api/django/contrats/contrats/{self.contrat.id}/rattacher-plan/',
            {'plan': self.plan.id}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['prix_applique'])
        self.assertEqual(resp.data['delta'], Decimal('500'))
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal('1000'))

    def test_endpoint_avec_appliquer_prix(self):
        resp = self.api.post(
            f'/api/django/contrats/contrats/{self.contrat.id}/rattacher-plan/',
            {'plan': self.plan.id, 'appliquer_prix': True}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['prix_applique'])
        self.assertIsNotNone(resp.data['avenant'])
        self.contrat.refresh_from_db()
        self.assertEqual(self.contrat.montant, Decimal('1500'))

    def test_endpoint_nomme_le_champ_manquant(self):
        resp = self.api.post(
            f'/api/django/contrats/contrats/{self.contrat.id}/rattacher-plan/',
            {}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('plan', resp.data)

    def test_endpoint_refuse_un_plan_hors_societe(self):
        from apps.contrats.models import PlanAbonnement

        autre = make_company('ntsub23-c', 'NTSUB23 C')
        plan_c = PlanAbonnement.objects.create(
            company=autre, code='HORS', nom='Offre hors société',
            prix_base=Decimal('10'))
        resp = self.api.post(
            f'/api/django/contrats/contrats/{self.contrat.id}/rattacher-plan/',
            {'plan': plan_c.id}, format='json')
        self.assertEqual(resp.status_code, 404)
