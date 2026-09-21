"""CAD154 — VAGUE 2 des champs du script d'appel guidé (audit L3 du 21/09/2026).

Six besoins réels qui ne bloquaient pas l'appel 1, ouverts une fois la vague 1
(CAD149) stabilisée. La liste est arrêtée par le fondateur (CAD160) :
``nb_personnes_foyer``, ``budget_client_mad``, ``frein_principal``,
``declencheur``, ``compteur_puissance_kva`` et le chauffage d'hiver.

CE QUI ALLÈGE LA CHECKLIST PAR RAPPORT À LA VAGUE 1 : aucun champ de cette
vague ne porte un marqueur de provenance énergie/toiture (``equip_``,
``pompe_``, ``*kwh*``, ``batterie*``, ``raccordement``, ``nb_etages``,
``structure_``, ``kwc``) — il n'y a donc AUCUNE exclusion à motiver dans
``selectors.py``, et le test ci-dessous le PROUVE au lieu de l'affirmer.

Deux décisions fondateur du 21/09/2026 sont vérifiées ici :
  · ``budget_client_mad`` est un champ DISTINCT de ``montant_estime``
    (l'estimation du commercial, qui nourrit le forecast pondéré) et il ne se
    pose qu'APRÈS l'envoi du devis — jamais à l'appel 1 ;
  · aucune couche de chauffage d'hiver n'est composée : le champ est
    informatif, et son ``help_text`` le dit.

Aucune base de données : tout se lit sur les métadonnées du modèle.
"""
from django.test import SimpleTestCase

from apps.crm import activity, panneau_appel, questionnaire, selectors, webhooks
from apps.crm.models import Lead

#: LA liste de la vague 2, dans l'ordre du plan.
CHAMPS_VAGUE_2 = (
    'nb_personnes_foyer',
    'budget_client_mad',
    'frein_principal',
    'declencheur',
    'compteur_puissance_kva',
    'chauffage_electrique_hiver',
)

#: Les deux vocabulaires, REPRIS de la qualification de visite.
VALEURS_ATTENDUES = {
    'frein_principal': ['aucun', 'prix', 'compare', 'timing', 'technique',
                        'confiance'],
    'declencheur': ['economies', 'coupures', 'ecologie', 'technologie'],
}


def _champ(nom):
    return Lead._meta.get_field(nom)


class LesSixChampsDeLaVague2(SimpleTestCase):
    def test_les_six_existent_et_sont_nullables(self):
        for nom in CHAMPS_VAGUE_2:
            champ = _champ(nom)
            self.assertTrue(champ.null, f'{nom} doit être null=True')
            self.assertTrue(champ.blank, f'{nom} doit être blank=True')
            self.assertFalse(champ.has_default(),
                             f'{nom} ne doit porter AUCUN défaut')

    def test_chacun_porte_sa_question_dans_son_help_text(self):
        for nom in CHAMPS_VAGUE_2:
            texte = _champ(nom).help_text
            self.assertTrue(texte, f'{nom} : help_text vide')
            self.assertIn("Question à l'appel", texte, nom)

    def test_les_deux_vocabulaires_reprennent_celui_de_la_visite(self):
        from apps.visites.qualification import CHOIX
        self.assertEqual([v for v, _ in _champ('frein_principal').choices],
                         list(CHOIX['frein']))
        self.assertEqual([v for v, _ in _champ('declencheur').choices],
                         list(CHOIX['declencheur']))
        for nom, valeurs in VALEURS_ATTENDUES.items():
            self.assertEqual([v for v, _ in _champ(nom).choices], valeurs, nom)

    def test_chaque_valeur_tient_dans_la_colonne(self):
        for nom, valeurs in VALEURS_ATTENDUES.items():
            longueur = _champ(nom).max_length
            for valeur in valeurs:
                self.assertLessEqual(len(valeur), longueur,
                                     f'{nom} : « {valeur} » déborde')

    def test_le_budget_du_client_n_est_PAS_le_montant_estime(self):
        """Décision fondateur (Q23) : deux champs, deux sens. Le montant
        estimé est l'estimation du COMMERCIAL et nourrit le forecast ; le
        budget est ce que le CLIENT annonce."""
        self.assertNotEqual(_champ('budget_client_mad').verbose_name,
                            _champ('montant_estime').verbose_name)
        self.assertIn('commercial', _champ('montant_estime').help_text.lower())
        self.assertIn('client', _champ('budget_client_mad').help_text.lower())

    def test_le_chauffage_d_hiver_est_informatif(self):
        """Décision fondateur (Q18) : PAS de couche de chauffage d'hiver."""
        texte = _champ('chauffage_electrique_hiver').help_text
        self.assertIn('INFORMATIF', texte)
        self.assertIn('AUCUNE courbe', texte)


