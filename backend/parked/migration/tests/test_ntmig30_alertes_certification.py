"""Tests NTMIG30 — alerte d'expiration de certification partenaire.

Critère d'acceptation : un partenaire dont la certification expire dans 30j
apparaît dans les alertes, un partenaire à jour n'apparaît pas.

Couvre aussi : le selector ``crm.selectors.certifications_expirantes`` exclut
un partenaire ``niveau_certification='aucun'`` et une certification déjà
expirée, la tâche Beat notifie UNE fois par jour (idempotence), et
l'isolation multi-société.

Run :
    python manage.py test apps.migration.tests.test_ntmig30_alertes_certification -v2
"""
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.crm import selectors as crm_selectors
from apps.crm.models import Partenaire
from apps.migration.tasks import alerter_certifications_expirantes
from apps.notifications.models import Notification

from ._base import make_admin, make_company


class Ntmig30SelectorTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig30-sel', 'NTMIG30 sel')

    def test_certification_expirant_sous_30_jours_apparait(self):
        partenaire = Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig30-token-1',
            niveau_certification=Partenaire.NiveauCertification.CERTIFIE,
            date_expiration_certification=(
                timezone.localdate() + timedelta(days=30)))
        resultat = list(crm_selectors.certifications_expirantes(
            self.company, within_days=60))
        self.assertEqual(resultat, [partenaire])

    def test_partenaire_a_jour_absent(self):
        """Une échéance lointaine (hors fenêtre) n'apparaît pas."""
        Partenaire.objects.create(
            company=self.company, nom='Intégrateur à jour',
            token_acces='ntmig30-token-2',
            niveau_certification=Partenaire.NiveauCertification.OR,
            date_expiration_certification=(
                timezone.localdate() + timedelta(days=400)))
        resultat = list(crm_selectors.certifications_expirantes(
            self.company, within_days=60))
        self.assertEqual(resultat, [])

    def test_niveau_aucun_exclu_meme_avec_echeance(self):
        Partenaire.objects.create(
            company=self.company, nom='Non certifié',
            token_acces='ntmig30-token-3',
            niveau_certification=Partenaire.NiveauCertification.AUCUN,
            date_expiration_certification=(
                timezone.localdate() + timedelta(days=5)))
        resultat = list(crm_selectors.certifications_expirantes(
            self.company, within_days=60))
        self.assertEqual(resultat, [])

    def test_certification_deja_expiree_exclue(self):
        """Rappel PRÉVENTIF seulement : une échéance ÉCHUE n'est pas re-signalée
        ici (visible directement sur l'annuaire NTMIG29)."""
        Partenaire.objects.create(
            company=self.company, nom='Expiré',
            token_acces='ntmig30-token-4',
            niveau_certification=Partenaire.NiveauCertification.CERTIFIE,
            date_expiration_certification=(
                timezone.localdate() - timedelta(days=3)))
        resultat = list(crm_selectors.certifications_expirantes(
            self.company, within_days=60))
        self.assertEqual(resultat, [])

    def test_sans_echeance_exclu(self):
        Partenaire.objects.create(
            company=self.company, nom='Sans échéance',
            token_acces='ntmig30-token-5',
            niveau_certification=Partenaire.NiveauCertification.PLATINE)
        resultat = list(crm_selectors.certifications_expirantes(
            self.company, within_days=60))
        self.assertEqual(resultat, [])


class Ntmig30AlertesBeatTests(TestCase):

    def setUp(self):
        self.company = make_company('ntmig30-beat', 'NTMIG30 beat')
        self.admin = make_admin(self.company, 'ntmig30-admin')

    def test_certification_expirant_notifie_une_fois(self):
        Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig30-token-6',
            niveau_certification=Partenaire.NiveauCertification.CERTIFIE,
            date_expiration_certification=(
                timezone.localdate() + timedelta(days=30)))
        resultat = alerter_certifications_expirantes()
        self.assertEqual(resultat['echeances'], 1)
        self.assertEqual(resultat['notifications'], 1)
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)

        # Deuxième exécution le même jour : aucune notification supplémentaire.
        alerter_certifications_expirantes()
        self.assertEqual(
            Notification.objects.filter(recipient=self.admin).count(), 1)

    def test_aucune_echeance_aucune_notification(self):
        resultat = alerter_certifications_expirantes()
        self.assertEqual(resultat['echeances'], 0)
        self.assertEqual(Notification.objects.count(), 0)

    def test_societe_isolee(self):
        autre = make_company('ntmig30-beat-bis', 'NTMIG30 beat bis')
        autre_admin = make_admin(autre, 'ntmig30-autre-admin')
        Partenaire.objects.create(
            company=self.company, nom='Intégrateur Atlas',
            token_acces='ntmig30-token-7',
            niveau_certification=Partenaire.NiveauCertification.CERTIFIE,
            date_expiration_certification=(
                timezone.localdate() + timedelta(days=10)))
        alerter_certifications_expirantes()
        self.assertEqual(
            Notification.objects.filter(recipient=autre_admin).count(), 0)
