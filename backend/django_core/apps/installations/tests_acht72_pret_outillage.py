"""ACHT72 (C-ACHT-068) — prêt d'outillage modélisé : cocher un outil à la
préparation le passe « En intervention » (409 s'il est Perdu, En réparation ou
déjà sorti) ; `confirmer-tool-return` ne traite que les outils sortis par CETTE
intervention et refuse une 2e confirmation (409).

Rejoue COUT-1 : A perdu et B en réparation redevenaient `disponible`, un retour
sans rien cocher passait D en `en_intervention`.

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht72_pret_outillage"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations import field_services
from apps.installations.models import Installation, Intervention
from apps.outillage.models import KitOutillage, KitOutillageItem, Outillage
from apps.stock.models import EmplacementStock

User = get_user_model()
BASE = '/api/django/installations/interventions'
S = Outillage.Statut


class PretOutillageTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht72', defaults={'nom': 'Co ACHT72'})
        self.user = User.objects.create_user(
            username='resp-acht72', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.depot = EmplacementStock.objects.create(
            company=self.company, nom='Dépôt')
        self.van = EmplacementStock.objects.create(
            company=self.company, nom='Van')
        self.outils = {}
        for nom, statut in (('A', S.PERDU), ('B', S.EN_REPARATION),
                            ('C', S.DISPONIBLE), ('D', S.DISPONIBLE),
                            ('E', S.DISPONIBLE)):
            self.outils[nom] = Outillage.objects.create(
                company=self.company, nom=nom, statut=statut,
                emplacement=self.depot)
        kit = KitOutillage.objects.create(
            company=self.company, nom='Kit', type_intervention='pose')
        for i, outil in enumerate(self.outils.values()):
            KitOutillageItem.objects.create(
                company=self.company, kit=kit, outil=outil, ordre=i)
        inst = Installation.objects.create(
            company=self.company, reference='CH-ACHT72')
        self.iv1 = self._iv(inst, kit)
        self.iv2 = self._iv(inst, kit)

    def _iv(self, inst, kit):
        iv = Intervention.objects.create(
            company=self.company, installation=inst,
            type_intervention='pose', created_by=self.user,
            technicien=self.user)
        prep = field_services.ensure_preparation(iv)
        prep.kit = kit
        prep.save()
        field_services._sync_outils(prep)
        return iv

    def _ligne(self, iv, nom):
        return iv.preparation.outils.get(outil=self.outils[nom])

    def _cocher(self, iv, nom, coche=True):
        return self.api.post(
            f'{BASE}/{iv.id}/cocher-outil/',
            {'ligne': self._ligne(iv, nom).id, 'coche': coche},
            format='json')

    def _statut(self, nom):
        o = Outillage.objects.get(pk=self.outils[nom].pk)
        return o.statut, o.emplacement_id

    def _scenario(self):
        for nom in ('C', 'E'):
            self.assertEqual(self._cocher(self.iv1, nom).status_code, 200)
        self.api.post(f'{BASE}/{self.iv1.id}/tool-return/', {},
                      format='json')
        lignes = {tr.outil.nom: tr for tr in self.iv1.tool_returns.all()}
        self.api.post(f'{BASE}/{self.iv1.id}/cocher-tool-return/', {
            'ligne': lignes['E'].id, 'rendu': True,
            'emplacement': self.van.id}, format='json')

    def test_retour_ne_ressuscite_pas_perdu(self):
        r = self._cocher(self.iv1, 'A')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Outil perdu', str(r.data))
        r = self._cocher(self.iv1, 'B')
        self.assertEqual(r.status_code, 409, r.data)
        self._scenario()
        r = self.api.post(f'{BASE}/{self.iv1.id}/confirmer-tool-return/', {},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(self._statut('A')[0], S.PERDU)
        self.assertEqual(self._statut('B')[0], S.EN_REPARATION)

    def test_confirmer_sans_cocher_ne_sort_rien(self):
        self._scenario()
        self.api.post(f'{BASE}/{self.iv1.id}/confirmer-tool-return/', {},
                      format='json')
        self.assertEqual(self._statut('D'), (S.DISPONIBLE, self.depot.id))
        self.assertEqual(self._statut('E'), (S.DISPONIBLE, self.van.id))
        statut_c, emplacement_c = self._statut('C')
        self.assertEqual(statut_c, S.EN_INTERVENTION)

    def test_double_pret_bloque(self):
        self._scenario()
        self.api.post(f'{BASE}/{self.iv1.id}/confirmer-tool-return/', {},
                      format='json')
        r = self.api.get(f'{BASE}/{self.iv2.id}/tool-return/')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['conflits'])
        self.assertIn(self.outils['C'].id,
                      [c['outil'] for c in r.data['conflits']])
        r = self._cocher(self.iv2, 'C')
        self.assertEqual(r.status_code, 409, r.data)

    def test_reconfirmation_refusee(self):
        self._scenario()
        url = f'{BASE}/{self.iv1.id}/confirmer-tool-return/'
        self.assertEqual(self.api.post(url, {}, format='json').status_code,
                         200)
        avant = {n: self._statut(n) for n in self.outils}
        r = self.api.post(url, {}, format='json')
        self.assertEqual(r.status_code, 409, r.data)
        self.assertIn('Retour déjà confirmé', str(r.data))
        self.assertEqual({n: self._statut(n) for n in self.outils}, avant)
