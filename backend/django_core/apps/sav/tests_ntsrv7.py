"""NTSRV7 — Affectation auto par COMPÉTENCE (étend XSAV9).

Critère d'acceptation : quand le flag ``affectation_par_competence`` est ON
et qu'au moins un technicien QUALIFIÉ existe, un technicien SANS la
compétence n'est JAMAIS choisi — même s'il est moins chargé.

Couvre aussi :
  * flag OFF (défaut) → comportement XSAV9 strictement inchangé ;
  * catégorie sans compétence → aucun filtre ;
  * aucun technicien qualifié → repli round-robin XSAV9.

Run :
    docker compose exec django_core python manage.py test apps.sav.tests_ntsrv7 -v 2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.rh.models import Competence, CompetenceEmploye, DossierEmploye
from apps.rh.selectors import employes_avec_competence
from apps.sav.models import CategorieTicket, SavSlaSettings, Ticket
from apps.sav.services import assign_technicien_auto

User = get_user_model()


class NTSRV7AffectationCompetenceTest(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv7', defaults={'nom': 'Sav Co NTSRV7'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='NTSRV7')

        # tech_a : NON qualifié mais le MOINS chargé (0 ticket ouvert).
        # tech_b : QUALIFIÉ, plus chargé (1 ticket ouvert).
        self.tech_a = User.objects.create_user(
            username='ntsrv7_tech_a', password='x', role_legacy='normal',
            company=self.company)
        self.tech_b = User.objects.create_user(
            username='ntsrv7_tech_b', password='x', role_legacy='normal',
            company=self.company)

        # Les deux participent au pool (déjà assignés au moins une fois).
        Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV7-SEED-A',
            client=self.client_obj, technicien_responsable=self.tech_a,
            statut=Ticket.Statut.CLOTURE)
        Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV7-SEED-B',
            client=self.client_obj, technicien_responsable=self.tech_b,
            statut=Ticket.Statut.EN_COURS)

        self.competence = Competence.objects.create(
            company=self.company, code='raccordement_ac',
            libelle='Raccordement AC',
            domaine=Competence.Domaine.RACCORDEMENT_AC)
        self.dossier_b = DossierEmploye.objects.create(
            company=self.company, user=self.tech_b, matricule='E-B',
            nom='Tech', prenom='B')
        CompetenceEmploye.objects.create(
            company=self.company, employe=self.dossier_b,
            competence=self.competence, niveau=3)

        self.categorie = CategorieTicket.objects.create(
            company=self.company, libelle='Onduleur Huawei',
            niveau_competence_min=2)
        self.categorie.competences_requises.add(self.competence)

        self.ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV7-1',
            client=self.client_obj, categorie=self.categorie)

    def _activer(self, **kwargs):
        sla = SavSlaSettings.get(self.company)
        sla.affectation_auto_sav = True
        for cle, valeur in kwargs.items():
            setattr(sla, cle, valeur)
        sla.save()
        return sla

    # ── Critère d'acceptation ────────────────────────────────────────────
    def test_technicien_non_qualifie_jamais_choisi_quand_flag_on(self):
        self._activer(affectation_par_competence=True)
        choisi = assign_technicien_auto(
            company=self.company, ticket=self.ticket)
        self.assertEqual(choisi, self.tech_b,
                         'le qualifié doit gagner malgré sa charge')

    def test_flag_off_garde_le_comportement_xsav9(self):
        self._activer(affectation_par_competence=False)
        choisi = assign_technicien_auto(
            company=self.company, ticket=self.ticket)
        self.assertEqual(choisi, self.tech_a,
                         'sans le flag, le moins chargé gagne (XSAV9)')

    def test_categorie_sans_competence_ne_filtre_rien(self):
        self._activer(affectation_par_competence=True)
        sans = CategorieTicket.objects.create(
            company=self.company, libelle='Question')
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV7-2',
            client=self.client_obj, categorie=sans)
        self.assertEqual(
            assign_technicien_auto(company=self.company, ticket=ticket),
            self.tech_a)

    def test_ticket_sans_categorie_ne_filtre_rien(self):
        self._activer(affectation_par_competence=True)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV7-3',
            client=self.client_obj)
        self.assertEqual(
            assign_technicien_auto(company=self.company, ticket=ticket),
            self.tech_a)

    def test_aucun_qualifie_replie_sur_le_round_robin(self):
        self._activer(affectation_par_competence=True)
        autre_competence = Competence.objects.create(
            company=self.company, code='pompage', libelle='Pompage',
            domaine=Competence.Domaine.POMPAGE)
        categorie = CategorieTicket.objects.create(
            company=self.company, libelle='Pompage solaire')
        categorie.competences_requises.add(autre_competence)
        ticket = Ticket.objects.create(
            company=self.company, reference='SAV-NTSRV7-4',
            client=self.client_obj, categorie=categorie)
        self.assertEqual(
            assign_technicien_auto(company=self.company, ticket=ticket),
            self.tech_a, 'pool filtré vide → repli XSAV9, jamais un blocage')

    def test_niveau_insuffisant_ne_qualifie_pas(self):
        self._activer(affectation_par_competence=True)
        CompetenceEmploye.objects.filter(employe=self.dossier_b).update(niveau=1)
        # Plus personne n'atteint le niveau 2 → pool filtré vide → repli.
        self.assertEqual(
            assign_technicien_auto(company=self.company, ticket=self.ticket),
            self.tech_a)

    def test_appel_sans_ticket_reste_compatible(self):
        """L'ancienne signature (sans `ticket`) reste valide — XSAV9."""
        self._activer(affectation_par_competence=True)
        self.assertEqual(assign_technicien_auto(company=self.company),
                         self.tech_a)

    def test_defaut_du_flag_est_off(self):
        autre, _ = Company.objects.get_or_create(
            slug='sav-ntsrv7-b', defaults={'nom': 'Autre'})
        self.assertFalse(SavSlaSettings.get(autre).affectation_par_competence)


