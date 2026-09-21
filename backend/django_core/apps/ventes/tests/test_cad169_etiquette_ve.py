# -*- coding: utf-8 -*-
"""CAD169 — la voiture seulement PRÉVUE est comptée, et le chiffre le DIT.

Le script d'appel demande « avez-vous OU prévoyez-vous un véhicule
électrique ? », et la couche se composait dès que la réponse était oui : une
voiture pas encore achetée gonflait donc l'autoconsommation et l'économie
promise SANS que le client le sache.

DÉCISION FONDATEUR DU 21/09/2026 : elle reste comptée des deux côtés — et le
devis comme la proposition portent l'étiquette « avec votre future voiture ».
L'étiquette est OBLIGATOIRE dès que le statut vaut « prévu » : sans elle, le
chiffre ment.

CE QUE CE MODULE VERROUILLE : le moteur ÉMET l'étiquette, à UNE source
(``courbes_journalieres.ETIQUETTE_VE_PREVU``), et une voiture possédée n'en
porte aucune. Le rendu qui l'imprime la lit de là — il ne la réécrit pas.
"""
from django.test import SimpleTestCase

from apps.ventes import courbes_journalieres as CJ


def _ve(**extra):
    base = {'voiture_electrique': True, 've_km_semaine': 300}
    base.update(extra)
    return base


class UneVoitureSeulementPREVUE(SimpleTestCase):
    def test_elle_est_COMPTEE_comme_une_voiture_possedee(self):
        """Décision fondateur : comptée des DEUX côtés, pas retirée."""
        prevue = CJ.composer_equipements(_ve(ve_statut='prevu'))
        possedee = CJ.composer_equipements(_ve(ve_statut='possede'))
        self.assertIn('ve', prevue)
        self.assertEqual(prevue['ve']['kwh_jour'], possedee['ve']['kwh_jour'])
        self.assertEqual(prevue['ve']['heures'], possedee['ve']['heures'])

    def test_elle_porte_l_etiquette(self):
        couches = CJ.composer_equipements(_ve(ve_statut='prevu'))
        self.assertEqual(couches['ve']['etiquette'], CJ.ETIQUETTE_VE_PREVU)
        self.assertEqual(CJ.etiquette_ve(couches), CJ.ETIQUETTE_VE_PREVU)

    def test_l_etiquette_parle_du_FUTUR_au_client(self):
        """Le texte est validé et vit à UNE seule source."""
        self.assertEqual(CJ.ETIQUETTE_VE_PREVU, 'avec votre future voiture')

    def test_le_statut_est_publie_avec_la_couche(self):
        couches = CJ.composer_equipements(_ve(ve_statut='prevu'))
        self.assertEqual(couches['ve']['statut'], CJ.VE_STATUT_PREVU)


class UneVoitureDEJA_LA(SimpleTestCase):
    def test_elle_ne_porte_AUCUNE_etiquette(self):
        couches = CJ.composer_equipements(_ve(ve_statut='possede'))
        self.assertNotIn('etiquette', couches['ve'])
        self.assertIsNone(CJ.etiquette_ve(couches))

    def test_son_statut_reste_publie(self):
        couches = CJ.composer_equipements(_ve(ve_statut='possede'))
        self.assertEqual(couches['ve']['statut'], CJ.VE_STATUT_POSSEDE)


class QuandLaQuestionN_A_PAS_ETE_POSEE(SimpleTestCase):
    """Non-régression stricte : une fiche sans statut garde une couche
    BYTE-IDENTIQUE à celle d'avant CAD169 — aucune clé en plus."""

    def test_la_couche_est_exactement_celle_d_avant(self):
        couches = CJ.composer_equipements(_ve())
        self.assertEqual(set(couches['ve']),
                         {'kwh_jour', 'heures', 'saisons', 'mode', 'source'})

    def test_aucune_etiquette_n_est_inventee(self):
        self.assertIsNone(CJ.etiquette_ve(CJ.composer_equipements(_ve())))


class L_ETIQUETTE_N_EXISTE_PAS_SANS_COUCHE(SimpleTestCase):
    def test_sans_voiture_declaree_aucune_etiquette(self):
        couches = CJ.composer_equipements(
            {'voiture_electrique': False, 've_statut': 'prevu'})
        self.assertNotIn('ve', couches)
        self.assertIsNone(CJ.etiquette_ve(couches))

    def test_sans_kilometrage_aucune_couche_donc_aucune_etiquette(self):
        """Zéro chiffre inventé : pas de km, pas de couche."""
        couches = CJ.composer_equipements(
            {'voiture_electrique': True, 've_statut': 'prevu'})
        self.assertNotIn('ve', couches)
        self.assertIsNone(CJ.etiquette_ve(couches))

    def test_un_dict_vide_ou_None_ne_casse_rien(self):
        self.assertIsNone(CJ.etiquette_ve({}))
        self.assertIsNone(CJ.etiquette_ve(None))


class LeChampDuLeadPORTE_LA_REGLE(SimpleTestCase):
    """« Chaque champ EST le script d'appel » : la règle de l'étiquette est
    écrite dans le `help_text`, à la source."""

    def test_le_statut_dit_que_l_etiquette_est_obligatoire(self):
        from apps.crm.models import Lead
        texte = Lead._meta.get_field('equip_ve_statut').help_text
        self.assertIn('future voiture', texte)

    def test_la_question_de_suivi_precise_le_OUI_NON(self):
        """Le booléen demande « avez-vous OU prévoyez-vous » ; c'est le champ
        de STATUT qui tranche, et c'est lui qui porte la règle. Le booléen
        reste inchangé (le modifier coûterait une migration qui n'appartient
        pas à cette tâche)."""
        from apps.crm.models import Lead
        booleen = Lead._meta.get_field('equip_voiture_electrique').help_text
        self.assertIn('prévoyez-vous', booleen)
        statut = Lead._meta.get_field('equip_ve_statut').help_text
        self.assertIn('Précise le', statut)
