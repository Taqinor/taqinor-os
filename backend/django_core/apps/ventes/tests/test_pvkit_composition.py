# -*- coding: utf-8 -*-
"""PVKIT — un devis issu du calepinage porte le KIT COMPLET, pas un squelette.

Ce que ces tests verrouillent, et pourquoi :

1. **Le kit vendu est le kit du simulateur.** Un devis auto ne composait que le
   panneau, l'onduleur et parfois une batterie : trois lignes, alors que le
   client achète aussi ses structures, ses socles, son câblage, son tableau de
   protection, sa pose et son transport. Les quantités et les prix vérifiés ici
   sont ceux de ``autoFillLines`` (frontend/src/features/ventes/solar.js), à la
   règle près — c'est le contrat de parité écran ↔ serveur.
2. **Le Smart Meter et la clé Wifi ne suivent QUE Huawei.** Les vendre derrière
   un onduleur Deye, c'est facturer un accessoire qui ne se connectera jamais.
3. **Un composant absent, ou non tarifé, est SAUTÉ — jamais coté, jamais
   fatal.** Un catalogue incomplet dégrade le kit ; il ne casse pas la vente.
4. **L'étude électrique se déclenche toute seule** derrière la création ET la
   resynchronisation (PV42), sans jamais pouvoir faire perdre le devis, et sans
   se recalculer pour rien quand les entrées n'ont pas bougé (PV41).

Run :
    DB_NAME=erp_ventes python manage.py test \
        apps.ventes.tests.test_pvkit_composition -v 2
"""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.stock.models import FicheTechnique, Produit
from apps.ventes import services
from apps.ventes.models import Devis
from authentication.models import Company

User = get_user_model()

#: Le catalogue tel que ``seed_catalogue`` le sème — désignations EXACTES, car
#: c'est par elles que la composition classe (mots-clés partagés avec le moteur
#: PDF). Prix de vente HT.
CATALOGUE = [
    ('Panneau Jinko 550W', 'PAN550', '1100'),
    ('Onduleur réseau Huawei 5kW Monophasé', 'ONDR5', '14000'),
    ('Onduleur hybride Deye 5kW Monophasé', 'ONDH5', '17000'),
    ('Batterie Dyness 5 kWh', 'BAT5', '16000'),
    ('Batterie Dyness 10 kWh', 'BAT10', '30000'),
    ('Structures acier', 'STR-ACIER', '500'),
    ('Structures aluminium', 'STR-ALU', '850'),
    ('Socles', 'SOC-BET', '80'),
    ('Smart Meter', 'SMART-MET', '1800'),
    ('Wifi Dongle', 'WIFI-DON', '1200'),
    ('Accessoires', 'ACC-CAT', '2000'),
    ('Tableau De Protection AC/DC', 'TAB-PROT', '2000'),
    ('Installation', 'INST-CAT', '4800'),
    ('Transport', 'TRANS-CAT', '1000'),
    ('Suivi journalier, maintenance chaque 12 mois pendant 2 ans',
     'SUIVI-2A', '5000'),
]

#: L-FORFAIT (fondateur 24/08/2026) — le barème AU PANNEAU des trois forfaits,
#: tel que ``seed_catalogue`` le pose : ``(part fixe HT, part par panneau HT)``.
#: Ces trois lignes ne se vendent plus au ``prix_vente`` catalogue ci-dessus :
#: leur montant est ``fixe + par_panneau × nb_panneaux``, et il vit dans le
#: STOCK (champs ``Produit.prix_fixe_ht`` / ``prix_par_panneau_ht``) pour que le
#: fondateur puisse le changer sans toucher au code.
BAREMES_FORFAIT = {
    'INST-CAT': ('2000', '250'),        # 8 p → 4 000 HT ; 16 p → 6 000 HT
    'ACC-CAT': ('0', '52.0833'),        # ancien barème ÷ 2
    'TAB-PROT': ('0', '203.1250'),      # ancien barème + 30 %
}