class NTSRV7SelecteurRhTest(TestCase):
    """Le sélecteur RH renvoie les COMPTES UTILISATEUR qualifiés, scopés."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='sav-ntsrv7-rh', defaults={'nom': 'RH Co'})
        self.user = User.objects.create_user(
            username='ntsrv7_rh_user', password='x', role_legacy='normal',
            company=self.company)
        self.competence_a = Competence.objects.create(
            company=self.company, code='a', libelle='A')
        self.competence_b = Competence.objects.create(
            company=self.company, code='b', libelle='B')
        self.dossier = DossierEmploye.objects.create(
            company=self.company, user=self.user, matricule='E-1',
            nom='N', prenom='P')

    def test_liste_vide_renvoie_un_set_vide(self):
        self.assertEqual(employes_avec_competence(self.company, []), set())

    def test_toutes_les_competences_doivent_etre_couvertes(self):
        CompetenceEmploye.objects.create(
            company=self.company, employe=self.dossier,
            competence=self.competence_a, niveau=4)
        self.assertEqual(
            employes_avec_competence(self.company, [self.competence_a.pk]),
            {self.user.pk})
        self.assertEqual(
            employes_avec_competence(
                self.company, [self.competence_a.pk, self.competence_b.pk]),
            set())

    def test_niveau_min_respecte(self):
        CompetenceEmploye.objects.create(
            company=self.company, employe=self.dossier,
            competence=self.competence_a, niveau=2)
        self.assertEqual(
            employes_avec_competence(
                self.company, [self.competence_a.pk], niveau_min=2),
            {self.user.pk})
        self.assertEqual(
            employes_avec_competence(
                self.company, [self.competence_a.pk], niveau_min=3),
            set())

    def test_dossier_sans_compte_utilisateur_absent(self):
        dossier = DossierEmploye.objects.create(
            company=self.company, matricule='E-2', nom='Sans', prenom='User')
        CompetenceEmploye.objects.create(
            company=self.company, employe=dossier,
            competence=self.competence_a, niveau=4)
        self.assertEqual(
            employes_avec_competence(self.company, [self.competence_a.pk]),
            set())
