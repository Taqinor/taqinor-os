"""CAL7 — les QUATRE modèles du module, dans UNE seule migration.

Ce qui est prouvé ici :

* les quatre modèles naissent dans ``0001_initial`` — il n'y a QU'UNE
  migration dans l'app (un seul manque de cache CI au lieu de quatre) ;
* le rattachement est multi-tenant (``TenantModel``) et les identifiants
  ``lead_id`` / ``appel_offre_id`` sont OPAQUES : aucune FK vers crm ni ao ;
* ``client`` et ``devis`` sont des FK-STRING vers ``crm.Client`` et
  ``ventes.Devis``, toutes deux NULLABLES — un calepinage sans devis est un
  objet de première classe ;
* la BASE refuse un calepinage sans lead NI client (``IntegrityError``), et
  ``clean()`` le refuse en français en NOMMANT le champ ;
* une société ne voit jamais les calepinages d'une autre ;
* ``CalepinageVariante`` ne tolère qu'UNE seule variante retenue (CAL9) ;
* ``ParametresCalepinage`` est unique par société et refuse une section
  inconnue en la nommant (CAL45).

Run :
    python manage.py test apps.calepinage.tests.test_models -v2
"""
import pathlib

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from apps.calepinage.models import (
    Calepinage,
    CalepinageVariante,
    CalepinageVersion,
    ParametresCalepinage,
)
from apps.calepinage.services.variantes import bascule_autorisee
from apps.crm.models import Client
from authentication.models import Company

User = get_user_model()

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / 'migrations'


class UneSeuleMigrationTest(SimpleTestCase):
    """Les quatre modèles du JOUR 1 arrivent ENSEMBLE, dans ``0001_initial``.

    LE GARDE A ÉTÉ RECALIBRÉ, PAS AFFAIBLI. Sa version d'origine exigeait UN
    SEUL fichier dans ``migrations/`` — ce qui était vrai au jour 1 et ne
    l'est plus depuis que des tâches du plan ajoutent explicitement leur
    colonne (CAL52 photos, CAL64 relevé, CAL130 norme, CAL139 pertes,
    CAL149 profils types). Ce qu'il protégeait réellement — « les quatre
    modèles fondateurs ne se dispersent pas en quatre migrations » — est
    tenu par ``test_les_quatre_modeles_y_sont`` ci-dessous. Ce qui est
    vérifié ICI est ce qui reste vrai et utile : la chaîne est LINÉAIRE
    (chaque migration dépend de la précédente), donc rejouable, et
    ``0001_initial`` reste la racine.
    """

    def test_la_chaine_de_migrations_est_lineaire(self):
        fichiers = sorted(
            p.name for p in MIGRATIONS.glob('*.py')
            if p.name != '__init__.py')
        self.assertEqual(fichiers[0], '0001_initial.py', fichiers)
        for precedent, suivant in zip(fichiers, fichiers[1:]):
            texte = (MIGRATIONS / suivant).read_text(encoding='utf-8')
            self.assertIn(
                f"('calepinage', '{precedent[:-3]}')", texte,
                f'{suivant} ne dépend pas de {precedent} : la chaîne de '
                'migrations du module doit rester linéaire pour être '
                'rejouable.')

    def test_les_quatre_modeles_y_sont(self):
        texte = (MIGRATIONS / '0001_initial.py').read_text(encoding='utf-8')
        for modele in ('Calepinage', 'CalepinageVersion',
                       'CalepinageVariante', 'ParametresCalepinage'):
            self.assertIn(f"name='{modele}'", texte, modele)


class DecouplageTest(SimpleTestCase):
    """Identifiants OPAQUES + FK-STRING : aucun couplage de modèles."""

    def test_lead_id_est_opaque(self):
        champ = Calepinage._meta.get_field('lead_id')
        self.assertEqual(champ.get_internal_type(), 'PositiveIntegerField')
        self.assertTrue(champ.null)

    def test_appel_offre_id_est_opaque(self):
        champ = Calepinage._meta.get_field('appel_offre_id')
        self.assertEqual(champ.get_internal_type(), 'PositiveIntegerField')
        self.assertTrue(champ.null)

    def test_client_pointe_crm_client(self):
        champ = Calepinage._meta.get_field('client')
        self.assertEqual(champ.related_model._meta.label, 'crm.Client')
        self.assertTrue(champ.null)

    def test_devis_pointe_ventes_devis(self):
        champ = Calepinage._meta.get_field('devis')
        self.assertEqual(champ.related_model._meta.label, 'ventes.Devis')
        self.assertTrue(champ.null)

    def test_societe_obligatoire(self):
        self.assertFalse(Calepinage._meta.get_field('company').null)


