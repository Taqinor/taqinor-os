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

from apps.crm.devis_auto import champs_manquants
from apps.crm.models import Lead
from apps.ventes.etude_horaire import profil_depuis_factures


def _lead_pro(**kwargs):
    return Lead(nom='Société', type_installation='commercial', **kwargs)


class LeGatingDuDevisAutomatiquePro(SimpleTestCase):
    def test_un_pro_avec_bill_kwh_SEUL_passe_le_gating(self):
        """LE test de la tâche : la donnée est là, le dossier part."""
        lead = _lead_pro(bill_kwh=Decimal('4200'))
        self.assertEqual(champs_manquants(lead), [])

    def test_un_pro_avec_la_conso_editable_passe_toujours(self):
        lead = _lead_pro(conso_mensuelle_kwh=Decimal('4200'))
        self.assertEqual(champs_manquants(lead), [])

    def test_un_pro_SANS_aucune_des_deux_reste_bloque(self):
        """Non-régression : on n'ouvre pas la porte à un dossier vide."""
        self.assertEqual(champs_manquants(_lead_pro()),
                         ['consommation mensuelle (kWh)'])

    def test_le_meme_repli_vaut_pour_l_industriel(self):
        lead = Lead(nom='Usine', type_installation='industriel',
                    bill_kwh=Decimal('90000'))
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
        self.assertEqual(
            champs_manquants(lead), ['pompe (CV)', 'HMT', 'débit souhaité'])


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
