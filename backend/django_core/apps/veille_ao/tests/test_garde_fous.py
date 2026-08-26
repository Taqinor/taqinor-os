"""VAO19 — CHAQUE mitigation promise au fichier de risque a son test.

``tos_risk/marchespublics_gov_ma.md`` engage Taqinor sur neuf mitigations.
Une mitigation sans test est une intention : ce module les vérifie une par
une, et deux d'entre elles sont des GARDES DE GREP qui balaient tout le
paquet ``portail/`` —

  (a) **anti-maquillage** : aucune chaîne d'User-Agent de navigateur nulle
      part, sauf dans ``garde_fous.py`` qui les nomme pour les interdire ;
  (b) **anti-balayage** : une recherche sans mot-clé restrictif est refusée
      par construction, donc un balayage du portail ne peut pas être écrit
      par accident.

Rien ici n'ouvre de socket ni ne dort pour de vrai : l'horloge et le sommeil
sont injectés.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from django.test import SimpleTestCase

from apps.veille_ao.portail import client as portail_client
from apps.veille_ao.portail import detail as portail_detail
from apps.veille_ao.portail import fixtures
from apps.veille_ao.portail import garde_fous
from apps.veille_ao.tests.test_purete_portail import GardeReseau

PAQUET = Path(fixtures.DOSSIER).parent
JOUR = '2026-08-26'
URL_BASE = 'https://portail.test.invalid'

#: Les chaînes qu'un User-Agent de navigateur contient. Écrites dans le TEST,
#: comme dans ``garde_fous`` : les deux seuls endroits où elles ont le droit
#: d'exister, parce que les deux servent à les interdire.
JETONS_NAVIGATEUR = ('mozilla', 'applewebkit', 'chrome', 'safari', 'firefox',
                     'gecko', 'trident', 'khtml', 'opera')

#: On cherche des MOTS, pas des sous-chaînes : « InvalidOperation » contient
#: « opera » sans être un déguisement. Le motif est réécrit ici plutôt
#: qu'importé du module — une garde qui s'auto-valide ne garde rien.
MOTIF_NAVIGATEUR = re.compile(
    r'(?<![a-z])(?:' + '|'.join(JETONS_NAVIGATEUR) + r')(?![a-z])',
    re.IGNORECASE)


@dataclass
class SourceFictive:
    libelle: str = 'Portail de test'
    url_base: str = URL_BASE
    actif: bool = True
    company_id: int = 7
    id: int = 3


class Horloge:
    """Une horloge de test : elle n'avance que quand on le lui demande."""

    def __init__(self):
        self.instant = 1000.0

    def __call__(self):
        return self.instant

    def avancer(self, secondes):
        self.instant += secondes


class Dormeur:
    def __init__(self, horloge=None):
        self.attentes = []
        self.horloge = horloge

    def __call__(self, secondes):
        self.attentes.append(secondes)
        if self.horloge is not None:
            self.horloge.avancer(secondes)


def _garde(**kwargs):
    """Une garde ISOLÉE : compteurs privés, horloge et sommeil de test."""
    horloge = kwargs.pop('horloge', None) or Horloge()
    dormeur = kwargs.pop('dormir', None) or Dormeur(horloge)
    kwargs.setdefault('compteurs', {})
    kwargs.setdefault('jour', JOUR)
    kwargs.setdefault('environnement', {garde_fous.DRAPEAU: '1'})
    return garde_fous.GardeFous(horloge=horloge, dormir=dormeur, **kwargs), \
        horloge, dormeur