class _Base(TestCase):
    """8 panneaux de 550 Wc = 4,4 kWc — le cas résidentiel de référence."""

    slug = 'pvkit-co'

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': 'PVKIT'})
        self.user = User.objects.create_user(
            username='pvkit-%s' % self.slug, password='x',
            role_legacy='responsable', company=self.company)
        self.produits = {}
        for nom, sku, prix in CATALOGUE:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[sku] = Produit.objects.create(
                company=self.company, nom=nom, sku='%s-%s' % (sku, self.slug),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                # L-FORFAIT — le barème vit au STOCK : le catalogue de ce
                # montage le porte comme celui de la production.
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))
        self._poser_fiches_techniques()

    def _poser_fiches_techniques(self):
        """PVFCH (fondateur 20/08/2026) — « never invent numbers ».

        La conception électrique ne comble plus une fiche absente avec des
        défauts de marché : elle REFUSE en nommant le champ manquant. Le
        catalogue de ce montage porte donc ses fiches, comme le catalogue
        seedé en production (``seed_catalogue``).
        """
        FicheTechnique.objects.create(
            company=self.company, produit=self.produits['PAN550'],
            type_fiche='module',
            pmax_wc=Decimal('550.00'), voc_v=Decimal('49.90'),
            isc_a=Decimal('14.02'), vmp_v=Decimal('41.80'),
            imp_a=Decimal('13.16'),
            temp_coeff_voc_pct_c=Decimal('-0.270'),
            temp_coeff_pmax_pct_c=Decimal('-0.350'))
        for sku in ('ONDR5', 'ONDH5'):
            FicheTechnique.objects.create(
                company=self.company, produit=self.produits[sku],
                type_fiche='onduleur',
                ond_ac_kw=Decimal('5.00'), ond_phases=1, ond_n_mppt=2,
                ond_mppt_v_min=Decimal('90.0'),
                ond_mppt_v_max=Decimal('560.0'),
                ond_v_max_abs=Decimal('600.0'),
                ond_i_max_mppt_a=Decimal('13.5'),
                ond_rendement_euro_pct=Decimal('97.0'),
                ond_bat_aucune=(sku == 'ONDR5'),
                ond_bat_v_min=(None if sku == 'ONDR5' else Decimal('40.0')),
                ond_bat_v_max=(None if sku == 'ONDR5' else Decimal('60.0')))
        # Les BATTERIES aussi portent leur fiche. Sans elle, la composition
        # n'en retenait AUCUNE et le kit « avec batterie » partait sans
        # stockage : dès que l'onduleur DÉCLARE une plage batterie (ici
        # 40-60 V), ``services._batterie_compatible`` exige une tension
        # MESURÉE et exclut toute candidate muette — c'est le garde-fou voulu
        # (fondateur 18/08 : une composition électriquement invalide ne doit
        # plus sortir d'un repli mot-clé), pas un défaut à contourner. Le
        # montage porte donc les mêmes valeurs constructeur que le catalogue
        # seedé (``seed_catalogue`` BAT-DEY-5/10, Dyness LV 51,2 V).
        for sku, kwh_nom, kwh_util, charge_kw in (
                ('BAT5', '5.12', '4.60', '3.84'),
                ('BAT10', '10.24', '9.22', '5.12')):
            FicheTechnique.objects.create(
                company=self.company, produit=self.produits[sku],
                type_fiche='batterie',
                bat_kwh_nominal=Decimal(kwh_nom),
                bat_kwh_usable=Decimal(kwh_util),
                bat_dod_pct=Decimal('90.0'),
                bat_v_nominal=Decimal('51.2'),
                bat_max_charge_kw=Decimal(charge_kw))

    def _lead(self, email='kit@example.com'):
        return Lead.objects.create(
            company=self.company, nom='Kit', prenom='Complet', email=email)

    def _layout(self, scenario='reseau', panels=8, kwc=4.4):
        return {'scenario': scenario, 'panelWatt': 550,
                'result': {'panels': panels, 'kwc': kwc,
                           'annualKwh': 7400, 'savings': 6300}}

    def _devis(self, **kwargs):
        return services.build_devis_from_layout(
            layout=self._layout(**kwargs), user=self.user,
            company=self.company, lead=self._lead())

    def _kit(self, devis):
        """``{désignation: (quantité, prix unitaire HT)}`` du devis."""
        return {ligne.designation: (int(ligne.quantite),
                                    Decimal(ligne.prix_unitaire))
                for ligne in devis.lignes.all()}


