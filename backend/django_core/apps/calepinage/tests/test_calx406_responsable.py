"""CALX406 — le responsable d'un calepinage, et la vue restreinte aux siens.

Ce qui est prouvé ici :

* ``Calepinage.responsable`` : FK utilisateur NULLABLE, posée par une
  migration ADDITIVE ``0016`` qui suit ``0015`` ; un responsable vide reste
  admis ;
* le sérialiseur du viewset l'expose en LECTURE-ÉCRITURE (identifiant) avec
  son nom pour la colonne de la liste, et refuse un compte d'une autre
  société sous le champ ``responsable`` ;
* le détail agrégé publie le responsable SAISI en priorité, celui du lead à
  défaut — forme du contrat committé ``calepinage_detail.json`` ;
* le réglage ``presets.vue_restreinte_au_responsable`` n'agit que s'il vaut
  EXACTEMENT ``True`` ; absent, la liste est celle d'aujourd'hui ; présent,
  chacun ne reçoit que les calepinages dont il est responsable ou créateur,
  le porteur de ``calepinage_approuver`` les reçoit tous ;
* ``?responsable=<id>`` filtre vraiment, un identifiant illisible est refusé
  en nommant le champ.

Les classes ``…EnBase`` exigent l'ORM : la CI est leur gate.

Run :
    python manage.py test apps.calepinage.tests.test_calx406_responsable -v2
"""
import importlib
import json
import pathlib
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from apps.calepinage.models import Calepinage
from apps.calepinage.serializers import CalepinageSerializer
from apps.calepinage.views import calepinages as vues

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]
CONTRAT = json.loads(
    (RACINE_APP / 'contract_samples' / 'calepinage_detail.json')
    .read_text(encoding='utf-8'))


def personne(pk=1, nom="Utilisateur d'essai", username='essai'):
    return SimpleNamespace(pk=pk, username=username,
                           get_full_name=lambda: nom)


class ChampEtMigrationTest(SimpleTestCase):
    """Le champ est nullable, la migration additive suit 0015."""

    def test_champ_nullable_vers_l_utilisateur(self):
        champ = Calepinage._meta.get_field('responsable')
        self.assertTrue(champ.null)
        self.assertTrue(champ.blank)
        self.assertEqual(champ.related_model._meta.label,
                         'authentication.CustomUser')
        # PROTECT (garde YDATA3) : jamais un responsable vidé en silence.
        self.assertEqual(champ.remote_field.on_delete.__name__, 'PROTECT')

    def test_migration_0016_additive_apres_0015(self):
        module = importlib.import_module(
            'apps.calepinage.migrations.0016_calx406_responsable')
        migration = module.Migration
        self.assertIn(('calepinage', '0015_calx364_provenance_releve_photo'),
                      migration.dependencies)
        self.assertEqual(len(migration.operations), 1)
        operation = migration.operations[0]
        self.assertEqual(type(operation).__name__, 'AddField')
        self.assertEqual((operation.model_name, operation.name),
                         ('calepinage', 'responsable'))
        self.assertTrue(operation.field.null)


class SerialiseurTest(SimpleTestCase):
    """Lecture-écriture, nom pour la liste, garde même-société."""

    def test_responsable_en_lecture_ecriture(self):
        champs = CalepinageSerializer().fields
        self.assertIn('responsable', champs)
        self.assertFalse(champs['responsable'].read_only)
        self.assertFalse(champs['responsable'].required)
        self.assertTrue(champs['responsable'].allow_null)
        self.assertTrue(champs['responsable_nom'].read_only)

    def test_compte_d_une_autre_societe_garde(self):
        self.assertIn('responsable', CalepinageSerializer.same_company_fields)

    def test_nom_du_responsable(self):
        serialiseur = CalepinageSerializer()
        self.assertIsNone(serialiseur.get_responsable_nom(
            SimpleNamespace(responsable=None)))
        self.assertEqual(serialiseur.get_responsable_nom(
            SimpleNamespace(responsable=personne(nom='Nadia B.'))), 'Nadia B.')
        self.assertEqual(serialiseur.get_responsable_nom(
            SimpleNamespace(responsable=personne(nom='  ', username='nb'))),
            'nb')


