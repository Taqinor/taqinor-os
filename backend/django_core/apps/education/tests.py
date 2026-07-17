"""Tests de l'app éducation (``apps.education``).

Fondations NTEDU1-3 ici (structure année/niveau/classe, famille/élève,
workflow d'inscription) — prérequis direct des tâches NTEDU4-8/12-14 de ce
lot, dont les tests dédiés sont ajoutés section par section au fil des
commits (une classe de tests par tâche, en dessous de ce module).
"""
from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from authentication.models import Company

from .models import (
    AnneeScolaire, Classe, Eleve, Famille, GrilleTarifaire, Inscription,
    Niveau, Presence, Remise, Seance)
from .services import affecter_classe, valider_inscription

User = get_user_model()


class EducationTestCaseMixin:
    def setUp(self):
        super().setUp()
        self.company, _ = Company.objects.get_or_create(
            slug='ecole-test', defaults={'nom': 'École Test'})
        self.user = User.objects.create_user(
            username='admin@ecole-test.ma', password='x', company=self.company)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.annee = AnneeScolaire.objects.create(
            company=self.company, libelle='2026-2027',
            date_debut=date(2026, 9, 1), date_fin=date(2027, 6, 30))
        self.niveau_cp = Niveau.objects.create(
            company=self.company, nom='CP', cycle=Niveau.Cycle.PRIMAIRE, ordre=1)
        self.niveau_ce1 = Niveau.objects.create(
            company=self.company, nom='CE1', cycle=Niveau.Cycle.PRIMAIRE, ordre=2)
        self.classe = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau_cp, nom='CP A', capacite_max=2)
        self.famille = Famille.objects.create(
            company=self.company, nom='Bennani',
            parent1_nom='Karim Bennani', parent1_whatsapp='+212600000000')


class FoundationTests(EducationTestCaseMixin, TestCase):
    def test_classe_effectif_vs_capacite(self):
        eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe)
        self.assertEqual(self.classe.effectif, 1)
        self.assertLess(self.classe.effectif, self.classe.capacite_max)
        self.assertEqual(eleve.statut, Eleve.Statut.PROSPECT)

    def test_eleve_radie_reste_consultable_mais_hors_liste_active(self):
        eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', statut=Eleve.Statut.RADIE)
        actifs = Eleve.objects.filter(company=self.company).exclude(
            statut__in=[Eleve.Statut.RADIE, Eleve.Statut.DIPLOME])
        self.assertNotIn(eleve, actifs)
        self.assertIn(eleve, Eleve.objects.filter(company=self.company))

    def test_inscription_validee_sur_classe_pleine_va_en_liste_attente(self):
        for i in range(2):
            Eleve.objects.create(
                company=self.company, famille=self.famille, nom='X',
                prenom=f'E{i}', classe=self.classe, statut=Eleve.Statut.INSCRIT)
        self.assertEqual(self.classe.effectif, 2)

        nouvel_eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Y', prenom='Z')
        inscription = Inscription.objects.create(
            company=self.company, eleve=nouvel_eleve,
            annee_scolaire=self.annee, classe_demandee=self.classe)
        affecter_classe(inscription, self.classe)
        inscription.refresh_from_db()
        self.assertEqual(inscription.statut, Inscription.Statut.LISTE_ATTENTE)
        self.assertEqual(inscription.position_liste_attente, 1)