class LeKitResidentielEstComplet(_Base):
    slug = 'pvkit-complet'

    def test_huit_panneaux_sans_batterie_donnent_le_kit_entier(self):
        kit = self._kit(self._devis())

        # Le cœur du système : 8 panneaux, un onduleur qui couvre 4,4 kWc.
        self.assertEqual(kit['Panneau Jinko 550W'],
                         (8, Decimal('1100.00')))
        self.assertEqual(kit['Onduleur réseau Huawei 5kW Monophasé'],
                         (1, Decimal('14000.00')))

        # Le kit de pose : une structure par panneau, deux socles par panneau.
        self.assertEqual(kit['Structures acier'], (8, Decimal('500.00')))
        self.assertEqual(kit['Socles'], (16, Decimal('80.00')))

        # L-FORFAIT (fondateur 24/08/2026) — les trois forfaits se cotent AU
        # PANNEAU, depuis le barème porté par le produit (HT) : une ligne,
        # quantité 1, prix unitaire = total de la formule.
        #   · Installation = 2 000 + 250 × 8  = 4 000 HT  ← ANCRAGE FONDATEUR
        #   · Accessoires  =    52,0833 × 8   =   416,67 HT (ancien ÷ 2)
        #   · Tableau      =   203,1250 × 8   = 1 625,00 HT (ancien + 30 %)
        self.assertEqual(kit['Accessoires'], (1, Decimal('416.67')))
        self.assertEqual(kit['Tableau De Protection AC/DC'],
                         (1, Decimal('1625.00')))
        self.assertEqual(kit['Installation'], (1, Decimal('4000.00')))
        self.assertEqual(kit['Transport'], (1, Decimal('1000.00')))

        # Onduleur Huawei ⇒ le duo de supervision suit.
        self.assertEqual(kit['Smart Meter'], (1, Decimal('1800.00')))
        self.assertEqual(kit['Wifi Dongle'], (1, Decimal('1200.00')))

        # Scénario réseau : ni hybride, ni batterie.
        self.assertNotIn('Onduleur hybride Deye 5kW Monophasé', kit)
        self.assertNotIn('Batterie Dyness 5 kWh', kit)
        # Le suivi est à quantité nulle au simulateur : jamais enregistré.
        self.assertNotIn(
            'Suivi journalier, maintenance chaque 12 mois pendant 2 ans', kit)
        # Une seule structure : le type non retenu reste à 0.
        self.assertNotIn('Structures aluminium', kit)

    def test_le_scenario_batterie_permute_onduleur_et_ajoute_le_stockage(self):
        kit = self._kit(self._devis(scenario='avec_batterie'))

        self.assertEqual(kit['Onduleur hybride Deye 5kW Monophasé'],
                         (1, Decimal('17000.00')))
        self.assertNotIn('Onduleur réseau Huawei 5kW Monophasé', kit)
        # 4,4 kWc → cible 5 kWh : un module de 5, aucun de 10.
        self.assertEqual(kit['Batterie Dyness 5 kWh'],
                         (1, Decimal('16000.00')))
        self.assertNotIn('Batterie Dyness 10 kWh', kit)
        # Le reste du kit ne bouge pas d'un pouce.
        self.assertEqual(kit['Structures acier'], (8, Decimal('500.00')))
        self.assertEqual(kit['Socles'], (16, Decimal('80.00')))
        # Onduleur Deye ⇒ AUCUN accessoire Huawei (ils ne s'y connectent pas).
        self.assertNotIn('Smart Meter', kit)
        self.assertNotIn('Wifi Dongle', kit)

    def test_une_grosse_installation_monte_les_paliers(self):
        """20 panneaux = 11 kWc : les forfaits suivent, et 3 modules de bat."""
        kit = self._kit(self._devis(scenario='avec_batterie',
                                    panels=20, kwc=11.0))
        self.assertEqual(kit['Panneau Jinko 550W'][0], 20)
        self.assertEqual(kit['Structures acier'][0], 20)
        self.assertEqual(kit['Socles'][0], 40)
        # L-FORFAIT — 20 panneaux : 52,0833×20 / 203,1250×20 / 2 000+250×20.
        # (L'ancienne règle par blocs les figeait au MÊME prix qu'à 16
        # panneaux, 11 kWc et 8,8 kWc tombant tous deux sur 2 blocs.)
        self.assertEqual(kit['Accessoires'][1], Decimal('1041.67'))
        self.assertEqual(kit['Tableau De Protection AC/DC'][1],
                         Decimal('4062.50'))
        self.assertEqual(kit['Installation'][1], Decimal('7000.00'))
        # Cible batterie = 10 kWh → un module de 10, aucun de 5.
        self.assertEqual(kit['Batterie Dyness 10 kWh'][0], 1)
        self.assertNotIn('Batterie Dyness 5 kWh', kit)
        # 11 kWc contre un hybride de 5 kW (seuil 8,8) : il en faut 3.
        self.assertEqual(kit['Onduleur hybride Deye 5kW Monophasé'][0], 3)

    def test_la_composition_est_une_fonction_pure_et_deterministe(self):
        produits = services.catalogue_de_la_societe(self.company)
        premier = services.composition_residentielle(
            produits, kwc=4.4, panel_watt=550, nb_panneaux=8)
        second = services.composition_residentielle(
            produits, kwc=4.4, panel_watt=550, nb_panneaux=8)
        self.assertEqual([(li.designation, li.quantite, li.prix_unitaire)
                          for li in premier],
                         [(li.designation, li.quantite, li.prix_unitaire)
                          for li in second])
        self.assertEqual(Devis.objects.count(), 0, 'la composition a écrit')

    def test_puissance_nulle_ne_compose_rien(self):
        self.assertEqual(services.composition_residentielle(
            services.catalogue_de_la_societe(self.company),
            kwc=0, panel_watt=550), [])


