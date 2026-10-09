"""ACHT26 (C-ACHT-024) — saisie du contrôle qualité d'assemblage validée
(`resultat` dans la liste, « pass » refusé hors tolérance, aucune saisie sur
un ordre terminé ou annulé — même garde pour les étapes) et forçage de
clôture tracé au chatter (motif + utilisateur).

Rejoue CKIT-11 (« banane » 200 ; pass 50 ouvre la clôture sans forcer ; QC
réécrit après clôture) et CKIT-12 (motif de forçage absent du chatter).

Run :
    powershell -File scripts/test-backend.ps1 -RestoreDb \
        -Modules "apps.installations.tests_acht_controle_qualite"
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.installations.models import (
    ControleQualiteItemModele, ControleQualiteModele, ControleQualiteOrdre,
    Kit, KitComposant, OrdreAssemblage,
)
from apps.stock.models import Produit

User = get_user_model()
BASE = '/api/django/installations/ordres-assemblage'


class ControleQualiteTests(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='co-acht26', defaults={'nom': 'Co ACHT26'})
        self.user = User.objects.create_user(
            username='resp-acht26', password='x', company=self.company,
            role_legacy='responsable')
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        coffret = Produit.objects.create(
            company=self.company, nom='Coffret', prix_vente=200,
            prix_achat=0, quantite_stock=0)
        disj = Produit.objects.create(
            company=self.company, nom='Disjoncteur', prix_vente=20,
            prix_achat=0, quantite_stock=100)
        self.kit = Kit.objects.create(
            company=self.company, nom='KA', produit_compose=coffret)
        KitComposant.objects.create(kit=self.kit, produit=disj, quantite=1)
        modele = ControleQualiteModele.objects.create(
            company=self.company, kit=self.kit, active=True)
        self.item = ControleQualiteItemModele.objects.create(
            modele=modele, libelle='Couple de serrage', ordre=1,
            valeur_min=1, valeur_max=10)
        self.ordre = OrdreAssemblage.objects.create(
            company=self.company, reference='ASM-ACHT26-1', kit=self.kit,
            quantite=1, statut=OrdreAssemblage.Statut.EN_COURS)
        self.api.get(f'{BASE}/{self.ordre.id}/controle-qualite/')

    def _qc(self, data, ordre=None):
        ordre = ordre or self.ordre
        return self.api.post(
            f'{BASE}/{ordre.id}/controle-qualite/{self.item.id}/', data,
            format='json')

    def _resultat(self, ordre=None):
        return ControleQualiteOrdre.objects.get(
            ordre=ordre or self.ordre, item_modele=self.item).resultat

    def test_resultat_hors_liste(self):
        r = self._qc({'resultat': 'banane'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('resultat', r.data)
        self.assertEqual(self._resultat(), 'en_attente')

    def test_pass_hors_tolerance_refuse(self):
        r = self._qc({'resultat': 'pass', 'valeur_mesuree': '50'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('Valeur 50 hors tolérance [1 ; 10] : enregistrez un '
                      'échec', str(r.data['resultat']))
        self.assertEqual(self._resultat(), 'en_attente')
        # La clôture non forcée reste bloquée.
        r = self.api.post(f'{BASE}/{self.ordre.id}/terminer/', {},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)

    def test_qc_apres_cloture_refuse(self):
        self._qc({'resultat': 'pass', 'valeur_mesuree': '5'})
        r = self.api.post(f'{BASE}/{self.ordre.id}/terminer/', {},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self._qc({'resultat': 'fail'})
        self.assertEqual(r.status_code, 400, r.data)
        self.assertEqual(self._resultat(), 'pass')

    def test_forcage_trace(self):
        self._qc({'resultat': 'fail'})
        r = self.api.post(f'{BASE}/{self.ordre.id}/terminer/', {
            'forcer': True, 'motif_forcage': 'client presse'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        r = self.api.get(f'{BASE}/{self.ordre.id}/historique/')
        self.assertEqual(r.status_code, 200)
        notes = [a for a in r.data if 'Clôture forcée malgré le contrôle '
                 'qualité : client presse' in (a.get('body') or '')]
        self.assertEqual(len(notes), 1)
        self.assertEqual(
            self.ordre.activites.filter(
                body__contains='client presse').first().user_id,
            self.user.id)
