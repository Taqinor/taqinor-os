"""CAD166 — le pro qui donne ses kWh sur le site n'est plus « incomplet ».

DEUX DÉFAUTS, UN MÊME GESTE.

1. **Le gating.** Le tunnel PROFESSIONNEL du site n'écrit que ``bill_kwh``
   (archive web, lecture seule) ; le gating du devis automatique, lui,
   n'interrogeait que ``conso_mensuelle_kwh`` (le champ ÉDITABLE, saisi par la
   commerciale ou écrit par l'OCR). Résultat : « Manque : consommation
   mensuelle (kWh) » sur un dossier dont la donnée était DÉJÀ là. Les deux
   champs ne fusionnent pas — chacun garde son rôle — mais l'un vaut l'autre
   pour décider si le devis peut partir.

2. **La priorité de la consommation.** Décision fondateur du 21/09/2026
   (Q14) : les kWh SAISIS passent en priorité 1 dans
   ``profil_depuis_factures`` ; les montants en dirhams inversés au barème ne
   servent que s'ils sont absents. Le moteur savait déjà lire des kWh — il ne
   les recevait simplement pas de la fiche.

Aucune base : le gating et la résolution de profil sont des fonctions pures.
"""
from decimal import Decimal

from django.test import SimpleTestCase

from apps.crm.devis_auto import (
    _rythme_ci, champs_manquants, champs_manquants_detail, champs_requis)
from apps.crm.devis_selectors import entrees_ci_du_lead
from apps.crm.models import Lead
from apps.ventes.horaire.conso import profil_depuis_factures


def _lead_pro(**kwargs):
    return Lead(nom='Société', type_installation='commercial', **kwargs)


# ALEA47 (D-ACI-5=a) — « prêt » = tout ce que le moteur C&I exige : un pro
# complet = sa conso + son contrat BT + une activité à archétype (bureau).
_PRO_COMPLET = {'contrat_electricite': 'bt_patente',
                'categorie_commerciale': 'bureau',
                # ADEV89 — + la phase du site (combinaison d'onduleurs).
                'raccordement': 'triphase'}
LIB_CONTRAT = "Contrat d'électricité"
LIB_PHASE = 'Phase du site (monophasé ou triphasé)'
LIB_RYTHME = "Jours et heures d'ouverture (ou catégorie d'activité)"


class LeGatingDuDevisAutomatiquePro(SimpleTestCase):
    def test_un_pro_avec_bill_kwh_SEUL_passe_le_gating(self):
        """LE test de la tâche : la donnée est là, le dossier part (ALEA47 :
        avec le contrat et l'activité que le moteur exige aussi)."""
        lead = _lead_pro(bill_kwh=Decimal('4200'), **_PRO_COMPLET)
        self.assertEqual(champs_manquants(lead), [])

    def test_un_pro_avec_la_conso_editable_passe_toujours(self):
        lead = _lead_pro(conso_mensuelle_kwh=Decimal('4200'), **_PRO_COMPLET)
        self.assertEqual(champs_manquants(lead), [])

    def test_un_pro_SANS_aucune_des_deux_reste_bloque(self):
        """Non-régression : on n'ouvre pas la porte à un dossier vide."""
        # CIQ404 — libellé du groupe pro (contrat CIQ1).
        self.assertEqual(champs_manquants(_lead_pro(**_PRO_COMPLET)),
                         ['Consommation (kWh) ou facture mensuelle (MAD)'])

    def test_le_meme_repli_vaut_pour_l_industriel(self):
        """``bill_kwh`` remplit le groupe conso de l'industriel (le rythme,
        lui, reste exigé : aucun archétype industriel)."""
        lead = Lead(nom='Usine', type_installation='industriel',
                    bill_kwh=Decimal('90000'), contrat_electricite='bt_patente',
                    regime_equipes='3x8', jours_ouverture=[1, 2, 3, 4, 5, 6, 7],
                    raccordement='triphase')
        self.assertEqual(champs_manquants(lead), [])

    def test_le_residentiel_n_est_PAS_touche(self):
        """Non-régression : le résidentiel reste gaté sur sa facture d'hiver,
        `bill_kwh` ne la remplace pas."""
        lead = Lead(nom='Prospect', type_installation='residentiel',
                    bill_kwh=Decimal('300'))
        self.assertEqual(champs_manquants(lead), ['facture hiver'])

    def test_l_agricole_n_est_PAS_touche(self):
        lead = Lead(nom='Ferme', type_installation='agricole',
                    bill_kwh=Decimal('300'))
        # AGR403 — groupes hydrauliques agricoles ; `bill_kwh` n'y entre pas.
        self.assertEqual(
            [e['champ'] for e in champs_manquants_detail(lead)],
            ['pompe_hmt_m', 'pompe_debit_m3h'])


