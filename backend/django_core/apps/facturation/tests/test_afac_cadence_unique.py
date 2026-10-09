"""AFAC46 (C-AFAC-034 + C-AFAC-037) — UNE cadence de relance :
``prochain_niveau(facture)`` (journal ``RelanceLog.niveau`` effectif, tous
canaux et auteurs, un seul tri) sert l'aperçu, la liste des impayés, la
relance manuelle, la relance en masse et le beat ; ``amorcer_cadence`` ré-arme
une facture rouverte en retard après un rejet de paiement.

Rejoue les sondes FREC-5 (journal `[(3, manuel), (1, auto)]`) et FREC-2
(après rejet : `en_retard`, `prochaine_relance None`). APIClient + services et
beats réels, aucun mock.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \\
        -Modules "apps.facturation.tests.test_afac_cadence_unique"
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
_CTR = [0]
BASE = '/api/django/ventes/factures/'


def _nxt():
    _CTR[0] += 1
    return _CTR[0]


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CadenceUniqueTests(TestCase):
    def setUp(self):
        from apps.crm.models import Client
        from apps.ventes.recouvrement import ensure_default_followup_levels
        from apps.ventes.scheduled import casablanca_today
        from authentication.models import Company
        self.today = casablanca_today()
        self.company = Company.objects.create(
            nom='AFAC46 Co', slug=f'afac46-co-{_nxt()}')
        ensure_default_followup_levels(self.company)
        from apps.ventes.domain.recouvrement import niveaux_cadence
        self.niveaux = niveaux_cadence(self.company)
        self.assertEqual(len(self.niveaux), 3)
        self.admin = User.objects.create_user(
            username=f'afac46_admin_{_nxt()}', password='x',
            role_legacy='admin', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Cadence', prenom='AFAC46',
            email=f'afac46-{_nxt()}@example.invalid')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def _facture(self, statut='en_retard', **kw):
        from apps.ventes.models import Facture
        return Facture.objects.create(
            company=self.company, reference=f'FAC-AFAC46-{_nxt():04d}',
            client=self.client_obj, statut=statut, taux_tva=Decimal('20'),
            montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
            montant_ttc=Decimal('1200'),
            date_echeance=self.today - timedelta(days=40), **kw)

    def _a_relancer_aujourdhui(self, facture):
        type(facture).objects.filter(pk=facture.pk).update(
            prochaine_relance=self.today)

    def _apercu(self, facture):
        r = self.api.get(f'{BASE}{facture.id}/relance-apercu/')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def _ligne_impayes(self, facture):
        r = self.api.get('/api/django/ventes/relances/')
        self.assertEqual(r.status_code, 200, r.data)
        return next(x for x in r.data if x['id'] == facture.id)

    def test_manuel_niveau3_beat_n_envoie_pas_niveau1(self):
        from apps.ventes.models import RelanceLog
        from apps.ventes.scheduled import relance_reminders
        f = self._facture()
        dernier = self.niveaux[-1]
        r = self.api.post(f'{BASE}{f.id}/relancer/',
                          {'niveau': dernier.ordre}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(self._apercu(f)['deja_tous_envoyes'])
        self._a_relancer_aujourdhui(f)
        relance_reminders()
        # CLAUSE PERSISTANCE : le journal ne porte que la relance manuelle.
        self.assertEqual(
            list(RelanceLog.objects.filter(facture=f).values_list(
                'niveau', flat=True)), [dernier.ordre])

    def test_apercu_liste_beat_meme_niveau(self):
        from apps.ventes.models import RelanceLog
        from apps.ventes.scheduled import relance_reminders
        f = self._facture()
        RelanceLog.objects.create(
            company=self.company, facture=f, niveau=self.niveaux[0].ordre,
            niveau_nom=self.niveaux[0].nom, note='Relance par courrier')
        attendu = self.niveaux[1].ordre
        self.assertEqual(self._apercu(f)['niveau_suivant']['ordre'], attendu)
        self.assertEqual(
            self._ligne_impayes(f)['niveau_suivant']['ordre'], attendu)
        self._a_relancer_aujourdhui(f)
        relance_reminders()
        dernier_log = RelanceLog.objects.filter(facture=f).order_by('-id')[0]
        self.assertEqual(dernier_log.niveau, attendu)

    def test_rejet_rearme_cadence(self):
        from apps.ventes.domain.recouvrement import rejeter_paiement
        from apps.ventes.models import Facture, Paiement, RelanceLog
        from apps.ventes.scheduled import (
            check_overdue_factures, relance_reminders,
        )
        f = self._facture(prochaine_relance=self.today)
        relance_reminders()
        self.assertEqual(RelanceLog.objects.filter(facture=f).count(), 1)
        r = self.api.post(
            f'{BASE}{f.id}/enregistrer-paiement/',
            {'montant': '1200', 'date_paiement': str(self.today),
             'mode': 'cheque'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.PAYEE)
        rejeter_paiement(paiement=Paiement.objects.get(facture=f),
                         motif='Chèque impayé', user=self.admin)
        f.refresh_from_db()
        self.assertEqual(f.statut, Facture.Statut.EN_RETARD)
        self.assertEqual(
            f.prochaine_relance,
            f.date_echeance + timedelta(days=self.niveaux[0].delai_jours))
        check_overdue_factures()
        relance_reminders()
        logs = list(RelanceLog.objects.filter(facture=f).order_by('id'))
        self.assertEqual(len(logs), 2)
        # La séquence repart au niveau 1 (le solde a neutralisé la première).
        self.assertFalse(logs[0].compte_dans_cadence)
        self.assertEqual(logs[1].niveau, self.niveaux[0].ordre)

    def test_masse_predicat_et_niveau(self):
        from apps.ventes.models import RelanceLog
        payee = self._facture(statut='payee')
        emise = self._facture(statut='emise')
        r = self.api.post(f'{BASE}bulk/', {
            'action': 'relancer', 'ids': [payee.id, emise.id]},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertFalse(r.data[payee.id]['ok'])
        self.assertTrue(r.data[emise.id]['ok'])
        self.assertFalse(RelanceLog.objects.filter(facture=payee).exists())
        log = RelanceLog.objects.get(facture=emise)
        self.assertEqual(log.niveau, self.niveaux[0].ordre)
