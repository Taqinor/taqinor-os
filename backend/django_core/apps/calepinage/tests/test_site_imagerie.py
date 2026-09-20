"""CAL47 — l'imagerie et le géocodage deviennent un RÉGLAGE société.

CE QUI EST PROUVÉ ICI
---------------------
* **ÉQUIVALENCE, d'abord** — une société qui n'a RIEN réglé obtient exactement
  le comportement d'aujourd'hui : ``imagerie`` vaut ``{}`` sur l'endpoint, et
  le sélecteur résolu ne rend que des inconnues. Aucun pays, aucun fournisseur,
  aucune altitude n'est inventé (c'est la condition posée par la tâche, et
  c'est ce qui rend le réglage déployable sans rien casser) ;
* l'endpoint rend le contrat CAL46 (``contract_samples/site_imagerie.json``)
  dès que la section est réglée : les HUIT clés, toujours toutes présentes ;
* les refus sont FRANÇAIS et NOMMENT le champ fautif — jamais un « non
  enregistré » générique : fournisseur inconnu, ``google_solar`` gaté (CAL51),
  attribution IGN manquante, fournisseur hors liste autorisée, pays non
  couvert, altitude sans source, pays mal formé, fuseau inconnu, clé inconnue ;
* l'isolation société tient : le réglage d'une société ne fuit jamais ;
* une écriture PARTIELLE d'une autre section ne touche pas ``imagerie``.

Le test de l'endpoint HTTP passe par le vrai routeur (``/api/django/
calepinage/parametres/``) avec les permissions du module, jamais par un appel
direct à la vue.

Run :
    python manage.py test apps.calepinage.tests.test_site_imagerie -v2
"""
import json
import pathlib

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.calepinage.selectors import imagerie_site, parametres_de_societe
from apps.calepinage.services.parametres import (
    ReglageInvalide,
    enregistrer_parametres,
)
from apps.calepinage.services.site import (
    CLES,
    FOURNISSEURS,
    fournisseur_actif,
    normaliser_section_imagerie,
    section_vide,
)
from apps.roles.models import DIRECTEUR_PERMISSIONS, TECHNICIEN_PERMISSIONS, Role
from authentication.models import Company

User = get_user_model()

URL = '/api/django/calepinage/parametres/'

CONTRAT = json.loads(
    (pathlib.Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'site_imagerie.json').read_text(encoding='utf-8'))

#: La section complète du contrat, telle qu'elle sera renvoyée.
REGLEE = CONTRAT['exemple']['imagerie']


def _refus(test, donnees, champ):
    """Écrit ``donnees`` dans la section et rend le refus attendu."""
    with test.assertRaises(ReglageInvalide) as capture:
        normaliser_section_imagerie(donnees)
    test.assertEqual(capture.exception.champ, champ,
                     f'{champ} attendu, message : {capture.exception}')
    return capture.exception


class ContratTest(SimpleTestCase):
    """La forme produite EST celle du contrat publié (PACT10)."""

    def test_les_huit_cles_du_contrat_sont_celles_du_service(self):
        self.assertEqual(sorted(CLES), sorted(REGLEE))

    def test_une_section_reglee_rend_les_huit_cles(self):
        self.assertEqual(sorted(normaliser_section_imagerie(REGLEE)),
                         sorted(REGLEE))

    def test_l_exemple_du_contrat_traverse_sans_etre_modifie(self):
        """Le contrat publié doit être ACCEPTÉ tel quel — sinon il ment."""
        self.assertEqual(normaliser_section_imagerie(REGLEE), REGLEE)

    def test_section_vide_porte_les_huit_cles_toutes_inconnues(self):
        vide = section_vide()
        self.assertEqual(sorted(vide), sorted(CLES))
        self.assertIsNone(vide['pays'])
        self.assertEqual(vide['fournisseurs_autorises'], [])


class EquivalenceTest(SimpleTestCase):
    """Rien n'est inventé : à vide, le comportement d'aujourd'hui."""

    def test_section_vide_reste_vide(self):
        """``{}`` n'est PAS complété : c'est la garantie d'équivalence."""
        self.assertEqual(normaliser_section_imagerie({}), {})
        self.assertEqual(normaliser_section_imagerie(None), {})

    def test_aucun_fournisseur_actif_sans_reglage(self):
        self.assertIsNone(fournisseur_actif({}))
        self.assertIsNone(fournisseur_actif(section_vide()))

    def test_le_premier_autorise_fait_l_actif(self):
        self.assertEqual(
            fournisseur_actif({'fournisseurs_autorises': ['mapbox',
                                                          'maptiler']}),
            'mapbox')

    def test_le_choix_explicite_prime(self):
        self.assertEqual(
            fournisseur_actif({'fournisseur_imagerie': 'maptiler',
                               'fournisseurs_autorises': ['mapbox']}),
            'maptiler')


