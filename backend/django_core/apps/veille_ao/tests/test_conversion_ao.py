"""VAO30 — « Retenir » crée l'affaire : l'UNIQUE contact cross-app du groupe.

Le « Done = » :
  * retenir un avis crée EXACTEMENT un ``AppelOffre`` référencé ;
  * re-cliquer ne crée pas de doublon (le lien existe déjà) ;
  * aucun import de ``apps.ao.models`` depuis ``veille_ao`` (lint-imports) ;
  * aucune régression sur les viewsets AO existants (rien n'y est touché).

La référence de NOTRE dossier reste générée par la plateforme
(``core.numbering``, jamais un ``count()+1`` — le dépôt a déjà payé une
collision en production) : c'est la fonction d'accueil d'``apps.ao`` qui s'en
charge, et c'est précisément pourquoi on passe par elle.
"""
import ast
import pathlib
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.ao.models import AppelOffre
from apps.records.models import Activity
from apps.roles.models import Role

from apps.veille_ao.models import (
    AvisMarche, Informateur, RegleExclusion, SourceVeille, StatutAvis,
    TypeSource,
)
from apps.veille_ao.services import ignorer_avis, retenir_avis

MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Conversion')
        self.user = CustomUser.objects.create_user(
            username='vao_conv', password='x', company=self.company)
        self.source = SourceVeille.objects.create(
            company=self.company, code='tuyau', libelle='Tuyau partenaire',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)

    def _avis(self, **extra):
        params = {
            'company': self.company, 'source': self.source,
            'objet': 'Pompage solaire à Figuig',
            'acheteur': 'Commune de Figuig',
            'reference_avis': 'AO-2026-042',
            'date_limite_remise': timezone.now() + timedelta(days=20),
        }
        params.update(extra)
        return AvisMarche.objects.create(**params)


class ConversionTests(_Base):
    def test_retenir_cree_EXACTEMENT_une_affaire_referencee(self):
        avis = self._avis()

        avis, appel_offre_id, cree = retenir_avis(avis, user=self.user)

        self.assertTrue(cree)
        self.assertEqual(AppelOffre.objects.filter(
            company=self.company).count(), 1)
        affaire = AppelOffre.objects.get(pk=appel_offre_id)
        self.assertEqual(affaire.statut, AppelOffre.Statut.IDENTIFIE)
        self.assertEqual(affaire.reference_acheteur, 'AO-2026-042')
        # NOTRE référence vient de la plateforme, jamais recopiée de l'avis.
        self.assertTrue(affaire.reference.startswith('AO-'))
        self.assertNotEqual(affaire.reference, affaire.reference_acheteur)

    def test_l_avis_passe_CONVERTI_et_porte_l_entier_opaque(self):
        avis = self._avis()
        avis, appel_offre_id, _ = retenir_avis(avis, user=self.user)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.CONVERTI)
        self.assertEqual(avis.appel_offre_id, appel_offre_id)

    def test_le_fond_de_l_avis_est_reporte_sur_l_affaire(self):
        avis = self._avis(lot='Lot 2', montant_estime='450000.00')
        _avis, appel_offre_id, _ = retenir_avis(avis, user=self.user)
        affaire = AppelOffre.objects.get(pk=appel_offre_id)
        self.assertEqual(affaire.objet, 'Pompage solaire à Figuig')
        self.assertEqual(affaire.acheteur, 'Commune de Figuig')
        self.assertEqual(affaire.lot, 'Lot 2')

    def test_les_deux_transitions_sont_journalisees_au_chatter(self):
        avis = self._avis()
        retenir_avis(avis, user=self.user, motif='Dans notre métier.')
        activites = Activity.objects.filter(company=self.company).order_by(
            'id')
        self.assertEqual([a.new_value for a in activites],
                         ['Retenu', "Converti en appel d'offres"])


