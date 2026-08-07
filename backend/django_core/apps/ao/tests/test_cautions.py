"""AOF16 — ``CautionSoumission`` : acte, pièce jointe, les DEUX régimes.

Le piège évité ici est une migration en DOUBLE CHAMP : ``banque``,
``date_emission``, ``date_echeance``, ``date_restitution`` et ``statut``
EXISTAIENT DÉJÀ sur le modèle ; seuls ``reference_acte`` et ``attachment``
sont nouveaux. Le premier test le vérifie sur la migration elle-même.

Le second invariant est métier : le cautionnement DÉFINITIF est un TAUX du
montant initial, LU dans ``ExigenceCPS`` (jamais une constante — c'est une
clause du marché, pas une loi du produit) tandis que le PROVISOIRE reste un
MONTANT ABSOLU saisi, jamais dérivé du montant de l'offre.

Le troisième invariant est de PORTE (AOF16, complété) : les deux services de
caution étaient testés mais n'avaient AUCUN appelant — ni endpoint pour
dériver la définitive, ni règle de cohérence pour l'échéance. Les deux
dernières classes de ce module verrouillent ces deux branchements.

Run :
    python manage.py test apps.ao.tests.test_cautions -v2
"""
import datetime
import importlib
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import controles, services
from apps.ao.fabrique import coherence
from apps.ao.models import (
    AppelOffre, CautionSoumission, DossierAO, ExigenceCPS, PieceDossierAO,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL_CAUTIONS = '/api/django/ao/cautions-soumission/'
URL_DERIVER = f'{URL_CAUTIONS}deriver-definitive/'

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


class TestApiDerivationCautionDefinitive(TestCase):
    """AOF16 — la dérivation a désormais une PORTE D'ENTRÉE HTTP.

    Le service existait et était testé, mais ``CautionSoumissionViewSet``
    était un CRUD nu : personne ne pouvait dériver la définitive autrement
    qu'en saisissant un montant à la main — c'est-à-dire en contournant la
    clause du CPS.
    """

    def setUp(self):
        self.company = Company.objects.create(nom='AOF16 API',
                                              slug='aof16-api')
        role = Role.objects.create(
            company=self.company, nom='Directeur',
            permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='aof16_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-16-API', objet='Cautions API',
            montant_offre_ht=Decimal('4200000.00'))

    def _clause_taux(self, taux='3', appel_offre=None, company=None):
        return ExigenceCPS.objects.create(
            company=company or self.company,
            appel_offre=appel_offre or self.ao,
            code='CAUTION_DEFINITIVE_TAUX', libelle='Cautionnement définitif',
            type_exigence=ExigenceCPS.TypeExigence.CAUTION_DEFINITIVE_TAUX,
            valeur_num=taux, unite='%')

    def test_le_taux_du_cps_calcule_la_caution_via_l_api(self):
        self._clause_taux('3')
        r = self.api.post(URL_DERIVER, {'appel_offre': self.ao.id},
                          format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['type_caution'], 'definitive')
        self.assertEqual(Decimal(str(r.data['montant'])),
                         Decimal('126000.00'))
        caution = CautionSoumission.objects.get(id=r.data['id'])
        self.assertEqual(caution.company_id, self.company.id)

    def test_un_second_appel_met_a_jour_sans_creer_de_doublon(self):
        """IDEMPOTENT : le taux qui change corrige la caution existante."""
        self._clause_taux('3')
        premiere = self.api.post(URL_DERIVER, {'appel_offre': self.ao.id},
                                 format='json')
        self._clause_taux('2')
        seconde = self.api.post(
            URL_DERIVER,
            {'appel_offre': self.ao.id, 'banque': 'BMCE',
             'date_echeance': '2026-12-31'}, format='json')
        self.assertEqual(seconde.status_code, 200, seconde.data)
        self.assertEqual(seconde.data['id'], premiere.data['id'])
        self.assertEqual(Decimal(str(seconde.data['montant'])),
                         Decimal('84000.00'))
        self.assertEqual(seconde.data['banque'], 'BMCE')
        self.assertEqual(
            self.ao.cautions.filter(type_caution='definitive').count(), 1)

    def test_un_montant_de_marche_explicite_prime_sur_l_offre(self):
        self._clause_taux('3')
        r = self.api.post(
            URL_DERIVER,
            {'appel_offre': self.ao.id, 'montant_marche': '1000000.00'},
            format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(str(r.data['montant'])), Decimal('30000.00'))

    def test_sans_clause_l_api_refuse_d_inventer_un_taux(self):
        r = self.api.post(URL_DERIVER, {'appel_offre': self.ao.id},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('caution', r.data)
        self.assertFalse(self.ao.cautions.exists())

    def test_le_taux_n_est_pas_un_champ_du_corps(self):
        """Poser ``taux`` dans le corps ne doit RIEN dériver : le taux se lit
        dans le marché, il n'est pas une saisie d'écran."""
        r = self.api.post(URL_DERIVER,
                          {'appel_offre': self.ao.id, 'taux': '10'},
                          format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('caution', r.data)

    def test_un_ao_d_une_autre_societe_est_introuvable(self):
        autre = Company.objects.create(nom='AOF16 X', slug='aof16-x')
        ao = AppelOffre.objects.create(
            company=autre, reference='AO-16-X', objet='X',
            montant_offre_ht=Decimal('4200000.00'))
        self._clause_taux('3', appel_offre=ao, company=autre)
        r = self.api.post(URL_DERIVER, {'appel_offre': ao.id}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('appel_offre', r.data)
        self.assertFalse(ao.cautions.exists())

    def test_appel_offre_manquant_est_un_400_motive(self):
        r = self.api.post(URL_DERIVER, {}, format='json')
        self.assertEqual(r.status_code, 400, r.data)
        self.assertIn('appel_offre', r.data)


class TestRegleCoherenceCautionExpiree(TestCase):
    """AOF16 — l'échéance de caution est désormais un INVARIANT du dossier.

    ``cautions_expirant_avant_ouverture`` n'avait aucun appelant : une caution
    périmée le jour de l'ouverture passait la porte de dépôt en silence, alors
    qu'elle fait REJETER le pli.
    """

    def setUp(self):
        self.company = Company.objects.create(nom='AOF16 Coh',
                                              slug='aof16-coh')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-16-C', objet='Cohérence',
            date_ouverture_plis=datetime.date(2026, 3, 10))
        self.dossier = services.creer_dossier_ao(self.company, self.ao)

    def _caution(self, date_echeance, type_caution=None):
        return CautionSoumission.objects.create(
            company=self.company, appel_offre=self.ao,
            type_caution=(type_caution
                          or CautionSoumission.TypeCaution.PROVISOIRE),
            montant=Decimal('30000.00'), banque='CIH',
            date_echeance=date_echeance)

    def _codes_bloquants(self):
        passe = coherence.passer_controle(self.dossier)
        return {item['code_regle'] for item in passe['bloquants']}, passe

    def test_la_regle_est_enregistree_et_bloquante(self):
        self.assertIn('AO_CAUTION_EXPIREE', controles.REGLES)
        self.assertEqual(controles.REGLES['AO_CAUTION_EXPIREE'].severite,
                         controles.BLOQUANT)

    def test_une_caution_expirant_avant_l_ouverture_bloque_en_la_citant(self):
        self._caution(datetime.date(2026, 3, 9))
        codes, passe = self._codes_bloquants()
        self.assertIn('AO_CAUTION_EXPIREE', codes)
        message = next(item['message'] for item in passe['bloquants']
                       if item['code_regle'] == 'AO_CAUTION_EXPIREE')
        self.assertIn('2026-03-09', message)
        self.assertIn('2026-03-10', message)
        self.assertIn('CIH', message)

    def test_une_caution_valide_le_jour_de_l_ouverture_ne_bloque_pas(self):
        self._caution(datetime.date(2026, 3, 10))
        codes, _passe = self._codes_bloquants()
        self.assertNotIn('AO_CAUTION_EXPIREE', codes)

    def test_une_caution_sans_echeance_ne_bloque_pas_a_tort(self):
        """``None`` n'est jamais lu comme « expirée » (ni comme « OK »)."""
        self._caution(None)
        codes, _passe = self._codes_bloquants()
        self.assertNotIn('AO_CAUTION_EXPIREE', codes)

    def test_sans_date_d_ouverture_la_regle_reste_muette(self):
        self.ao.date_ouverture_plis = None
        self.ao.save(update_fields=['date_ouverture_plis'])
        self._caution(datetime.date(2026, 3, 9))
        codes, _passe = self._codes_bloquants()
        self.assertNotIn('AO_CAUTION_EXPIREE', codes)

    def test_la_porte_de_depot_refuse_en_citant_le_code(self):
        self._caution(datetime.date(2026, 3, 9),
                      CautionSoumission.TypeCaution.DEFINITIVE)
        PieceDossierAO.objects.create(
            company=self.company, dossier=self.dossier, code='04',
            libelle='Bordereau', presente=True)
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.EN_CONSTITUTION)
        services.changer_statut_dossier(
            self.dossier, DossierAO.Statut.CONTROLE)
        with self.assertRaises(ValidationError) as ctx:
            services.changer_statut_dossier(
                self.dossier, DossierAO.Statut.PRET_A_DEPOSER)
        motifs = ' '.join(ctx.exception.message_dict['controles'])
        self.assertIn('AO_CAUTION_EXPIREE', motifs)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.statut, DossierAO.Statut.CONTROLE)
