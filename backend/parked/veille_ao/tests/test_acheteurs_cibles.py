"""VAO29 — le carnet des acheteurs à DÉMARCHER.

Constat central du groupe : ce marché-là ne se surveille pas, il se démarche.
La seule façon de recevoir la PROCHAINE consultation FRDISI est d'être sur la
liste d'invitation — et aucun collecteur, aucun agrégateur, aucun flux RSS ne
peut y mettre Taqinor. C'est un travail de relation, et ce carnet en est
l'outil.

Le « Done = » :
  * carnet CRUD scopé société ;
  * une relance due remonte dans le centre d'échéances ;
  * lien vers le lead CRM par identifiant OPAQUE (aucun import de
    ``apps.crm.models``) ;
  * aucun nom d'organisme INVENTÉ nulle part.
"""
import ast
import pathlib
from datetime import timedelta

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company, CustomUser
from apps.roles.models import Role

from apps.veille_ao.models import (
    AcheteurCible, StatutRelation, TypeAcheteur,
)
from apps.veille_ao.selectors import (
    acheteurs_sans_lead, compte_relances_dues, relances_dues,
)

URL = '/api/django/veille_ao/acheteurs-cibles/'
MODULE_DIR = pathlib.Path(__file__).resolve().parents[1]


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='ACME Carnet')

    def _api(self, permissions=('veille_ao_voir', 'veille_ao_gerer'),
             suffixe='carnet'):
        role = Role.objects.create(
            company=self.company, nom=f'Rôle {suffixe}',
            permissions=list(permissions))
        user = CustomUser.objects.create_user(
            username=f'vao_{suffixe}', password='x', company=self.company,
            role=role)
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def _acheteur(self, nom, *, jours_relance=None, **extra):
        relance = (timezone.localdate() + timedelta(days=jours_relance)
                   if jours_relance is not None else None)
        return AcheteurCible.objects.create(
            company=self.company, nom=nom, prochaine_relance=relance, **extra)


class CrudTests(_Base):
    def test_le_carnet_se_cree_par_l_API_avec_les_champs_de_l_ecran(self):
        api = self._api()
        reponse = api.post(URL, {
            'nom': 'Organisme réel saisi par le fondateur',
            'type': 'fondation',
            'contact': 'M. X — 06 00 00 00 00',
            'prochaine_relance': '2026-12-01',
            'notes': 'Rencontré au salon.',
        }, 'json')

        self.assertEqual(reponse.status_code, 201, reponse.data)
        acheteur = AcheteurCible.objects.get(company=self.company)
        self.assertEqual(acheteur.type, TypeAcheteur.FONDATION)
        self.assertEqual(acheteur.statut_relation, StatutRelation.A_CONTACTER)

    def test_la_societe_est_FORCEE_serveur(self):
        autre = Company.objects.create(nom='Autre société')
        api = self._api()
        api.post(URL, {'nom': 'Test', 'company': autre.pk}, 'json')
        self.assertEqual(AcheteurCible.objects.get().company, self.company)

    def test_le_carnet_d_une_AUTRE_societe_est_invisible(self):
        autre = Company.objects.create(nom='Autre société')
        AcheteurCible.objects.create(company=autre, nom='Ailleurs')
        api = self._api()

        corps = api.get(URL).data
        lignes = corps['results'] if isinstance(corps, dict) else corps

        self.assertEqual([ligne['nom'] for ligne in lignes], [])

    def test_deux_societes_peuvent_porter_le_MEME_nom(self):
        """L'unicité est par SOCIÉTÉ : deux tenants démarchent les mêmes."""
        autre = Company.objects.create(nom='Autre société')
        self._acheteur('Même organisme')
        AcheteurCible.objects.create(company=autre, nom='Même organisme')
        self.assertEqual(AcheteurCible.objects.count(), 2)

    def test_un_lecteur_seul_ne_peut_pas_ecrire(self):
        api = self._api(['veille_ao_voir'], 'lecteur')
        self.assertEqual(api.post(URL, {'nom': 'X'}, 'json').status_code, 403)

    def test_un_role_etranger_ne_lit_rien(self):
        api = self._api(['crm_voir'], 'etranger')
        self.assertEqual(api.get(URL).status_code, 403)


