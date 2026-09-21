"""VAO31 — ATTRIBUTION : d'où vient réellement le chiffre d'affaires.

Le constat central de l'étude : l'AO qui a occupé le fondateur n'aurait été
capté par AUCUN dispositif automatique. Il faut donc MESURER, sur douze mois,
quel canal rapporte — au lieu de le supposer. C'est la seule façon d'arbitrer
honnêtement entre payer un agrégateur, améliorer le collecteur, et aller
démarcher (VAO29).

Le « Done = » :
  * un tableau « canal → avis → affaires → gagnés » CALCULÉ (jamais saisi) ;
  * lecture cross-app par SELECTOR uniquement ;
  * le canal ``tuyau_partenaire`` apparaît à ÉGALITÉ avec le portail — c'est
    tout l'intérêt de la mesure.
"""
import ast
import pathlib

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.ao.models import AppelOffre
from apps.roles.models import Role

from apps.veille_ao.kpis import attribution
from apps.veille_ao.models import (
    AvisMarche, Informateur, SourceVeille, StatutAvis, TypeSource,
)

URL = '/api/django/veille_ao/attribution/'
MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]


def _ligne(tableau, cle):
    return next(ligne for ligne in tableau if ligne['cle'] == cle)


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Attribution')
        self.portail = SourceVeille.objects.create(
            company=self.company, code='pmmp', libelle='Portail',
            type_source=TypeSource.PORTAIL_OFFICIEL,
            url_base='https://exemple.test/', actif=True)
        self.tuyau = SourceVeille.objects.create(
            company=self.company, code='tuyau', libelle='Tuyau partenaire',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)

    def _avis(self, source, *, statut=StatutAvis.NOUVEAU, informateur='',
              issue=None, objet='Avis'):
        appel_offre_id = None
        if issue is not None:
            affaire = AppelOffre.objects.create(
                company=self.company,
                reference=f'AO-TEST-{AppelOffre.objects.count() + 1:04d}',
                reference_acheteur=f'REF-{AppelOffre.objects.count() + 1}',
                objet=objet, statut=issue)
            appel_offre_id = affaire.pk
        return AvisMarche.objects.create(
            company=self.company, source=source, objet=objet, statut=statut,
            informateur=informateur, appel_offre_id=appel_offre_id)


class TableauCalculeTests(_Base):
    def test_le_tableau_compte_avis_retenus_affaires_et_gagnes(self):
        self._avis(self.portail)
        self._avis(self.portail, statut=StatutAvis.RETENU)
        self._avis(self.portail, statut=StatutAvis.CONVERTI,
                   issue=AppelOffre.Statut.GAGNE)
        self._avis(self.portail, statut=StatutAvis.CONVERTI,
                   issue=AppelOffre.Statut.PERDU)

        ligne = _ligne(attribution(self.company)['par_source'],
                       TypeSource.PORTAIL_OFFICIEL)

        self.assertEqual(ligne['avis'], 4)
        self.assertEqual(ligne['retenus'], 3)
        self.assertEqual(ligne['affaires'], 2)
        self.assertEqual(ligne['gagnes'], 1)
        self.assertEqual(ligne['perdus'], 1)

    def test_une_affaire_encore_ouverte_compte_EN_COURS(self):
        self._avis(self.portail, statut=StatutAvis.CONVERTI,
                   issue=AppelOffre.Statut.CHIFFRAGE)
        ligne = _ligne(attribution(self.company)['par_source'],
                       TypeSource.PORTAIL_OFFICIEL)
        self.assertEqual(ligne['en_cours'], 1)
        self.assertEqual(ligne['gagnes'], 0)

    def test_le_total_agrege_tous_les_canaux(self):
        self._avis(self.portail, statut=StatutAvis.CONVERTI,
                   issue=AppelOffre.Statut.GAGNE)
        self._avis(self.tuyau, informateur=Informateur.PARTENAIRE,
                   statut=StatutAvis.CONVERTI, issue=AppelOffre.Statut.GAGNE)

        total = attribution(self.company)['total']

        self.assertEqual(total['avis'], 2)
        self.assertEqual(total['gagnes'], 2)


class TuyauPartenaireAEgaliteTests(_Base):
    """C'est tout l'intérêt de la mesure : le tuyau n'est PAS une note de bas
    de page — il apparaît dans le même tableau, avec les mêmes colonnes."""

    def test_le_tuyau_partenaire_est_une_ligne_comme_les_autres(self):
        self._avis(self.tuyau, informateur=Informateur.PARTENAIRE,
                   statut=StatutAvis.CONVERTI, issue=AppelOffre.Statut.GAGNE)

        tableau = attribution(self.company)['par_source']
        ligne = _ligne(tableau, TypeSource.TUYAU_PARTENAIRE)

        self.assertEqual(ligne['gagnes'], 1)
        self.assertEqual(ligne['libelle'], 'Tuyau partenaire')

    def test_le_canal_qui_gagne_arrive_EN_TETE(self):
        self._avis(self.portail)
        self._avis(self.portail)
        self._avis(self.tuyau, informateur=Informateur.PARTENAIRE,
                   statut=StatutAvis.CONVERTI, issue=AppelOffre.Statut.GAGNE)

        tableau = attribution(self.company)['par_source']

        self.assertEqual(tableau[0]['cle'], TypeSource.TUYAU_PARTENAIRE)

    def test_un_canal_sans_aucun_avis_apparait_A_ZERO(self):
        """Absent = « pas mesuré » ; à zéro = « mesuré, ne rapporte rien ».
        La différence est exactement ce que cette mesure établit."""
        self._avis(self.portail)
        tableau = attribution(self.company)['par_source']
        self.assertEqual(_ligne(tableau, TypeSource.AGREGATEUR)['avis'], 0)
        self.assertEqual({ligne['cle'] for ligne in tableau},
                         {c for c, _ in TypeSource.choices})


