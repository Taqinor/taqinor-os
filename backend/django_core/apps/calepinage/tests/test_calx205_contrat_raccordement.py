"""CALX205 — le contrat du RACCORDEMENT RÉSEAU.

CE QUE CE FICHIER GARDE
-----------------------
Rien du raccordement n'existe encore : `phases` ne sert qu'à choisir un
barème de câble et un coefficient de protection, et aucune élévation de
tension, aucune puissance souscrite, aucun équilibrage n'est calculé nulle
part. Le producteur arrive avec `services/raccordement.py` (CALX241-243) et
la vue avec CALX244. Ce qui peut — et doit — être affirmé aujourd'hui tient
en quatre promesses :

1. **Les trois blocs et les cinq verdicts sont TOUJOURS là**, dans chaque
   état. Un écran qui reçoit parfois cinq verdicts et parfois deux finit par
   tester l'absence de clé au lieu de l'absence de données (PACT10).
2. **Une limite est une SAISIE qui porte sa source.** Sans elle,
   `elevation_pct` est publiée quand même et le verdict vaut `omis` avec son
   motif — jamais un barème supposé pour le Maroc (D1).
3. **`marge_pct` est une différence, pas un confort** : `null` tant
   qu'aucune limite n'est saisie. `0` se lirait « limite atteinte ».
4. **`cos_phi_impose` et `source_cos_phi` vont ensemble** — c'est le couple
   que l'étape d'écrêtage (CALX172) lira pour borner la puissance ; un cos φ
   sans source est refusé en nommant le champ.

Aucun seuil n'est écrit dans ce module de test : les seules valeurs
comparées sont celles de l'échantillon, et la règle vérifiée est un LIEN
entre champs (limite ⇔ source, limite ⇔ marge), jamais un nombre.

Aucune base de données, aucun réseau : un fichier JSON et le registre des
réglages.

Run :
    python manage.py test apps.calepinage.tests.test_calx205_contrat_raccordement
"""
from __future__ import annotations

import json
import pathlib

from django.test import SimpleTestCase

from apps.calepinage.services.parametres_cles import CLES_ELECTRIQUE_SOCIETE

ECHANTILLONS = (pathlib.Path(__file__).resolve().parents[1]
                / 'contract_samples')


def charger(nom):
    return json.loads((ECHANTILLONS / nom).read_text(encoding='utf-8'))


RACCORDEMENT = charger('calepinage_raccordement.json')

ETATS = ('exemple', 'exemple_limite_saisie', 'exemple_vide')

#: Les sept champs de la saisie — `source_limite` et `source_cos_phi` sont
#: des champs À PART ENTIÈRE, pas des annotations facultatives.
CHAMPS_SAISIE = {'puissance_souscrite_kva', 'phases', 'tension_nominale_v',
                 'limite_elevation_pct', 'source_limite', 'cos_phi_impose',
                 'source_cos_phi'}

#: Les quatre grandeurs calculées.
CHAMPS_CALCUL = {'elevation_pct', 'marge_pct', 'puissance_injectee_kva',
                 'desequilibre_pct'}

#: Les cinq champs d'un verdict, et les quatre statuts admis.
CHAMPS_VERDICT = {'code', 'libelle', 'statut', 'detail', 'source'}
STATUTS = ('ok', 'alerte', 'bloquant', 'omis')

#: Les cinq contrôles, dans l'ordre où l'écran les affiche.
CODES = ['elevation_tension', 'puissance_souscrite', 'regime_phases',
         'tension_nominale', 'desequilibre_phases']

#: Les couples « valeur ⇔ sa provenance » : l'une sans l'autre est refusée.
COUPLES_SOURCES = (('limite_elevation_pct', 'source_limite'),
                   ('cos_phi_impose', 'source_cos_phi'))

#: « marge » N'Y FIGURE PAS volontairement : `marge_pct` est ici la marge à
#: la limite d'élévation, en points de pourcentage — pas une marge
#: commerciale.
HORS_SUJET = ('prix', 'montant', 'mad', 'tva', 'kwh', 'remise')


def verdicts(etat):
    return {verdict['code']: verdict for verdict in RACCORDEMENT[etat]
            ['verdicts']}


class EnveloppeTest(SimpleTestCase):
    """L'échantillon porte l'enveloppe PACT10 et vise la bonne route."""

    def test_enveloppe_complete(self):
        for cle in ('endpoint', 'pourquoi', 'exemple'):
            self.assertIn(
                cle, RACCORDEMENT,
                f'calepinage_raccordement.json : clé « {cle} » absente.')

    def test_l_endpoint_est_lisible_par_la_garde(self):
        verbe, _, route = RACCORDEMENT['endpoint'].partition(' ')
        self.assertEqual(verbe, 'GET')
        self.assertEqual(
            route,
            '/api/django/calepinage/calepinages/<int:pk>/raccordement/',
            'Une seule forme d’URL dans ce module : sous-ressource en '
            '@action sous calepinages/<pk>/.')

    def test_le_post_est_decrit(self):
        self.assertIn('POST', RACCORDEMENT['pourquoi'])


