"""PV67 — les variantes d'ORIENTATION se génèrent toutes seules, et REJOUÉES.

L'atelier savait comparer des variantes ; encore fallait-il les SAISIR une par
une, en recopiant les paramètres et en changeant un mot. Les trois questions
d'orientation d'une toiture — dans quel sens courent les rangées, quelle table
pose-t-on, peut-on mélanger deux kits — sont pourtant toujours les mêmes, et
personne ne les posait toutes : le dessinateur comparait ce qu'il avait eu le
temps de taper.

Ce module verrouille quatre choses, et rien d'autre :

  1. **Aucun compte n'est estimé.** Chaque alternative est REJOUÉE par
     ``calculer_variante`` — même chemin, même preuve, même version de moteur
     que la variante retenue.
  2. **Une orientation inconstructible est ÉCARTÉE AVEC SON MOTIF.** C'est le
     moteur (``orientation.verifier``) qui refuse, et c'est SA phrase qui est
     publiée : l'alternative impossible dit pourquoi, elle ne disparaît pas.
  3. **Sans variante retenue, on refuse poliment.** Comparer des alternatives
     suppose une référence ; l'API rend 400 en français, jamais une
     comparaison sans point de comparaison.
  4. **L'appel est IDEMPOTENT.** Rejouer ne duplique pas les alternatives dans
     l'écran de comparaison.

Run :
    python manage.py test apps.ao.tests.test_pv67_variantes_orientation -v2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import calepinage_service, services
from apps.ao.models import (
    AppelOffre, BatimentAO, KitCalepinage, ToitureAO, VarianteCalepinage,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

GENERER = '/api/django/ao/calepinage/variantes/%s/generer-variantes/'

CODE_PORTRAIT = 'AO-TABLE-PORTRAIT'
CODE_PAYSAGE = 'AO-TABLE-PAYSAGE'
CODE_VILLA = 'VILLA-720'

PARAMS = {
    'rive_laterale_m': 0.35,
    'rive_extremite_m': 0.35,
    'allee_min_m': 0.60,
    'degagements_par_provenance_m': {'MESURE': 0.30, 'DEVINE': 0.50},
    'kits_autorises': [CODE_PORTRAIT],
    'axe_rangee': 'NORD_SUD',
    'pas_recherche_m': 0.01,
}


class BasePv67(TestCase):
    """Une toiture rectangulaire, trois kits au catalogue, une retenue."""

    def setUp(self):
        cache.clear()
        self.company = Company.objects.create(nom='PV67 Co', slug='pv67-co')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-67-1', objet='Orientation')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='C')
        self.toiture = ToitureAO.objects.create(
            company=self.company, batiment=self.batiment, code_document='05H',
            contour_local_m=[[0, 0], [30, 0], [30, 18], [0, 18]],
            parametres_calepinage=dict(PARAMS))
        self.portrait = self._kit(CODE_PORTRAIT, 'Table dos-à-dos portrait',
                                  modules=2, pas='1.134', pente='2.382',
                                  faitage='0.098',
                                  orientation=KitCalepinage.Orientation.PORTRAIT)
        self.paysage = self._kit(CODE_PAYSAGE, 'Table dos-à-dos paysage',
                                 modules=2, pas='2.382', pente='1.134',
                                 faitage='0.059',
                                 orientation=KitCalepinage.Orientation.PAYSAGE)
        self.villa = self._kit(CODE_VILLA, 'Panneau simple villa 720 Wc',
                               modules=1, pas='1.303', pente='2.384',
                               faitage='0.000', puissance=720,
                               inclinaison='13.00',
                               orientation=KitCalepinage.Orientation.PORTRAIT)

    def _kit(self, code, libelle, *, modules, pas, pente, faitage,
             orientation, puissance=625, inclinaison='15.00'):
        kit = KitCalepinage.objects.create(
            company=self.company, code=code, libelle=libelle,
            modules_par_kit=modules, pas_rangee_m=Decimal(pas),
            longueur_pente_m=Decimal(pente), faitage_m=Decimal(faitage),
            puissance_module_w=puissance,
            inclinaison_deg=Decimal(inclinaison),
            orientation_modules=orientation)
        kit.appliquer_emprise()
        kit.save()
        return kit

    def _retenue(self):
        variante = calepinage_service.calculer_variante(
            self.toiture, params=dict(PARAMS))
        return services.retenir_variante(variante)


class SansReferenceOnRefusePoliment(BasePv67):
    """Une comparaison sans point de comparaison n'est pas une comparaison."""

    def test_le_service_leve_une_exception_nommee(self):
        with self.assertRaises(calepinage_service.SansVarianteRetenue) as levee:
            calepinage_service.generer_variantes_orientation(self.toiture)
        self.assertIn('RETENUE', str(levee.exception))

    def test_une_variante_non_retenue_ne_suffit_pas(self):
        """Une variante CALCULÉE mais jamais retenue n'est pas une référence."""
        calepinage_service.calculer_variante(self.toiture,
                                             params=dict(PARAMS))
        with self.assertRaises(calepinage_service.SansVarianteRetenue):
            calepinage_service.generer_variantes_orientation(self.toiture)


