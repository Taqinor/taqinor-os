"""Tests NTWFL18 — chatter du dossier + alerte d'échéance dépassée.

Acceptance criteria couverte : lier un objet au dossier crée une entrée de
chatter automatique, une note manuelle s'ajoute, un dossier en retard notifie
une seule fois par jour.
"""
import datetime

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from authentication.models import Company, CustomUser

from core import dossiers as dossiers_service
from core.events import dossier_echeance_depassee
from core.models import Dossier, DossierActivity
from core.views_dossiers import DossierViewSet

LIER = DossierViewSet.as_view({'post': 'lier'})
DELIER = DossierViewSet.as_view({'post': 'delier'})
NOTER = DossierViewSet.as_view({'post': 'noter'})
HISTORIQUE = DossierViewSet.as_view({'get': 'historique'})
DETAIL = DossierViewSet.as_view({'patch': 'partial_update'})

CIBLE = 'sav.ticket'


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username):
    user, _ = CustomUser.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@example.test', 'company': company})
    return user


def poster(user, **kwargs):
    requete = APIRequestFactory().post('/', kwargs, format='json')
    force_authenticate(requete, user=user)
    return requete


class ChatterDossierTests(TestCase):
    """Les gestes du dossier laissent une trace, jamais un non-évènement."""

    def setUp(self):
        self.company = make_company('ntwfl18-chatter', 'NTWFL18 Chatter')
        self.user = make_user(self.company, 'ntwfl18-user')
        self.dossier = Dossier.objects.create(
            company=self.company, titre='Onboarding grand compte',
            type_dossier=Dossier.TYPE_ONBOARDING_GRAND_COMPTE)

    def test_lier_puis_delier_ecrit_deux_entrees_automatiques(self):
        avant = self.dossier.activites.count()

        reponse = LIER(
            poster(self.user, cle_modele=CIBLE, object_id=42,
                   libelle='Ticket onduleur'),
            pk=self.dossier.pk)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(self.dossier.activites.count(), avant + 1)

        entree = self.dossier.activites.first()
        self.assertEqual(entree.kind, DossierActivity.KIND_LIEN)
        self.assertEqual(entree.user_id, self.user.id)
        self.assertEqual(entree.company_id, self.company.id)
        self.assertIn(CIBLE, entree.new_value)
        self.assertIn('42', entree.new_value)

        # Re-lier la MÊME cible n'ajoute PAS une seconde entrée.
        LIER(poster(self.user, cle_modele=CIBLE, object_id=42),
             pk=self.dossier.pk)
        self.assertEqual(self.dossier.activites.count(), avant + 1)

        reponse = DELIER(
            poster(self.user, cle_modele=CIBLE, object_id=42),
            pk=self.dossier.pk)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(self.dossier.activites.count(), avant + 2)
        detache = self.dossier.activites.first()
        self.assertEqual(detache.kind, DossierActivity.KIND_LIEN)
        self.assertIn(CIBLE, detache.old_value)
        self.assertEqual(detache.new_value, '')

    def test_note_manuelle_sajoute_et_une_note_vide_est_refusee(self):
        avant = self.dossier.activites.count()

        reponse = NOTER(poster(self.user, body='  Client rappelé, RDV mardi '),
                        pk=self.dossier.pk)
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertEqual(self.dossier.activites.count(), avant + 1)
        note = self.dossier.activites.first()
        self.assertEqual(note.kind, DossierActivity.KIND_NOTE)
        self.assertEqual(note.body, 'Client rappelé, RDV mardi')
        self.assertEqual(note.user_id, self.user.id)

        reponse = NOTER(poster(self.user, body='   '), pk=self.dossier.pk)
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(self.dossier.activites.count(), avant + 1)

    def test_changement_de_statut_journalise_une_seule_fois(self):
        avant = self.dossier.activites.count()

        requete = APIRequestFactory().patch(
            '/', {'statut': Dossier.STATUT_EN_COURS}, format='json')
        force_authenticate(requete, user=self.user)
        reponse = DETAIL(requete, pk=self.dossier.pk)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(self.dossier.activites.count(), avant + 1)
        entree = self.dossier.activites.first()
        self.assertEqual(entree.kind, DossierActivity.KIND_MODIFICATION)
        self.assertEqual(entree.field, 'statut')
        self.assertEqual(entree.old_value, Dossier.STATUT_OUVERT)
        self.assertEqual(entree.new_value, Dossier.STATUT_EN_COURS)

        # Ré-envoyer la MÊME valeur n'écrit aucun non-évènement.
        requete = APIRequestFactory().patch(
            '/', {'statut': Dossier.STATUT_EN_COURS}, format='json')
        force_authenticate(requete, user=self.user)
        DETAIL(requete, pk=self.dossier.pk)
        self.assertEqual(self.dossier.activites.count(), avant + 1)

    def test_historique_est_antechronologique(self):
        dossiers_service.noter(self.dossier, 'Première', user=self.user)
        dossiers_service.noter(self.dossier, 'Seconde', user=self.user)

        requete = APIRequestFactory().get('/')
        force_authenticate(requete, user=self.user)
        reponse = HISTORIQUE(requete, pk=self.dossier.pk)
        self.assertEqual(reponse.status_code, 200)
        corps = [entree['body'] for entree in reponse.data]
        self.assertEqual(corps[:2], ['Seconde', 'Première'])


