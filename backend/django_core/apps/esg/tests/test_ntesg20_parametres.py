"""NTESG20 — réglages ESG par société.

Ce que le test PROUVE :
  * la pondération du badge DOIT sommer à 100 — validé côté SERVEUR
    (``clean()``/``save()``), pas seulement à l'écran ;
  * modifier la pondération recalcule IMMÉDIATEMENT le badge de maturité
    (critère d'acceptation), sans redémarrage ni cache à invalider ;
  * le seuil de dérive (NTESG10) et le pilote ESG destinataire viennent du
    réglage de la société, avec repli sur les défauts historiques quand
    aucune ligne n'existe ;
  * l'écriture est réservée aux administrateurs ; la société vient de
    l'utilisateur, jamais du corps.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.esg import selectors, services
from apps.esg.models import (
    CatalogueIndicateurESG, ObjectifESGTrajectoire, ParametresESG,
)
from authentication.models import Company

User = get_user_model()

URL = '/api/django/esg/parametres-esg/'


def _api(user):
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
    return api


class ParametresESGTests(TestCase):
    def setUp(self):
        self.co = Company.objects.create(nom='ESG Co', slug='esg-co-ntesg20')
        self.admin = User.objects.create_user(
            username='ntesg20-admin', password='x', company=self.co,
            role_legacy='admin')
        self.membre = User.objects.create_user(
            username='ntesg20-membre', password='x', company=self.co,
            role_legacy='responsable')

    # ── validation serveur de la pondération ───────────────────────────────
    def test_ponderation_doit_sommer_a_100(self):
        reglages = ParametresESG(
            company=self.co,
            ponderation_badge_maturite={
                'couverture': 50, 'cibles': 25, 'trajectoire': 10})
        with self.assertRaises(ValidationError) as ctx:
            reglages.save()
        self.assertIn('100', str(ctx.exception))

    def test_ponderation_composante_inconnue_refusee(self):
        reglages = ParametresESG(
            company=self.co,
            ponderation_badge_maturite={
                'couverture': 50, 'cibles': 25, 'trajectoire': 20,
                'inventee': 5})
        with self.assertRaises(ValidationError) as ctx:
            reglages.save()
        self.assertIn('inventee', str(ctx.exception))

    def test_ponderation_composante_manquante_refusee(self):
        reglages = ParametresESG(
            company=self.co,
            ponderation_badge_maturite={'couverture': 100})
        with self.assertRaises(ValidationError) as ctx:
            reglages.save()
        self.assertIn('cibles', str(ctx.exception))

    def test_ponderation_vide_vaut_defauts(self):
        reglages = ParametresESG.objects.create(company=self.co)
        self.assertEqual(reglages.ponderation_badge_maturite, {})
        self.assertEqual(
            services.config_esg(self.co)['ponderation_badge_maturite'],
            ParametresESG.PONDERATION_DEFAUT)

    def test_ponderation_valide_acceptee(self):
        ParametresESG.objects.create(
            company=self.co,
            ponderation_badge_maturite={
                'couverture': 50, 'cibles': 25, 'trajectoire': 25})
        self.assertEqual(
            services.config_esg(self.co)['ponderation_badge_maturite'],
            {'couverture': 50, 'cibles': 25, 'trajectoire': 25})

    # ── défauts sans ligne ─────────────────────────────────────────────────
    def test_defauts_sans_ligne(self):
        config = services.config_esg(self.co)
        self.assertEqual(config['seuil_alerte_derive_pct'], 10)
        self.assertIsNone(config['pilote_esg'])
        self.assertEqual(config['frequence_reporting'], 'annuelle')
        self.assertEqual(
            config['ponderation_badge_maturite'],
            ParametresESG.PONDERATION_DEFAUT)

    def test_reglages_poses_sont_lus(self):
        ParametresESG.objects.create(
            company=self.co, seuil_alerte_derive_pct=25,
            pilote_esg=self.membre,
            frequence_reporting=ParametresESG.Frequence.MENSUELLE)
        config = services.config_esg(self.co)
        self.assertEqual(config['seuil_alerte_derive_pct'], 25)
        self.assertEqual(config['pilote_esg'], self.membre)
        self.assertEqual(config['frequence_reporting'], 'mensuelle')

    # ── effet IMMÉDIAT sur le badge (critère d'acceptation) ────────────────
    def test_ponderation_change_le_badge_immediatement(self):
        # Catalogue à 1 indicateur, doté d'une trajectoire ACTIVE : la
        # composante « trajectoire » vaut 100 %, la « couverture » 0 %.
        CatalogueIndicateurESG.objects.create(
            company=self.co, code='ENV-1', libelle='Émissions',
            pilier=CatalogueIndicateurESG.Pilier.ENVIRONNEMENT)
        ObjectifESGTrajectoire.objects.create(
            company=self.co, indicateur_code='ENV-1',
            valeur_reference=Decimal('100'), annee_reference=2024,
            valeur_cible=Decimal('50'), annee_cible=2030, actif=True)

        avant = selectors.badge_maturite_esg(self.co)
        self.assertEqual(
            avant['ponderation'], ParametresESG.PONDERATION_DEFAUT)

        # Tout le poids sur la trajectoire (la seule composante à 100 %).
        ParametresESG.objects.create(
            company=self.co,
            ponderation_badge_maturite={
                'couverture': 0, 'cibles': 0, 'trajectoire': 100})
        apres = selectors.badge_maturite_esg(self.co)

        self.assertEqual(apres['ponderation']['trajectoire'], 100)
        self.assertEqual(apres['score'], 100.0)
        self.assertNotEqual(apres['score'], avant['score'])

    # ── NTESG10 : seuil + destinataire ─────────────────────────────────────
    def test_seuil_de_derive_vient_du_reglage(self):
        from apps.esg.models import PeriodeReportingESG
        ParametresESG.objects.create(
            company=self.co, seuil_alerte_derive_pct=42)
        # Vraies dates (pas des chaînes) : `objects.create` ne recharge pas
        # l'instance, donc un `date_fin='2026-12-31'` resterait une `str` en
        # mémoire et le service casserait sur `.year`.
        periode = PeriodeReportingESG.objects.create(
            company=self.co, libelle='2026', date_debut=date(2026, 1, 1),
            date_fin=date(2026, 12, 31))
        # Aucun objectif : l'alerte ne part pas, mais elle a bien LU le seuil
        # de la société (pas d'exception, pas de défaut fixe imposé).
        self.assertEqual(services.alerter_derive_trajectoire(periode), [])
        self.assertEqual(
            services.config_esg(self.co)['seuil_alerte_derive_pct'], 42)

    # ── API ────────────────────────────────────────────────────────────────
    def test_get_cree_la_ligne_a_la_demande(self):
        self.assertEqual(ParametresESG.objects.count(), 0)
        resp = _api(self.admin).get(URL)
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(resp.data['seuil_alerte_derive_pct'], 10)
        self.assertEqual(resp.data['frequence_reporting'], 'annuelle')
        self.assertEqual(ParametresESG.objects.count(), 1)
        self.assertEqual(
            ParametresESG.objects.get().company_id, self.co.id)

    def test_patch_admin(self):
        resp = _api(self.admin).patch(URL, {
            'seuil_alerte_derive_pct': 20,
            'ponderation_badge_maturite': {
                'couverture': 40, 'cibles': 30, 'trajectoire': 30},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.content)
        self.assertEqual(resp.data['seuil_alerte_derive_pct'], 20)
        self.assertEqual(
            services.config_esg(self.co)['ponderation_badge_maturite'],
            {'couverture': 40, 'cibles': 30, 'trajectoire': 30})

    def test_patch_non_admin_refuse(self):
        resp = _api(self.membre).patch(
            URL, {'seuil_alerte_derive_pct': 20}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_ponderation_invalide_400_nomme_le_champ(self):
        resp = _api(self.admin).patch(URL, {
            'ponderation_badge_maturite': {
                'couverture': 50, 'cibles': 25, 'trajectoire': 10},
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('ponderation_badge_maturite', resp.data)

    def test_pilote_d_une_autre_societe_refuse(self):
        autre = Company.objects.create(nom='Autre', slug='esg-autre-ntesg20')
        voisin = User.objects.create_user(
            username='ntesg20-voisin', password='x', company=autre,
            role_legacy='admin')
        resp = _api(self.admin).patch(
            URL, {'pilote_esg': voisin.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('pilote_esg', resp.data)

    def test_chaque_societe_a_ses_propres_reglages(self):
        autre = Company.objects.create(nom='Autre', slug='esg-autre2-ntesg20')
        voisin = User.objects.create_user(
            username='ntesg20-voisin2', password='x', company=autre,
            role_legacy='admin')
        _api(self.admin).patch(
            URL, {'seuil_alerte_derive_pct': 30}, format='json')
        resp = _api(voisin).get(URL)
        self.assertEqual(resp.data['seuil_alerte_derive_pct'], 10)
        self.assertEqual(
            services.config_esg(self.co)['seuil_alerte_derive_pct'], 30)