class TroisBlocsTest(SimpleTestCase):
    """Aucune clé ne disparaît, dans aucun état."""

    def test_les_trois_blocs_dans_chaque_etat(self):
        for etat in ETATS:
            self.assertEqual(sorted(RACCORDEMENT[etat]),
                             ['calcul', 'saisie', 'verdicts'],
                             f'{etat} : les blocs de réponse ont bougé.')

    def test_les_sept_champs_de_saisie(self):
        for etat in ETATS:
            self.assertEqual(
                set(RACCORDEMENT[etat]['saisie']), CHAMPS_SAISIE,
                f'{etat} : champs de saisie '
                f"{sorted(set(RACCORDEMENT[etat]['saisie']) ^ CHAMPS_SAISIE)}"
                f' en écart.')

    def test_les_quatre_grandeurs_calculees(self):
        for etat in ETATS:
            self.assertEqual(set(RACCORDEMENT[etat]['calcul']), CHAMPS_CALCUL,
                             f'{etat} : grandeurs calculées en écart.')

    def test_les_cinq_verdicts_dans_chaque_etat(self):
        for etat in ETATS:
            self.assertEqual(
                [verdict['code']
                 for verdict in RACCORDEMENT[etat]['verdicts']], CODES,
                f'{etat} : les cinq contrôles doivent TOUS être présents, '
                f'dans le même ordre — un contrôle absent se lit « pas de '
                f'problème ».')

    def test_forme_et_statut_de_chaque_verdict(self):
        for etat in ETATS:
            for verdict in RACCORDEMENT[etat]['verdicts']:
                self.assertEqual(set(verdict), CHAMPS_VERDICT,
                                 f"{etat} / {verdict.get('code')} : champs en "
                                 f"écart.")
                self.assertIn(verdict['statut'], STATUTS)
                self.assertTrue(verdict['libelle'].strip())
                self.assertTrue(verdict['detail'].strip())


class AucuneValeurSansProvenanceTest(SimpleTestCase):
    """D-CALX 7 : saisi AVEC sa provenance, sourcé, ou OMIS en le disant."""

    def test_une_valeur_saisie_porte_toujours_sa_source(self):
        for etat in ETATS:
            saisie = RACCORDEMENT[etat]['saisie']
            for valeur, source in COUPLES_SOURCES:
                if saisie[valeur] is not None:
                    self.assertTrue(
                        (saisie[source] or '').strip(),
                        f'{etat} : « {valeur} » est saisi sans '
                        f'« {source} » — un seuil sans provenance est un '
                        f'seuil inventé.')

    def test_une_source_sans_valeur_n_existe_pas(self):
        for etat in ETATS:
            saisie = RACCORDEMENT[etat]['saisie']
            for valeur, source in COUPLES_SOURCES:
                if saisie[valeur] is None:
                    self.assertIsNone(
                        saisie[source],
                        f'{etat} : « {source} » est renseignée alors que '
                        f'« {valeur} » ne l’est pas.')

    def test_les_deux_refus_nomment_le_champ_de_provenance(self):
        for etat, attendu in (('refus_limite_sans_source', 'source_limite'),
                              ('refus_cos_phi_sans_source',
                               'source_cos_phi')):
            self.assertEqual(sorted(RACCORDEMENT[etat]), [attendu],
                             f'{etat} : le refus doit porter sur le champ '
                             f'de provenance, et sur lui seul.')
            self.assertTrue(RACCORDEMENT[etat][attendu].strip().endswith('.'))

    def test_le_couple_du_cos_phi_est_bien_publie(self):
        """CALX172 lit ces deux clés pour borner l'écrêtage."""
        saisie = RACCORDEMENT['exemple']['saisie']
        self.assertIsNotNone(
            saisie['cos_phi_impose'],
            "L'exemple doit montrer un cos φ SAISI : c'est l'état où "
            "l'écrêtage borne à s_max_kva × cos_phi_impose (CALX172).")
        self.assertTrue(saisie['source_cos_phi'])
        self.assertIsNone(
            RACCORDEMENT['exemple_vide']['saisie']['cos_phi_impose'],
            "L'état vide doit montrer le cos φ NON saisi : l'écrêtage "
            "retombe alors sur puissance_ac_kw, jamais sur un 1,0 supposé.")

    def test_le_cos_phi_du_site_n_est_pas_le_reglage_societe(self):
        """Deux grandeurs distinctes, deux noms distincts.

        `cos_phi_par_defaut` est un réglage SOCIÉTÉ (registre CALX145) ;
        `cos_phi_impose` est ce que le contrat de raccordement de CE site
        impose. Leur donner le même nom en ferait deux sources de vérité.
        """
        reglages = {entree[0] for entree in CLES_ELECTRIQUE_SOCIETE}
        self.assertIn('cos_phi_par_defaut', reglages)
        self.assertNotIn('cos_phi_impose', reglages)
        self.assertIn('cos_phi_par_defaut', RACCORDEMENT['pourquoi'])


