"""Bloc ``courbes_journalieres`` de la proposition — niveaux réels, unités justes.

Le graphe « une journée type » de ``/proposition`` dessinait une cloche
SYNTHÉTIQUE et affichait son sommet en « kWh » alors que c'est une PUISSANCE.
Ces tests verrouillent le contrat serveur : formes PVGIS, niveaux tirés du
devis (kWc + factures réelles du lead), pic en kW, variantes batterie réelles,
drapeau d'occupation, et OMISSION quand la donnée manque.

Épingles PVGIS issues du relevé du 21/08/2026 (URLs citées dans
``apps/parametres/pvgis_profils.py`` : PVcalc et DRcalc v5.3, angle 30,
aspect 0, loss 14, crystSi). AUCUN accès réseau : les seuls chemins live sont
mockés, et les chemins testés ici passent par la table de référence.
"""
from unittest import mock

from django.core.cache import cache as django_cache
from django.test import SimpleTestCase

from apps.parametres import pvgis_profils as pp
from apps.ventes import courbes_journalieres as cj

CASA_CONSO = [900, 880, 860, 840, 900, 1100,
              1300, 1350, 1100, 900, 870, 910]


def _data(**extra):
    """Sortie ``build_quote_data`` minimale utile au graphe."""
    base = {
        'puissance_kwc': 10.0,
        'client_city': 'Casablanca',
        'mode_installation': 'residentiel',
        'sans_ok': True,
        'avec_ok': True,
        'deux_options': True,
        'batterie_kwh_total': 10.0,
    }
    base.update(extra)
    return base


class _CourbesBase(SimpleTestCase):
    def setUp(self):
        django_cache.clear()
        # Pas de lead → pas de GPS : la chaîne passe par la ville (aucun réseau).
        patch_loc = mock.patch(
            'apps.crm.selectors.site_location_for_devis',
            return_value={'site_adresse': None, 'site_ville': None,
                          'gps_lat': None, 'gps_lng': None})
        patch_profil = mock.patch(
            'apps.crm.selectors.profil_activite_pour_devis', return_value=None)
        self.loc = patch_loc.start()
        self.profil = patch_profil.start()
        self.addCleanup(patch_loc.stop)
        self.addCleanup(patch_profil.stop)

    def _bloc(self, data=None, conso=None):
        return cj.construire_courbes_journalieres(
            object(), _data() if data is None else data,
            monthly_consumption=conso)


