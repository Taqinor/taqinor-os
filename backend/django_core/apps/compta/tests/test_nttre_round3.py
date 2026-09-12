"""Tests NTTRE round 3 — cockpit cash, exports et états imprimables.

NTTRE17 : bloc « Cash aujourd'hui » publié DANS ``etats/position-tresorerie/``
(solde consolidé du jour, delta vs la veille, 3 prochaines échéances) — la
carte du cockpit n'émet aucune requête supplémentaire.
NTTRE19 : export .xlsx du prévisionnel 13 semaines (colonnes semaine + ligne
« Solde projeté »), identique aux chiffres de l'écran.
"""
import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import selectors, services
from apps.compta.models import (
    CompteTresorerie, Effet, LignePrevisionnelTresorerie, PaymentRun)

User = get_user_model()

JOUR = date(2026, 3, 10)


def make_company(slug, nom=None):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom or slug})
    return company


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def ecriture_banque(company, montant, jour):
    """Encaissement en banque : débit 5141 / crédit 3421 (écriture équilibrée)."""
    from apps.compta.models import Journal

    journal = services._journal(company, Journal.Type.BANQUE)
    return services.creer_ecriture(
        company, journal, jour, 'Encaissement test', [
            {'compte': services.get_compte(company, '5141'),
             'debit': Decimal(montant), 'credit': Decimal('0')},
            {'compte': services.get_compte(company, '3421'),
             'debit': Decimal('0'), 'credit': Decimal(montant)},
        ])


