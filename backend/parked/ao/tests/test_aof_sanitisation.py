"""AOF143 — la sanitisation est contextuelle par champ, pas un grep.

Les trois promesses :
  1. un rendu client contenant un mot BLOQUANT est REFUSÉ, avec le mot cité,
     son champ et son extrait — jamais un refus muet ;
  2. l'exception explicitement codée « capacité démontrée N vs engagé E »
     PASSE : c'est l'argument de sérieux du dossier réel ;
  3. le niveau AVERTISSEMENT ne bloque pas mais PROPOSE une substitution
     canonique ; la réécriture est un geste séparé, jamais automatique.

Et le corollaire qui rend la règle contextuelle : le MÊME texte est refusé
dans un champ `client` et accepté dans un champ `directeur`.

Run :
    python manage.py test apps.ao.tests.test_aof_sanitisation -v2
"""
from django.test import SimpleTestCase

from apps.ao.fabrique.sanitisation import (
    AVERTISSEMENT, BLOQUANT, SanitisationBloquante, analyser,
    appliquer_substitutions, empans_exception, sanitiser,
)


def champ(valeur, *, nom='memoire.4.2', portee='client'):
    return [{'champ': nom, 'valeur': valeur, 'portee': portee}]


class LexiqueBloquantTest(SimpleTestCase):
    def test_les_cinq_mots_bloquants_refusent_le_rendu(self):
        cas = {
            "Le prix d'achat des modules est de 2 950 DH.": 'COUT_ACHAT',
            'Notre coût de revient couvre la pose.': 'COUT_REVIENT',
            'La marge appliquée est confortable.': 'MARGE',
            'Le bénéfice net attendu est conforme.': 'BENEFICE',
            'Le maximum posable sur ce site est atteint.': 'MAX_POSABLE',
        }
        for texte, code in cas.items():
            with self.assertRaises(SanitisationBloquante, msg=texte) as capt:
                sanitiser(champ(texte))
            codes = [c['code'] for c in capt.exception.constats]
            self.assertIn(code, codes, texte)

    def test_le_refus_cite_le_mot_le_champ_et_l_extrait(self):
        with self.assertRaises(SanitisationBloquante) as capture:
            sanitiser(champ("Notre coût de revient est maîtrisé.",
                            nom='memoire.7.1'))
        constat = capture.exception.constats[0]
        self.assertEqual(constat['champ'], 'memoire.7.1')
        self.assertEqual(constat['mot'], 'coût de revient')
        self.assertIn('revient', constat['extrait'])
        # Le message d'erreur est lisible tel quel par un humain.
        self.assertIn('memoire.7.1', str(capture.exception))
        self.assertIn('coût de revient', str(capture.exception))

    def test_le_maximum_agrege_du_site_est_refuse(self):
        for texte in ('La capacité maximale du site est de 630 modules.',
                      'Potentiel maximum : 618 modules.',
                      'Le maximum global atteignable est connu.'):
            with self.assertRaises(SanitisationBloquante, msg=texte):
                sanitiser(champ(texte))

    def test_une_valeur_de_base_interne_est_refusee_avec_ses_espaces(self):
        for ecriture in ('630', '618'):
            texte = 'Nous retenons {} unités.'.format(ecriture)
            with self.assertRaises(SanitisationBloquante) as capture:
                sanitiser(champ(texte), valeurs_interdites=(630, 618))
            self.assertIn('VALEUR_INTERNE',
                          [c['code'] for c in capture.exception.constats])

    def test_le_nom_du_bureau_est_refuse_en_marque_blanche(self):
        texte = 'Étude réalisée par TAQINOR pour le compte du groupement.'
        with self.assertRaises(SanitisationBloquante) as capture:
            sanitiser(champ(texte), marque_blanche=True, bureau='TAQINOR')
        self.assertEqual(capture.exception.constats[0]['code'],
                         'MARQUE_BLANCHE')
        # Hors marque blanche, la même phrase passe.
        self.assertEqual(
            [c for c in analyser(champ(texte), marque_blanche=False,
                                 bureau='TAQINOR')
             if c['niveau'] == BLOQUANT], [])


