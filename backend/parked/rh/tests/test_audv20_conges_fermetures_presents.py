"""AUDV20 — écran RH Maroc : congés, fermetures, présents-chantier.

Quatre moteurs RH existaient mais n'étaient consommés NULLE PART. Ce module
couvre leur câblage :

* ``services.droit_annuel`` → exposé sur la fiche solde de congés
  (``SoldeCongeSerializer.droit_annuel``), ancienneté prise au 31/12 de
  l'année du solde (jamais « aujourd'hui » — rendu déterministe) ;
* ``selectors.jours_fermeture_exclus`` (docstring : « évite le
  double-décompte », appelée nulle part) → câblée dans la création d'une
  demande de congé, viewset RH ET portail self-service ;
* ``selectors.effectif_present_le`` → servi par
  ``GET /rh/presences-chantier/effectif/`` (contrat figé dans
  ``contract_samples/effectif_chantier.json``) ;
* ``selectors.poste_appartient_societe`` (DC17) → devient le contrôle unique
  du rattachement d'un ``Poste``, y compris sur les DEUX FK MÊME-APP qui n'en
  avaient AUCUN (``GrilleSalariale.poste``, ``CompetenceRequise.poste``) —
  invisibles à ``check_fk_scoping`` qui ne balaie que le cross-app.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.roles.models import Role
from apps.rh.models import (
    Competence,
    CompetenceRequise,
    Departement,
    DossierEmploye,
    GrilleSalariale,
    PeriodeFermeture,
    Poste,
    PresenceChantier,
    SoldeConge,
    TypeAbsence,
)

User = get_user_model()

SOLDES = '/api/django/rh/soldes-conge/'
DEMANDES = '/api/django/rh/demandes-conge/'
EFFECTIF = '/api/django/rh/presences-chantier/effectif/'
GRILLES = '/api/django/rh/grilles-salariales/'
REQUISES = '/api/django/rh/competences-requises/'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role_legacy='responsable', permissions=None):
    role = None
    if permissions is not None:
        role = Role.objects.create(
            company=company, nom=f'role-{username}',
            permissions=list(permissions))
    return User.objects.create_user(
        username=username, password='x', company=company,
        role=role, role_legacy=role_legacy)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class DroitAnnuelSurFicheSoldeTests(TestCase):
    """Le droit LÉGAL annuel théorique est lisible sur la fiche solde."""

    def setUp(self):
        self.co = make_company('audv20-droit', 'A')
        self.rh = make_user(self.co, 'audv20-droit-rh')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='D1', nom='Tazi', prenom='Reda',
            date_embauche=date(2020, 1, 1))

    def test_droit_annuel_expose_avec_bonus_anciennete(self):
        SoldeConge.objects.create(
            company=self.co, employe=self.emp, annee=2026,
            acquis=Decimal('9.00'), pris=Decimal('2.00'))
        resp = auth(self.rh).get(SOLDES)
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = (resp.data['results'] if isinstance(resp.data, dict)
                 else resp.data)[0]
        # Embauché le 01/01/2020, 6 ans révolus au 31/12/2026 → 18 + 1,5.
        self.assertEqual(Decimal(ligne['droit_annuel']), Decimal('19.50'))

    def test_droit_annuel_null_sans_date_embauche(self):
        """Jamais un chiffre par défaut : sans ancienneté calculable, on omet."""
        sans_date = DossierEmploye.objects.create(
            company=self.co, matricule='D2', nom='Chraibi', prenom='Sanae')
        SoldeConge.objects.create(
            company=self.co, employe=sans_date, annee=2026,
            acquis=Decimal('3.00'))
        resp = auth(self.rh).get(f'{SOLDES}?employe={sans_date.id}')
        self.assertEqual(resp.status_code, 200, resp.data)
        ligne = (resp.data['results'] if isinstance(resp.data, dict)
                 else resp.data)[0]
        self.assertIsNone(ligne['droit_annuel'])


class DemandeCongeChevauchantFermetureTests(TestCase):
    """XRH14 — une demande chevauchant une fermeture n'est plus double-comptée."""

    def setUp(self):
        self.co = make_company('audv20-ferm', 'A')
        self.rh = make_user(self.co, 'audv20-ferm-rh')
        self.dep = Departement.objects.create(company=self.co, nom='Production')
        self.type_cp = TypeAbsence.objects.create(
            company=self.co, code='CP', libelle='Congé payé',
            decompte_jours_ouvres=False, deduit_solde=True)
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='F1', nom='Tazi', prenom='Reda',
            departement=self.dep, statut=DossierEmploye.Statut.ACTIF)

    def _demander(self, debut, fin):
        resp = auth(self.rh).post(DEMANDES, {
            'employe': self.emp.id, 'type_absence': self.type_cp.id,
            'date_debut': debut, 'date_fin': fin,
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        return Decimal(resp.data['jours'])

    def test_sans_fermeture_le_decompte_est_inchange(self):
        self.assertEqual(self._demander('2026-08-10', '2026-08-14'),
                         Decimal('5'))

    def test_jours_couverts_par_une_fermeture_ne_sont_pas_recomptes(self):
        PeriodeFermeture.objects.create(
            company=self.co, libelle='Fermeture Aïd',
            date_debut=date(2026, 8, 10), date_fin=date(2026, 8, 11),
            type_absence=self.type_cp)
        # 5 jours calendaires demandés, 2 déjà couverts par la fermeture.
        self.assertEqual(self._demander('2026-08-10', '2026-08-14'),
                         Decimal('3'))

    def test_fermeture_d_un_autre_departement_ne_retranche_rien(self):
        autre = Departement.objects.create(company=self.co, nom='Commercial')
        fermeture = PeriodeFermeture.objects.create(
            company=self.co, libelle='Fermeture Commercial',
            date_debut=date(2026, 8, 10), date_fin=date(2026, 8, 11),
            type_absence=self.type_cp)
        fermeture.departements.add(autre)
        self.assertEqual(self._demander('2026-08-10', '2026-08-14'),
                         Decimal('5'))

    def test_type_en_jours_ouvres_traite_la_fermeture_comme_un_ferie(self):
        ouvre = TypeAbsence.objects.create(
            company=self.co, code='RTT', libelle='Récupération',
            decompte_jours_ouvres=True, deduit_solde=True)
        # Semaine du 07/09/2026 : lundi→vendredi, AUCUN férié marocain fixe
        # (le 14/08 en est un — la fenêtre est choisie pour que le test ne
        # mesure que l'effet de la fermeture).
        PeriodeFermeture.objects.create(
            company=self.co, libelle='Pont',
            date_debut=date(2026, 9, 7), date_fin=date(2026, 9, 8),
            type_absence=self.type_cp)
        resp = auth(self.rh).post(DEMANDES, {
            'employe': self.emp.id, 'type_absence': ouvre.id,
            'date_debut': '2026-09-07', 'date_fin': '2026-09-11',
        })
        self.assertEqual(resp.status_code, 201, resp.data)
        # Lun→ven = 5 jours ouvrés, moins les 2 jours de fermeture.
        self.assertEqual(Decimal(resp.data['jours']), Decimal('3'))


class EffectifChantierTests(TestCase):
    """L'effectif présent d'un chantier a enfin un endpoint (et un écran)."""

    JOUR = '2026-09-04'

    def setUp(self):
        self.co = make_company('audv20-eff', 'A')
        self.autre = make_company('audv20-eff-b', 'B')
        self.rh = make_user(self.co, 'audv20-eff-rh')
        self.rh_autre = make_user(self.autre, 'audv20-eff-rh-b')
        self.emp = DossierEmploye.objects.create(
            company=self.co, matricule='P1', nom='Bennani', prenom='Youssef')
        self.emp2 = DossierEmploye.objects.create(
            company=self.co, matricule='P2', nom='Alami', prenom='Sara')
        self.absent = DossierEmploye.objects.create(
            company=self.co, matricule='P3', nom='Idrissi', prenom='Nabil')
        for emp, statut in (
                (self.emp, PresenceChantier.Statut.PRESENT),
                (self.emp2, PresenceChantier.Statut.PRESENT),
                (self.absent, PresenceChantier.Statut.ABSENT)):
            PresenceChantier.objects.create(
                company=self.co, employe=emp, installation_id=42,
                date=date(2026, 9, 4), statut=statut)

    def test_effectif_exclut_les_absents_et_liste_les_comptes(self):
        resp = auth(self.rh).get(
            f'{EFFECTIF}?installation_id=42&date={self.JOUR}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['installation_id'], 42)
        self.assertEqual(resp.data['date'], self.JOUR)
        self.assertEqual(resp.data['effectif'], 2)
        # Le nombre facturé s'affiche TOUJOURS avec les employés qu'il compte.
        self.assertEqual(len(resp.data['presents']), 2)
        noms = {p['employe_nom'] for p in resp.data['presents']}
        self.assertNotIn('Idrissi Nabil', noms)

    def test_installation_id_obligatoire(self):
        self.assertEqual(auth(self.rh).get(EFFECTIF).status_code, 400)

    def test_isolation_societe(self):
        resp = auth(self.rh_autre).get(
            f'{EFFECTIF}?installation_id=42&date={self.JOUR}')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['effectif'], 0)
        self.assertEqual(resp.data['presents'], [])


class PosteCrossSocieteTests(TestCase):
    """DC17 — aucun ``Poste`` d'une autre société ne peut être rattaché."""

    def setUp(self):
        self.co = make_company('audv20-poste', 'A')
        self.autre = make_company('audv20-poste-b', 'B')
        self.rh = make_user(self.co, 'audv20-poste-rh')
        self.paie = make_user(
            self.co, 'audv20-poste-paie', permissions=['salaires_voir'])
        self.poste_local = Poste.objects.create(
            company=self.co, intitule='Chef de chantier')
        self.poste_etranger = Poste.objects.create(
            company=self.autre, intitule='Chef de chantier')
        self.competence = Competence.objects.create(
            company=self.co, code='ELEC', libelle='Électricité PV')

    def test_grille_salariale_refuse_un_poste_d_une_autre_societe(self):
        resp = auth(self.paie).post(GRILLES, {
            'poste': self.poste_etranger.id, 'salaire_min': '8000',
            'salaire_max': '12000', 'date_effet': '2026-01-01',
        })
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('poste', resp.data)
        self.assertFalse(
            GrilleSalariale.objects.filter(poste=self.poste_etranger).exists())

    def test_grille_salariale_accepte_un_poste_de_la_societe(self):
        resp = auth(self.paie).post(GRILLES, {
            'poste': self.poste_local.id, 'salaire_min': '8000',
            'salaire_max': '12000', 'date_effet': '2026-01-01',
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_competence_requise_refuse_un_poste_d_une_autre_societe(self):
        resp = auth(self.rh).post(REQUISES, {
            'poste': self.poste_etranger.id,
            'competence': self.competence.id, 'niveau_requis': 2,
        })
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('poste', resp.data)
        self.assertFalse(
            CompetenceRequise.objects.filter(
                poste=self.poste_etranger).exists())

    def test_competence_requise_accepte_un_poste_de_la_societe(self):
        resp = auth(self.rh).post(REQUISES, {
            'poste': self.poste_local.id,
            'competence': self.competence.id, 'niveau_requis': 2,
        })
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_dossier_employe_refuse_un_poste_d_une_autre_societe(self):
        resp = auth(self.rh).post('/api/django/rh/employes/', {
            'matricule': 'X1', 'nom': 'Tazi', 'prenom': 'Reda',
            'poste_ref': self.poste_etranger.id,
        })
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('poste_ref', resp.data)