class AxeInformateurTests(_Base):
    def test_l_axe_informateur_repond_a_QUI_me_l_a_signale(self):
        self._avis(self.tuyau, informateur=Informateur.PARTENAIRE,
                   statut=StatutAvis.CONVERTI, issue=AppelOffre.Statut.GAGNE)
        self._avis(self.tuyau, informateur=Informateur.CLIENT)

        tableau = attribution(self.company)['par_informateur']

        self.assertEqual(_ligne(tableau, 'partenaire')['gagnes'], 1)
        self.assertEqual(_ligne(tableau, 'client')['avis'], 1)

    def test_un_avis_COLLECTE_est_range_sous_collecte_automatique(self):
        """Personne ne l'a signalé — une machine l'a lu. Le dire vaut mieux
        qu'un blanc."""
        self._avis(self.portail)
        tableau = attribution(self.company)['par_informateur']
        ligne = _ligne(tableau, 'collecte_automatique')
        self.assertEqual(ligne['avis'], 1)
        self.assertIn('personne', ligne['libelle'].lower())


class IsolationTests(_Base):
    def test_l_attribution_est_scopee_SOCIETE(self):
        autre = Company.objects.create(nom='Autre société')
        source = SourceVeille.objects.create(
            company=autre, code='tuyau', libelle='Tuyau',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        AvisMarche.objects.create(company=autre, source=source,
                                  objet='Ailleurs')

        self.assertEqual(attribution(self.company)['total']['avis'], 0)

    def test_une_affaire_d_une_AUTRE_societe_ne_compte_jamais_comme_gagnee(self):
        autre = Company.objects.create(nom='Autre société')
        affaire = AppelOffre.objects.create(
            company=autre, reference='AO-AUTRE-0001',
            reference_acheteur='REF-AUTRE', objet='Ailleurs',
            statut=AppelOffre.Statut.GAGNE)
        AvisMarche.objects.create(
            company=self.company, source=self.portail, objet='Avis',
            statut=StatutAvis.CONVERTI, appel_offre_id=affaire.pk)

        ligne = _ligne(attribution(self.company)['par_source'],
                       TypeSource.PORTAIL_OFFICIEL)

        self.assertEqual(ligne['affaires'], 1)
        self.assertEqual(ligne['gagnes'], 0)
        self.assertEqual(ligne['en_cours'], 1)


class EndpointTests(_Base):
    def _api(self, permissions=('veille_ao_voir',), suffixe='lecteur'):
        role = Role.objects.create(
            company=self.company, nom=f'Rôle {suffixe}',
            permissions=list(permissions))
        user = CustomUser.objects.create_user(
            username=f'vao_attr_{suffixe}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_l_ecran_recoit_les_deux_axes_et_le_total(self):
        self._avis(self.tuyau, informateur=Informateur.PARTENAIRE)
        api = self._api()

        reponse = api.get(URL)

        self.assertEqual(reponse.status_code, 200)
        for cle in ('par_source', 'par_informateur', 'total'):
            self.assertIn(cle, reponse.data, cle)
        self.assertTrue(reponse.data['par_source'])

    def test_un_role_etranger_est_refuse(self):
        api = self._api(['crm_voir'], 'etranger')
        self.assertEqual(api.get(URL).status_code, 403)


class LectureParSelectorTests(SimpleTestCase):
    """« Lecture cross-app par selector uniquement. »"""

    def test_l_issue_des_affaires_est_lue_par_apps_ao_selectors(self):
        source = (MODULE_DIR / 'kpis.py').read_text(encoding='utf-8')
        self.assertIn('from apps.ao.selectors import', source)

    def test_kpis_n_importe_AUCUN_modele_d_une_autre_app(self):
        arbre = ast.parse(
            (MODULE_DIR / 'kpis.py').read_text(encoding='utf-8'))
        for noeud in ast.walk(arbre):
            module = ''
            if isinstance(noeud, ast.ImportFrom):
                module = noeud.module or ''
            elif isinstance(noeud, ast.Import):
                module = ' '.join(a.name for a in noeud.names)
            if module.startswith('apps.') and not module.startswith(
                    'apps.veille_ao'):
                self.assertTrue(
                    module.endswith('.selectors'),
                    f'lecture cross-app hors selector : {module}')

    def test_le_tableau_est_CALCULE_jamais_stocke(self):
        """Aucun modèle de la veille ne porte un compteur d'attribution."""
        from apps.veille_ao import models as modeles

        for nom in ('gagnes', 'affaires', 'taux_attribution'):
            self.assertFalse(
                any(f.name == nom
                    for f in modeles.AvisMarche._meta.get_fields()),
                nom)
