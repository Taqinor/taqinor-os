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

from django.db import connection
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
