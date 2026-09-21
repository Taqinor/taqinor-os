# -*- coding: utf-8 -*-
"""CAD173 — le lot des réglages du calcul et du contenu, tranché le 21/09/2026.

Huit décisions fondateur sont APPLIQUÉES par cette tâche ; les cinq autres sont
parties dans leur propre tâche de build (Q14 → CAD166, Q16 → CAD167, Q20 →
CAD74, Q23 → CAD154, Q24 → CAD158). Ce module verrouille les huit.

* **Q10** — le chauffe-eau se qualifie par la PAIRE puissance + créneau ; le
  booléen seul reste informatif. C'est le statu quo déjà câblé : rien à changer
  dans le moteur, et le test l'exige pour que personne ne le « corrige ».
* **Q11** — une couche qui dépasse la journée est PLAFONNÉE, et le plafonnement
  est EXPOSÉ par un drapeau (jamais un dépassement silencieux).
* **Q12** — la clim et la piscine passent de juin-août à MAI→OCTOBRE, alignées
  sur la facture d'été : les deux « étés » du moteur n'en font plus qu'un.
* **Q15** — les coupures restent un ARGUMENT commercial : aucun dimensionnement
  de secours, aucun calcul.
* **Q17** — l'économie de carburant agricole se calcule UNIQUEMENT sur le prix
  déclaré par le client : AUCUN prix de gasoil de référence n'est écrit nulle
  part (grep = 0).
* **Q18** — PAS de couche de chauffage d'hiver.
* **Q21** — budget, délai, décideur et concurrents restent HORS du
  questionnaire envoyé au client.
* **Q22** — sur les subventions, on ne promet rien.
"""
import re
from pathlib import Path

from django.test import SimpleTestCase

from apps.crm import questionnaire
from apps.ventes import courbes_journalieres as CJ
from apps.ventes import etude_horaire as EH

RACINE = Path(__file__).resolve().parents[5]
MESSAGES = RACINE / 'docs' / 'crm' / 'messages_meryem.md'
SOURCES_MOTEUR = (
    RACINE / 'backend' / 'django_core' / 'apps' / 'ventes'
    / 'courbes_journalieres.py',
    RACINE / 'backend' / 'django_core' / 'apps' / 'ventes' / 'etude_horaire.py',
)


class Q11_LePlafonnementEstEXPOSE(SimpleTestCase):
    """« Jamais un dépassement silencieux. »"""

    #: Chauffe-eau volontairement démesuré pour le niveau servi : 2,5 kW
    #: pendant les 9 h du créneau « journée » sur une journée de 5 kWh.
    COUCHE = {'chauffe_eau': {
        'kw': 2.5, 'heures': list(CJ.CHAUFFE_EAU_CRENEAUX['journee']),
        'saisons': None, 'mode': 'redistribution', 'source': 'test'}}

    def test_une_couche_qui_deborde_porte_le_DRAPEAU(self):
        _, couches = CJ.forme_consommation_detaillee(
            5.0, 'presence_jour', equipements=self.COUCHE)
        info = couches['chauffe_eau']
        self.assertTrue(info['plafonnee'])
        self.assertLess(info['facteur'], 1.0)
        self.assertIn('journée', info['plafond_motif'])
        # Le débordement est CHIFFRÉ : la couche déclare plus que la journée.
        self.assertGreater(info['brute_kwh'], 5.0)

    def test_une_couche_qui_tient_dans_la_journee_n_est_PAS_plafonnee(self):
        _, couches = CJ.forme_consommation_detaillee(
            300.0, 'presence_jour', equipements=self.COUCHE)
        self.assertFalse(couches['chauffe_eau']['plafonnee'])
        self.assertNotIn('plafond_motif', couches['chauffe_eau'])

    def test_le_facteur_est_publie_avec_chaque_couche(self):
        _, couches = CJ.forme_consommation_detaillee(
            5.0, 'presence_jour', equipements=self.COUCHE)
        self.assertIn('facteur', couches['chauffe_eau'])
        self.assertGreater(couches['chauffe_eau']['facteur'], 0.0)

    def test_l_energie_servie_reste_celle_du_facteur(self):
        """Le drapeau DÉCRIT le rabotage, il ne le change pas."""
        _, couches = CJ.forme_consommation_detaillee(
            5.0, 'presence_jour', equipements=self.COUCHE)
        info = couches['chauffe_eau']
        for heure in info['heures']:
            self.assertAlmostEqual(info['heures_kwh'][heure],
                                   info['kw'] * info['facteur'], places=6)