class BaseSociete(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='Calepinage Co',
                                              slug='calepinage-co')
        self.autre = Company.objects.create(nom='Autre Co', slug='autre-co')
        self.client_a = Client.objects.create(company=self.company,
                                              nom='Bâtiment Atlas')
        self.client_b = Client.objects.create(company=self.autre,
                                              nom='Bâtiment Rif')


class RattachementTest(BaseSociete):
    """Au moins un rattachement — garanti en BASE, expliqué en français."""

    def test_sans_lead_ni_client_refuse_en_base(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Calepinage.objects.create(company=self.company,
                                          titre='Orphelin')

    def test_sans_lead_ni_client_refuse_en_clean(self):
        pivot = Calepinage(company=self.company, titre='Orphelin')
        with self.assertRaises(ValidationError) as capture:
            pivot.clean()
        self.assertIn('client', capture.exception.message_dict)
        self.assertIn('lead', str(capture.exception).lower())

    def test_lead_seul_suffit(self):
        pivot = Calepinage.objects.create(company=self.company, lead_id=77)
        self.assertIsNone(pivot.client_id)
        self.assertIsNone(pivot.devis_id)

    def test_client_seul_suffit(self):
        pivot = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        self.assertIsNone(pivot.lead_id)

    def test_empreinte_de_mauvaise_longueur_refusee(self):
        pivot = Calepinage(company=self.company, lead_id=1,
                           layout_hash='trop-court')
        with self.assertRaises(ValidationError) as capture:
            pivot.clean()
        self.assertIn('layout_hash', capture.exception.message_dict)


class IsolationSocieteTest(BaseSociete):
    def test_une_societe_ne_voit_pas_l_autre(self):
        Calepinage.objects.create(company=self.company, client=self.client_a)
        Calepinage.objects.create(company=self.autre, client=self.client_b)
        self.assertEqual(
            Calepinage.objects.filter(company=self.company).count(), 1)
        self.assertEqual(
            Calepinage.objects.filter(company=self.autre).count(), 1)


class VarianteRetenueUniqueTest(BaseSociete):
    """CAL9 — une deuxième variante retenue lève IntegrityError."""

    def setUp(self):
        super().setUp()
        self.pivot = Calepinage.objects.create(company=self.company,
                                               client=self.client_a)

    def test_deux_retenues_impossible(self):
        # ``retenue`` ne s'écrit que par le chemin sanctionné (CAL9) ; on s'y
        # place ici pour éprouver la contrainte de BASE elle-même.
        with bascule_autorisee():
            CalepinageVariante.objects.create(company=self.company,
                                              calepinage=self.pivot,
                                              nom='A', retenue=True)
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    CalepinageVariante.objects.create(company=self.company,
                                                      calepinage=self.pivot,
                                                      nom='B', retenue=True)

    def test_plusieurs_non_retenues_possibles(self):
        CalepinageVariante.objects.create(company=self.company,
                                          calepinage=self.pivot, nom='A')
        CalepinageVariante.objects.create(company=self.company,
                                          calepinage=self.pivot, nom='B')
        self.assertEqual(self.pivot.variantes.count(), 2)


class VersionTest(BaseSociete):
    def test_version_rattachee_et_horodatee(self):
        pivot = Calepinage.objects.create(company=self.company,
                                          client=self.client_a)
        version = CalepinageVersion.objects.create(
            company=self.company, calepinage=pivot,
            roof_layout={'zones': []}, layout_hash='a' * 64)
        self.assertEqual(version.calepinage_id, pivot.pk)
        self.assertIsNotNone(version.created_at)


class ParametresTest(BaseSociete):
    """CAL45 — un enregistrement par société, sections connues seulement."""

    def test_sections_vides_par_defaut(self):
        reglages = ParametresCalepinage.objects.create(company=self.company)
        for section in ParametresCalepinage.SECTIONS:
            self.assertEqual(getattr(reglages, section), {}, section)

    def test_un_seul_enregistrement_par_societe(self):
        ParametresCalepinage.objects.create(company=self.company)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ParametresCalepinage.objects.create(company=self.company)

    def test_section_inconnue_nommee(self):
        inconnues = ParametresCalepinage.sections_inconnues(
            {'imagerie': {}, 'couleur_du_toit': {}})
        self.assertEqual(inconnues, ['couleur_du_toit'])

    def test_section_non_objet_refusee_en_nommant_la_section(self):
        reglages = ParametresCalepinage(company=self.company,
                                        degagements=['1.0'])
        with self.assertRaises(ValidationError) as capture:
            reglages.clean()
        self.assertIn('degagements', capture.exception.message_dict)
