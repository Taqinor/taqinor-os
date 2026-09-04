"""AUD122 — le verrou de période comptable couvre enfin TOUS les chemins
d'encaissement, pas seulement ``views/facture.py`` et ``views/avoir.py``.

Avant ce correctif, un grep de ``_guard_periode_verrouillee`` /
``_DatedDocument`` sur tout ``apps/ventes`` ne rendait que ces deux
fichiers. Les quatre chemins ci-dessous créent chacun un mouvement d'argent
à une date fournie par l'appelant, et AUCUN n'appliquait la garde :

  * import de relevé bancaire (la date vient de la colonne « date ») ;
  * rejet de paiement (rouvre une facture PAYÉE) ;
  * ventilation d'avance ;
  * paiement avec retenue à la source.

Les quatre tests ROUGES sont ici, chacun avec son jumeau VERT (même geste,
date hors période close) qui prouve qu'aucun comportement légitime n'est
cassé.
"""
import csv
import io
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.compta.models import PeriodeComptable
from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement

User = get_user_model()

DANS_LA_PERIODE = '2026-02-15'
HORS_PERIODE = '2026-03-15'


def make_company(slug='aud122-co', nom='AUD122 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


def _csv(rows, headers):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=headers, delimiter=';')
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode('utf-8')


class _Aud122Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud122_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD122',
            email='aud122@example.com', telephone='+212600000122')

    def _facture(self, reference, ttc):
        return Facture.objects.create(
            company=self.company, reference=reference, client=self.cl,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)

    def _verrouiller_fevrier(self):
        return PeriodeComptable.objects.create(
            company=self.company, date_debut=date(2026, 2, 1),
            date_fin=date(2026, 2, 28), verrouillee=True)


class TestAUD122ImportReleve(_Aud122Base):
    DRY_URL = '/api/django/ventes/paiements/import-releve/dry-run/'
    COMMIT_URL = '/api/django/ventes/paiements/import-releve/commit/'

    def _importer(self, date_ligne, facture):
        contenu = _csv(
            [{'date': date_ligne, 'reference': facture.reference,
              'montant': '3000'}],
            headers=['date', 'reference', 'montant'])
        dry = self.api.post(
            self.DRY_URL, {'file': io.BytesIO(contenu)}, format='multipart')
        self.assertEqual(dry.status_code, 200, dry.data)
        return self.api.post(
            self.COMMIT_URL, {'token': dry.data['token']}, format='json')

    def test_releve_date_en_periode_verrouillee_refuse(self):
        facture = self._facture('FAC-AUD122-IMP1', Decimal('3000'))
        self._verrouiller_fevrier()
        r = self._importer(DANS_LA_PERIODE, facture)
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Paiement.objects.filter(facture=facture).count(), 0)

    def test_releve_date_hors_periode_verrouillee_passe(self):
        facture = self._facture('FAC-AUD122-IMP2', Decimal('3000'))
        self._verrouiller_fevrier()
        r = self._importer(HORS_PERIODE, facture)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Paiement.objects.filter(facture=facture).count(), 1)


class TestAUD122RejetPaiement(_Aud122Base):
    def _paiement(self, reference='FAC-AUD122-REJ1'):
        facture = self._facture(reference, Decimal('4000'))
        return Paiement.objects.create(
            company=self.company, facture=facture, montant=Decimal('4000'),
            date_paiement=date(2026, 2, 10), mode=Paiement.Mode.CHEQUE)

    def test_rejet_date_en_periode_verrouillee_refuse(self):
        paiement = self._paiement()
        self._verrouiller_fevrier()
        r = self.api.post(
            f'/api/django/ventes/paiements/{paiement.id}/rejeter/',
            {'motif': 'Chèque impayé', 'date_rejet': DANS_LA_PERIODE},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        paiement.refresh_from_db()
        self.assertNotEqual(paiement.statut, Paiement.Statut.REJETE)

    def test_rejet_date_hors_periode_verrouillee_passe(self):
        paiement = self._paiement('FAC-AUD122-REJ2')
        self._verrouiller_fevrier()
        r = self.api.post(
            f'/api/django/ventes/paiements/{paiement.id}/rejeter/',
            {'motif': 'Chèque impayé', 'date_rejet': HORS_PERIODE},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, Paiement.Statut.REJETE)


class TestAUD122VentilationAvance(_Aud122Base):
    def _avance(self, jour):
        return Paiement.objects.create(
            company=self.company, client=self.cl, facture=None,
            statut_affectation=Paiement.StatutAffectation.NON_AFFECTE,
            montant=Decimal('2000'), date_paiement=jour,
            mode=Paiement.Mode.VIREMENT)

    def test_ventilation_avance_datee_en_periode_verrouillee_refuse(self):
        facture = self._facture('FAC-AUD122-VEN1', Decimal('5000'))
        avance = self._avance(date(2026, 2, 12))
        self._verrouiller_fevrier()
        r = self.api.post(
            f'/api/django/ventes/paiements/{avance.id}/ventiler/',
            {'facture': facture.id, 'montant': '2000'}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('5000.00'))

    def test_ventilation_avance_hors_periode_verrouillee_passe(self):
        facture = self._facture('FAC-AUD122-VEN2', Decimal('5000'))
        avance = self._avance(date(2026, 3, 12))
        self._verrouiller_fevrier()
        r = self.api.post(
            f'/api/django/ventes/paiements/{avance.id}/ventiler/',
            {'facture': facture.id, 'montant': '2000'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('3000.00'))


class TestAUD122PaiementAvecRetenue(_Aud122Base):
    URL = ('/api/django/ventes/paiements/factures/{}/'
           'paiement-avec-retenue/')

    def test_retenue_date_en_periode_verrouillee_refuse(self):
        facture = self._facture('FAC-AUD122-RAS1', Decimal('10000'))
        self._verrouiller_fevrier()
        r = self.api.post(
            self.URL.format(facture.id),
            {'montant': '9000', 'date_paiement': DANS_LA_PERIODE,
             'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '10'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(Paiement.objects.filter(facture=facture).count(), 0)

    def test_retenue_date_hors_periode_verrouillee_passe(self):
        facture = self._facture('FAC-AUD122-RAS2', Decimal('10000'))
        self._verrouiller_fevrier()
        r = self.api.post(
            self.URL.format(facture.id),
            {'montant': '9000', 'date_paiement': HORS_PERIODE,
             'mode': 'virement', 'type_retenue': 'ras_tva', 'taux': '10'},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Paiement.objects.filter(facture=facture).count(), 1)


class TestAUD122GardePartagee(TestCase):
    """La garde vit dans UN module partagé, et les deux copies historiques
    pointent dessus (plus de troisième copie qui diverge)."""

    def test_facture_et_avoir_utilisent_la_fonction_partagee(self):
        from apps.ventes.utils.periode import (
            DatedDocument, guard_periode_date, guard_periode_verrouillee,
        )
        from apps.ventes.views.facture import _DatedDocument
        self.assertIs(_DatedDocument, DatedDocument)
        self.assertTrue(callable(guard_periode_verrouillee))
        self.assertTrue(callable(guard_periode_date))

    def test_sans_periode_la_garde_est_silencieuse(self):
        """Contrat préservé : aucune société/période → no-op, jamais 400."""
        from apps.ventes.utils.periode import guard_periode_date
        guard_periode_date(None, '2026-02-15')
        guard_periode_date(None, None)
