"""Décision fondateur 08/10/2026 — « nouveaux rendus seulement ».

Un devis déjà envoyé (``regles_calcul = 1`` posé par la migration 0138) reste
rendu avec les règles d'origine ; un devis neuf naît aux règles corrigées.
"""
import importlib
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase

from apps.ventes.domain.regles_calcul import (
    REGLES_ARRONDI_3010, REGLES_CENTAINE_0311, REGLES_CONSO_PUBLIQUE_0111, REGLES_CORRIGEES,
    REGLES_CORRIGEES_2710, REGLES_COURANTES, REGLES_CYCLES_BATTERIE_1911, REGLES_ECARTS_0111,
    REGLES_ECARTS_0411, REGLES_ECARTS_3110, REGLES_ORIGINE,
    REGLES_PANIER_UNIQUE_0211, REGLES_RETOURS_3010B, REGLES_SENSIBILITES_1911, REGLES_SENSIBILITES_3010,
    REGLES_POSE_REELLE_2111, calcul_corrige, regles_au_moins)


class ReglesCalculTests(SimpleTestCase):
    def test_devis_envoye_garde_les_regles_d_origine(self):
        self.assertFalse(calcul_corrige(SimpleNamespace(regles_calcul=REGLES_ORIGINE)))

    def test_devis_neuf_aux_regles_corrigees(self):
        self.assertTrue(calcul_corrige(SimpleNamespace(regles_calcul=REGLES_CORRIGEES)))

    def test_doublure_sans_champ_suit_les_regles_corrigees(self):
        self.assertTrue(calcul_corrige(SimpleNamespace()))

    def test_defaut_du_modele_est_corrige(self):
        from apps.ventes.models import Devis
        defaut = Devis._meta.get_field('regles_calcul').default
        self.assertEqual(defaut, REGLES_COURANTES)
        self.assertEqual(REGLES_COURANTES, REGLES_SENSIBILITES_1911)
        self.assertEqual(REGLES_SENSIBILITES_1911, 14)
        self.assertEqual(REGLES_CYCLES_BATTERIE_1911, 13)
        self.assertEqual(REGLES_ECARTS_0411, 12)
        self.assertGreater(REGLES_ECARTS_0411, REGLES_CENTAINE_0311)
        self.assertGreater(REGLES_CENTAINE_0311, REGLES_PANIER_UNIQUE_0211)
        self.assertGreater(REGLES_PANIER_UNIQUE_0211, REGLES_ECARTS_0111)
        self.assertGreater(REGLES_ECARTS_0111, REGLES_CONSO_PUBLIQUE_0111)
        self.assertGreater(REGLES_CONSO_PUBLIQUE_0111, REGLES_ECARTS_3110)
        self.assertGreater(REGLES_ECARTS_3110, REGLES_ARRONDI_3010)
        self.assertGreater(REGLES_ARRONDI_3010, REGLES_RETOURS_3010B)
        self.assertGreater(REGLES_RETOURS_3010B, REGLES_SENSIBILITES_3010)
        self.assertGreater(REGLES_CYCLES_BATTERIE_1911, REGLES_ECARTS_0411)
        self.assertGreater(REGLES_SENSIBILITES_1911, REGLES_CYCLES_BATTERIE_1911)
        self.assertTrue(calcul_corrige(SimpleNamespace(regles_calcul=defaut)))

    def test_niveau_15_declare_non_courant(self):
        # ACAL998 — le niveau 15 existe mais n'est pas courant tant
        # qu'ACAL1001 ne l'a pas activé : aucun devis, neuf ou existant.
        from apps.ventes.models import Devis
        self.assertEqual(REGLES_POSE_REELLE_2111, 15)
        self.assertEqual(REGLES_COURANTES, 14)
        self.assertEqual(Devis._meta.get_field('regles_calcul').default, 14)
        for devis in (Devis(), SimpleNamespace(regles_calcul=14), None,
                      SimpleNamespace()):
            self.assertFalse(regles_au_moins(devis, REGLES_POSE_REELLE_2111))
        self.assertTrue(regles_au_moins(
            SimpleNamespace(regles_calcul=15), REGLES_POSE_REELLE_2111))

    def test_niveau_16_haute_tension_nouveaux_devis_seulement(self):
        # HT24 (fondateur 24/11/2026) — l'option « avec batterie » haute
        # tension : niveau 16 déclaré (il suit le 15, pas courant) ; seul un
        # devis ENVOYÉ avant le 25/11/2026 garde l'option qu'il a reçue.
        from datetime import datetime, timezone

        from apps.ventes.domain.regles_calcul import (
            REGLES_HYBRIDES_HT_2411, hybrides_ht_ouverts)
        self.assertEqual(REGLES_HYBRIDES_HT_2411, 16)
        self.assertGreater(REGLES_HYBRIDES_HT_2411, REGLES_POSE_REELLE_2111)
        avant = datetime(2026, 11, 24, 23, 0, tzinfo=timezone.utc)
        apres = datetime(2026, 11, 25, 8, 0, tzinfo=timezone.utc)

        def devis(**champs):
            return SimpleNamespace(**dict({'regles_calcul': 14, 'date_creation': avant}, **champs))
        # Envoyé (ou sorti du brouillon sans envoi) avant la coupure : fermé.
        self.assertFalse(hybrides_ht_ouverts(devis(statut='envoye', date_envoi=avant)))
        self.assertFalse(hybrides_ht_ouverts(devis(statut='accepte', date_envoi=None)))
        # Brouillon jamais envoyé, même créé avant : rien n'a été montré, ouvert.
        self.assertTrue(hybrides_ht_ouverts(devis(statut='brouillon', date_envoi=None)))
        # Le même devis, envoyé après la coupure : le client l'a reçu avec, ouvert.
        self.assertTrue(hybrides_ht_ouverts(devis(statut='envoye', date_envoi=apres)))
        self.assertTrue(hybrides_ht_ouverts(devis(statut='accepte', date_envoi=None, date_creation=apres)))
        self.assertTrue(hybrides_ht_ouverts(devis(regles_calcul=16, statut='envoye', date_envoi=avant)))
        for apercu in (None, SimpleNamespace()):
            self.assertTrue(hybrides_ht_ouverts(apercu))

    def test_d_acal_102_phrases_profil_nouveaux_rendus(self):
        # D-ACAL-102 (fondateur 25/11/2026 « Live now ») — les deux phrases
        # corrigées du PDF C&I (T4-U2-019 / T4-U2-020) : nouveaux rendus
        # seulement, sans rendre le niveau 15 courant.
        from datetime import datetime, timezone

        from apps.ventes.domain.regles_calcul import (
            COUPURE_PHRASES_PROFIL, drapeaux_phrases_profil, phrases_profil_ouvertes)
        self.assertEqual(COUPURE_PHRASES_PROFIL, (2026, 11, 26))
        self.assertEqual(REGLES_COURANTES, REGLES_SENSIBILITES_1911)
        avant = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
        apres = datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc)

        def devis(**champs):
            return SimpleNamespace(**dict({'regles_calcul': 14, 'date_creation': avant,
                                           'mode_installation': 'industriel'}, **champs))
        self.assertTrue(phrases_profil_ouvertes(devis(statut='brouillon', date_envoi=None)))
        self.assertFalse(phrases_profil_ouvertes(devis(statut='envoye', date_envoi=avant)))
        self.assertTrue(phrases_profil_ouvertes(devis(statut='envoye', date_envoi=apres)))
        self.assertTrue(phrases_profil_ouvertes(devis(regles_calcul=15, statut='envoye', date_envoi=avant)))
        for apercu in (None, SimpleNamespace()):
            self.assertTrue(phrases_profil_ouvertes(apercu))
        # Le drapeau de rendu marque le cas OUVERT (le rendu change : l'empreinte
        # des données bouge) ; un devis qui garde son rendu (envoyé avant la
        # coupure, autre marché) n'en reçoit aucun : charge utile inchangée.
        for ouvert in (devis(statut='brouillon', date_envoi=None),
                       devis(statut='envoye', date_envoi=apres)):
            self.assertEqual(drapeaux_phrases_profil(ouvert), {'phrases_profil_ouvertes': True})
        for ferme in (devis(statut='envoye', date_envoi=avant),
                      devis(statut='brouillon', date_envoi=None, mode_installation='residentiel')):
            self.assertEqual(drapeaux_phrases_profil(ferme), {})
        from apps.ventes.quote_engine.builder import _avec_regles_pose_reelle
        self.assertEqual(_avec_regles_pose_reelle({}, False, devis(statut='brouillon', date_envoi=None)),
                         {'phrases_profil_ouvertes': True, 'phrases_pdf_2611': True})
        self.assertEqual(_avec_regles_pose_reelle({}, False, devis(statut='envoye', date_envoi=avant)), {})
        self.assertEqual(_avec_regles_pose_reelle({}, True, None),
                         {'regles_pose_reelle': True, 'phrases_pdf_2511': True,
                          'phrases_pdf_2611': True})

    def test_d_acal_111_114_une_coupure_un_predicat_cas_ouvert(self):
        from datetime import datetime, timezone

        from apps.ventes.domain.regles_calcul import (
            COUPURE_PDF_2511, drapeaux_nouveaux_rendus, drapeaux_pdf_2511,
            phrases_pdf_2511_ouvertes)
        self.assertEqual(COUPURE_PDF_2511, (2026, 11, 26))
        avant = datetime(2026, 11, 20, 9, 0, tzinfo=timezone.utc)
        apres = datetime(2026, 11, 26, 8, 0, tzinfo=timezone.utc)

        def devis(mode='residentiel', **champs):
            return SimpleNamespace(**dict({'regles_calcul': 14, 'date_creation': avant,
                                           'mode_installation': mode}, **champs))
        for mode in ('residentiel', '', 'agricole'):
            self.assertEqual(drapeaux_pdf_2511(devis(mode, statut='brouillon', date_envoi=None)),
                             {'phrases_pdf_2511': True})
            self.assertEqual(drapeaux_pdf_2511(devis(mode, statut='envoye', date_envoi=apres)),
                             {'phrases_pdf_2511': True})
            self.assertEqual(drapeaux_pdf_2511(devis(mode, statut='envoye', date_envoi=avant)), {})
        for mode in ('commercial', 'industriel'):
            self.assertEqual(drapeaux_pdf_2511(devis(mode, statut='brouillon', date_envoi=None)), {})
        self.assertFalse(phrases_pdf_2511_ouvertes(devis(statut='accepte', date_envoi=avant)))
        self.assertEqual(drapeaux_nouveaux_rendus(devis('industriel', statut='brouillon', date_envoi=None)),
                         {'phrases_profil_ouvertes': True, 'phrases_pdf_2611': True})

    def test_lot_8_une_coupure_un_drapeau_marches_dont_le_pdf_change(self):
        # Lot 8 (D-AMOT-9, fondateur 26/11/2026) — nouveaux rendus seulement.
        from datetime import datetime, time, timedelta, timezone

        from apps.ventes.domain.regles_calcul import (
            COUPURE_PDF_2611, COUPURE_TOIT_PLAT, drapeaux_nouveaux_rendus, drapeaux_pdf_2611)
        self.assertEqual(COUPURE_PDF_2611, COUPURE_TOIT_PLAT)
        coupure = datetime.combine(datetime(*COUPURE_PDF_2611), time(8), tzinfo=timezone.utc)
        avant = coupure - timedelta(days=2)

        def devis(mode='residentiel', **champs):
            return SimpleNamespace(**dict({'regles_calcul': 14, 'date_creation': avant,
                                           'mode_installation': mode}, **champs))
        for mode in ('residentiel', '', 'industriel'):
            for ouvert in (devis(mode, statut='brouillon', date_envoi=None),
                           devis(mode, statut='envoye', date_envoi=coupure)):
                self.assertEqual(drapeaux_pdf_2611(ouvert), {'phrases_pdf_2611': True})
            self.assertEqual(drapeaux_pdf_2611(devis(mode, statut='envoye', date_envoi=avant)), {})
        for mode in ('commercial', 'agricole'):
            self.assertEqual(drapeaux_pdf_2611(devis(mode, statut='brouillon', date_envoi=None)), {})
        self.assertIn('phrases_pdf_2611', drapeaux_nouveaux_rendus(devis(statut='brouillon', date_envoi=None)))

    def test_lecteurs_aval_role_fiche_nouveaux_rendus_seulement(self):
        # Lecteurs en aval (fondateur 24/11/2026) — la classe d'une ligne par le
        # rôle et la fiche du produit : même littéral que la coupure du toit plat.
        from datetime import datetime, time, timedelta, timezone

        from apps.ventes.domain.regles_calcul import (
            COUPURE_CLASSE_PAR_ROLE, COUPURE_TOIT_PLAT, classe_par_role_ouverte)
        self.assertEqual(COUPURE_CLASSE_PAR_ROLE, COUPURE_TOIT_PLAT)
        coupure = datetime.combine(datetime(*COUPURE_CLASSE_PAR_ROLE), time(8), tzinfo=timezone.utc)
        avant = coupure - timedelta(days=1)

        def devis(**champs):
            return SimpleNamespace(**dict({'regles_calcul': 14, 'date_creation': avant}, **champs))
        self.assertTrue(classe_par_role_ouverte(None))
        self.assertTrue(classe_par_role_ouverte(devis(statut='brouillon', date_envoi=None)))
        self.assertTrue(classe_par_role_ouverte(devis(statut='envoye', date_envoi=coupure)))
        self.assertFalse(classe_par_role_ouverte(devis(statut='envoye', date_envoi=avant)))
        self.assertFalse(classe_par_role_ouverte(devis(statut='accepte', date_envoi=avant)))

    def test_t4_u1_009_rib_sous_echeancier_nouveaux_rendus_seulement(self):
        # T4-U1-009 / T4-X7-020 — « Devis final » commercial / industriel /
        # agricole : le RIB du profil sous l'échéancier, même coupure que les
        # corrections du 26/11 ; un devis envoyé avant n'a pas la clé.
        from datetime import datetime, time, timedelta, timezone

        from apps.ventes.domain.regles_calcul import COUPURE_PDF_2611
        from apps.ventes.quote_engine.builder import _avec_regles_pose_reelle
        from apps.ventes.quote_engine.rib_devis_final import CLE, drapeau_rib, drapeaux_rendu
        coupure = datetime.combine(datetime(*COUPURE_PDF_2611), time(8), tzinfo=timezone.utc)
        avant = coupure - timedelta(days=2)
        profil = {'nom': 'SOCIETE 43 SARL', 'ice': '1', 'rib': '011 780 0000000000000000 12', 'banque': 'Banque X'}
        data = {'devis_final': True, 'pdf_mode': 'full', 'entreprise': profil}

        def devis(mode, **champs):
            return SimpleNamespace(**dict({'regles_calcul': 14, 'date_creation': avant,
                                           'mode_installation': mode}, **champs))
        for mode in ('commercial', 'industriel', 'agricole', 'Agricole'):
            for ouvert in (devis(mode, statut='brouillon', date_envoi=None),
                           devis(mode, statut='envoye', date_envoi=coupure)):
                self.assertEqual(drapeau_rib(ouvert, data), {CLE: True})
            ferme = devis(mode, statut='envoye', date_envoi=avant)
            self.assertEqual(drapeau_rib(ferme, data), {})
            # La charge utile d'un devis envoyé avant : clé ABSENTE (jamais False).
            self.assertNotIn(CLE, drapeaux_rendu(ferme, data))
            self.assertNotIn(CLE, _avec_regles_pose_reelle(dict(data), False, ferme))
        ouvert = devis('commercial', statut='brouillon', date_envoi=None)
        self.assertIn(CLE, _avec_regles_pose_reelle(dict(data), False, ouvert))
        # Résidentiel (sa page 3 imprime déjà la ligne), une-page, sans « Devis
        # final », profil sans RIB ni banque : aucune clé.
        self.assertEqual(drapeau_rib(devis('residentiel', statut='brouillon', date_envoi=None), data), {})
        for autre in (dict(data, pdf_mode='onepage'), dict(data, devis_final=False),
                      dict(data, entreprise=dict(profil, rib='', banque=' ')), dict(data, entreprise={})):
            self.assertEqual(drapeau_rib(ouvert, autre), {})

    def test_t4_u1_009_rib_imprime_du_profil_seul_sous_l_echeancier(self):
        # Clé absente : les deux échéanciers sont rendus octet pour octet comme
        # avant, même avec un RIB au profil. Clé posée : la ligne du profil.
        from apps.ventes.quote_engine.agricole.pages import _echeancier
        from apps.ventes.quote_engine.ci.blocs import bloc_echeancier
        from apps.ventes.quote_engine.rib_devis_final import CLE
        profil = {'nom': 'SOCIETE 43 SARL', 'ice': '1', 'rib': '011 780 0000000000000000 12', 'banque': 'Banque X'}
        synthese = {'echeancier': [{'cle': 'commande', 'libelle': 'Commande', 'pct': 30, 'montant_ttc': 3000},
                                   {'cle': 'reception', 'libelle': 'Réception', 'pct': 70, 'montant_ttc': 7000}]}
        agricole = {'payment_terms': {'acompte': 30, 'materiel': 60, 'solde': 10}}
        ci_avant = bloc_echeancier(synthese, 'c3', doc={})
        agri_avant = _echeancier(dict(agricole), 'fr')
        self.assertEqual(bloc_echeancier(synthese, 'c3', doc={'entreprise': profil}), ci_avant)
        self.assertEqual(_echeancier(dict(agricole, entreprise=profil), 'fr'), agri_avant)
        self.assertNotIn('Virement', ci_avant + agri_avant)
        for rendu in (bloc_echeancier(synthese, 'c3', doc={'entreprise': profil, CLE: True}),
                      _echeancier(dict(agricole, entreprise=profil, **{CLE: True}), 'fr')):
            self.assertIn('Virement bancaire&nbsp;:', rendu)
            self.assertIn('<b>SOCIETE 43 SARL</b> · Banque X · RIB 011 780 0000000000000000 12', rendu)
            self.assertNotIn('0002720029379418', rendu)  # jamais le RIB historique
        # Agricole : le RIB vient APRÈS la note « acompte après l'accord FDA », sous tout l'échéancier.
        from apps.ventes.quote_engine.agricole.pages import _t
        agri = _echeancier(dict(agricole, entreprise=profil, **{CLE: True}), 'fr')
        self.assertLess(agri.index(_t('fr', 'agr_acompte_apres_fda')), agri.index('ag-ech-rib'))
        # Clé posée mais profil vidé depuis : rien (jamais « RIB à communiquer »).
        vide = dict(profil, rib='', banque='')
        self.assertEqual(bloc_echeancier(synthese, 'c3', doc={'entreprise': vide, CLE: True}), ci_avant)
        self.assertEqual(_echeancier(dict(agricole, entreprise=vide, **{CLE: True}), 'fr'), agri_avant)
        self.assertEqual(bloc_echeancier({}, 'c3', doc={'entreprise': profil, CLE: True}), '')

    def test_t4_v2_010_protection_marche_a_sec_prouvee_par_la_fiche(self):
        # T4-V2-010 — le PDF n'imprime « protection marche à sec » sur la ligne
        # du variateur que si sa fiche la publie ; nouveaux rendus seulement.
        from datetime import datetime, timedelta, timezone

        from apps.ventes.domain.regles_calcul import (
            COUPURE_PROTECTION_FICHE, protection_fiche_ouverte)
        from apps.ventes.quote_engine.lignes_classement import _item_du_devis
        # La garde : la date bouge avec le déploiement (le lendemain), et SEUL
        # ce littéral bouge avec elle ; ``avant`` / ``apres`` en dérivent.
        self.assertEqual(COUPURE_PROTECTION_FICHE, (2026, 11, 28))
        apres = datetime(*COUPURE_PROTECTION_FICHE, 8, 0, tzinfo=timezone.utc)
        avant = apres - timedelta(days=1)
        desc = ('Variateur solaire dédié pompage : MPPT intégré, entrée PV directe\n'
                'Pilotage automatique lever/coucher du soleil, protection marche à sec\n'
                'Compatible pompes AC triphasées/monophasées standards')

        def ligne(protection, role='variateur_pompage'):
            fiche = SimpleNamespace(type_fiche='variateur_pompage',
                                    var_protection_marche_a_sec=protection)
            produit = SimpleNamespace(pk=7, nom='VARIATEUR VEICHI SI23 4KW 380V', marque='VEICHI',
                                      description=desc, garantie='', role_pompage=role,
                                      fiche_technique=fiche)
            return SimpleNamespace(designation=produit.nom, produit=produit, quantite=1,
                                   prix_unitaire=Decimal('2291.67'), remise=0, taux_tva=20)

        def devis(**champs):
            return SimpleNamespace(**dict({'regles_calcul': 14, 'date_creation': avant,
                                           'mode_installation': 'agricole', 'reglages_figes': None},
                                          **champs))
        ouvert = devis(statut='brouillon', date_envoi=None)
        ferme = devis(statut='envoye', date_envoi=avant)
        self.assertTrue(protection_fiche_ouverte(ouvert))
        self.assertTrue(protection_fiche_ouverte(devis(statut='envoye', date_envoi=apres)))
        self.assertFalse(protection_fiche_ouverte(ferme))
        # Fiche muette (None) ou négative (False) : l'affirmation disparaît, le
        # reste de la ligne demeure.
        for protection in (None, False):
            texte = _item_du_devis(ligne(protection), Decimal('20'), ouvert)['description']
            self.assertNotIn('marche à sec', texte)
            self.assertIn('Pilotage automatique lever/coucher du soleil\n', texte)
            self.assertIn('Compatible pompes AC', texte)
        # Fiche qui la publie : la phrase reste.
        self.assertEqual(_item_du_devis(ligne(True), Decimal('20'), ouvert)['description'], desc)
        # Devis envoyé avant la coupure : l'item reste celui que le client a reçu.
        self.assertEqual(_item_du_devis(ligne(None), Decimal('20'), ferme)['description'], desc)
        # Un autre produit (sonde de niveau, sans fiche de variateur) garde son texte.
        sonde = ligne(None, role='sonde_niveau')
        sonde.produit.fiche_technique = None
        self.assertEqual(_item_du_devis(sonde, Decimal('20'), ouvert)['description'], desc)

    def test_t4_v2_010_retrait_toujours_grammatical(self):
        # Revue du 26/11 — d'autres tournures que celle des VEICHI : jamais de
        # parenthèses vides, de séparateur orphelin ni de double espace ; un
        # produit qui n'est pas un variateur n'est jamais touché.
        from apps.ventes.quote_engine.lignes_classement import _description_prouvee
        variateur = SimpleNamespace(role_pompage='variateur_pompage', fiche_technique=None)
        autre = SimpleNamespace(role_pompage='sonde_niveau', fiche_technique=None)
        cas = {
            'Relais de niveau (protection marche à sec / cuve pleine)': 'Relais de niveau (cuve pleine)',
            'Protection marche à sec, pilotage automatique': 'Pilotage automatique',
            'Relais (protection marche à sec)': 'Relais',
            'MPPT intégré – protection contre la marche à sec': 'MPPT intégré',
            'Pilotage automatique lever/coucher du soleil, protection marche à sec':
                'Pilotage automatique lever/coucher du soleil',
            'Arrêt sur défaut, protection marche à sec, redémarrage auto': 'Arrêt sur défaut, redémarrage auto',
        }
        for avant, attendu in cas.items():
            with self.subTest(avant=avant):
                self.assertEqual(_description_prouvee(avant, variateur, None), attendu)
                self.assertEqual(_description_prouvee(avant, autre, None), avant)
                self.assertEqual(_description_prouvee(avant, variateur, True), avant)
        # Une ligne sans la clause revient à l'octet, une ligne vidée disparaît.
        self.assertEqual(_description_prouvee('A  ,  b\nprotection marche à sec', variateur, None), 'A  ,  b')

    def test_t4_v2_010_la_preuve_est_figee_a_l_envoi(self):
        # Revue du 26/11 — la description est figée à l'envoi ; la PREUVE de la
        # protection aussi (``envoi.figer_reglages_rendu``) : un devis envoyé
        # garde la ligne que son client a reçue quand la fiche change ensuite.
        from datetime import datetime, timedelta, timezone

        from apps.ventes.domain.regles_calcul import COUPURE_PROTECTION_FICHE
        from apps.ventes.quote_engine.lignes_classement import _item_du_devis
        apres = datetime(*COUPURE_PROTECTION_FICHE, 8, 0, tzinfo=timezone.utc)
        avant = apres - timedelta(days=1)
        desc = 'Pilotage automatique lever/coucher du soleil, protection marche à sec'

        def ligne(protection_du_jour):
            fiche = SimpleNamespace(type_fiche='variateur_pompage',
                                    var_protection_marche_a_sec=protection_du_jour)
            produit = SimpleNamespace(pk=7, nom='VEICHI SI23', marque='VEICHI', description=desc,
                                      garantie='', role_pompage='variateur_pompage', fiche_technique=fiche)
            return SimpleNamespace(designation=produit.nom, produit=produit, quantite=1,
                                   prix_unitaire=Decimal('1'), remise=0, taux_tva=20)

        def envoye(date_envoi, **fige):
            produit = dict({'marque': 'VEICHI', 'description': desc, 'garantie': '',
                            'garantie_mois': None, 'garantie_production_mois': None}, **fige)
            return SimpleNamespace(regles_calcul=14, statut='envoye', date_envoi=date_envoi,
                                   date_creation=date_envoi, mode_installation='agricole',
                                   clauses_appliquees=[{'type': 'reglages_figes', 'produits': {'7': produit}}])

        def texte(devis, protection_du_jour):
            return _item_du_devis(ligne(protection_du_jour), Decimal('20'), devis)['description']
        # Envoyé avant la coupure (instantané sans la clé, d'avant ce gel) : octet-identique.
        self.assertEqual(texte(envoye(avant), None), desc)
        self.assertEqual(texte(envoye(avant), True), desc)
        # Envoyé après, fiche muette à l'envoi, remplie ensuite : toujours SANS la phrase.
        self.assertEqual(texte(envoye(apres, protection_marche_a_sec=None), True),
                         'Pilotage automatique lever/coucher du soleil')
        # Envoyé après, fiche vraie à l'envoi, vidée ensuite : toujours AVEC la phrase.
        self.assertEqual(texte(envoye(apres, protection_marche_a_sec=True), None), desc)
        self.assertEqual(texte(envoye(apres, protection_marche_a_sec=True), False), desc)

    # ── Niveau 3 (corrections résidentielles du 27/10/2026) ──
    def test_devis_envoye_au_niveau_2_hors_corrections_2710(self):
        envoye = SimpleNamespace(regles_calcul=REGLES_CORRIGEES)
        self.assertFalse(regles_au_moins(envoye, REGLES_CORRIGEES_2710))
        # Garde de niveau 2 inchangée : il reste aux règles corrigées.
        self.assertTrue(calcul_corrige(envoye))

    def test_devis_neuf_aux_corrections_2710(self):
        from apps.ventes.models import Devis
        neuf = Devis()  # brouillon neuf, jamais enregistré
        self.assertTrue(regles_au_moins(neuf, REGLES_CORRIGEES_2710))
        self.assertTrue(calcul_corrige(neuf))

    def test_niveau_1_hors_des_deux_corrections(self):
        origine = SimpleNamespace(regles_calcul=REGLES_ORIGINE)
        self.assertFalse(calcul_corrige(origine))
        self.assertFalse(regles_au_moins(origine, REGLES_CORRIGEES_2710))

    def test_doublure_sans_champ_suit_le_niveau_courant(self):
        self.assertTrue(regles_au_moins(SimpleNamespace(), REGLES_CORRIGEES_2710))
        self.assertTrue(regles_au_moins(None, REGLES_CORRIGEES_2710))

    def test_migration_0142_ne_touche_que_les_brouillons(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0142_regles_calcul_niveau_2710')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [7]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_3(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=2))
        Devis.objects.filter.assert_called_with(pk__in=[7])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=3)

    def test_migration_0143_ne_touche_que_les_brouillons(self):
        """D-CI-SENSIB-ENVOYES (30/10/2026) — un devis envoyé reste au niveau 3."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0143_regles_calcul_niveau_3010')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [9]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_4(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=3))
        Devis.objects.filter.assert_called_with(pk__in=[9])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=4)

    def test_migration_0144_ne_touche_que_les_brouillons(self):
        """D-CI-SENSIB-ENVOYES (30/10/2026) — un devis envoyé au niveau 4 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0144_regles_calcul_niveau_5')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [11]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_5(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=4))
        Devis.objects.filter.assert_called_with(pk__in=[11])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=5)

    def test_migration_0144_retour_ramene_5_a_4(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0144_regles_calcul_niveau_5')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [12]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_4(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=5))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=4)

    def test_migration_0145_ne_touche_que_les_brouillons(self):
        """D-ENF-ARRONDI-PDF (30/10/2026) — un devis envoyé au niveau 5 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0145_regles_calcul_niveau_6')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [13]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_6(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=5))
        Devis.objects.filter.assert_called_with(pk__in=[13])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=6)

    def test_migration_0145_retour_ramene_6_a_5(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0145_regles_calcul_niveau_6')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [14]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_5(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=6))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=5)

    def test_migration_0146_ne_touche_que_les_brouillons(self):
        """AMOT103 (31/10/2026) — un devis envoyé au niveau 6 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0146_regles_calcul_niveau_7')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [15]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_7(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=6))
        Devis.objects.filter.assert_called_with(pk__in=[15])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=7)

    def test_migration_0146_retour_ramene_7_a_6(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0146_regles_calcul_niveau_7')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [16]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_6(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=7))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=6)

    def test_migration_0147_ne_touche_que_les_brouillons(self):
        """AGNR54 (01/11/2026) — un devis envoyé au niveau 7 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0147_regles_calcul_niveau_8')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [17]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_8(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=7))
        Devis.objects.filter.assert_called_with(pk__in=[17])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=8)

    def test_migration_0147_retour_ramene_8_a_7(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0147_regles_calcul_niveau_8')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [18]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_7(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=8))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=7)

    def test_migration_0148_ne_touche_que_les_brouillons(self):
        """AMOT116 (01/11/2026) — un devis envoyé au niveau 8 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0148_regles_calcul_niveau_9')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [19]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_9(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=8))
        Devis.objects.filter.assert_called_with(pk__in=[19])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=9)

    def test_migration_0148_retour_ramene_9_a_8(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0148_regles_calcul_niveau_9')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [20]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_8(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=9))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=8)

    def test_migration_0149_ne_touche_que_les_brouillons(self):
        """ADVS5/ADVS6 (02/11/2026) — un devis envoyé au niveau 9 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0149_regles_calcul_niveau_10')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [21]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_10(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=9))
        Devis.objects.filter.assert_called_with(pk__in=[21])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=10)

    def test_migration_0149_retour_ramene_10_a_9(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0149_regles_calcul_niveau_10')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [22]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_9(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=10))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=9)

    def test_migration_0151_ne_touche_que_les_brouillons(self):
        """ADVS3 (03/11/2026) — un devis envoyé au niveau 10 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0151_regles_calcul_niveau_11')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [31]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_11(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=10))
        Devis.objects.filter.assert_called_with(pk__in=[31])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=11)

    def test_migration_0153_ne_touche_que_les_brouillons(self):
        """AMOT118 (04/11/2026) — un devis envoyé au niveau 11 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0153_regles_calcul_niveau_12')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [41]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_12(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=11))
        Devis.objects.filter.assert_called_with(pk__in=[41])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=12)
        self.assertEqual(mod.Migration.dependencies,
                         [('ventes', '0152_retenuesubie_annulee')])

    def test_migration_0153_retour_ramene_12_a_11(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0153_regles_calcul_niveau_12')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [42]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_11(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=12))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=11)

    def test_migration_0158_ne_touche_que_les_brouillons(self):
        """Fondateur 19/11/2026 (cycles batterie C&I) — un devis envoyé au niveau 12 y reste."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0158_regles_calcul_niveau_13')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [51]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_13(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=12))
        Devis.objects.filter.assert_called_with(pk__in=[51])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=13)
        self.assertEqual(mod.Migration.dependencies,
                         [('ventes', '0157_ntplt33_devis_fts_null')])

    def test_migration_0158_retour_ramene_13_a_12(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0158_regles_calcul_niveau_13')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value \
            .values_list.return_value = [52]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_12(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=13))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=12)

    def test_migration_0159_ne_touche_que_les_brouillons(self):
        """D-SENS-1 (19/11/2026) — un devis envoyé au niveau 13 garde son tableau de sensibilités."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0159_regles_calcul_niveau_14')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [61]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.brouillons_au_niveau_14(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0], mock.call(
            statut='brouillon', date_envoi__isnull=True, regles_calcul=13))
        Devis.objects.filter.assert_called_with(pk__in=[61])
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=14)
        self.assertEqual(mod.Migration.dependencies,
                         [('ventes', '0158_regles_calcul_niveau_13')])

    def test_migration_0159_retour_ramene_14_a_13(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0159_regles_calcul_niveau_14')
        Devis = mock.MagicMock()
        Devis.objects.filter.return_value.order_by.return_value             .values_list.return_value = [62]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retour_niveau_13(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(regles_calcul=14))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            regles_calcul=13)

    def test_migration_0160_drapeau_des_seuls_ci_non_brouillons(self):
        """R4-02 (22/11/2026) — un devis C&I envoyé garde « kWh déclarés » :
        le drapeau seul est ajouté, aucune autre clé de l'étude ne bouge."""
        mod = importlib.import_module(
            'apps.ventes.migrations.0160_r402_source_conso_historique')
        etude_ci = {'etude_ci': {'feuille_consommation_retenue': 'facture_hiver_mad'}, 'tension': 'bt'}
        lignes = [SimpleNamespace(pk=71, etude_params=dict(etude_ci), mode_installation='industriel'),
                  SimpleNamespace(pk=72, etude_params={'kwc': 5}, mode_installation='residentiel'),
                  SimpleNamespace(pk=73, etude_params={}, mode_installation='commercial'),
                  SimpleNamespace(pk=74, etude_params={'kwc': 50}, mode_installation='Commercial')]
        Devis = mock.MagicMock()
        (Devis.objects.exclude.return_value.exclude.return_value.only.return_value
         .order_by.return_value.iterator.return_value) = lignes
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.marquer(apps, None)
        self.assertEqual(Devis.objects.exclude.call_args_list[0],
                         mock.call(statut='brouillon', date_envoi__isnull=True))
        self.assertEqual(Devis.objects.filter.call_args_list,
                         [mock.call(pk=71), mock.call(pk=74)])
        self.assertEqual(Devis.objects.filter.return_value.update.call_args_list, [
            mock.call(etude_params=dict(etude_ci, regles_source_conso_historique=True)),
            mock.call(etude_params={'kwc': 50, 'regles_source_conso_historique': True})])
        self.assertEqual(lignes[0].etude_params, etude_ci)  # l'objet lu n'est pas muté
        self.assertTrue(mod.doit_marquer({'etude_ci': {}}, None))
        self.assertFalse(mod.doit_marquer({'regles_source_conso_historique': True}, 'industriel'))
        self.assertFalse(mod.doit_marquer(None, 'industriel'))
        self.assertEqual(mod.Migration.dependencies,
                         [('ventes', '0159_regles_calcul_niveau_14')])

    def test_migration_0160_retour_retire_le_drapeau(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0160_r402_source_conso_historique')
        Devis = mock.MagicMock()
        (Devis.objects.filter.return_value.only.return_value.order_by.return_value
         .iterator.return_value) = [SimpleNamespace(
             pk=75, etude_params={'kwc': 50, 'regles_source_conso_historique': True})]
        apps = mock.MagicMock()
        apps.get_model.return_value = Devis
        mod.retirer(apps, None)
        self.assertEqual(Devis.objects.filter.call_args_list[0],
                         mock.call(etude_params__regles_source_conso_historique=True))
        Devis.objects.filter.return_value.update.assert_called_once_with(
            etude_params={'kwc': 50})

    def test_niveau_6_arrondi_des_seuls_nouveaux_rendus(self):
        self.assertFalse(regles_au_moins(
            SimpleNamespace(regles_calcul=REGLES_RETOURS_3010B), REGLES_ARRONDI_3010))
        self.assertTrue(regles_au_moins(SimpleNamespace(), REGLES_ARRONDI_3010))

    def test_migration_fige_les_envoyes(self):
        mod = importlib.import_module(
            'apps.ventes.migrations.0138_regles_calcul_devis_envoyes')
        self.assertTrue(callable(mod.figer_devis_envoyes))


class ReglesCalculDryrunCommandeTests(TestCase):
    """ATST24 (C-ATST-012) — la commande jouée sur des devis en base, seul le
    builder doublé. Mutants : ``!=`` → ``==`` dans ``ecarts_du_devis``, ou un
    ``.update(regles_calcul=…)`` après le bloc atomique ⇒ rouge."""

    def test_sortie_et_aucune_ecriture(self):
        from io import StringIO
        from django.core.management import call_command
        from apps.ventes.management.commands.regles_calcul_ecarts_dryrun import ecarts_du_devis
        from apps.ventes.models import Devis
        from apps.ventes.tests.test_l_niv_niveau import make_client, make_company, make_devis, make_user
        co = make_company('atst24')
        user, client = make_user(co), make_client(co)
        a, b, c = (make_devis(co, user, client, f'DEV-ATST24-{n}') for n in 'ABC')
        Devis.objects.filter(pk__in=[a.pk, b.pk]).update(regles_calcul=REGLES_ORIGINE)
        a.refresh_from_db()

        def faux_builder(devis, opts):
            if devis.reference.endswith('B'):
                raise ValueError('illisible')
            return {'display_total': 100 if devis.regles_calcul == REGLES_ORIGINE else 120,
                    'puissance_kwc': 5}
        buf = StringIO()
        with mock.patch('apps.ventes.quote_engine.builder.build_quote_data', faux_builder):
            call_command('regles_calcul_ecarts_dryrun', '--detail', stdout=buf)
            self.assertEqual(ecarts_du_devis(a), {'display_total': (100, 120)})
        self.assertEqual(a.regles_calcul, REGLES_ORIGINE)
        out = buf.getvalue()
        self.assertIn("2 devis aux règles d'origine ; 1 changeraient", out)
        self.assertIn('DEV-ATST24-A [envoye] : display_total\n', out)
        self.assertIn('display_total: 100 -> 120', out)
        self.assertIn('DEV-ATST24-B : rendu impossible (ValueError)', out)
        self.assertNotIn('DEV-ATST24-C', out)
        relus = dict(Devis.objects.filter(pk__in=[a.pk, b.pk, c.pk]).values_list('reference', 'regles_calcul'))
        self.assertEqual(relus, {'DEV-ATST24-A': REGLES_ORIGINE, 'DEV-ATST24-B': REGLES_ORIGINE,
                                 'DEV-ATST24-C': REGLES_COURANTES})

    def test_niveau_15_bloc_recalcule_changera_et_aucune_ecriture(self):
        """ACAL1000 — ``--niveau 15`` : le bloc horaire est RECALCULÉ (doublure :
        la pose réelle de l'est-ouest produit moins), « changera » dit oui pour
        le brouillon jamais envoyé, non pour l'envoyé ; rien n'est écrit.
        Mutants : ne pas recalculer ⇒ aucun écart ; enregistrer le niveau ⇒ rouge."""
        from io import StringIO
        from django.core.management import call_command
        from apps.ventes.models import Devis
        from apps.ventes.tests.test_l_niv_niveau import make_client, make_company, make_devis, make_user
        co = make_company('acal1000')
        user, client = make_user(co), make_client(co)
        est_ouest, envoye, sans = (make_devis(co, user, client, f'DEV-ACAL1000-{n}') for n in 'EVS')
        Devis.objects.filter(pk=est_ouest.pk).update(statut='brouillon', date_envoi=None)
        for d in (est_ouest, envoye, sans):
            Devis.objects.filter(pk=d.pk).update(etude_params={'etude_horaire': {'prod': 1000}})
        Devis.objects.filter(company=co).update(regles_calcul=REGLES_SENSIBILITES_1911)
        prod_pose = {'DEV-ACAL1000-E': 900, 'DEV-ACAL1000-V': 950, 'DEV-ACAL1000-S': 1000}

        def faux_rafraichir(devis, force=False):
            self.assertTrue(force)
            self.assertEqual((devis.regles_calcul, devis.statut), (REGLES_POSE_REELLE_2111, 'brouillon'))
            devis.etude_params = {'etude_horaire': {'prod': prod_pose[devis.reference]}}
            devis.save(update_fields=['etude_params'])

        def faux_builder(devis, opts):
            prod = devis.etude_params['etude_horaire']['prod']
            return {'prod_kwh': prod, 'eco_s_ann': prod * 2, 'nb_panneaux': 10,
                    'totaux_all': {'ttc': 50000}}
        buf = StringIO()
        with mock.patch('apps.ventes.quote_engine.builder.build_quote_data', faux_builder), \
                mock.patch('apps.ventes.domain.etudes.rafraichir_etude_horaire_devis', faux_rafraichir):
            call_command('regles_calcul_ecarts_dryrun', '--niveau', '15', '--company', str(co.pk), stdout=buf)
        out = buf.getvalue()
        self.assertIn('DEV-ACAL1000-E, brouillon, oui, prod_kwh, 1000, 900, -100', out)
        self.assertIn('DEV-ACAL1000-E, brouillon, oui, eco_s_ann, 2000, 1800, -200', out)
        self.assertIn('DEV-ACAL1000-V, envoye, non, prod_kwh, 1000, 950, -50', out)
        self.assertNotIn('DEV-ACAL1000-S,', out)
        self.assertNotIn('nb_panneaux,', out)
        self.assertIn('TOTAL prod_kwh : -150.0', out)
        relus = {r: (n, p['etude_horaire']['prod'], s) for r, n, p, s in Devis.objects.filter(company=co)
                 .values_list('reference', 'regles_calcul', 'etude_params', 'statut')}
        self.assertEqual(relus, {'DEV-ACAL1000-E': (14, 1000, 'brouillon'), 'DEV-ACAL1000-V': (14, 1000, 'envoye'),
                                 'DEV-ACAL1000-S': (14, 1000, 'envoye')})

    def test_acal1203_niveau_15_agricole_etude_pompage_recalculee(self):
        """ACAL1203 — ``--niveau 15`` sur des devis AGRICOLES : l'étude de pompage
        RANGÉE est recalculée (doublure : la pose est-ouest livre moins d'eau),
        « changera » oui pour le brouillon, non pour l'envoyé ; rien n'est écrit.
        Mutants : ne pas recalculer ⇒ aucun écart ; enregistrer le niveau ⇒ rouge."""
        from io import StringIO
        from django.core.management import call_command
        from apps.ventes.models import Devis
        from apps.ventes.tests.test_l_niv_niveau import make_client, make_company, make_devis, make_user
        co = make_company('acal1203')
        user, client = make_user(co), make_client(co)
        lie, envoye, sans = (make_devis(co, user, client, f'DEV-ACAL1203-{n}') for n in 'EVS')
        Devis.objects.filter(pk=lie.pk).update(statut='brouillon', date_envoi=None)

        def etude(m3, source):
            return {'m3_jour': m3, 'heures_pompage': 7, 'couverture_pct_mois': [100] * 12,
                    'production': {'m3_jour_mois': [m3] * 12, 'plan_irradiation': {'source': source}}}
        Devis.objects.filter(company=co).update(mode_installation='agricole', etude_params=etude(40, 'site_reference'),
                                                regles_calcul=REGLES_SENSIBILITES_1911)
        apres = {'DEV-ACAL1203-E': etude(36, 'pose_calepinage'), 'DEV-ACAL1203-V': etude(38, 'pose_calepinage'),
                 'DEV-ACAL1203-S': etude(40, 'site_reference')}

        def faux_pompage(devis, force=False):
            self.assertTrue(force)
            self.assertEqual((devis.regles_calcul, devis.statut), (REGLES_POSE_REELLE_2111, 'brouillon'))
            devis.etude_params = apres[devis.reference]
            devis.save(update_fields=['etude_params'])
        buf = StringIO()
        with mock.patch('apps.ventes.quote_engine.builder.build_quote_data', lambda d, o: {'prod_kwh': 1000}), \
                mock.patch('apps.ventes.domain.etudes.rafraichir_etude_horaire_devis', lambda d, force=False: None), \
                mock.patch('apps.ventes.domain.pompage.rafraichir_etude_pompage_devis', faux_pompage):
            call_command('regles_calcul_ecarts_dryrun', '--niveau', '15', '--company', str(co.pk), stdout=buf)
        out = buf.getvalue()
        self.assertIn('DEV-ACAL1203-E, brouillon, oui, m3_jour, 40, 36, -4', out)
        self.assertIn('DEV-ACAL1203-E, brouillon, oui, production.m3_jour_mois, %s, %s, %s'
                      % ([40] * 12, [36] * 12, [-4] * 12), out)
        self.assertIn('DEV-ACAL1203-E, brouillon, oui, production.plan_irradiation.source, '
                      'site_reference, pose_calepinage, None', out)
        self.assertIn('DEV-ACAL1203-V, envoye, non, m3_jour, 40, 38, -2', out)
        self.assertNotIn('DEV-ACAL1203-S,', out)
        self.assertNotIn('heures_pompage,', out)
        self.assertIn('TOTAL m3_jour : -6.0', out)
        self.assertIn('TOTAL production.m3_jour_mois : -72.0', out)
        relus = {r: (n, p['m3_jour'], s) for r, n, p, s in Devis.objects.filter(company=co)
                 .values_list('reference', 'regles_calcul', 'etude_params', 'statut')}
        self.assertEqual(relus, {'DEV-ACAL1203-E': (14, 40, 'brouillon'), 'DEV-ACAL1203-V': (14, 40, 'envoye'),
                                 'DEV-ACAL1203-S': (14, 40, 'envoye')})


class FormateursReglesOrigineTests(SimpleTestCase):
    """AMOT24 / AMOT26 / AMOT45 / AMOT33 / AMOT27 — un devis aux règles
    d'origine garde les formats d'hier ; un devis corrigé prend les nouveaux."""

    def setUp(self):
        from apps.ventes.quote_engine.montants import poser_regles_origine
        self.addCleanup(poser_regles_origine, False)

    def test_pct_fr_origine_et_corrige(self):
        from apps.ventes.quote_engine import montants
        montants.poser_regles_origine(True)
        self.assertEqual(montants.pct_fr(2.5), '2.5')
        self.assertEqual(montants.pct_fr(20.0), '20')
        montants.poser_regles_origine(False)
        self.assertEqual(montants.pct_fr(2.5), '2,5')
        self.assertEqual(montants.pct_fr(20.0), '20')

    def test_fmt_dirhams_arrondi_origine_et_corrige(self):
        from apps.ventes.quote_engine import montants
        montants.poser_regles_origine(True)
        # ``round`` de Python : au pair.
        self.assertEqual(montants.fmt_dirhams(52650.5, sep=' '), '52 650')
        montants.poser_regles_origine(False)
        self.assertEqual(montants.fmt_dirhams(52650.5, sep=' '), '52 651')

    def test_lignes_remisees_catalogue_seul(self):
        from apps.ventes.quote_engine.montants import lignes_remisees
        it = {'prix_unit_ht': 1000, 'quantite': 2, 'pu_ht_remise': 950,
              'total_ht_remise': 1900}
        (_i, pu_cat, pu, tot_cat, tot, remisee) = lignes_remisees(
            [it], catalogue_seul=True)[0]
        self.assertEqual((pu_cat, pu, tot_cat, tot, remisee),
                         (1000.0, 1000.0, 2000.0, 2000.0, False))
        (_i, _c, pu, _tc, tot, remisee) = lignes_remisees([it])[0]
        self.assertEqual((pu, tot, remisee), (950.0, 1900.0, True))

    def test_option_recommandee_origine_toujours_avec(self):
        from apps.ventes.quote_engine.figures import option_recommandee
        quote = {'deux_options': True, 'recommended': 'Sans batterie'}
        self.assertEqual(option_recommandee(quote), 'sans')
        self.assertEqual(
            option_recommandee(dict(quote, regles_calcul_origine=True)),
            'avec')

    def test_repartition_mensuelle_historique(self):
        from apps.ventes.quote_engine.pricing import (
            CLE_SOLAIRE_MENSUELLE_HISTORIQUE, calculate_savings_roi)
        kw = {}  # modèle « estimation » : la série vient de la clé
        origine = calculate_savings_roi(5.0, 50000, 80000,
                                        forme_mensuelle_ghi=False, **kw)
        attendu = [round(origine['eco_s_ann'] * f)
                   for f in CLE_SOLAIRE_MENSUELLE_HISTORIQUE]
        self.assertEqual(origine['eco_s_monthly'], attendu)
        corrige = calculate_savings_roi(5.0, 50000, 80000, **kw)
        self.assertEqual(sum(corrige['eco_s_monthly']),
                         round(corrige['eco_s_ann']))


class ArrondiAffichageTests(SimpleTestCase):
    """D-ENF-ARRONDI-PDF (fondateur 30/10/2026) — l'argent affiché par le
    moteur est arrondi MOITIÉ VERS LE HAUT (``core.money.quantize_mad``) à la
    MÊME précision ; un devis envoyé avant le niveau 6 garde ``round``."""

    def setUp(self):
        from apps.ventes.quote_engine.montants import poser_regles_origine
        poser_regles_origine(False)
        self.addCleanup(poser_regles_origine, False)

    def test_quantize_mad_garde_la_precision_demandee(self):
        from core.money import quantize_mad
        self.assertEqual(quantize_mad('12.505'), Decimal('12.51'))
        self.assertEqual(quantize_mad(12.5, decimales=0), Decimal('13'))
        self.assertEqual(quantize_mad('0.1234565', decimales=6), Decimal('0.123457'))

    def test_cas_moitie_par_precision(self):
        from apps.ventes.quote_engine.montants import arrondi_affichage as A
        # (valeur, ndigits, moitié vers le haut, round() bancaire d'hier)
        for valeur, nd, haut, banquier in (
                (12.5, None, 13, 12),            # dirham : cartes, prix au kWc
                (51232.5, None, 51233, 51232),   # QJR53 : carte = bloc de totaux
                (1250.5, None, 1251, 1250),      # provision onduleur
                (0.125, 2, 0.13, 0.12),          # centime : multi-villa, cumul
                (12.505, 2, 12.51, None),        # exemple de la convention
                (1.25, 1, 1.3, 1.2),             # payback / kWh au dixième
                (0.1234565, 6, 0.123457, 0.123456)):  # prix de tranche
            with self.subTest(valeur=valeur, nd=nd):
                self.assertEqual(A(valeur, nd), haut)
                if banquier is not None:
                    self.assertEqual(round(valeur, nd), banquier)
        self.assertEqual(A(Decimal('1.005'), 2), Decimal('1.01'))

    def test_aucune_valeur_hors_moitie_ne_bouge(self):
        """Hors cas moitié, le chiffre est celui de ``round`` — au type près."""
        from apps.ventes.quote_engine.montants import arrondi_affichage as A
        for i in range(1, 4000):
            for valeur in (i * 7.31, i / 3.0, i * 1.2 + 0.004, i * 0.37):
                for nd in (None, 1, 2):
                    attendu = round(valeur, nd)
                    if Decimal(repr(valeur)).scaleb(nd or 0) % 1 == Decimal('0.5'):
                        continue  # cas moitié (décimal) : il bouge, voulu
                    self.assertEqual(A(valeur, nd), attendu, (valeur, nd))
                    self.assertIs(type(A(valeur, nd)), type(attendu))
        self.assertIs(type(A(7, 2)), int)

    def test_devis_envoye_garde_round(self):
        from apps.ventes.quote_engine import montants
        montants.poser_regles_origine(False, arrondi_historique=True)
        self.assertEqual(montants.arrondi_affichage(12.5), 12)
        self.assertEqual(montants.arrondi_affichage(0.125, 2), 0.12)
        montants.poser_regles_origine(True)  # niveau 1 : historique aussi
        self.assertEqual(montants.arrondi_affichage(12.5), 12)
        montants.reinitialiser_regles()
        self.assertEqual(montants.arrondi_affichage(12.5), 13)

    def test_entrees_non_finies_comme_round(self):
        from apps.ventes.quote_engine.montants import arrondi_affichage as A
        with self.assertRaises(ValueError):
            A(float('nan'))
        self.assertEqual(A(float('inf'), 1), float('inf'))


# ── ADEV155 (D-ACAL-108 « Yes, with level 15 ») — le moteur sans toit sur le plan par défaut ─
# Module voisin lu par son NOM (jamais ses classes importées ici : le chargeur les rejouerait).
from apps.ventes.tests import test_conception_lead as TCL  # noqa: E402 — après les classes de ce module


def _plan_simule(company, lead, kwc, produits, nb_panneaux=None, *, suppositions=()):
    """La doublure de ``porte_calepinage.production_du_plan_par_defaut`` : 2 100 kWh/kWc,
    bien au-dessus de la ville — toute valeur calculée sur lui s'en écarte."""
    return {'production_annuelle': kwc * 2100.0, 'production_mensuelle': [kwc * 175.0] * 12, 'kwc': kwc,
            'pente_deg': 30.0, 'azimut_deg': 180.0, 'complete': True,
            'suppositions': [{'code': 'pente_supposee', 'champ': 'inclinaison_deg'},
                             {'code': 'pose_supposee', 'champ': 'type_toiture', 'valeur': 'affleurante'},
                             *suppositions]}


class MoteurSansToitPlanParDefautTests(TCL._emprunt(TCL.FigeageDevisAutoTests, *TCL._FABRIQUES), TestCase):
    """ADEV155 — au niveau 14 COURANT, rien ne bouge au bit près (la simulation du plan n'est
    jamais appelée) ; au niveau 15, la production d'un lead sans toit tracé vient du plan par
    défaut, dite (source ``plan_par_defaut`` + suppositions) ; un plan à fiche de module vide
    n'est jamais servi (la ville reste, absence dite)."""

    def _calculer(self, company, lead, *, niveau=None, plan=_plan_simule, ouvert=None):
        from apps.ventes.conception import moteur as M
        from apps.ventes.conception import porte_calepinage as P
        from apps.ventes.domain import regles_calcul as RC

        TCL._reglages_de_la_societe(company)
        ferme = mock.patch.object(M, 'plan_par_defaut_ouvert', return_value=False) if ouvert is False else None
        with mock.patch.object(RC, 'REGLES_COURANTES', niveau or RC.REGLES_COURANTES), \
                mock.patch.object(P, 'production_du_plan_par_defaut', side_effect=plan) as simule:
            if ferme is None:
                return M.calculer_conception(lead, company), simule
            with ferme:
                return M.calculer_conception(lead, company), simule

    def test_niveau_courant_identique_avec_et_sans_le_plan(self):
        from apps.ventes.domain import regles_calcul as RC

        self.assertEqual(RC.REGLES_COURANTES, RC.REGLES_SENSIBILITES_1911)  # le niveau 15 reste dormant
        company, lead = self._cas('res_facture_dirhams')
        resultat, simule = self._calculer(company, lead)
        simule.assert_not_called()  # mutant « ouvrir le plan au niveau 14 » : rouge
        sans, _s = self._calculer(company, lead, ouvert=False)
        self.assertEqual(TCL._json(resultat.sortie()), TCL._json(sans.sortie()))
        self.assertEqual(TCL._json(resultat.etude_params), TCL._json(sans.etude_params))
        self.assertNotIn('production_plan_par_defaut', resultat.absents)
        self.assertEqual(resultat.valeurs[resultat.option_retenue]['production_annuelle']['source'], 'moteur')

    def test_niveau_15_production_du_plan_par_defaut_dite(self):
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111 as N15

        company, lead = self._cas('res_batterie_sans')
        temoin, _s = self._calculer(company, lead, niveau=N15, plan=lambda *a, **k: {'refus': 'fiche vide'})
        resultat, simule = self._calculer(company, lead, niveau=N15)
        self.assertEqual(resultat.etat, 'complet', resultat.refus)
        args = simule.call_args.args
        self.assertEqual((args[0], args[1].pk), (company, lead.pk))
        self.assertGreater(args[2], 0)
        self.assertEqual(set(args[3]), {'module', 'onduleur'})
        option = resultat.option_retenue
        retenue, avant = resultat.valeurs[option], temoin.valeurs[option]
        self.assertEqual(resultat.blocs['etude_horaire']['base_production']['source'], 'plan_par_defaut')
        self.assertEqual(resultat.blocs['etude_horaire']['base_production']['kwh_kwc_annuel'], 2100.0)
        self.assertEqual(retenue['production_annuelle']['source'], 'plan_par_defaut')
        self.assertEqual(retenue['production_annuelle']['valeur'],
                         resultat.blocs['etude_horaire']['annuel']['production_kwh'])
        for cle in ('production_annuelle', 'economies_annuelles'):
            self.assertNotEqual(retenue[cle]['valeur'], avant[cle]['valeur'], cle)
        codes = [s['code'] for s in resultat.suppositions]
        for code in ('pente_supposee', 'pose_supposee', 'production_plan_par_defaut'):
            self.assertIn(code, codes)
        dite = next(s for s in resultat.suppositions if s['code'] == 'production_plan_par_defaut')
        self.assertIn('toit supposé', dite['message'])
        self.assertIn('2100', dite['message'])
        # Le plan refusé : la ville reste, l'absence est DITE (jamais un refus de la conception).
        self.assertEqual(avant['production_annuelle']['source'], 'moteur')
        self.assertEqual(temoin.absents['production_plan_par_defaut'], 'plan par défaut refusé : fiche vide')
        # Point 4 de la relecture — l'échec n'est plus muet : une supposition SERVIE le dit (``absents``
        # n'est ni rangé ni servi). Mutant « absents seulement » : rouge.
        non_simule = [s for s in temoin.suppositions if s['code'] == 'plan_par_defaut_non_simule']
        self.assertEqual(len(non_simule), 1, temoin.suppositions)
        self.assertIn('plan par défaut refusé : fiche vide', non_simule[0]['message'])
        self.assertIn('production standard de la ville', non_simule[0]['message'])
        self.assertIn('plan_par_defaut_non_simule', [s['code'] for s in temoin.sortie()['suppositions']])
        self.assertNotIn('plan_par_defaut_non_simule', codes)

    def test_niveau_15_fiche_du_module_vide_jamais_servie(self):
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111 as N15

        company, lead = self._cas('res_facture_dirhams')
        resultat, simule = self._calculer(company, lead, niveau=N15, plan=lambda *a, **k: _plan_simule(
            *a, **k, suppositions=[{'code': 'fiche_module_incomplete'}]))
        simule.assert_called()
        self.assertEqual(resultat.valeurs[resultat.option_retenue]['production_annuelle']['source'], 'moteur')
        self.assertIn('fiche technique du module', resultat.absents['production_plan_par_defaut'])
        self.assertNotIn('production_plan_par_defaut', [s['code'] for s in resultat.suppositions])
        dite = next(s for s in resultat.suppositions if s['code'] == 'plan_par_defaut_non_simule')
        self.assertEqual(dite['champ'], 'fiche_technique')
        self.assertIn('renseigner la fiche technique du produit dans Stock', dite['message'])


class MoteurSansToitCITests(TCL._emprunt(TCL.FigeageDevisAutoTests, *TCL._FABRIQUES), TestCase):
    """ADEV155, point 1 (a) de la relecture — un lead COMMERCIAL sans toit tracé : au niveau 14
    courant rien ne bouge ; au niveau 15 la production de l'étude C&I vient du plan par défaut,
    et la pose supposée est « sur châssis » (D-ACAL-107, règle RÉELLE de ``_pose_supposee``
    alimentée par le ``type_installation`` du lead)."""

    def _calculer(self, company, lead, *, niveau=None, ouvert=None):
        from apps.calepinage.services import plan_par_defaut as PPD
        from apps.ventes.conception import moteur as M
        from apps.ventes.domain import regles_calcul as RC

        def simuler(company_, lat, lon, kwc, **kw):  # la simulation doublée, la règle de pose réelle
            _flush, pose = PPD._pose_supposee(kw.get('type_installation'), kw.get('type_toiture'))
            return dict(_plan_simule(company_, None, kwc, {}), suppositions=[pose])
        TCL._reglages_de_la_societe(company)
        with mock.patch.object(RC, 'REGLES_COURANTES', niveau or RC.REGLES_COURANTES), \
                mock.patch.object(PPD, 'simuler_plan_par_defaut', side_effect=simuler) as simule, \
                mock.patch.object(M, 'plan_par_defaut_ouvert', wraps=M.plan_par_defaut_ouvert,
                                  **({'return_value': False} if ouvert is False else {})):
            return M.calculer_conception(lead, company), simule

    def test_niveau_courant_identique_puis_niveau_15_plan_par_defaut_sur_chassis(self):
        from apps.ventes.domain.regles_calcul import REGLES_POSE_REELLE_2111 as N15

        company, lead = self._cas('ci_commercial')
        courant, simule = self._calculer(company, lead)
        simule.assert_not_called()
        ferme, _s = self._calculer(company, lead, ouvert=False)
        self.assertEqual(TCL._json(courant.sortie()), TCL._json(ferme.sortie()))
        resultat, simule = self._calculer(company, lead, niveau=N15)
        self.assertEqual(resultat.etat, 'complet', resultat.refus)
        self.assertEqual(simule.call_args.kwargs['type_installation'], 'commercial')
        etude = resultat.blocs['etude_ci']
        self.assertEqual(etude['production']['source'], 'calepinage')
        self.assertEqual(etude['production']['kwh_kwc_mensuel'], [175.0] * 12)
        self.assertIn('plan_par_defaut', [h.get('source') for h in etude.get('hypotheses') or []])
        option = resultat.option_retenue
        self.assertEqual(resultat.valeurs[option]['production_annuelle']['source'], 'plan_par_defaut')
        self.assertNotEqual(resultat.valeurs[option]['production_annuelle']['valeur'],
                            courant.valeurs[option]['production_annuelle']['valeur'])
        pose = [s for s in resultat.suppositions if s['code'] == 'pose_supposee']
        self.assertEqual([(s['champ'], s['valeur']) for s in pose], [('type_installation', 'sur châssis')])
        self.assertIn('tracer le toit au calepinage', pose[0]['message'])


class ListeSansToitHorsPompageTests(TCL._emprunt(TCL.FigeageDevisAutoTests, *TCL._FABRIQUES), TestCase):
    """Point 3 de la relecture — ``remplir_conceptions --ecarts-sans-toit`` laisse de côté un lead
    AGRICOLE sans toit par LA règle du moteur (``moteur.marche_au_plan_par_defaut``), le dit dans
    sa ligne de synthèse, et ne simule jamais son plan. (Dans ce module plutôt que dans
    ``test_conception_lead.py`` : ce fichier-mur de 4 481 lignes ne peut plus grossir — C20.)"""

    def test_lead_agricole_sans_toit_hors_liste_et_compte(self):
        import io

        from django.core.management import call_command

        from apps.crm.models import Lead

        company, lead = self._residentiel(facture_hiver=Decimal('1800'))
        TCL._reglages_de_la_societe(company)
        agricole = Lead.objects.create(company=company, nom='Agri', prenom='Sans toit', ville=lead.ville,
                                       type_installation='agricole', facture_hiver=Decimal('1800'))
        simules = []

        def plan(company_, lat, lon, kwc, **kw):
            simules.append(kw['lead_id'])
            return dict(_plan_simule(company_, None, kwc, {}), suppositions=[])
        sortie = io.StringIO()
        with mock.patch('apps.calepinage.services.plan_par_defaut.simuler_plan_par_defaut', side_effect=plan):
            call_command('remplir_conceptions', '--company', str(company.pk), '--ecarts-sans-toit', stdout=sortie,
                         stderr=io.StringIO())
        liste = sortie.getvalue()
        self.assertIn('ÉCARTS SANS TOIT : 1 lead(s) sans toit tracé listé(s), 1 lead(s) agricole(s) laissé(s) '
                      'de côté', liste)  # mutant « liste sans la règle du moteur » : 2 listés, rouge
        self.assertIn(f'lead #{lead.pk} (sans toit) option ', liste)
        self.assertNotIn(f'lead #{agricole.pk} ', liste)
        self.assertNotIn(agricole.pk, simules)
        self.assertIn(lead.pk, simules)


class ProductibleDuPlanParDefautTests(SimpleTestCase):
    """ADEV155 — la porte ne sert JAMAIS un plan dont une étape a été omise faute de fiche
    (B1, relecture lot 5 : fiche à puissance sans coefficient de température)."""

    def _porte(self, plan):
        from apps.ventes.conception import porte_calepinage as P
        with mock.patch.object(P, 'production_du_plan_par_defaut', return_value=plan):
            return P.productible_du_plan_par_defaut(None, SimpleNamespace(pk=1), 6.0, {})

    def test_fiche_a_puissance_sans_coefficient_jamais_servie_champ_nomme(self):
        manque = {'code': 'fiche_module_incomplete', 'champ': 'fiche_technique',
                  'valeur': 'fiche_module.temp_coeff_pmax_pct_c'}
        servi, suppositions, motif = self._porte(_plan_simule(None, None, 6.0, {}, suppositions=[manque]))
        self.assertIsNone(servi)  # mutant « ne refuser que si la puissance vient de la conception » : rouge
        self.assertEqual(suppositions, [])
        self.assertIn('« fiche_module.temp_coeff_pmax_pct_c »', motif)
        servi, _s, _m = self._porte(_plan_simule(None, None, 6.0, {}))
        self.assertEqual(servi['kwh_kwc_annuel'], 2100.0)

    def test_mois_absent_jamais_servi_comme_zero(self):
        plan = _plan_simule(None, None, 6.0, {})
        plan['production_mensuelle'][6] = None
        self.assertEqual(self._porte(plan), (None, [], 'plan par défaut incomplet'))  # mutant « m or 0 » : rouge


class BrouillonDuPlanParDefautTests(SimpleTestCase):
    """ADEV155 — un brouillon de niveau 15 né du plan par défaut (aucune pose servie) garde la
    base rangée du plan ; au niveau 14, et pour une base rangée d'une autre source, rien ne change."""

    BASE = {'kwh_kwc_annuel': 2100.0, 'kwh_kwc_mensuel': [175.0] * 12, 'pertes_incluses': True,
            'source': 'plan_par_defaut'}

    def _diag(self, **champs):
        from apps.ventes.horaire.productible_pose import diagnostic_base_de_production
        devis = SimpleNamespace(**dict(dict(pk=1, company=None, regles_calcul=REGLES_POSE_REELLE_2111,
                                            statut='brouillon', mode_installation='residentiel',
                                            etude_params={'etude_horaire': {'base_production': self.BASE}}),
                                       **champs))
        with mock.patch('apps.calepinage.selectors_devis.productible_pose_servi', return_value=None):
            return diagnostic_base_de_production(devis, kwc=6.0)

    def test_brouillon_niveau_15_garde_la_base_du_plan(self):
        self.assertEqual(self._diag(), (self.BASE, ''))
        self.assertEqual(self._diag(regles_calcul=REGLES_SENSIBILITES_1911), (None, 'règles d’avant le 21/11'))
        autre = dict(self.BASE, source='calepinage_enregistre')
        self.assertEqual(self._diag(etude_params={'etude_horaire': {'base_production': autre}}),
                         (None, 'aucune simulation du calepinage'))

    def test_brouillon_ci_niveau_15_relit_la_base_du_plan_de_son_etude(self):
        """Point 1 (b) de la relecture — un brouillon C&I né du plan par défaut, rafraîchi : sa
        base est relue sur son bloc ``etude_ci`` (12 kWh/kWc d'origine ``calepinage`` + la
        source ``plan_par_defaut`` de ses hypothèses), jamais la ville. Mutant « lire le seul
        bloc horaire » : (None, …) — rouge."""
        from apps.ventes.horaire.productible_pose import base_etude_ci
        etude_ci = {'production': {'source': 'calepinage', 'kwh_kwc_mensuel': [175.0] * 12},
                    'hypotheses': [{'cle': 'forme_horaire', 'source': 'plan_par_defaut'}]}
        devis = SimpleNamespace(pk=1, company=None, regles_calcul=REGLES_POSE_REELLE_2111, statut='brouillon',
                                mode_installation='commercial', etude_params={'etude_ci': etude_ci})
        with mock.patch('apps.calepinage.selectors_devis.productible_pose_servi', return_value=None):
            base, hypothese = base_etude_ci(devis, kwc=30.0)
            self.assertEqual(base, self.BASE)
            self.assertEqual(hypothese['source'], 'plan_par_defaut')
            # Une étude C&I sur PVGIS (ou d'une pose) n'est jamais prise pour le plan.
            devis.etude_params = {'etude_ci': dict(etude_ci, hypotheses=[])}
            self.assertIsNone(base_etude_ci(devis, kwc=30.0)[0])
            pvgis = {'source': 'pvgis', 'kwh_kwc_mensuel': [175.0] * 12}
            devis.etude_params = {'etude_ci': dict(etude_ci, production=pvgis)}
            self.assertIsNone(base_etude_ci(devis, kwc=30.0)[0])
            devis.regles_calcul = REGLES_SENSIBILITES_1911  # niveau 14 : rien
            devis.etude_params = {'etude_ci': etude_ci}
            self.assertEqual(base_etude_ci(devis, kwc=30.0), (None, None))
