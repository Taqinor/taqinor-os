"""COUVBAT (ordre fondateur, 26/08/2026) — clé ``couverture_batterie`` du
payload public de la proposition (contrat
``apps/ventes/contract_samples/couverture_batterie.json``).

DEUX PROMESSES À ÉPINGLER, ET UNE SEULE SOURCE.

1. COUVERTURE — à chaque cran du curseur « N batteries », la page doit pouvoir
   dire ce que le client CONSOMME et qui le lui fournit, heure par heure. Les
   trois bandes (solaire direct / batterie / réseau) somment donc EXACTEMENT à
   la consommation de l'heure : une bande qui déborderait dessinerait de
   l'énergie que personne ne produit.
2. AUTONOMIE COMPLÈTE — le nombre de batteries qui couvrirait tout le jour ET
   toute la nuit vient du MÊME plafond que le balayage de stockage
   (``déficit maximal ÷ rendement``), et il DIT quand il dépasse ce que ce toit
   remplit chaque jour au lieu de se faire passer pour une offre.

Fixtures calquées sur ``test_payload_paliers_batterie.py`` : Casablanca est
dans la table de référence PVGIS, aucun accès réseau n'est nécessaire.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.etude_horaire import (
    BATTERY_ROUNDTRIP,
    COUVERTURE_PACKS_PLAFOND,
    couverture_batterie_publique,
    jours_types_annee,
    simuler_batterie_jour,
)
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import (
    _couverture_batterie_publique,
    _paliers_curseur_batterie,
)

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent / 'contract_samples'
           / 'couverture_batterie.json')

#: Profil de référence des tests purs : villa 8,5 kWc à Casablanca, 900 kWh de
#: consommation par mois. Ces entrées ne sont PAS un chiffre client — ce sont
#: les entrées d'un cas de test, comme les fixtures voisines.
KWC = 8.5
CONSO_12 = [900.0] * 12
CAP_PACK = 4.6


def _bloc(nb_packs_max=4, **kwargs):
    return couverture_batterie_publique(
        kwc=KWC, conso_kwh_mensuelles=CONSO_12,
        capacite_utile_pack_kwh=CAP_PACK, nb_packs_max=nb_packs_max,
        ville='Casablanca', **kwargs)


# ═══════════════════════════════════════════════════════════════════════════
# 1. La ventilation horaire du simulateur — additive, jamais un second moteur
# ═══════════════════════════════════════════════════════════════════════════

class VentilationHoraireTests(SimpleTestCase):
    """``simuler_batterie_jour`` rend désormais AUSSI ses 24 heures. Le total
    ne bouge pas d'un centième : c'est la même énergie, simplement gardée
    heure par heure au lieu d'être sommée tout de suite."""

    CONSO = [0.5] * 6 + [1.0] * 6 + [1.2] * 6 + [2.5] * 6
    PROD = [0.0] * 6 + [2.0] * 8 + [0.0] * 10

    def test_les_24_heures_somment_au_total_restitue(self):
        r = simuler_batterie_jour(self.CONSO, self.PROD, 8.0)
        self.assertEqual(len(r['restitue_24h']), 24)
        self.assertEqual(len(r['charge_24h']), 24)
        self.assertAlmostEqual(sum(r['restitue_24h']), r['restitue_kwh'],
                               places=6)
        self.assertAlmostEqual(sum(r['charge_24h']), r['charge_kwh'], places=6)

    def test_la_batterie_ne_restitue_qu_aux_heures_deficitaires(self):
        """Une heure où le soleil couvre déjà tout n'a rien à restituer — la
        bande « batterie » y est nulle, sinon le dessin ferait croire à un
        stockage qui sert en plein midi."""
        r = simuler_batterie_jour(self.CONSO, self.PROD, 8.0)
        for heure in range(24):
            if self.PROD[heure] >= self.CONSO[heure]:
                self.assertEqual(r['restitue_24h'][heure], 0.0)

    def test_capacite_nulle_rend_des_series_de_zeros_jamais_none(self):
        r = simuler_batterie_jour(self.CONSO, self.PROD, 0)
        self.assertEqual(r['restitue_24h'], [0.0] * 24)
        self.assertEqual(r['charge_24h'], [0.0] * 24)


# ═══════════════════════════════════════════════════════════════════════════
# 2. ``couverture_batterie_publique`` — pur, aucune BD
# ═══════════════════════════════════════════════════════════════════════════

