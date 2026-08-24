"""PACT10 (« deux optimiseurs », 25/08/2026) — ``dimensionnement_options`` /
``production_par_option`` du payload public de la proposition (contrat
``apps/ventes/contract_samples/dimensionnement_options.json``).

Un devis résidentiel pourra porter des dimensionnements DIFFÉRENTS par
option (nb panneaux/kWc/batteries), portés par ``LigneDevis.variante`` (une
autre lane) et par le split ``sans_items``/``avec_items`` du builder — déjà
par option. Tant que ce split ne distingue pas encore les lignes panneau par
option (aucun devis réel ne peut donc ENCORE diverger), les tests « clés
correctes sur variantes divergentes » appellent directement les fonctions
PURES du payload (``_dimensionnement_options_publique``) avec des
``sans_items``/``avec_items`` construits à la main — exactement la forme que
le builder rendra une fois le split posé. Les tests « devis legacy »/
« niveau standard »/« avec_ok=false » passent par le VRAI pipeline
(``build_quote_data`` → ``proposal_data``) pour prouver le câblage bout en
bout.

Fixtures calquées sur ``test_cj2b_economies_publiques.py`` : Casablanca est
dans la table de référence PVGIS, aucun accès réseau n'est nécessaire.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.crm.models import Client, Lead
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink
from apps.ventes.public_views import (
    _dimensionnement_option_depuis_items,
    _dimensionnement_options_publique,
    _production_par_option_publique,
)

User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════════
# 1. ``_dimensionnement_option_depuis_items`` — pur, aucune BD
# ═══════════════════════════════════════════════════════════════════════════

class DimensionnementOptionDepuisItemsTests(SimpleTestCase):
    def test_panneaux_watt_lu_donne_le_kwc(self):
        items = [{'designation': 'Panneau mono 550W', 'quantite': 22.0,
                  '_produit_nom': ''}]
        bloc = _dimensionnement_option_depuis_items(items)
        self.assertEqual(bloc['nb_panneaux'], 22)
        self.assertEqual(bloc['puissance_kwc'], round(22 * 550 / 1000, 2))
        self.assertEqual(bloc['nb_batteries'], 0)
        self.assertIsNone(bloc['capacite_batterie_kwh'])

    def test_watt_illisible_laisse_puissance_kwc_none(self):
        """M3 — jamais le repli 710 W sur un document client : un watt non
        lu laisse le kWc absent, le compte de panneaux reste vrai."""
        items = [{'designation': 'Panneau solaire', 'quantite': 10.0,
                  '_produit_nom': ''}]
        bloc = _dimensionnement_option_depuis_items(items)
        self.assertEqual(bloc['nb_panneaux'], 10)
        self.assertIsNone(bloc['puissance_kwc'])

    def test_batteries_avec_kwh_lu_sur_la_designation(self):
        items = [{'designation': 'Batterie 7.7kWh', 'quantite': 2.0,
                  '_produit_nom': ''}]
        bloc = _dimensionnement_option_depuis_items(items)
        self.assertEqual(bloc['nb_batteries'], 2)
        self.assertEqual(bloc['capacite_batterie_kwh'], 15.4)

    def test_batterie_sans_kwh_lisible_retombe_sur_le_defaut_moteur(self):
        """Même défaut que ``builder._battery_kwh_from_items`` — jamais un
        second forfait."""
        items = [{'designation': 'Batterie', 'quantite': 1.0,
                  '_produit_nom': ''}]
        bloc = _dimensionnement_option_depuis_items(items)
        self.assertEqual(bloc['nb_batteries'], 1)
        self.assertEqual(bloc['capacite_batterie_kwh'], 5.0)

    def test_items_vides_ou_none(self):
        for items in (None, []):
            with self.subTest(items=items):
                bloc = _dimensionnement_option_depuis_items(items)
                self.assertEqual(bloc, {
                    'nb_panneaux': 0, 'puissance_kwc': None,
                    'nb_batteries': 0, 'capacite_batterie_kwh': None,
                })

    def test_ligne_quantite_nulle_ou_negative_ignoree(self):
        items = [
            {'designation': 'Panneau mono 550W', 'quantite': 0,
             '_produit_nom': ''},
            {'designation': 'Panneau mono 550W', 'quantite': -1,
             '_produit_nom': ''},
        ]
        bloc = _dimensionnement_option_depuis_items(items)
        self.assertEqual(bloc['nb_panneaux'], 0)

    def test_deux_lignes_panneau_le_premier_watt_lu_gagne(self):
        """Même ordre de résolution que ``panneaux_et_watt_lu`` : le premier
        watt lisible l'emporte, jamais un second calcul par ligne."""
        items = [
            {'designation': 'Panneau mono 550W', 'quantite': 10.0,
             '_produit_nom': ''},
            {'designation': 'Panneau mono 450W', 'quantite': 4.0,
             '_produit_nom': ''},
        ]
        bloc = _dimensionnement_option_depuis_items(items)
        self.assertEqual(bloc['nb_panneaux'], 14)
        self.assertEqual(bloc['puissance_kwc'], round(14 * 550 / 1000, 2))

    def test_aucun_prix_achat_ni_marge_dans_le_rendu(self):
        """RULE #4 — le bloc ne recopie jamais un champ de marge, même si
        l'item du builder en portait un par mégarde."""
        items = [{'designation': 'Panneau mono 550W', 'quantite': 10.0,
                  '_produit_nom': '', 'prix_achat': 999, 'marge': 50}]
        bloc = _dimensionnement_option_depuis_items(items)
        self.assertEqual(set(bloc), {
            'nb_panneaux', 'puissance_kwc', 'nb_batteries',
            'capacite_batterie_kwh'})