class Q12_LaSaisonDeLaClimEtDeLaPiscine(SimpleTestCase):
    """Mai→octobre, le découpage de la FACTURE d'été."""

    PISCINE = {'piscine': {
        'kw': 1.5, 'heures': list(CJ.PISCINE_HEURES), 'saisons': ['ete'],
        'mode': 'redistribution', 'source': 'test'}}

    def test_les_mois_sont_ceux_de_la_facture_d_ete(self):
        self.assertEqual(sorted(CJ.MOIS_REDISTRIBUTION_ETE),
                         sorted(mois + 1 for mois in EH.MOIS_ETE_FACTURE))

    def test_mai_et_octobre_sont_DESORMAIS_actifs(self):
        for mois in (5, 10):
            _, couches = CJ.forme_consommation_detaillee(
                300.0, 'presence_jour', equipements=self.PISCINE, mois=mois)
            self.assertIn('piscine', couches, mois)

    def test_avril_et_novembre_restent_HORS_saison(self):
        for mois in (1, 4, 11, 12):
            _, couches = CJ.forme_consommation_detaillee(
                300.0, 'presence_jour', equipements=self.PISCINE, mois=mois)
            self.assertNotIn('piscine', couches, mois)

    def test_le_coeur_de_l_ete_reste_actif(self):
        for mois in (6, 7, 8):
            _, couches = CJ.forme_consommation_detaillee(
                300.0, 'presence_jour', equipements=self.PISCINE, mois=mois)
            self.assertIn('piscine', couches, mois)

    def test_une_couche_SANS_saison_est_active_toute_l_annee(self):
        chauffe_eau = {'chauffe_eau': {
            'kw': 2.0, 'heures': [23, 0, 1], 'saisons': None,
            'mode': 'redistribution', 'source': 'test'}}
        for mois in range(1, 13):
            _, couches = CJ.forme_consommation_detaillee(
                300.0, 'presence_jour', equipements=chauffe_eau, mois=mois)
            self.assertIn('chauffe_eau', couches, mois)

    def test_SANS_mois_le_comportement_d_avant_est_conserve(self):
        """Non-régression : un appelant qui ne connaît que la saison PVGIS
        garde exactement le chemin d'avant."""
        _, ete = CJ.forme_consommation_detaillee(
            300.0, 'presence_jour', equipements=self.PISCINE, saison='ete')
        self.assertIn('piscine', ete)
        _, hiver = CJ.forme_consommation_detaillee(
            300.0, 'presence_jour', equipements=self.PISCINE, saison='hiver')
        self.assertNotIn('piscine', hiver)

    def test_la_publication_client_suit_les_MEMES_mois(self):
        """Deux portes différentes publieraient d'autres mois que ceux
        réellement servis — c'est exactement le défaut que Q12 ferme."""
        estimation = EH.estimation_conso_mensuelle([600.0] * 12, self.PISCINE)
        self.assertIsNotNone(estimation)
        ajouts = estimation['ajouts']['piscine']
        for index, valeur in enumerate(ajouts):
            actif = (index + 1) in CJ.MOIS_REDISTRIBUTION_ETE
            if actif:
                self.assertGreater(valeur, 0.0, index + 1)
            else:
                self.assertEqual(valeur, 0.0, index + 1)