class InterrupteurTests(SimpleTestCase):
    """Mitigation 6 — l'interrupteur d'arrêt, DÉSARMÉ par défaut."""

    def test_le_defaut_est_desarme(self):
        self.assertFalse(garde_fous.collecte_armee({}))

    def test_un_zero_explicite_reste_desarme(self):
        self.assertFalse(garde_fous.collecte_armee({garde_fous.DRAPEAU: '0'}))
        self.assertFalse(garde_fous.collecte_armee({garde_fous.DRAPEAU: ''}))
        self.assertFalse(garde_fous.collecte_armee({garde_fous.DRAPEAU: 'non'}))

    def test_les_formes_d_armement_reconnues(self):
        for valeur in ('1', 'true', 'oui', 'YES', 'On', 'vrai'):
            with self.subTest(valeur=valeur):
                self.assertTrue(
                    garde_fous.collecte_armee({garde_fous.DRAPEAU: valeur}))

    def test_desarme_aucune_requete_ne_passe_la_garde(self):
        garde = garde_fous.GardeFous(cle='t', compteurs={}, jour=JOUR,
                                     environnement={})
        with self.assertRaises(garde_fous.CollecteDesarmee) as capture:
            garde.avant_requete('recherche')
        self.assertIn('VAO4', str(capture.exception))

    def test_le_drapeau_est_relu_a_chaque_appel(self):
        """Désarmer ne doit jamais exiger un redéploiement."""
        environnement = {garde_fous.DRAPEAU: '1'}
        garde = garde_fous.GardeFous(cle='t', compteurs={}, jour=JOUR,
                                     dormir=lambda s: None,
                                     environnement=environnement)
        garde.avant_requete('une')
        environnement[garde_fous.DRAPEAU] = '0'
        with self.assertRaises(garde_fous.CollecteDesarmee):
            garde.avant_requete('deux')

    def test_le_client_desarme_ne_touche_JAMAIS_le_reseau(self):
        """Le défaut de ``rechercher`` est la garde RÉELLE, pas une neutre."""
        appels = []

        def repondre(requete):
            appels.append(requete)
            return httpx.Response(200, text='')

        garde_fous.reinitialiser()
        with GardeReseau():
            with self.assertRaises(garde_fous.CollecteDesarmee):
                portail_client.rechercher(
                    SourceFictive(), 'solaire',
                    transport=httpx.MockTransport(repondre))
        self.assertEqual(appels, [])

    def test_le_declenchement_MANUEL_est_coupe_lui_aussi(self):
        """« Y compris le déclenchement manuel » : le détail est ce chemin-là."""
        appels = []

        def repondre(requete):
            appels.append(requete)
            return httpx.Response(200, text='')

        garde_fous.reinitialiser()
        detail = portail_detail.enrichir(
            SourceFictive(), '812340', 'k1z',
            transport=httpx.MockTransport(repondre), dormir=lambda s: None)
        self.assertEqual(appels, [])
        self.assertFalse(detail.disponible)
        self.assertEqual(detail.cause, 'CollecteDesarmee')


class QuotaTests(SimpleTestCase):
    """Mitigation 3 — moins de 10 requêtes par jour, plafond DUR."""

    def test_le_plafond_est_bien_dix(self):
        """10 est le chiffre du fichier de risque — pas 20."""
        self.assertEqual(garde_fous.QUOTA_QUOTIDIEN, 10)

    def test_les_dix_premieres_passent_la_onzieme_est_refusee(self):
        garde, _, _ = _garde(cle='societe:1')
        for numero in range(10):
            garde.avant_requete(f'requête {numero}')
        self.assertEqual(garde.consommees, 10)
        self.assertEqual(garde.restantes, 0)
        with self.assertRaises(garde_fous.QuotaDepasse) as capture:
            garde.avant_requete('la onzième')
        self.assertIn('10', str(capture.exception))

    def test_le_depassement_LEVE_au_lieu_de_continuer(self):
        """Continuer « juste un peu » invaliderait l'analyse de risque."""
        garde, _, _ = _garde(cle='societe:1', quota=2)
        garde.avant_requete('une')
        garde.avant_requete('deux')
        with self.assertRaises(garde_fous.QuotaDepasse):
            garde.avant_requete('trois')

    def test_le_compteur_est_PARTAGE_entre_deux_gardes_de_la_meme_cle(self):
        """Recréer un objet ne doit pas remettre le quota à zéro."""
        compteurs = {}
        premiere = garde_fous.GardeFous(
            cle='societe:1', quota=2, compteurs=compteurs, jour=JOUR,
            dormir=lambda s: None, environnement={garde_fous.DRAPEAU: '1'})
        premiere.avant_requete('une')
        seconde = garde_fous.GardeFous(
            cle='societe:1', quota=2, compteurs=compteurs, jour=JOUR,
            dormir=lambda s: None, environnement={garde_fous.DRAPEAU: '1'})
        seconde.avant_requete('deux')
        with self.assertRaises(garde_fous.QuotaDepasse):
            seconde.avant_requete('trois')

    def test_deux_societes_ont_deux_quotas(self):
        """Multi-tenant : la société A ne consomme pas le quota de la B."""
        compteurs = {}
        a = garde_fous.GardeFous(
            cle='societe:1', quota=1, compteurs=compteurs, jour=JOUR,
            dormir=lambda s: None, environnement={garde_fous.DRAPEAU: '1'})
        b = garde_fous.GardeFous(
            cle='societe:2', quota=1, compteurs=compteurs, jour=JOUR,
            dormir=lambda s: None, environnement={garde_fous.DRAPEAU: '1'})
        a.avant_requete('a')
        b.avant_requete('b')  # ne doit pas lever
        with self.assertRaises(garde_fous.QuotaDepasse):
            a.avant_requete('a2')

    def test_le_quota_repart_le_lendemain(self):
        compteurs = {}
        hier = garde_fous.GardeFous(
            cle='societe:1', quota=1, compteurs=compteurs, jour='2026-08-25',
            dormir=lambda s: None, environnement={garde_fous.DRAPEAU: '1'})
        hier.avant_requete('hier')
        aujourdhui = garde_fous.GardeFous(
            cle='societe:1', quota=1, compteurs=compteurs, jour='2026-08-26',
            dormir=lambda s: None, environnement={garde_fous.DRAPEAU: '1'})
        aujourdhui.avant_requete('aujourd\'hui')  # ne doit pas lever

    def test_le_quota_est_JOURNALISE(self):
        """Mitigation 8 : le respect du plafond doit être vérifiable APRÈS."""
        garde, _, _ = _garde(cle='societe:1')
        garde.avant_requete('recherche « solaire »')
        self.assertEqual(len(garde.journal), 1)
        self.assertEqual(garde.journal[0]['numero'], 1)
        self.assertIn('solaire', garde.journal[0]['description'])

    def test_la_cle_de_societe_isole_bien_les_societes(self):
        a = garde_fous.cle_de_societe(SourceFictive(company_id=1, id=9))
        b = garde_fous.cle_de_societe(SourceFictive(company_id=2, id=9))
        self.assertNotEqual(a, b)
        self.assertIn('1', a)


