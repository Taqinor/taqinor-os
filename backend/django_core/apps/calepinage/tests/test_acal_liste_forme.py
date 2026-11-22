"""ACAL196 — la LISTE des calepinages publie la forme du contrat.

Ce qui est prouvé ici (HTTP réels, jamais une doublure) :

* une ligne « client seul » porte ``reference`` (égale à celle du détail),
  ``image`` (chemin RELATIF du proxy Django, aucune signature par ligne),
  ``modifie_le`` (ISO) et ``client_apercu {id, nom, ville}`` — toutes les clés
  du contrat ``calepinage_liste.json`` ;
* ``?q=`` trouve la ligne par le TITRE, par la RÉFÉRENCE affichée
  (CAL-AAMM-NNNN), par le NOM DU LEAD rattaché et par le NOM DU CLIENT ;
* les statuts publiés par le contrat sont ceux du modèle ;
* le budget de requêtes de la liste ne grandit pas avec le nombre de lignes.

Run :
    python manage.py test apps.calepinage.tests.test_acal_liste_forme -v2
"""
import json
import pathlib
from types import SimpleNamespace

from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext

from apps.calepinage.models import Calepinage
from apps.calepinage.services.presentation import reference_calepinage

from .test_api_liste import URL, BaseApiCalepinage, url_detail

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')
CONTRAT = json.loads(
    (ECHANTILLONS / 'calepinage_liste.json').read_text(encoding='utf-8'))


class FormeDeLaListeTest(BaseApiCalepinage):
    def _ligne(self, calepinage, **params):
        reponse = self.api.get(URL, params)
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return next(ligne for ligne in self._lignes(reponse)
                    if ligne['id'] == calepinage.pk)

    def test_ligne_client_seul_porte_reference_image_modifie_le_client_apercu(
            self):
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            titre='Toiture hangar', roof_image='calepinage/roof/hangar.png')

        ligne = self._ligne(calepinage)
        detail = self.api.get(url_detail(calepinage.pk))

        # Toutes les clés du contrat sont servies (le sérialiseur en publie
        # d'autres, jamais moins).
        attendues = set(CONTRAT['exemple_client_seul']['results'][0])
        self.assertEqual(sorted(attendues - set(ligne)), [])
        self.assertEqual(ligne['reference'], detail.data['reference'])
        self.assertEqual(ligne['reference'], reference_calepinage(calepinage))
        self.assertRegex(ligne['reference'], r'^CAL-\d{4}-\d{4}$')
        # Chemin RELATIF du proxy Django : jamais une URL MinIO signée.
        self.assertEqual(
            ligne['image']['url'],
            f'/api/django/calepinage/calepinages/{calepinage.pk}'
            '/roof-image/fichier/')
        self.assertNotIn('X-Amz', json.dumps(ligne['image']))
        self.assertEqual(
            sorted(ligne['image']), ['expire_le', 'genere_le', 'url'])
        self.assertTrue(ligne['modifie_le'])
        self.assertEqual(ligne['client'], self.client_a.pk)
        self.assertEqual(ligne['client_apercu']['id'], self.client_a.pk)
        self.assertEqual(ligne['client_apercu']['nom'], 'Bâtiment Atlas')
        self.assertEqual(sorted(ligne['client_apercu']),
                         ['id', 'nom', 'ville'])

    def test_sans_rendu_ni_client_trois_null_et_client_apercu_nul(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Sans rendu')

        ligne = self._ligne(calepinage)

        self.assertEqual(ligne['image'], {'url': None, 'genere_le': None,
                                          'expire_le': None})
        self.assertIsNone(ligne['client_apercu'])

    def test_client_apercu_est_en_lecture_seule(self):
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Usine')

        reponse = self.api.patch(
            url_detail(calepinage.pk),
            {'client_apercu': {'id': 1, 'nom': 'x', 'ville': None}},
            format='json')

        self.assertEqual(reponse.status_code, 400)
        self.assertIn('client_apercu', reponse.data)


class RechercheDeLaListeTest(BaseApiCalepinage):
    def setUp(self):
        super().setUp()
        self.hangar = Calepinage.objects.create(
            company=self.company, client=self.client_a,
            lead_id=self.lead.pk, titre='Toiture hangar')
        self.autre_ligne = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk, titre='Villa')

    def _ids(self, q):
        reponse = self.api.get(URL, {'q': q})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        return {ligne['id'] for ligne in self._lignes(reponse)}

    def test_recherche_par_reference_par_nom_de_lead_et_de_client(self):
        # Le TITRE.
        self.assertEqual(self._ids('hangar'), {self.hangar.pk})
        # La RÉFÉRENCE affichée, telle que la liste la montre.
        self.assertEqual(self._ids(reference_calepinage(self.hangar)),
                         {self.hangar.pk})
        # Le NOM DU LEAD rattaché (« Toiture Anfa »).
        self.assertEqual(self._ids('Anfa'), {self.hangar.pk})
        # Le NOM DU CLIENT rattaché (« Bâtiment Atlas »).
        self.assertEqual(self._ids('Atlas'), {self.hangar.pk})

    def test_titre_de_repli_calepinage_diese_numero_est_trouve(self):
        """ACAL948 — « Calepinage #12 » et « #12 » trouvent le 12 sans titre,
        pas le 120 ; l'égalité porte sur le numéro."""
        sans_titre = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk)
        autre = Calepinage.objects.create(
            company=self.company, lead_id=self.lead_2.pk)
        for terme in (f'Calepinage #{sans_titre.pk}', f'#{sans_titre.pk}',
                      f'calepinage # {sans_titre.pk}'):
            with self.subTest(terme=terme):
                trouves = self._ids(terme)
                self.assertIn(sans_titre.pk, trouves)
                self.assertNotIn(autre.pk, trouves)
        # un numéro qui n'est qu'une sous-chaîne ne remonte pas
        self.assertNotIn(sans_titre.pk, self._ids(f'#{sans_titre.pk}0'))

    def test_recherche_ne_sort_pas_de_la_societe(self):
        etranger = Calepinage.objects.create(
            company=self.autre, lead_id=999, titre='Toiture hangar voisine')

        self.assertNotIn(etranger.pk, self._ids('hangar'))
        self.assertNotIn(etranger.pk,
                         self._ids(reference_calepinage(etranger)))

    def test_une_reference_inconnue_ne_rend_rien(self):
        self.assertEqual(self._ids('CAL-2601-9999'), set())