class CashAujourdhuiTests(TestCase):
    """NTTRE17 — solde du jour, delta vs la veille, 3 prochaines échéances."""

    def setUp(self):
        self.co = make_company('nttre17', 'NTTRE17 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('1000'),
            compte_comptable=services.get_compte(self.co, '5141'))

    def test_delta_veille_isole_les_mouvements_du_jour(self):
        ecriture_banque(self.co, '300', JOUR)
        bloc = selectors.cash_aujourdhui(self.co, aujourd_hui=JOUR)
        self.assertEqual(bloc['total'], Decimal('1300'))
        self.assertEqual(bloc['total_veille'], Decimal('1000'))
        self.assertEqual(bloc['delta_veille'], Decimal('300'))

    def test_trois_prochaines_echeances_effets_et_campagnes(self):
        # Effet à recevoir (+), effet à payer (−) et campagne de règlement (−).
        Effet.objects.create(
            company=self.co, sens=Effet.Sens.RECEVOIR,
            type_effet=Effet.TypeEffet.CHEQUE, numero='CHQ-1',
            montant=Decimal('500'), date_emission=JOUR,
            date_echeance=JOUR + timedelta(days=3))
        Effet.objects.create(
            company=self.co, sens=Effet.Sens.PAYER,
            type_effet=Effet.TypeEffet.TRAITE, numero='LCN-9',
            montant=Decimal('700'), date_emission=JOUR,
            date_echeance=JOUR + timedelta(days=5))
        # Effet DÉJÀ encaissé : hors échéancier.
        Effet.objects.create(
            company=self.co, sens=Effet.Sens.RECEVOIR,
            type_effet=Effet.TypeEffet.CHEQUE, numero='CHQ-SOLDE',
            montant=Decimal('999'), date_emission=JOUR,
            date_echeance=JOUR + timedelta(days=1),
            statut=Effet.Statut.ENCAISSE)
        PaymentRun.objects.create(
            company=self.co, reference='RUN-1',
            compte_tresorerie=self.banque,
            date_paiement=JOUR + timedelta(days=2),
            total=Decimal('200'))

        bloc = selectors.cash_aujourdhui(self.co, aujourd_hui=JOUR)
        echeances = bloc['prochaines_echeances']
        self.assertEqual(len(echeances), 3)
        # Chronologique : campagne J+2, effet à recevoir J+3, effet à payer J+5.
        self.assertEqual(
            [e['libelle'] for e in echeances], ['RUN-1', 'CHQ-1', 'LCN-9'])
        self.assertEqual(echeances[0]['montant'], Decimal('-200'))
        self.assertEqual(echeances[1]['montant'], Decimal('500'))
        self.assertEqual(echeances[2]['montant'], Decimal('-700'))

    def test_maximum_trois_echeances(self):
        for i in range(6):
            Effet.objects.create(
                company=self.co, sens=Effet.Sens.RECEVOIR,
                type_effet=Effet.TypeEffet.CHEQUE, numero=f'CHQ-{i}',
                montant=Decimal('100'), date_emission=JOUR,
                date_echeance=JOUR + timedelta(days=i + 1))
        bloc = selectors.cash_aujourdhui(self.co, aujourd_hui=JOUR)
        self.assertEqual(len(bloc['prochaines_echeances']), 3)

    def test_isolation_societe(self):
        autre = make_company('nttre17-b', 'NTTRE17 B')
        services.seed_plan_comptable(autre)
        CompteTresorerie.objects.create(
            company=autre, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='Autre banque', solde_initial=Decimal('9999'),
            compte_comptable=services.get_compte(autre, '5141'))
        bloc = selectors.cash_aujourdhui(self.co, aujourd_hui=JOUR)
        self.assertEqual(bloc['total'], Decimal('1000'))

    def test_endpoint_position_publie_le_bloc_sans_appel_supplementaire(self):
        user = User.objects.create_user(
            username='nttre17-user', password='x', company=self.co,
            role_legacy='responsable')
        resp = auth(user).get('/api/django/compta/etats/position-tresorerie/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('cash_du_jour', resp.data)
        bloc = resp.data['cash_du_jour']
        for cle in ('total', 'total_veille', 'delta_veille',
                    'prochaines_echeances'):
            self.assertIn(cle, bloc)


class PrevisionnelXlsxTests(TestCase):
    """NTTRE19 — classeur banquier : 13 colonnes semaine + solde projeté."""

    def setUp(self):
        self.co = make_company('nttre19', 'NTTRE19 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', solde_initial=Decimal('1000'),
            compte_comptable=services.get_compte(self.co, '5141'))
        self.user = User.objects.create_user(
            username='nttre19-user', password='x', company=self.co,
            role_legacy='responsable')
        self.api = auth(self.user)

    def _feuille(self, contenu):
        from openpyxl import load_workbook
        return load_workbook(io.BytesIO(contenu)).active

    def test_treize_colonnes_semaine_et_ligne_solde_projete(self):
        resp = self.api.get(
            '/api/django/compta/etats/previsionnel-tresorerie/?export=xlsx')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
        ws = self._feuille(resp.content)
        # 1 colonne de libellé + 13 colonnes semaine.
        self.assertEqual(ws.max_column, 14)
        libelles = [ws.cell(row=r, column=1).value
                    for r in range(2, ws.max_row + 1)]
        self.assertIn('Solde projeté', libelles)

    def test_chiffres_identiques_a_ceux_de_l_ecran(self):
        # Le prévisionnel démarre au LUNDI de la semaine courante : on cale la
        # ligne prévue sur cette même semaine (aucune horloge figée requise).
        aujourdhui = timezone.localdate()
        lundi = aujourdhui - timedelta(days=aujourdhui.weekday())
        LignePrevisionnelTresorerie.objects.create(
            company=self.co, libelle='Subvention',
            date_prevue=lundi + timedelta(days=2), montant=Decimal('750'))
        ecran = self.api.get(
            '/api/django/compta/etats/previsionnel-tresorerie/')
        classeur = self.api.get(
            '/api/django/compta/etats/previsionnel-tresorerie/?export=xlsx')
        self.assertEqual(ecran.status_code, 200)
        self.assertEqual(classeur.status_code, 200)
        ws = self._feuille(classeur.content)
        lignes = {ws.cell(row=r, column=1).value: [
            ws.cell(row=r, column=c).value
            for c in range(2, ws.max_column + 1)]
            for r in range(2, ws.max_row + 1)}
        soldes_ecran = [float(s['solde_fin'])
                        for s in ecran.data['semaines']]
        self.assertEqual(lignes['Solde projeté'], soldes_ecran)
        self.assertEqual(lignes['Encaissements'][0], 750.0)

    def test_nb_semaines_personnalise_change_le_nombre_de_colonnes(self):
        resp = self.api.get(
            '/api/django/compta/etats/previsionnel-tresorerie/'
            '?export=xlsx&nb_semaines=4')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._feuille(resp.content).max_column, 5)