# ═══════════════════════════════════════════════════════════════════════════
# 2. ``_dimensionnement_options_publique`` / ``_production_par_option_publique``
#    — aucune BD : ``devis=None`` + ``data['client_city']`` explicite pour la
#    localisation (table PVGIS Casablanca, aucun accès réseau — même
#    discipline que ``JoursTypesPublicsTests``/``test_cj2b_economies_publiques``).
# ═══════════════════════════════════════════════════════════════════════════

def _data(sans_items, avec_items, *, avec_ok, ville='Casablanca'):
    d = {'sans_items': sans_items, 'avec_items': avec_items,
         'avec_ok': avec_ok}
    if ville is not None:
        d['client_city'] = ville
    return d


_PANNEAU_550W = {'designation': 'Panneau mono 550W', 'quantite': 22.0,
                 '_produit_nom': ''}


class DimensionnementOptionsPubliqueTests(SimpleTestCase):
    def test_devis_sans_variante_meme_dimensionnement_divergent_faux(self):
        """Cas de TOUS les devis existants tant que le split par variante
        n'est pas posé : les deux options partagent les mêmes lignes
        panneau — divergent=false, valeurs égales."""
        items = [_PANNEAU_550W]
        bloc = _dimensionnement_options_publique(None, _data(items, items, avec_ok=True))
        self.assertIsNotNone(bloc)
        self.assertFalse(bloc['divergent'])
        self.assertEqual(bloc['sans']['nb_panneaux'], bloc['avec']['nb_panneaux'])
        self.assertEqual(bloc['sans']['puissance_kwc'], bloc['avec']['puissance_kwc'])

    def test_variantes_divergentes_nb_panneaux_differents(self):
        """La forme que le builder rendra une fois le split par variante
        posé : deux tailles réellement différentes par option."""
        sans_items = [{'designation': 'Panneau mono 550W', 'quantite': 22.0,
                       '_produit_nom': ''}]
        avec_items = [
            {'designation': 'Panneau mono 550W', 'quantite': 26.0,
             '_produit_nom': ''},
            {'designation': 'Batterie 7.7kWh', 'quantite': 2.0,
             '_produit_nom': ''},
        ]
        bloc = _dimensionnement_options_publique(
            None, _data(sans_items, avec_items, avec_ok=True))
        self.assertTrue(bloc['divergent'])
        self.assertEqual(bloc['sans']['nb_panneaux'], 22)
        self.assertEqual(bloc['avec']['nb_panneaux'], 26)
        self.assertEqual(bloc['avec']['nb_batteries'], 2)
        self.assertEqual(bloc['avec']['capacite_batterie_kwh'], 15.4)
        self.assertIsNone(bloc['sans']['capacite_batterie_kwh'])
        # Production annuelle : localisation résolue (Casablanca, table PVGIS
        # sans réseau) → un vrai chiffre par option, plus élevé pour la
        # taille la plus grande (même productible, kWc supérieur).
        self.assertIsNotNone(bloc['sans']['production_annuelle_kwh'])
        self.assertIsNotNone(bloc['avec']['production_annuelle_kwh'])
        self.assertGreater(bloc['avec']['production_annuelle_kwh'],
                           bloc['sans']['production_annuelle_kwh'])

    def test_avec_ok_faux_aucune_branche_avec(self):
        """L-VAR — jamais un dimensionnement 'avec batterie' sur une option
        que ce devis ne livre pas."""
        sans_items = [{'designation': 'Panneau mono 550W', 'quantite': 14.0,
                       '_produit_nom': ''}]
        bloc = _dimensionnement_options_publique(
            None, _data(sans_items, [], avec_ok=False))
        self.assertIsNotNone(bloc)
        self.assertNotIn('avec', bloc)
        self.assertFalse(bloc['divergent'])
        self.assertEqual(bloc['sans']['nb_panneaux'], 14)

    def test_localisation_absente_production_annuelle_reste_none(self):
        """Q6/Z2 — sans localisation résolue, jamais un chiffre inventé."""
        items = [_PANNEAU_550W]
        bloc = _dimensionnement_options_publique(
            None, _data(items, [], avec_ok=False, ville=None))
        self.assertIsNone(bloc['sans']['production_annuelle_kwh'])


