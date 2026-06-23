"""U10 — Reset de l'escalade de relance au paiement intégral d'une facture.

Quand un paiement amène ``montant_du <= 0`` la facture passe « Payée », mais
le niveau d'escalade de relance (compteur de relances automatiques) et
``prochaine_relance`` n'étaient pas réinitialisés : une facture soldée pouvait
continuer d'afficher un ancien niveau de retard et le scheduler reprenait la
séquence là où elle s'était arrêtée.

Couvre :
  * payer intégralement une facture « en retard » la passe « Payée », efface
    ``prochaine_relance`` et neutralise les relances automatiques consignées
    (l'historique est conservé, juste marqué résolu) ;
  * le scheduler repart alors du PREMIER niveau (escalade remise à zéro) ;
  * un paiement PARTIEL ne réinitialise rien ;
  * le service ``reset_relance_escalation`` est idempotent et conserve les
    RelanceLog (jamais supprimés).

Run :
    python manage.py test apps.ventes.tests.test_relance_reset -v 2
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import (
    Facture, FollowupLevel, LigneFacture, RelanceLog,
)
from apps.ventes.services import (
    RELANCE_AUTO_NOTE, RELANCE_AUTO_NOTE_RESOLUE, reset_relance_escalation,
)

User = get_user_model()
LOCMEM = 'django.core.mail.backends.locmem.EmailBackend'


def make_company(slug='u10-co', nom='U10 Co'):
    from authentication.models import Company
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


@override_settings(EMAIL_BACKEND=LOCMEM)
class U10RelanceResetTests(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username='u10_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth(self.user)
        self.cl = Client.objects.create(
            company=self.company, nom='Débiteur', prenom='U10',
            email='u10@example.com', telephone='+212600000004')
        self.produit = Produit.objects.create(
            company=self.company, nom='Onduleur', sku='OND-U10',
            prix_vente=Decimal('5000'), quantite_stock=10, tva=Decimal('20.00'))
        for ordre, nom, delai in [(1, 'Rappel', 7), (2, 'Relance', 15),
                                  (3, 'Ferme', 30)]:
            FollowupLevel.objects.create(
                company=self.company, ordre=ordre, nom=nom, delai_jours=delai)
        # Facture EN RETARD, due 6000 TTC, échéance dépassée de 45 j.
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-U10-0001',
            client=self.cl, statut=Facture.Statut.EN_RETARD,
            taux_tva=Decimal('20.00'),
            date_echeance=date.today() - timedelta(days=45))
        LigneFacture.objects.create(
            facture=self.facture, produit=self.produit, designation='Onduleur',
            quantite=Decimal('1'), prix_unitaire=Decimal('5000'),
            taux_tva=Decimal('20.00'))

    def _escalate(self):
        """Simule une escalade en cours : 2 relances auto consignées + une
        prochaine relance programmée."""
        for _ in range(2):
            RelanceLog.objects.create(
                company=self.company, facture=self.facture,
                niveau=1, niveau_nom='Rappel', note=RELANCE_AUTO_NOTE)
        Facture.objects.filter(pk=self.facture.pk).update(
            prochaine_relance=date.today() + timedelta(days=3))
        self.facture.refresh_from_db()

    def _pay(self, montant):
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            f'enregistrer-paiement/',
            {'montant': montant, 'date_paiement': date.today().isoformat(),
             'mode': 'virement'}, format='json')

    def test_full_payment_resets_escalation(self):
        self._escalate()
        r = self._pay('6000')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'payee')
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.statut, Facture.Statut.PAYEE)
        # prochaine_relance effacée → plus de retard programmé.
        self.assertIsNone(self.facture.prochaine_relance)
        # Les relances auto ne sont plus comptées dans l'escalade…
        self.assertEqual(self.facture.relances.filter(
            note=RELANCE_AUTO_NOTE).count(), 0)
        # …mais l'historique est conservé (marqué résolu, jamais supprimé).
        self.assertEqual(self.facture.relances.filter(
            note=RELANCE_AUTO_NOTE_RESOLUE).count(), 2)

    def test_reset_clears_the_escalation_counter_the_scheduler_uses(self):
        # Le scheduler (relance_reminders) déduit le niveau courant du NOMBRE de
        # relances automatiques consignées : idx = min(deja, len(levels)-1).
        # Avant reset, 2 relances auto → le scheduler reprendrait au 3e niveau.
        self._escalate()
        self.assertEqual(self.facture.relances.filter(
            note=RELANCE_AUTO_NOTE).count(), 2)
        # Paiement intégral → reset : le compteur d'escalade retombe à 0, donc
        # une éventuelle nouvelle séquence repartirait du PREMIER niveau.
        self.assertEqual(self._pay('6000').status_code, 201)
        self.facture.refresh_from_db()
        self.assertEqual(self.facture.relances.filter(
            note=RELANCE_AUTO_NOTE).count(), 0)

    def test_partial_payment_does_not_reset(self):
        self._escalate()
        r = self._pay('1000')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data['statut'], 'en_retard')
        self.facture.refresh_from_db()
        # Rien réinitialisé : escalade et date intactes.
        self.assertIsNotNone(self.facture.prochaine_relance)
        self.assertEqual(self.facture.relances.filter(
            note=RELANCE_AUTO_NOTE).count(), 2)

    def test_reset_service_is_idempotent_and_preserves_history(self):
        self._escalate()
        # 1er reset.
        self.assertTrue(reset_relance_escalation(self.facture))
        self.facture.refresh_from_db()
        # 2e reset : rien à faire (date déjà nulle, plus de note auto).
        self.assertFalse(reset_relance_escalation(self.facture))
        # Les deux RelanceLog existent toujours (total inchangé).
        self.assertEqual(self.facture.relances.count(), 2)