class StatutsEtBudgetTest(BaseApiCalepinage):
    def test_statuts_publies_egalent_choices(self):
        publies = [(ligne['valeur'], ligne['libelle'])
                   for ligne in CONTRAT['statuts_publies']]
        self.assertEqual(publies, [(valeur, str(libelle))
                                   for valeur, libelle
                                   in Calepinage.Statut.choices])

    def test_budget_requetes_de_la_liste(self):
        def mesurer(nombre):
            Calepinage.objects.filter(company=self.company).delete()
            for rang in range(nombre):
                Calepinage.objects.create(
                    company=self.company, client=self.client_a,
                    titre=f'Toiture {rang}', roof_image=f'r/{rang}.png')
            self.api.get(URL)  # chauffe les caches de processus
            with CaptureQueriesContext(connection) as requetes:
                reponse = self.api.get(URL)
            self.assertEqual(reponse.status_code, 200)
            return len(requetes)

        # Pas de requête PAR ligne : le compte ne bouge pas de 5 à 15 lignes.
        self.assertEqual(mesurer(5), mesurer(15))


class LectureDeLaCarteSansBaseTest(SimpleTestCase):
    """kWc et production de la carte : lus sur ce qui est enregistré, jamais inventés."""

    def test_kwc_du_document_arrondi_au_centieme_ou_none(self):
        from apps.calepinage.services.lecture_liste import kwc_pose

        self.assertEqual(kwc_pose(SimpleNamespace(_liste_mesures={'kwc': 6.9555})), 6.96)
        self.assertIsNone(kwc_pose(SimpleNamespace(_liste_mesures={'kwc': None})))
        self.assertIsNone(kwc_pose(SimpleNamespace(_liste_mesures={})))

    def test_production_enregistree_servie_en_entier(self):
        from apps.calepinage.services.lecture_liste import production_annuelle

        ligne = SimpleNamespace(_liste_p50_texte='11480.4', _liste_modules_simules_texte='12',
                                _liste_mesures={'modules': 12})
        self.assertEqual(production_annuelle(ligne), 11480)

    def test_pas_de_production_sans_simulation_ligne_non_annotee_ou_toit_change(self):
        from apps.calepinage.services.lecture_liste import production_annuelle

        self.assertIsNone(production_annuelle(SimpleNamespace(_liste_mesures={})))  # non annotée
        self.assertIsNone(production_annuelle(SimpleNamespace(
            _liste_p50_texte=None, _liste_modules_simules_texte=None, _liste_mesures={})))
        # La simulation décrivait 12 modules, le document en pose 16 : jamais un chiffre périmé.
        self.assertIsNone(production_annuelle(SimpleNamespace(
            _liste_p50_texte='11480', _liste_modules_simules_texte='12',
            _liste_mesures={'modules': 16})))

    def test_le_kwc_simule_complete_un_document_sans_puissance_de_module(self):
        """F4 — la carte lit aussi le bloc ``pose`` du résultat enregistré (annoté en SQL) : il est
        transmis à ``mesures_du_document``, qui ne l'emploie que s'il décrit CE document."""
        from unittest import mock

        from apps.calepinage.services.lecture_liste import kwc_pose

        ligne = SimpleNamespace(roof_layout={'result': {}}, _liste_modules_simules_texte='12',
                                _liste_kwc_simule_texte='6.96')
        with mock.patch('apps.calepinage.services.mesures.mesures_du_document',
                        return_value={'modules': 12, 'kwc': 6.96}) as lecture:
            self.assertEqual(kwc_pose(ligne), 6.96)
        self.assertEqual(lecture.call_args.args[1], {'pose': {'total_modules': 12.0, 'kwc': 6.96}})
        # Pas de simulation (ou pose incomplète) : le document seul, jamais un nombre inventé.
        sans = SimpleNamespace(roof_layout={'result': {}}, _liste_modules_simules_texte=None,
                               _liste_kwc_simule_texte=None)
        with mock.patch('apps.calepinage.services.mesures.mesures_du_document',
                        return_value={'modules': None, 'kwc': None}) as lecture:
            self.assertIsNone(kwc_pose(sans))
        self.assertIsNone(lecture.call_args.args[1])