class NTEDU4ReinscriptionMasseTests(EducationTestCaseMixin, TestCase):
    """NTEDU4 — réinscription annuelle en masse, idempotente."""

    def setUp(self):
        super().setUp()
        self.annee_cible = AnneeScolaire.objects.create(
            company=self.company, libelle='2027-2028',
            date_debut=date(2027, 9, 1), date_fin=date(2028, 6, 30),
            statut=AnneeScolaire.Statut.ARCHIVEE)
        self.classe_ce1 = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee_cible,
            niveau=self.niveau_ce1, nom='CE1 A', capacite_max=30)
        self.eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe, statut=Eleve.Statut.INSCRIT)

    def test_reinscription_masse_propose_niveau_superieur(self):
        from .services import reinscrire_en_masse

        result = reinscrire_en_masse(
            company=self.company, annee_source=self.annee,
            annee_cible=self.annee_cible)
        self.assertEqual(len(result['creees']), 1)
        inscription = result['creees'][0]
        self.assertEqual(inscription.classe_demandee, self.classe_ce1)
        self.assertEqual(inscription.statut, Inscription.Statut.EN_ATTENTE)

    def test_reinscription_masse_est_idempotente(self):
        from .services import reinscrire_en_masse

        reinscrire_en_masse(
            company=self.company, annee_source=self.annee,
            annee_cible=self.annee_cible)
        result = reinscrire_en_masse(
            company=self.company, annee_source=self.annee,
            annee_cible=self.annee_cible)
        self.assertEqual(len(result['creees']), 0)
        self.assertEqual(result['deja_existantes'], 1)
        self.assertEqual(
            Inscription.objects.filter(
                eleve=self.eleve, annee_scolaire=self.annee_cible).count(), 1)

    def test_endpoint_reinscription_masse_deux_fois_ne_duplique_pas(self):
        url = '/api/django/education/inscriptions/reinscription-masse/'
        payload = {
            'annee_source': self.annee.id, 'annee_cible': self.annee_cible.id}
        response1 = self.client.post(url, payload, format='json')
        self.assertEqual(response1.status_code, 200, response1.content)
        self.assertEqual(response1.data['creees'], 1)

        response2 = self.client.post(url, payload, format='json')
        self.assertEqual(response2.status_code, 200, response2.content)
        self.assertEqual(response2.data['creees'], 0)
        self.assertEqual(response2.data['deja_existantes'], 1)

    def test_confirmer_reinscription_bulk(self):
        from .services import reinscrire_en_masse

        result = reinscrire_en_masse(
            company=self.company, annee_source=self.annee,
            annee_cible=self.annee_cible)
        inscription_id = result['creees'][0].id

        url = '/api/django/education/inscriptions/confirmer-reinscription/'
        response = self.client.post(
            url, {'ids': [inscription_id]}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        inscription = Inscription.objects.get(pk=inscription_id)
        self.assertEqual(inscription.statut, Inscription.Statut.VALIDEE)


class NTEDU5ListeAttenteTests(EducationTestCaseMixin, TestCase):
    """NTEDU5 — liste d'attente : position FIFO + promotion automatique."""

    def setUp(self):
        super().setUp()
        self.inscrits = []
        for i in range(2):
            eleve = Eleve.objects.create(
                company=self.company, famille=self.famille, nom='X',
                prenom=f'E{i}', classe=self.classe, statut=Eleve.Statut.INSCRIT)
            inscription = Inscription.objects.create(
                company=self.company, eleve=eleve, annee_scolaire=self.annee,
                classe_demandee=self.classe, classe_affectee=self.classe,
                statut=Inscription.Statut.VALIDEE)
            self.inscrits.append((eleve, inscription))

        self.eleve_attente = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Attente',
            prenom='Un')
        self.inscription_attente = Inscription.objects.create(
            company=self.company, eleve=self.eleve_attente,
            annee_scolaire=self.annee, classe_demandee=self.classe)
        affecter_classe(self.inscription_attente, self.classe)

    def test_desinscription_promeut_le_suivant(self):
        from .services import desinscrire

        self.inscription_attente.refresh_from_db()
        self.assertEqual(
            self.inscription_attente.statut, Inscription.Statut.LISTE_ATTENTE)

        _, inscription_a_liberer = self.inscrits[0]
        desinscrire(inscription_a_liberer)

        self.inscription_attente.refresh_from_db()
        self.assertEqual(
            self.inscription_attente.statut, Inscription.Statut.VALIDEE)
        self.eleve_attente.refresh_from_db()
        self.assertEqual(self.eleve_attente.classe_id, self.classe.id)

    def test_endpoint_desinscrire_promeut_via_api(self):
        _, inscription_a_liberer = self.inscrits[0]
        url = (
            f'/api/django/education/inscriptions/{inscription_a_liberer.id}/'
            'desinscrire/')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200, response.content)

        self.inscription_attente.refresh_from_db()
        self.assertEqual(
            self.inscription_attente.statut, Inscription.Statut.VALIDEE)

    def test_endpoint_liste_attente_filtre_par_classe_triee_par_position(self):
        url = (
            '/api/django/education/inscriptions/liste-attente/'
            f'?classe={self.classe.id}')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.inscription_attente.id)
        self.assertEqual(response.data[0]['position_liste_attente'], 1)


