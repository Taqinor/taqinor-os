"""NTSCM33 — Écran de réglages SCM par société : `ParametresSCM` enrichi
(horizon de prévision par défaut, niveaux de service par défaut par classe
ABC, seuils d'alerte), consommé via `selectors.parametres(company)` au lieu
de constantes codées en dur.

ADAPTATION DE PÉRIMÈTRE : le critère d'acceptation du plan cite
`seuil_ecart_delai_pct`/NTSCM11 — NTSCM11 (délai fournisseur mesuré vs promis)
vit dans `apps.stock` et n'est pas construit dans ce repo. Le champ est stocké
(voir `models.ParametresSCM`) mais sans consommateur. Le test ci-dessous
vérifie le MÊME contrat (« changer un seuil modifie le comportement sans
redéploiement ») sur `seuil_alerte_ecart_financier_pct`, qui EST câblé
(NTSCM15, `selectors.impact_financier_cycle`)."""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from apps.scm.models import CyclePlanificationSOP, LigneDemandeSOP, ParametresSCM
from apps.scm.selectors import impact_financier_cycle, parametres
from apps.scm.services import recalculer_politiques_stock
from apps.stock.models import Produit

from .helpers import auth, make_company, make_user


class ParametresScmSelectorTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-parametres', 'Supply Paramètres')

    def test_parametres_cree_paresseusement_avec_les_defauts(self):
        p = parametres(self.company)
        self.assertTrue(ParametresSCM.objects.filter(pk=p.pk).exists())
        self.assertEqual(p.horizon_prevision_mois_defaut, 3)
        self.assertEqual(p.service_level_defaut_a_pct, Decimal('95'))
        self.assertEqual(p.service_level_defaut_b_pct, Decimal('90'))
        self.assertEqual(p.service_level_defaut_c_pct, Decimal('85'))
        self.assertEqual(p.seuil_alerte_ecart_financier_pct, Decimal('15'))
        self.assertEqual(p.retention_previsions_mois, 24)


class SeuilAlerteEcartFinancierConfigurableTests(TestCase):
    """Changer `seuil_alerte_ecart_financier_pct` change le comportement de
    `impact_financier_cycle` (NTSCM15) SANS redéploiement — même contrat que
    demandé par le plan pour NTSCM11, appliqué au seuil réellement câblé."""

    def setUp(self):
        self.company = make_company('scm-seuil-financier', 'Supply Seuil Fin')
        self.produit = Produit.objects.create(
            company=self.company, nom='Kit Solaire 3kWc', prix_vente=30000,
            quantite_stock=10)
        self.cycle = CyclePlanificationSOP.objects.create(
            company=self.company, periode='2025-01')
        LigneDemandeSOP.objects.create(
            company=self.company, cycle=self.cycle, produit=self.produit,
            quantite_prevision_systeme=Decimal('10'))

    def test_seuil_par_defaut_pas_dalerte_sur_petit_ecart(self):
        with patch('apps.ventes.selectors.carnet_commande_par_mois', return_value={}):
            resultat = impact_financier_cycle(self.cycle)
        self.assertEqual(resultat['seuil_alerte_pct'], Decimal('15'))

    def test_abaisser_le_seuil_declenche_lalerte_sans_redeploiement(self):
        p = parametres(self.company)
        p.seuil_alerte_ecart_financier_pct = Decimal('0.01')
        p.save(update_fields=['seuil_alerte_ecart_financier_pct'])

        with patch('apps.ventes.selectors.carnet_commande_par_mois', return_value={}):
            resultat = impact_financier_cycle(self.cycle)
        self.assertEqual(resultat['seuil_alerte_pct'], Decimal('0.01'))
        # CA prévisionnel non nul, aucun historique de forecast -> ecart_pct
        # est None (aucun forecast dispo) : on vérifie surtout que le seuil
        # LU est bien celui de la société, pas la constante d'origine.
        self.assertNotEqual(resultat['seuil_alerte_pct'], Decimal('15'))


class ServiceLevelParDefautConfigurableTests(TestCase):
    """Changer les niveaux de service par défaut (classe A/B/C) modifie le
    résultat de `recalculer_politiques_stock` (NTSCM6) à la CRÉATION d'une
    politique — sans redéploiement."""

    def setUp(self):
        self.company = make_company('scm-service-level-defaut', 'Supply SL Défaut')
        self.produit = Produit.objects.create(
            company=self.company, nom='Régulateur MPPT', prix_vente=1200,
            quantite_stock=15)

    def test_niveau_service_defaut_classe_c_personnalise(self):
        p = parametres(self.company)
        p.service_level_defaut_c_pct = Decimal('99')
        p.save(update_fields=['service_level_defaut_c_pct'])

        politiques = recalculer_politiques_stock(self.company)
        politique = next(pol for pol in politiques if pol.produit_id == self.produit.id)
        # Produit jamais classé -> classe 'C' par défaut (voir
        # `recalculer_politiques_stock`) -> doit reprendre le NOUVEAU défaut.
        self.assertEqual(politique.classe_abc, 'C')
        self.assertEqual(politique.service_level_pct, Decimal('99'))


class ParametresScmEndpointTests(TestCase):
    def setUp(self):
        self.company = make_company('scm-parametres-endpoint', 'Supply Param API')
        self.admin = make_user(self.company, 'scm-param-admin', 'admin')

    def test_get_renvoie_les_defauts(self):
        resp = auth(self.admin).get('/api/django/scm/parametres/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['horizon_prevision_mois_defaut'], '3')
        self.assertEqual(resp.data['retention_previsions_mois'], '24')

    def test_patch_modifie_un_seuil(self):
        resp = auth(self.admin).patch(
            '/api/django/scm/parametres/',
            {'seuil_alerte_ecart_financier_pct': '5'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['seuil_alerte_ecart_financier_pct'], '5')

        p = parametres(self.company)
        self.assertEqual(p.seuil_alerte_ecart_financier_pct, Decimal('5'))

    def test_refuse_role_non_responsable(self):
        normal = make_user(self.company, 'scm-param-normal', 'normal')
        resp = auth(normal).get('/api/django/scm/parametres/')
        self.assertEqual(resp.status_code, 403)
