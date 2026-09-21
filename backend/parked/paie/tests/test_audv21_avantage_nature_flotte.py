"""Tests AUDV21/XFLT29 — Import des avantages en nature véhicule (flotte) en
éléments variables paie.

Couvre ``apps.paie.services.importer_avantages_nature_flotte(periode)`` :
- lit ``apps.flotte.selectors.avantages_en_nature`` en cross-app (jamais
  ``apps.flotte.models`` directement depuis ``services.py``) ;
- crée un ``ElementVariable`` (``source='flotte'``, rubrique ``AV_VOITURE``
  quand le catalogue de la société la porte) pour chaque conducteur en usage
  privé ayant un compte ERP ET un ``ProfilPaie`` actif ;
- une valeur nulle/zéro n'est jamais importée (rien à intégrer) ;
- un conducteur sans ``ProfilPaie`` (compte ERP sans dossier paie) est
  ignoré, jamais une erreur ;
- idempotent : un ré-import purge les anciens éléments ``source='flotte'`` de
  la période avant de recréer (pas de doublon), la saisie manuelle et
  l'import RH restent intacts ;
- refuse une période non brouillon (``TransitionPeriodeInterdite``) ;
- multi-tenant : n'importe jamais les avantages d'une autre société ;
- l'élément importé se reflète dans ``calculer_bulletin`` (brut imposable).
"""
import datetime
from decimal import Decimal

from django.test import TestCase

from authentication.models import Company
from apps.flotte.models import AffectationConducteur, Conducteur, Vehicule
from apps.paie.models import ElementVariable, PeriodePaie, ProfilPaie, Rubrique
from apps.paie.services import (
    TransitionPeriodeInterdite,
    calculer_bulletin,
    ensure_defaults,
    ensure_rubriques_standard,
    importer_avantages_nature_flotte,
)
from apps.rh.models import DossierEmploye


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_dossier(company, matricule='E1'):
    return DossierEmploye.objects.create(
        company=company, matricule=matricule, nom='Nom', prenom='Prenom')


def make_profil(company, dossier, salaire_base=Decimal('10000'), actif=True):
    return ProfilPaie.objects.create(
        company=company, employe=dossier,
        type_remuneration=ProfilPaie.TYPE_MENSUEL,
        salaire_base=salaire_base, affilie_cnss=True, affilie_amo=True,
        actif=actif)


def make_periode(company, annee=2026, mois=6):
    return PeriodePaie.objects.create(company=company, annee=annee, mois=mois)


def make_user_avec_dossier(company, username, dossier):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.create_user(
        username=username, password='x', company=company, role_legacy='normal')
    dossier.user = user
    dossier.save(update_fields=['user'])
    return user


def make_vehicule(company, immat):
    return Vehicule.objects.create(
        company=company, immatriculation=immat, energie='diesel')


def make_affectation_usage_prive(company, conducteur, vehicule, valeur,
                                 date_debut=datetime.date(2026, 1, 1),
                                 date_fin=None):
    return AffectationConducteur.objects.create(
        company=company, conducteur=conducteur, vehicule=vehicule,
        date_debut=date_debut, date_fin=date_fin,
        usage_prive=True, valeur_avantage_mensuelle=valeur)


# ── Import cross-app : cas nominal + garde-fous ─────────────────────────────

