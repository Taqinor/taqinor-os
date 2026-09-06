"""AUD131 — la cadence automatique ne démarrait jamais, l'action manuelle n'avait
aucune garde d'état.

(a) PAY-9 : `relance_reminders` sélectionne `prochaine_relance__lte=today`, or
    le SEUL site d'écriture non nulle hors de la tâche était l'action
    `relancer`, depuis le corps de la requête. Ni `check_overdue_factures`, ni
    l'émission, ni la bascule EN_RETARD ne posaient de date : la cadence
    « automatique » n'existait qu'APRÈS une première relance manuelle.

(b) PAY-18 : l'action `relancer` ne vérifiait ni `facture.statut` ni
    `montant_du` — contrairement au cron qui exclut payee/annulee/brouillon —
    le `niveau` reçu n'était pas validé, et `prochaine_relance` était affecté
    brut (une chaîne non-date remontait en erreur base, pas en 400).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, FollowupLevel, RelanceLog

User = get_user_model()


class _Base(TestCase):
    slug = 'aud131-co'

    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'AUD131 Co'})[0]
        self.user = User.objects.create_user(
            username=f'{self.slug}-resp', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Débiteur AUD131',
            email='aud131@example.com', telephone='+212600000131')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        mail.outbox = []

    def _facture(self, statut=Facture.Statut.EMISE, jours=40, reference=None):
        return Facture.objects.create(
            company=self.company,
            reference=reference or f'FAC-AUD131-{Facture.objects.count() + 1:04d}',
            client=self.client_obj, statut=statut,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal('1000.00'),
            date_echeance=date.today() - timedelta(days=jours))


class TestAud131CadenceDemarreSeule(_Base):
    """(a) La cadence doit démarrer SANS intervention humaine."""

    slug = 'aud131-cad'

    def test_bascule_en_retard_pose_la_prochaine_relance(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Rappel', delai_jours=7,
            message='Rappel amiable.')
        facture = self._facture(jours=40)
        self.assertIsNone(facture.prochaine_relance)

        from apps.ventes.scheduled import check_overdue_factures
        self.assertEqual(check_overdue_factures(), 1)

        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EN_RETARD)
        self.assertEqual(
            facture.prochaine_relance,
            facture.date_echeance + timedelta(days=7))

    def test_le_beat_relance_ensuite_sans_intervention_humaine(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Rappel', delai_jours=7,
            message='Rappel amiable pour {reference}.')
        facture = self._facture(jours=40)

        from apps.ventes.scheduled import (
            check_overdue_factures, relance_reminders,
        )
        check_overdue_factures()
        # AUCUNE relance manuelle n'a eu lieu entre les deux.
        self.assertFalse(RelanceLog.objects.filter(facture=facture).exists())
        self.assertEqual(relance_reminders(), 1)
        self.assertTrue(RelanceLog.objects.filter(facture=facture).exists())

    def test_sans_niveau_configure_aucune_date_n_est_posee(self):
        """Comportement actuel PRÉSERVÉ : pas de niveau ⇒ on ne pose rien."""
        facture = self._facture(jours=40)
        from apps.ventes.scheduled import check_overdue_factures
        check_overdue_factures()
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EN_RETARD)
        self.assertIsNone(facture.prochaine_relance)

    def test_une_date_deja_posee_n_est_jamais_ecrasee(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=0, nom='Rappel', delai_jours=7)
        deja = date.today() + timedelta(days=3)
        facture = self._facture(jours=40)
        facture.prochaine_relance = deja
        facture.save(update_fields=['prochaine_relance'])

        from apps.ventes.scheduled import check_overdue_factures
        check_overdue_factures()
        facture.refresh_from_db()
        self.assertEqual(facture.prochaine_relance, deja)


class TestAud131GardeEtatRelanceManuelle(_Base):
    """(b) L'action manuelle doit refuser ce que le cron exclut."""

    slug = 'aud131-garde'

    def _post(self, facture, body):
        return self.api.post(
            f'/api/django/ventes/factures/{facture.id}/relancer/',
            body, format='json')

    def test_relancer_une_facture_payee_est_refuse(self):
        facture = self._facture(statut=Facture.Statut.PAYEE)
        resp = self._post(facture, {'niveau': 1})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(RelanceLog.objects.filter(facture=facture).exists())

    def test_relancer_une_facture_annulee_est_refuse(self):
        facture = self._facture(statut=Facture.Statut.ANNULEE)
        resp = self._post(facture, {'niveau': 1})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_relancer_un_brouillon_est_refuse(self):
        facture = self._facture(statut=Facture.Statut.BROUILLON)
        resp = self._post(facture, {'niveau': 1})
        self.assertEqual(resp.status_code, 400, resp.data)

    def test_prochaine_relance_non_date_est_refusee_en_400(self):
        # Niveau VALIDE : seule la date doit être en cause dans le 400.
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel', delai_jours=7)
        facture = self._facture()
        resp = self._post(
            facture, {'niveau': 1, 'prochaine_relance': 'demain'})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertIn('prochaine_relance', resp.data)
        facture.refresh_from_db()
        self.assertIsNone(facture.prochaine_relance)

    def test_niveau_inconnu_est_refuse_en_400(self):
        """Le niveau était enregistré même quand `lvl` restait None."""
        facture = self._facture()
        resp = self._post(facture, {'niveau': 99})
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(RelanceLog.objects.filter(facture=facture).exists())

    def test_relance_valide_reste_acceptee(self):
        FollowupLevel.objects.create(
            company=self.company, ordre=1, nom='Rappel', delai_jours=7)
        facture = self._facture()
        nxt = (date.today() + timedelta(days=7)).isoformat()
        resp = self._post(
            facture, {'niveau': 1, 'note': 'Appel', 'prochaine_relance': nxt})
        self.assertEqual(resp.status_code, 200, resp.data)
        facture.refresh_from_db()
        self.assertEqual(facture.prochaine_relance.isoformat(), nxt)


class TestAud131PredicatPartage(_Base):
    """UN prédicat partagé par la vue, la liste des impayés et le beat."""

    slug = 'aud131-pred'

    def test_facture_relancable_aligne_les_trois_surfaces(self):
        from apps.ventes.recouvrement import facture_relancable

        due = self._facture()
        self.assertTrue(facture_relancable(due)[0])
        for statut in (Facture.Statut.PAYEE, Facture.Statut.ANNULEE,
                       Facture.Statut.BROUILLON):
            f = self._facture(statut=statut)
            ok, motif = facture_relancable(f)
            self.assertFalse(ok, statut)
            self.assertTrue(motif)

    def test_facture_soldee_n_est_pas_relancable(self):
        from apps.ventes.recouvrement import facture_relancable
        facture = self._facture()
        facture.abandon_montant = facture.total_ttc
        facture.save(update_fields=['abandon_montant'])
        self.assertEqual(facture.montant_du, Decimal('0'))
        self.assertFalse(facture_relancable(facture)[0])