class PretEgaleCeQueLeMoteurExigeALEA47(SimpleTestCase):
    """ALEA47 (D-ACI-5=a, constat C-ACI-001) — la carte lead ne dit « devis
    automatique prêt » que si le moteur C&I peut chiffrer : contrat BT +
    rythme (ou catégorie à archétype), par la règle partagée du moteur."""

    def test_lead_1637_conso_seule_pas_pret_contrat_et_rythme_nommes(self):
        lead = _lead_pro(conso_mensuelle_kwh=Decimal('10000'))
        self.assertEqual(champs_manquants(lead),
                         [LIB_CONTRAT, LIB_PHASE, LIB_RYTHME])
        self.assertEqual(
            [e['champ'] for e in champs_manquants_detail(lead)],
            ['contrat_electricite', 'raccordement', 'jours_ouverture'])
        self.assertEqual(champs_requis(lead)[1:], [
            ['contrat_electricite'], ['raccordement'], ['jours_ouverture'],
            ['heure_debut', 'regime_equipes']])

    def test_phase_inconnue_pas_prete(self):
        # ADEV89 — « je ne sais pas » n'est pas une phase : le devis
        # automatique attend (un hôtel triphasé sortait en onduleurs mono).
        lead = _lead_pro(conso_mensuelle_kwh=Decimal('10000'),
                         **dict(_PRO_COMPLET, raccordement='inconnu'))
        self.assertEqual(champs_manquants(lead), [LIB_PHASE])
        lead.raccordement = 'monophase'
        self.assertEqual(champs_manquants(lead), [])

    def test_bureau_et_bt_patente_pret(self):
        lead = _lead_pro(conso_mensuelle_kwh=Decimal('10000'), **_PRO_COMPLET)
        self.assertEqual(champs_manquants_detail(lead), [])

    def test_categorie_autre_et_contrat_heures_manquantes(self):
        lead = _lead_pro(conso_mensuelle_kwh=Decimal('10000'),
                         categorie_commerciale='autre',
                         contrat_electricite='bt_patente',
                         raccordement='triphase')
        self.assertIn(['heure_debut', 'regime_equipes'], champs_requis(lead))
        self.assertEqual(champs_manquants(lead), [LIB_RYTHME])
        lead.jours_ouverture = [1, 2, 3, 4, 5]
        self.assertEqual([e['champ'] for e in champs_manquants_detail(lead)],
                         ['heure_debut'])
        lead.heure_debut, lead.heure_fin = 8, 18
        self.assertEqual(champs_manquants(lead), [])

    def test_industriel_conso_et_contrat_sans_rythme_pas_pret(self):
        lead = Lead(nom='Usine', type_installation='industriel',
                    conso_mensuelle_kwh=Decimal('20000'),
                    contrat_electricite='bt_force_motrice',
                    raccordement='triphase')
        self.assertEqual(champs_manquants(lead), [LIB_RYTHME])
        # Un 1x8 sans heure de début ne place aucune plage (règle moteur).
        lead.jours_ouverture, lead.regime_equipes = [1, 2, 3, 4, 5], '1x8'
        self.assertEqual([e['champ'] for e in champs_manquants_detail(lead)],
                         ['heure_debut'])
        lead.heure_debut = 7
        self.assertEqual(champs_manquants(lead), [])

    def test_mt_declaree_sans_contrat_aucun_groupe_contrat(self):
        lead = Lead(nom='Usine', type_installation='industriel',
                    tension_raccordement='mt', tension_source='declare',
                    conso_mensuelle_kwh=Decimal('20000'))
        self.assertNotIn(['contrat_electricite'], champs_requis(lead))
        # Tension inconnue / défaut visible du site : le contrat est exigé.
        lead.tension_source = 'site_defaut_visible'
        self.assertIn(['contrat_electricite'], champs_requis(lead))

    def test_ne_sait_pas_n_est_pas_un_contrat(self):
        lead = _lead_pro(conso_mensuelle_kwh=Decimal('10000'),
                         categorie_commerciale='bureau',
                         contrat_electricite='ne_sait_pas',
                         raccordement='triphase')
        self.assertEqual(champs_manquants(lead), [LIB_CONTRAT])

    def test_facture_mad_ne_compte_qu_avec_un_contrat_bt(self):
        lead = _lead_pro(tension_raccordement='bt', tension_source='declare',
                         facture_hiver=Decimal('25000'),
                         categorie_commerciale='bureau',
                         raccordement='triphase')
        self.assertEqual(
            champs_manquants(lead),
            ['Consommation (kWh) ou facture mensuelle (MAD)', LIB_CONTRAT])
        lead.contrat_electricite = 'mt_general'
        self.assertIn('Consommation (kWh) ou facture mensuelle (MAD)',
                      champs_manquants(lead))
        lead.contrat_electricite = 'bt_patente'
        self.assertEqual(champs_manquants(lead), [])

    def test_le_rythme_lu_est_celui_que_lit_le_moteur(self):
        """Jumeau : :func:`_rythme_ci` = les entrées ``rythme.*`` que
        ``entrees_ci_du_lead`` sert au moteur (hors fermetures / secteur)."""
        lus = ('jours_ouverts', 'plages', 'debut_equipe_h', 'equipes',
               'categorie_commerciale', 'reponses_categorie')
        for kw in ({}, {'jours_ouverture': [1, 6], 'heure_debut': 8,
                        'heure_fin': 17, 'categorie_commerciale': 'autre'},
                   {'heure_debut': 6, 'regime_equipes': '2x8'},
                   {'categorie_commerciale': 'hotel',
                    'reponses_categorie': {'chambres': 40}}):
            for mode in ('commercial', 'industriel'):
                lead = Lead(nom='x', type_installation=mode, **kw)
                attendu = {e['chemin'].split('.', 1)[1]: e['valeur']
                           for e in entrees_ci_du_lead(lead)['entrees']
                           if e['chemin'].startswith('rythme.')
                           and e['chemin'].split('.', 1)[1] in lus}
                self.assertEqual(_rythme_ci(lead), attendu, (mode, kw))