class LeForfaitSeCoteAuPanneau(_Base):
    """L-FORFAIT (ordre fondateur 24/08/2026).

    « change the rule of calculating instalation cost to be per pannel plus
    2000dh HT always there plus 250 dh HT per pannel, so 8 pannels is still
    4000dh HT and 16 pannels is 6000dh HT. but now what is inbetween changes,
    also make the same for the tableau AC DC and the accesoirs, also now reduce
    the price of accesoirs by half and add 30% to tableau DC AC total price »

    Puis, le même jour : « dans le stock ceci devra être bien fait, c'est-à-dire
    chaque case de installation, tableau AC/DC et accessoires devra avoir une
    partie fixe et une par panneau que je pourrai changer par la suite ».

    Ces tests verrouillent LES DEUX moitiés : les ancrages chiffrés du
    fondateur, et le fait que le barème vive dans le STOCK (donc qu'il suive
    une saisie du fondateur sans qu'on retouche au code).
    """

    slug = 'pvkit-forfait'

    def _forfaits(self, panneaux, kwc):
        kit = self._kit(self._devis(panels=panneaux, kwc=kwc))
        return (kit['Accessoires'][1],
                kit['Tableau De Protection AC/DC'][1],
                kit['Installation'][1])

    def test_les_deux_ancrages_du_fondateur_sont_tenus(self):
        """8 → 4 000 HT et 16 → 6 000 HT, exactement comme avant."""
        self.assertEqual(self._forfaits(8, 4.4)[2], Decimal('4000.00'))
        self.assertEqual(self._forfaits(16, 8.8)[2], Decimal('6000.00'))

    def test_l_entre_deux_se_lisse_au_lieu_de_sauter(self):
        """Le cœur de l'ordre : « what is inbetween changes ».

        L'ancienne règle par blocs de 5 kWc cotait 8, 10 ET 12 panneaux au
        MÊME prix (tous dans le premier bloc), puis sautait d'une marche
        entière. La droite au panneau les sépare.
        """
        acc10, tab10, inst10 = self._forfaits(10, 5.5)
        # Installation : 2 000 + 250 × 10 — pile entre les deux ancrages.
        self.assertEqual(inst10, Decimal('4500.00'))
        # Accessoires : 52,0833 × 10 ; Tableau : 203,1250 × 10.
        self.assertEqual(acc10, Decimal('520.83'))
        self.assertEqual(tab10, Decimal('2031.25'))
        # …et 9 panneaux ne coûtent PAS la même chose que 10.
        self.assertEqual(self._forfaits(9, 4.95)[2], Decimal('4250.00'))

    def test_accessoires_moitie_et_tableau_plus_30_pct(self):
        """Les deux corrections de barème, aux ancrages du fondateur.

        Ancienne règle : Accessoires 833,33 HT à 8 panneaux et 1 666,67 à 16 ;
        Tableau 1 250,00 et 2 500,00. La MOITIÉ et le + 30 % se lisent donc
        directement sur ces quatre montants.
        """
        acc8, tab8, _ = self._forfaits(8, 4.4)
        acc16, tab16, _ = self._forfaits(16, 8.8)
        self.assertEqual(acc8, Decimal('416.67'))    # 833,33 ÷ 2
        self.assertEqual(acc16, Decimal('833.33'))   # 1 666,67 ÷ 2
        self.assertEqual(tab8, Decimal('1625.00'))   # 1 250,00 × 1,30
        self.assertEqual(tab16, Decimal('3250.00'))  # 2 500,00 × 1,30

    def test_chaque_forfait_reste_une_seule_ligne_a_l_unite(self):
        """Une ligne, quantité 1, prix unitaire = le total. Désignations
        INCHANGÉES — le moteur PDF classe par elles."""
        kit = self._kit(self._devis())
        for designation in ('Accessoires', 'Tableau De Protection AC/DC',
                            'Installation'):
            self.assertEqual(kit[designation][0], 1, designation)

    def test_le_barreme_se_change_depuis_le_stock(self):
        """Le fondateur change ``prix_par_panneau_ht`` : le devis suit.

        C'est TOUTE la raison pour laquelle le barème vit au catalogue et non
        dans le code — vérifié sans toucher à une ligne de Python.
        """
        Produit.objects.filter(
            company=self.company, nom='Installation').update(
                prix_fixe_ht=Decimal('3000'),
                prix_par_panneau_ht=Decimal('300'))
        # 3 000 + 300 × 8 = 5 400 HT.
        self.assertEqual(self._forfaits(8, 4.4)[2], Decimal('5400.00'))

    def test_une_part_fixe_seule_suffit(self):
        """Un seul des deux champs renseigné suffit à basculer la ligne sur le
        barème : le forfait devient alors un montant PLAT."""
        Produit.objects.filter(
            company=self.company, nom='Accessoires').update(
                prix_fixe_ht=Decimal('750'), prix_par_panneau_ht=None)
        self.assertEqual(self._forfaits(8, 4.4)[0], Decimal('750.00'))
        self.assertEqual(self._forfaits(16, 8.8)[0], Decimal('750.00'))

    def test_sans_bareme_le_produit_garde_son_prix_de_vente(self):
        """Les deux champs vides ⇒ ``prix_vente`` catalogue, comme avant et
        comme tout le reste du catalogue (aucun produit existant ne change de
        prix du seul fait de la migration)."""
        Produit.objects.filter(
            company=self.company,
            nom__in=['Accessoires', 'Tableau De Protection AC/DC',
                     'Installation']).update(
                prix_fixe_ht=None, prix_par_panneau_ht=None)
        acc, tab, inst = self._forfaits(8, 4.4)
        self.assertEqual(acc, Decimal('2000.00'))    # prix_vente du catalogue
        self.assertEqual(tab, Decimal('2000.00'))
        self.assertEqual(inst, Decimal('4800.00'))

    def test_le_taux_de_tva_du_devis_ne_change_plus_les_forfaits(self):
        """Le barème est dicté EN HT : il ne se reconvertit plus depuis un TTC,
        donc un devis à 10 % porte les mêmes montants forfaitaires qu'à 20 %."""
        produits = services.catalogue_de_la_societe(self.company)
        montants = []
        for taux in (Decimal('20'), Decimal('10')):
            lignes = services.composition_residentielle(
                produits, kwc=4.4, panel_watt=550, nb_panneaux=8,
                taux_tva=taux)
            montants.append({li.designation: li.prix_unitaire
                             for li in lignes}['Installation'])
        self.assertEqual(montants[0], Decimal('4000.00'))
        self.assertEqual(montants[0], montants[1])


