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


def make_plan_recurrent(company, nom='Mensuel'):
    """Cadence ZCTR1 — OBLIGATOIRE sur ``PlanAbonnement.plan_recurrent``
    (FK non nullable) : une offre du catalogue porte toujours sa cadence de
    facturation. Même fabrique que ``test_ntsub1_4_catalogue_paliers``."""
    from apps.contrats.models import PlanRecurrent

    return PlanRecurrent.objects.create(
        company=company, nom=nom, unite=PlanRecurrent.Unite.MENSUEL,
        intervalle=1)


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
            plan_recurrent=make_plan_recurrent(self.co, nom='Plan-PREMIUM'),
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
            plan_recurrent=make_plan_recurrent(autre, nom='Plan-AUTRE'),
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
            plan_recurrent=make_plan_recurrent(autre, nom='Plan-HORS'),
            prix_base=Decimal('10'))
        resp = self.api.post(
            f'/api/django/contrats/contrats/{self.contrat.id}/rattacher-plan/',
            {'plan': plan_c.id}, format='json')
        self.assertEqual(resp.status_code, 404)


class ParametresAbonnementTests(TestCase):
    """NTSUB24 — réglages par société : défauts = comportement historique."""

    def setUp(self):
        self.co = make_company('ntsub24', 'NTSUB24 Co')
        self.user = User.objects.create_user(
            username='ntsub24-user', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.user)

    def test_valeurs_par_defaut_egalent_les_constantes_historiques(self):
        from apps.contrats import services

        params = services.get_parametres_abonnement(self.co)
        self.assertEqual(params.jours_alerte_fin_essai, 3)
        self.assertEqual(params.jours_alerte_expiration_carte, 30)
        self.assertEqual(params.seuil_alerte_usage_pct_defaut, 80)
        self.assertIsNone(params.sequence_dunning_defaut_id)

    def test_singleton_cree_paresseusement_une_seule_fois(self):
        from apps.contrats import services
        from apps.contrats.models import ParametresAbonnement

        premier = services.get_parametres_abonnement(self.co)
        second = services.get_parametres_abonnement(self.co)
        self.assertEqual(premier.pk, second.pk)
        self.assertEqual(
            ParametresAbonnement.objects.filter(company=self.co).count(), 1)

    def test_le_delai_regle_change_bien_le_declenchement_ntsub5(self):
        from datetime import timedelta

        from apps.contrats import services
        from apps.contrats.models import (
            AbonnementAddOnLigne, EssaiAbonnement)

        today = date(2026, 6, 1)
        contrat = Contrat.objects.create(
            company=self.co, objet='Contrat en essai', montant=Decimal('500'),
            type_contrat='om', statut='actif')
        essai = EssaiAbonnement.objects.create(
            company=self.co,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat.id,
            date_fin_essai=today + timedelta(days=7))

        # Réglage par DÉFAUT (J-3) : rien ne se déclenche à J-7.
        res = services.convertir_essais_expires(self.co, today=today)
        self.assertEqual(res['alertes_j3'], 0)
        essai.refresh_from_db()
        self.assertFalse(essai.notifie_j3)

        # Réglage porté à 7 jours : l'alerte part le même jour.
        params = services.get_parametres_abonnement(self.co)
        params.jours_alerte_fin_essai = 7
        params.save(update_fields=['jours_alerte_fin_essai'])
        res2 = services.convertir_essais_expires(self.co, today=today)
        self.assertEqual(res2['alertes_j3'], 1)
        essai.refresh_from_db()
        self.assertTrue(essai.notifie_j3)

    def test_endpoint_courant_get_puis_patch(self):
        get = self.api.get(
            '/api/django/contrats/parametres-abonnement/courant/')
        self.assertEqual(get.status_code, 200)
        self.assertEqual(get.data['jours_alerte_fin_essai'], 3)

        patch = self.api.patch(
            '/api/django/contrats/parametres-abonnement/courant/',
            {'jours_alerte_fin_essai': 10}, format='json')
        self.assertEqual(patch.status_code, 200)
        self.assertEqual(patch.data['jours_alerte_fin_essai'], 10)

    def test_seuil_d_usage_hors_bornes_refuse_en_nommant_le_champ(self):
        resp = self.api.patch(
            '/api/django/contrats/parametres-abonnement/courant/',
            {'seuil_alerte_usage_pct_defaut': 250}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('seuil_alerte_usage_pct_defaut', resp.data)

    def test_isolation_multi_tenant_des_reglages(self):
        from apps.contrats import services

        autre = make_company('ntsub24-b', 'NTSUB24 B')
        user_b = User.objects.create_user(
            username='ntsub24-user-b', password='x', company=autre,
            role_legacy='admin')
        params_a = services.get_parametres_abonnement(self.co)
        params_a.jours_alerte_fin_essai = 15
        params_a.save(update_fields=['jours_alerte_fin_essai'])

        resp_b = auth(user_b).get(
            '/api/django/contrats/parametres-abonnement/courant/')
        self.assertEqual(resp_b.status_code, 200)
        # La société B garde le DÉFAUT, jamais le réglage de A.
        self.assertEqual(resp_b.data['jours_alerte_fin_essai'], 3)
        self.assertNotEqual(resp_b.data['id'], params_a.id)

    def test_sequence_dunning_d_une_autre_societe_refusee(self):
        from apps.contrats.models import SequenceDunning

        autre = make_company('ntsub24-c', 'NTSUB24 C')
        sequence_c = SequenceDunning.objects.create(
            company=autre, nom='Séquence hors société')
        resp = self.api.patch(
            '/api/django/contrats/parametres-abonnement/courant/',
            {'sequence_dunning_defaut': sequence_c.id}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('sequence_dunning_defaut', resp.data)


class PurgeCompteursUsageTests(TestCase):
    """NTSUB26 — purge : seulement ANCIEN **et** FACTURÉ, agrégat exact."""

    AUJOURDHUI = date(2026, 6, 15)

    def setUp(self):
        self.co = make_company('ntsub26', 'NTSUB26 Co')
        self.contrat = Contrat.objects.create(
            company=self.co, objet='Abonnement télémétrie',
            montant=Decimal('500'), type_contrat='om', statut='actif')
        self.echeancier = EcheancierContrat.objects.create(
            company=self.co, contrat=self.contrat,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE)
        self.numero = 0

    def _compteur(self, debut, fin, quantite, code='api'):
        return CompteurUsage.objects.create(
            company=self.co,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=self.contrat.id, code_compteur=code,
            periode_debut=debut, periode_fin=fin,
            quantite=Decimal(quantite))

    def _facturer(self, jour):
        """Échéance FACTURÉE couvrant ``jour`` (facture_id renseigné)."""
        self.numero += 1
        return LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=self.numero,
            date_echeance=jour, montant=Decimal('500'),
            facture_id=1000 + self.numero)

    def test_agregat_egal_a_la_somme_des_lignes_purgees(self):
        from apps.contrats import services
        from apps.contrats.models import CompteurUsageArchive

        # Deux relevés du même mois (janvier 2024), facturés, > 24 mois.
        self._compteur(date(2024, 1, 1), date(2024, 1, 15), '120')
        self._compteur(date(2024, 1, 16), date(2024, 1, 31), '80')
        self._facturer(date(2024, 1, 10))
        self._facturer(date(2024, 1, 20))

        res = services.purger_compteurs_usage_factures(
            self.co, today=self.AUJOURDHUI)
        self.assertEqual(res['lignes_purgees'], 2)
        self.assertEqual(res['archives'], 1)
        archive = CompteurUsageArchive.objects.get(
            company=self.co, code_compteur='api', periode='2024-01')
        self.assertEqual(archive.quantite_totale, Decimal('200'))
        self.assertEqual(archive.nb_lignes, 2)
        self.assertEqual(
            CompteurUsage.objects.filter(company=self.co).count(), 0)

    def test_periode_non_facturee_jamais_purgee(self):
        from apps.contrats import services
        from apps.contrats.models import CompteurUsageArchive

        self._compteur(date(2024, 2, 1), date(2024, 2, 29), '500')
        # Une échéance existe mais n'est NI facturée NI payée.
        self.numero += 1
        LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=self.numero,
            date_echeance=date(2024, 2, 10), montant=Decimal('500'))

        res = services.purger_compteurs_usage_factures(
            self.co, today=self.AUJOURDHUI)
        self.assertEqual(res['lignes_purgees'], 0)
        self.assertFalse(CompteurUsageArchive.objects.exists())
        self.assertEqual(
            CompteurUsage.objects.filter(company=self.co).count(), 1)

    def test_periode_recente_jamais_purgee_meme_facturee(self):
        from apps.contrats import services

        self._compteur(date(2026, 3, 1), date(2026, 3, 31), '42')
        self._facturer(date(2026, 3, 10))
        res = services.purger_compteurs_usage_factures(
            self.co, today=self.AUJOURDHUI)
        self.assertEqual(res['lignes_purgees'], 0)
        self.assertEqual(
            CompteurUsage.objects.filter(company=self.co).count(), 1)

    def test_echeance_payee_compte_comme_facturee(self):
        from apps.contrats import services

        self._compteur(date(2024, 3, 1), date(2024, 3, 31), '15')
        self.numero += 1
        LigneEcheance.objects.create(
            company=self.co, echeancier=self.echeancier, numero=self.numero,
            date_echeance=date(2024, 3, 5), montant=Decimal('500'),
            statut=LigneEcheance.Statut.PAYEE)
        res = services.purger_compteurs_usage_factures(
            self.co, today=self.AUJOURDHUI)
        self.assertEqual(res['lignes_purgees'], 1)

    def test_rejouer_la_purge_ne_double_pas_l_agregat(self):
        from apps.contrats import services
        from apps.contrats.models import CompteurUsageArchive

        self._compteur(date(2024, 1, 1), date(2024, 1, 31), '90')
        self._facturer(date(2024, 1, 10))
        services.purger_compteurs_usage_factures(
            self.co, today=self.AUJOURDHUI)
        services.purger_compteurs_usage_factures(
            self.co, today=self.AUJOURDHUI)
        archive = CompteurUsageArchive.objects.get(company=self.co)
        self.assertEqual(archive.quantite_totale, Decimal('90'))
        self.assertEqual(archive.nb_lignes, 1)

    def test_isolation_societe(self):
        from apps.contrats import services
        from apps.contrats.models import CompteurUsageArchive

        autre = make_company('ntsub26-b', 'NTSUB26 B')
        contrat_b = Contrat.objects.create(
            company=autre, objet='Autre', montant=Decimal('100'),
            type_contrat='om', statut='actif')
        ech_b = EcheancierContrat.objects.create(
            company=autre, contrat=contrat_b,
            periodicite=EcheancierContrat.Periodicite.MENSUELLE)
        LigneEcheance.objects.create(
            company=autre, echeancier=ech_b, numero=1,
            date_echeance=date(2024, 1, 10), montant=Decimal('100'),
            facture_id=999)
        CompteurUsage.objects.create(
            company=autre,
            type_cible=AbonnementAddOnLigne.TypeCible.CONTRAT,
            cible_id=contrat_b.id, code_compteur='api',
            periode_debut=date(2024, 1, 1), periode_fin=date(2024, 1, 31),
            quantite=Decimal('7'))

        services.purger_compteurs_usage_factures(
            self.co, today=self.AUJOURDHUI)
        # Le relevé de la société B est intact et n'a produit aucune archive.
        self.assertEqual(
            CompteurUsage.objects.filter(company=autre).count(), 1)
        self.assertFalse(
            CompteurUsageArchive.objects.filter(company=autre).exists())