class NTEDU6GrilleTarifaireTests(EducationTestCaseMixin, TestCase):
    """NTEDU6 — grille tarifaire : une seule ligne active par
    (annee_scolaire, niveau)."""

    def test_une_seule_grille_active_par_annee_niveau_en_base(self):
        from django.db import IntegrityError, transaction

        GrilleTarifaire.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau_cp, frais_inscription=500,
            scolarite_annuelle=12000)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GrilleTarifaire.objects.create(
                    company=self.company, annee_scolaire=self.annee,
                    niveau=self.niveau_cp, frais_inscription=600,
                    scolarite_annuelle=13000)

    def test_endpoint_refuse_doublon_en_400_pas_500(self):
        url = '/api/django/education/grilles-tarifaires/'
        response1 = self.client.post(url, {
            'annee_scolaire': self.annee.id, 'niveau': self.niveau_cp.id,
            'frais_inscription': '500', 'scolarite_annuelle': '12000',
        }, format='json')
        self.assertEqual(response1.status_code, 201, response1.content)

        response2 = self.client.post(url, {
            'annee_scolaire': self.annee.id, 'niveau': self.niveau_cp.id,
            'frais_inscription': '600', 'scolarite_annuelle': '13000',
        }, format='json')
        self.assertEqual(response2.status_code, 400, response2.content)


class NTEDU7RemiseFratrieTests(EducationTestCaseMixin, TestCase):
    """NTEDU7 — remise fratrie auto-détectée, toujours en brouillon."""

    def setUp(self):
        super().setUp()
        self.classe_libre = Classe.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau_cp, nom='CP B', capacite_max=30)

    def test_deuxieme_enfant_meme_famille_propose_remise_fratrie_brouillon(self):
        eleve1 = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine')
        inscription1 = Inscription.objects.create(
            company=self.company, eleve=eleve1, annee_scolaire=self.annee,
            classe_demandee=self.classe_libre)
        valider_inscription(inscription1, user=self.user)
        self.assertEqual(
            Remise.objects.filter(famille=self.famille).count(), 0,
            "un seul enfant inscrit : pas encore de remise fratrie")

        eleve2 = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Sami')
        inscription2 = Inscription.objects.create(
            company=self.company, eleve=eleve2, annee_scolaire=self.annee,
            classe_demandee=self.classe_libre)
        valider_inscription(inscription2, user=self.user)

        remises = Remise.objects.filter(
            famille=self.famille, type=Remise.Type.FRATRIE)
        self.assertEqual(remises.count(), 1)
        self.assertEqual(remises.first().statut, Remise.Statut.BROUILLON)

    def test_remise_fratrie_jamais_auto_appliquee_sans_validation(self):
        for prenom in ('Yasmine', 'Sami'):
            eleve = Eleve.objects.create(
                company=self.company, famille=self.famille, nom='Bennani',
                prenom=prenom)
            inscription = Inscription.objects.create(
                company=self.company, eleve=eleve, annee_scolaire=self.annee,
                classe_demandee=self.classe_libre)
            valider_inscription(inscription, user=self.user)

        remise = Remise.objects.get(
            famille=self.famille, type=Remise.Type.FRATRIE)
        self.assertEqual(remise.statut, Remise.Statut.BROUILLON)

        url = f'/api/django/education/remises/{remise.id}/approuver/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200, response.content)
        remise.refresh_from_db()
        self.assertEqual(remise.statut, Remise.Statut.APPROUVEE)


class NTEDU8EcheancierTests(EducationTestCaseMixin, TestCase):
    """NTEDU8 — échéancier de scolarité auto-généré à la validation."""

    def setUp(self):
        super().setUp()
        GrilleTarifaire.objects.create(
            company=self.company, annee_scolaire=self.annee,
            niveau=self.niveau_cp, frais_inscription=Decimal('500'),
            scolarite_annuelle=Decimal('12000'))

    def test_valider_inscription_genere_echeancier_complet(self):
        eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine')
        inscription = Inscription.objects.create(
            company=self.company, eleve=eleve, annee_scolaire=self.annee,
            classe_demandee=self.classe)
        valider_inscription(inscription, user=self.user)

        echeancier = eleve.echeanciers.get(annee_scolaire=self.annee)
        self.assertEqual(echeancier.lignes.count(), 10)
        self.assertEqual(echeancier.montant_total, Decimal('12500.00'))
        self.assertEqual(
            sum((ligne.montant for ligne in echeancier.lignes.all()),
                Decimal('0')),
            echeancier.montant_total)

    def test_generation_est_idempotente(self):
        from .services_echeancier import generer_echeancier

        eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine', classe=self.classe)
        e1 = generer_echeancier(eleve, self.annee)
        e2 = generer_echeancier(eleve, self.annee)
        self.assertEqual(e1.id, e2.id)

    def test_endpoint_echeancier_lecture_seule(self):
        eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='Bennani',
            prenom='Yasmine')
        inscription = Inscription.objects.create(
            company=self.company, eleve=eleve, annee_scolaire=self.annee,
            classe_demandee=self.classe)
        valider_inscription(inscription, user=self.user)
        echeancier = eleve.echeanciers.get(annee_scolaire=self.annee)

        url = f'/api/django/education/echeanciers/{echeancier.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.data['lignes']), 10)

        response_post = self.client.post(url, {}, format='json')
        self.assertEqual(response_post.status_code, 405)


