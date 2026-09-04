"""AUD124 — « Marquer payée » ne solde plus une facture sans encaissement,
sans motif ni trace.

Le geste ne vérifiait QUE le statut de départ : aucun contrôle de
``montant_du``, aucun motif, aucune écriture, aucun chatter. Or le
recouvrement filtre sur le STATUT (``ventes/recouvrement.py``
``.exclude(statut__in=['payee', …])``) et ``jours_retard`` retombe à 0 dès
que le statut vaut ``payee``, tandis que ``montant_du`` continue d'afficher
la totalité : une créance de 40 000 MAD disparaissait de la balance âgée
d'un clic, sans qu'aucun écran ne dise qui, quand ni pourquoi.

Trois tests ROUGES (sans motif → 400 ; résiduel au-dessus de la tolérance →
400 vers ``abandonner-solde`` ; le cas légitime doit produire exactement une
``FactureActivity`` nommant l'auteur et le motif), plus la permission
dédiée.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company
from apps.crm.models import Client
from apps.ventes.models import Facture, FactureActivity, Paiement

User = get_user_model()


def make_company(slug='aud124-co', nom='AUD124 Co'):
    return Company.objects.get_or_create(slug=slug, defaults={'nom': nom})[0]


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class TestAUD124MarquerPayee(TestCase):
    def setUp(self):
        self.company = make_company()
        self.admin = User.objects.create_user(
            username='aud124_admin', password='x', role_legacy='admin',
            company=self.company)
        self.api = auth(self.admin)
        self.cl = Client.objects.create(
            company=self.company, nom='Client', prenom='AUD124',
            email='aud124@example.com', telephone='+212600000124')

    def _facture(self, reference, ttc=Decimal('40000')):
        return Facture.objects.create(
            company=self.company, reference=reference, client=self.cl,
            statut=Facture.Statut.EMISE, taux_tva=Decimal('20.00'),
            montant_ht=ttc / Decimal('1.2'), montant_tva=ttc / Decimal('6'),
            montant_ttc=ttc)

    def _url(self, facture):
        return f'/api/django/ventes/factures/{facture.id}/marquer-payee/'

    def test_sans_motif_refuse(self):
        facture = self._facture('FAC-AUD124-0001')
        r = self.api.post(self._url(facture), {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        self.assertEqual(
            FactureActivity.objects.filter(facture=facture).count(), 0)

    def test_motif_vide_refuse(self):
        facture = self._facture('FAC-AUD124-0002')
        r = self.api.post(self._url(facture), {'motif': '   '},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

    def test_residuel_au_dessus_de_la_tolerance_redirige_vers_abandon(self):
        """Une créance de 40 000 MAD ne disparaît plus d'un clic."""
        facture = self._facture('FAC-AUD124-0003')
        self.assertEqual(facture.montant_du, Decimal('40000.00'))
        r = self.api.post(
            self._url(facture), {'motif': 'Le client dit avoir payé'},
            format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(r.data.get('action_attendue'), 'abandonner-solde')
        self.assertIn('abandonner-solde', r.data['detail'])
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)

    def test_cas_legitime_trace_exactement_une_activite(self):
        """Reste dû nul (règlement encaissé hors ERP, déjà saisi) : le geste
        passe, et laisse une trace nommant l'auteur ET le motif."""
        facture = self._facture('FAC-AUD124-0004', ttc=Decimal('12000'))
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('12000'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('0'))
        avant = FactureActivity.objects.filter(facture=facture).count()

        motif = 'Virement encaissé hors ERP, constaté au relevé'
        r = self.api.post(self._url(facture), {'motif': motif},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)

        nouvelles = FactureActivity.objects.filter(
            facture=facture, field='statut',
            field_label='Marquée payée (manuel)')
        self.assertEqual(nouvelles.count(), 1)
        self.assertEqual(
            FactureActivity.objects.filter(facture=facture).count(),
            avant + 1)
        trace = nouvelles.first()
        self.assertEqual(trace.user_id, self.admin.id)
        self.assertIn(self.admin.username, trace.body)
        self.assertIn(motif, trace.body)

    def test_residuel_sous_la_tolerance_societe_passe(self):
        """XFAC13 — une société qui tolère un écart de règlement peut solder
        les centimes restants (mais toujours avec motif et trace)."""
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.get(company=self.company)
        profile.tolerance_ecart_reglement = Decimal('1.00')
        profile.save(update_fields=['tolerance_ecart_reglement'])

        facture = self._facture('FAC-AUD124-0005', ttc=Decimal('12000'))
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('11999.50'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        facture.refresh_from_db()
        self.assertEqual(facture.montant_du, Decimal('0.50'))

        r = self.api.post(
            self._url(facture), {'motif': 'Écart de règlement de 0,50 MAD'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.PAYEE)

    def test_permission_dediee_distincte_de_l_edition_courante(self):
        """Le responsable édite les factures au quotidien, mais faire
        disparaître une créance de la balance âgée est un geste comptable."""
        responsable = User.objects.create_user(
            username='aud124_resp', password='x', role_legacy='responsable',
            company=self.company)
        facture = self._facture('FAC-AUD124-0006', ttc=Decimal('12000'))
        Paiement.objects.create(
            company=self.company, facture=facture,
            montant=Decimal('12000'), date_paiement=date.today(),
            mode=Paiement.Mode.VIREMENT)
        r = auth(responsable).post(
            self._url(facture), {'motif': 'Constaté au relevé'},
            format='json')
        self.assertEqual(r.status_code, 403, r.data)
        facture.refresh_from_db()
        self.assertEqual(facture.statut, Facture.Statut.EMISE)
        # Le responsable garde bien l'édition courante de la facture.
        r2 = auth(responsable).patch(
            f'/api/django/ventes/factures/{facture.id}/',
            {'note': 'edition courante'}, format='json')
        self.assertEqual(r2.status_code, 200, r2.data)