class LesAlternativesSontRejouees(BasePv67):
    """Chaque alternative publiée a été POSÉE par le moteur."""

    def setUp(self):
        super().setUp()
        self.retenue = self._retenue()
        self.sortie = calepinage_service.generer_variantes_orientation(
            self.toiture)

    def test_entre_deux_et_quatre_alternatives_sont_persistees(self):
        enfants = VarianteCalepinage.objects.filter(
            company=self.company, parent=self.retenue,
            role=VarianteCalepinage.Role.ALTERNATIVE)
        self.assertGreaterEqual(enfants.count(), 2)
        self.assertLessEqual(enfants.count(), 4)
        self.assertEqual(enfants.count(), len(self.sortie['variantes']))

    def test_chaque_alternative_porte_une_preuve_du_moteur(self):
        for ligne in self.sortie['variantes']:
            variante = VarianteCalepinage.objects.get(pk=ligne['id'])
            self.assertTrue(variante.version_moteur)
            self.assertTrue(variante.preuve)
            self.assertEqual(variante.preuve.get('total_retenu'),
                             variante.total_modules)
            self.assertGreater(variante.total_modules, 0)

    def test_le_delta_est_calcule_contre_la_retenue(self):
        reference = self.retenue.total_modules
        self.assertEqual(self.sortie['reference_modules'], reference)
        for ligne in self.sortie['variantes']:
            self.assertEqual(ligne['delta_modules'],
                             ligne['modules'] - reference)

    def test_le_patch_publie_est_du_vocabulaire_des_parametres(self):
        """Le patch doit être rejouable tel quel par ``majParametres``."""
        vocabulaire = set(PARAMS) | {'axe_rangee', 'kits_autorises'}
        for ligne in self.sortie['variantes']:
            self.assertTrue(ligne['patch'])
            self.assertLessEqual(set(ligne['patch']), vocabulaire)
            params = dict(PARAMS)
            params.update(ligne['patch'])
            variante = VarianteCalepinage.objects.get(pk=ligne['id'])
            self.assertEqual(variante.params, params)

    def test_les_alternatives_sont_visibles_dans_la_comparaison(self):
        identifiants = [self.retenue.pk] + [ligne['id'] for ligne
                                            in self.sortie['variantes']]
        comparaison = calepinage_service.comparer_variantes(self.company,
                                                            identifiants)
        self.assertEqual(comparaison['introuvables'], [])
        vues = {ligne['id'] for ligne in comparaison['lignes']}
        self.assertEqual(vues, set(identifiants))
        roles = {ligne['id']: ligne['role'] for ligne in comparaison['lignes']}
        for ligne in self.sortie['variantes']:
            self.assertEqual(roles[ligne['id']],
                             VarianteCalepinage.Role.ALTERNATIVE)

    def test_rejouer_l_appel_ne_duplique_rien(self):
        avant = {ligne['id'] for ligne in self.sortie['variantes']}
        seconde = calepinage_service.generer_variantes_orientation(
            self.toiture)
        self.assertEqual({ligne['id'] for ligne in seconde['variantes']},
                         avant)
        self.assertEqual(VarianteCalepinage.objects.filter(
            company=self.company, parent=self.retenue,
            role=VarianteCalepinage.Role.ALTERNATIVE).count(), len(avant))