class IdempotenceTests(_Base):
    def test_re_cliquer_ne_cree_PAS_de_doublon(self):
        avis = self._avis()
        _avis, premier, cree_1 = retenir_avis(avis, user=self.user)
        _avis, second, cree_2 = retenir_avis(avis, user=self.user)

        self.assertTrue(cree_1)
        self.assertFalse(cree_2)
        self.assertEqual(premier, second)
        self.assertEqual(AppelOffre.objects.count(), 1)

    def test_deux_avis_de_MEME_reference_partagent_l_affaire(self):
        """La déduplication d'``apps.ao`` se fait par référence acheteur."""
        premier = self._avis()
        second = self._avis(reference_avis='AO-2026-042',
                            ref_consultation='9002')
        _a, id_1, cree_1 = retenir_avis(premier, user=self.user)
        _b, id_2, cree_2 = retenir_avis(second, user=self.user)

        self.assertTrue(cree_1)
        self.assertFalse(cree_2)
        self.assertEqual(id_1, id_2)
        self.assertEqual(AppelOffre.objects.count(), 1)


class AvisSansReferenceTests(_Base):
    """Le cas FRDISI : une consultation PRIVÉE n'a aucune référence publiée.

    Refuser la conversion ici viderait le groupe de son sens — c'est
    précisément l'avis qu'aucun dispositif automatique n'aurait vu.
    """

    def test_un_avis_capte_par_whatsapp_se_convertit_quand_meme(self):
        avis = self._avis(reference_avis='', ref_consultation='',
                          informateur=Informateur.PARTENAIRE)

        _avis, appel_offre_id, cree = retenir_avis(avis, user=self.user)

        self.assertTrue(cree)
        affaire = AppelOffre.objects.get(pk=appel_offre_id)
        self.assertEqual(affaire.reference_acheteur, f'VEILLE-{avis.pk}')

    def test_la_reference_interne_deduplique_aussi(self):
        avis = self._avis(reference_avis='', ref_consultation='')
        retenir_avis(avis, user=self.user)
        retenir_avis(avis, user=self.user)
        self.assertEqual(AppelOffre.objects.count(), 1)


class MarcheArriereTests(_Base):
    def test_un_avis_IGNORE_peut_etre_retenu(self):
        """« Ignorer » est un geste d'une seconde : s'en dédire aussi."""
        avis = self._avis(statut=StatutAvis.IGNORE)
        _avis, appel_offre_id, cree = retenir_avis(avis, user=self.user)
        self.assertTrue(cree)
        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.CONVERTI)

    def test_un_avis_EXPIRE_ne_se_retient_plus(self):
        avis = self._avis(statut=StatutAvis.EXPIRE)
        with self.assertRaises(ValidationError):
            retenir_avis(avis, user=self.user)
        self.assertEqual(AppelOffre.objects.count(), 0)


class IgnorerTests(_Base):
    def test_ignorer_PROPOSE_la_regle_sans_jamais_la_creer(self):
        avis = self._avis()

        avis, proposition = ignorer_avis(avis, user=self.user,
                                         motif='Hors périmètre')

        avis.refresh_from_db()
        self.assertEqual(avis.statut, StatutAvis.IGNORE)
        self.assertEqual(proposition['valeur'], 'Commune de Figuig')
        self.assertFalse(proposition['existe_deja'])
        self.assertEqual(RegleExclusion.objects.count(), 0)

    def test_une_regle_JUMELLE_deja_enregistree_est_signalee(self):
        from apps.veille_ao.models import PorteeExclusion

        regle = RegleExclusion.objects.create(
            company=self.company, portee=PorteeExclusion.ACHETEUR,
            valeur='Commune de Figuig', motif='Déjà écarté', actif=False)
        avis = self._avis()

        _avis, proposition = ignorer_avis(avis, user=self.user)

        self.assertTrue(proposition['existe_deja'])
        self.assertEqual(proposition['regle_existante_id'], regle.pk)
        self.assertFalse(proposition['regle_existante_active'])


