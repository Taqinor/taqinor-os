"""NTP2P47 — sélecteurs d'agrégation KPI notes de frais & per-diem.

Couvre les 4 nouveaux sélecteurs de ``apps.frais.selectors`` : total
remboursé par catégorie, top employés par montant, délai moyen
dépense→remboursement (critère d'acceptation NTP2P47 : soumis/dépensé le
1er, remboursé le 15 → 14 jours), total per-diem par destination."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.frais.models import BaremeIndemnite, IndemniteChantier, NoteFrais
from apps.frais.selectors import (
    delai_moyen_depense_remboursement_jours,
    top_employes_par_montant_notes_frais,
    total_per_diem_par_destination,
    total_rembourse_par_categorie,
)
from authentication.models import Company

User = get_user_model()


def make_company(slug, nom):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def make_user(company, username, **kwargs):
    return User.objects.create_user(
        username=username, password='x', company=company, **kwargs)


class TotalRembourseParCategorieTests(TestCase):
    def setUp(self):
        self.company = make_company('ntp2p47-cat-co', 'NTP2P47 Cat Co')
        self.employe = make_user(self.company, 'ntp2p47-cat-emp')

    def test_agrege_uniquement_les_notes_remboursees(self):
        NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 2, 1), montant=Decimal('100'),
            motif='Carburant', categorie=NoteFrais.Categorie.CARBURANT,
            statut=NoteFrais.Statut.REMBOURSEE,
            date_remboursement=date(2026, 2, 15))
        NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 2, 2), montant=Decimal('50'),
            motif='Repas', categorie=NoteFrais.Categorie.REPAS,
            statut=NoteFrais.Statut.SOUMISE)  # pas remboursée : ignorée

        lignes = total_rembourse_par_categorie(self.company)
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['categorie'], NoteFrais.Categorie.CARBURANT)
        self.assertEqual(lignes[0]['montant_total'], Decimal('100'))

    def test_borne_par_date_remboursement(self):
        NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 1, 1), montant=Decimal('100'),
            motif='x', statut=NoteFrais.Statut.REMBOURSEE,
            date_remboursement=date(2026, 1, 15))
        lignes = total_rembourse_par_categorie(
            self.company, debut=date(2026, 2, 1))
        self.assertEqual(lignes, [])

    def test_sans_societe_renvoie_liste_vide(self):
        self.assertEqual(total_rembourse_par_categorie(None), [])


class TopEmployesParMontantTests(TestCase):
    def setUp(self):
        self.company = make_company('ntp2p47-top-co', 'NTP2P47 Top Co')
        self.e1 = make_user(
            self.company, 'ntp2p47-top-e1', first_name='Amine',
            last_name='B.')
        self.e2 = make_user(
            self.company, 'ntp2p47-top-e2', first_name='Sara',
            last_name='K.')

    def test_classe_par_montant_total_decroissant(self):
        NoteFrais.objects.create(
            company=self.company, employe=self.e1,
            date_frais=date(2026, 2, 1), montant=Decimal('300'), motif='x')
        NoteFrais.objects.create(
            company=self.company, employe=self.e2,
            date_frais=date(2026, 2, 2), montant=Decimal('100'), motif='x')
        NoteFrais.objects.create(
            company=self.company, employe=self.e2,
            date_frais=date(2026, 2, 3), montant=Decimal('250'), motif='x')

        top = top_employes_par_montant_notes_frais(self.company)
        self.assertEqual(len(top), 2)
        self.assertEqual(top[0]['employe_id'], self.e2.id)  # 100+250=350
        self.assertEqual(top[0]['montant_total'], Decimal('350'))
        self.assertEqual(top[0]['employe_nom'], 'Sara K.')
        self.assertEqual(top[1]['employe_id'], self.e1.id)

    def test_respecte_la_limite(self):
        for i in range(7):
            emp = make_user(self.company, f'ntp2p47-top-many-{i}')
            NoteFrais.objects.create(
                company=self.company, employe=emp,
                date_frais=date(2026, 2, 1), montant=Decimal('10'), motif='x')
        self.assertEqual(
            len(top_employes_par_montant_notes_frais(
                self.company, limit=5)), 5)


class DelaiMoyenDepenseRemboursementTests(TestCase):
    def setUp(self):
        self.company = make_company('ntp2p47-delai-co', 'NTP2P47 Delai Co')
        self.employe = make_user(self.company, 'ntp2p47-delai-emp')

    def test_critere_acceptation_1er_au_15_egale_14_jours(self):
        NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 2, 1), montant=Decimal('100'), motif='x',
            statut=NoteFrais.Statut.REMBOURSEE,
            date_remboursement=date(2026, 2, 15))
        self.assertEqual(
            delai_moyen_depense_remboursement_jours(self.company), 14.0)

    def test_moyenne_sur_plusieurs_notes(self):
        NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 2, 1), montant=Decimal('100'), motif='x',
            statut=NoteFrais.Statut.REMBOURSEE,
            date_remboursement=date(2026, 2, 11))  # 10 jours
        NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 2, 1), montant=Decimal('100'), motif='x',
            statut=NoteFrais.Statut.REMBOURSEE,
            date_remboursement=date(2026, 2, 21))  # 20 jours
        self.assertEqual(
            delai_moyen_depense_remboursement_jours(self.company), 15.0)

    def test_none_sans_note_remboursee(self):
        NoteFrais.objects.create(
            company=self.company, employe=self.employe,
            date_frais=date(2026, 2, 1), montant=Decimal('100'), motif='x',
            statut=NoteFrais.Statut.SOUMISE)
        self.assertIsNone(
            delai_moyen_depense_remboursement_jours(self.company))


class TotalPerDiemParDestinationTests(TestCase):
    def setUp(self):
        self.company = make_company('ntp2p47-pd-co', 'NTP2P47 PerDiem Co')
        self.employe = make_user(self.company, 'ntp2p47-pd-emp')
        self.bareme = BaremeIndemnite.objects.create(
            company=self.company, libelle='Barème NTP2P47',
            taux_km=Decimal('3'), per_diem=Decimal('150'), defaut=True)

    def test_agrege_par_destination(self):
        IndemniteChantier.objects.create(
            company=self.company, employe=self.employe, bareme=self.bareme,
            date_deplacement=date(2026, 2, 10), libelle_chantier='Rabat',
            montant_per_diem=Decimal('300'), montant_total=Decimal('300'))
        IndemniteChantier.objects.create(
            company=self.company, employe=self.employe, bareme=self.bareme,
            date_deplacement=date(2026, 2, 12), libelle_chantier='Rabat',
            montant_per_diem=Decimal('150'), montant_total=Decimal('150'))
        IndemniteChantier.objects.create(
            company=self.company, employe=self.employe, bareme=self.bareme,
            date_deplacement=date(2026, 2, 14), libelle_chantier='Marrakech',
            montant_per_diem=Decimal('450'), montant_total=Decimal('450'))

        lignes = total_per_diem_par_destination(self.company)
        par_destination = {ligne['destination']: ligne['montant_total']
                           for ligne in lignes}
        self.assertEqual(par_destination['Rabat'], Decimal('450'))
        self.assertEqual(par_destination['Marrakech'], Decimal('450'))

    def test_sans_societe_renvoie_liste_vide(self):
        self.assertEqual(total_per_diem_par_destination(None), [])