class Q17_AucunPrixDeCarburantEnDur(SimpleTestCase):
    """L'économie de carburant se calcule sur le prix DÉCLARÉ, jamais sur un
    prix de marché supposé."""

    #: Une constante de prix de carburant, sous toutes ses graphies.
    MOTIF = re.compile(
        r'(?i)\b(prix|cout|coût|tarif)[_ ]?(gasoil|gazole|diesel|carburant)\b'
        r'|\b(gasoil|gazole|diesel)[_ ]?(mad|dh|prix|litre)\b')

    def _fichiers(self):
        racine = RACINE / 'backend' / 'django_core' / 'apps'
        for chemin in racine.rglob('*.py'):
            if 'migrations' in chemin.parts or 'tests' in chemin.parts:
                continue
            if chemin.name.startswith('test'):
                continue
            yield chemin

    def test_grep_zero_sur_tout_le_backend(self):
        coupables = []
        for chemin in self._fichiers():
            texte = chemin.read_text(encoding='utf-8', errors='ignore')
            for numero, ligne in enumerate(texte.splitlines(), start=1):
                if self.MOTIF.search(ligne) and re.search(r'\d', ligne):
                    coupables.append(f'{chemin.name}:{numero}: {ligne.strip()}')
        self.assertEqual(coupables, [])

    def test_le_moteur_ne_porte_aucune_conversion_litres_vers_dirhams(self):
        for chemin in SOURCES_MOTEUR:
            texte = chemin.read_text(encoding='utf-8')
            self.assertNotIn('MAD_PAR_LITRE', texte, chemin.name)
            self.assertNotIn('PRIX_LITRE', texte, chemin.name)

    def test_la_regle_est_ECRITE_pour_les_textes_clients(self):
        contenu = MESSAGES.read_text(encoding='utf-8')
        self.assertIn('Carburant agricole', contenu)
        self.assertIn('Aucun prix de gasoil de référence', contenu)


class Q21_LesQuatreChampsDeProjetRestentORAUX(SimpleTestCase):
    """Budget, délai, décideur et concurrents ne se posent qu'à l'oral."""

    CHAMPS = ('budget_client_mad', 'project_timeline', 'decideur',
              'devis_concurrents')

    def test_aucun_des_quatre_n_est_dans_CHAMPS_PAR_SECTION(self):
        toutes = set()
        for colonnes in questionnaire.CHAMPS_PAR_SECTION.values():
            toutes.update(colonnes)
        for champ in self.CHAMPS:
            self.assertNotIn(champ, toutes, champ)

    def test_les_quatre_existent_bien_sur_la_fiche(self):
        """Hors du questionnaire ne veut pas dire inexistant : ce sont des
        questions de l'APPEL."""
        from apps.crm.models import Lead
        noms = {f.name for f in Lead._meta.get_fields()
                if getattr(f, 'concrete', False)}
        for champ in self.CHAMPS:
            self.assertIn(champ, noms, champ)


class Q10_Q15_Q18_LesTroisSTATU_QUO(SimpleTestCase):
    def test_Q10_le_chauffe_eau_exige_toujours_la_PAIRE(self):
        """Le booléen seul reste INFORMATIF : sans la paire, aucune couche."""
        self.assertNotIn('chauffe_eau', CJ.composer_equipements(
            {'chauffe_eau_electrique': True}))
        self.assertNotIn('chauffe_eau', CJ.composer_equipements(
            {'chauffe_eau_electrique': True, 'chauffe_eau_kw': 2.2}))
        self.assertIn('chauffe_eau', CJ.composer_equipements(
            {'chauffe_eau_electrique': True, 'chauffe_eau_kw': 2.2,
             'chauffe_eau_creneau': 'nuit'}))

    def test_Q15_les_coupures_ne_dimensionnent_RIEN(self):
        """« Tenir pendant les coupures » est un objectif déclaré : aucune
        couche, aucun calcul de secours n'en découle."""
        from apps.crm.models import Lead
        valeurs = [v for v, _ in
                   Lead._meta.get_field('objectif_projet').choices]
        self.assertIn('secours_coupures', valeurs)
        for chemin in SOURCES_MOTEUR:
            texte = chemin.read_text(encoding='utf-8')
            self.assertNotIn('secours_coupures', texte, chemin.name)
            self.assertNotIn('objectif_projet', texte, chemin.name)

    def test_Q18_aucune_couche_de_chauffage_d_hiver(self):
        for cle in CJ.COUCHES_REDISTRIBUTION:
            self.assertNotIn('chauffage', cle)
        for chemin in SOURCES_MOTEUR:
            texte = chemin.read_text(encoding='utf-8')
            self.assertNotIn('chauffage_electrique_hiver', texte, chemin.name)

    def test_Q22_aucun_texte_ne_promet_une_subvention(self):
        contenu = MESSAGES.read_text(encoding='utf-8')
        self.assertIn('Subventions', contenu)
        self.assertIn('conditions officielles', contenu)