class CouvertureBatteriePubliqueTests(SimpleTestCase):

    def test_chaque_heure_somme_exactement_a_la_consommation(self):
        """LA garde centrale : direct + batterie + réseau == consommation de
        l'heure, sur chaque jour type et à chaque cran du curseur. La tolérance
        est celle de l'arrondi publié (3 décimales × 3 bandes)."""
        bloc = _bloc()
        jours, _av, _src = jours_types_annee(
            kwc=KWC, conso_kwh_mensuelles=CONSO_12, ville='Casablanca')
        conso_par_mois = {j['mois']: j['conso_24h'] for j in jours}
        for pas in bloc['pas']:
            for mois, courbes in pas['jours_types'].items():
                conso = conso_par_mois[int(mois)]
                for heure in range(24):
                    somme = (courbes['direct_kwh'][heure]
                             + courbes['batterie_kwh'][heure]
                             + courbes['reseau_kwh'][heure])
                    self.assertAlmostEqual(somme, conso[heure], places=2)

    def test_les_quatre_mois_publics_et_24_valeurs_par_bande(self):
        bloc = _bloc()
        for pas in bloc['pas']:
            self.assertEqual(set(pas['jours_types']), {'1', '4', '7', '11'})
            for courbes in pas['jours_types'].values():
                for bande in ('direct_kwh', 'batterie_kwh', 'reseau_kwh'):
                    self.assertEqual(len(courbes[bande]), 24)
                    self.assertTrue(all(v >= 0 for v in courbes[bande]))

    def test_la_couverture_monte_avec_le_nombre_de_batteries(self):
        """Une batterie de plus ne peut pas couvrir MOINS : si ce test tombe,
        le curseur raconterait au client l'inverse de la physique."""
        bloc = _bloc()
        couvertures = [p['couverture_pct'] for p in bloc['pas']]
        self.assertEqual(couvertures, sorted(couvertures))
        self.assertLessEqual(couvertures[-1], 100.0)

    def test_zero_batterie_ne_restitue_rien(self):
        pas0 = _bloc()['pas'][0]
        self.assertEqual(pas0['nb_packs'], 0)
        self.assertEqual(pas0['capacite_kwh'], 0.0)
        self.assertEqual(pas0['batterie_annuel_kwh'], 0.0)
        for courbes in pas0['jours_types'].values():
            self.assertEqual(courbes['batterie_kwh'], [0.0] * 24)

    def test_annuel_coherent_direct_plus_batterie_plus_reseau(self):
        bloc = _bloc()
        for pas in bloc['pas']:
            total = (pas['direct_annuel_kwh'] + pas['batterie_annuel_kwh']
                     + pas['reseau_annuel_kwh'])
            self.assertAlmostEqual(total, bloc['conso_annuelle_kwh'], places=1)

    def test_capacite_du_cran_est_n_fois_le_pack_du_devis(self):
        """Le curseur est indexé par NOMBRE DE PACKS et la capacité en découle
        — jamais un module de catalogue codé en dur (règle CAPUTIL)."""
        bloc = _bloc()
        self.assertEqual(bloc['capacite_utile_pack_kwh'], CAP_PACK)
        for pas in bloc['pas']:
            self.assertAlmostEqual(pas['capacite_kwh'],
                                   pas['nb_packs'] * CAP_PACK, places=2)

    def test_autonomie_complete_est_le_plafond_de_deficit_du_moteur(self):
        """MÊME formule que ``balayer_stockage_horaire.plafond_deficit_kwh`` :
        déficit du jour type le plus gourmand ÷ rendement, arrondi au pack
        supérieur. Deux formules donneraient deux autonomies contradictoires
        sur la même page."""
        bloc = _bloc()
        auto = bloc['autonomie_complete']
        requise = auto['deficit_jour_max_kwh'] / BATTERY_ROUNDTRIP
        self.assertGreaterEqual(auto['capacite_kwh'], requise - 1e-6)
        self.assertLess(auto['capacite_kwh'] - CAP_PACK, requise)
        self.assertIn(auto['mois'], range(1, 13))

    def test_autonomie_hors_remplissage_est_dite_pas_cachee(self):
        """HONNÊTETÉ (contrainte fondateur) : quand l'autonomie complète
        dépasse la plus grosse banque que ce toit remplit chaque jour, le bloc
        le DIT — il ne masque pas le nombre et ne le présente pas comme
        vendable."""
        auto = _bloc()['autonomie_complete']
        if auto['capacite_kwh'] > auto['capacite_remplissable_max_kwh']:
            self.assertFalse(auto['se_remplit_tous_les_jours'])
            self.assertGreater(auto['nb_packs'], 0)
            self.assertLess(auto['nb_packs_remplissables'], auto['nb_packs'])
        else:
            self.assertTrue(auto['se_remplit_tous_les_jours'])

    def test_se_remplit_suit_le_plafond_de_remplissage_cran_par_cran(self):
        bloc = _bloc()
        plafond = bloc['autonomie_complete']['capacite_remplissable_max_kwh']
        for pas in bloc['pas']:
            self.assertEqual(pas['se_remplit_tous_les_jours'],
                             pas['capacite_kwh'] <= plafond)

    def test_le_curseur_va_jusqu_a_l_autonomie_complete(self):
        """ORDRE FONDATEUR (26/08) — « monter à 30-40 kWh avec des modules de
        5 kWh, pas de problème » : le curseur DOIT atteindre le repère
        d'autonomie complète, sinon on montre un repère que personne ne peut
        aller voir. Le plafond demandé par l'appelant ne fait que le PLANCHER."""
        bloc = _bloc(nb_packs_max=1)
        auto = bloc['autonomie_complete']
        self.assertGreaterEqual(bloc['nb_packs_max'],
                                min(auto['nb_packs'],
                                    COUVERTURE_PACKS_PLAFOND))
        self.assertEqual(len(bloc['pas']), bloc['nb_packs_max'] + 1)
        self.assertTrue(auto['dans_le_curseur'])

    def test_couverture_de_l_autonomie_toujours_servie(self):
        """« Autonomie complète : N batteries (≈ X % de votre consommation) »
        reste affichable, y compris si N dépassait le plafond dur des crans."""
        self.assertIsNotNone(
            _bloc(nb_packs_max=1)['autonomie_complete']['couverture_pct'])

    def test_plafond_dur_du_nombre_de_crans(self):
        bloc = _bloc(nb_packs_max=999)
        self.assertEqual(bloc['nb_packs_max'], COUVERTURE_PACKS_PLAFOND)
        self.assertEqual(len(bloc['pas']), COUVERTURE_PACKS_PLAFOND + 1)

    def test_sans_capacite_de_pack_aucun_bloc(self):
        """Sans capacité utile lisible, on OMET — on n'invente pas un module
        « 5 kWh du catalogue » que ce client n'achète pas."""
        self.assertIsNone(couverture_batterie_publique(
            kwc=KWC, conso_kwh_mensuelles=CONSO_12,
            capacite_utile_pack_kwh=0, nb_packs_max=3, ville='Casablanca'))

    def test_sans_kwc_ni_conso_aucun_bloc(self):
        self.assertIsNone(_bloc_avec(kwc=0))
        self.assertIsNone(_bloc_avec(conso_kwh_mensuelles=[]))

    def test_sans_localisation_aucun_bloc_jamais_une_courbe_inventee(self):
        self.assertIsNone(couverture_batterie_publique(
            kwc=KWC, conso_kwh_mensuelles=CONSO_12,
            capacite_utile_pack_kwh=CAP_PACK, nb_packs_max=3,
            ville='Ville-Qui-N-Existe-Pas'))

    def test_aucun_prix_dans_le_bloc(self):
        """RULE #4 — ce bloc ne porte que des kWh et des pourcentages : donc
        a fortiori aucun prix d'achat, aucune marge."""
        blob = json.dumps(_bloc())
        for interdit in ('prix', 'ttc', 'mad', 'marge', 'achat', 'cout'):
            self.assertNotIn(interdit, blob.lower())