class CompteursEtCarteDeLaListeTest(BaseApiCalepinage):
    """D07-L6 — « compteurs_statut » et les deux chiffres de la carte (test à base : non lancé)."""

    def test_les_compteurs_ignorent_le_filtre_de_statut_et_comptent_la_societe(self):
        for rang in range(2):
            Calepinage.objects.create(company=self.company, client=self.client_a, titre=f'B{rang}')
        Calepinage.objects.create(company=self.company, client=self.client_a, titre='R',
                                  approbation={'etat': 'refuse'})
        Calepinage.objects.create(company=self.autre, lead_id=999, titre='Voisin')

        reponse = self.api.get(URL, {'statut': 'brouillon'})

        self.assertEqual(reponse.status_code, 200, reponse.data)
        self.assertEqual(len(self._lignes(reponse)), 2)
        self.assertEqual(reponse.data['compteurs_statut'],
                         {'tous': 3, 'brouillon': 2, 'valide': 0, 'perime': 0, 'refuse': 1})

    def test_la_ligne_porte_kwc_et_production_nuls_sans_simulation(self):
        calepinage = Calepinage.objects.create(company=self.company, client=self.client_a, titre='Nu')

        ligne = next(ligne for ligne in self._lignes(self.api.get(URL)) if ligne['id'] == calepinage.pk)

        self.assertIsNone(ligne['kwc'])
        self.assertIsNone(ligne['production_kwh_an'])

    def test_la_production_enregistree_est_lue_sans_charger_le_resultat(self):
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Simule',
            resultat={'production': {'total': {'p50_kwh': 11480.4}}})

        ligne = next(ligne for ligne in self._lignes(self.api.get(URL)) if ligne['id'] == calepinage.pk)

        self.assertEqual(ligne['production_kwh_an'], 11480)