class AucuneExclusionDeProvenanceANeMotiver(SimpleTestCase):
    """La précision qui allège la checklist : aucun champ de cette vague n'est
    capté par les marqueurs de provenance — il n'y a donc rien à déclarer dans
    ``LEAD_PROVENANCE_EXCLUSIONS``. Prouvé, pas affirmé."""

    def test_aucun_champ_de_la_vague_2_n_est_surveille(self):
        surveilles = set(selectors.lead_provenance_champs_energie_toit())
        for nom in CHAMPS_VAGUE_2:
            self.assertNotIn(nom, surveilles, nom)

    def test_la_garde_de_provenance_reste_verte(self):
        self.assertEqual(selectors.lead_provenance_omissions(), [])

    def test_aucune_exclusion_inutile_n_a_ete_ajoutee(self):
        for nom in CHAMPS_VAGUE_2:
            self.assertNotIn(nom, selectors.LEAD_PROVENANCE_EXCLUSIONS, nom)


class LesEndroitsQuiSuivent(SimpleTestCase):
    def test_le_chatter_journalise_les_six(self):
        for nom in CHAMPS_VAGUE_2:
            self.assertIn(nom, activity.TRACKED_FIELDS, nom)
            self.assertTrue(activity.TRACKED_FIELDS[nom], nom)

    def test_seuls_les_deux_vocabulaires_sont_declares_comme_choices(self):
        for nom in VALEURS_ATTENDUES:
            self.assertIn(nom, activity._CHOICE_FIELDS, nom)
        for nom in ('nb_personnes_foyer', 'budget_client_mad',
                    'compteur_puissance_kva', 'chauffage_electrique_hiver'):
            self.assertNotIn(nom, activity._CHOICE_FIELDS, nom)

    def test_le_questionnaire_client_sait_nettoyer_les_six(self):
        for nom in CHAMPS_VAGUE_2:
            self.assertIn(nom, webhooks._QUEST_NETTOYEURS_HORS_SITE, nom)

    def test_un_nettoyeur_refuse_une_valeur_hors_vocabulaire(self):
        nettoyeurs = webhooks._QUEST_NETTOYEURS_HORS_SITE
        self.assertEqual(nettoyeurs['frein_principal']('prix'), 'prix')
        self.assertIsNone(nettoyeurs['frein_principal']('pas_envie'))
        self.assertIsNone(nettoyeurs['declencheur']('curiosite'))
        self.assertIs(nettoyeurs['chauffage_electrique_hiver'](True), True)
        self.assertIsNone(nettoyeurs['chauffage_electrique_hiver']('oui'))
        self.assertEqual(nettoyeurs['nb_personnes_foyer']('5'), 5)


class OuChaqueQuestionSePose(SimpleTestCase):
    def test_les_deux_questions_techniques_entrent_dans_le_questionnaire(self):
        occupation = questionnaire.CHAMPS_PAR_SECTION['occupation']
        self.assertIn('nb_personnes_foyer', occupation)
        self.assertIn('chauffage_electrique_hiver', occupation)

    def test_budget_frein_declencheur_restent_HORS_du_questionnaire(self):
        """Décision fondateur (Q21) : budget, délai, décideur et concurrents
        ne se posent qu'à l'oral."""
        toutes = set()
        for colonnes in questionnaire.CHAMPS_PAR_SECTION.values():
            toutes.update(colonnes)
        for nom in ('budget_client_mad', 'frein_principal', 'declencheur'):
            self.assertNotIn(nom, toutes, nom)

    def test_la_puissance_du_compteur_n_est_pas_demandee_par_ecrit(self):
        """La voie NORMALE est la photo du compteur, que le questionnaire
        demande déjà — on ne fait pas lire une plaque en dernier recours."""
        toutes = set()
        for colonnes in questionnaire.CHAMPS_PAR_SECTION.values():
            toutes.update(colonnes)
        self.assertNotIn('compteur_puissance_kva', toutes)
        self.assertIn('photo_compteur', questionnaire.CHAMPS_PAR_SECTION)

    def test_frein_et_declencheur_sont_proposes_par_le_panneau_d_appel(self):
        champs = [q['champ'] for q in panneau_appel.questions_a_poser(
            Lead(nom='Prospect'))]
        self.assertIn('frein_principal', champs)
        self.assertIn('declencheur', champs)

    def test_le_budget_n_est_pas_propose_a_l_appel_1(self):
        """Il ne se pose qu'APRÈS l'envoi du devis (décision fondateur)."""
        self.assertNotIn('budget_client_mad', panneau_appel.CHAMPS_ORAUX)
        champs = [q['champ'] for q in panneau_appel.questions_a_poser(
            Lead(nom='Prospect'))]
        self.assertNotIn('budget_client_mad', champs)
