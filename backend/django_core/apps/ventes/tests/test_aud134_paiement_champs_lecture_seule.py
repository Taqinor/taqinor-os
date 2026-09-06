"""AUD134 — `PaiementSerializer` en `fields='__all__'` : `client`, `statut` et
`statut_affectation` restaient écrivables depuis le corps de l'encaissement.

`read_only_fields` ne déclarait que
`['company','created_by','date_creation','facture','escompte_montant']` —
`client`, `statut`, `statut_affectation`, `provider_ref`, `motif_rejet`,
`frais_rejet` et `date_rejet` restaient donc en écriture. L'action
`enregistrer-paiement` instancie `PaiementSerializer(data=request.data)` puis
`serializer.save(facture=…, company=…, created_by=…, escompte_montant=…)` :
tout champ non surchargé passait tel quel. Un encaissement pouvait donc être
enregistré avec `statut='rejete'` posé directement — contournant l'action
`rejeter` et sa permission — et un `client` pointant sur une AUTRE société.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.crm.models import Client
from apps.ventes.models import Facture, Paiement

User = get_user_model()


class TestAud134PaiementChampsLectureSeule(TestCase):
    def setUp(self):
        from authentication.models import Company
        self.company = Company.objects.get_or_create(
            slug='aud134-co', defaults={'nom': 'AUD134 Co'})[0]
        self.autre = Company.objects.get_or_create(
            slug='aud134-autre', defaults={'nom': 'AUD134 Autre'})[0]
        self.user = User.objects.create_user(
            username='aud134_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client AUD134',
            telephone='+212600000134')
        self.client_autre = Client.objects.create(
            company=self.autre, nom='Client autre société',
            telephone='+212600000135')
        self.facture = Facture.objects.create(
            company=self.company, reference='FAC-AUD134-0001',
            client=self.client_obj, statut=Facture.Statut.EMISE,
            taux_tva=Decimal('20.00'), libelle='Prestation',
            montant_ht=Decimal('10000.00'),
            date_echeance=date.today() + timedelta(days=30))
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def _enregistrer(self, **extra):
        corps = {
            'montant': '1000.00', 'mode': 'virement',
            'date_paiement': date.today().isoformat(),
        }
        corps.update(extra)
        return self.api.post(
            f'/api/django/ventes/factures/{self.facture.id}/'
            f'enregistrer-paiement/', corps, format='json')

    def test_statut_du_corps_est_ignore(self):
        """Poser `statut='rejete'` contournait l'action `rejeter` ET sa garde."""
        resp = self._enregistrer(statut='rejete')
        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.statut, Paiement.Statut.ENCAISSE)

    def test_champs_de_rejet_du_corps_sont_ignores(self):
        resp = self._enregistrer(
            motif_rejet='inventé', frais_rejet='250.00',
            date_rejet=date.today().isoformat())
        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.motif_rejet, '')
        self.assertEqual(paiement.frais_rejet or Decimal('0'), Decimal('0'))
        self.assertIsNone(paiement.date_rejet)

    def test_statut_affectation_du_corps_est_ignore(self):
        # XFAC1 — un règlement posé SUR une facture est `affecte` (défaut du
        # modèle). Le corps envoie donc la valeur CONTRAIRE : c'est le seul
        # moyen de prouver qu'il est ignoré (envoyer « affecte », comme avant,
        # ne distinguait rien du défaut serveur).
        resp = self._enregistrer(statut_affectation='non_affecte')
        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(
            paiement.statut_affectation,
            Paiement.StatutAffectation.AFFECTE)

    def test_client_du_corps_est_ignore(self):
        """Un `client` d'une AUTRE société ne doit jamais être posé."""
        resp = self._enregistrer(client=self.client_autre.id)
        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertIsNone(paiement.client_id)

    def test_provider_ref_du_corps_est_ignore(self):
        resp = self._enregistrer(provider_ref='psp_inventee')
        self.assertEqual(resp.status_code, 201, resp.data)
        paiement = Paiement.objects.get(facture=self.facture)
        self.assertEqual(paiement.provider_ref or '', '')

    def test_avance_refuse_un_client_d_une_autre_societe(self):
        resp = self.api.post(
            '/api/django/ventes/paiements/enregistrer-avance/',
            {'client': self.client_autre.id, 'montant': '500.00',
             'mode': 'virement', 'date_paiement': date.today().isoformat()},
            format='json')
        self.assertEqual(resp.status_code, 400, resp.data)
        self.assertFalse(
            Paiement.objects.filter(client=self.client_autre).exists())

    def test_avance_accepte_un_client_de_sa_societe(self):
        resp = self.api.post(
            '/api/django/ventes/paiements/enregistrer-avance/',
            {'client': self.client_obj.id, 'montant': '500.00',
             'mode': 'virement', 'date_paiement': date.today().isoformat()},
            format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(
            Paiement.objects.filter(client=self.client_obj).exists())

    def test_les_sept_champs_sont_declares_en_lecture_seule(self):
        from apps.ventes.serializers import PaiementSerializer
        champs = PaiementSerializer().fields
        for nom in ('client', 'statut', 'statut_affectation', 'provider_ref',
                    'motif_rejet', 'frais_rejet', 'date_rejet',
                    'company', 'created_by', 'facture', 'escompte_montant'):
            self.assertTrue(
                champs[nom].read_only, f'{nom} devrait être en lecture seule')
