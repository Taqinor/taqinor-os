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