class UneOrientationImpossibleDitPourquoi(BasePv67):
    """PV67-2 — l'alternative écartée publie le MOTIF du moteur."""

    def setUp(self):
        super().setUp()
        self.retenue = self._retenue()
        self.sortie = calepinage_service.generer_variantes_orientation(
            self.toiture)
        self.ignorees = {ligne['code']: ligne
                         for ligne in self.sortie['ignorees']}

    def test_l_inversion_d_axe_est_refusee_sur_une_table_dos_a_dos(self):
        """AOF45 : faces est/ouest ⇒ faîtage nord-sud ⇒ rangées nord-sud."""
        self.assertIn('AXE_INVERSE', self.ignorees)
        motif = self.ignorees['AXE_INVERSE']['motif']
        self.assertIn('dos-à-dos', motif)
        self.assertIn('EST_OUEST', motif)

    def test_le_motif_vient_du_moteur_et_non_d_une_phrase_recopiee(self):
        from core.calepinage.orientation import motif_orientation
        from core.calepinage.types import KIT_AO_PORTRAIT, Axe

        attendu = motif_orientation(KIT_AO_PORTRAIT, Axe.EST_OUEST)
        publie = self.ignorees['AXE_INVERSE']['motif']
        # Le kit du catalogue porte un autre code que la constante du moteur :
        # on compare la CAUSE, qui est la phrase générée, pas le préfixe.
        self.assertIn(attendu.split(':', 1)[1].strip(), publie)

    def test_une_alternative_ecartee_ne_cree_aucune_variante(self):
        noms = set(VarianteCalepinage.objects.filter(
            company=self.company, parent=self.retenue,
            role=VarianteCalepinage.Role.ALTERNATIVE
        ).values_list('nom', flat=True))
        self.assertFalse(noms & set(self.ignorees))

    def test_chaque_famille_est_soit_produite_soit_motivee(self):
        """Aucune des quatre familles ne disparaît en silence."""
        codes = ({ligne['code'] for ligne in self.sortie['variantes']}
                 | set(self.ignorees))
        self.assertEqual(
            codes, {code for code, _libelle
                    in calepinage_service.VARIANTES_ORIENTATION})
        for ligne in self.sortie['ignorees']:
            self.assertTrue(ligne['motif'].strip())


class LEndpointGenereLesVariantes(BasePv67):
    """L'action POST ``generer-variantes``, montée comme ``sensibilites``."""

    def setUp(self):
        super().setUp()
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='pv67_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')

    def test_sans_retenue_l_api_refuse_en_francais(self):
        variante = calepinage_service.calculer_variante(self.toiture,
                                                        params=dict(PARAMS))
        reponse = self.api.post(GENERER % variante.pk, {}, format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('retenue', reponse.data)
        self.assertIn('RETENUE', reponse.data['retenue'][0])

    def test_avec_une_retenue_l_api_publie_les_alternatives(self):
        retenue = self._retenue()
        reponse = self.api.post(GENERER % retenue.pk, {}, format='json')
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['retenue'], retenue.pk)
        self.assertEqual(reponse.data['toiture'], self.toiture.pk)
        self.assertGreaterEqual(len(reponse.data['variantes']), 2)
        self.assertTrue(reponse.data['ignorees'])

    def test_l_action_est_montee_en_post_seulement(self):
        retenue = self._retenue()
        self.assertEqual(self.api.get(GENERER % retenue.pk).status_code, 405)

    def test_une_variante_d_une_autre_societe_est_introuvable(self):
        """404 et non 403 : un 403 confirmerait l'existence de l'objet."""
        autre = Company.objects.create(nom='PV67 Autre', slug='pv67-autre')
        role = Role.objects.create(company=autre, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        etranger = User.objects.create_user(
            username='pv67_etranger', password='x', company=autre, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(etranger)}')
        retenue = self._retenue()
        self.assertEqual(
            api.post(GENERER % retenue.pk, {}, format='json').status_code, 404)