def _bloc_avec(**remplacements):
    params = dict(kwc=KWC, conso_kwh_mensuelles=CONSO_12,
                  capacite_utile_pack_kwh=CAP_PACK, nb_packs_max=3,
                  ville='Casablanca')
    params.update(remplacements)
    return couverture_batterie_publique(**params)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Le plafond du curseur — la MÊME règle que la page
# ═══════════════════════════════════════════════════════════════════════════

class PlafondCurseurTests(SimpleTestCase):

    def test_sans_balayage_le_plafond_historique_de_trois(self):
        self.assertEqual(_paliers_curseur_batterie(None, 1), 3)

    def test_jamais_sous_les_packs_reellement_au_devis(self):
        self.assertEqual(_paliers_curseur_batterie(None, 5), 5)

    def test_monte_jusqu_au_premier_palier_refuse_inclus(self):
        balayage = {'paliers': [{'nb_packs': 1}, {'nb_packs': 2}],
                    'refuse': {'nb_packs': 3}}
        self.assertEqual(_paliers_curseur_batterie(balayage, 1), 3)

    def test_monte_jusqu_au_dernier_retenu_sans_refuse(self):
        balayage = {'paliers': [{'nb_packs': 1}, {'nb_packs': 6}],
                    'refuse': None}
        self.assertEqual(_paliers_curseur_batterie(balayage, 1), 6)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Le contrat partagé (PACT10)