class CadenceTests(SimpleTestCase):
    """Mitigation 3 — au plus une requête toutes les 2 secondes."""

    def test_la_cadence_promise_est_de_deux_secondes(self):
        self.assertEqual(garde_fous.CADENCE_MINIMALE, 2.0)

    def test_la_premiere_requete_n_attend_pas(self):
        garde, _, dormeur = _garde(cle='c1')
        garde.avant_requete('une')
        self.assertEqual(dormeur.attentes, [])

    def test_deux_requetes_collees_font_attendre_deux_secondes(self):
        garde, _, dormeur = _garde(cle='c2')
        garde.avant_requete('une')
        garde.avant_requete('deux')
        self.assertEqual(dormeur.attentes, [2.0])

    def test_une_requete_deja_espacee_n_attend_pas(self):
        garde, horloge, dormeur = _garde(cle='c3')
        garde.avant_requete('une')
        horloge.avancer(5.0)
        garde.avant_requete('deux')
        self.assertEqual(dormeur.attentes, [])

    def test_le_quota_est_verifie_AVANT_l_attente(self):
        """Attendre deux secondes pour se voir refuser serait absurde."""
        garde, _, dormeur = _garde(cle='c4', quota=1)
        garde.avant_requete('une')
        with self.assertRaises(garde_fous.QuotaDepasse):
            garde.avant_requete('deux')
        self.assertEqual(dormeur.attentes, [])


class VerrouTests(SimpleTestCase):
    """Mitigation 3 — jamais deux collectes simultanées pour une société."""

    def setUp(self):
        garde_fous.reinitialiser()

    def tearDown(self):
        garde_fous.reinitialiser()

    def test_une_seconde_collecte_de_la_meme_societe_est_refusee(self):
        premiere = garde_fous.GardeFous(cle='societe:7', compteurs={},
                                        jour=JOUR)
        with premiere:
            seconde = garde_fous.GardeFous(cle='societe:7', compteurs={},
                                           jour=JOUR)
            with self.assertRaises(garde_fous.CollecteConcurrente):
                with seconde:
                    pass

    def test_deux_societes_differentes_collectent_en_parallele(self):
        with garde_fous.GardeFous(cle='societe:7', compteurs={}, jour=JOUR):
            with garde_fous.GardeFous(cle='societe:8', compteurs={}, jour=JOUR):
                pass

    def test_le_verrou_est_rendu_meme_apres_une_erreur(self):
        garde = garde_fous.GardeFous(cle='societe:7', compteurs={}, jour=JOUR)
        try:
            with garde:
                raise RuntimeError('panne au milieu de la collecte')
        except RuntimeError:
            pass
        with garde_fous.GardeFous(cle='societe:7', compteurs={}, jour=JOUR):
            pass  # le verrou a bien été rendu


