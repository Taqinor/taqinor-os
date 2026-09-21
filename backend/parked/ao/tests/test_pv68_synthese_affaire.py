"""PV68 — le total de calepinage d'une AFFAIRE existe enfin quelque part.

L'écran « Affaire » affichait ses toitures une par une : le total de modules
d'un dossier à plusieurs bâtiments n'existait NULLE PART et se refaisait à la
main — donc faux un jour sur deux.

Ce que ce module VERROUILLE :

  1. **Seule la variante RETENUE compte.** Les alternatives et les
     sensibilités sont des hypothèses, pas l'offre : les additionner
     gonflerait le dossier d'un facteur trois.
  2. **Les toitures NON calepinées figurent quand même**, ``calepinee:
     False`` — c'est le trou qu'un chargé d'affaires doit voir, et le taire
     ferait passer un dossier incomplet pour un dossier fini.
  3. **Cloisonnement société** : une affaire d'un autre tenant ne contribue
     jamais, et un identifiant nu SANS société est REFUSÉ.
  4. **Le bloc est publié sur le détail de l'affaire**, avec la clé TOUJOURS
     présente (``null`` en liste, pour ne pas payer deux requêtes par ligne).
  5. **Aucun coût, aucune marge** n'entre dans la synthèse (règle AOF2).

Run :
    python manage.py test apps.ao.tests.test_pv68_synthese_affaire -v2
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ao import selectors
from apps.ao.models import (
    AppelOffre, BatimentAO, ToitureAO, VarianteCalepinage,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/ao/appels-offres/'


class BasePv68(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='PV68 Co', slug='pv68-co')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        self.user = User.objects.create_user(
            username='pv68_dir', password='x', company=self.company,
            role=role)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.ao = AppelOffre.objects.create(
            company=self.company, reference='AO-68-1', objet='Synthèse')
        self.batiment = BatimentAO.objects.create(
            company=self.company, appel_offre=self.ao, code='A')
        self.toiture_1 = self._toiture('05H')
        self.toiture_2 = self._toiture('06H')

    def _toiture(self, code, batiment=None, company=None):
        return ToitureAO.objects.create(
            company=company or self.company, batiment=batiment or self.batiment,
            code_document=code, designation=f'Toiture {code}',
            contour_local_m=[[0, 0], [30, 0], [30, 18], [0, 18]])

    def _variante(self, toiture, modules, kwc, *, retenue=True,
                  role=VarianteCalepinage.Role.RETENUE, nom='Calepinage',
                  appel_offre=None, company=None):
        return VarianteCalepinage.objects.create(
            company=company or self.company, toiture=toiture,
            appel_offre=appel_offre or self.ao, role=role, nom=nom,
            est_retenue=retenue,
            resultat={'total_modules': modules, 'kwc': kwc},
            preuve={'optimal': True, 'methode': 'dp_exact_1cm'},
            statut=VarianteCalepinage.Statut.PUBLIABLE)

    def _synthese(self, **kwargs):
        return selectors.synthese_calepinage_affaire(self.ao, **kwargs)


class LesSommesSontJustes(BasePv68):
    def test_deux_toitures_retenues_s_additionnent(self):
        self._variante(self.toiture_1, 150, 93.75)
        self._variante(self.toiture_2, 96, 60.0)
        synthese = self._synthese()
        self.assertEqual(synthese['total_modules'], 246)
        self.assertAlmostEqual(synthese['total_kwc'], 153.75, places=3)
        self.assertEqual(synthese['toitures_total'], 2)
        self.assertEqual(synthese['toitures_calepinees'], 2)

    def test_seule_la_variante_RETENUE_compte(self):
        """Une alternative est une hypothèse : l'additionner gonflerait tout."""
        self._variante(self.toiture_1, 150, 93.75)
        self._variante(self.toiture_1, 999, 999.0, retenue=False,
                       role=VarianteCalepinage.Role.ALTERNATIVE,
                       nom='Alternative')
        self._variante(self.toiture_1, 777, 777.0, retenue=False,
                       role=VarianteCalepinage.Role.SENSIBILITE,
                       nom='Sensibilité')
        synthese = self._synthese()
        self.assertEqual(synthese['total_modules'], 150)
        self.assertEqual(synthese['toitures_calepinees'], 1)

    def test_une_affaire_sans_toiture_rend_des_zeros_EXPLICITES(self):
        vide = AppelOffre.objects.create(
            company=self.company, reference='AO-68-VIDE', objet='Vide')
        synthese = selectors.synthese_calepinage_affaire(vide)
        self.assertEqual(synthese['total_modules'], 0)
        self.assertEqual(synthese['total_kwc'], 0.0)
        self.assertEqual(synthese['toitures'], [])
        self.assertEqual(synthese['toitures_total'], 0)
        self.assertEqual(synthese['toitures_calepinees'], 0)

    def test_les_cles_sont_les_MEMES_dans_tous_les_cas(self):
        attendues = {'total_modules', 'total_kwc', 'toitures_total',
                     'toitures_calepinees', 'toitures'}
        self.assertEqual(set(self._synthese()), attendues)
        self._variante(self.toiture_1, 150, 93.75)
        self.assertEqual(set(self._synthese()), attendues)


