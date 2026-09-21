"""CAD149 — VAGUE 1 des champs du script d'appel guidé (audit L3 du 21/09/2026).

Huit colonnes, ni plus ni moins (liste arrêtée par le fondateur — CAD160), et
les SIX endroits qui doivent suivre dans le MÊME commit :

  1. ``apps/crm/activity.py`` — ``TRACKED_FIELDS`` + ``_CHOICE_FIELDS`` ;
  2. ``apps/crm/selectors.py`` — ``LEAD_PROVENANCE_EXCLUSIONS`` (les deux
     champs que les marqueurs ``equip_``/``pompe_`` captent) ;
  3. ``draftCore.js`` ``TRACKED_KEYS``/``SECTION_FIELDS`` et
  4. ``fieldLabels.js`` — les DEUX endroits d'écran, livrés par CAD174 ;
  5. ``apps/crm/webhooks.py`` — ``_QUEST_NETTOYEURS_HORS_SITE`` (sans lui, une
     réponse portant le nom de la colonne est silencieusement jetée) ;
  6. ``apps/crm/questionnaire.py`` — ``CHAMPS_PAR_SECTION``, pour les seuls
     champs posables au client.

Règle qui gouverne le tout (``apps/crm/models.py``, bloc L4) : « chaque champ
EST le script d'appel » — la question orale vit dans le ``help_text``, jamais
recopiée ailleurs. D'où le test qui exige un ``help_text`` non vide, portant la
question, sur chacun des huit.

Aucune base de données : tout se vérifie sur les MÉTADONNÉES du modèle et sur
des fonctions pures (le mapping du webhook travaille sur un dict).
"""
from django.test import SimpleTestCase

from apps.crm import activity, questionnaire, selectors, webhooks
from apps.crm.models import Lead

#: LA liste, dans l'ordre du plan. Le test la compare au modèle : un neuvième
#: champ ajouté à cette vague rougit ici, et c'est le but.
CHAMPS_VAGUE_1 = (
    'type_bien',
    'objectif_projet',
    'decideur',
    'devis_concurrents',
    'equip_ve_statut',
    'pompage_heures_jour',
    'pompe_alim_actuelle',
    'carburant_litres_mois',
)

#: Les six champs à vocabulaire fermé, et leurs valeurs EXACTES.
VALEURS_ATTENDUES = {
    'type_bien': ['villa', 'appartement', 'immeuble', 'riad', 'ferme',
                  'autre'],
    'objectif_projet': ['facture', 'secours_coupures', 'autonomie',
                        'injection_8221', 'autre'],
    'decideur': ['seul', 'conjoint_famille', 'associe_direction',
                 'proprietaire_tiers'],
    'devis_concurrents': ['non', 'en_attente', 'recu'],
    'equip_ve_statut': ['possede', 'prevu'],
    'pompe_alim_actuelle': ['aucune', 'diesel', 'butane', 'electrique'],
}


def _champ(nom):
    return Lead._meta.get_field(nom)


class LesHuitChampsDeLaVague1(SimpleTestCase):
    def test_les_huit_existent_sur_le_lead(self):
        for nom in CHAMPS_VAGUE_1:
            self.assertIsNotNone(_champ(nom), nom)

    def test_chacun_est_nullable_donc_vide_veut_dire_pas_encore_posee(self):
        """Vide ≠ « non » : une question jamais posée ne doit pas se lire
        comme une réponse négative (même règle que le bloc L4)."""
        for nom in CHAMPS_VAGUE_1:
            champ = _champ(nom)
            self.assertTrue(champ.null, f'{nom} doit être null=True')
            self.assertTrue(champ.blank, f'{nom} doit être blank=True')
            self.assertFalse(champ.has_default(),
                             f'{nom} ne doit porter AUCUN défaut')

    def test_chacun_porte_sa_question_dans_son_help_text(self):
        """« Chaque champ EST le script d'appel » : la question orale vit
        dans le ``help_text``, à la source, jamais recopiée ailleurs."""
        for nom in CHAMPS_VAGUE_1:
            texte = _champ(nom).help_text
            self.assertTrue(texte, f'{nom} : help_text vide')
            self.assertIn("Question à l'appel", texte, nom)

    def test_les_vocabulaires_sont_exactement_ceux_arretes(self):
        for nom, valeurs in VALEURS_ATTENDUES.items():
            self.assertEqual([v for v, _ in _champ(nom).choices], valeurs, nom)

    def test_le_butane_est_garde(self):
        """Inventer « diesel/réseau/aucune » créerait un second vocabulaire
        et perdrait un cas réel du parc marocain."""
        self.assertIn('butane', [v for v, _ in
                                 _champ('pompe_alim_actuelle').choices])

    def test_chaque_valeur_tient_dans_la_colonne(self):
        for nom, valeurs in VALEURS_ATTENDUES.items():
            longueur = _champ(nom).max_length
            for valeur in valeurs:
                self.assertLessEqual(len(valeur), longueur,
                                     f'{nom} : « {valeur} » déborde')

    def test_aucun_prenom_dans_les_questions(self):
        """Règle fondateur du 08/09/2026 : aucun prénom codé en dur."""
        for nom in CHAMPS_VAGUE_1:
            texte = _champ(nom).help_text
            for interdit in ('Meryem', 'Reda', 'TAQINOR'):
                self.assertNotIn(interdit, texte, nom)