class ProductionParOptionPubliqueTests(SimpleTestCase):
    def test_dimensionnement_options_none_renvoie_les_deux_cles_a_none(self):
        bloc = _production_par_option_publique(None, {}, None)
        self.assertEqual(bloc, {'sans': None, 'avec': None})

    def test_non_divergent_ne_calcule_rien_la_page_garde_la_courbe_unique(self):
        dimensionnement = {
            'sans': {'puissance_kwc': 9.94}, 'avec': {'puissance_kwc': 9.94},
            'divergent': False,
        }
        bloc = _production_par_option_publique(
            None, {'client_city': 'Casablanca'}, dimensionnement)
        self.assertEqual(bloc, {'sans': None, 'avec': None})

    def test_divergent_calcule_les_deux_series_meme_forme_que_courbes(self):
        dimensionnement = {
            'sans': {'puissance_kwc': 15.62}, 'avec': {'puissance_kwc': 18.46},
            'divergent': True,
        }
        bloc = _production_par_option_publique(
            None, {'client_city': 'Casablanca'}, dimensionnement)
        self.assertIsNotNone(bloc['sans'])
        self.assertIsNotNone(bloc['avec'])
        for cote in ('sans', 'avec'):
            self.assertTrue(bloc[cote])  # au moins une saison résolue
            for entree in bloc[cote].values():
                self.assertEqual(len(entree['forme']), 24)
                self.assertIsInstance(entree['kwh_jour'], float)
                self.assertIsInstance(entree['pic_kw'], float)

    def test_kwc_absent_sur_une_option_reste_none(self):
        dimensionnement = {
            'sans': {'puissance_kwc': None}, 'avec': {'puissance_kwc': 18.46},
            'divergent': True,
        }
        bloc = _production_par_option_publique(
            None, {'client_city': 'Casablanca'}, dimensionnement)
        self.assertIsNone(bloc['sans'])
        self.assertIsNotNone(bloc['avec'])


# ═══════════════════════════════════════════════════════════════════════════
# 3. Bout en bout — vrai pipeline (build_quote_data → proposal_data)
# ═══════════════════════════════════════════════════════════════════════════

