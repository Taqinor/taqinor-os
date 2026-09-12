"""CHT4 — verrou anti-course + atomicité de la décision d'étape d'achat.

``_decider_etape_approbation_achat`` lisait-puis-écrivait ``etape.statut``
sans transaction ni verrou de ligne : deux décisions concurrentes sur la même
étape pouvaient toutes les deux franchir la garde EN_ATTENTE. Et
``rejeter_etape_achat``/``approuver_etape_achat`` enchaînaient plusieurs
écritures hors transaction — un échec en cours de route (ex. la libération du
budget) laissait l'étape décidée mais la demande dans un état incohérent.

NOTE D'HONNÊTETÉ (patron ``tests_aud320_comptage_verrou.py``) : deux requêtes
réellement concurrentes ne sont pas reproductibles dans une ``TestCase`` (une
seule connexion, une transaction de test). On vérifie donc les deux choses
observables et suffisantes : (1) la relecture de l'étape porte bien un verrou
de ligne (``FOR UPDATE``) — sans lui la course reste ouverte ; (2) une
seconde décision sur une étape déjà tranchée est refusée (ROUGE avant le
correctif si l'appelant réutilise un objet Python périmé) ; (3) un échec en
aval (libération du budget) annule TOUT — l'étape reste EN_ATTENTE.

Run :
    python manage.py test apps.installations.tests_cht4_approbation_achat_verrou -v2
"""
import itertools
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from apps.installations import services
from apps.installations.models import (
    DemandeAchat, EtapeApprobationAchat, RegleApprobationAchat,
)
from authentication.models import Company

User = get_user_model()
_seq = itertools.count(1)


class BaseCht4(TestCase):
    def setUp(self):
        n = next(_seq)
        self.company = Company.objects.create(
            slug=f'cht4-co-{n}', nom=f'CHT4 Co {n}')
        self.demandeur = User.objects.create_user(
            username=f'cht4-demandeur-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.approbateur = User.objects.create_user(
            username=f'cht4-approbateur-{n}', password='x',
            role_legacy='admin', company=self.company)
        self.demande = DemandeAchat.objects.create(
            company=self.company, reference=f'DA-CHT4-{n}',
            objet='12 panneaux', statut=DemandeAchat.Statut.SOUMISE,
            created_by=self.demandeur)
        regle = RegleApprobationAchat.objects.create(
            company=self.company, libelle=f'Règle CHT4 {n}', actif=True,
            nombre_approbateurs=1)
        self.etape = EtapeApprobationAchat.objects.create(
            company=self.company, demande=self.demande, regle=regle,
            niveau=1, statut=EtapeApprobationAchat.Statut.EN_ATTENTE)


class TestVerrouDecisionEtape(BaseCht4):
    def test_la_relecture_de_l_etape_est_verrouillee(self):
        """ROUGE avant le correctif : aucun `FOR UPDATE` — deux décisions
        concurrentes pouvaient toutes les deux franchir la garde."""
        if not connection.features.has_select_for_update:  # pragma: no cover
            self.skipTest('Le moteur de base ne supporte pas SELECT FOR UPDATE.')
        table = EtapeApprobationAchat._meta.db_table
        with CaptureQueriesContext(connection) as ctx:
            services.approuver_etape_achat(
                self.etape, approbateur=self.approbateur)
        verrous = [q['sql'] for q in ctx.captured_queries
                   if 'FOR UPDATE' in q['sql'].upper() and table in q['sql']]
        self.assertTrue(
            verrous,
            "_decider_etape_approbation_achat relit l'étape SANS verrou de "
            'ligne : deux décisions concurrentes peuvent toutes les deux '
            'franchir la garde EN_ATTENTE.')

    def test_une_seule_decision_gagne(self):
        """Une étape déjà tranchée refuse toute nouvelle décision — même
        rejouée sur l'objet Python d'origine (retry, double-clic)."""
        services.approuver_etape_achat(
            self.etape, approbateur=self.approbateur)
        with self.assertRaises(services.ApprobationAchatError):
            services.approuver_etape_achat(
                self.etape, approbateur=self.approbateur)
        self.etape.refresh_from_db()
        self.assertEqual(
            self.etape.statut, EtapeApprobationAchat.Statut.APPROUVE)


class TestAtomiciteDecisionEtape(BaseCht4):
    def test_echec_liberation_budget_laisse_l_etape_en_attente(self):
        """Le rejet enchaîne décision d'étape + transition de la demande +
        libération du budget : si cette dernière échoue, TOUT est annulé."""
        with patch.object(services, 'liberer_budget_demande_achat',
                          side_effect=RuntimeError('budget indisponible')):
            with self.assertRaises(RuntimeError):
                services.rejeter_etape_achat(
                    self.etape, approbateur=self.approbateur,
                    commentaire='Hors budget')
        self.etape.refresh_from_db()
        self.demande.refresh_from_db()
        self.assertEqual(
            self.etape.statut, EtapeApprobationAchat.Statut.EN_ATTENTE)
        self.assertEqual(self.demande.statut, DemandeAchat.Statut.SOUMISE)
        self.assertIsNone(self.demande.date_decision)

    def test_rejet_nominal_libere_le_budget_et_tranche_l_etape(self):
        services.rejeter_etape_achat(
            self.etape, approbateur=self.approbateur,
            commentaire='Hors budget')
        self.etape.refresh_from_db()
        self.demande.refresh_from_db()
        self.assertEqual(
            self.etape.statut, EtapeApprobationAchat.Statut.REJETE)
        self.assertEqual(self.demande.statut, DemandeAchat.Statut.REFUSEE)
