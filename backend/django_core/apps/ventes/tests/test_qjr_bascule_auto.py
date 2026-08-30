# -*- coding: utf-8 -*-
"""QJR96 (M5, bascule 4/5) — le DEVIS AUTOMATIQUE et le TUNNEL.

``build_devis_auto`` et ``creer_devis_automatique_depuis_lead`` sont devenus des
ADAPTATEURS : ils gardent ce qu'eux seuls savent faire — lire une fiche lead,
arrêter une taille, poser les portes d'idempotence du tunnel — et confient tout
le reste à ``pipeline.appliquer`` (``origine='auto'`` / ``origine='tunnel'``).
Le corps qui rebâtissait un layout pour le repasser à ``build_devis_from_layout``
est SUPPRIMÉ : c'est le chemin où AUCUN commercial n'est dans la boucle, et il
compose désormais par LE MÊME composeur que l'écran, écrit ses lignes par
L'ÉCRIVAIN UNIQUE et se fait pré-vérifier par LA MÊME étape.

CE QUE CE FICHIER PROUVE, ET DANS QUEL REGISTRE.

* GOLDEN (égalité stricte) — LES LIGNES CRÉÉES sur TROIS leads (les deux
  options, « avec » seule, « sans » seule). Les attentes sont DÉRIVÉES et
  écrites en dur, chacune avec sa dérivation depuis la fixture : l'ancien corps
  a disparu, il ne peut plus servir de référence.
* GOLDEN — LE TUNNEL EST LE CHEMIN AUTO. Deux leads jumeaux, l'un chiffré par
  ``build_devis_auto`` (le bouton du commercial), l'autre par
  ``creer_devis_automatique_depuis_lead`` (le webhook), rendent le MÊME jeu de
  lignes et la MÊME étude. Seule l'ORIGINE déclarée au pipeline diffère.
* RÈGLE CONSERVÉE — « une puissance DEMANDÉE gagne sur le moteur, et ne
  réécrit JAMAIS la fiche du lead ». Elle est portée par la CIBLE souveraine de
  l'étape 2 (``decider_taille`` rend l'intention telle quelle et n'appelle pas
  le moteur), et le lead ressort de la création à l'octet près.
* NON-RÉGRESSION — le tracé du client survit à la bascule : la zone roofPro11,
  ``_pans_geometry`` et ``etude_params['toiture']`` sont les mêmes qu'avant,
  parce que le layout est lu par LE MÊME lecteur.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_qjr_bascule_auto -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.domain import creation as _creation
from apps.ventes.domain.pipeline import (
    ORIGINE_AUTO, ORIGINE_TUNNEL, MSG_SANS_BATTERIE, MSG_SANS_ONDULEUR_RESEAU,
)
from apps.ventes.domain.taille import AutoDevisError
from apps.ventes.models import Devis
from apps.ventes.services import (
    build_devis_auto, creer_devis_automatique_depuis_lead,
)

User = get_user_model()

#: Le catalogue MINIMAL, identique en nommage à ``seed_catalogue`` : quatre
#: produits, un par rôle. Le kit complet du simulateur (structures, socles,
#: accessoires, tableau de protection, pose, transport) est ABSENT du
#: catalogue, donc simplement SAUTÉ par la composition — c'est ce qui rend le
#: jeu de lignes attendu court et énumérable ici.
PRIX = {
    'panneau': Decimal('1100'),
    'onduleur_reseau': Decimal('14000'),
    'onduleur_hybride': Decimal('17000'),
    'batterie': Decimal('17000'),
}

#: Ancrage de productible des fixtures (leçon #86) — sans ville ni GPS le
#: moteur ne sait rien du site. Les fixtures GOLDEN ci-dessous ne le SOLLICITENT
#: pas (elles portent une taille demandée, donc souveraine), mais les quatre
#: études qui suivent la création le lisent.
VILLE_ANCRE = 'Casablanca'

#: LA TAILLE DEMANDÉE DES FIXTURES, choisie pour que la conversion tombe JUSTE.
#: ``_residential_panel_count`` est un PLAFOND (U1) sur le panneau de
#: dimensionnement à 710 Wc : 7,1 kWc × 1000 / 710 = 10,0 pile, donc 10
#: panneaux sans arrondi discutable, et kWc = 10 × 710 / 1000 = 7,10.
TAILLE_KWC = Decimal('7.1')
PANNEAUX_ATTENDUS = 10

#: LE kWc STOCKÉ (QJR63) — il vient des LIGNES, jamais de la taille demandée :
#: 10 panneaux du catalogue RÉEL (« Panneau Jinko 550W ») = 5 500 W = 5,50 kWc.
#: Les 7,10 kWc du dimensionnement sont la DEMANDE, pas ce que le catalogue a
#: su servir — les stocker mettrait deux bases de puissance dans le document.
KWC_STOCKE = 5.5

# ── LES QUANTITÉS DÉRIVÉES DU KIT — CALCULÉES, JAMAIS ÉCRITES DE MÉMOIRE ─────
#
# Une attente de golden posée « de mémoire » est un aller-retour de CI garanti :
# c'est très exactement ce qui a coûté une ronde à ce fichier (et une autre à
# ``test_qjr_bascule_3d`` avant lui). Chaque nombre ci-dessous est donc DÉRIVÉ
# de la fixture, avec son calcul écrit, contre la règle réelle de
# ``domain/composition.composition_residentielle``.
#
# LE CHAMP PV COMPOSÉ. L'adaptateur passe au composeur le kWc du
# DIMENSIONNEMENT (panneau de référence à 710 Wc), pas celui du catalogue :
#
#     kwp = 10 panneaux × 710 Wc / 1000 = 7,10 kWc
#
# LES ONDULEURS — ``quantite_onduleur`` : « un onduleur suffit dès qu'il couvre
# le seuil ; sinon on en met assez pour absorber le champ », le seuil valant
# 80 % de la puissance :
#
#     seuil                                 = 7,10 × 0,8 = 5,68 kW
#     les DEUX onduleurs de cette fixture   =        5 kW → 5 < 5,68
#     quantité = plafond(kwp / kW_onduleur) = plafond(7,10 / 5) = plafond(1,42)
#                                           = 2
#
# Les deux familles (réseau et hybride) portent le MÊME palier 5 kW, donc la
# MÊME quantité : cette fixture exerce la branche MULTI-ONDULEURS des deux
# côtés. (Le témoin de l'autre branche vit dans ``test_qjr_bascule_3d``, où
# 5,5 kWc ⇒ seuil 4,4 kW ≤ 5 kW ⇒ ×1.)
ONDULEURS_ATTENDUS = 2

# LA BATTERIE — capacité VISÉE puis modules du calibre catalogue. Aucun
# ``batterie_cible_kwh`` n'est transmis sur le chemin d'une taille DEMANDÉE
# (le moteur n'est pas appelé, donc pas d'optimum « avec ») : la règle
# historique kWc/5 décide seule.
#
#     cible_kwh = max(5, arrondi(kwp / 5) × 5) = max(5, arrondi(1,42) × 5)
#               = max(5, 1 × 5) = 5 kWh
#     calibre du catalogue (« Batterie Dyness 5 kWh »)          = 5 kWh
#     modules   = max(1, plafond(cible_kwh / calibre))          = 1
BATTERIES_ATTENDUES = 1

# Un carré d'environ 20 m de côté à Casablanca, en [lat, lng] — la forme
# EXACTE que le webhook range dans ``Lead.roof_outline``.
_LAT0, _LNG0 = 33.5731, -7.5898
CONTOUR_LATLNG = [
    [_LAT0, _LNG0],
    [_LAT0, _LNG0 + 0.000216],
    [_LAT0 + 0.00018, _LNG0 + 0.000216],
    [_LAT0 + 0.00018, _LNG0],
]


class _BaseAuto(TestCase):
    def setUp(self):
        from authentication.models import Company

        self.company, _ = Company.objects.get_or_create(
            slug='qjr96-co', defaults={'nom': 'QJR96 Co'})
        self.user = User.objects.create_user(
            username='qjr96user', password='x', role_legacy='responsable',
            company=self.company)
        # Un golden qui rougit doit DIRE ce qui diverge. Sans ceci, unittest
        # abrège le dict (« Diff is N characters long ») et le log de CI ne
        # montre plus la valeur réelle — l'abréviation a déjà coûté un
        # aller-retour entier à la lane jumelle (``test_qjr_bascule_3d``).
        self.maxDiff = None
        self._seed()

    def _seed(self):
        def mk(nom, sku, prix):
            return Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=prix, prix_achat=Decimal('1'), quantite_stock=100)

        self.panneau = mk('Panneau Jinko 550W', 'QJR96-PAN', PRIX['panneau'])
        self.reseau = mk('Onduleur réseau Huawei 5kW Monophasé',
                         'QJR96-ONDR', PRIX['onduleur_reseau'])
        self.hybride = mk('Onduleur hybride Deye 5kW Monophasé',
                          'QJR96-ONDH', PRIX['onduleur_hybride'])
        self.batterie = mk('Batterie Dyness 5 kWh', 'QJR96-BAT',
                           PRIX['batterie'])

    def _lead(self, **extra):
        extra.setdefault('ville', VILLE_ANCRE)
        extra.setdefault('email', 'auto-qjr96@example.com')
        extra.setdefault('taille_souhaitee_kwc', TAILLE_KWC)
        return Lead.objects.create(
            company=self.company, nom='Auto', prenom='QJR96', **extra)

    def _par_designation(self, devis):
        """Les lignes créées, indexées par désignation.

        L'ORDRE des lignes est celui de la société (PVORD) et appartient à
        ``composer``, que cette bascule ne touche pas : ce que le golden épingle
        ici est le CONTENU écrit ; la propriété d'ORDRE est vérifiée séparément
        par :meth:`_assert_ordre_explicite`.
        """
        return {
            li.designation: (Decimal(str(li.quantite)),
                             Decimal(str(li.prix_unitaire)),
                             li.variante, li.remise)
            for li in devis.lignes.all()
        }

    def _assert_ordre_explicite(self, devis):
        """U3/PVORD — l'ordre VOULU est posé EXPLICITEMENT, jamais laissé au
        tri de repli sur ``id``."""
        ordres = sorted(li.ordre for li in devis.lignes.all())
        self.assertEqual(ordres, list(range(devis.lignes.count())))

    def _origines_declarees(self):
        """Enregistre l'``origine`` de chaque ``IntentionDevis`` qui atteint le
        pipeline, SANS remplacer le pipeline : l'espion délègue au vrai."""
        vrai = _creation.appliquer
        vues = []

        def _espion(devis, intention):
            vues.append(intention.origine)
            return vrai(devis, intention)

        _creation.appliquer = _espion
        self.addCleanup(setattr, _creation, 'appliquer', vrai)
        return vues