class NormalisationTest(SimpleTestCase):
    """Ce qui est accepté est RANGÉ, pas seulement toléré."""

    def test_pays_mis_en_minuscules(self):
        self.assertEqual(normaliser_section_imagerie({'pays': 'MA'})['pays'],
                         'ma')

    def test_chaine_blanche_vaut_inconnu(self):
        section = normaliser_section_imagerie({'pays': '  ',
                                               'attribution': '   '})
        self.assertIsNone(section['pays'])
        self.assertIsNone(section['attribution'])

    def test_doublons_de_fournisseurs_retires_l_ordre_garde(self):
        section = normaliser_section_imagerie({
            'fournisseurs_autorises': ['mapbox', 'maptiler', 'mapbox'],
        })
        self.assertEqual(section['fournisseurs_autorises'],
                         ['mapbox', 'maptiler'])

    def test_altitude_entiere_devient_un_nombre(self):
        section = normaliser_section_imagerie(
            {'altitude_m': 145, 'source_altitude': 'relevé GPS'})
        self.assertEqual(section['altitude_m'], 145.0)

    def test_les_autres_cles_restent_inconnues(self):
        section = normaliser_section_imagerie({'pays': 'ma'})
        self.assertEqual(sorted(section), sorted(CLES))
        self.assertIsNone(section['fuseau'])
        self.assertEqual(section['calques_optionnels'], [])


class RefusTest(SimpleTestCase):
    """Chaque refus nomme SON champ, en français."""

    def test_cle_inconnue_nommee(self):
        erreur = _refus(self, {'fournisseur': 'maptiler'}, 'fournisseur')
        self.assertIn('fournisseur', str(erreur))

    def test_fournisseur_inconnu_nomme(self):
        erreur = _refus(self, {'fournisseur_imagerie': 'bing'},
                        'fournisseur_imagerie')
        self.assertIn('bing', str(erreur))

    def test_google_solar_est_gate(self):
        """CAL51 : le refus le NOMME plutôt que de le noyer dans « inconnu »."""
        erreur = _refus(self, {'fournisseur_imagerie': 'google_solar'},
                        'fournisseur_imagerie')
        self.assertIn('CAL51', str(erreur))
        self.assertNotIn('google_solar', FOURNISSEURS)

    def test_google_solar_refuse_aussi_dans_la_liste(self):
        _refus(self, {'fournisseurs_autorises': ['google_solar']},
               'fournisseurs_autorises')

    def test_fournisseur_hors_liste_autorisee(self):
        _refus(self, {'fournisseur_imagerie': 'mapbox',
                      'fournisseurs_autorises': ['maptiler']},
               'fournisseur_imagerie')

    def test_ign_sans_attribution_refuse(self):
        """L'IGN impose sa mention : elle est SAISIE, jamais inventée."""
        erreur = _refus(self, {'pays': 'fr',
                               'fournisseur_imagerie': 'ign_bd_ortho'},
                        'attribution')
        self.assertIn('mention légale', str(erreur))

    def test_ign_hors_france_refuse(self):
        _refus(self, {'pays': 'ma', 'fournisseur_imagerie': 'ign_bd_ortho',
                      'attribution': '© IGN'}, 'fournisseur_imagerie')

    def test_altitude_sans_source_refusee(self):
        """Zéro chiffre invraisemblable : une altitude dit d'où elle vient."""
        erreur = _refus(self, {'altitude_m': 145}, 'source_altitude')
        self.assertIn("Source de l'altitude", str(erreur))

    def test_altitude_hors_plage_refusee(self):
        _refus(self, {'altitude_m': 99000, 'source_altitude': 'x'},
               'altitude_m')

    def test_altitude_non_numerique_refusee(self):
        _refus(self, {'altitude_m': '145', 'source_altitude': 'x'},
               'altitude_m')

    def test_pays_mal_forme_refuse(self):
        erreur = _refus(self, {'pays': 'maroc'}, 'pays')
        self.assertIn('deux lettres', str(erreur))

    def test_fuseau_inconnu_refuse(self):
        _refus(self, {'fuseau': 'Africa/Casablanca_Ouest'}, 'fuseau')

    def test_fuseau_mal_forme_refuse(self):
        _refus(self, {'fuseau': 'Africa / Casablanca'}, 'fuseau')

    def test_fuseau_valide_accepte(self):
        section = normaliser_section_imagerie({'fuseau': 'Africa/Casablanca'})
        self.assertEqual(section['fuseau'], 'Africa/Casablanca')

    def test_liste_qui_n_en_est_pas_une(self):
        _refus(self, {'calques_optionnels': 'cadastre'}, 'calques_optionnels')

    def test_calque_mal_forme_refuse(self):
        _refus(self, {'calques_optionnels': ['Cadastre 2024']},
               'calques_optionnels')