class DetailContratTest(SimpleTestCase):
    """Le détail publie le responsable SAISI — forme du contrat committé."""

    def test_responsable_saisi_prime(self):
        calepinage = SimpleNamespace(responsable=personne(), lead_id=None)
        with mock.patch('apps.crm.selectors.get_company_lead',
                        side_effect=AssertionError('lead lu pour rien')):
            rendu = vues._responsable(calepinage, None)
        self.assertEqual(rendu, CONTRAT['exemple']['responsable'])

    def test_ni_responsable_ni_lead(self):
        calepinage = SimpleNamespace(responsable=None, lead_id=None)
        self.assertEqual(vues._responsable(calepinage, None),
                         CONTRAT['exemple_vide']['responsable'])

    def test_a_defaut_le_responsable_du_lead(self):
        calepinage = SimpleNamespace(responsable=None, lead_id=3)
        lead = SimpleNamespace(owner=personne(pk=9, nom='Porteur du lead'))
        with mock.patch('apps.crm.selectors.get_company_lead',
                        return_value=lead):
            rendu = vues._responsable(calepinage, SimpleNamespace(pk=1))
        self.assertEqual(rendu, {'id': 9, 'nom_complet': 'Porteur du lead'})

    def test_la_cle_est_au_contrat(self):
        self.assertIn('responsable', CONTRAT['exemple'])
        self.assertIn('CALX406', CONTRAT['pourquoi'])


class ReglageSocieteTest(SimpleTestCase):
    """``True`` et rien d'autre — jamais une restriction devinée."""

    def _vue(self, presets):
        with mock.patch.object(vues.selectors, 'parametres_de_societe',
                               return_value={'presets': presets}):
            return vues.vue_restreinte_au_responsable(SimpleNamespace(pk=1))

    def test_seul_true_restreint(self):
        self.assertTrue(self._vue({vues.CLE_VUE_RESTREINTE: True}))
        for valeur in (None, False, 'oui', 1, 'true'):
            with self.subTest(valeur=valeur):
                self.assertFalse(self._vue({vues.CLE_VUE_RESTREINTE: valeur}))
        self.assertFalse(self._vue({}))

    def test_sans_societe_rien_n_est_lu(self):
        with mock.patch.object(vues.selectors, 'parametres_de_societe',
                               side_effect=AssertionError('lu pour rien')):
            self.assertFalse(vues.vue_restreinte_au_responsable(None))


class RestrictionTest(SimpleTestCase):
    """Qui est restreint, et à quoi."""

    def _requete(self, approuve):
        user = mock.Mock(is_authenticated=True, portee='interne',
                         is_superuser=False, company=SimpleNamespace(pk=1))
        user.has_erp_permission.side_effect = (
            lambda code: approuve and code == 'calepinage_approuver')
        return SimpleNamespace(user=user, method='GET')

    def test_le_relecteur_voit_tout_sans_lire_le_reglage(self):
        lignes = mock.Mock()
        with mock.patch.object(vues, 'vue_restreinte_au_responsable',
                               side_effect=AssertionError('lu pour rien')):
            rendu = vues._restreindre_au_responsable(lignes,
                                                     self._requete(True))
        self.assertIs(rendu, lignes)
        lignes.filter.assert_not_called()

    def test_sans_reglage_la_liste_est_inchangee(self):
        lignes = mock.Mock()
        with mock.patch.object(vues, 'vue_restreinte_au_responsable',
                               return_value=False):
            rendu = vues._restreindre_au_responsable(lignes,
                                                     self._requete(False))
        self.assertIs(rendu, lignes)
        lignes.filter.assert_not_called()

    def test_avec_reglage_responsable_ou_createur(self):
        from django.db.models import Q

        lignes = mock.Mock()
        requete = self._requete(False)
        with mock.patch.object(vues, 'vue_restreinte_au_responsable',
                               return_value=True):
            vues._restreindre_au_responsable(lignes, requete)
        lignes.filter.assert_called_once_with(
            Q(responsable=requete.user) | Q(cree_par=requete.user))

    def test_anonyme_intouche(self):
        lignes = mock.Mock()
        requete = SimpleNamespace(user=None)
        self.assertIs(vues._restreindre_au_responsable(lignes, requete),
                      lignes)


# ── EN BASE — exige l'ORM (la CI est la gate de ces classes) ──────────────

from django.contrib.auth import get_user_model  # noqa: E402

from apps.calepinage.models import ParametresCalepinage  # noqa: E402
from apps.calepinage.permissions import CAL_GERER, CAL_VOIR  # noqa: E402
from apps.roles.models import Role  # noqa: E402

from .test_api_liste import URL, BaseApiCalepinage, url_detail  # noqa: E402

User = get_user_model()