class GoldenLeadLesDeuxOptions(_BaseAuto):
    """FIXTURE 1 — le lead ne dit RIEN de la batterie : les DEUX options (U2).

    DÉRIVATION DE LA TAILLE. ``taille_souhaitee_kwc = 7,1`` est une puissance
    DEMANDÉE : elle gagne sur le moteur (qui n'est même pas appelé) et vaut
    ``plafond(7 100 / 710) = 10`` panneaux, soit 7,10 kWc de dimensionnement.

    DÉRIVATION DES LIGNES (catalogue minimal : tout ce qui n'y est pas est
    sauté ; ``deux_options`` compose les DEUX onduleurs et la batterie ; les
    quantités viennent du bloc de dérivation en tête de module) :

        Panneau Jinko 550W                      ×10 à 1 100,00
        Onduleur réseau Huawei 5kW Monophasé    × 2 à 14 000,00
        Onduleur hybride Deye 5kW Monophasé     × 2 à 17 000,00
        Batterie Dyness 5 kWh                   × 1 à 17 000,00

    Toutes COMMUNES (``variante=''``) : sans ``dimensionnement_avec``, les deux
    options partagent le MÊME champ PV et la composition reste mono-optimum —
    c'est le repli documenté de la fusion L-2OPT.
    """

    def _construire(self):
        return build_devis_auto(lead=self._lead(), user=self.user,
                                company=self.company)

    def test_golden_les_lignes_creees(self):
        devis = self._construire()
        self.assertEqual(self._par_designation(devis), {
            'Panneau Jinko 550W': (
                Decimal(PANNEAUX_ATTENDUS), PRIX['panneau'], '', Decimal('0')),
            # ×2 : 5 kW < seuil (0,8 × 7,10 = 5,68) ⇒ plafond(7,10/5) = 2.
            'Onduleur réseau Huawei 5kW Monophasé': (
                Decimal(ONDULEURS_ATTENDUS), PRIX['onduleur_reseau'], '',
                Decimal('0')),
            'Onduleur hybride Deye 5kW Monophasé': (
                Decimal(ONDULEURS_ATTENDUS), PRIX['onduleur_hybride'], '',
                Decimal('0')),
            # ×1 : cible 5 kWh (arrondi(7,10/5) × 5) servie par un module 5 kWh.
            'Batterie Dyness 5 kWh': (
                Decimal(BATTERIES_ATTENDUES), PRIX['batterie'], '',
                Decimal('0')),
        })
        self._assert_ordre_explicite(devis)

    def test_golden_le_devis_reste_un_brouillon_numerote(self):
        """Ce service ne CRÉE que : aucun statut aval n'est jamais touché
        (règle #4), et la référence passe par l'util anti-collision."""
        devis = self._construire()
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)
        self.assertEqual(devis.company_id, self.company.id)
        self.assertTrue(devis.reference.startswith('DEV-'))
        self.assertEqual(devis.mode_installation,
                         Devis.ModeInstallation.RESIDENTIEL)

    def test_golden_l_etude(self):
        devis = self._construire()
        etude = devis.etude_params or {}
        # Les lignes servent RÉELLEMENT les deux côtés (réseau ET hybride ET
        # batterie) : la garde anti-mensonge d'U2 est satisfaite.
        self.assertEqual(etude['scenario'], 'Les deux (Sans + Avec)')
        # QJR63 — le kWc vient des LIGNES (10 × 550 W), jamais des 7,10 kWc
        # demandés ni des 710 Wc du panneau de dimensionnement.
        self.assertEqual(etude['puissance_kwc'], KWC_STOCKE)

    def test_golden_le_layout_synthetique_est_range_avec_le_devis(self):
        """Sans tracé client, le layout du devis automatique ne porte que le
        bloc ``result`` et son wattage de dimensionnement — aucune géométrie
        n'est inventée."""
        devis = self._construire()
        self.assertEqual(devis.roof_layout['result'],
                         {'panels': PANNEAUX_ATTENDUS, 'kwc': 7.1})
        self.assertEqual(devis.roof_layout['panelWatt'], 710)
        self.assertNotIn('zones', devis.roof_layout)

    def test_l_origine_declaree_au_pipeline_est_auto(self):
        vues = self._origines_declarees()
        self._construire()
        self.assertEqual(vues, [ORIGINE_AUTO])