class AntiMaquillageTests(SimpleTestCase):
    """Garde (a) — aucune identité de navigateur, NULLE PART dans le paquet."""

    def _sources_du_paquet(self):
        for chemin in sorted(PAQUET.rglob('*.py')):
            if chemin.name == 'garde_fous.py':
                continue  # le seul fichier qui les NOMME, pour les interdire
            yield chemin, chemin.read_text(encoding='utf-8')

    def test_aucun_jeton_de_navigateur_dans_le_paquet(self):
        fautifs = []
        for chemin, source in self._sources_du_paquet():
            for trouve in MOTIF_NAVIGATEUR.finditer(source):
                fautifs.append(f'{chemin.name} contient « {trouve.group(0)} »')
        self.assertEqual(fautifs, [], '\n'.join(fautifs))

    def test_le_user_agent_reellement_envoye_est_honnete(self):
        ua = portail_client.user_agent()
        self.assertIn('Taqinor', ua)
        self.assertIsNone(MOTIF_NAVIGATEUR.search(ua))

    def test_une_identite_de_navigateur_leve(self):
        with self.assertRaises(garde_fous.MaquillageRefuse):
            garde_fous.verifier_identite_honnete(
                'Mozilla/5.0 (X11; Linux) AppleWebKit/537.36 Chrome/120')

    def test_la_garde_de_grep_sait_rougir(self):
        """Testée à l'envers : sinon elle finit verte sans rien inspecter."""
        faux = 'ENTETES = {"User-Agent": "Mozilla/5.0 (Chrome)"}'
        self.assertTrue(MOTIF_NAVIGATEUR.search(faux))

    def test_la_garde_ne_confond_pas_un_mot_francais_avec_un_navigateur(self):
        """``InvalidOperation`` contient « opera » — et n'est pas un déguisement.

        Une garde qui crie au loup sur du code légitime est une garde qu'on
        finit par désactiver.
        """
        self.assertIsNone(MOTIF_NAVIGATEUR.search('except InvalidOperation:'))
        garde_fous.verifier_identite_honnete(
            'TaqinorBot/1.0 (+mailto:operations@exemple.test)')


class AucunAccesAuthentifieTests(SimpleTestCase):
    """Mitigation 4 — aucune page authentifiée, aucun compte, aucun secret.

    ``PHPSESSID`` n'est pas dans la liste des interdits, et c'est un choix
    argumenté : c'est le cookie que le serveur pose de lui-même sur une visite
    ANONYME et que httpx transporte sans qu'on le fabrique. Ce n'est pas une
    session UTILISATEUR — le dispositif n'ouvre aucun compte.
    """

    def _sources_du_paquet(self):
        for chemin in sorted(PAQUET.rglob('*.py')):
            if chemin.name == 'garde_fous.py':
                continue
            yield chemin, chemin.read_text(encoding='utf-8').lower()

    def test_aucune_marque_d_authentification_dans_le_paquet(self):
        fautifs = []
        for chemin, source in self._sources_du_paquet():
            for marque in garde_fous.MARQUES_D_AUTHENTIFICATION:
                if marque in source:
                    fautifs.append(f'{chemin.name} contient « {marque} »')
        self.assertEqual(fautifs, [], '\n'.join(fautifs))

    def test_aucun_identifiant_en_dur_dans_le_paquet(self):
        """Ni clé, ni jeton, ni mot de passe : la lecture est ANONYME."""
        suspects = re.compile(
            r'(api[_-]?key|secret|token\s*=|bearer\s)', re.IGNORECASE)
        for chemin, source in self._sources_du_paquet():
            with self.subTest(fichier=chemin.name):
                self.assertIsNone(suspects.search(source), chemin.name)

    def test_la_garde_sait_rougir(self):
        faux = 'entetes = {"authorization": "basic xxx"}'
        self.assertTrue(any(marque in faux
                            for marque in garde_fous.MARQUES_D_AUTHENTIFICATION))