class LimiteAbsenteTest(SimpleTestCase):
    """Le cas du Done : élévation publiée, verdict `omis` avec motif."""

    def test_l_exemple_n_a_pas_de_limite_saisie(self):
        self.assertIsNone(
            RACCORDEMENT['exemple']['saisie']['limite_elevation_pct'])

    def test_l_elevation_est_publiee_quand_meme(self):
        """Le chiffre existe, il est vrai, il se lit — c'est le verdict qui
        manque, pas la mesure."""
        self.assertIsNotNone(
            RACCORDEMENT['exemple']['calcul']['elevation_pct'])

    def test_le_verdict_est_omis_et_dit_pourquoi(self):
        verdict = verdicts('exemple')['elevation_tension']
        self.assertEqual(verdict['statut'], 'omis')
        self.assertIsNone(verdict['source'])
        detail = verdict['detail'].lower()
        self.assertIn('limite', detail)
        for attendu in ('maroc', 'suppos'):
            self.assertIn(
                attendu, detail,
                'Le motif doit dire qu’AUCUNE limite n’est supposée.')

    def test_sans_limite_aucune_marge_n_est_publiee(self):
        """`0` se lirait « limite atteinte »."""
        self.assertIsNone(RACCORDEMENT['exemple']['calcul']['marge_pct'])
        self.assertIsNone(RACCORDEMENT['exemple_vide']['calcul']['marge_pct'])

    def test_avec_limite_saisie_le_verdict_est_prononce(self):
        saisie = RACCORDEMENT['exemple_limite_saisie']['saisie']
        self.assertIsNotNone(saisie['limite_elevation_pct'])
        self.assertTrue(saisie['source_limite'])
        verdict = verdicts('exemple_limite_saisie')['elevation_tension']
        self.assertNotEqual(verdict['statut'], 'omis')
        self.assertTrue(verdict['source'],
                        'Un verdict prononcé nomme la saisie qui le fonde.')

    def test_la_marge_est_la_difference_a_la_limite(self):
        etat = RACCORDEMENT['exemple_limite_saisie']
        self.assertAlmostEqual(
            etat['calcul']['marge_pct'],
            etat['saisie']['limite_elevation_pct']
            - etat['calcul']['elevation_pct'],
            places=6,
            msg='`marge_pct` est la différence à la limite SAISIE, rien '
                'd’autre.')


class DesequilibreTest(SimpleTestCase):
    """Publié sans verdict tant que le réglage société n'est pas posé."""

    def test_la_cle_est_ecrite_sans_accent(self):
        """Deux graphies pour une même grandeur : le défaut que ce dossier
        existe pour empêcher. Le registre des réglages dit `desequilibre`."""
        self.assertIn('desequilibre_pct',
                      RACCORDEMENT['exemple']['calcul'])
        self.assertIn('seuil_desequilibre_pct',
                      {entree[0] for entree in CLES_ELECTRIQUE_SOCIETE})

    def test_le_desequilibre_est_publie_sans_verdict(self):
        self.assertIsNotNone(
            RACCORDEMENT['exemple']['calcul']['desequilibre_pct'])
        verdict = verdicts('exemple')['desequilibre_phases']
        self.assertEqual(verdict['statut'], 'omis')
        self.assertIn('seuil_desequilibre_pct', verdict['detail'])


class EtatVideTest(SimpleTestCase):
    """Aucune saisie ⇒ tout est `null`, et chaque verdict dit ce qui manque."""

    def test_toutes_les_saisies_sont_nulles(self):
        for valeur in RACCORDEMENT['exemple_vide']['saisie'].values():
            self.assertIsNone(valeur)

    def test_aucune_grandeur_n_est_publiee_a_zero(self):
        for champ, valeur in RACCORDEMENT['exemple_vide']['calcul'].items():
            self.assertIsNone(
                valeur,
                f'« {champ} » vaut {valeur!r} : une grandeur non calculée '
                f'vaut `null`, jamais `0` (README des contrats, règle 3).')

    def test_chaque_verdict_est_omis_et_nomme_son_champ(self):
        for verdict in RACCORDEMENT['exemple_vide']['verdicts']:
            self.assertEqual(verdict['statut'], 'omis', verdict['code'])
            self.assertIsNone(verdict['source'])
            self.assertTrue(verdict['detail'].strip())

    def test_aucune_tension_n_est_supposee(self):
        detail = verdicts('exemple_vide')['tension_nominale']['detail']
        self.assertIn('230', detail)
        self.assertIn('400', detail)
        self.assertIn('suppos', detail.lower(),
                      'Le motif doit dire que ni 230 V ni 400 V ne sont '
                      'supposés.')


class HorsSujetTest(SimpleTestCase):
    """Ni argent (D-CALX 5) ni énergie (W3) dans un raccordement."""

    def test_aucune_cle_d_argent_ni_d_energie(self):
        for etat in ETATS:
            texte = json.dumps(RACCORDEMENT[etat],
                               ensure_ascii=False).lower()
            for interdit in HORS_SUJET:
                self.assertNotIn(
                    f'"{interdit}', texte,
                    f'{etat} : le raccordement publie « {interdit} » — le '
                    f'calepinage ne calcule ni argent ni énergie.')
