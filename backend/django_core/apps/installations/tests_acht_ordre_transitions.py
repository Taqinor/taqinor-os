"""ACHT18 (C-ACHT-017) — table de transitions des ordres d'assemblage
(planifié → en cours → terminé ; planifié/en cours → annulé ; planifié →
terminé conservé) et de démontage (planifié → terminé), lue par `demarrer`,
`terminer` et `annuler`.

Rejoue CKIT-2 : terminer sur un annulé 200 (disjoncteurs −10, coffret +5) ;
demarrer sur un terminé 200 ; re-terminer qp=3 200.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_ordre_transitions"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    Kit, KitComposant, OrdreAssemblage, OrdreDemontage,
)
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/installations'
S = OrdreAssemblage.Statut


class OrdreTransitionsTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht18', defaults={'nom': 'Co ACHT18'})
        self.user = User.objects.create_user(
            username='resp-acht18', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.coffret = Produit.objects.create(
            company=self.company, nom='Coffret', prix_vente=200,
            prix_achat=0, quantite_stock=10)
        self.disj = Produit.objects.create(
            company=self.company, nom='Disjoncteur', prix_vente=20,
            prix_achat=0, quantite_stock=100)
        self.kit = Kit.objects.create(
            company=self.company, nom='KA', produit_compose=self.coffret)
        KitComposant.objects.create(kit=self.kit, produit=self.disj,
                                    quantite=2)
        self._n = 0

    def _ordre(self, statut, **extra):
        self._n += 1
        return OrdreAssemblage.objects.create(
            company=self.company, reference=f'ASM-ACHT18-{self._n}',
            kit=self.kit, quantite=5, statut=statut, **extra)

    def _post(self, ordre, action, data=None, base='ordres-assemblage'):
        return self.api.post(f'{BASE}/{base}/{ordre.id}/{action}/',
                             data or {}, format='json')

    def _stocks(self):
        self.disj.refresh_from_db()
        self.coffret.refresh_from_db()
        return (self.disj.quantite_stock, self.coffret.quantite_stock)

    def _assert_refus(self, ordre, action, data, message):
        avant = (ordre.statut, ordre.quantite_produite,
                 ordre.date_terminaison, self._stocks())
        r = self._post(ordre, action, data)
        self.assertEqual(r.status_code, 400, (action, r.data))
        self.assertIn(message, str(r.data))
        ordre.refresh_from_db()
        self.assertEqual((ordre.statut, ordre.quantite_produite,
                          ordre.date_terminaison, self._stocks()), avant)

    def test_matrice_refus_assemblage(self):
        annule = self._ordre(S.ANNULE, motif_annulation='x')
        self._assert_refus(annule, 'terminer', {},
                           'Ordre annulé : impossible de le terminer')
        self._assert_refus(annule, 'demarrer', {},
                           'Ordre annulé : impossible de le démarrer')
        self._assert_refus(annule, 'annuler', {'motif_annulation': 'y'},
                           "Ordre annulé : impossible de l'annuler")
        termine = self._ordre(S.TERMINE, quantite_produite=4,
                              stock_mouvemente=True)
        self._assert_refus(termine, 'demarrer', {},
                           'Ordre terminé : impossible de le démarrer')
        self._assert_refus(termine, 'terminer', {'quantite_produite': 3},
                           'Ordre terminé : impossible de le terminer')

    def test_planifie_terminer_accepte(self):
        ordre = self._ordre(S.PLANIFIE)
        r = self._post(ordre, 'terminer')
        self.assertEqual(r.status_code, 200, r.data)
        ordre.refresh_from_db()
        self.assertEqual(ordre.statut, S.TERMINE)
        self.assertEqual(self._stocks(), (90, 15))

    def test_chemin_nominal(self):
        ordre = self._ordre(S.PLANIFIE)
        self.assertEqual(self._post(ordre, 'demarrer').status_code, 200)
        self.assertEqual(self._post(ordre, 'terminer').status_code, 200)
        autre = self._ordre(S.PLANIFIE)
        self.assertEqual(self._post(autre, 'demarrer').status_code, 200)
        r = self._post(autre, 'annuler', {'motif_annulation': 'stop'})
        self.assertEqual(r.status_code, 200, r.data)

    def test_demontage_termine_refuse(self):
        ordre = OrdreDemontage.objects.create(
            company=self.company, reference='DSM-ACHT18', kit=self.kit,
            quantite=1, statut=OrdreDemontage.Statut.TERMINE,
            stock_mouvemente=True)
        avant = self._stocks()
        r = self._post(ordre, 'terminer', base='ordres-demontage')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Ordre terminé : impossible de le terminer',
                      str(r.data))
        self.assertEqual(self._stocks(), avant)
