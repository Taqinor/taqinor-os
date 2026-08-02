"""AOF16 — ``CautionSoumission`` : acte, pièce jointe, les DEUX régimes.

Le piège évité ici est une migration en DOUBLE CHAMP : ``banque``,
``date_emission``, ``date_echeance``, ``date_restitution`` et ``statut``
EXISTAIENT DÉJÀ sur le modèle ; seuls ``reference_acte`` et ``attachment``
sont nouveaux. Le premier test le vérifie sur la migration elle-même.

Le second invariant est métier : le cautionnement DÉFINITIF est un TAUX du
montant initial, LU dans ``ExigenceCPS`` (jamais une constante — c'est une
clause du marché, pas une loi du produit) tandis que le PROVISOIRE reste un
MONTANT ABSOLU saisi, jamais dérivé du montant de l'offre.

Run :
    python manage.py test apps.ao.tests.test_cautions -v2
"""
import datetime
import importlib
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from apps.ao import services
from apps.ao.models import AppelOffre, CautionSoumission, ExigenceCPS
from authentication.models import Company

CHAMPS_PREEXISTANTS = (
    'banque', 'date_emission', 'date_echeance', 'date_restitution', 'statut',
)


class TestMigrationSansDoublon(SimpleTestCase):
    def test_aucun_champ_existant_redeclare(self):
        migration = importlib.import_module(
            'apps.ao.migrations.0003_projet_ao')
        ajouts_caution = {
            op.name for op in migration.Migration.operations
            if getattr(op, 'model_name', None) == 'cautionsoumission'
        }
        self.assertEqual(ajouts_caution, {'reference_acte', 'attachment'})
        for champ in CHAMPS_PREEXISTANTS:
            self.assertNotIn(champ, ajouts_caution, champ)

    def test_aucun_nouveau_filefield(self):
        """ARC26 — la pièce jointe passe par ``records.Attachment``."""
        from django.db import models as dj_models

        champ = CautionSoumission._meta.get_field('attachment')
        self.assertIsInstance(champ, dj_models.ForeignKey)
        self.assertEqual(
            champ.remote_field.model._meta.label_lower, 'records.attachment')
        for f in CautionSoumission._meta.local_fields:
            self.assertNotIsInstance(f, dj_models.FileField, f.name)


class TestDeuxRegimesDeCaution(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF16 Co', slug='aof16-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-16-1', objet='Cautions',
            montant_offre_ht=Decimal('4200000.00'))

    def _clause_taux(self, taux='3'):
        return ExigenceCPS.objects.create(
            company=self.company, appel_offre=self.ao,
            code='CAUTION_DEFINITIVE_TAUX', libelle='Cautionnement définitif',
            type_exigence=ExigenceCPS.TypeExigence.CAUTION_DEFINITIVE_TAUX,
            valeur_num=taux, unite='%')

    def test_taux_lu_dans_les_clauses_jamais_une_constante(self):
        self._clause_taux('3')
        self.assertEqual(services.taux_caution_definitive(self.ao),
                         Decimal('3.0000'))

    def test_sans_clause_le_service_refuse_d_inventer_un_taux(self):
        with self.assertRaises(ValidationError) as ctx:
            services.taux_caution_definitive(self.ao)
        self.assertIn('caution', ctx.exception.message_dict)

    def test_definitive_derivee_du_taux(self):
        self._clause_taux('3')
        caution = services.deriver_caution_definitive(self.ao)
        self.assertEqual(caution.type_caution,
                         CautionSoumission.TypeCaution.DEFINITIVE)
        self.assertEqual(caution.montant, Decimal('126000.00'))

    def test_un_autre_taux_donne_un_autre_montant(self):
        """Le taux est une CLAUSE : 2 % doit donner 2 %, pas 3 %."""
        self._clause_taux('2')
        caution = services.deriver_caution_definitive(self.ao)
        self.assertEqual(caution.montant, Decimal('84000.00'))

    def test_derivation_idempotente(self):
        self._clause_taux('3')
        premiere = services.deriver_caution_definitive(self.ao)
        seconde = services.deriver_caution_definitive(self.ao)
        self.assertEqual(premiere.pk, seconde.pk)
        self.assertEqual(
            self.ao.cautions.filter(type_caution='definitive').count(), 1)

    def test_provisoire_reste_un_montant_absolu_saisi(self):
        """La provisoire n'est JAMAIS dérivée du montant de l'offre."""
        self._clause_taux('3')
        provisoire = CautionSoumission.objects.create(
            company=self.company, appel_offre=self.ao,
            type_caution=CautionSoumission.TypeCaution.PROVISOIRE,
            montant=Decimal('30000.00'))
        services.deriver_caution_definitive(self.ao)
        provisoire.refresh_from_db()
        self.assertEqual(provisoire.montant, Decimal('30000.00'))


class TestAlerteEcheance(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='AOF16 Al', slug='aof16-al')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-16-A', objet='Alerte',
            date_ouverture_plis=datetime.date(2026, 3, 10))

    def _caution(self, date_echeance):
        return CautionSoumission.objects.create(
            company=self.company, appel_offre=self.ao,
            type_caution=CautionSoumission.TypeCaution.PROVISOIRE,
            montant=Decimal('30000.00'), banque='Banque',
            date_echeance=date_echeance)

    def test_caution_expirant_avant_l_ouverture_est_signalee(self):
        caution = self._caution(datetime.date(2026, 3, 9))
        self.assertTrue(caution.expire_avant_ouverture)
        self.assertEqual(
            [c.pk for c in services.cautions_expirant_avant_ouverture(self.ao)],
            [caution.pk])

    def test_caution_valide_le_jour_de_l_ouverture_n_est_pas_signalee(self):
        caution = self._caution(datetime.date(2026, 3, 10))
        self.assertFalse(caution.expire_avant_ouverture)
        self.assertEqual(services.cautions_expirant_avant_ouverture(self.ao),
                         [])

    def test_aucune_date_donne_none_jamais_un_faux_ok(self):
        caution = self._caution(None)
        self.assertIsNone(caution.expire_avant_ouverture)

    def test_echeance_de_caution_rejoint_l_echeancier(self):
        self._caution(datetime.date(2026, 3, 9))
        services.generer_echeancier_ao(self.ao)
        libelles = set(self.ao.echeances.values_list('libelle', flat=True))
        self.assertIn('Échéance de la caution provisoire', libelles)

    def test_echeancier_avec_cautions_reste_idempotent(self):
        self._caution(datetime.date(2026, 3, 9))
        services.generer_echeancier_ao(self.ao)
        resume = services.generer_echeancier_ao(self.ao)
        self.assertEqual(resume['creees'], 0)
        self.assertEqual(resume['mises_a_jour'], 0)

    def test_deux_cautions_donnent_deux_echeances_distinctes(self):
        self._caution(datetime.date(2026, 3, 9))
        CautionSoumission.objects.create(
            company=self.company, appel_offre=self.ao,
            type_caution=CautionSoumission.TypeCaution.DEFINITIVE,
            montant=Decimal('126000.00'),
            date_echeance=datetime.date(2026, 12, 31))
        services.generer_echeancier_ao(self.ao)
        libelles = set(self.ao.echeances.values_list('libelle', flat=True))
        self.assertIn('Échéance de la caution provisoire', libelles)
        self.assertIn('Échéance de la caution définitive', libelles)
