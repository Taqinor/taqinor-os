"""CAD168 — les deux lignes fixes de la facture ne sont jamais dites.

Toute facture porte la location du compteur et l'entretien du branchement :
ils ne sont PAS solarisables. Le calcul les porte bien des deux côtés (ils
s'annulent dans l'économie), mais l'économie présentée ne le disait pas — le
client ne retrouvait pas son chiffre sur sa facture suivante.

Ce que ces tests tiennent (Done de la tâche, moitié serveur — la question du
script est gardée par ``PanneauScriptAppel.test.jsx``) :
  1. l'étude horaire d'un devis NOMME la part non solarisable ;
  2. son montant vient du BARÈME ou du réglage société — jamais recopié dans
     un texte : le libellé ne porte aucun chiffre ;
  3. la forme historique de ``calculer_etude_horaire`` ne bouge pas.

Aucune base : le chemin devis est simulé au niveau de ses lecteurs.
"""
from unittest import mock

from django.test import SimpleTestCase

from apps.ventes import etude_horaire as EH
from apps.ventes.quote_engine import bareme


class LaPartNonSolarisableVientDuBareme(SimpleTestCase):
    def test_sans_reglage_le_montant_est_celui_des_factures_sourcees(self):
        part = EH.part_non_solarisable()
        self.assertEqual(part['montant_mad_mois'],
                         round(bareme.charges_fixes_ttc(), 2))
        self.assertEqual(part['source'], bareme.CHARGES_FIXES_SOURCE)

    def test_le_reglage_societe_remplace_les_deux_lignes_en_bloc(self):
        part = EH.part_non_solarisable(42.5)
        self.assertEqual(part['montant_mad_mois'], 42.5)
        self.assertEqual(part['source'], 'réglage société')

    def test_le_libelle_nomme_les_deux_lignes_sans_aucun_chiffre(self):
        libelle = EH.part_non_solarisable()['libelle']
        self.assertIn('Location du compteur', libelle)
        self.assertIn('entretien du branchement', libelle)
        self.assertIn('non solarisables', libelle)
        self.assertNotRegex(libelle, r'[0-9]')

    def test_le_montant_n_est_recopie_dans_aucun_texte_du_module(self):
        """Garde-fou : « 39,94 » (ou 39.94) n'apparaît nulle part en dur."""
        from pathlib import Path
        source = Path(EH.__file__).read_text(encoding='utf-8')
        self.assertNotIn('39,94', source)
        self.assertNotIn('39.94', source)


class LEtudeDuDevisNommeLaPart(SimpleTestCase):
    """Le chemin devis (``etude_horaire_pour_devis``) : ses lecteurs cross-app
    et le moteur sont simulés — on ne vérifie ici que la PART posée à côté
    de l'économie, et qu'elle suit le réglage de la société."""

    def _etude(self, charges_fixes):
        lecteurs = {
            'apps.crm.selectors.lead_bills_for_devis': {
                'facture_hiver': 600.0, 'facture_ete': None,
                'ete_differente': False},
            'apps.crm.selectors.site_location_for_devis': {
                'site_ville': 'Casablanca', 'gps_lat': None, 'gps_lng': None},
            'apps.crm.selectors.conso_mensuelle_kwh_pour_devis': None,
        }
        patches = [mock.patch(cible, return_value=valeur)
                   for cible, valeur in lecteurs.items()]
        patches += [
            mock.patch.object(EH, '_reglages_tarifaires',
                              return_value=(None, charges_fixes)),
            mock.patch.object(EH, 'profil_depuis_factures',
                              return_value=([300.0] * 12, 'factures', {})),
            mock.patch.object(EH, 'occupation_du_devis',
                              return_value=('presence_jour', 'defaut')),
            mock.patch.object(EH, 'equipements_du_devis', return_value={}),
            mock.patch.object(EH, 'capacite_batterie_du_devis',
                              return_value=None),
            mock.patch.object(EH, 'puissance_batterie_du_devis', return_value={
                'packs_decharge_kw': None, 'ond_decharge_kw': None,
                'charge_kw': None}),
            mock.patch.object(EH, 'rendement_batterie_du_devis',
                              return_value={'rendement': None, 'source': None}),
            mock.patch.object(EH, 'calculer_etude_horaire',
                              return_value={'annuel': {'economie_sans_mad': 1.0}}),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        devis = mock.Mock(company=None, etude_params={}, mode_installation='residentiel')
        return EH.etude_horaire_pour_devis(devis, kwc=5.0, data={})

    def test_l_etude_porte_la_part_non_solarisable_a_cote_de_l_economie(self):
        etude = self._etude(None)
        self.assertIn('annuel', etude)
        part = etude['part_non_solarisable']
        self.assertEqual(part, EH.part_non_solarisable())
        self.assertEqual(part['libelle'], EH.LIBELLE_PART_NON_SOLARISABLE)

    def test_la_part_suit_le_reglage_de_la_societe(self):
        etude = self._etude(55.0)
        self.assertEqual(etude['part_non_solarisable']['montant_mad_mois'], 55.0)


class LaFormeHistoriqueNeBougePas(SimpleTestCase):
    def test_calculer_etude_horaire_ne_gagne_aucune_cle(self):
        """La part est posée par le chemin devis, jamais par le moteur :
        ``CLES_RACINE_HISTORIQUES`` (test_etude_horaire) reste vrai."""
        import inspect
        source = inspect.getsource(EH.calculer_etude_horaire)
        self.assertNotIn('part_non_solarisable', source)