class GoldenLeadAvecBatterie(_BaseAuto):
    """FIXTURE 2 — ``batterie_souhaitee='avec'`` : le stockage SEUL.

    Un choix EXPLICITE du lead reste souverain (U2) : on ne repropose pas une
    option que le client a déjà écartée. La composition est MONO « avec », donc
    (mêmes dérivations qu'en tête de module : seuil 5,68 kW, cible 5 kWh)

        Panneau Jinko 550W                  ×10 à 1 100,00
        Onduleur hybride Deye 5kW Monophasé × 2 à 17 000,00
        Batterie Dyness 5 kWh               × 1 à 17 000,00

    et JAMAIS l'onduleur réseau — c'est le dict COMPLET, donc son absence est
    épinglée par l'égalité elle-même.

    ``optimum_avec`` reste ``None`` : le moteur n'est pas appelé sur le chemin
    d'une puissance DEMANDÉE — elle vaut pour les deux axes, et la batterie
    retombe donc sur la règle historique kWc/5.
    """

    def _construire(self):
        return build_devis_auto(
            lead=self._lead(batterie_souhaitee='avec'),
            user=self.user, company=self.company)

    def test_golden_les_lignes_creees(self):
        devis = self._construire()
        self.assertEqual(self._par_designation(devis), {
            'Panneau Jinko 550W': (
                Decimal(PANNEAUX_ATTENDUS), PRIX['panneau'], '', Decimal('0')),
            # ×2 : 5 kW < seuil (0,8 × 7,10 = 5,68) ⇒ plafond(7,10/5) = 2.
            'Onduleur hybride Deye 5kW Monophasé': (
                Decimal(ONDULEURS_ATTENDUS), PRIX['onduleur_hybride'], '',
                Decimal('0')),
            # ×1 : cible 5 kWh (arrondi(7,10/5) × 5) servie par un module 5 kWh.
            'Batterie Dyness 5 kWh': (
                Decimal(BATTERIES_ATTENDUES), PRIX['batterie'], '',
                Decimal('0')),
        })
        self._assert_ordre_explicite(devis)

    def test_golden_l_etude(self):
        devis = self._construire()
        etude = devis.etude_params or {}
        self.assertEqual(etude['scenario'], 'Avec batterie')
        self.assertEqual(etude['puissance_kwc'], KWC_STOCKE)