class ResponsableEnBase(BaseApiCalepinage):
    """La liste, le détail et l'écriture, sur de vrais comptes."""

    def setUp(self):
        super().setUp()
        role = Role.objects.create(company=self.company, nom='Concepteur406',
                                   permissions=[CAL_VOIR, CAL_GERER])
        self.anne = User.objects.create_user(
            username='calx406_a', password='x', company=self.company,
            role=role)
        self.bruno = User.objects.create_user(
            username='calx406_b', password='x', company=self.company,
            role=role)
        self.api_anne = self._client(self.anne)
        self.api_bruno = self._client(self.bruno)
        self.confie_a_anne = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Confié',
            responsable=self.anne)
        self.cree_par_bruno = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Créé',
            cree_par=self.bruno)
        self.a_personne = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Libre')
        self.tous = {self.confie_a_anne.pk, self.cree_par_bruno.pk,
                     self.a_personne.pk}

    def _ids(self, api, **params):
        reponse = api.get(URL, params)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return {ligne['id'] for ligne in self._lignes(reponse)}

    def _restreindre(self, valeur=True):
        ParametresCalepinage.objects.create(
            company=self.company,
            presets={'vue_restreinte_au_responsable': valeur})

    def test_sans_reglage_la_meme_liste_qu_aujourd_hui(self):
        self.assertEqual(self._ids(self.api_anne), self.tous)
        self.assertEqual(self._ids(self.api_bruno), self.tous)
        self.assertEqual(self._ids(self.api), self.tous)

    def test_reglage_non_true_ne_restreint_pas(self):
        self._restreindre('oui')
        self.assertEqual(self._ids(self.api_anne), self.tous)

    def test_avec_reglage_chacun_les_siens(self):
        self._restreindre()
        self.assertEqual(self._ids(self.api_anne), {self.confie_a_anne.pk})
        self.assertEqual(self._ids(self.api_bruno), {self.cree_par_bruno.pk})
        # Le relecteur (Directeur, porteur de calepinage_approuver) voit tout.
        self.assertEqual(self._ids(self.api), self.tous)
        reponse = self.api_anne.get(url_detail(self.cree_par_bruno.pk))
        self.assertEqual(reponse.status_code, 404)

    def test_filtre_responsable(self):
        self.assertEqual(self._ids(self.api, responsable=self.anne.pk),
                         {self.confie_a_anne.pk})
        reponse = self.api.get(URL, {'responsable': 'anne'})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('responsable', reponse.data)

    def test_la_liste_publie_identifiant_et_nom(self):
        reponse = self.api.get(URL)
        ligne = next(ligne for ligne in self._lignes(reponse)
                     if ligne['id'] == self.confie_a_anne.pk)
        self.assertEqual(ligne['responsable'], self.anne.pk)
        self.assertEqual(ligne['responsable_nom'], self.anne.username)
        libre = next(ligne for ligne in self._lignes(reponse)
                     if ligne['id'] == self.a_personne.pk)
        self.assertIsNone(libre['responsable'])
        self.assertIsNone(libre['responsable_nom'])

    def test_ecrire_puis_vider_le_responsable(self):
        reponse = self.api.patch(url_detail(self.a_personne.pk),
                                 {'responsable': self.bruno.pk},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.a_personne.refresh_from_db()
        self.assertEqual(self.a_personne.responsable, self.bruno)
        vide = self.api.patch(url_detail(self.a_personne.pk),
                              {'responsable': None}, format='json')
        self.assertEqual(vide.status_code, 200, vide.data)
        self.a_personne.refresh_from_db()
        self.assertIsNone(self.a_personne.responsable)

    def test_creation_sans_responsable_admise(self):
        reponse = self.api.post(URL, {'lead': self.lead.pk, 'titre': 'Neuf'},
                                format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        self.assertIsNone(Calepinage.objects.get(
            pk=reponse.data['id']).responsable)

    def test_compte_d_une_autre_societe_refuse(self):
        reponse = self.api.patch(url_detail(self.a_personne.pk),
                                 {'responsable': self.user_autre.pk},
                                 format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('responsable', reponse.data)
        self.a_personne.refresh_from_db()
        self.assertIsNone(self.a_personne.responsable)

    def test_detail_publie_le_responsable_saisi(self):
        reponse = self.api.get(url_detail(self.confie_a_anne.pk))
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['responsable']['id'], self.anne.pk)
        self.assertEqual(sorted(reponse.data['responsable']),
                         sorted(CONTRAT['exemple']['responsable']))
