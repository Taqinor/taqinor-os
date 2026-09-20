"""CAL218 — indicateurs calepinage du reporting : des compteurs EXACTS.

Le critère « Done » en trois points, tenu test par test :
  * l'agrégat rend des compteurs exacts sur un jeu de test ;
  * une période SANS donnée rend ZÉRO compteur — et surtout pas une
    estimation : moyenne, médiane et taux valent alors ``None``, jamais 0 ;
  * aucun écran ni aucune route neuve : les tuiles passent par le KPI fédéré
    qui existe déjà (``reports.kpi_federes``, ARC40).

Les modèles sont obtenus par ``apps.get_model`` : ce module ne fait aucun
import statique de ``apps.calepinage.models`` ni de ``apps.ventes.models`` —
la lecture métier passe par ``apps.calepinage.selectors`` (dans le code) et le
registre (dans les fixtures).
"""
from datetime import timedelta

from django.apps import apps as django_apps
from django.test import TestCase
from django.utils import timezone

from authentication.models import Company

from .calepinage_kpis import indicateurs_calepinage, kpi_calepinage


def modele(app, nom):
    return django_apps.get_model(app, nom)


def creer_calepinage(company, **champs):
    return modele('calepinage', 'Calepinage').objects.create(
        company=company, **champs)


def dater(instance, champ, valeur):
    """Force une date ``auto_now_add`` (impossible à poser à la création)."""
    type(instance).objects.filter(pk=instance.pk).update(**{champ: valeur})
    instance.refresh_from_db()
    return instance


class IndicateursCalepinageTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='rep-cal218-a', defaults={'nom': 'REP CAL218 A'})
        self.autre, _ = Company.objects.get_or_create(
            slug='rep-cal218-b', defaults={'nom': 'REP CAL218 B'})
        self.statuts = modele('calepinage', 'Calepinage').Statut

    def test_compteurs_par_statut_exacts_zero_compris(self):
        creer_calepinage(self.co, lead_id=1, titre='A')
        creer_calepinage(self.co, lead_id=2, titre='B')
        creer_calepinage(self.co, lead_id=3, titre='C',
                         statut=self.statuts.VALIDE)
        chiffres = indicateurs_calepinage(self.co)
        self.assertEqual(chiffres['total'], 3)
        self.assertEqual(chiffres['par_statut'][self.statuts.BROUILLON], 2)
        self.assertEqual(chiffres['par_statut'][self.statuts.VALIDE], 1)
        # Un statut déclaré mais sans aucun calepinage vaut 0 — un compteur
        # exact, pas un trou dans la table.
        self.assertEqual(chiffres['par_statut'][self.statuts.PERIME], 0)

    def test_kwc_somme_uniquement_ce_qui_a_ete_calcule(self):
        creer_calepinage(self.co, lead_id=1, titre='Calculé',
                         resultat={'kwc': 8.64, 'total_modules': 12})
        creer_calepinage(self.co, lead_id=2, titre='Calculé aussi',
                         resultat={'kwc': 1.36})
        creer_calepinage(self.co, lead_id=3, titre='Jamais calculé')
        chiffres = indicateurs_calepinage(self.co)
        self.assertEqual(chiffres['kwc_concus'], 10.0)
        self.assertEqual(chiffres['kwc_mesures'], 2)
        self.assertEqual(chiffres['total'], 3)

    def test_une_societe_ne_voit_jamais_les_chiffres_d_une_autre(self):
        creer_calepinage(self.co, lead_id=1, titre='À moi')
        creer_calepinage(self.autre, lead_id=2, titre='Pas à moi',
                         resultat={'kwc': 99.0})
        chiffres = indicateurs_calepinage(self.co)
        self.assertEqual(chiffres['total'], 1)
        self.assertEqual(chiffres['kwc_concus'], 0.0)

    def test_sans_societe_tout_est_vide(self):
        creer_calepinage(self.co, lead_id=1, titre='A')
        chiffres = indicateurs_calepinage(None)
        self.assertEqual(chiffres['total'], 0)

    # ── Période sans donnée : des zéros, JAMAIS une estimation ───────────────
    def test_periode_sans_donnee_rend_zero_compteur_et_aucune_moyenne(self):
        chiffres = indicateurs_calepinage(self.co)
        self.assertEqual(chiffres['total'], 0)
        self.assertEqual(chiffres['kwc_concus'], 0.0)
        self.assertEqual(chiffres['conversion_devis']['devis_signes'], 0)
        delai = chiffres['delai_conception_devis_jours']
        self.assertEqual(delai['echantillon'], 0)
        self.assertIsNone(delai['moyenne'])
        self.assertIsNone(delai['mediane'])
        self.assertIsNone(chiffres['conversion_devis']['taux_signature_pct'])

    def test_les_bornes_de_periode_sont_respectees(self):
        vieux = creer_calepinage(self.co, lead_id=1, titre='Vieux')
        dater(vieux, 'created_at', timezone.now() - timedelta(days=60))
        creer_calepinage(self.co, lead_id=2, titre='Récent')
        chiffres = indicateurs_calepinage(
            self.co, debut=timezone.now() - timedelta(days=7))
        self.assertEqual(chiffres['total'], 1)