class AntiBalayageTests(SimpleTestCase):
    """Garde (b) — un balayage du portail ne peut pas être ÉCRIT."""

    def test_une_recherche_sans_mot_cle_est_refusee(self):
        for mot in ('', '   ', None):
            with self.subTest(mot=mot):
                with self.assertRaises(garde_fous.RechercheNonRestreinte):
                    garde_fous.exiger_mot_cle_restrictif(mot)

    def test_un_joker_est_refuse(self):
        for mot in ('*', '%', 'sol%', '*aire*'):
            with self.subTest(mot=mot):
                with self.assertRaises(garde_fous.RechercheNonRestreinte):
                    garde_fous.exiger_mot_cle_restrictif(mot)

    def test_un_mot_trop_court_est_refuse(self):
        with self.assertRaises(garde_fous.RechercheNonRestreinte):
            garde_fous.exiger_mot_cle_restrictif('so')

    def test_les_mots_cles_mesures_passent(self):
        """Ceux du seed, mesurés sur le portail réel le 2026-08-01."""
        for mot in ('solaire', 'photovolta', 'pompage'):
            with self.subTest(mot=mot):
                self.assertEqual(garde_fous.exiger_mot_cle_restrictif(mot), mot)

    def test_le_client_refuse_AVANT_toute_connexion(self):
        appels = []

        def repondre(requete):
            appels.append(requete)
            return httpx.Response(200, text='')

        with self.assertRaises(garde_fous.RechercheNonRestreinte):
            portail_client.rechercher(
                SourceFictive(), '', garde=portail_client.GardeNeutre(),
                transport=httpx.MockTransport(repondre))
        self.assertEqual(appels, [])

    def test_le_plafond_de_pages_reste_celui_du_fichier_de_risque(self):
        """« 1 à 3 pages » — le code ne doit pas promettre plus large."""
        self.assertEqual(portail_client.PAGES_MAX, 3)


class DelaisPartoutTests(SimpleTestCase):
    """Mitigation 3 — « délais d'attente partout ».

    Un client sans délai d'attente sur un point de terminaison qui se bloque
    110 secondes, c'est un worker qui ne revient jamais.
    """

    def test_le_client_de_recherche_declare_ses_delais(self):
        source = Path(portail_client.__file__).read_text(encoding='utf-8')
        self.assertIn('httpx.Timeout(', source)
        self.assertIn('timeout=delai', source)
        self.assertGreater(portail_client.DELAI_LECTURE, 0)

    def test_le_client_de_detail_declare_ses_delais(self):
        source = Path(portail_detail.__file__).read_text(encoding='utf-8')
        self.assertIn('httpx.Timeout(', source)
        self.assertIn('timeout=delai', source)

    def test_le_delai_du_detail_est_dans_la_fourchette_demandee(self):
        """30-60 s : les blocages mesurés duraient 110 s."""
        self.assertGreaterEqual(portail_detail.DELAI_DETAIL, 30)
        self.assertLessEqual(portail_detail.DELAI_DETAIL, 60)


class CollecteArmeeTests(SimpleTestCase):
    """Armée, la garde laisse passer — et la séquence complète fonctionne."""

    def setUp(self):
        garde_fous.reinitialiser()

    def tearDown(self):
        garde_fous.reinitialiser()

    def test_armee_la_sequence_complete_passe_et_consomme_son_quota(self):
        horloge = Horloge()
        dormeur = Dormeur(horloge)
        garde = garde_fous.GardeFous(
            cle='societe:7', compteurs={}, jour=JOUR, horloge=horloge,
            dormir=dormeur, environnement={garde_fous.DRAPEAU: '1'})

        appels = []

        def repondre(requete):
            appels.append(requete)
            nom = (fixtures.RESULTATS_10 if requete.method == 'GET'
                   else fixtures.RESULTATS_500)
            return httpx.Response(200, text=fixtures.charger(nom))

        with GardeReseau():
            recherche = portail_client.rechercher(
                SourceFictive(), 'solaire', garde=garde,
                transport=httpx.MockTransport(repondre))

        self.assertEqual(recherche.total_annonce, 34)
        self.assertEqual(len(appels), 2)
        self.assertEqual(garde.consommees, 2)
        self.assertEqual(garde.restantes, 8)
        # La cadence a bien été respectée entre les deux requêtes.
        self.assertEqual(dormeur.attentes, [2.0])

    def test_le_verrou_est_pris_pendant_toute_la_sequence(self):
        garde = garde_fous.GardeFous(
            cle='societe:7', compteurs={}, jour=JOUR, dormir=lambda s: None,
            environnement={garde_fous.DRAPEAU: '1'})
        concurrente = garde_fous.GardeFous(cle='societe:7', compteurs={},
                                           jour=JOUR)

        def repondre(requete):
            # PENDANT la séquence : une seconde collecte doit être refusée.
            with self.assertRaises(garde_fous.CollecteConcurrente):
                with concurrente:
                    pass
            return httpx.Response(
                200, text=fixtures.charger(fixtures.RESULTATS_VIDE))

        portail_client.rechercher(SourceFictive(), 'solaire', garde=garde,
                                  transport=httpx.MockTransport(repondre))
        # Et rendu à la sortie.
        with concurrente:
            pass