class ProductionTests(_CourbesBase):
    def test_niveau_reel_productible_pvgis_fois_kwc(self):
        bloc = self._bloc(conso=CASA_CONSO)
        hiver = bloc['production']['hiver']
        attendu = pp.moyenne_journaliere_saison(
            pp.PRODUCTIBLE_MENSUEL_VILLE['casablanca']['e_m'], 'hiver') * 10.0
        self.assertAlmostEqual(hiver['kwh_jour'], round(attendu, 1), places=6)
        # Épingle : 10 kWc à Casablanca en hiver ≈ 40,7 kWh/jour (PVcalc).
        self.assertAlmostEqual(hiver['kwh_jour'], 40.7, delta=0.2)
        # L'été produit plus que l'hiver — sinon la saisonnalité est inversée.
        self.assertGreater(bloc['production']['ete']['kwh_jour'],
                           hiver['kwh_jour'])

    def test_pic_est_une_puissance_kw_pas_une_energie(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for saison, serie in bloc['production'].items():
            attendu = serie['kwh_jour'] * max(serie['forme'])
            self.assertAlmostEqual(serie['pic_kw'], attendu,
                                   delta=0.02, msg=saison)
            # Une puissance de pointe reste très en-dessous de l'énergie du
            # jour : c'est exactement la confusion que l'ancien libellé faisait.
            self.assertLess(serie['pic_kw'], serie['kwh_jour'])
        self.assertEqual(bloc['unites']['pic_kw'], 'kW')

    def test_aucune_cle_de_pic_libellee_en_kwh(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for serie in bloc['production'].values():
            for cle in serie:
                if 'pic' in cle:
                    self.assertTrue(cle.endswith('_kw'), cle)
                    self.assertFalse(cle.endswith('_kwh'), cle)

    def test_forme_servie_en_heure_locale_utc_plus_un(self):
        bloc = self._bloc(conso=CASA_CONSO)
        forme = bloc['production']['hiver']['forme']
        self.assertEqual(len(forme), 24)
        self.assertAlmostEqual(sum(forme), 1.0, places=4)
        # PVGIS place le pic de janvier à 12 h UTC → 13 h en heure marocaine.
        self.assertEqual(forme.index(max(forme)), 13)
        self.assertEqual(
            forme, pp.vers_heure_locale(
                pp.profil_production_journalier(
                    saison='hiver', ville='Casablanca')[0]))

    def test_source_tracable(self):
        bloc = self._bloc(conso=CASA_CONSO)
        hiver = bloc['production']['hiver']
        self.assertEqual(hiver['source'], 'pvgis_ville:casablanca')
        self.assertEqual(hiver['source_productible'], 'pvgis_ville:casablanca')

    def test_gps_du_lead_declenche_le_live_mocke(self):
        self.loc.return_value = {'site_adresse': None, 'site_ville': 'Casablanca',
                                 'gps_lat': 33.5, 'gps_lng': -7.6}
        profil = [{'month': 1, 'time': '%02d:00' % h,
                   'G(i)': (900.0 if h == 11 else (100.0 if 7 <= h <= 17 else 0.0))}
                  for h in range(24)]
        pvcalc = {'outputs': {'monthly': {'fixed': [
            {'month': i + 1, 'E_m': 150.0} for i in range(12)]}}}

        def _reponse(url):
            return pvcalc if '/PVcalc?' in url else {
                'outputs': {'daily_profile': profil}}

        with mock.patch.object(pp, '_appel_pvgis', side_effect=_reponse):
            bloc = self._bloc(conso=CASA_CONSO)
        hiver = bloc['production']['hiver']
        self.assertEqual(hiver['source'], 'pvgis_live')
        self.assertEqual(hiver['source_productible'], 'pvgis_live')
        # 150 kWh/mois sur 31/31/28 jours × 10 kWc ≈ 50,1 kWh/jour.
        self.assertAlmostEqual(hiver['kwh_jour'], 50.1, delta=0.2)
        # Pic à 11 h UTC → 12 h locale.
        self.assertEqual(hiver['forme'].index(max(hiver['forme'])), 12)

    def test_ville_inconnue_omet_la_production(self):
        # Jamais de courbe INVENTÉE pour une ville hors table ET hors
        # gazetier (Tombouctou n'est pas au Maroc ; Ifrane, l'ancien
        # fixture, est une ville de table depuis le 31/08/2026).
        bloc = self._bloc(_data(client_city='Tombouctou'), conso=CASA_CONSO)
        self.assertNotIn('production', bloc)
        self.assertIn('consommation', bloc)

    def test_ville_du_gazetier_sert_l_ancre_la_plus_proche(self):
        # Fondateur 31/08/2026 — Skhirat (gazetier, hors table) sert la
        # production de son ancre la plus proche (Bouznika), source nommée.
        bloc = self._bloc(_data(client_city='Skhirat'), conso=CASA_CONSO)
        self.assertIn('production', bloc)
        hiver = bloc['production']['hiver']
        self.assertTrue(
            str(hiver['source_productible']).startswith(
                'pvgis_ville_proche:bouznika'),
            hiver['source_productible'])

    def test_puissance_inconnue_omet_la_production(self):
        bloc = self._bloc(_data(puissance_kwc=None), conso=CASA_CONSO)
        self.assertNotIn('production', bloc)


class ConsommationTests(_CourbesBase):
    def test_niveau_reel_par_saison_depuis_les_factures(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for saison in pp.SAISONS:
            attendu = pp.moyenne_journaliere_saison(CASA_CONSO, saison)
            self.assertAlmostEqual(bloc['consommation'][saison]['kwh_jour'],
                                   round(attendu, 1), places=6, msg=saison)
        # L'été consomme plus (climatisation) : la série le dit, pas nous.
        self.assertGreater(bloc['consommation']['ete']['kwh_jour'],
                           bloc['consommation']['hiver']['kwh_jour'])

    def test_la_forme_de_base_ne_porte_que_kwh_jour_et_forme(self):
        """CJ2b — le serveur sert désormais la forme DE BASE (silhouette
        d'occupation) à côté du niveau ; les couches équipements restent
        composées CÔTÉ PAGE par-dessus elle (``proposalCurve.ts``), jamais ici
        — les recomposer ici les compterait deux fois."""
        bloc = self._bloc(conso=CASA_CONSO)
        for serie in bloc['consommation'].values():
            self.assertEqual(set(serie), {'kwh_jour', 'forme'})

    def test_sans_facture_pas_de_consommation(self):
        for vide in (None, [], [1, 2, 3]):
            bloc = self._bloc(conso=vide)
            self.assertNotIn('consommation', bloc, repr(vide))


class OptionsEtBatterieTests(_CourbesBase):
    def test_deux_options(self):
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['sans', 'avec'])
        self.assertEqual(bloc['batterie_kwh'], 10.0)

    def test_option_sans_batterie_seule(self):
        bloc = self._bloc(
            _data(avec_ok=False, deux_options=False, batterie_kwh_total=None),
            conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['sans'])
        self.assertNotIn('batterie_kwh', bloc)

    def test_option_avec_batterie_seule(self):
        bloc = self._bloc(
            _data(sans_ok=False, deux_options=False, batterie_kwh_total=15.0),
            conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['avec'])
        self.assertEqual(bloc['batterie_kwh'], 15.0)

    def test_mono_option_hybride_sans_batterie_suit_le_stockage_reel(self):
        bloc = self._bloc(
            _data(deux_options=False, batterie_kwh_total=None),
            conso=CASA_CONSO)
        self.assertEqual(bloc['options'], ['sans'])

    def test_aucune_option_valide_omet_la_cle(self):
        bloc = self._bloc(
            _data(sans_ok=False, avec_ok=False, deux_options=False,
                  batterie_kwh_total=None),
            conso=CASA_CONSO)
        self.assertNotIn('options', bloc)


class OccupationTests(_CourbesBase):
    def test_residentiel_present_en_journee_par_defaut(self):
        """Décision terrain du fondateur (21/08/2026), pas une statistique."""
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'],
                         'defaut_residentiel_fondateur')

    def test_non_residentiel_absent_par_defaut(self):
        bloc = self._bloc(_data(mode_installation='industriel'),
                          conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'absence_jour')
        self.assertEqual(bloc['occupation_source'], 'defaut_non_residentiel')

    def test_profil_activite_pro_declare_prime_sur_le_defaut(self):
        self.profil.return_value = 'day'
        bloc = self._bloc(_data(mode_installation='commercial'),
                          conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'], 'lead_profil_activite:day')

    def test_mode_inconnu_traite_comme_non_residentiel(self):
        bloc = self._bloc(_data(mode_installation=None), conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'absence_jour')


# ── L4 (extension fondateur, 21/08/2026) — occupation_jour du lead PRIME ─────
class OccupationLeadTests(_CourbesBase):
    """``crm.Lead.occupation_jour`` (script d'appel) PRIME sur tout le reste
    quand renseigné ; absent ⇒ comportement HISTORIQUE (``OccupationTests``
    ci-dessus, byte-identique — aucun mock de ``occupation_jour_pour_devis``
    n'est posé par ces tests-là, donc le VRAI sélecteur tourne sur
    ``object()`` et renvoie ``None``)."""

    def _bloc_occ(self, occ, data=None):
        with mock.patch('apps.crm.selectors.occupation_jour_pour_devis',
                        return_value=occ):
            return self._bloc(data=data, conso=CASA_CONSO)

    def test_partiel_prime_sur_le_defaut_residentiel(self):
        bloc = self._bloc_occ('partiel')
        self.assertEqual(bloc['occupation'], 'presence_partielle')
        self.assertEqual(bloc['occupation_source'], 'lead_occupation_jour:partiel')

    def test_absent_prime_sur_le_defaut_residentiel(self):
        bloc = self._bloc_occ('absent')
        self.assertEqual(bloc['occupation'], 'absence_jour')
        self.assertEqual(bloc['occupation_source'], 'lead_occupation_jour:absent')

    def test_present_prime_sur_le_defaut_non_residentiel(self):
        bloc = self._bloc_occ('present', _data(mode_installation='industriel'))
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'], 'lead_occupation_jour:present')

    def test_valeur_non_reconnue_ignoree_retombe_sur_le_defaut(self):
        bloc = self._bloc_occ('n_importe_quoi')
        self.assertEqual(bloc['occupation_source'], 'defaut_residentiel_fondateur')

    def test_absent_du_lead_comportement_historique_inchange(self):
        # Aucun mock posé : le VRAI sélecteur tourne sur object() (pas de
        # .lead) ⇒ None ⇒ repli identique à OccupationTests d'avant L4.
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['occupation_source'], 'defaut_residentiel_fondateur')


# ── QJR10 (29/08/2026) — UN SEUL lecteur d'occupation, défaut PRÉSENCE ───────
#
# Avant QJR10, ``services._panneaux_dimensionnement_horaire`` traduisait
# ``lead.occupation_jour`` avec un dict ``drapeaux`` LOCAL et laissait
# ``occupation=None`` quand la question n'avait pas été posée : le moteur
# retombait alors sur la silhouette de repli PARTIELLE, tandis que l'aperçu
# écran retombait, lui, sur le défaut fondateur PRÉSENCE. Le même lead était
# donc dimensionné sur deux journées différentes selon le chemin emprunté.
# Décision fondateur D4 du 29/08/2026 : PRÉSENCE partout.

class _LeadFactice:
    """Lead minimal : ``occupation_jour`` + les 15 champs d'équipement à
    ``None`` (ce que ``crm.selectors.equipements_pour_lead`` lit)."""

    CHAMPS_EQUIP = (
        'equip_piscine', 'equip_piscine_pompe_kw', 'equip_voiture_electrique',
        'equip_ve_km_semaine', 'equip_clim', 'equip_clim_pieces',
        'equip_chauffe_eau_electrique', 'equip_chauffe_eau_kw',
        'equip_chauffe_eau_creneau', 'equip_ve_chargeur_kw', 'equip_ve_creneau',
        'equip_clim_kw', 'equip_piscine_heures_jour', 'equip_clim_creneau',
        'equip_piscine_creneau',
    )

    def __init__(self, occupation_jour=None):
        self.occupation_jour = occupation_jour
        self.facture_hiver = 1800
        self.facture_ete = None
        self.ete_differente = False
        self.ville = 'Casablanca'
        self.gps_lat = None
        self.gps_lng = None
        for champ in self.CHAMPS_EQUIP:
            setattr(self, champ, None)


class OccupationLecteurUniqueTests(SimpleTestCase):
    """CHEMIN 1 — le lecteur de lead seul (devis automatique / tunnel)."""

    def test_les_trois_drapeaux_sont_traduits(self):
        self.assertEqual(cj.occupation_du_lead(_LeadFactice('present')),
                         ('presence_jour', 'lead_occupation_jour:present'))
        self.assertEqual(cj.occupation_du_lead(_LeadFactice('absent')),
                         ('absence_jour', 'lead_occupation_jour:absent'))
        self.assertEqual(cj.occupation_du_lead(_LeadFactice('partiel')),
                         ('presence_partielle', 'lead_occupation_jour:partiel'))

    def test_lead_sans_reponse_retombe_sur_le_defaut_fondateur(self):
        self.assertEqual(cj.occupation_du_lead(_LeadFactice(None)),
                         cj.DEFAUT_RESIDENTIEL)
        self.assertEqual(cj.DEFAUT_RESIDENTIEL,
                         ('presence_jour', 'defaut_residentiel_fondateur'))

    def test_valeur_non_reconnue_ou_lead_absent_retombe_sur_le_defaut(self):
        self.assertEqual(cj.occupation_du_lead(_LeadFactice('n_importe_quoi')),
                         cj.DEFAUT_RESIDENTIEL)
        self.assertEqual(cj.occupation_du_lead(None), cj.DEFAUT_RESIDENTIEL)

    def test_le_repli_partielle_ne_sert_plus_de_defaut_a_ce_chemin(self):
        """La silhouette de repli existe toujours pour un drapeau ILLISIBLE
        en aval, mais elle n'est plus ce que ce chemin CHOISIT par défaut."""
        self.assertEqual(cj.OCCUPATION_REPLI, cj.OCCUPATION_PARTIELLE)
        self.assertNotEqual(cj.occupation_du_lead(_LeadFactice(None))[0],
                            cj.OCCUPATION_REPLI)


class OccupationDevisMemeLecteurTests(_CourbesBase):
    """CHEMIN 2 — l'aperçu écran (devis) passe par le MÊME traducteur."""

    def _source(self, occ):
        with mock.patch('apps.crm.selectors.occupation_jour_pour_devis',
                        return_value=occ):
            return cj.occupation_du_devis(object(), _data())

    def test_les_trois_drapeaux_donnent_le_meme_couple_que_le_lecteur_lead(self):
        for reponse in ('present', 'absent', 'partiel'):
            self.assertEqual(
                self._source(reponse),
                cj.occupation_du_lead(_LeadFactice(reponse)), msg=reponse)

    def test_sans_reponse_le_defaut_est_le_meme_couple(self):
        self.assertEqual(self._source(None), cj.DEFAUT_RESIDENTIEL)
        self.assertEqual(self._source(None),
                         cj.occupation_du_lead(_LeadFactice(None)))

    def test_le_defaut_non_residentiel_reste_intact(self):
        """Non-régression : hors résidentiel et sans réponse du lead, le
        défaut historique ``absence_jour`` ne bouge PAS (D4 ne concerne que
        les deux chemins résidentiels)."""
        with mock.patch('apps.crm.selectors.occupation_jour_pour_devis',
                        return_value=None):
            self.assertEqual(
                cj.occupation_du_devis(
                    object(), _data(mode_installation='industriel')),
                ('absence_jour', 'defaut_non_residentiel'))


class OccupationPipelineAutoTests(SimpleTestCase):
    """Le pipeline auto/tunnel remet bien au moteur ce que le lecteur unique
    a résolu — c'est CE branchement qui manquait (dict ``drapeaux`` local)."""

    def _occupation_remise_au_moteur(self, lead):
        from apps.ventes import services

        vu = {}

        def _espion(**kwargs):
            vu.update(kwargs)
            return {'recommandation': {'panneaux': 12, 'panel_watt': 550}}

        with mock.patch('apps.ventes.dimensionnement.recommander_taille',
                        _espion):
            nb, _watt, source, _avec = (
                services._panneaux_dimensionnement_horaire(
                    lead=lead, company=object(), phase=None))
        self.assertEqual(source, 'moteur_horaire')
        self.assertEqual(nb, 12)
        return vu.get('occupation')

    def test_sans_reponse_le_moteur_recoit_le_defaut_fondateur_presence(self):
        """ROUGE avant QJR10 : le moteur recevait ``None`` (⇒ repli
        PARTIELLE), alors que l'écran dimensionnait sur PRÉSENCE."""
        self.assertEqual(
            self._occupation_remise_au_moteur(_LeadFactice(None)),
            cj.DEFAUT_RESIDENTIEL[0])

    def test_les_trois_reponses_reelles_du_lead_restent_souveraines(self):
        for reponse, attendu in (('present', 'presence_jour'),
                                 ('absent', 'absence_jour'),
                                 ('partiel', 'presence_partielle')):
            self.assertEqual(
                self._occupation_remise_au_moteur(_LeadFactice(reponse)),
                attendu, msg=reponse)


# ── CJ2b (21/08/2026) — la forme de base de consommation devient SERVEUR ────
class FormeConsommationServieTests(_CourbesBase):
    """Le serveur sert désormais la silhouette d'occupation (24 parts, somme
    1,0) sur CHAQUE saison de consommation servie, et nomme sa provenance."""

    def test_chaque_saison_porte_une_forme_de_24_parts_qui_somme_a_un(self):
        bloc = self._bloc(conso=CASA_CONSO)
        for saison, serie in bloc['consommation'].items():
            self.assertIn('forme', serie, saison)
            self.assertEqual(len(serie['forme']), 24, saison)
            self.assertAlmostEqual(sum(serie['forme']), 1.0, places=4,
                                   msg=saison)

    def test_la_source_nomme_l_occupation_reellement_servie(self):
        bloc = self._bloc(conso=CASA_CONSO)
        # Défaut résidentiel fondateur (OccupationTests) : présent en journée.
        self.assertEqual(bloc['occupation'], 'presence_jour')
        self.assertEqual(bloc['consommation_forme_source'],
                         'silhouette_occupation:presence_jour')

    def test_la_forme_suit_l_occupation_reellement_servie_pas_un_defaut_fige(self):
        with mock.patch('apps.crm.selectors.occupation_jour_pour_devis',
                        return_value='absent'):
            bloc = self._bloc(conso=CASA_CONSO)
        self.assertEqual(bloc['occupation'], 'absence_jour')
        self.assertEqual(bloc['consommation_forme_source'],
                         'silhouette_occupation:absence_jour')
        attendu = cj.silhouette_occupation('absence_jour')
        for saison, serie in bloc['consommation'].items():
            self.assertEqual(serie['forme'], attendu, saison)

    def test_forme_absente_sans_bloc_consommation(self):
        # Aucune facture ⇒ pas de bloc consommation ⇒ rien à sourcer.
        bloc = self._bloc(conso=[])
        self.assertNotIn('consommation', bloc)
        self.assertNotIn('consommation_forme_source', bloc)

    def test_la_forme_de_base_est_identique_a_la_production_servie(self):
        # « part du total du jour, somme = 1 » : même unité que la forme de
        # production déjà servie (bloc['unites']['forme']).
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertIn('forme', bloc['unites'])
        self.assertEqual(bloc['unites']['forme'],
                         'part du total du jour (somme = 1)')


class OmissionTests(_CourbesBase):
    def test_rien_a_servir_renvoie_none(self):
        # Ville inconnue ET aucune facture → la page garde son affichage actuel.
        self.assertIsNone(self._bloc(_data(client_city='Tombouctou'), conso=[]))

    def test_note_horaire_dit_le_cas_ramadan(self):
        bloc = self._bloc(conso=CASA_CONSO)
        self.assertIn('UTC+1', bloc['note_horaire'])
        self.assertIn('Ramadan', bloc['note_horaire'])

    def test_donnee_illisible_ne_casse_jamais_la_page(self):
        self.assertIsNone(cj.construire_courbes_journalieres(
            object(), None, monthly_consumption=None))


# ── L4 (21/08/2026) — Équipements du lead : couches sourcées de la courbe ────
class EquipementsTests(_CourbesBase):
    """``apps.crm.selectors.equipements_pour_devis`` mocké par test (comme
    ``site_location_for_devis``/``profil_activite_pour_devis`` ci-dessus) : la
    base ``_CourbesBase`` laisse le VRAI sélecteur tourner sur un ``object()``
    (aucun ``.lead``) ⇒ ``{}`` ⇒ tests existants byte-identiques (pinné par
    ``ConsommationTests.test_la_forme_24h_de_consommation_reste_cote_page``)."""

    def _bloc_equip(self, equip, data=None, conso=None):
        with mock.patch('apps.crm.selectors.equipements_pour_devis',
                        return_value=equip):
            return self._bloc(data=data, conso=CASA_CONSO if conso is None else conso)

    def test_aucun_equipement_ne_change_rien(self):
        bloc = self._bloc_equip({})
        self.assertNotIn('equipements', bloc)
        for saison in pp.SAISONS:
            attendu = round(pp.moyenne_journaliere_saison(CASA_CONSO, saison), 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu)

    def test_piscine_avec_puissance_reelle_redistribue_sans_changer_le_niveau(self):
        bloc = self._bloc_equip({'piscine': True, 'piscine_pompe_kw': 1.5})
        self.assertEqual(bloc['equipements']['piscine'], {
            'kw': 1.5,
            'heures': list(range(10, 18)),
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'memo_2026-08-21_etage2:piscine_bloc_10_18h',
        })
        # Redistribution PURE : le niveau kwh_jour reste EXACTEMENT celui des
        # factures — la piscine ne fait que déplacer la forme, jamais ajouter.
        for saison in pp.SAISONS:
            attendu = round(pp.moyenne_journaliere_saison(CASA_CONSO, saison), 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu,
                             msg=saison)

    def test_piscine_sans_puissance_ne_produit_aucune_couche(self):
        # Bool vrai mais AUCUNE grandeur réelle saisie ⇒ omission (jamais un
        # défaut de puissance inventé).
        bloc = self._bloc_equip({'piscine': True, 'piscine_pompe_kw': None})
        self.assertNotIn('equipements', bloc)

    def test_clim_kw_derive_du_nombre_de_pieces(self):
        bloc = self._bloc_equip({'clim': True, 'clim_pieces': 2})
        self.assertEqual(bloc['equipements']['clim'], {
            'kw': 2.8,  # 2 pièces × 1,4 kWh/h (mémo, 12000 BTU non-inverter)
            'heures': list(range(13, 21)),
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h',
        })

    def test_ve_ajoute_au_niveau_toutes_saisons(self):
        # 140 km/sem × 19,8 kWh/100 km ADEME ÷ 7 = 3,96 kWh/jour — la SEULE
        # couche qui change kwh_jour (charge future, absente des factures).
        bloc = self._bloc_equip(
            {'voiture_electrique': True, 've_km_semaine': 140})
        self.assertEqual(bloc['equipements']['ve'], {
            'kwh_jour': 3.96,
            'heures': [21, 22, 23, 0, 1, 2, 3, 4, 5],
            'saisons': None,
            'mode': 'addition',
            'source': 'memo_2026-08-21_etage2:ve_ademe_19_8kwh_100km',
        })
        for saison in pp.SAISONS:
            attendu = round(
                pp.moyenne_journaliere_saison(CASA_CONSO, saison) + 3.96, 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu,
                             msg=saison)

    def test_ve_sans_km_saisi_ne_produit_aucune_couche(self):
        # « PAS de défaut km, saisie obligatoire » (mémo) — bool seul n'ajoute
        # rien tant que le km/semaine réel n'est pas connu.
        bloc = self._bloc_equip(
            {'voiture_electrique': True, 've_km_semaine': None})
        self.assertNotIn('equipements', bloc)
        for saison in pp.SAISONS:
            attendu = round(pp.moyenne_journaliere_saison(CASA_CONSO, saison), 1)
            self.assertEqual(bloc['consommation'][saison]['kwh_jour'], attendu)

    def test_chauffe_eau_ne_produit_jamais_de_couche(self):
        # Aucune fenêtre/puissance sourcée pour le chauffe-eau (mémo : kWh/
        # personne/an sans champ « nombre de personnes ») — omission voulue,
        # même quand le booléen est vrai.
        bloc = self._bloc_equip({'chauffe_eau_electrique': True})
        self.assertNotIn('equipements', bloc)

    def test_plusieurs_couches_actives_coexistent(self):
        bloc = self._bloc_equip({
            'piscine': True, 'piscine_pompe_kw': 1.0,
            'clim': True, 'clim_pieces': 1,
            'voiture_electrique': True, 've_km_semaine': 70,
            'chauffe_eau_electrique': True,
        })
        self.assertEqual(set(bloc['equipements']), {'piscine', 'clim', 've'})

    def test_equipements_absent_sans_courbe_de_conso_a_ajuster(self):
        # Piscine renseignée mais AUCUNE facture ⇒ pas de bloc consommation
        # ⇒ rien à composer : la clé equipements reste absente.
        bloc = self._bloc_equip(
            {'piscine': True, 'piscine_pompe_kw': 1.5}, conso=[])
        self.assertNotIn('consommation', bloc)
        self.assertNotIn('equipements', bloc)


class EquipementsLBackTests(_CourbesBase):
    """L-BACK (24/08/2026) — les 4 grandeurs complémentaires (kW/créneau)."""

    def _bloc_equip(self, equip, data=None, conso=None):
        with mock.patch('apps.crm.selectors.equipements_pour_devis',
                        return_value=equip):
            return self._bloc(data=data, conso=CASA_CONSO if conso is None else conso)

    def test_piscine_heures_jour_remplace_la_duree_par_defaut(self):
        bloc = self._bloc_equip({
            'piscine': True, 'piscine_pompe_kw': 1.5,
            'piscine_heures_jour': 4,
        })
        self.assertEqual(bloc['equipements']['piscine'], {
            'kw': 1.5,
            'heures': [10, 11, 12, 13],  # 4h à partir de 10h (même départ)
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'lead:equip_piscine_heures_jour',
        })

    def test_piscine_sans_heures_jour_garde_le_defaut(self):
        bloc = self._bloc_equip({
            'piscine': True, 'piscine_pompe_kw': 1.5,
            'piscine_heures_jour': None,
        })
        self.assertEqual(bloc['equipements']['piscine']['heures'],
                         list(range(10, 18)))
        self.assertEqual(bloc['equipements']['piscine']['source'],
                         'memo_2026-08-21_etage2:piscine_bloc_10_18h')

    def test_clim_kw_declare_remplace_l_estimation_par_piece(self):
        bloc = self._bloc_equip({
            'clim': True, 'clim_pieces': 5, 'clim_kw': 4.2,
        })
        self.assertEqual(bloc['equipements']['clim'], {
            'kw': 4.2,
            'heures': list(range(13, 21)),
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'lead:equip_clim_kw',
        })

    def test_clim_kw_absent_retombe_sur_l_estimation_par_piece(self):
        bloc = self._bloc_equip({'clim': True, 'clim_pieces': 2, 'clim_kw': None})
        self.assertEqual(bloc['equipements']['clim']['kw'], 2.8)
        self.assertEqual(bloc['equipements']['clim']['source'],
                         'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h')

    def test_ve_chargeur_et_creneau_resserrent_la_fenetre(self):
        # 140 km/sem × 19,8/100 ÷ 7 = 3,96 kWh/jour ; à 7,4 kW ⇒ 3,96/7,4×60
        # ≈ 32 min ⇒ 1 seule heure nécessaire dans le créneau 'nuit'.
        bloc = self._bloc_equip({
            'voiture_electrique': True, 've_km_semaine': 140,
            've_chargeur_kw': 7.4, 've_creneau': 'nuit',
        })
        couche = bloc['equipements']['ve']
        self.assertEqual(couche['kwh_jour'], 3.96)
        self.assertEqual(couche['heures'], [21])
        self.assertEqual(
            couche['source'],
            'memo_2026-08-21_etage2:ve_ademe_19_8kwh_100km'
            '+lead:equip_ve_chargeur_kw+creneau')

    def test_ve_sans_chargeur_garde_la_fenetre_par_defaut(self):
        bloc = self._bloc_equip({
            'voiture_electrique': True, 've_km_semaine': 140,
            've_chargeur_kw': None, 've_creneau': None,
        })
        self.assertEqual(bloc['equipements']['ve']['heures'],
                         [21, 22, 23, 0, 1, 2, 3, 4, 5])

    def test_chauffe_eau_kw_et_creneau_composent_une_couche(self):
        bloc = self._bloc_equip({
            'chauffe_eau_electrique': True,
            'chauffe_eau_kw': 2.2, 'chauffe_eau_creneau': 'nuit',
        })
        self.assertEqual(bloc['equipements']['chauffe_eau'], {
            'kw': 2.2,
            'heures': [23, 0, 1, 2, 3, 4, 5],
            'saisons': None,
            'mode': 'redistribution',
            'source': 'lead:equip_chauffe_eau_kw+creneau',
        })

    def test_chauffe_eau_moitie_de_paire_ne_produit_rien(self):
        bloc = self._bloc_equip({
            'chauffe_eau_kw': 2.2, 'chauffe_eau_creneau': None,
        })
        self.assertNotIn('equipements', bloc)
        bloc2 = self._bloc_equip({
            'chauffe_eau_kw': None, 'chauffe_eau_creneau': 'nuit',
        })
        self.assertNotIn('equipements', bloc2)


class EquipementsLBack2Tests(_CourbesBase):
    """L-BACK2 (24/08/2026) — créneaux clim/piscine (comble la lacune : ces
    deux couches n'avaient AUCUNE granularité horaire, contrairement à la
    paire kW/créneau du chauffe-eau/VE)."""

    def _bloc_equip(self, equip, data=None, conso=None):
        with mock.patch('apps.crm.selectors.equipements_pour_devis',
                        return_value=equip):
            return self._bloc(data=data, conso=CASA_CONSO if conso is None else conso)

    def test_clim_creneau_deplace_la_fenetre_sans_toucher_la_puissance(self):
        bloc = self._bloc_equip({
            'clim': True, 'clim_pieces': 2, 'clim_kw': 3.5,
            'clim_creneau': 'matin',
        })
        self.assertEqual(bloc['equipements']['clim'], {
            'kw': 3.5,
            'heures': list(range(8, 13)),
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'lead:equip_clim_kw+lead:equip_clim_creneau',
        })

    def test_clim_sans_creneau_garde_la_fenetre_par_defaut(self):
        bloc = self._bloc_equip({
            'clim': True, 'clim_pieces': 2, 'clim_kw': None,
            'clim_creneau': None,
        })
        self.assertEqual(bloc['equipements']['clim']['heures'],
                         list(range(13, 21)))
        self.assertEqual(bloc['equipements']['clim']['source'],
                         'memo_2026-08-21_etage2:clim_12000btu_1p4kwh_h')

    def test_clim_creneau_inconnu_est_ignore(self):
        # Valeur hors choices (ne devrait jamais arriver via l'API, mais le
        # moteur ne doit jamais planter) ⇒ repli sur la fenêtre par défaut.
        bloc = self._bloc_equip({
            'clim': True, 'clim_pieces': 2, 'clim_creneau': 'inconnu',
        })
        self.assertEqual(bloc['equipements']['clim']['heures'],
                         list(range(13, 21)))

    def test_piscine_creneau_deplace_le_depart_sans_toucher_la_duree(self):
        bloc = self._bloc_equip({
            'piscine': True, 'piscine_pompe_kw': 1.5,
            'piscine_creneau': 'matin',
        })
        self.assertEqual(bloc['equipements']['piscine'], {
            'kw': 1.5,
            'heures': list(range(6, 14)),  # 8h (défaut) à partir de 6h
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'lead:equip_piscine_creneau',
        })

    def test_piscine_creneau_et_heures_jour_se_composent(self):
        bloc = self._bloc_equip({
            'piscine': True, 'piscine_pompe_kw': 1.5,
            'piscine_heures_jour': 4, 'piscine_creneau': 'soir',
        })
        self.assertEqual(bloc['equipements']['piscine'], {
            'kw': 1.5,
            'heures': [16, 17, 18, 19],  # 4h à partir de 16h (créneau soir)
            'saisons': ['ete'],
            'mode': 'redistribution',
            'source': 'lead:equip_piscine_heures_jour+equip_piscine_creneau',
        })

    def test_piscine_sans_creneau_ni_heures_jour_garde_le_defaut(self):
        bloc = self._bloc_equip({
            'piscine': True, 'piscine_pompe_kw': 1.5,
            'piscine_heures_jour': None, 'piscine_creneau': None,
        })
        self.assertEqual(bloc['equipements']['piscine']['heures'],
                         list(range(10, 18)))
        self.assertEqual(bloc['equipements']['piscine']['source'],
                         'memo_2026-08-21_etage2:piscine_bloc_10_18h')


# ── QJR15 (29/08/2026) — la couche chauffe-eau ENTRE dans la forme ───────────
#
# LE DÉFAUT : ``_equipements`` composait bien une couche ``chauffe_eau``
# (mode ``redistribution``) depuis les données RÉELLES du client, et
# ``etude_horaire.estimation_conso_mensuelle`` la publiait comme un ajout
# mensuel en kWh — mais le composeur de forme n'itérait que sur
# ``('piscine', 'clim')`` : la répartition MONTRÉE et la forme sur laquelle les
# économies étaient CALCULÉES décrivaient deux clients différents.

CHAUFFE_EAU_COUCHE = {
    'chauffe_eau': {
        'kw': 2.4,
        'heures': list(cj.CHAUFFE_EAU_CRENEAUX['soir']),   # 18h, 19h, 20h
        'saisons': None,
        'mode': 'redistribution',
        'source': 'lead:equip_chauffe_eau_kw+creneau',
    },
}

PISCINE_COUCHE = {
    'piscine': {'kw': 1.1, 'heures': list(range(10, 18)), 'saisons': ['ete'],
                'mode': 'redistribution', 'source': 'test'},
}

CLIM_COUCHE = {
    'clim': {'kw': 1.4, 'heures': list(range(13, 21)), 'saisons': ['ete'],
             'mode': 'redistribution', 'source': 'test'},
}

VE_COUCHE = {
    've': {'kwh_jour': 4.0, 'heures': [21, 22, 23, 0, 1, 2], 'saisons': None,
           'mode': 'addition', 'source': 'test'},
}


class ChauffeEauDansLaFormeTests(SimpleTestCase):
    """La couche chauffe-eau est PLACÉE par le composeur, pas seulement
    publiée."""

    def test_la_couche_chauffe_eau_est_rendue_par_le_composeur(self):
        """ROUGE avant QJR15 : ``couches`` ne contenait que piscine/clim."""
        _forme, couches = cj.forme_consommation_detaillee(
            20.0, cj.OCCUPATION_PRESENCE, saison='ete',
            equipements=CHAUFFE_EAU_COUCHE)
        self.assertIn('chauffe_eau', couches)
        self.assertEqual(couches['chauffe_eau']['kw'], 2.4)
        self.assertEqual(couches['chauffe_eau']['heures'], [18, 19, 20])

    def test_l_energie_placee_est_la_bosse_RENORMALISEE(self):
        """Dérivation, pas un chiffre posé : 20 kWh de base + une bosse de
        2,4 kW × 3 h = 7,2 kWh ⇒ facteur 20 ÷ 27,2 ; la couche pèse donc
        2,4 × 20 ÷ 27,2 = 1,764706 kWh dans CHACUNE de ses trois heures."""
        _forme, couches = cj.forme_consommation_detaillee(
            20.0, cj.OCCUPATION_PRESENCE, saison='ete',
            equipements=CHAUFFE_EAU_COUCHE)
        heures_kwh = couches['chauffe_eau']['heures_kwh']
        for heure in (18, 19, 20):
            self.assertAlmostEqual(heures_kwh[heure], 1.764706, places=6)
        for heure in range(24):
            if heure not in (18, 19, 20):
                self.assertEqual(heures_kwh[heure], 0.0, 'heure %d' % heure)

    def test_la_forme_grossit_sur_la_fenetre_du_chauffe_eau(self):
        nu = cj.forme_consommation_kwh(20.0, cj.OCCUPATION_PRESENCE,
                                       saison='ete')
        avec = cj.forme_consommation_kwh(
            20.0, cj.OCCUPATION_PRESENCE, saison='ete',
            equipements=CHAUFFE_EAU_COUCHE)
        fenetre = (18, 19, 20)
        self.assertGreater(sum(avec[h] for h in fenetre),
                           sum(nu[h] for h in fenetre))

    def test_le_total_du_jour_ne_bouge_pas_d_un_kwh(self):
        """Le chauffe-eau existe DÉJÀ dans la facture : seule la forme change."""
        forme = cj.forme_consommation_kwh(
            20.0, cj.OCCUPATION_PRESENCE, saison='ete',
            equipements=CHAUFFE_EAU_COUCHE)
        self.assertAlmostEqual(sum(forme), 20.0, places=9)

    def test_le_chauffe_eau_n_est_pas_saisonnier(self):
        """Contrairement à la piscine et à la clim, sa couche n'a pas de
        saison : elle est placée en hiver comme en été."""
        for saison in cj.SAISONS:
            _forme, couches = cj.forme_consommation_detaillee(
                20.0, cj.OCCUPATION_PRESENCE, saison=saison,
                equipements=CHAUFFE_EAU_COUCHE)
            self.assertIn('chauffe_eau', couches, msg=saison)


class CouchesPublieesEgalesCouchesIntegreesTests(SimpleTestCase):
    """« Ce qui est publié est ce qui est intégré » — la liste des couches de
    redistribution a UN seul propriétaire (``cj.COUCHES_REDISTRIBUTION``), lu
    par le composeur de forme ET par la décomposition mensuelle."""

    def _tout(self):
        equip = {}
        equip.update(PISCINE_COUCHE)
        equip.update(CLIM_COUCHE)
        equip.update(CHAUFFE_EAU_COUCHE)
        return equip

    def test_le_composeur_et_la_decomposition_lisent_la_meme_liste(self):
        from apps.ventes import etude_horaire as eh

        self.assertEqual(cj.COUCHES_REDISTRIBUTION,
                         ('piscine', 'clim', 'chauffe_eau'))
        self.assertIs(eh.COUCHES_REDISTRIBUTION, cj.COUCHES_REDISTRIBUTION)

    def test_en_ete_les_couches_publiees_sont_exactement_les_integrees(self):
        from apps.ventes.etude_horaire import estimation_conso_mensuelle

        equip = self._tout()
        _forme, couches = cj.forme_consommation_detaillee(
            30.0, cj.OCCUPATION_PRESENCE, saison='ete', equipements=equip)
        estimation = estimation_conso_mensuelle(CASA_CONSO, equip)
        self.assertEqual(set(estimation['ajouts']), set(couches))
        self.assertEqual(set(couches), {'piscine', 'clim', 'chauffe_eau'})

    def test_en_hiver_seul_le_chauffe_eau_reste_integre(self):
        """Piscine et clim sont hors saison : elles ne sont ni placées ni
        publiées ce mois-là (leur ajout de janvier vaut zéro)."""
        from apps.ventes.etude_horaire import estimation_conso_mensuelle

        equip = self._tout()
        _forme, couches = cj.forme_consommation_detaillee(
            30.0, cj.OCCUPATION_PRESENCE, saison='hiver', equipements=equip)
        self.assertEqual(set(couches), {'chauffe_eau'})
        estimation = estimation_conso_mensuelle(CASA_CONSO, equip)
        self.assertEqual(estimation['ajouts']['piscine'][0], 0.0)
        self.assertEqual(estimation['ajouts']['clim'][0], 0.0)
        self.assertGreater(estimation['ajouts']['chauffe_eau'][0], 0.0)

    def test_le_total_publie_retombe_sur_la_facture_chauffe_eau_compris(self):
        """La somme des couches publiées (base + ajouts de redistribution)
        égale la consommation réelle — donc la même énergie que la forme
        intégrée, qui somme elle aussi au niveau facture."""
        from apps.ventes.etude_horaire import estimation_conso_mensuelle

        estimation = estimation_conso_mensuelle(CASA_CONSO, self._tout())
        for index, attendu in enumerate(CASA_CONSO):
            self.assertAlmostEqual(
                estimation['totale_mensuelle'][index], float(attendu),
                delta=0.02, msg='mois %d' % (index + 1))

    def test_le_ve_reste_le_seul_ajout_par_dessus_le_total(self):
        """Non-régression de la distinction redistribution/addition : le VE
        n'entre PAS dans COUCHES_REDISTRIBUTION."""
        from apps.ventes.etude_horaire import estimation_conso_mensuelle

        self.assertNotIn('ve', cj.COUCHES_REDISTRIBUTION)
        equip = dict(VE_COUCHE)
        equip.update(CHAUFFE_EAU_COUCHE)
        estimation = estimation_conso_mensuelle(CASA_CONSO, equip)
        for index, attendu in enumerate(CASA_CONSO):
            self.assertGreater(estimation['totale_mensuelle'][index],
                               float(attendu), 'mois %d' % (index + 1))


class SansChauffeEauRienNeChangeTests(SimpleTestCase):
    """« Golden inchangé pour un lead sans chauffe-eau » : aucun chemin sans
    couche chauffe-eau utilisable ne bouge d'un chiffre."""

    def _formes(self, equipements, saison='ete'):
        return cj.forme_consommation_detaillee(
            20.0, cj.OCCUPATION_PRESENCE, saison=saison,
            equipements=equipements)

    def _piscine_clim(self):
        equip = {}
        equip.update(PISCINE_COUCHE)
        equip.update(CLIM_COUCHE)
        return equip

    def test_lead_sans_chauffe_eau_forme_identique(self):
        forme, couches = self._formes(self._piscine_clim())
        self.assertEqual(set(couches), {'piscine', 'clim'})
        self.assertAlmostEqual(sum(forme), 20.0, places=9)

    def test_une_couche_chauffe_eau_sans_puissance_est_ignoree(self):
        """Le composeur n'invente rien : sans ``kw`` utilisable, la couche est
        absente et la forme est celle d'un lead sans chauffe-eau, à l'octet."""
        avec_couche_vide = self._piscine_clim()
        avec_couche_vide['chauffe_eau'] = {
            'kw': 0, 'heures': [18, 19, 20], 'saisons': None,
            'mode': 'redistribution', 'source': 'test'}
        attendue, couches_attendues = self._formes(self._piscine_clim())
        obtenue, couches_obtenues = self._formes(avec_couche_vide)
        self.assertEqual([round(v, 12) for v in obtenue],
                         [round(v, 12) for v in attendue])
        self.assertEqual(set(couches_obtenues), set(couches_attendues))

    def test_aucun_equipement_forme_de_base_intacte(self):
        nu, couches = self._formes(None)
        self.assertEqual(couches, {})
        self.assertEqual(
            [round(v, 12) for v in nu],
            [round(part * 20.0, 12)
             for part in cj.silhouette_jour(cj.OCCUPATION_PRESENCE,
                                            saison='ete')])