class LesKwhSaisisPriment(SimpleTestCase):
    """Q14 — les kWh déclarés d'abord, les dirhams inversés ensuite."""

    def test_une_conso_mensuelle_declaree_prime_sur_la_facture(self):
        serie, source, detail = profil_depuis_factures(
            facture_hiver_mad=1200.0,
            conso_kwh_mensuelle_unique=830.0)
        self.assertEqual(serie, [830.0] * 12)
        self.assertEqual(source, 'kwh_mensuel_saisi')
        self.assertEqual(detail['methode'], 'saisie_directe_mois_unique')

    def test_les_douze_kwh_mesures_priment_sur_la_conso_unique(self):
        """L'ordre interne ne change pas : douze valeurs réelles portent une
        VRAIE variation mensuelle, une seule valeur n'en porte aucune."""
        douze = [700.0] * 11 + [900.0]
        serie, source, _ = profil_depuis_factures(
            conso_kwh_mensuelles=douze, conso_kwh_mensuelle_unique=830.0)
        self.assertEqual(serie, douze)
        self.assertEqual(source, 'kwh_mensuels_saisis')

    def test_sans_kwh_declares_la_facture_reprend_la_main(self):
        """Non-régression : le chemin d'inversion au barème est intact."""
        serie, source, _ = profil_depuis_factures(facture_hiver_mad=1200.0)
        self.assertTrue(serie)
        self.assertEqual(source, 'facture_hiver')

    def test_une_conso_nulle_ou_absente_n_est_pas_une_reponse(self):
        """Zéro chiffre inventé : 0 et None ne fabriquent aucune série."""
        for valeur in (None, 0, 0.0, '', 'abc'):
            serie, source, _ = profil_depuis_factures(
                conso_kwh_mensuelle_unique=valeur)
            self.assertIsNone(serie, repr(valeur))
            self.assertEqual(source, 'absente', repr(valeur))