class GoldenLeadSansBatterie(_BaseAuto):
    """FIXTURE 3 — ``batterie_souhaitee='sans'`` : le réseau SEUL.

        Panneau Jinko 550W                   ×10 à 1 100,00
        Onduleur réseau Huawei 5kW Monophasé × 2 à 14 000,00

    et AUCUNE batterie, AUCUN onduleur hybride (dict COMPLET : leur absence est
    épinglée par l'égalité). La quantité d'onduleur vient de la même dérivation
    qu'en tête de module — seuil 5,68 kW, palier catalogue 5 kW.
    """

    def _construire(self):
        return build_devis_auto(
            lead=self._lead(batterie_souhaitee='sans'),
            user=self.user, company=self.company)

    def test_golden_les_lignes_creees(self):
        devis = self._construire()
        self.assertEqual(self._par_designation(devis), {
            'Panneau Jinko 550W': (
                Decimal(PANNEAUX_ATTENDUS), PRIX['panneau'], '', Decimal('0')),
            # ×2 : 5 kW < seuil (0,8 × 7,10 = 5,68) ⇒ plafond(7,10/5) = 2.
            'Onduleur réseau Huawei 5kW Monophasé': (
                Decimal(ONDULEURS_ATTENDUS), PRIX['onduleur_reseau'], '',
                Decimal('0')),
        })
        self._assert_ordre_explicite(devis)

    def test_golden_l_etude(self):
        devis = self._construire()
        etude = devis.etude_params or {}
        self.assertEqual(etude['scenario'], 'Sans batterie')
        self.assertEqual(etude['puissance_kwc'], KWC_STOCKE)