class LeCatalogueIncompletDegradeSansCasser(_Base):
    slug = 'pvkit-degrade'

    def test_un_composant_absent_est_saute(self):
        Produit.objects.filter(
            company=self.company,
            nom__in=['Socles', 'Transport', 'Structures acier']).delete()
        kit = self._kit(self._devis())
        self.assertNotIn('Socles', kit)
        self.assertNotIn('Transport', kit)
        self.assertNotIn('Structures acier', kit)
        # Le reste du kit est bien là : la vente n'est pas perdue.
        self.assertEqual(kit['Panneau Jinko 550W'][0], 8)
        self.assertEqual(kit['Installation'][0], 1)

    def test_un_composant_sans_prix_n_est_jamais_cote(self):
        """Règle du dépôt : un produit non tarifé ne part JAMAIS en devis."""
        Produit.objects.filter(
            company=self.company,
            nom__in=['Structures acier', 'Accessoires']).update(
                prix_vente=Decimal('0'))
        kit = self._kit(self._devis())
        self.assertNotIn('Structures acier', kit)
        self.assertNotIn('Accessoires', kit)
        for quantite, prix in kit.values():
            self.assertGreater(prix, 0)

    def test_un_catalogue_sans_prix_du_tout_ne_produit_aucune_ligne(self):
        Produit.objects.filter(company=self.company).update(
            prix_vente=Decimal('0'))
        devis = self._devis()
        self.assertEqual(devis.lignes.count(), 0)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_le_catalogue_d_une_autre_societe_ne_fuite_pas(self):
        # On RETIRE notre structure : si le scoping société fuitait, celle de
        # la voisine serait le seul candidat — et elle entrerait dans le kit.
        Produit.objects.filter(company=self.company,
                               nom='Structures acier').delete()
        autre, _ = Company.objects.get_or_create(
            slug='pvkit-autre', defaults={'nom': 'Autre'})
        Produit.objects.create(
            company=autre, nom='Structures acier VOISINE', sku='STR-VOISIN',
            prix_vente=Decimal('1'), prix_achat=Decimal('1'),
            quantite_stock=10)
        kit = self._kit(self._devis())
        self.assertNotIn('Structures acier VOISINE', kit)
        self.assertNotIn('Structures acier', kit)