class _PayloadBase(TestCase):
    """Fixture calquée sur ``test_cj2b_economies_publiques._CJ2bBase`` :
    société, lead Casablanca (facture réelle, table PVGIS — aucun réseau)."""

    LIGNES_DEUX_ONDULEURS = (
        ('Panneau Canadien Solar 710W', '14', '1166.67'),
        ('Onduleur réseau Huawei 10kW Monophasé', '1', '15000.00'),
        ('Onduleur hybride Deye 10kW Monophasé', '1', '23333.33'),
        ('Batterie Dyness 10 kWh', '1', '25000.00'),
    )

    def _company(self, slug):
        from authentication.models import Company
        company = Company.objects.get_or_create(
            slug=slug, defaults={'nom': slug})[0]
        User.objects.get_or_create(
            username=f'{slug}-user',
            defaults={'password': 'x', 'company': company})
        return company

    def _devis(self, slug, *, avec_batterie=True, scenario='Les deux (Sans + Avec)'):
        company = self._company(slug)
        client_obj = Client.objects.get_or_create(
            company=company, nom=f'Client {slug}', defaults={})[0]
        lead = Lead.objects.create(
            company=company, nom='Lead', prenom=slug,
            telephone='+212600000000', ville='Casablanca',
            facture_hiver=1800, ete_differente=False)
        etude_params = {'scenario': scenario} if scenario else {}
        devis = Devis.objects.create(
            company=company, reference=f'DEV-{slug.upper()}-01',
            client=client_obj, lead=lead, statut='envoye',
            taux_tva=Decimal('20'), mode_installation='residentiel',
            etude_params=etude_params)
        lignes = list(self.LIGNES_DEUX_ONDULEURS)
        if not avec_batterie:
            lignes = lignes[:2]   # panneau + onduleur réseau seulement
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


class DevisLegacyPayloadTests(_PayloadBase):
    """Un devis « legacy » (aucune ligne encore taggée par variante) : les
    deux options partagent les mêmes lignes panneau — divergent=false,
    valeurs égales, ``production_par_option`` reste null des deux côtés."""

    def test_dimensionnement_options_divergent_faux_valeurs_egales(self):
        devis = self._devis('do-legacy')
        p = self._payload(devis)
        self.assertIn('dimensionnement_options', p)
        d = p['dimensionnement_options']
        self.assertFalse(d['divergent'])
        self.assertEqual(d['sans']['nb_panneaux'], 14)
        self.assertEqual(d['avec']['nb_panneaux'], 14)
        self.assertEqual(d['sans']['puissance_kwc'], d['avec']['puissance_kwc'])
        # La batterie RÉELLE (Dyness 10 kWh) n'apparaît que côté 'avec'.
        self.assertEqual(d['sans']['nb_batteries'], 0)
        self.assertEqual(d['avec']['nb_batteries'], 1)
        self.assertEqual(d['avec']['capacite_batterie_kwh'], 10.0)

    def test_production_par_option_null_quand_pas_divergent(self):
        devis = self._devis('do-legacy-prod')
        p = self._payload(devis)
        self.assertIn('production_par_option', p)
        self.assertEqual(p['production_par_option'], {'sans': None, 'avec': None})

    def test_aucun_prix_achat_ni_marge_dans_le_bloc(self):
        devis = self._devis('do-rule4')
        p = self._payload(devis)
        import json
        blob = json.dumps(p['dimensionnement_options'])
        self.assertNotIn('prix_achat', blob)
        self.assertNotIn('marge', blob)


class NiveauStandardMemeClesTests(_PayloadBase):
    """L-NIV — les tailles/nombres ne se dégradent JAMAIS au niveau standard
    (seule la nomenclature détaillée le fait) : mêmes clés, mêmes valeurs."""

    def test_standard_et_confiance_servent_le_meme_dimensionnement(self):
        devis = self._devis('do-niveau')
        p_standard = self._payload(devis, niveau=ShareLink.NIVEAU_STANDARD)
        p_confiance = self._payload(devis, niveau=ShareLink.NIVEAU_CONFIANCE)
        self.assertIn('dimensionnement_options', p_standard)
        self.assertIn('dimensionnement_options', p_confiance)
        self.assertEqual(set(p_standard['dimensionnement_options']),
                         set(p_confiance['dimensionnement_options']))
        self.assertEqual(p_standard['dimensionnement_options'],
                         p_confiance['dimensionnement_options'])


class AvecOkFauxPayloadTests(_PayloadBase):
    """Onduleur hybride sans ligne batterie (Z1) : avec_ok reste faux — la
    branche 'avec' est absente de ``dimensionnement_options``."""

    def test_pas_de_branche_avec_quand_avec_ok_faux(self):
        devis = self._devis('do-sansavec', avec_batterie=False, scenario=None)
        p = self._payload(devis)
        self.assertIn('dimensionnement_options', p)
        d = p['dimensionnement_options']
        self.assertNotIn('avec', d)
        self.assertFalse(d['divergent'])
        self.assertEqual(d['sans']['nb_panneaux'], 14)
        self.assertEqual(p['production_par_option'], {'sans': None, 'avec': None})