class LaTailleDemandeeGagneEtNeReecritJamaisLeLead(_BaseAuto):
    """LA RÈGLE CONSERVÉE PAR LA BASCULE (QJR63 / registre de surcharges).

    « ``target_kwc`` / ``lead.taille_souhaitee_kwc`` gagne sur le moteur, et ne
    réécrit JAMAIS la fiche du lead. »

    ELLE EST PORTÉE PAR LA CIBLE SOUVERAINE, pas par un ``if`` recopié : une
    ``IntentionDevis`` qui porte une ``cible`` fait rendre cette cible TELLE
    QUELLE par l'étape 2 (``decider_taille``), qui n'interroge alors aucun
    moteur. Et la fiche du lead n'est jamais écrite : ce choix vaut POUR CE
    DEVIS-LÀ.

    CE QUE LA BASCULE NE FAIT PAS, ET POURQUOI. Elle ne POSE aucune entrée dans
    ``Devis.overrides`` : les chemins ``taille.*`` du registre (D12) portent des
    déclarations HUMAINES (``manuel``/``import``/``api``) que
    ``puissance_kwc_du_devis`` fait gagner sur les lignes. Un chemin automatique
    qui en poserait une signerait d'une main humaine un chiffre que personne n'a
    tapé, et ferait publier la puissance DEMANDÉE là où QJR63 a établi que
    seules les LIGNES font foi.
    """

    def test_le_moteur_n_est_pas_appele_quand_une_taille_est_demandee(self):
        """Les DEUX porteurs du nom sont espionnés : l'adaptateur
        (``domain.creation``) ET l'étape 2 (``domain.pipeline``), chacun ayant
        importé la fonction dans SON espace de noms. Espionner un seul des deux
        laisserait passer un dimensionnement fait de l'autre côté."""
        from apps.ventes.domain import pipeline as _pipeline

        appels = []

        for module in (_creation, _pipeline):
            vrai = module._panneaux_dimensionnement_horaire

            def _espion(_vrai=vrai, **kwargs):
                appels.append(kwargs)
                return _vrai(**kwargs)

            module._panneaux_dimensionnement_horaire = _espion
            self.addCleanup(setattr, module,
                            '_panneaux_dimensionnement_horaire', vrai)

        devis = build_devis_auto(lead=self._lead(), user=self.user,
                                 company=self.company)
        self.assertEqual(appels, [])
        panneau = devis.lignes.get(designation='Panneau Jinko 550W')
        self.assertEqual(int(panneau.quantite), PANNEAUX_ATTENDUS)

    def test_target_kwc_gagne_sur_la_taille_de_la_fiche(self):
        """5 kWc demandés POUR CE DEVIS : ``plafond(5 000 / 710) = 8``
        panneaux, contre les 10 de la taille souhaitée du lead."""
        lead = self._lead()
        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company, target_kwc='5')
        panneau = devis.lignes.get(designation='Panneau Jinko 550W')
        self.assertEqual(int(panneau.quantite), 8)

    def test_la_fiche_du_lead_ressort_intacte(self):
        lead = self._lead()
        avant = (lead.taille_souhaitee_kwc, lead.batterie_souhaitee)
        build_devis_auto(lead=lead, user=self.user, company=self.company,
                         target_kwc='5')
        lead.refresh_from_db()
        self.assertEqual((lead.taille_souhaitee_kwc, lead.batterie_souhaitee),
                         avant)

    def test_aucune_surcharge_n_est_posee_par_un_chemin_automatique(self):
        devis = build_devis_auto(lead=self._lead(), user=self.user,
                                 company=self.company, target_kwc='5')
        self.assertIn(getattr(devis, 'overrides', None), (None, {}))