class ImporterAvantagesNatureFlotteTests(TestCase):
    def setUp(self):
        self.co = make_company('audv21-av')
        ensure_defaults(self.co)
        ensure_rubriques_standard(self.co)
        self.dossier = make_dossier(self.co, 'AV1')
        self.profil = make_profil(self.co, self.dossier)
        self.periode = make_periode(self.co, 2026, 6)
        self.user = make_user_avec_dossier(self.co, 'audv21-user', self.dossier)
        self.conducteur = Conducteur.objects.create(
            company=self.co, nom='Chauffeur Perso', user=self.user)
        self.vehicule = make_vehicule(self.co, 'AV-1')

    def test_import_cree_element_variable_rubrique_av_voiture(self):
        make_affectation_usage_prive(
            self.co, self.conducteur, self.vehicule, Decimal('800.00'))
        importes = importer_avantages_nature_flotte(self.periode)
        self.assertEqual(importes, 1)
        el = ElementVariable.objects.get(periode=self.periode)
        self.assertEqual(el.profil_id, self.profil.id)
        self.assertEqual(el.montant, Decimal('800.00'))
        self.assertEqual(el.source, ElementVariable.SOURCE_FLOTTE)
        self.assertEqual(el.type, ElementVariable.TYPE_PRIME)
        self.assertIsNotNone(el.rubrique_id)
        self.assertEqual(el.rubrique.code, 'AV_VOITURE')

    def test_sans_rubrique_catalogue_element_cree_sans_rubrique(self):
        """Catalogue non provisionné (ensure_rubriques_standard non lancé
        pour cette société) : l'élément se crée quand même, rubrique=None,
        jamais bloquant."""
        co2 = make_company('audv21-norub')
        ensure_defaults(co2)  # PAS ensure_rubriques_standard -> pas d'AV_VOITURE
        dossier2 = make_dossier(co2, 'AV2')
        make_profil(co2, dossier2)
        periode2 = make_periode(co2, 2026, 6)
        user2 = make_user_avec_dossier(co2, 'audv21-user2', dossier2)
        cond2 = Conducteur.objects.create(company=co2, nom='C2', user=user2)
        veh2 = make_vehicule(co2, 'AV-2')
        make_affectation_usage_prive(co2, cond2, veh2, Decimal('500.00'))

        self.assertFalse(
            Rubrique.objects.filter(company=co2, code='AV_VOITURE').exists())
        importes = importer_avantages_nature_flotte(periode2)
        self.assertEqual(importes, 1)
        el = ElementVariable.objects.get(periode=periode2)
        self.assertIsNone(el.rubrique_id)
        self.assertEqual(el.montant, Decimal('500.00'))

    def test_valeur_nulle_non_importee(self):
        # valeur_avantage_mensuelle défaut = 0.
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.conducteur, vehicule=self.vehicule,
            date_debut=datetime.date(2026, 1, 1), usage_prive=True)
        importes = importer_avantages_nature_flotte(self.periode)
        self.assertEqual(importes, 0)
        self.assertEqual(ElementVariable.objects.count(), 0)

    def test_sans_usage_prive_non_importe(self):
        AffectationConducteur.objects.create(
            company=self.co, conducteur=self.conducteur, vehicule=self.vehicule,
            date_debut=datetime.date(2026, 1, 1), usage_prive=False,
            valeur_avantage_mensuelle=Decimal('800'))
        importes = importer_avantages_nature_flotte(self.periode)
        self.assertEqual(importes, 0)

    def test_conducteur_sans_profil_paie_ignore(self):
        """Compte ERP conducteur sans dossier/profil paie -> ignoré, jamais
        une erreur."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_sans_profil = User.objects.create_user(
            username='audv21-sans-profil', password='x', company=self.co,
            role_legacy='normal')
        cond_sans_profil = Conducteur.objects.create(
            company=self.co, nom='Sans Profil', user=user_sans_profil)
        make_affectation_usage_prive(
            self.co, cond_sans_profil, self.vehicule, Decimal('600.00'))
        importes = importer_avantages_nature_flotte(self.periode)
        self.assertEqual(importes, 0)
        self.assertEqual(ElementVariable.objects.count(), 0)

    def test_conducteur_sans_compte_erp_ignore(self):
        """Conducteur externe (``user=None``) -> déjà filtré par le sélecteur
        flotte, jamais remonté ici."""
        cond_externe = Conducteur.objects.create(
            company=self.co, nom='Externe')
        make_affectation_usage_prive(
            self.co, cond_externe, self.vehicule, Decimal('600.00'))
        importes = importer_avantages_nature_flotte(self.periode)
        self.assertEqual(importes, 0)

    def test_idempotent_reimport_ne_duplique_pas(self):
        make_affectation_usage_prive(
            self.co, self.conducteur, self.vehicule, Decimal('800.00'))
        importer_avantages_nature_flotte(self.periode)
        importer_avantages_nature_flotte(self.periode)
        self.assertEqual(
            ElementVariable.objects.filter(
                periode=self.periode,
                source=ElementVariable.SOURCE_FLOTTE).count(),
            1)

    def test_reimport_preserve_saisie_manuelle(self):
        rub = Rubrique.objects.filter(company=self.co, code='TRANSPORT').first()
        manuel = ElementVariable.objects.create(
            company=self.co, periode=self.periode, profil=self.profil,
            type=ElementVariable.TYPE_PRIME, rubrique=rub, libelle='TRANSPORT',
            montant=Decimal('400'), source=ElementVariable.SOURCE_MANUEL)
        make_affectation_usage_prive(
            self.co, self.conducteur, self.vehicule, Decimal('800.00'))
        importer_avantages_nature_flotte(self.periode)
        importer_avantages_nature_flotte(self.periode)
        manuel.refresh_from_db()  # ne lève pas DoesNotExist.
        self.assertEqual(
            ElementVariable.objects.filter(periode=self.periode).count(), 2)

    def test_periode_non_brouillon_refuse(self):
        self.periode.statut = PeriodePaie.STATUT_CLOTUREE
        self.periode.save()
        make_affectation_usage_prive(
            self.co, self.conducteur, self.vehicule, Decimal('800.00'))
        with self.assertRaises(TransitionPeriodeInterdite):
            importer_avantages_nature_flotte(self.periode)

    def test_scope_societe(self):
        autre_co = make_company('audv21-av-b')
        ensure_defaults(autre_co)
        ensure_rubriques_standard(autre_co)
        dossier_b = make_dossier(autre_co, 'AVB1')
        make_profil(autre_co, dossier_b)
        periode_b = make_periode(autre_co, 2026, 6)
        user_b = make_user_avec_dossier(autre_co, 'audv21-user-b', dossier_b)
        cond_b = Conducteur.objects.create(
            company=autre_co, nom='Chauffeur B', user=user_b)
        veh_b = make_vehicule(autre_co, 'AV-B1')
        make_affectation_usage_prive(autre_co, cond_b, veh_b, Decimal('900.00'))

        # L'import de la période A ne remonte rien de la société B.
        make_affectation_usage_prive(
            self.co, self.conducteur, self.vehicule, Decimal('800.00'))
        importer_avantages_nature_flotte(self.periode)
        self.assertEqual(
            ElementVariable.objects.filter(periode=self.periode).count(), 1)
        importer_avantages_nature_flotte(periode_b)
        self.assertEqual(
            ElementVariable.objects.filter(periode=periode_b).count(), 1)


# ── Intégration : impact sur le bulletin calculé ────────────────────────────

class AvantageNatureFlotteBulletinIntegrationTests(TestCase):
    def setUp(self):
        self.co = make_company('audv21-bull')
        ensure_defaults(self.co)
        ensure_rubriques_standard(self.co)
        self.dossier = make_dossier(self.co, 'AVBULL1')
        self.profil = make_profil(self.co, self.dossier, Decimal('10000'))
        self.periode = make_periode(self.co, 2026, 6)
        self.user = make_user_avec_dossier(
            self.co, 'audv21-bull-user', self.dossier)
        self.conducteur = Conducteur.objects.create(
            company=self.co, nom='Chauffeur Bull', user=self.user)
        self.vehicule = make_vehicule(self.co, 'AVBULL-1')

    def test_avantage_importe_augmente_le_brut_imposable(self):
        """AV_VOITURE est imposable sans plafond (catalogue standard) : le
        montant importé s'ajoute intégralement au brut imposable."""
        make_affectation_usage_prive(
            self.co, self.conducteur, self.vehicule, Decimal('2000.00'))
        importer_avantages_nature_flotte(self.periode)
        res = calculer_bulletin(self.profil, self.periode)
        self.assertEqual(res['brut'], Decimal('12000.00'))
        self.assertEqual(res['brut_imposable'], Decimal('12000.00'))