class RelancesDuesTests(_Base):
    def test_une_relance_echue_remonte_dans_le_centre_d_echeances(self):
        self._acheteur('Échue', jours_relance=-2)
        self._acheteur('Aujourd’hui', jours_relance=0)
        self._acheteur('Plus tard', jours_relance=30)
        self._acheteur('Sans relance')

        dues = list(relances_dues(self.company))

        self.assertEqual([a.nom for a in dues], ['Échue', 'Aujourd’hui'])

    def test_les_relances_sont_triees_par_URGENCE(self):
        self._acheteur('Moins urgente', jours_relance=-1)
        self._acheteur('Plus urgente', jours_relance=-40)
        self.assertEqual(
            [a.nom for a in relances_dues(self.company)],
            ['Plus urgente', 'Moins urgente'])

    def test_une_relation_SANS_SUITE_ne_se_relance_plus(self):
        """Relancer quelqu'un qui a dit non use la relation."""
        self._acheteur('Sans suite', jours_relance=-10,
                       statut_relation=StatutRelation.SANS_SUITE)
        self.assertEqual(compte_relances_dues(self.company), 0)

    def test_le_compteur_est_scope_societe(self):
        autre = Company.objects.create(nom='Autre société')
        AcheteurCible.objects.create(
            company=autre, nom='Ailleurs',
            prochaine_relance=timezone.localdate() - timedelta(days=5))
        self.assertEqual(compte_relances_dues(self.company), 0)

    def test_relance_due_est_lisible_sur_la_ligne(self):
        echue = self._acheteur('Échue', jours_relance=-1)
        future = self._acheteur('Future', jours_relance=1)
        self.assertTrue(echue.relance_due)
        self.assertFalse(future.relance_due)

    def test_l_ecran_recoit_relance_due_et_le_libelle_du_statut(self):
        self._acheteur('Échue', jours_relance=-1)
        api = self._api()

        corps = api.get(URL).data
        ligne = (corps['results'] if isinstance(corps, dict) else corps)[0]

        self.assertTrue(ligne['relance_due'])
        self.assertIn('statut_relation_display', ligne)
        self.assertIn('lead_id', ligne)


class LienCrmOpaqueTests(_Base):
    def test_le_lead_est_un_ENTIER_opaque_jamais_une_cle_etrangere(self):
        champ = AcheteurCible._meta.get_field('lead_id')
        self.assertEqual(champ.get_internal_type(), 'PositiveIntegerField')

    def test_un_acheteur_sans_lead_est_identifiable(self):
        self._acheteur('Sans lead')
        self._acheteur('Avec lead', lead_id=17)
        self.assertEqual([a.nom for a in acheteurs_sans_lead(self.company)],
                         ['Sans lead'])


class DecouplageTests(SimpleTestCase):
    """Le contrat import-linter, vérifié ici plutôt qu'attendu de la CI."""

    def test_le_module_n_importe_JAMAIS_les_modeles_du_crm_ni_de_ao(self):
        fautifs = []
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
                for interdit in ('apps.crm.models', 'apps.ao.models',
                                 'apps.crm.views', 'apps.ao.views'):
                    if interdit in module:
                        fautifs.append(f'{relatif}:{noeud.lineno} {module}')
        self.assertEqual(fautifs, [], fautifs)


class AucunNomInventeTests(SimpleTestCase):
    """« Aucun nom d'organisme inventé dans le seed. »

    Le carnet part VIDE : il n'y a aucun seed d'organismes, seulement des
    CATÉGORIES. Un nom faux dans un carnet de prospection est pire qu'un
    carnet vide — il se recopie, il se démarche, et il fait perdre du temps.
    """

    def test_aucune_commande_de_seed_ne_cree_d_acheteur_cible(self):
        commandes = MODULE_DIR / 'management' / 'commands'
        for chemin in sorted(commandes.glob('*.py')):
            texte = chemin.read_text(encoding='utf-8')
            self.assertNotIn('AcheteurCible', texte, chemin.name)

    def test_le_modele_n_offre_que_des_CATEGORIES(self):
        valeurs = {v for v, _ in TypeAcheteur.choices}
        self.assertEqual(valeurs, {
            'fondation', 'universite_privee', 'clinique', 'groupe_hotelier',
            'industriel', 'cooperative_agricole', 'promoteur', 'collectivite',
        })
