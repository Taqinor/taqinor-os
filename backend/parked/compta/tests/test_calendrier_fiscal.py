"""XACC9 — Calendrier des obligations fiscales.

Couvre :

* l'exercice généré affiche toutes les échéances TVA/IS/RAS/timbre/9421/
  liasse avec des dates limites marocaines correctes ;
* génération idempotente (rejouer ne duplique rien) ;
* le dépôt d'une ``DeclarationTVA`` passe l'obligation TVA correspondante en
  « déposée » ;
* le rappel J-7 notifie une seule fois (idempotent) ;
* endpoints API.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
from apps.compta.models import DeclarationTVA, ExerciceComptable, ObligationFiscale

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class CalendrierFiscalTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc9', 'XACC9 Co')
        services.seed_plan_comptable(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026')

    def test_calendrier_mensuel_complet(self):
        obligations = services.generer_calendrier_fiscal(
            self.co, self.exercice, regime_tva=DeclarationTVA.Regime.MENSUEL)
        types = {o.type_obligation for o in obligations}
        self.assertEqual(types, {
            ObligationFiscale.Type.TVA, ObligationFiscale.Type.RAS,
            ObligationFiscale.Type.IS_ACOMPTE, ObligationFiscale.Type.TIMBRE,
            ObligationFiscale.Type.LIASSE_FISCALE,
            ObligationFiscale.Type.ETAT_9421,
        })
        # 12 échéances TVA mensuelles.
        self.assertEqual(
            len([o for o in obligations
                if o.type_obligation == ObligationFiscale.Type.TVA]), 12)
        # 4 acomptes IS.
        self.assertEqual(
            len([o for o in obligations
                if o.type_obligation == ObligationFiscale.Type.IS_ACOMPTE]), 4)

    def test_dates_limites_marocaines_correctes(self):
        obligations = services.generer_calendrier_fiscal(
            self.co, self.exercice, regime_tva=DeclarationTVA.Regime.MENSUEL)
        tva_janvier = next(
            o for o in obligations
            if o.type_obligation == ObligationFiscale.Type.TVA
            and o.periode_debut == date(2026, 1, 1))
        # TVA janvier → limite 20 février.
        self.assertEqual(tva_janvier.date_limite, date(2026, 2, 20))
        acompte_mars = next(
            o for o in obligations
            if o.type_obligation == ObligationFiscale.Type.IS_ACOMPTE
            and o.date_limite.month == 3)
        self.assertEqual(acompte_mars.date_limite, date(2026, 3, 31))

    def test_calendrier_trimestriel(self):
        obligations = services.generer_calendrier_fiscal(
            self.co, self.exercice,
            regime_tva=DeclarationTVA.Regime.TRIMESTRIEL)
        tva = [o for o in obligations
               if o.type_obligation == ObligationFiscale.Type.TVA]
        self.assertEqual(len(tva), 4)
        q1 = next(o for o in tva if o.periode_debut == date(2026, 1, 1))
        self.assertEqual(q1.periode_fin, date(2026, 3, 31))
        self.assertEqual(q1.date_limite, date(2026, 4, 20))

    def test_generation_idempotente(self):
        n1 = len(services.generer_calendrier_fiscal(self.co, self.exercice))
        n2 = len(services.generer_calendrier_fiscal(self.co, self.exercice))
        self.assertEqual(n1, n2)
        self.assertEqual(
            ObligationFiscale.objects.filter(company=self.co).count(), n1)


class DepotDeclarationTests(TestCase):
    def setUp(self):
        self.co = make_company('xacc9-depot', 'XACC9 Dépôt Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026')
        services.generer_calendrier_fiscal(self.co, self.exercice)

    def test_depot_passe_obligation_deposee(self):
        decl = services.preparer_declaration_tva(
            self.co, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        obligation = ObligationFiscale.objects.get(
            company=self.co, type_obligation=ObligationFiscale.Type.TVA,
            periode_debut=date(2026, 1, 1))
        self.assertEqual(obligation.statut, ObligationFiscale.Statut.A_PREPARER)
        services.deposer_declaration_tva(decl)
        obligation.refresh_from_db()
        self.assertEqual(obligation.statut, ObligationFiscale.Statut.DEPOSEE)
        self.assertEqual(obligation.source_type, 'declaration_tva')
        self.assertEqual(obligation.source_id, decl.id)
        decl.refresh_from_db()
        self.assertEqual(decl.statut, DeclarationTVA.Statut.DEPOSEE)

    def test_depot_sans_calendrier_ne_bloque_pas(self):
        co2 = make_company('xacc9-sans-cal', 'XACC9 Sans Calendrier')
        services.seed_plan_comptable(co2)
        services.seed_journaux(co2)
        decl = services.preparer_declaration_tva(
            co2, date_debut=date(2026, 1, 1), date_fin=date(2026, 1, 31))
        # Aucun calendrier généré pour co2 : le dépôt ne lève pas d'erreur.
        result = services.deposer_declaration_tva(decl)
        self.assertEqual(result.statut, DeclarationTVA.Statut.DEPOSEE)


class RappelsJ7Tests(TestCase):
    def setUp(self):
        self.co = make_company('xacc9-rappel', 'XACC9 Rappel Co')
        services.seed_plan_comptable(self.co)
        self.admin = make_user(self.co, 'admin-xacc9', role='admin')
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026')

    def test_rappel_j7_notifie_une_fois(self):
        obligation = ObligationFiscale.objects.create(
            company=self.co, type_obligation=ObligationFiscale.Type.TVA,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 1, 31),
            date_limite=date(2026, 2, 20), libelle='TVA janvier')
        aujourdhui = date(2026, 2, 13)  # J-7 exact.
        notifiees = services.envoyer_rappels_j7(self.co, aujourdhui=aujourdhui)
        self.assertEqual(len(notifiees), 1)
        obligation.refresh_from_db()
        self.assertIsNotNone(obligation.rappel_envoye_le)
        # Rejouer le même jour ne renvoie rien (idempotent).
        notifiees2 = services.envoyer_rappels_j7(self.co, aujourdhui=aujourdhui)
        self.assertEqual(notifiees2, [])

    def test_hors_fenetre_j7_pas_de_rappel(self):
        ObligationFiscale.objects.create(
            company=self.co, type_obligation=ObligationFiscale.Type.TVA,
            periode_debut=date(2026, 1, 1), periode_fin=date(2026, 1, 31),
            date_limite=date(2026, 2, 20), libelle='TVA janvier')
        notifiees = services.envoyer_rappels_j7(
            self.co, aujourdhui=date(2026, 1, 1))
        self.assertEqual(notifiees, [])


class CalendrierFiscalAPITests(TestCase):
    def setUp(self):
        self.co = make_company('xacc9-api', 'XACC9 API Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.exercice = ExerciceComptable.objects.create(
            company=self.co, date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31), libelle='Exercice 2026')
        self.user = make_user(self.co, 'admin-xacc9-api')
        self.api = auth(self.user)

    def test_generer_via_api(self):
        resp = self.api.post(
            '/api/django/compta/obligations-fiscales/generer/',
            {'exercice': self.exercice.id}, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertGreater(len(resp.data), 0)

    def test_liste_et_filtre_statut(self):
        services.generer_calendrier_fiscal(self.co, self.exercice)
        resp = self.api.get(
            '/api/django/compta/obligations-fiscales/?statut=a_preparer')
        self.assertEqual(resp.status_code, 200)