class QualiteRapprochementsTests(TestCase):
    """NTTRE20 — lignes restées non pointées à la clôture, mois par mois."""

    def setUp(self):
        self.co = make_company('nttre20', 'NTTRE20 Co')
        services.seed_plan_comptable(self.co)
        services.seed_journaux(self.co)
        self.banque = CompteTresorerie.objects.create(
            company=self.co, type_compte=CompteTresorerie.Type.BANQUE,
            libelle='BMCE', compte_comptable=services.get_compte(self.co, '5141'))

    def _rapprochement(self, mois, *, non_pointees=0, cloture=True):
        from apps.compta.models import RapprochementBancaire

        rap = services.creer_rapprochement(
            self.co, self.banque, date_debut=date(2026, mois, 1),
            date_fin=date(2026, mois, 28), solde_releve=Decimal('0'))
        for i in range(non_pointees):
            services.ajouter_ligne_releve(
                rap, date_operation=date(2026, mois, 5),
                libelle=f'Op {mois}-{i}', montant=Decimal('10'))
        if cloture:
            # Clôture POSÉE directement : le service refuse de clôturer tant
            # qu'un écart subsiste — on teste ici la LECTURE d'un historique
            # déjà clôturé (reprise d'antériorité, clôture forcée en base).
            rap.statut = RapprochementBancaire.Statut.RAPPROCHE
            rap.save(update_fields=['statut'])
        return rap

    def test_compte_exact_des_lignes_non_pointees_par_mois(self):
        self._rapprochement(2, non_pointees=3)
        self._rapprochement(3, non_pointees=1)
        data = selectors.qualite_rapprochements(
            self.co, nb_mois=12, today=date(2026, 12, 31))
        par_mois = {m['mois']: m for m in data['mois']}
        self.assertEqual(par_mois['2026-02']['lignes_non_pointees'], 3)
        self.assertEqual(par_mois['2026-02']['rapprochements'], 1)
        self.assertEqual(par_mois['2026-03']['lignes_non_pointees'], 1)
        self.assertEqual(data['total_lignes_non_pointees'], 4)

    def test_rapprochement_non_cloture_exclu(self):
        self._rapprochement(4, non_pointees=5, cloture=False)
        data = selectors.qualite_rapprochements(
            self.co, nb_mois=12, today=date(2026, 12, 31))
        self.assertEqual(data['total_lignes_non_pointees'], 0)
        par_mois = {m['mois']: m for m in data['mois']}
        self.assertEqual(par_mois['2026-04']['rapprochements'], 0)

    def test_fenetre_de_mois_continue_et_ordonnee(self):
        data = selectors.qualite_rapprochements(
            self.co, nb_mois=6, today=date(2026, 6, 15))
        self.assertEqual(
            [m['mois'] for m in data['mois']],
            ['2026-01', '2026-02', '2026-03', '2026-04', '2026-05', '2026-06'])

    def test_endpoint_scope_societe(self):
        self._rapprochement(2, non_pointees=2)
        autre = make_company('nttre20-b', 'NTTRE20 B')
        user_b = User.objects.create_user(
            username='nttre20-user-b', password='x', company=autre,
            role_legacy='responsable')
        resp = auth(user_b).get(
            '/api/django/compta/etats/qualite-rapprochements/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['total_lignes_non_pointees'], 0)