class NTEDU12PresenceBulkTests(EducationTestCaseMixin, TestCase):
    """NTEDU12 — saisie de présence pour une classe entière en un seul appel."""

    def setUp(self):
        super().setUp()
        self.eleve1 = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='A', prenom='A',
            classe=self.classe)
        self.eleve2 = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='B', prenom='B',
            classe=self.classe)
        self.seance = Seance.objects.create(
            company=self.company, classe=self.classe, matiere='Maths',
            date=date(2026, 9, 15), heure_debut=time(8, 0), heure_fin=time(9, 0))

    def test_bulk_saisie_un_seul_appel_pour_toute_la_classe(self):
        url = '/api/django/education/presences/bulk-saisie/'
        response = self.client.post(url, {
            'seance': self.seance.id,
            'presences': [
                {'eleve': self.eleve1.id, 'statut': 'present'},
                {'eleve': self.eleve2.id, 'statut': 'absent'},
            ],
        }, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            Presence.objects.filter(seance=self.seance).count(), 2)
        self.assertEqual(
            Presence.objects.get(seance=self.seance, eleve=self.eleve2).statut,
            Presence.Statut.ABSENT)

    def test_bulk_saisie_est_un_upsert_rejouable(self):
        url = '/api/django/education/presences/bulk-saisie/'
        payload = {
            'seance': self.seance.id,
            'presences': [{'eleve': self.eleve1.id, 'statut': 'absent'}],
        }
        self.client.post(url, payload, format='json')
        payload['presences'][0]['statut'] = 'retard'
        self.client.post(url, payload, format='json')

        self.assertEqual(
            Presence.objects.filter(seance=self.seance).count(), 1)
        self.assertEqual(
            Presence.objects.get(seance=self.seance, eleve=self.eleve1).statut,
            Presence.Statut.RETARD)


class NTEDU13NotificationAbsenceTests(EducationTestCaseMixin, TestCase):
    """NTEDU13 — notification parent sur absence, anti-doublon par jour."""

    def setUp(self):
        super().setUp()
        self.eleve = Eleve.objects.create(
            company=self.company, famille=self.famille, nom='A', prenom='A',
            classe=self.classe)
        self.seance1 = Seance.objects.create(
            company=self.company, classe=self.classe, matiere='Maths',
            date=date(2026, 9, 15), heure_debut=time(8, 0), heure_fin=time(9, 0))
        self.seance2 = Seance.objects.create(
            company=self.company, classe=self.classe, matiere='Français',
            date=date(2026, 9, 15), heure_debut=time(10, 0), heure_fin=time(11, 0))

    def test_une_seule_notification_par_jour_meme_si_plusieurs_absences(self):
        from unittest.mock import patch

        with patch(
                'apps.notifications.services.send_whatsapp_campaign_message'
        ) as mocked:
            Presence.objects.create(
                company=self.company, seance=self.seance1, eleve=self.eleve,
                statut=Presence.Statut.ABSENT)
            Presence.objects.create(
                company=self.company, seance=self.seance2, eleve=self.eleve,
                statut=Presence.Statut.ABSENT)
            self.assertEqual(mocked.call_count, 1)

    def test_pas_de_notification_si_present(self):
        from unittest.mock import patch

        with patch(
                'apps.notifications.services.send_whatsapp_campaign_message'
        ) as mocked:
            Presence.objects.create(
                company=self.company, seance=self.seance1, eleve=self.eleve,
                statut=Presence.Statut.PRESENT)
            self.assertEqual(mocked.call_count, 0)