class LeTunnelEstLeMemeCheminQueLEcran(_BaseAuto):
    """« chemin tunnel prouvé identique au chemin écran pour le MÊME lead ».

    Deux leads JUMEAUX (même fiche, même catalogue, même société) : l'un chiffré
    par ``build_devis_auto`` — ce que déclenche le bouton du commercial —,
    l'autre par ``creer_devis_automatique_depuis_lead`` — ce que déclenche le
    webhook du tunnel. Les deux traversent le MÊME pipeline ; seule l'ORIGINE
    déclarée diffère, et elle ne décide d'aucune ligne.
    """

    def test_les_deux_chemins_rendent_le_meme_devis(self):
        ecran = build_devis_auto(
            lead=self._lead(email='ecran-qjr96@example.com'),
            user=self.user, company=self.company)

        lead_tunnel = self._lead(email='tunnel-qjr96@example.com')
        tunnel = creer_devis_automatique_depuis_lead(
            lead_id=lead_tunnel.pk, company_id=self.company.pk)

        self.assertIsNotNone(tunnel)
        self.assertEqual(self._par_designation(tunnel),
                         self._par_designation(ecran))
        for cle in ('scenario', 'puissance_kwc'):
            self.assertEqual((tunnel.etude_params or {}).get(cle),
                             (ecran.etude_params or {}).get(cle), cle)

    def test_l_origine_declaree_au_pipeline_est_le_tunnel(self):
        vues = self._origines_declarees()
        lead = self._lead(email='tunnel-origine@example.com')
        creer_devis_automatique_depuis_lead(lead_id=lead.pk,
                                            company_id=self.company.pk)
        self.assertEqual(vues, [ORIGINE_TUNNEL])