class LesToituresNonCalepineesSontVUES(BasePv68):
    """Taire le trou ferait passer un dossier incomplet pour un dossier fini."""

    def test_une_toiture_sans_variante_retenue_figure_a_zero(self):
        self._variante(self.toiture_1, 150, 93.75)
        lignes = {ligne['toiture']: ligne for ligne in
                  self._synthese()['toitures']}
        self.assertEqual(len(lignes), 2)
        self.assertTrue(lignes[self.toiture_1.pk]['calepinee'])
        vide = lignes[self.toiture_2.pk]
        self.assertFalse(vide['calepinee'])
        self.assertEqual(vide['modules'], 0)
        self.assertEqual(vide['kwc'], 0.0)
        self.assertIsNone(vide['variante'])
        self.assertEqual(vide['statut'], '')
        self.assertIsNone(vide['optimal'])

    def test_chaque_ligne_porte_les_MEMES_cles(self):
        self._variante(self.toiture_1, 150, 93.75)
        lignes = self._synthese()['toitures']
        attendues = set(lignes[0])
        for ligne in lignes:
            self.assertEqual(set(ligne), attendues)
        self.assertLessEqual(
            {'toiture', 'code_document', 'batiment', 'batiment_code',
             'calepinee', 'variante', 'modules', 'kwc'}, attendues)

    def test_la_ligne_reprend_la_preuve_de_la_variante(self):
        self._variante(self.toiture_1, 150, 93.75)
        ligne = next(ligne for ligne in self._synthese()['toitures']
                     if ligne['toiture'] == self.toiture_1.pk)
        self.assertEqual(ligne['modules'], 150)
        self.assertEqual(ligne['methode'], 'dp_exact_1cm')
        self.assertTrue(ligne['optimal'])
        self.assertEqual(ligne['batiment_code'], 'A')
        self.assertEqual(ligne['code_document'], '05H')

    def test_aucun_cout_ni_aucune_marge_dans_la_synthese(self):
        """AOF2 — l'économie vit derrière ``ao_rentabilite_voir``, ailleurs."""
        self._variante(self.toiture_1, 150, 93.75)
        synthese = self._synthese()
        interdits = ('prix', 'cout', 'marge', 'benefice', 'montant', 'tva')
        cles = set(synthese) | {c for ligne in synthese['toitures']
                                for c in ligne}
        for cle in cles:
            for interdit in interdits:
                self.assertNotIn(interdit, cle.lower())