class DelaiEtConversionTests(TestCase):
    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='rep-cal218-c', defaults={'nom': 'REP CAL218 C'})
        self.Devis = modele('ventes', 'Devis')
        self.client_a = modele('crm', 'Client').objects.create(
            company=self.co, nom='Client CAL218')

    def devis(self, reference, statut=None, jours_apres=2, base=None):
        devis = self.Devis.objects.create(
            company=self.co, reference=reference, client=self.client_a,
            **({'statut': statut} if statut else {}))
        depart = base or timezone.now()
        return dater(devis, 'date_creation', depart + timedelta(days=jours_apres))

    def test_delai_conception_devis_sur_les_dates_reelles(self):
        base = timezone.now() - timedelta(days=30)
        for index, jours in enumerate((2, 4, 9), start=1):
            cal = creer_calepinage(self.co, lead_id=index, titre=f'C{index}')
            dater(cal, 'created_at', base)
            cal.devis = self.devis(f'DEV-CAL218-{index}', jours_apres=jours,
                                   base=base)
            cal.save(update_fields=['devis'])
        delai = indicateurs_calepinage(self.co)['delai_conception_devis_jours']
        self.assertEqual(delai['echantillon'], 3)
        self.assertEqual(delai['mediane'], 4.0)
        self.assertEqual(delai['moyenne'], 5.0)

    def test_un_calepinage_sans_devis_ne_compte_dans_aucun_delai(self):
        creer_calepinage(self.co, lead_id=9, titre='Sans devis')
        chiffres = indicateurs_calepinage(self.co)
        self.assertEqual(
            chiffres['delai_conception_devis_jours']['echantillon'], 0)
        self.assertEqual(chiffres['conversion_devis']['avec_devis'], 0)

    def test_taux_de_signature_compte_les_devis_acceptes(self):
        signe = creer_calepinage(self.co, lead_id=1, titre='Signé')
        signe.devis = self.devis('DEV-CAL218-S',
                                 statut=self.Devis.Statut.ACCEPTE)
        signe.save(update_fields=['devis'])
        en_cours = creer_calepinage(self.co, lead_id=2, titre='En cours')
        en_cours.devis = self.devis('DEV-CAL218-E',
                                    statut=self.Devis.Statut.ENVOYE)
        en_cours.save(update_fields=['devis'])
        creer_calepinage(self.co, lead_id=3, titre='Sans devis')
        conversion = indicateurs_calepinage(self.co)['conversion_devis']
        self.assertEqual(conversion['avec_devis'], 2)
        self.assertEqual(conversion['devis_signes'], 1)
        self.assertEqual(conversion['taux_signature_pct'], 33.3)


class TuilesKpiFedereTests(TestCase):
    """Les chiffres arrivent par le KPI fédéré existant — aucun écran neuf."""

    def setUp(self):
        self.co, _ = Company.objects.get_or_create(
            slug='rep-cal218-d', defaults={'nom': 'REP CAL218 D'})

    def test_les_tuiles_ont_la_forme_normalisee_du_kpi_federe(self):
        creer_calepinage(self.co, lead_id=1, titre='A',
                         resultat={'kwc': 8.64})
        tuiles = kpi_calepinage(self.co)
        self.assertTrue(tuiles)
        for tuile in tuiles:
            self.assertIn('id', tuile)
            self.assertIn('label', tuile)
            self.assertIn('valeur', tuile)
        valeurs = {t['id']: t['valeur'] for t in tuiles}
        self.assertEqual(valeurs['calepinage_total'], 1)
        self.assertEqual(valeurs['calepinage_kwc_concus'], 8.64)
        # Aucun devis ⇒ aucun échantillon ⇒ AUCUNE tuile de délai : afficher
        # « 0 jour » se lirait comme une mesure.
        self.assertNotIn('calepinage_delai_devis_median', valeurs)

    def test_le_provider_est_declare_et_resolvable(self):
        from core import platform as core_platform

        providers = core_platform.kpi_providers(self.co)
        self.assertIn('apps.reporting.calepinage_kpis.kpi_calepinage',
                      providers)

    def test_module_desactive_aucune_tuile(self):
        from unittest import mock

        with mock.patch('core.feature_flags.modules_desactives',
                        return_value={'calepinage'}):
            self.assertEqual(kpi_calepinage(self.co), [])