class EndpointsTests(_Base):
    def _api(self, permissions=('veille_ao_voir', 'veille_ao_gerer'),
             suffixe='gerant'):
        role = Role.objects.create(
            company=self.company, nom=f'Rôle {suffixe}',
            permissions=list(permissions))
        user = CustomUser.objects.create_user(
            username=f'vao_conv_{suffixe}', password='x',
            company=self.company, role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_l_ecran_retient_et_recoit_l_identifiant_de_l_affaire(self):
        avis = self._avis()
        api = self._api()

        reponse = api.post(
            f'/api/django/veille_ao/avis/{avis.pk}/retenir/', {}, 'json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertTrue(reponse.data['appel_offre_id'])
        self.assertTrue(reponse.data['appel_offre_cree'])
        self.assertEqual(reponse.data['statut'], StatutAvis.CONVERTI)

    def test_l_ecran_ignore_et_recoit_la_regle_proposee(self):
        avis = self._avis()
        api = self._api()

        reponse = api.post(
            f'/api/django/veille_ao/avis/{avis.pk}/ignorer/',
            {'motif': 'Hors périmètre'}, 'json')

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['statut'], StatutAvis.IGNORE)
        self.assertIn('portee', reponse.data['regle_proposee'])

    def test_un_lecteur_seul_ne_peut_ni_retenir_ni_ignorer(self):
        avis = self._avis()
        api = self._api(['veille_ao_voir'], 'lecteur')
        for geste in ('retenir', 'ignorer'):
            self.assertEqual(
                api.post(f'/api/django/veille_ao/avis/{avis.pk}/{geste}/',
                         {}, 'json').status_code, 403, geste)

    def test_un_avis_d_une_AUTRE_societe_est_introuvable(self):
        autre = Company.objects.create(nom='Autre société')
        source = SourceVeille.objects.create(
            company=autre, code='tuyau', libelle='Tuyau',
            type_source=TypeSource.TUYAU_PARTENAIRE, actif=True)
        etranger = AvisMarche.objects.create(
            company=autre, source=source, objet='Ailleurs')
        api = self._api()

        reponse = api.post(
            f'/api/django/veille_ao/avis/{etranger.pk}/retenir/', {}, 'json')

        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(AppelOffre.objects.count(), 0)

    def test_une_transition_interdite_repond_400_en_francais(self):
        avis = self._avis(statut=StatutAvis.EXPIRE)
        api = self._api()

        reponse = api.post(
            f'/api/django/veille_ao/avis/{avis.pk}/retenir/', {}, 'json')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('Transition interdite', str(reponse.data))


class DecouplageCrossAppTests(SimpleTestCase):
    """« Aucun import de ``apps.ao.models`` depuis ``veille_ao``. »

    Le contrat import-linter, vérifié ici plutôt qu'attendu de la CI : le seul
    contact autorisé est ``apps.ao.services``, et le lien retour est un ENTIER
    opaque.
    """

    def test_le_SEUL_import_vers_apps_ao_est_son_services(self):
        imports = []
        for chemin in sorted(MODULE_DIR.rglob('*.py')):
            relatif = chemin.relative_to(MODULE_DIR).as_posix()
            if relatif.startswith(('migrations/', 'tests/')):
                continue
            arbre = ast.parse(chemin.read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                module = ''
                if isinstance(noeud, ast.ImportFrom):
                    module = noeud.module or ''
                elif isinstance(noeud, ast.Import):
                    module = ' '.join(a.name for a in noeud.names)
                if module.startswith('apps.ao'):
                    imports.append(module)
        # La frontière inter-apps du dépôt autorise DEUX portes, et deux
        # seulement : `services` pour ÉCRIRE/orchestrer (VAO30 crée l'affaire)
        # et `selectors` pour LIRE (VAO31 lit l'issue de l'AO pour attribuer le
        # chiffre d'affaires). Ce qui reste interdit — et ce que ce test
        # attrape — c'est un import de `apps.ao.models` ou `apps.ao.views`.
        self.assertEqual(sorted(set(imports)),
                         ['apps.ao.selectors', 'apps.ao.services'])

    def test_le_lien_vers_l_affaire_reste_un_ENTIER(self):
        from apps.veille_ao.models import AvisMarche as Modele

        champ = Modele._meta.get_field('appel_offre_id')
        self.assertEqual(champ.get_internal_type(), 'PositiveIntegerField')
