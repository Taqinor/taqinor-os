# -*- coding: utf-8 -*-
"""L-2OPT — la resynchronisation 3D ne RÉTRÉCIT plus un devis « Les deux ».

L'INCIDENT, sur donnée réelle (DEV-202608-0023, production). Le devis naît
« Les deux (Sans + Avec) » (U2) : il porte un onduleur RÉSEAU (option « sans »),
un onduleur HYBRIDE et une BATTERIE (option « avec »), et son
``etude_params['scenario']`` le DÉCLARE — c'est cette déclaration que le moteur
PDF lit pour rendre la comparaison (PV86/QF6). Puis quelqu'un enregistre le
calepinage 3D, et la resynchronisation :

  * voyait dans l'onduleur réseau l'« intrus » de l'artefact deux-onduleurs
    (PVHEAL) et le SUPPRIMAIT ;
  * supprimait la batterie dès que le layout ne « voulait » pas de batterie ;
  * réécrivait le scénario avec un libellé MONO (``_scenario_stocke`` ne sait
    rendre que « Sans batterie » / « Avec batterie »).

Le moteur relisait alors une déclaration mono : ``nb_options`` retombait à 1,
``sans_items`` se vidait, et la page publique du client ne montrait plus qu'une
seule option — celle que le commercial n'avait jamais choisie seule.

Ces tests verrouillent la préservation, ET son témoin négatif : sur un devis
MONO « Avec batterie », l'artefact deux-onduleurs est toujours assaini comme
avant.

Run :
    DB_NAME=erp_ventes python manage.py test \\
        apps.ventes.tests.test_resync_les_deux -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis
from apps.ventes.services import (SCENARIO_AVEC_BATTERIE, SCENARIO_LES_DEUX)

# Fixtures PARTAGÉES avec le module PV18 : mêmes désignations catalogue (c'est
# par elles que le classifieur range les produits), même client authentifié,
# même fabrique de layout. On importe des FONCTIONS et des CONSTANTES seulement
# — jamais une classe ``TestCase``, qui serait alors collectée deux fois.
from apps.ventes.tests.test_pv18_sync_layout import (
    BAREMES_FORFAIT, CATALOGUE_KIT, CLES_REPONSE, auth_client, layout,
    make_company)

User = get_user_model()

RESEAU = 'Onduleur réseau Huawei 5kW'
HYBRIDE = 'Onduleur hybride Deye 5kW'
BATTERIE = 'Batterie Dyness 5 kWh'
PANNEAU = 'Panneau Jinko 550W'


class _BaseDeuxOptions(TestCase):
    """Catalogue COMPLET + fabriques de devis à deux options."""

    def setUp(self):
        self.company = make_company('l2opt-co')
        self.user = User.objects.create_user(
            username='l2optuser', password='x', role_legacy='responsable',
            company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client L-2OPT')
        self.produits = {}
        for nom, sku, prix in CATALOGUE_KIT:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku='L2OPT-%s' % sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))
        self.compteur = 0

    def _devis(self, *, scenario_stocke, reseau=True, hybride=True,
               batterie=True, panneaux=12):
        """Le devis « Les deux » tel que la création (U2) le compose."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-L2OPT-%s' % self.compteur,
            client=self.client_obj, statut=Devis.Statut.BROUILLON,
            created_by=self.user,
            etude_params={'scenario': scenario_stocke})
        devis.lignes.create(
            produit=self.produits[PANNEAU], designation=PANNEAU,
            quantite=Decimal(str(panneaux)), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), ordre=1)
        ordre = 1
        for actif, nom, prix in ((reseau, RESEAU, '14000'),
                                 (hybride, HYBRIDE, '17000'),
                                 (batterie, BATTERIE, '16000')):
            if not actif:
                continue
            ordre += 1
            devis.lignes.create(
                produit=self.produits[nom], designation=nom,
                quantite=Decimal('1'), prix_unitaire=Decimal(prix),
                remise=Decimal('0'), ordre=ordre)
        return devis

    def _post(self, devis, corps):
        return self.api.post(
            '/api/django/ventes/devis/%s/sync-layout/' % devis.id,
            corps, format='json')

    def _designations(self, devis):
        return set(devis.lignes.values_list('designation', flat=True))