# ═══════════════════════════════════════════════════════════════════════════

class ContratCouvertureBatterieTests(SimpleTestCase):
    """Le fichier ``contract_samples/couverture_batterie.json`` EST le porteur
    du contrat : ses clés doivent être exactement celles que le moteur rend,
    sinon les deux moitiés repartent en aveugle (incident du 03/08/2026)."""

    def setUp(self):
        self.contrat = json.loads(CONTRAT.read_text(encoding='utf-8'))
        self.exemple = self.contrat['exemple']['couverture_batterie']

    def test_endpoint_et_exemple_presents(self):
        self.assertEqual(self.contrat['endpoint'],
                         'GET /api/django/public/proposal/<token>/data/')
        self.assertIn('pourquoi', self.contrat)
        self.assertIn('couverture_batterie', self.contrat['exemple'])

    def test_cles_de_premier_niveau_identiques_au_moteur(self):
        self.assertEqual(set(_bloc()), set(self.exemple))

    def test_cles_d_un_cran_identiques_au_moteur(self):
        self.assertEqual(set(_bloc()['pas'][0]), set(self.exemple['pas'][0]))

    def test_cles_des_bandes_horaires_identiques_au_moteur(self):
        moteur = _bloc()['pas'][1]['jours_types']['7']
        contrat = self.exemple['pas'][1]['jours_types']['7']
        self.assertEqual(set(moteur), set(contrat))
        self.assertEqual(len(contrat['direct_kwh']), 24)

    def test_cles_de_l_autonomie_identiques_au_moteur(self):
        self.assertEqual(set(_bloc()['autonomie_complete']),
                         set(self.exemple['autonomie_complete']))

    def test_la_variante_garde_la_meme_forme(self):
        """Un ``exemple_*`` décrit un autre ÉTAT du serveur, jamais une autre
        FORME (README du dossier)."""
        variante = (self.contrat['exemple_autonomie_atteignable']
                    ['couverture_batterie'])
        self.assertEqual(set(variante), set(self.exemple))
        self.assertEqual(set(variante['autonomie_complete']),
                         set(self.exemple['autonomie_complete']))

    def test_l_exemple_raconte_la_meme_histoire_que_le_moteur(self):
        """L'exemple n'est pas décoratif : il a été produit par le MÊME
        algorithme. Ses invariants sont donc ceux du moteur — bandes positives,
        consommation identique d'un cran à l'autre (seule sa RÉPARTITION
        bouge), couverture croissante avec le nombre de batteries."""
        couvertures = [p['couverture_pct'] for p in self.exemple['pas']]
        self.assertEqual(couvertures, sorted(couvertures))
        totaux_par_mois = {}
        for pas in self.exemple['pas']:
            for mois, courbes in pas['jours_types'].items():
                for bande in ('direct_kwh', 'batterie_kwh', 'reseau_kwh'):
                    self.assertEqual(len(courbes[bande]), 24)
                    self.assertTrue(all(v >= 0 for v in courbes[bande]))
                total = sum(courbes['direct_kwh']) + sum(
                    courbes['batterie_kwh']) + sum(courbes['reseau_kwh'])
                totaux_par_mois.setdefault(mois, []).append(total)
        for totaux in totaux_par_mois.values():
            for total in totaux[1:]:
                self.assertAlmostEqual(total, totaux[0], places=2)

    def test_aucun_prix_dans_le_contrat(self):
        exemple_json = json.dumps(self.contrat['exemple']).lower()
        for interdit in ('prix', 'ttc', 'marge', 'achat'):
            self.assertNotIn(interdit, exemple_json)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Bout en bout — vrai pipeline (build_quote_data → proposal_data)
# ═══════════════════════════════════════════════════════════════════════════