class MetriquesSaasCacheTests(TestCase):
    """NTSUB27 — cache nocturne : lu s'il est frais, jamais bloquant."""

    def setUp(self):
        self.co = make_company('ntsub27', 'NTSUB27 Co')
        self.user = User.objects.create_user(
            username='ntsub27-user', password='x', company=self.co,
            role_legacy='admin')
        self.api = auth(self.user)

    def test_le_job_ecrit_une_photo_datee_du_mois_courant(self):
        from django.utils import timezone

        from apps.contrats import services
        from apps.contrats.models import MetriquesSaasCache

        today = timezone.localdate()
        cache = services.recalculer_metriques_saas_cache(self.co, today=today)
        self.assertEqual(
            cache.periode, f'{today.year:04d}-{today.month:02d}')
        self.assertIsNotNone(cache.calcule_le)
        self.assertIsInstance(cache.arr_bridge, dict)
        # NTSUB13 non branché : aucune prévision inventée.
        self.assertIsNone(cache.prevision_mrr)
        self.assertEqual(
            MetriquesSaasCache.objects.filter(company=self.co).count(), 1)

    def test_rejouer_le_job_rafraichit_sans_dupliquer(self):
        from django.utils import timezone

        from apps.contrats import services
        from apps.contrats.models import MetriquesSaasCache

        today = timezone.localdate()
        premier = services.recalculer_metriques_saas_cache(
            self.co, today=today)
        second = services.recalculer_metriques_saas_cache(self.co, today=today)
        self.assertEqual(premier.pk, second.pk)
        self.assertEqual(
            MetriquesSaasCache.objects.filter(company=self.co).count(), 1)

    def test_endpoint_sert_le_cache_frais(self):
        from apps.contrats import services

        services.recalculer_metriques_saas_cache(self.co)
        resp = self.api.get('/api/django/contrats/contrats/metriques-saas/')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data['depuis_cache'])
        self.assertIn('arr_bridge', resp.data)

    def test_cache_absent_ne_bloque_jamais_l_endpoint(self):
        from apps.contrats.models import MetriquesSaasCache

        self.assertFalse(MetriquesSaasCache.objects.exists())
        resp = self.api.get('/api/django/contrats/contrats/metriques-saas/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['depuis_cache'])
        self.assertIn('arr_bridge', resp.data)
        self.assertIn('rule_of_40', resp.data)

    def test_cache_perime_est_ignore_et_recalcule(self):
        from datetime import timedelta

        from django.utils import timezone

        from apps.contrats import services
        from apps.contrats.models import MetriquesSaasCache

        services.recalculer_metriques_saas_cache(self.co)
        cache = MetriquesSaasCache.objects.get(company=self.co)
        MetriquesSaasCache.objects.filter(pk=cache.pk).update(
            calcule_le=timezone.now() - timedelta(hours=30))
        resp = self.api.get('/api/django/contrats/contrats/metriques-saas/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['depuis_cache'])

    def test_plage_hors_mois_calendaire_calculee_a_la_volee(self):
        from apps.contrats import services

        services.recalculer_metriques_saas_cache(self.co)
        resp = self.api.get(
            '/api/django/contrats/contrats/metriques-saas/'
            '?debut=2026-01-05&fin=2026-01-20')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['depuis_cache'])

    def test_isolation_societe_du_cache(self):
        from apps.contrats import services
        from apps.contrats.models import MetriquesSaasCache

        autre = make_company('ntsub27-b', 'NTSUB27 B')
        user_b = User.objects.create_user(
            username='ntsub27-user-b', password='x', company=autre,
            role_legacy='admin')
        services.recalculer_metriques_saas_cache(self.co)
        self.assertFalse(
            MetriquesSaasCache.objects.filter(company=autre).exists())
        resp_b = auth(user_b).get(
            '/api/django/contrats/contrats/metriques-saas/')
        self.assertEqual(resp_b.status_code, 200)
        self.assertFalse(resp_b.data['depuis_cache'])
