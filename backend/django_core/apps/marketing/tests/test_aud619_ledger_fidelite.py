"""AUD619 — doctrine D9 (fondateur) : ``MouvementFidelite`` est un LEDGER.

DELETE interdit ; une correction s'écrit en mouvement de sens INVERSE ; le
solde reste TOUJOURS recalculable depuis le registre.

Constat d'origine : ``MouvementFideliteViewSet`` n'surchargeait que
``perform_create`` — le routeur standard exposait donc un DELETE qui ne
repassait JAMAIS par ``appliquer_mouvement_fidelite`` à rebours. La ligne
disparaissait et ``CompteFidelite.points`` restait figé sur une valeur ne
correspondant plus à aucun historique : un solde faux, indétectable et
irréparable.

Test ROUGE d'abord : ``test_delete_refuse_sur_un_mouvement`` recevait 204 et
laissait ``points`` divergent de Σ mouvements ; il attend désormais 405.
"""
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.compta import services
# Les deux modèles VIVENT dans marketing (compta.models ne fait que les
# ré-exporter) : on les importe donc chez eux, jamais via le ré-export.
from apps.marketing.models import CompteFidelite, MouvementFidelite

User = get_user_model()


def make_company(slug, nom):
    company, _ = Company.objects.get_or_create(
        slug=slug, defaults={'nom': nom})
    return company


def make_user(company, username, role='responsable'):
    return User.objects.create_user(
        username=username, password='x', company=company, role_legacy=role)


def auth(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class LedgerFideliteTests(TestCase):
    def setUp(self):
        self.co = make_company('aud619', 'AUD619')
        self.user = make_user(self.co, 'aud619-user')
        self.api = auth(self.user)
        self.compte = CompteFidelite.objects.create(
            company=self.co, client_id=61901)

    def _somme_ledger(self, compte=None):
        return MouvementFidelite.objects.filter(
            compte=compte or self.compte,
        ).aggregate(total=Sum('points'))['total'] or 0

    def _creer_mouvement(self, points, motif=''):
        resp = self.api.post('/api/django/marketing/mouvements-fidelite/', {
            'compte': self.compte.id, 'points': points, 'motif': motif,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        return resp.data['id']

    def test_delete_refuse_sur_un_mouvement(self):
        """ROUGE avant correctif : 204, et le solde restait divergent."""
        mouvement_id = self._creer_mouvement(300, 'Parrainage')
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.points, 300)

        resp = self.api.delete(
            f'/api/django/marketing/mouvements-fidelite/{mouvement_id}/')
        self.assertEqual(resp.status_code, 405, resp.content)

        # Ni la ligne ni le solde n'ont bougé — le registre est intact.
        self.assertTrue(
            MouvementFidelite.objects.filter(id=mouvement_id).exists())
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.points, self._somme_ledger())

    def test_le_refus_explique_la_correction_par_mouvement_inverse(self):
        mouvement_id = self._creer_mouvement(120)
        resp = self.api.delete(
            f'/api/django/marketing/mouvements-fidelite/{mouvement_id}/')
        self.assertIn('inverse', str(resp.data['detail']).lower())

    def test_correction_par_mouvement_inverse_laisse_solde_egal_somme(self):
        """La voie AUTORISÉE : corriger en écrivant l'inverse."""
        self._creer_mouvement(300, 'Crédit erroné')
        self._creer_mouvement(-300, 'Annulation du crédit erroné')

        self.compte.refresh_from_db()
        self.assertEqual(self._somme_ledger(), 0)
        self.assertEqual(self.compte.points, 0)
        # Les DEUX lignes restent au registre (traçabilité).
        self.assertEqual(
            MouvementFidelite.objects.filter(compte=self.compte).count(), 2)

    def test_delete_dun_mouvement_dune_autre_societe_reste_404(self):
        """Le scoping société passe AVANT le refus : jamais un 405 qui
        révélerait l'existence de la ligne d'un autre tenant."""
        autre = make_company('aud619-b', 'AUD619B')
        compte_autre = CompteFidelite.objects.create(
            company=autre, client_id=61902)
        mouvement = services.appliquer_mouvement_fidelite(
            compte_autre, points=50, motif='x')
        resp = self.api.delete(
            f'/api/django/marketing/mouvements-fidelite/{mouvement.id}/')
        self.assertEqual(resp.status_code, 404, resp.content)


class RecalculSoldeFideliteTests(TestCase):
    def setUp(self):
        self.co = make_company('aud619r', 'AUD619R')
        self.user = make_user(self.co, 'aud619r-user')
        self.api = auth(self.user)
        self.compte = CompteFidelite.objects.create(
            company=self.co, client_id=61903)

    def test_recalcul_repare_un_cache_divergent(self):
        """Le cas laissé par les DELETE d'avant le correctif : un solde figé
        que plus aucun historique ne justifie."""
        services.appliquer_mouvement_fidelite(
            self.compte, points=1000, motif='Achat')
        # On simule la divergence héritée (cache faux, ledger sain).
        CompteFidelite.objects.filter(id=self.compte.id).update(
            points=9999, palier='or')

        resp = self.api.post(
            f'/api/django/marketing/comptes-fidelite/{self.compte.id}/'
            f'recalculer-solde/', {}, format='json')
        self.assertEqual(resp.status_code, 200, resp.content)

        self.compte.refresh_from_db()
        self.assertEqual(self.compte.points, 1000)
        self.assertEqual(self.compte.palier, 'argent')  # 500–1999.

    def test_recalcul_egale_la_somme_des_mouvements(self):
        for points in (500, -200, 1300):
            services.appliquer_mouvement_fidelite(
                self.compte, points=points, motif='x')
        services.recalculer_solde_fidelite(self.compte)
        self.compte.refresh_from_db()
        somme = MouvementFidelite.objects.filter(
            compte=self.compte).aggregate(t=Sum('points'))['t']
        self.assertEqual(somme, 1600)
        self.assertEqual(self.compte.points, 1600)

    def test_recalcul_ne_descend_jamais_sous_zero(self):
        """Même plancher qu'à l'écriture — le résultat reste entièrement
        dérivable du registre, jamais path-dépendant."""
        services.appliquer_mouvement_fidelite(
            self.compte, points=-500, motif='x')
        services.recalculer_solde_fidelite(self.compte)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.points, 0)

    def test_recalcul_ignore_les_mouvements_dune_autre_societe(self):
        autre = make_company('aud619r-b', 'AUD619RB')
        compte_autre = CompteFidelite.objects.create(
            company=autre, client_id=61904)
        services.appliquer_mouvement_fidelite(
            compte_autre, points=7000, motif='x')
        services.appliquer_mouvement_fidelite(
            self.compte, points=250, motif='x')
        services.recalculer_solde_fidelite(self.compte)
        self.compte.refresh_from_db()
        self.assertEqual(self.compte.points, 250)

    def test_recalcul_dun_compte_dune_autre_societe_est_404(self):
        autre = make_company('aud619r-c', 'AUD619RC')
        compte_autre = CompteFidelite.objects.create(
            company=autre, client_id=61905)
        resp = self.api.post(
            f'/api/django/marketing/comptes-fidelite/{compte_autre.id}/'
            f'recalculer-solde/', {}, format='json')
        self.assertEqual(resp.status_code, 404, resp.content)