class LesSixEndroitsSuivent(SimpleTestCase):
    def test_1_le_chatter_journalise_les_huit(self):
        for nom in CHAMPS_VAGUE_1:
            self.assertIn(nom, activity.TRACKED_FIELDS, nom)
            self.assertTrue(activity.TRACKED_FIELDS[nom], nom)

    def test_1bis_les_champs_a_vocabulaire_sont_declares_comme_tels(self):
        """Sans cela, l'historique afficherait la valeur BRUTE (« recu »)
        au lieu de son libellé français."""
        for nom in VALEURS_ATTENDUES:
            self.assertIn(nom, activity._CHOICE_FIELDS, nom)
        for nom in ('pompage_heures_jour', 'carburant_litres_mois'):
            self.assertNotIn(nom, activity._CHOICE_FIELDS, nom)

    def test_2_la_garde_de_provenance_ne_signale_aucune_omission(self):
        """QJR234/DC11 : `equip_ve_statut` et `pompe_alim_actuelle` portent
        un marqueur — sans exclusion MOTIVÉE, la garde rougit."""
        self.assertEqual(selectors.lead_provenance_omissions(), [])

    def test_2bis_les_deux_champs_marques_portent_une_raison_ecrite(self):
        surveilles = selectors.lead_provenance_champs_energie_toit()
        for nom in ('equip_ve_statut', 'pompe_alim_actuelle'):
            self.assertIn(nom, surveilles, nom)
            raison = selectors.LEAD_PROVENANCE_EXCLUSIONS.get(nom)
            self.assertTrue(isinstance(raison, str) and len(raison) > 40, nom)

    def test_2ter_les_six_autres_ne_sont_pas_captes_par_les_marqueurs(self):
        """Contrôle négatif : une exclusion inutile est du bruit à relire."""
        surveilles = set(selectors.lead_provenance_champs_energie_toit())
        for nom in CHAMPS_VAGUE_1:
            if nom in ('equip_ve_statut', 'pompe_alim_actuelle'):
                continue
            self.assertNotIn(nom, surveilles, nom)

    def test_5_le_questionnaire_client_sait_nettoyer_les_huit(self):
        for nom in CHAMPS_VAGUE_1:
            self.assertIn(nom, webhooks._QUEST_NETTOYEURS_HORS_SITE, nom)

    def test_5bis_un_nettoyeur_refuse_une_valeur_hors_vocabulaire(self):
        nettoyeurs = webhooks._QUEST_NETTOYEURS_HORS_SITE
        self.assertEqual(nettoyeurs['type_bien']('villa'), 'villa')
        self.assertIsNone(nettoyeurs['type_bien']('chateau'))
        self.assertIsNone(nettoyeurs['pompe_alim_actuelle']('solaire'))
        self.assertIsNone(nettoyeurs['pompage_heures_jour']('beaucoup'))

    def test_6_seuls_les_champs_posables_au_client_sont_dans_une_section(self):
        """Décision fondateur du 21/09/2026 : décideur et concurrents ne se
        posent qu'à l'ORAL — jamais dans le questionnaire envoyé au client."""
        toutes = set()
        for colonnes in questionnaire.CHAMPS_PAR_SECTION.values():
            toutes.update(colonnes)
        self.assertIn('type_bien', questionnaire.CHAMPS_PAR_SECTION['toiture'])
        self.assertIn('objectif_projet',
                      questionnaire.CHAMPS_PAR_SECTION['energie'])
        self.assertIn('equip_ve_statut',
                      questionnaire.CHAMPS_PAR_SECTION['equipements'])
        for nom in ('decideur', 'devis_concurrents'):
            self.assertNotIn(nom, toutes, nom)

    def test_6bis_toute_colonne_de_section_est_un_vrai_champ_du_lead(self):
        concrets = {f.name for f in Lead._meta.get_fields()
                    if getattr(f, 'concrete', False)}
        for section, colonnes in questionnaire.CHAMPS_PAR_SECTION.items():
            for colonne in colonnes:
                self.assertIn(colonne, concrets, f'{section}.{colonne}')


class LesReponsesDePompagePromues(SimpleTestCase):
    """Les deux réponses du site qui vivaient dans le sac ``web_questionnaire``
    atterrissent désormais dans leur colonne — même geste que HMT/débit/CV."""

    PAYLOAD = {
        'mode': 'agricole',
        'heuresPompage': 7,
        'pompeActuelle': 'butane',
    }

    def test_les_deux_quittent_le_sac_pour_leur_colonne(self):
        fields = webhooks._map_payload_to_fields(dict(self.PAYLOAD))
        self.assertEqual(float(fields['pompage_heures_jour']), 7.0)
        self.assertEqual(fields['pompe_alim_actuelle'], 'butane')
        sac = fields.get('web_questionnaire') or {}
        self.assertNotIn('heures_pompage', sac)
        self.assertNotIn('pompe_actuelle', sac)

    def test_la_note_de_chatter_cite_toujours_les_deux_reponses(self):
        """La note est construite depuis le payload COMPLET : la promotion ne
        doit RIEN retirer de ce que la commerciale lit dans l'historique."""
        complet = webhooks._extract_web_questionnaire(dict(self.PAYLOAD))
        note = webhooks._build_questionnaire_note(complet, {}, 'agricole')
        self.assertIn('7 h/j', note)
        self.assertIn('butane', note)

    def test_une_reponse_absente_ne_pose_aucune_valeur(self):
        """Zéro chiffre inventé : pas de réponse, pas de colonne écrite."""
        fields = webhooks._map_payload_to_fields({'mode': 'agricole'})
        self.assertNotIn('pompage_heures_jour', fields)
        self.assertNotIn('pompe_alim_actuelle', fields)