class ExceptionDemontreeEngageTest(SimpleTestCase):
    """L'argument VOULU du dossier réel doit passer."""

    def test_la_phrase_demontree_vs_engage_passe(self):
        texte = ("Capacité démontrée par le calepinage : 314 modules ; "
                 "engagement porté au bordereau : 288 modules. Le marché "
                 "étant à prix unitaires, le décompte final portera sur les "
                 "quantités réellement installées.")
        avertissements = sanitiser(champ(texte))
        self.assertTrue(all(c['niveau'] == AVERTISSEMENT
                            for c in avertissements))

    def test_l_exception_est_bien_reconnue_comme_empan(self):
        texte = 'capacité maximale démontrée 314, engagement 288'
        self.assertTrue(empans_exception(texte))
        # Le « maximale » est dans l'empan de l'exception : il passe.
        self.assertEqual(
            [c for c in analyser(champ(texte)) if c['niveau'] == BLOQUANT], [])

    def test_l_exception_ne_couvre_QUE_son_empan(self):
        texte = ("Capacité démontrée 314, engagement 288. "
                 "Par ailleurs le maximum du site est de 630.")
        with self.assertRaises(SanitisationBloquante) as capture:
            sanitiser(champ(texte))
        codes = [c['code'] for c in capture.exception.constats]
        self.assertIn('MAX_AGREGE', codes)

    def test_l_exception_ne_couvre_pas_les_mots_de_cout(self):
        texte = "Capacité démontrée 314, engagement 288, marge 36 %."
        with self.assertRaises(SanitisationBloquante) as capture:
            sanitiser(champ(texte))
        self.assertIn('MARGE', [c['code'] for c in capture.exception.constats])


class ContextuelParChampTest(SimpleTestCase):
    """Le même texte : refusé côté client, accepté côté directeur."""

    TEXTE = "Coût de revient 2 666 600 HT, bénéfice net visé 1 500 000."

    def test_refuse_en_portee_client(self):
        with self.assertRaises(SanitisationBloquante):
            sanitiser(champ(self.TEXTE, portee='client'))

    def test_accepte_en_portee_directeur(self):
        self.assertEqual(
            [c for c in analyser(champ(self.TEXTE, portee='directeur'))
             if c['niveau'] == BLOQUANT], [])

    def test_accepte_en_portee_interne(self):
        self.assertEqual(
            [c for c in analyser(champ(self.TEXTE, portee='interne'))
             if c['niveau'] == BLOQUANT], [])

    def test_une_portee_absente_est_traitee_comme_client(self):
        """Le défaut est le plus SÉVÈRE : un champ mal étiqueté ne passe pas."""
        with self.assertRaises(SanitisationBloquante):
            sanitiser([{'champ': 'x', 'valeur': self.TEXTE}])


class VocabulaireTechniqueTest(SimpleTestCase):
    """Un détecteur bruyant est désactivé en trois dossiers."""

    def test_les_marges_d_ingenieur_ne_sont_pas_bloquees(self):
        for texte in ('Marge de sécurité de 4,15 cm en rive.',
                      'Les marges de robustesse sont conservées.',
                      "Marge d'implantation respectée.",
                      'Marge disponible : 4,94 kWh.',
                      'Marge de manœuvre en maintenance.'):
            self.assertEqual(
                [c for c in analyser(champ(texte)) if c['niveau'] == BLOQUANT],
                [], texte)

    def test_la_marge_nue_reste_bloquee(self):
        with self.assertRaises(SanitisationBloquante):
            sanitiser(champ('Notre marge reste raisonnable.'))


class AvertissementsTest(SimpleTestCase):
    def test_les_trois_substitutions_canoniques_sont_proposees(self):
        texte = ("Sur consigne client, le croquis a été repris ; "
                 "le client a validé.")
        avertissements = sanitiser(
            champ(texte),
            substitutions={'date_decision': '27/07/2026',
                           'date_releve': '27/07/2026'})
        par_code = {c['code']: c for c in avertissements}
        self.assertEqual(par_code['CONSIGNE_CLIENT']['suggestion'],
                         'prescription')
        self.assertIn("décision d'études du 27/07/2026",
                      par_code['CLIENT']['suggestion'])
        self.assertIn('relevé contradictoire du 27/07/2026',
                      par_code['CROQUIS']['suggestion'])

    def test_consigne_client_l_emporte_sur_client(self):
        """La règle la plus spécifique gagne : pas deux constats sur un mot."""
        constats = analyser(champ('Sur consigne client uniquement.'))
        codes = [c['code'] for c in constats]
        self.assertIn('CONSIGNE_CLIENT', codes)
        self.assertNotIn('CLIENT', codes)

    def test_un_avertissement_ne_bloque_jamais(self):
        avertissements = sanitiser(champ('Le croquis du client.'))
        self.assertTrue(avertissements)

    def test_la_reecriture_est_un_geste_separe(self):
        texte = 'Sur consigne client, le croquis a été repris.'
        constats = analyser(champ(texte),
                            substitutions={'date_releve': '27/07/2026'})
        # sanitiser() ne touche pas au texte…
        self.assertEqual(sanitiser(champ(texte)) and texte, texte)
        # …c'est appliquer_substitutions() qui le fait, sur demande.
        reecrit = appliquer_substitutions(texte, constats)
        self.assertIn('prescription', reecrit)
        self.assertIn('relevé contradictoire du 27/07/2026', reecrit)
        self.assertNotIn('croquis', reecrit)

    def test_les_avertissements_valent_aussi_en_portee_interne(self):
        constats = analyser(champ('Le croquis du client.', portee='interne'))
        self.assertTrue([c for c in constats if c['niveau'] == AVERTISSEMENT])
