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

#: Clés posées au contrat AVANT leur producteur (PACT10) : la tâche nommée les
#: sert et retire son entrée dans le même commit.
EN_ATTENTE_LISTE = {}


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
        attendues = (set(CONTRAT['exemple_client_seul']['results'][0])
                     - set(EN_ATTENTE_LISTE))
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

    def test_recherche_par_ville_du_client_et_du_lead(self):
        """Maquette « Liste » (« Client, ville ou lead ») : la VILLE du lead
        rattaché est cherchée (le client n'a pas de ville), bornées société."""
        from apps.crm.models import Lead

        Lead.objects.filter(pk=self.lead.pk).update(ville='Essaouira')
        Lead.objects.filter(pk=self.lead_2.pk).update(ville='Tétouan')
        Lead.objects.create(company=self.autre, nom='Voisin', ville='Tétouan')
        etranger = Calepinage.objects.create(
            company=self.autre, lead_id=999, titre='Ailleurs')

        self.assertEqual(self._ids('Essaouira'), {self.hangar.pk})
        self.assertEqual(self._ids('essaou'), {self.hangar.pk})
        self.assertEqual(self._ids('Tétouan'), {self.autre_ligne.pk})
        self.assertNotIn(etranger.pk, self._ids('Tétouan'))
        self.assertEqual(self._ids('Quelquepartintrouvable'), set())

    def test_recherche_ville_au_dela_des_cinquante_premiers_leads(self):
        """T4-X3-010 — « Rabat » doit trouver TOUS les calepinages de Rabat :
        ``_condition_recherche`` ne retenait que les 50 premiers leads (par nom)
        et perdait le reste en silence."""
        from apps.calepinage.selectors import appliquer_filtres_liste
        from apps.crm.models import Lead

        attendus = set()
        for i in range(55):
            lead = Lead.objects.create(company=self.company,
                                       nom='A lead %02d' % i, ville='Rabat')
            attendus.add(Calepinage.objects.create(
                company=self.company, lead_id=lead.pk).pk)
        dernier = Lead.objects.create(company=self.company, nom='Zorro',
                                      ville='Rabat')
        attendus.add(Calepinage.objects.create(
            company=self.company, lead_id=dernier.pk).pk)
        etranger = Lead.objects.create(company=self.autre, nom='Voisin',
                                       ville='Rabat')
        Calepinage.objects.create(company=self.autre, lead_id=etranger.pk)

        trouves = set(appliquer_filtres_liste(
            Calepinage.objects.filter(company=self.company), q='Rabat',
            company=self.company).values_list('pk', flat=True))

        self.assertEqual(trouves, attendus)

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


class TriParTitreAfficheTest(BaseApiCalepinage):
    """T4-X3-011 — « Tri : Titre » range le titre que la carte AFFICHE
    (``CalepinageList.helpers.js::identiteCarte`` : client, sinon lead, sinon
    titre, sinon « Calepinage #N »), sans tenir compte de la casse ni des accents."""

    def _creer(self, **champs):
        return Calepinage.objects.create(
            company=self.company, lead_id=champs.pop('lead_id', 9_999_999),
            **champs)

    def test_tri_titre_suit_le_nom_affiche_sans_casse_ni_accents(self):
        zebre = self._creer(titre='zèbre')
        eric = self._creer(titre='Éric')
        abel = self._creer(titre='abel')
        repli = self._creer(titre='')
        # La carte montre le CLIENT avant le titre saisi.
        atlas = self._creer(titre='zzz dernier', client=self.client_a)

        reponse = self.api.get(URL, {'ordering': 'titre'})
        self.assertEqual(reponse.status_code, 200, reponse.data)
        ids = [ligne['id'] for ligne in self._lignes(reponse)]
        self.assertEqual(
            ids, [abel.pk, atlas.pk, repli.pk, eric.pk, zebre.pk])

        reponse = self.api.get(URL, {'ordering': '-titre'})
        ids = [ligne['id'] for ligne in self._lignes(reponse)]
        self.assertEqual(
            ids, [zebre.pk, eric.pk, repli.pk, atlas.pk, abel.pk])


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