class LEtudeElectriqueSuitToutSeule(_Base):
    """PV42/PV41 — la pièce technique est calculée sans clic, et sans risque."""

    slug = 'pvkit-elec'

    def test_la_creation_pose_la_conception_electrique(self):
        devis = self._devis()
        devis.refresh_from_db()
        self.assertIsInstance(devis.electrical_design, dict)
        self.assertTrue(devis.electrical_design.get('chaines'))
        self.assertEqual(len(devis.electrical_design_hash), 64)
        # Règle #4 : la pièce technique n'a touché aucun statut.
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_recalculer_aux_memes_entrees_n_ecrit_rien(self):
        devis = self._devis()
        devis.refresh_from_db()
        empreinte = devis.electrical_design_hash
        # Marqueur : si le second appel RÉÉCRIT la conception, il disparaît.
        devis.electrical_design = dict(devis.electrical_design,
                                       _marqueur='intact')
        devis.save(update_fields=['electrical_design'])

        services.concevoir_electrique_du_devis(devis, origine='test')

        devis.refresh_from_db()
        self.assertEqual(devis.electrical_design.get('_marqueur'), 'intact')
        self.assertEqual(devis.electrical_design_hash, empreinte)

    def test_la_resynchro_recalcule_la_conception(self):
        devis = self._devis()
        devis.refresh_from_db()
        avant = devis.electrical_design_hash

        services.sync_devis_from_layout(
            devis, self._layout(panels=16, kwc=8.8), user=self.user)

        devis.refresh_from_db()
        self.assertNotEqual(devis.electrical_design_hash, avant)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_une_panne_electrique_ne_fait_pas_perdre_le_devis(self):
        with patch('apps.ventes.electrical_service.build_electrical_design',
                   side_effect=RuntimeError('moteur électrique HS')):
            devis = self._devis()
        devis.refresh_from_db()
        self.assertIsNone(devis.electrical_design)
        # Le devis, lui, est COMPLET : le kit entier est en base.
        kit = self._kit(devis)
        self.assertEqual(kit['Panneau Jinko 550W'][0], 8)
        self.assertEqual(kit['Structures acier'][0], 8)
        self.assertEqual(kit['Installation'][0], 1)
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_une_panne_electrique_ne_bloque_pas_la_resynchro(self):
        devis = self._devis()
        with patch('apps.ventes.electrical_service.build_electrical_design',
                   side_effect=RuntimeError('moteur électrique HS')):
            resultat = services.sync_devis_from_layout(
                devis, self._layout(panels=16, kwc=8.8), user=self.user)
        self.assertFalse(resultat['inchange'])
        devis.refresh_from_db()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