class LeTraceDuClientSurvitALaBascule(_BaseAuto):
    """NON-RÉGRESSION — le layout est lu par LE MÊME lecteur qu'avant.

    L'adaptateur ne délègue plus à ``build_devis_from_layout``, mais la LECTURE
    du calepinage (``extract_roof_config`` → ``_pans_geometry`` →
    ``etude_params['toiture']``) est la même fonction, appelée au même endroit
    du geste. Sans cette garantie, un devis automatique né d'un tracé client
    repartirait sans sa configuration de toiture — et l'écran 3D sur une carte
    vierge.
    """

    def test_la_zone_du_client_et_sa_toiture_sont_conservees(self):
        lead = self._lead(roof_outline=CONTOUR_LATLNG)
        devis = build_devis_auto(lead=lead, user=self.user,
                                 company=self.company)

        layout = devis.roof_layout
        self.assertEqual(layout['_origine_calepinage'], 'contour_client')
        self.assertEqual(len(layout['zones'][0]['vertices']), 4)
        self.assertEqual(layout['zones'][0]['neededPanels'],
                         PANNEAUX_ATTENDUS)
        # QJ21 — la géométrie PROCESSÉE est rangée avec le layout, pour que
        # personne n'ait à rejouer ``extract_roof_config``.
        self.assertEqual(len(layout['_pans_geometry']), 1)

        toiture = (devis.etude_params or {}).get('toiture') or {}
        self.assertEqual(toiture.get('nb_panneaux'), PANNEAUX_ATTENDUS)
        self.assertGreater(toiture.get('surface_m2') or 0, 0)


class LaPreVerificationRefuseAvantDEcrire(_BaseAuto):
    """QJR82 conservé par la bascule : refuser vaut mieux que créer puis
    effacer (un devis effacé rendrait sa référence au compteur, et le numéro
    suivant la reprendrait)."""

    def test_sans_onduleur_reseau_tarife_un_devis_les_deux_est_refuse(self):
        Produit.objects.filter(pk=self.reseau.pk).update(
            prix_vente=Decimal('0'))
        with self.assertRaises(AutoDevisError) as leve:
            build_devis_auto(lead=self._lead(), user=self.user,
                             company=self.company)
        self.assertIn(MSG_SANS_ONDULEUR_RESEAU, str(leve.exception))
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_sans_batterie_tarifee_un_devis_avec_batterie_est_refuse(self):
        Produit.objects.filter(pk=self.batterie.pk).update(
            prix_vente=Decimal('0'))
        with self.assertRaises(AutoDevisError) as leve:
            build_devis_auto(lead=self._lead(batterie_souhaitee='avec'),
                             user=self.user, company=self.company)
        self.assertIn(MSG_SANS_BATTERIE, str(leve.exception))
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_le_marche_non_residentiel_reste_refuse_par_l_adaptateur(self):
        """Le message de CETTE fonction est conservé : il précède le pipeline
        et n'a pas bougé."""
        lead = self._lead(type_installation='agricole')
        with self.assertRaises(AutoDevisError) as leve:
            build_devis_auto(lead=lead, user=self.user, company=self.company)
        self.assertEqual(leve.exception.field, 'type_installation')