class ContratDeLaCarteTest(SimpleTestCase):
    """ACAL1308 — les chiffres de la carte au contrat, avec leurs règles d'absence."""

    def _lignes(self):
        return {cle: CONTRAT[cle]['results'][0]
                for cle in ('exemple', 'exemple_client_seul', 'exemple_sans_image')}

    def test_chaque_ligne_porte_les_cles_de_la_carte(self):
        for cle, ligne in self._lignes().items():
            for nom in ('kwc', 'production_kwh_an', 'points_a_regler',
                        'points_a_regler_lu_le', 'points_a_regler_perime',
                        'client_apercu', 'lead'):
                self.assertIn(nom, ligne, cle)
        self.assertEqual(sorted(CONTRAT['exemple']['compteurs_statut']),
                         ['brouillon', 'perime', 'refuse', 'tous', 'valide'])

    def test_points_a_regler_entier_ou_nul_jamais_zero_invente(self):
        lignes = self._lignes()
        rangee = lignes['exemple']
        self.assertIsInstance(rangee['points_a_regler'], int)
        self.assertNotIsInstance(rangee['points_a_regler'], bool)
        self.assertRegex(rangee['points_a_regler_lu_le'], r'^\d{4}-\d{2}-\d{2}T')
        self.assertIs(rangee['points_a_regler_perime'], False)
        # Jamais lu : les trois clés nulles.
        jamais = lignes['exemple_client_seul']
        self.assertEqual([jamais['points_a_regler'], jamais['points_a_regler_lu_le'],
                          jamais['points_a_regler_perime']], [None, None, None])
        # Document changé depuis la lecture : plus de nombre, la date reste, « à relire ».
        perime = lignes['exemple_sans_image']
        self.assertIsNone(perime['points_a_regler'])
        self.assertIsNotNone(perime['points_a_regler_lu_le'])
        self.assertIs(perime['points_a_regler_perime'], True)
        self.assertIn('points_a_regler', CONTRAT['pourquoi'])

    def test_apercu_toit_trace_normalise_ou_nul(self):
        """ACAL1334 — un tracé de contours de 0 à 100, ou ``null`` : ni image ni URL."""
        lignes = self._lignes()
        self.assertIsNone(lignes['exemple_sans_image']['apercu_toit'])
        for cle in ('exemple', 'exemple_client_seul'):
            apercu = lignes[cle]['apercu_toit']
            self.assertEqual(sorted(apercu), ['contours', 'viewBox'], cle)
            self.assertEqual(apercu['viewBox'], '0 0 100 100')
            self.assertTrue(apercu['contours'])
            for contour in apercu['contours']:
                self.assertGreaterEqual(len(contour), 3)
                for x, y in contour:
                    self.assertTrue(0 <= x <= 100 and 0 <= y <= 100, (cle, x, y))
            self.assertNotIn('http', json.dumps(apercu))
        self.assertIn('apercu_toit', CONTRAT['pourquoi'])

    def test_apercu_du_toit_pur(self):
        """ACAL1335 — le tracé lu sur ``outline`` à défaut de pans ; rien ⇒ None."""
        from apps.calepinage.services.lecture_liste import _apercu_du_toit

        self.assertIsNone(_apercu_du_toit(None))
        self.assertIsNone(_apercu_du_toit({'zones': []}))
        contour = _apercu_du_toit({'outline': [[33.0, -7.0], [33.0, -6.999], [33.001, -6.999]]})
        self.assertEqual(len(contour['contours']), 1)
        self.assertTrue(all(0 <= v <= 100 for p in contour['contours'][0] for v in p))

    def test_kwc_et_production_nombres_ou_nuls(self):
        for cle, ligne in self._lignes().items():
            self.assertTrue(ligne['kwc'] is None or isinstance(ligne['kwc'], float), cle)
            self.assertTrue(ligne['production_kwh_an'] is None
                            or isinstance(ligne['production_kwh_an'], int), cle)


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


#: Un champ au sol de 12 modules de 580 Wc (6,96 kWc) : la puissance du document.
SOL_12 = {'version': 2, 'pin': {'lat': 33.57, 'lng': -7.59}, 'zones': [],
          'poseSurfaces': [{'id': 'champ-1', 'kind': 'sol', 'label': 'Champ sud',
                            'moduleWc': 580, 'tiltDeg': 20, 'rowAzimuthDeg': 90,
                            'engine': {'modules': 12}}]}


