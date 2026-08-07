"""VAO8 — le SAS ``AvisMarche``.

Ce qui est vérifié ici :
  * le modèle est bien sur ``TenantModel`` (isolation multi-société réelle) ;
  * un avis dont la date limite est dépassée bascule seul en ``expire``,
    et un avis SANS date limite n'expire jamais ;
  * le lien vers l'appel d'offres est un ENTIER OPAQUE, jamais une FK ;
  * **aucun champ de coût ou de marge** n'existe sur le modèle — le sas
    décrit un avis public, pas une affaire chiffrée ;
  * aucune création automatique d'``AppelOffre`` (le sas ne connaît pas
    ``apps.ao``).
"""
import ast
import datetime as dt
from pathlib import Path

from django.db import models as django_models
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.veille_ao.models import (
    AvisMarche, CategorieAvis, SourceVeille, StatutAvis, TypeSource,
)
from authentication.models import Company
from core.models import TenantModel

MODELS_PATH = Path(__file__).resolve().parent.parent / 'models.py'


def creer_source(company, code='src'):
    return SourceVeille.objects.create(
        company=company, code=code, libelle='Source de test',
        type_source=TypeSource.PORTAIL_OFFICIEL,
        url_base='https://exemple.test', actif=True)


def creer_avis(company, source, **kwargs):
    params = {
        'company': company,
        'source': source,
        'objet': "Fourniture et installation de panneaux photovoltaïques",
        'acheteur': 'Commune de Test',
    }
    params.update(kwargs)
    return AvisMarche.objects.create(**params)


class SocleMultiTenantTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Avis')
        cls.autre = Company.objects.create(nom='Autre Avis')

    def test_modele_herite_de_tenant_model(self):
        self.assertTrue(issubclass(AvisMarche, TenantModel))

    def test_isolation_entre_societes(self):
        creer_avis(self.company, creer_source(self.company))
        creer_avis(self.autre, creer_source(self.autre))
        self.assertEqual(
            AvisMarche.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            AvisMarche.objects.filter(company=self.autre).count(), 1)

    def test_statut_par_defaut_est_nouveau(self):
        avis = creer_avis(self.company, creer_source(self.company))
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)

    def test_categorie_par_defaut_est_autre(self):
        avis = creer_avis(self.company, creer_source(self.company))
        self.assertEqual(avis.categorie, CategorieAvis.AUTRE)


class ExpirationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Expiration')
        cls.source = creer_source(cls.company)

    def test_avis_depasse_bascule_en_expire(self):
        avis = creer_avis(
            self.company, self.source,
            date_limite_remise=timezone.now() - dt.timedelta(days=1))
        self.assertTrue(avis.est_depasse)

        bascules = AvisMarche.objects.filter(
            company=self.company).expirer_les_depasses()

        self.assertEqual(bascules, 1)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.EXPIRE)

    def test_avis_retenu_depasse_bascule_aussi(self):
        avis = creer_avis(
            self.company, self.source, statut=StatutAvis.RETENU,
            date_limite_remise=timezone.now() - dt.timedelta(hours=2))
        AvisMarche.objects.filter(company=self.company).expirer_les_depasses()
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.EXPIRE)

    def test_avis_a_venir_ne_bascule_pas(self):
        avis = creer_avis(
            self.company, self.source,
            date_limite_remise=timezone.now() + dt.timedelta(days=3))
        self.assertFalse(avis.est_depasse)
        self.assertEqual(
            AvisMarche.objects.filter(
                company=self.company).expirer_les_depasses(), 0)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)

    def test_avis_sans_date_limite_n_expire_jamais(self):
        """On ne devine pas une échéance qu'on n'a pas lue."""
        avis = creer_avis(self.company, self.source,
                          date_limite_remise=None)
        self.assertFalse(avis.est_depasse)
        self.assertEqual(
            AvisMarche.objects.filter(
                company=self.company).expirer_les_depasses(), 0)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.NOUVEAU)

    def test_avis_deja_converti_ne_rebascule_pas_en_expire(self):
        avis = creer_avis(
            self.company, self.source, statut=StatutAvis.CONVERTI,
            date_limite_remise=timezone.now() - dt.timedelta(days=5))
        AvisMarche.objects.filter(company=self.company).expirer_les_depasses()
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.CONVERTI)

    def test_expiration_reste_scopee_par_societe(self):
        autre = Company.objects.create(nom='Autre Expiration')
        avis_autre = creer_avis(
            autre, creer_source(autre),
            date_limite_remise=timezone.now() - dt.timedelta(days=1))
        AvisMarche.objects.filter(company=self.company).expirer_les_depasses()
        avis_autre.refresh_from_db()
        self.assertEqual(avis_autre.statut, StatutAvis.NOUVEAU)


class LienOpaqueVersAoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.company = Company.objects.create(nom='ACME Lien')
        cls.source = creer_source(cls.company)

    def test_appel_offre_id_est_un_entier_pas_une_fk(self):
        champ = AvisMarche._meta.get_field('appel_offre_id')
        self.assertNotIsInstance(champ, django_models.ForeignKey)
        self.assertIsInstance(champ, django_models.PositiveIntegerField)

    def test_appel_offre_id_vide_par_defaut(self):
        """Aucun avis ne devient automatiquement un appel d'offres."""
        avis = creer_avis(self.company, self.source)
        self.assertIsNone(avis.appel_offre_id)

    def test_aucune_fk_vers_apps_ao(self):
        cibles = {
            champ.related_model._meta.app_label
            for champ in AvisMarche._meta.get_fields()
            if champ.is_relation and champ.related_model is not None
        }
        self.assertNotIn('ao', cibles)


class AucunChampDeCoutTests(SimpleTestCase):
    """« Aucun champ de coût/marge » — le sas n'est pas un chiffrage.

    Les deux seuls montants admis sont ceux PUBLIÉS PAR L'ACHETEUR sur
    l'avis : le montant estimé du marché et la caution provisoire.
    """

    MONTANTS_AUTORISES = {'montant_estime', 'caution_provisoire'}
    MOTS_INTERDITS = ('marge', 'cout', 'coût', 'prix_achat', 'prix_revient',
                      'revient', 'benefice', 'bénéfice', 'rentabilite',
                      'rentabilité')

    def test_aucun_champ_de_marge_ou_de_cout(self):
        noms = [champ.name for champ in AvisMarche._meta.get_fields()]
        fautifs = [
            nom for nom in noms
            if any(mot in nom.lower() for mot in self.MOTS_INTERDITS)
        ]
        self.assertEqual(fautifs, [], fautifs)

    def test_les_seuls_montants_sont_ceux_publies_par_l_acheteur(self):
        montants = {
            champ.name for champ in AvisMarche._meta.get_fields()
            if isinstance(champ, django_models.DecimalField)
        }
        self.assertEqual(montants, self.MONTANTS_AUTORISES)


class AucunImportDeAppsAoTests(SimpleTestCase):
    """Le sas ne connaît pas ``apps.ao`` : découplage par entier opaque.

    La SEULE écriture cross-app du groupe passera plus tard par
    ``apps.ao.services`` (fonction appelée, jamais un import de modèle).
    """

    def test_models_n_importe_pas_apps_ao(self):
        arbre = ast.parse(MODELS_PATH.read_text(encoding='utf-8'))
        importes = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                importes += [alias.name for alias in noeud.names]
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                importes.append(noeud.module)
        fautifs = [nom for nom in importes if nom.startswith('apps.ao')]
        self.assertEqual(fautifs, [], fautifs)