class EcheanceDepasseeTests(TestCase):
    """Un dossier en retard n'alerte qu'une fois par jour."""

    def setUp(self):
        self.company = make_company('ntwfl18-echeance', 'NTWFL18 Échéance')
        self.proprietaire = make_user(self.company, 'ntwfl18-proprietaire')
        self.aujourdhui = datetime.date(2026, 9, 19)
        self.hier = self.aujourdhui - datetime.timedelta(days=1)
        self.recus = []
        dossier_echeance_depassee.connect(
            self._capter, dispatch_uid='ntwfl18-test')
        self.addCleanup(dossier_echeance_depassee.disconnect,
                        self._capter, dispatch_uid='ntwfl18-test')

    def _capter(self, sender, dossier=None, **kwargs):
        self.recus.append(dossier)

    def _dossier(self, titre, echeance, statut=Dossier.STATUT_OUVERT):
        return Dossier.objects.create(
            company=self.company, titre=titre, echeance=echeance,
            statut=statut, proprietaire=self.proprietaire)

    def test_une_seule_alerte_par_jour_puis_relance_le_lendemain(self):
        en_retard = self._dossier('En retard', self.hier)

        alertes = dossiers_service.notifier_echeances_depassees(
            self.company, self.aujourdhui)
        self.assertEqual([d.pk for d in alertes], [en_retard.pk])
        self.assertEqual([d.pk for d in self.recus], [en_retard.pk])
        en_retard.refresh_from_db()
        self.assertEqual(en_retard.dernier_rappel_echeance_le,
                         self.aujourdhui)

        # Rejouer le MÊME jour n'émet plus rien.
        rejeu = dossiers_service.notifier_echeances_depassees(
            self.company, self.aujourdhui)
        self.assertEqual(rejeu, [])
        self.assertEqual(len(self.recus), 1)

        # Le lendemain, le dossier toujours en retard réalerte.
        demain = self.aujourdhui + datetime.timedelta(days=1)
        suite = dossiers_service.notifier_echeances_depassees(
            self.company, demain)
        self.assertEqual([d.pk for d in suite], [en_retard.pk])
        self.assertEqual(len(self.recus), 2)

    def test_dossier_clos_ou_a_echeance_future_jamais_alerte(self):
        self._dossier('Clos', self.hier, statut=Dossier.STATUT_CLOS)
        self._dossier('Abandonné', self.hier,
                      statut=Dossier.STATUT_ABANDONNE)
        self._dossier('Échéance du jour', self.aujourdhui)
        self._dossier('Sans échéance', None)

        alertes = dossiers_service.notifier_echeances_depassees(
            self.company, self.aujourdhui)
        self.assertEqual(alertes, [])
        self.assertEqual(self.recus, [])

    def test_une_autre_societe_nest_jamais_balayee(self):
        autre = make_company('ntwfl18-autre', 'NTWFL18 Autre')
        Dossier.objects.create(
            company=autre, titre='Retard voisin', echeance=self.hier)

        alertes = dossiers_service.notifier_echeances_depassees(
            self.company, self.aujourdhui)
        self.assertEqual(alertes, [])
        self.assertEqual(self.recus, [])