class TestResyncPreserveLesDeux(_BaseDeuxOptions):
    """Un devis NÉ « Les deux » sort de la resynchro toujours à deux options."""

    def test_les_trois_lignes_survivent_a_un_layout_avec_batterie(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(set(resp.data), CLES_REPONSE)
        designations = self._designations(devis)
        self.assertIn(RESEAU, designations)
        self.assertIn(HYBRIDE, designations)
        self.assertIn(BATTERIE, designations)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_le_layout_sans_batterie_ne_retire_pas_la_batterie(self):
        """La batterie EST l'option « avec » : un layout « réseau » ne la
        supprime pas d'un devis qui propose les deux."""
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='reseau'))
        self.assertEqual(resp.status_code, 200, resp.content)
        designations = self._designations(devis)
        self.assertIn(BATTERIE, designations)
        self.assertIn(RESEAU, designations)
        self.assertIn(HYBRIDE, designations)
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_aucun_avertissement_deux_onduleurs(self):
        """Les DEUX onduleurs sont légitimes ici : rien à signaler."""
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            [a for a in resp.data['avertissements'] if 'onduleur' in a.lower()],
            [])

    def test_la_reponse_dit_les_deux(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['scenario'], 'les_deux')
        self.assertTrue(resp.data['batterie'])

    def test_le_moteur_rend_toujours_deux_options(self):
        """La preuve par le moteur : c'est LUI que la page publique lit."""
        from apps.ventes.quote_engine.builder import build_quote_data

        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        self._post(devis, layout(panels=16, kwc=8.8, scenario='avec_batterie'))
        devis.refresh_from_db()

        data = build_quote_data(devis)
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['scenario'], SCENARIO_LES_DEUX)
        self.assertTrue(data['sans_items'])
        self.assertGreater(data['total_sans'], 0)
        self.assertGreater(data['total_avec'], 0)

    def test_les_prix_negocies_des_deux_onduleurs_sont_intacts(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX)
        devis.lignes.filter(designation=RESEAU).update(
            prix_unitaire=Decimal('11900'))
        self._post(devis, layout(panels=16, kwc=8.8, scenario='avec_batterie'))
        reseau = devis.lignes.get(designation=RESEAU)
        self.assertEqual(reseau.prix_unitaire, Decimal('11900.00'))
        hybride = devis.lignes.get(designation=HYBRIDE)
        self.assertEqual(hybride.prix_unitaire, Decimal('17000.00'))


class TestResyncCompleteLOnduleurManquant(_BaseDeuxOptions):
    """Un devis deux-options AMPUTÉ d'un onduleur est COMPLÉTÉ, pas permuté."""

    def test_le_reseau_manquant_est_re_ajoute_au_prix_catalogue(self):
        """DEV-202608-0023 rejoué : hybride + batterie, réseau disparu."""
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX, reseau=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        reseau = devis.lignes.get(designation=RESEAU)
        self.assertEqual(reseau.produit_id, self.produits[RESEAU].id)
        self.assertEqual(reseau.prix_unitaire, Decimal('14000.00'))
        self.assertEqual(reseau.remise, Decimal('0.00'))
        # L'hybride n'a PAS été permuté : il est toujours là, intact.
        hybride = devis.lignes.get(designation=HYBRIDE)
        self.assertEqual(hybride.prix_unitaire, Decimal('17000.00'))
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_l_hybride_manquant_est_re_ajoute_quand_la_batterie_est_la(self):
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX, hybride=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        hybride = devis.lignes.get(designation=HYBRIDE)
        self.assertEqual(hybride.produit_id, self.produits[HYBRIDE].id)
        self.assertEqual(hybride.prix_unitaire, Decimal('17000.00'))
        # Le réseau n'a PAS été permuté en hybride : les deux coexistent.
        self.assertTrue(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'], SCENARIO_LES_DEUX)

    def test_sans_reseau_tarife_on_previent_au_lieu_de_mentir(self):
        Produit.objects.filter(pk=self.produits[RESEAU].pk).update(
            is_archived=True)
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX, reseau=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        self.assertTrue(
            any('réseau' in a and 'deux options' in a
                for a in resp.data['avertissements']),
            resp.data['avertissements'])
        # Le scénario stocké ne PROMET pas une option que les lignes ne
        # peuvent pas servir : il dégrade honnêtement.
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)