class EcritureEtLectureTest(TestCase):
    """Le service d'écriture et le sélecteur, bout en bout."""

    def setUp(self):
        self.company = Company.objects.create(nom='Imagerie Co',
                                              slug='imagerie-co-47')
        self.autre = Company.objects.create(nom='Autre Imagerie',
                                            slug='autre-imagerie-47')

    def test_societe_sans_reglage_inchangee(self):
        """LA garantie : rien réglé ⇒ comportement d'aujourd'hui."""
        self.assertEqual(parametres_de_societe(self.company)['imagerie'], {})
        resolu = imagerie_site(self.company)
        self.assertEqual(resolu, section_vide())
        self.assertIsNone(fournisseur_actif(resolu))

    def test_sans_societe_tout_est_inconnu(self):
        self.assertEqual(imagerie_site(None), section_vide())

    def test_enregistrement_rend_le_contrat(self):
        rendu = enregistrer_parametres(self.company, {'imagerie': REGLEE})
        self.assertEqual(rendu['imagerie'], REGLEE)
        self.assertEqual(sorted(rendu['imagerie']), sorted(CLES))

    def test_enregistrement_partiel_complete_les_huit_cles(self):
        rendu = enregistrer_parametres(self.company,
                                       {'imagerie': {'pays': 'ma'}})
        self.assertEqual(sorted(rendu['imagerie']), sorted(CLES))
        self.assertEqual(rendu['imagerie']['pays'], 'ma')
        self.assertIsNone(rendu['imagerie']['fournisseur_imagerie'])

    def test_refus_n_ecrit_rien(self):
        with self.assertRaises(ReglageInvalide):
            enregistrer_parametres(self.company,
                                   {'imagerie': {'altitude_m': 145}})
        self.assertEqual(parametres_de_societe(self.company)['imagerie'], {})

    def test_une_autre_section_ne_touche_pas_l_imagerie(self):
        enregistrer_parametres(self.company, {'imagerie': {'pays': 'ma'}})
        enregistrer_parametres(self.company,
                               {'degagements': {'retrait_rive_m': 0.5}})
        self.assertEqual(imagerie_site(self.company)['pays'], 'ma')

    def test_isolation_societe(self):
        enregistrer_parametres(self.company, {'imagerie': REGLEE})
        self.assertEqual(imagerie_site(self.autre), section_vide())
        self.assertEqual(parametres_de_societe(self.autre)['imagerie'], {})


class EndpointTest(TestCase):
    """``GET/PUT /api/django/calepinage/parametres/`` sert le contrat."""

    def setUp(self):
        self.company = Company.objects.create(nom='HTTP Imagerie',
                                              slug='http-imagerie-47')
        self.autre = Company.objects.create(nom='Voisine Imagerie',
                                            slug='voisine-imagerie-47')
        role = Role.objects.create(company=self.company, nom='Directeur',
                                   permissions=list(DIRECTEUR_PERMISSIONS))
        role_sans = Role.objects.create(
            company=self.company, nom='Technicien',
            permissions=list(TECHNICIEN_PERMISSIONS))
        self.user = User.objects.create_user(
            username='cal47', password='x', company=self.company, role=role)
        self.user_sans = User.objects.create_user(
            username='cal47_tech', password='x', company=self.company,
            role=role_sans)
        self.api = self._api(self.user)
        self.api_sans = self._api(self.user_sans)

    @staticmethod
    def _api(user):
        api = APIClient()
        api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(user)}')
        return api

    def test_get_sans_reglage_rend_une_section_vide(self):
        reponse = self.api.get(URL)
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.data['imagerie'], {})

    def test_put_puis_get_rendent_le_contrat(self):
        reponse = self.api.put(URL, {'imagerie': REGLEE}, format='json')
        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(reponse.data['imagerie'], REGLEE)
        relecture = self.api.get(URL)
        self.assertEqual(relecture.data['imagerie'], REGLEE)

    def test_put_invalide_nomme_le_champ(self):
        reponse = self.api.put(
            URL, {'imagerie': {'fournisseur_imagerie': 'google_solar'}},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertIn('fournisseur_imagerie', reponse.data)

    def test_sans_droit_d_ecriture_refuse(self):
        reponse = self.api_sans.put(URL, {'imagerie': {'pays': 'ma'}},
                                    format='json')
        self.assertEqual(reponse.status_code, 403)
        self.assertEqual(parametres_de_societe(self.company)['imagerie'], {})

    def test_la_societe_ne_vient_jamais_du_corps(self):
        """`company` n'est pas une SECTION : le refus le dit, et rien n'est
        écrit chez la voisine."""
        reponse = self.api.put(
            URL, {'imagerie': {'pays': 'ma'}, 'company': self.autre.pk},
            format='json')
        self.assertEqual(reponse.status_code, 400)
        self.assertEqual(parametres_de_societe(self.autre)['imagerie'], {})