class ValeursRangeesDeLaListeTest(BaseApiCalepinage):
    """ACAL1309 — six lignes : les valeurs RANGÉES sont lues, ``null`` sinon,
    les effectifs somment à six et le compte de requêtes ne suit pas les lignes."""

    def _creer(self, rang, simule):
        resultat = ({'production': {'total': {'p50_kwh': 9000.4 + rang}},
                     'pose': {'total_modules': 12, 'kwc': 6.96}} if simule else None)
        return Calepinage.objects.create(
            company=self.company, client=self.client_a, lead_id=self.lead.pk,
            titre=f'Toiture {rang}', roof_layout=SOL_12, resultat=resultat,
            approbation=({'etat': 'refuse'} if rang == 5 else None))

    def test_six_lignes_lues_sans_rien_recalculer(self):
        simules = {self._creer(rang, True).pk: 9000 + rang for rang in range(3)}
        nus = {self._creer(rang, False).pk for rang in range(3, 6)}

        reponse = self.api.get(URL, {'page_size': 50})

        self.assertEqual(reponse.status_code, 200, reponse.data)
        lignes = {ligne['id']: ligne for ligne in self._lignes(reponse)}
        for pk, p50 in simules.items():
            self.assertEqual(lignes[pk]['production_kwh_an'], p50)
            self.assertEqual(lignes[pk]['kwc'], 6.96)
        for pk in nus:
            self.assertIsNone(lignes[pk]['production_kwh_an'])
            self.assertEqual(lignes[pk]['kwc'], 6.96)  # puissance du document seul
        compteurs = reponse.data['compteurs_statut']
        self.assertEqual(compteurs['tous'], 6)
        self.assertEqual(sum(compteurs[s] for s in ('brouillon', 'valide', 'perime', 'refuse')), 6)
        self.assertEqual(compteurs['refuse'], 1)

    def test_le_compte_de_requetes_ne_suit_pas_les_lignes(self):
        def mesurer(nombre):
            Calepinage.objects.filter(company=self.company).delete()
            for rang in range(nombre):
                self._creer(rang, rang % 2 == 0)
            self.api.get(URL)  # chauffe les caches de processus
            with CaptureQueriesContext(connection) as requetes:
                reponse = self.api.get(URL, {'page_size': 50})
            self.assertEqual(reponse.status_code, 200)
            return len(requetes)

        self.assertEqual(mesurer(6), mesurer(18))

    def test_points_a_regler_lus_sur_le_verdict_range(self):
        """ACAL1333 — rangé ⇒ servi ; jamais lu ⇒ null (jamais 0) ; document
        modifié depuis ⇒ null, date gardée, « à relire » ; aucun contrôle lancé."""
        from unittest import mock

        lu = self._creer(0, True)
        Calepinage.objects.filter(pk=lu.pk).update(layout_hash='h1', dernier_verdict={
            'a_regler': 2, 'bloquants': 1, 'empreinte': 'h1', 'lu_le': '2026-11-22T10:00:00+00:00'})
        jamais = self._creer(1, True)
        change = self._creer(2, True)
        Calepinage.objects.filter(pk=change.pk).update(layout_hash='h2', dernier_verdict={
            'a_regler': 4, 'bloquants': 0, 'empreinte': 'h1', 'lu_le': '2026-11-21T10:00:00+00:00'})

        with mock.patch('apps.calepinage.services.pret_a_envoyer.agreger') as controle:
            reponse = self.api.get(URL)
        controle.assert_not_called()

        lignes = {ligne['id']: ligne for ligne in self._lignes(reponse)}
        self.assertEqual(
            [lignes[lu.pk][c] for c in ('points_a_regler', 'points_a_regler_lu_le', 'points_a_regler_perime')],
            [3, '2026-11-22T10:00:00+00:00', False])
        self.assertEqual(
            [lignes[jamais.pk][c] for c in ('points_a_regler', 'points_a_regler_lu_le', 'points_a_regler_perime')],
            [None, None, None])
        self.assertEqual(
            [lignes[change.pk][c] for c in ('points_a_regler', 'points_a_regler_lu_le', 'points_a_regler_perime')],
            [None, '2026-11-21T10:00:00+00:00', True])

    def test_lignes_avec_devis_et_leads_requetes_constantes(self):
        """ACAL1343 — le cas réel de la pile : chaque calepinage a SON lead et SON
        devis, dont les lignes portent un produit. 4 lignes ou 12 : même compte."""
        from decimal import Decimal

        from apps.crm.models import Lead
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis

        panneau = Produit.objects.create(
            company=self.company, nom='Panneau 580 Wc', sku='ACAL1343-P',
            prix_achat=Decimal('9876543.21'), prix_vente=Decimal('1500'), quantite_stock=1)

        def mesurer(nombre):
            Calepinage.objects.filter(company=self.company).delete()
            for rang in range(nombre):
                lead = Lead.objects.create(company=self.company, nom=f'Lead 1343-{nombre}-{rang}',
                                           ville='Rabat', owner=self.user)
                devis = Devis.objects.create(
                    company=self.company, client=self.client_a, lead=lead, roof_layout=SOL_12,
                    reference=f'DEV-202611-{nombre:02d}{rang:02d}', layout_hash='d' * 64)
                for _ in range(2):
                    LigneDevis.objects.create(devis=devis, produit=panneau, designation='Panneau 580 Wc',
                                              quantite=Decimal(6), prix_unitaire=Decimal('1000'))
                Calepinage.objects.create(
                    company=self.company, lead_id=lead.pk, devis=devis, titre=f'Toiture {rang}',
                    roof_layout=SOL_12, layout_hash='d' * 64,
                    resultat={'production': {'total': {'p50_kwh': 9000}},
                              'pose': {'total_modules': 12, 'kwc': 6.96}})
            self.api.get(URL)  # chauffe les caches de processus
            with CaptureQueriesContext(connection) as requetes:
                reponse = self.api.get(URL, {'page_size': 300})
            self.assertEqual(reponse.status_code, 200)
            self.assertEqual(len(self._lignes(reponse)), nombre)
            self.assertNotIn('9876543', json.dumps(reponse.data, default=str))  # prix_achat jamais servi
            return len(requetes)

        self.assertEqual(mesurer(4), mesurer(12))

    def test_apercu_toit_contours_normalises_ou_nul_sans_requete_de_plus(self):
        """ACAL1335 — un contour par pan, de 0 à 100 ; sans contour ⇒ null ; le compte
        de requêtes ne bouge pas (le document est déjà chargé)."""
        deux_pans = {'version': 2, 'zones': [
            {'id': 'a', 'vertices': [[-7.5900, 33.5730], [-7.5898, 33.5730],
                                     [-7.5898, 33.5732], [-7.5900, 33.5732]]},
            {'id': 'b', 'vertices': [[-7.5897, 33.5730], [-7.5896, 33.5730], [-7.5896, 33.5731]]},
            {'id': 'c', 'vertices': [[-7.59, 33.57]]}]}  # illisible : ignoré
        avec = Calepinage.objects.create(company=self.company, client=self.client_a,
                                         titre='Deux pans', roof_layout=deux_pans)
        sans = self._creer(0, False)  # champ au sol sans contour de pan

        with CaptureQueriesContext(connection) as un_trace:
            lignes = {ligne['id']: ligne for ligne in self._lignes(self.api.get(URL))}

        apercu = lignes[avec.pk]['apercu_toit']
        self.assertEqual(apercu['viewBox'], '0 0 100 100')
        self.assertEqual([len(c) for c in apercu['contours']], [4, 3])
        points = [p for c in apercu['contours'] for p in c]
        self.assertTrue(all(0 <= x <= 100 and 0 <= y <= 100 for x, y in points), points)
        # Le cadre commun est rempli (jamais des degrés ni des mètres bruts).
        self.assertGreater(max(x for x, _ in points) - min(x for x, _ in points), 80)
        self.assertIsNone(lignes[sans.pk]['apercu_toit'])
        Calepinage.objects.filter(pk=avec.pk).update(roof_layout=SOL_12)
        with CaptureQueriesContext(connection) as sans_trace:
            self.api.get(URL)
        self.assertEqual(len(un_trace), len(sans_trace))
