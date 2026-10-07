"""AANA34 — `Idempotency-Key` sûre : longueur bornée et clé réservée AVANT
l'action.

Constat C-AANA-027 : une clé de 300 caractères faisait créer le lead PUIS
échouer la mémorisation (colonne de 255) en 500 — le client réessaie et crée
un doublon à chaque tentative ; deux POST concurrents portant la même clé
lisaient tous deux « clé neuve » et créaient deux leads.

``TransactionTestCase`` : les écritures sont réellement commitées (une
requête concurrente voit ce que l'autre a commité), vraie vue, vraie base,
vrai service CRM ; rien n'est mocké.

Run :
    python manage.py test apps.publicapi.tests_aana_idempotence -v2
"""
import threading

from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.crm.models import Lead
from authentication.models import Company

from .idempotency import LONGUEUR_MAX_CLE
from .models import ApiKey, IdempotencyRecord
from .portees import SCOPE_WRITE_LEADS

URL = '/api/public/v1/leads-write/'


class IdempotenceSureTest(TransactionTestCase):
    def setUp(self):
        self.co = Company.objects.create(slug='aana34-co', nom='AANA34')
        self.cle, self.brute = ApiKey.issue(
            company=self.co, label='ecriture', scopes=[SCOPE_WRITE_LEADS])

    def _post(self, corps, idem_key):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f'Api-Key {self.brute}')
        return api.post(URL, corps, format='json',
                        HTTP_IDEMPOTENCY_KEY=idem_key)

    def test_cle_trop_longue_400_sans_ecriture(self):
        self.assertEqual(LONGUEUR_MAX_CLE, 255)
        resp = self._post({'nom': 'Trop long'}, 'k' * 300)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Lead.objects.filter(company=self.co).exists())
        self.assertFalse(IdempotencyRecord.objects.exists())

    def test_cle_de_255_caracteres_acceptee(self):
        cle = 'k' * 255
        premier = self._post({'nom': 'Limite'}, cle)
        second = self._post({'nom': 'Limite'}, cle)
        self.assertEqual(premier.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(premier.data['id'], second.data['id'])
        self.assertEqual(Lead.objects.filter(company=self.co).count(), 1)

    def test_deux_post_concurrents_un_seul_lead(self):
        depart = threading.Barrier(2)
        statuts = []
        erreurs = []

        def envoyer():
            try:
                depart.wait(timeout=10)
                statuts.append(
                    self._post({'nom': 'Concurrent'}, 'meme-cle').status_code)
            except Exception as exc:  # noqa: BLE001 — remonté au test
                erreurs.append(exc)
            finally:
                connection.close()

        fils = [threading.Thread(target=envoyer) for _ in range(2)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join(timeout=30)
        self.assertEqual(erreurs, [])
        self.assertEqual(sorted(statuts), [201, 201])
        self.assertEqual(
            Lead.objects.filter(company=self.co, nom='Concurrent').count(), 1)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)

    def test_action_en_echec_libere_la_cle(self):
        # Un corps refusé (aucun nom) n'est pas mémorisé : la même clé reste
        # utilisable pour l'appel corrigé.
        refuse = self._post({}, 'cle-reutilisable')
        self.assertEqual(refuse.status_code, 400)
        self.assertFalse(IdempotencyRecord.objects.exists())