class TestTemoinNegatifDevisMono(_BaseDeuxOptions):
    """Le devis MONO « Avec batterie » garde EXACTEMENT l'ancien comportement."""

    def test_l_intrus_reseau_au_prix_catalogue_est_toujours_retire(self):
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        self.assertTrue(devis.lignes.filter(designation=HYBRIDE).exists())
        self.assertTrue(devis.lignes.filter(designation=BATTERIE).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)
        self.assertEqual(resp.data['scenario'], 'avec_batterie')

    def test_un_devis_sans_scenario_stocke_reste_assaini(self):
        """Aucune déclaration = artefact deux-onduleurs, comme avant."""
        devis = self._devis(scenario_stocke=None)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        devis.refresh_from_db()
        self.assertEqual(devis.etude_params['scenario'],
                         SCENARIO_AVEC_BATTERIE)

    def test_la_batterie_sort_toujours_d_un_devis_mono(self):
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE,
                            reseau=False)
        resp = self._post(devis, layout(panels=16, kwc=8.8,
                                        scenario='reseau'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertFalse(devis.lignes.filter(designation=BATTERIE).exists())


class TestQjr60QuantiteVerrouillee(_BaseDeuxOptions):
    """QJR60 / décision fondateur D12 — la resynchro RESPECTE une quantité
    tapée à la main, et le DIT.

    Avant : la resynchro réécrivait librement les quantités (panneaux, mètres
    de câble, structures/socles) pendant que le PRIX tapé sur la MÊME ligne
    était sacré. Deux entrées commerciales, deux traitements opposés.
    """

    def _verrouiller_panneaux(self, devis):
        ligne = devis.lignes.get(designation=PANNEAU)
        ligne.quantite_manuelle = True
        ligne.save(update_fields=['quantite_manuelle'])
        return ligne

    def test_le_compte_de_panneaux_tape_survit_a_la_resynchro(self):
        """ROUGE avant QJR60 : le calepinage écrasait la saisie."""
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE,
                            reseau=False, panneaux=12)
        ligne = self._verrouiller_panneaux(devis)

        resp = self._post(devis, layout(panels=20, kwc=11.0,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne.refresh_from_db()
        self.assertEqual(int(ligne.quantite), 12)

    def test_un_avertissement_FR_nomme_la_ligne_et_l_ecart(self):
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE,
                            reseau=False, panneaux=12)
        self._verrouiller_panneaux(devis)

        resp = self._post(devis, layout(panels=20, kwc=11.0,
                                        scenario='avec_batterie'))
        avertissements = ' | '.join(resp.data['avertissements'])
        self.assertIn('verrouill', avertissements.lower())
        self.assertIn(PANNEAU, avertissements)
        self.assertIn('8', avertissements)

    def test_sans_marqueur_le_comportement_est_celui_d_avant(self):
        """Le témoin : aucune ligne verrouillée ⇒ la resynchro écrit, comme
        avant les marqueurs QJR59."""
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE,
                            reseau=False, panneaux=12)
        ligne = devis.lignes.get(designation=PANNEAU)
        self.assertFalse(ligne.quantite_manuelle)

        resp = self._post(devis, layout(panels=20, kwc=11.0,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        ligne.refresh_from_db()
        self.assertEqual(int(ligne.quantite), 20)
        self.assertNotIn(
            'verrouill',
            ' | '.join(resp.data['avertissements']).lower())

    def test_une_structure_verrouillee_n_est_pas_recomptee(self):
        """Le TROISIÈME écrivain (``_resynchroniser_quantite``) — celui des
        mètres de câble et des comptes structure/socle."""
        devis = self._devis(scenario_stocke=SCENARIO_AVEC_BATTERIE,
                            reseau=False, panneaux=12)
        structure = devis.lignes.create(
            produit=self.produits['Structures acier'],
            designation='Structures acier', quantite=Decimal('12'),
            prix_unitaire=Decimal('500'), remise=Decimal('0'), ordre=8,
            quantite_manuelle=True)

        resp = self._post(devis, layout(panels=20, kwc=11.0,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        structure.refresh_from_db()
        self.assertEqual(int(structure.quantite), 12)
        avertissements = ' | '.join(resp.data['avertissements'])
        self.assertIn('Structures acier', avertissements)
        self.assertIn('verrouill', avertissements.lower())

    def test_le_verrou_d_une_option_ne_bloque_pas_l_autre(self):
        """Devis « Les deux » : verrouiller la ligne d'UNE variante ne fige
        pas l'autre — le verrou est une propriété de LIGNE, pas de devis."""
        devis = self._devis(scenario_stocke=SCENARIO_LES_DEUX, panneaux=20)
        commune = devis.lignes.get(designation=PANNEAU)
        commune.variante = 'sans'
        commune.quantite_manuelle = True
        commune.save(update_fields=['variante', 'quantite_manuelle'])
        autre = devis.lignes.create(
            produit=self.produits[PANNEAU], designation=PANNEAU,
            quantite=Decimal('20'), prix_unitaire=Decimal('1100'),
            remise=Decimal('0'), ordre=9, variante='avec')

        resp = self._post(devis, layout(panels=12, kwc=6.6,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        commune.refresh_from_db()
        autre.refresh_from_db()
        self.assertEqual(int(commune.quantite), 20)
        self.assertEqual(int(autre.quantite), 12)


# ════════════════════════════════════════════════════════════════════════════
# QJR81 — LE CHEMIN DE RÉPARATION (PVHEAL) HÉRITE DES RÈGLES DE LA CRÉATION
# ════════════════════════════════════════════════════════════════════════════
#
# Constat QB81 (audit L3 du 29/08/2026), vérifié en code :
#
#   1. ``_completer_kit_residentiel`` composait le « kit attendu » par un appel
#      DIRECT à ``composition_residentielle``, SANS la carte des marques
#      épinglées (PVMRQ), SANS l'ordre de lignes de la société (PVORD) et SANS
#      la phase électrique déclarée du client (PVCOMPAT). Ce chemin pouvait
#      donc coter une marque et une phase que le chemin de CRÉATION s'interdit.
#   2. Sur un devis « Les deux » dont les deux optimums DIVERGENT, il ajoutait
#      ses lignes SANS variante — donc COMMUNES — dimensionnées sur le compte
#      de l'option SANS. La resynchronisation PVSTR refuse ensuite, par design,
#      de porter une ferrure COMMUNE au compte d'une seule option : l'option
#      AVEC restait durablement sous-structurée, et son forfait de pose par
#      panneau sous-facturé.
#
# La réparation passe désormais par ``pipeline.composer`` — LE composeur, celui
# de l'aperçu et de la création — et estampille la variante de l'option
# réparée.

class _BaseReparation(TestCase):
    """Un devis SQUELETTE (aucune ligne de kit) et un catalogue COMPLET."""

    slug = 'qjr81-reparation'

    def setUp(self):
        from apps.crm.models import Lead

        self.company = make_company(self.slug)
        self.user = User.objects.create_user(
            username='qjr81-%s' % self.slug, password='x',
            role_legacy='responsable', company=self.company)
        self.api = auth_client(self.user)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR81')
        self._Lead = Lead
        self.produits = {}
        for nom, sku, prix in CATALOGUE_KIT:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku='QJR81-%s' % sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))
        self.compteur = 0

    def _lead(self, raccordement):
        return self._Lead.objects.create(
            company=self.company, nom='QJR81', prenom='Raccordement',
            email='qjr81-%s@example.com' % raccordement,
            raccordement=raccordement)

    def _squelette(self, *, scenario_stocke, lignes, lead=None):
        """Devis sans AUCUNE ligne de kit : ``lignes`` est une suite de
        ``(désignation, quantité, variante)``."""
        self.compteur += 1
        devis = Devis.objects.create(
            company=self.company, reference='DEV-QJR81-%s' % self.compteur,
            client=self.client_obj, lead=lead,
            statut=Devis.Statut.BROUILLON, created_by=self.user,
            etude_params={'scenario': scenario_stocke})
        for ordre, (nom, quantite, variante) in enumerate(lignes, start=1):
            produit = self.produits[nom]
            devis.lignes.create(
                produit=produit, designation=nom,
                quantite=Decimal(str(quantite)),
                prix_unitaire=Decimal(produit.prix_vente),
                remise=Decimal('0'), ordre=ordre, variante=variante)
        return devis

    def _post(self, devis, corps):
        return self.api.post(
            '/api/django/ventes/devis/%s/sync-layout/' % devis.id,
            corps, format='json')


class TestReparationHeriteDesReglesDeCreation(_BaseReparation):
    """QJR81 #1 — marque épinglée et phase déclarée valent AUSSI ici."""

    slug = 'qjr81-regles'

    def test_la_marque_epinglee_gagne_sur_le_chemin_de_reparation(self):
        """PVMRQ — deux transporteurs au catalogue, un seul épinglé : la
        réparation doit coter CELUI-LÀ. Avant QJR81 elle prenait le premier
        venu, la carte des marques ne lui étant jamais passée."""
        from apps.ventes.models import ParametresGammes

        # Le catalogue standard porte déjà « Transport » (sans marque) ; on
        # ajoute un SECOND transporteur, celui que la société épingle.
        Produit.objects.create(
            company=self.company, nom='Transport Premium',
            sku='QJR81-TRANS2', marque='SunRak',
            prix_vente=Decimal('1400'), prix_achat=Decimal('1'),
            quantite_stock=500)
        ParametresGammes.objects.create(
            company=self.company, deux_gammes=False,
            marques={ParametresGammes.SLOT_ESSENTIELLE:
                     {'transport': 'SunRak'}})

        devis = self._squelette(
            scenario_stocke=SCENARIO_AVEC_BATTERIE,
            lignes=((PANNEAU, 8, ''), (HYBRIDE, 1, ''), (BATTERIE, 1, '')))
        resp = self._post(devis, layout(panels=8, kwc=4.4,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)

        transports = [li for li in devis.lignes.all()
                      if 'Transport' in li.designation]
        self.assertEqual(len(transports), 1,
                         [li.designation for li in devis.lignes.all()])
        self.assertEqual(transports[0].designation, 'Transport Premium',
                         'la réparation n’a pas respecté la marque épinglée')

    def test_la_marque_epinglee_introuvable_ne_retombe_pas_en_silence(self):
        """Ordre fondateur #5 : une marque réglée SANS candidat vide le vivier
        — la classe est alors DITE absente, jamais remplacée en douce."""
        from apps.ventes.models import ParametresGammes

        ParametresGammes.objects.create(
            company=self.company, deux_gammes=False,
            marques={ParametresGammes.SLOT_ESSENTIELLE:
                     {'transport': 'MarqueQuiNExistePas'}})
        devis = self._squelette(
            scenario_stocke=SCENARIO_AVEC_BATTERIE,
            lignes=((PANNEAU, 8, ''), (HYBRIDE, 1, ''), (BATTERIE, 1, '')))
        resp = self._post(devis, layout(panels=8, kwc=4.4,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)

        self.assertNotIn('Transport',
                         [li.designation for li in devis.lignes.all()])
        self.assertIn('Transport absent du catalogue ou sans prix — ligne non '
                      'ajoutée.', resp.data['avertissements'])

    def test_la_phase_declaree_descend_jusqua_la_reparation(self):
        """PVCOMPAT/L-TRI — client TRIPHASÉ, catalogue 100 % monophasé : la
        composition REFUSE de coter un monophasé et le DIT. Avant QJR81, la
        phase n'était pas transmise : ce message ne pouvait pas sortir."""
        devis = self._squelette(
            scenario_stocke=SCENARIO_AVEC_BATTERIE,
            lead=self._lead('triphase'),
            lignes=((PANNEAU, 8, ''), (HYBRIDE, 1, ''), (BATTERIE, 1, '')))
        resp = self._post(devis, layout(panels=8, kwc=4.4,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)

        avertissements = ' | '.join(resp.data['avertissements'])
        self.assertIn('TRIPHASÉ', avertissements, avertissements)

    def test_sans_lead_la_reparation_est_inchangee(self):
        """Le témoin négatif : pas de raccordement déclaré ⇒ aucun filtre de
        phase, aucun message, et le kit est complété comme avant."""
        devis = self._squelette(
            scenario_stocke=SCENARIO_AVEC_BATTERIE,
            lignes=((PANNEAU, 8, ''), (HYBRIDE, 1, ''), (BATTERIE, 1, '')))
        resp = self._post(devis, layout(panels=8, kwc=4.4,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn('TRIPHAS', ' | '.join(resp.data['avertissements']))
        designations = {li.designation for li in devis.lignes.all()}
        for attendu in ('Structures acier', 'Socles', 'Installation',
                        'Transport', 'Tableau De Protection AC/DC'):
            self.assertIn(attendu, designations)
        # Devis NON varianté : le kit ajouté reste COMMUN, comme avant QJR81.
        self.assertEqual({li.variante for li in devis.lignes.all()}, {''})


class TestReparationDevisLesDeuxDivergent(_BaseReparation):
    """QJR81 #2 — l'option AVEC porte ses PROPRES ferrures."""

    slug = 'qjr81-divergent'

    #: 8 panneaux sans stockage, 12 avec : les deux optimums DIVERGENT.
    SANS, AVEC = 8, 12

    def _devis_divergent(self):
        return self._squelette(
            scenario_stocke=SCENARIO_LES_DEUX,
            lignes=((PANNEAU, self.SANS, 'sans'),
                    (PANNEAU, self.AVEC, 'avec'),
                    (RESEAU, 1, 'sans'),
                    (HYBRIDE, 1, 'avec'),
                    (BATTERIE, 1, 'avec')))

    def _quantites(self, devis, designation):
        return {(li.variante or ''): int(li.quantite)
                for li in devis.lignes.all()
                if li.designation == designation}

    def test_chaque_option_recoit_ses_propres_ferrures(self):
        devis = self._devis_divergent()
        # Le calepinage est un PLAFOND (12 panneaux) : l'option SANS reste à 8,
        # l'option AVEC à 12 — la divergence survit à la resynchro.
        resp = self._post(devis, layout(panels=self.AVEC, kwc=6.6,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)

        structures = self._quantites(devis, 'Structures acier')
        self.assertEqual(structures, {'sans': self.SANS, 'avec': self.AVEC},
                         'l’option AVEC ne porte pas ses propres ferrures : '
                         'elle reste sous-structurée (constat QB81)')
        socles = self._quantites(devis, 'Socles')
        self.assertEqual(socles,
                         {'sans': self.SANS * 2, 'avec': self.AVEC * 2})

    def test_le_forfait_de_pose_suit_le_compte_de_son_option(self):
        """L-FORFAIT : 2 000 HT + 250 HT/panneau. 8 panneaux → 4 000,
        12 panneaux → 5 000. Une ligne commune facturerait 4 000 aux deux."""
        devis = self._devis_divergent()
        resp = self._post(devis, layout(panels=self.AVEC, kwc=6.6,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)

        poses = {(li.variante or ''): Decimal(li.prix_unitaire)
                 for li in devis.lignes.all()
                 if li.designation == 'Installation'}
        self.assertEqual(sorted(poses), ['avec', 'sans'])
        self.assertEqual(poses['sans'], Decimal('4000.00'))
        self.assertEqual(poses['avec'], Decimal('5000.00'))

    def test_un_devis_les_deux_non_divergent_reste_en_lignes_communes(self):
        """Témoin négatif : mêmes comptes des deux côtés ⇒ rien à distinguer,
        le kit reste COMMUN — comportement d'avant QJR81, à l'octet."""
        devis = self._squelette(
            scenario_stocke=SCENARIO_LES_DEUX,
            lignes=((PANNEAU, 12, 'sans'), (PANNEAU, 12, 'avec'),
                    (RESEAU, 1, 'sans'), (HYBRIDE, 1, 'avec'),
                    (BATTERIE, 1, 'avec')))
        resp = self._post(devis, layout(panels=12, kwc=6.6,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)

        structures = self._quantites(devis, 'Structures acier')
        self.assertEqual(structures, {'': 12})

    def test_les_ferrures_variantees_sont_ensuite_resynchronisables(self):
        """La raison d'être du #2 : PVSTR ne touche PAS une ferrure commune.
        Estampillées, les deux ferrures suivent enfin leur propre compte."""
        devis = self._devis_divergent()
        self._post(devis, layout(panels=self.AVEC, kwc=6.6,
                                 scenario='avec_batterie'))
        # Second passage : le toit ne porte plus que 10 panneaux — l'option
        # AVEC (12) redescend, l'option SANS (8) ne bouge pas.
        resp = self._post(devis, layout(panels=10, kwc=5.5,
                                        scenario='avec_batterie'))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(self._quantites(devis, 'Structures acier'),
                         {'sans': self.SANS, 'avec': 10})