class _PayloadBase(TestCase):
    """Fixture calquée sur ``test_payload_paliers_batterie._PayloadBase``."""

    LIGNES = (
        ('Panneau Canadien Solar 710W', '14', '1166.67'),
        ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
        ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
        ('Batterie Dyness 5 kWh', '2', '12500.00'),
    )

    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, avec_batterie=True, mode='residentiel',
               scenario='Les deux (Sans + Avec)', ville='Casablanca'):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        lead = Lead.objects.create(
            company=company, nom='Lead', prenom=slug,
            telephone='+212600000000', ville=ville,
            facture_hiver=1800, ete_differente=False)
        etude_params = {'scenario': scenario} if scenario else {}
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='envoye',
            taux_tva=Decimal('20'), mode_installation=mode,
            etude_params=etude_params)
        lignes = list(self.LIGNES)
        if not avec_batterie:
            lignes = lignes[:2]
        for nom, qte, pu in lignes:
            produit = Produit.objects.create(
                company=company, nom=nom, prix_vente=pu, quantite_stock=50)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=nom,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def _payload(self, devis, **share_link_kwargs):
        link = ShareLink.objects.create(
            company=devis.company, devis=devis, **share_link_kwargs)
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()


class GardesPayloadTests(_PayloadBase):

    def test_non_residentiel_aucune_cle(self):
        """Même discriminant que ``paliers_batterie`` — un devis
        industriel/agricole n'a pas ce curseur de batterie domestique."""
        bloc = _couverture_batterie_publique(
            None, {'avec_ok': True}, False, None)
        self.assertIsNone(bloc)

    def test_avec_ok_faux_aucune_cle(self):
        bloc = _couverture_batterie_publique(
            None, {'avec_ok': False}, True, None)
        self.assertIsNone(bloc)

    def test_devis_sans_ligne_batterie_aucune_cle(self):
        """Sans ligne batterie, la capacité utile d'un pack est inconnue :
        la clé est absente du payload (jamais un module inventé)."""
        devis = self._devis('cb-sansbat', avec_batterie=False, scenario=None)
        self.assertNotIn('couverture_batterie', self._payload(devis))

    def test_une_erreur_moteur_ne_fait_pas_tomber_la_page(self):
        from unittest import mock
        devis = self._devis('cb-boom')
        with mock.patch(
                'apps.ventes.etude_horaire.couverture_batterie_publique',
                side_effect=RuntimeError('boom')):
            payload = self._payload(devis)
        self.assertNotIn('couverture_batterie', payload)
        self.assertIn('quote', payload)


class ServiPayloadTests(_PayloadBase):

    def test_residentiel_avec_batterie_sert_le_bloc(self):
        payload = self._payload(self._devis('cb-servi'))
        self.assertIn('couverture_batterie', payload)
        bloc = payload['couverture_batterie']
        self.assertGreaterEqual(len(bloc['pas']), 2)
        self.assertEqual(bloc['pas'][0]['nb_packs'], 0)
        self.assertIn('autonomie_complete', bloc)

    def test_le_pack_servi_est_celui_du_devis_pas_du_catalogue(self):
        """Le devis porte DEUX packs de 5 kWh : la capacité par pack servie
        vaut 5 kWh, jamais la capacité totale ni un module du catalogue."""
        bloc = self._payload(self._devis('cb-pack'))['couverture_batterie']
        self.assertAlmostEqual(bloc['capacite_utile_pack_kwh'], 5.0, places=2)

    def test_standard_et_confiance_servent_le_meme_bloc(self):
        devis = self._devis('cb-niveau')
        standard = self._payload(devis, niveau=ShareLink.NIVEAU_STANDARD)
        confiance = self._payload(devis, niveau=ShareLink.NIVEAU_CONFIANCE)
        self.assertIn('couverture_batterie', standard)
        self.assertEqual(standard['couverture_batterie'],
                         confiance['couverture_batterie'])

    def test_aucun_prix_ni_marge_dans_le_bloc_servi(self):
        bloc = self._payload(self._devis('cb-rule4'))['couverture_batterie']
        blob = json.dumps(bloc).lower()
        for interdit in ('prix', 'ttc', 'marge', 'achat', 'mad'):
            self.assertNotIn(interdit, blob)

    def test_aucune_regression_des_cles_voisines(self):
        payload = self._payload(self._devis('cb-voisines'))
        for cle in ('courbes_journalieres', 'dimensionnement_options',
                    'variantes_servables'):
            self.assertIn(cle, payload)