class LeCloisonnementSociete(BasePv68):
    def test_une_toiture_d_une_autre_societe_ne_contribue_pas(self):
        autre = Company.objects.create(nom='PV68 Voisin', slug='pv68-voisin')
        ao_voisin = AppelOffre.objects.create(
            company=autre, reference='AO-68-Z', objet='Ailleurs')
        batiment = BatimentAO.objects.create(company=autre,
                                             appel_offre=ao_voisin, code='Z')
        toiture = self._toiture('99H', batiment=batiment, company=autre)
        self._variante(toiture, 500, 300.0, appel_offre=ao_voisin,
                       company=autre)
        self._variante(self.toiture_1, 150, 93.75)
        self.assertEqual(self._synthese()['total_modules'], 150)
        self.assertEqual(
            selectors.synthese_calepinage_affaire(ao_voisin)['total_modules'],
            500)

    def test_une_societe_qui_ne_possede_pas_l_affaire_ne_voit_rien(self):
        autre = Company.objects.create(nom='PV68 Tiers', slug='pv68-tiers')
        self._variante(self.toiture_1, 150, 93.75)
        synthese = selectors.synthese_calepinage_affaire(self.ao.pk,
                                                         company=autre)
        self.assertEqual(synthese['total_modules'], 0)
        self.assertEqual(synthese['toitures_total'], 0)

    def test_un_identifiant_nu_SANS_societe_est_refuse(self):
        with self.assertRaises(ValueError):
            selectors.synthese_calepinage_affaire(self.ao.pk)

    def test_un_identifiant_avec_sa_societe_est_accepte(self):
        self._variante(self.toiture_1, 150, 93.75)
        synthese = selectors.synthese_calepinage_affaire(
            self.ao.pk, company=self.company)
        self.assertEqual(synthese['total_modules'], 150)


class LeBlocEstPublieSurLeDetailDeLAffaire(BasePv68):
    def test_le_detail_porte_la_synthese(self):
        self._variante(self.toiture_1, 150, 93.75)
        self._variante(self.toiture_2, 96, 60.0)
        reponse = self.api.get(f'{URL}{self.ao.pk}/')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        synthese = reponse.data['synthese_calepinage']
        self.assertEqual(synthese['total_modules'], 246)
        self.assertEqual(len(synthese['toitures']), 2)

    def test_la_cle_existe_TOUJOURS_meme_en_liste(self):
        """Un écran qui reçoit parfois une clé finit par tester la mauvaise."""
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200)
        donnees = reponse.data
        lignes = donnees['results'] if isinstance(donnees, dict) else donnees
        self.assertTrue(lignes)
        for ligne in lignes:
            self.assertIn('synthese_calepinage', ligne)
            self.assertIsNone(ligne['synthese_calepinage'])

    def test_l_affaire_d_une_autre_societe_reste_introuvable(self):
        autre = Company.objects.create(nom='PV68 Autre', slug='pv68-autre')
        etrangere = AppelOffre.objects.create(
            company=autre, reference='AO-68-X', objet='Ailleurs')
        reponse = self.api.get(f'{URL}{etrangere.pk}/')
        self.assertEqual(reponse.status_code, 404)

    def test_le_bloc_survit_a_une_modification(self):
        self._variante(self.toiture_1, 150, 93.75)
        reponse = self.api.patch(f'{URL}{self.ao.pk}/',
                                 {'objet': 'Synthèse modifiée'},
                                 format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(
            reponse.data['synthese_calepinage']['total_modules'], 150)


class LesMontantsRestentDesDecimales(BasePv68):
    """Garde-fou de type : un total de kWc n'est pas une chaîne."""

    def test_les_totaux_sont_des_nombres(self):
        self._variante(self.toiture_1, 150, 93.75)
        synthese = self._synthese()
        self.assertIsInstance(synthese['total_modules'], int)
        self.assertIsInstance(synthese['total_kwc'], float)
        self.assertIsInstance(synthese['toitures'][0]['modules'], int)
        self.assertIsInstance(synthese['toitures'][0]['kwc'], float)
