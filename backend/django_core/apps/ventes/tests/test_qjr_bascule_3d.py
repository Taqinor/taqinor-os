# -*- coding: utf-8 -*-
"""QJR95 (M5, bascule 3/5) — la création depuis un CALEPINAGE 3D.

``build_devis_from_layout`` est devenue un ADAPTATEUR : elle LIT le calepinage
(compte de panneaux, wattage, kWc, scénario, toiture) et confie tout le reste à
``pipeline.appliquer``. Le corps qui composait, créait, écrivait les lignes,
écrivait l'étude et finalisait — une recopie des mêmes étapes dans un ordre qui
n'était celui d'aucun autre chemin — est SUPPRIMÉ.

CE QUE CE FICHIER PROUVE, ET DANS QUEL REGISTRE.

* GOLDEN (égalité stricte) — LES LIGNES CRÉÉES. C'est le contrat de la bascule :
  l'adaptateur remplit le MÊME ``IntentionComposition`` qu'avant, donc
  ``composer`` reçoit les mêmes entrées et rend la même composition ; ce que le
  golden vérifie est que cette composition arrive INTACTE en base alors qu'elle
  passe désormais par l'ÉCRIVAIN UNIQUE (``remplacer_lignes``) et non plus par
  une boucle ``creer_ligne`` locale. Les attentes sont DÉRIVÉES et écrites en
  dur (l'ancien corps a disparu, il ne peut plus servir de référence), chacune
  avec sa dérivation depuis la fixture.

* AJOUT NOMMÉ (jamais une égalité golden) — LES QUATRE ÉTUDES. Ce chemin
  n'appelait ``rafraichir_etudes_du_devis`` PAS DU TOUT : un devis né du
  calepinage partait sans bloc horaire, sans tableau de dimensionnement et sans
  profils comparatifs. C'est un GAIN, donc il est testé pour ce qu'il est — les
  quatre rafraîchisseurs TOURNENT — et surtout pas comme une égalité avec un
  avant qui ne les avait pas.

* AJOUT NOMMÉ — LA PRÉ-VÉRIFICATION. Elle n'existait ici que dans la vue
  appelante, en version mono-scénario. Un devis dont le catalogue ne sert pas le
  scénario demandé est désormais REFUSÉ AVANT toute écriture — refuser vaut
  mieux que créer puis effacer (un devis effacé rendrait sa référence au
  compteur, et le numéro suivant la reprendrait).

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_qjr_bascule_3d -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Lead
from apps.stock.models import Produit
from apps.ventes.domain.pipeline import (
    MSG_AUCUN_PANNEAU, MSG_SANS_BATTERIE, MSG_SANS_ONDULEUR_RESEAU,
)
from apps.ventes.domain.taille import AutoDevisError
from apps.ventes.models import Devis
from apps.ventes.services import build_devis_from_layout

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


class _Base3D(TestCase):
    def setUp(self):
        from authentication.models import Company

        self.company, _ = Company.objects.get_or_create(
            slug='qjr95-co', defaults={'nom': 'QJR95 Co'})
        self.user = User.objects.create_user(
            username='qjr95user', password='x', role_legacy='responsable',
            company=self.company)
        # Un golden qui rougit doit DIRE ce qui diverge. Sans ceci, unittest
        # abrège le dict (« Diff is 893 characters long ») et le log de CI ne
        # montre plus la valeur réelle — le rouge de la première ronde a coûté
        # un aller-retour entier pour cette seule raison.
        self.maxDiff = None
        self._seed()

    def _seed(self):
        def mk(nom, sku, prix):
            return Produit.objects.create(
                company=self.company, nom=nom, sku=sku,
                prix_vente=prix, prix_achat=Decimal('1'), quantite_stock=100)

        self.panneau = mk('Panneau Jinko 550W', 'QJR95-PAN', PRIX['panneau'])
        self.reseau = mk('Onduleur réseau Huawei 5kW Monophasé',
                         'QJR95-ONDR', PRIX['onduleur_reseau'])
        self.hybride = mk('Onduleur hybride Deye 5kW Monophasé',
                          'QJR95-ONDH', PRIX['onduleur_hybride'])
        self.batterie = mk('Batterie Dyness 5 kWh', 'QJR95-BAT',
                           PRIX['batterie'])

    def _lead(self):
        return Lead.objects.create(
            company=self.company, nom='Calepinage', prenom='QJR95',
            email='calepinage@example.com')

    def _par_designation(self, devis):
        """Les lignes créées, indexées par désignation.

        L'ORDRE des lignes est celui de la société (PVORD, ``ordre_lignes_societe``)
        et appartient à ``composer`` — que cette bascule ne touche pas. Ce que le
        golden épingle ici est le CONTENU écrit ; la propriété d'ORDRE (des
        positions explicites, contiguës, sans doublon) est vérifiée séparément
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

    def _espionner_les_quatre(self):
        from apps.ventes import electrical_service, profils_comparatifs
        from apps.ventes.domain import etudes

        journal = []
        cibles = [
            (etudes, 'rafraichir_etude_horaire_devis'),
            (etudes, 'rafraichir_dimensionnement_devis'),
            (profils_comparatifs, 'rafraichir_profils_comparatifs_devis'),
            (electrical_service, 'rafraichir_conception_electrique_devis'),
        ]
        anciens = [(mod, nom, getattr(mod, nom)) for mod, nom in cibles]

        def _restaurer():
            for mod, nom, valeur in anciens:
                setattr(mod, nom, valeur)

        def _espion(nom):
            def _appel(devis, force=False, **_):
                journal.append(nom)
                return None
            return _appel

        for mod, nom in cibles:
            setattr(mod, nom, _espion(nom))
        self.addCleanup(_restaurer)
        return journal


class GoldenLayoutReseau(_Base3D):
    """FIXTURE 1 — le calepinage RÉSEAU (mono-option, sans batterie).

    Layout : ``{'scenario': 'reseau', 'result': {'panels': 12, 'kwc': 8.64,
    'annualKwh': 10800, 'savings': 9200}}``.

    DÉRIVATION DU WATTAGE. Le layout ne porte pas de ``panelWatt`` : il est
    déduit du couple (kWc, panneaux) — 8,64 kWc / 12 panneaux = 720 W, le
    modèle CONSTANT de roofPro. Le devis, lui, vend le panneau RÉEL du
    catalogue : « Panneau Jinko 550W ».

    DÉRIVATION DES LIGNES (catalogue minimal : tout ce qui n'y est pas est
    sauté) :

        Panneau Jinko 550W                      ×12 à 1 100,00
        Onduleur réseau Huawei 5kW Monophasé    × 2 à 14 000,00

    et AUCUNE batterie ni onduleur hybride — le scénario est « sans ».

    DÉRIVATION DU COMPTE D'ONDULEURS — ×2, ET C'EST LE POINT INTÉRESSANT DE
    CETTE FIXTURE. La règle de ``composition_residentielle`` est « un onduleur
    suffit dès qu'il couvre le seuil ; sinon on en met assez pour absorber le
    champ » (``quantite_onduleur``), le seuil valant 80 % de la puissance :

        seuil    = 8,64 kWc × 0,8            = 6,912 kW
        le seul onduleur réseau du catalogue =     5 kW  → 5 < 6,912
        quantité = plafond(8,64 / 5)         = plafond(1,728) = 2

    Cette fixture exerce donc la branche MULTI-ONDULEURS, et
    :class:`GoldenLayoutAvecBatterie` (5,5 kWc ⇒ seuil 4,4 kW ≤ 5 kW ⇒ ×1) est
    son témoin sur l'autre branche : les deux côtés de la règle sont couverts.

    (La première rédaction de ce golden écrivait ×1 sans dériver ce seuil —
    une attente posée de mémoire, pas calculée. Le rouge de CI venait de LÀ,
    pas de la bascule : le corps supprimé passait à ``composer`` exactement les
    mêmes ``kwc`` / ``nb_panneaux`` / ``panel_watt``, donc l'ancien chemin
    quotait déjà DEUX onduleurs sur cette fixture.)

    DÉRIVATION DU kWc STOCKÉ (QJR63). Le calepinage propose 8,64 (720 W), les
    LIGNES disent 12 × 550 W = 6 600 W = 6,60 kWc. Le propriétaire du kWc est la
    dérivation depuis les lignes : c'est 6,60 qui est stocké, jamais 8,64 —
    sinon le document porterait deux bases de puissance (incident
    DEV-202608-0007).
    """

    LAYOUT = {
        'scenario': 'reseau',
        'result': {'panels': 12, 'kwc': 8.64,
                   'annualKwh': 10800, 'savings': 9200},
    }

    def _construire(self):
        return build_devis_from_layout(
            layout=dict(self.LAYOUT), user=self.user, company=self.company,
            lead=self._lead())

    def test_golden_les_lignes_creees(self):
        devis = self._construire()
        self.assertEqual(self._par_designation(devis), {
            'Panneau Jinko 550W': (
                Decimal('12'), PRIX['panneau'], '', Decimal('0')),
            # ×2 : 5 kW < seuil (0,8 × 8,64 = 6,912) ⇒ plafond(8,64/5) = 2.
            'Onduleur réseau Huawei 5kW Monophasé': (
                Decimal('2'), PRIX['onduleur_reseau'], '', Decimal('0')),
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

    def test_golden_l_etude_du_calepinage(self):
        devis = self._construire()
        etude = devis.etude_params or {}
        # Ce que le CALEPINAGE apporte, transporté tel quel jusqu'à la création.
        self.assertEqual(etude['production_annuelle'], 10800)
        self.assertEqual(etude['economies_annuelles'], 9200)
        # Ce que les LIGNES arrêtent (QJR63) — 12 × 550 W, jamais les 720 W du
        # modèle 3D.
        self.assertEqual(etude['puissance_kwc'], 6.6)
        # Garde anti-mensonge : « Avec batterie » exigerait l'onduleur hybride
        # ET la batterie ; ces lignes ne les portent pas.
        self.assertEqual(etude['scenario'], 'Sans batterie')

    def test_le_layout_est_range_avec_le_devis(self):
        devis = self._construire()
        self.assertEqual(devis.roof_layout['result']['panels'], 12)


class GoldenLayoutAvecBatterie(_Base3D):
    """FIXTURE 2 — le calepinage AVEC BATTERIE.

    Layout : ``{'scenario': 'avec_batterie', 'result': {'panels': 10,
    'kwc': 5.5, 'annualKwh': 9000, 'savings': 8000}}``.

    DÉRIVATION. 5,5 kWc / 10 panneaux = 550 W — ici le modèle 3D et le panneau
    vendu coïncident, donc le kWc stocké vaut 5,50 des deux façons. Le scénario
    « avec » compose l'onduleur HYBRIDE et une batterie, et JAMAIS l'onduleur
    réseau :

        Panneau Jinko 550W                       ×10 à 1 100,00
        Onduleur hybride Deye 5kW Monophasé      × 1 à 17 000,00
        Batterie Dyness 5 kWh                    × N à 17 000,00

    Le NOMBRE de modules batterie (``N``) est arrêté par
    ``composition_residentielle`` (règle kWc/5 ou capacité cible), que cette
    bascule ne touche pas et qui a ses propres tests : le golden épingle donc
    ici la PRÉSENCE, le PRIX et le fait que la ligne arrive intacte par
    l'écrivain unique — pas une règle de dimensionnement qui ne lui appartient
    pas.
    """

    LAYOUT = {
        'scenario': 'avec_batterie',
        'result': {'panels': 10, 'kwc': 5.5,
                   'annualKwh': 9000, 'savings': 8000},
    }

    def _construire(self):
        return build_devis_from_layout(
            layout=dict(self.LAYOUT), user=self.user, company=self.company,
            lead=self._lead())

    def test_golden_les_lignes_creees(self):
        devis = self._construire()
        lignes = self._par_designation(devis)

        self.assertEqual(lignes['Panneau Jinko 550W'],
                         (Decimal('10'), PRIX['panneau'], '', Decimal('0')))
        self.assertEqual(lignes['Onduleur hybride Deye 5kW Monophasé'],
                         (Decimal('1'), PRIX['onduleur_hybride'], '',
                          Decimal('0')))
        self.assertIn('Batterie Dyness 5 kWh', lignes)
        quantite, prix, variante, remise = lignes['Batterie Dyness 5 kWh']
        self.assertGreater(quantite, Decimal('0'))
        self.assertEqual(prix, PRIX['batterie'])
        self.assertEqual(variante, '')
        self.assertEqual(remise, Decimal('0'))
        # Un devis « avec » ne porte JAMAIS l'onduleur réseau.
        self.assertNotIn('Onduleur réseau Huawei 5kW Monophasé', lignes)
        self._assert_ordre_explicite(devis)

    def test_golden_l_etude(self):
        devis = self._construire()
        etude = devis.etude_params or {}
        self.assertEqual(etude['production_annuelle'], 9000)
        self.assertEqual(etude['economies_annuelles'], 8000)
        self.assertEqual(etude['puissance_kwc'], 5.5)
        # Les lignes servent RÉELLEMENT « avec » (hybride + batterie).
        self.assertEqual(etude['scenario'], 'Avec batterie')


class GoldenLayoutDeuxOptions(_Base3D):
    """FIXTURE 3 — les DEUX options dans un seul devis.

    Layout : 10 panneaux à 5,5 kWc, appelé avec ``deux_options=True``. Le
    catalogue sert les deux côtés (onduleur réseau d'un côté, hybride +
    batterie de l'autre), donc la garde anti-mensonge d'U2 est satisfaite et le
    devis stocke « Les deux (Sans + Avec) » — le seul libellé qui dise au
    moteur PDF de rendre la comparaison.

    Sans ``dimensionnement_avec``, les deux options partagent le MÊME champ PV :
    la composition reste mono-optimum, donc toutes les lignes sont COMMUNES
    (``variante=''``) — c'est le repli documenté de la fusion, et il est ici
    épinglé pour qu'une future divergence se voie.
    """

    LAYOUT = {'result': {'panels': 10, 'kwc': 5.5, 'annualKwh': 9000}}

    def _construire(self):
        return build_devis_from_layout(
            layout=dict(self.LAYOUT), user=self.user, company=self.company,
            lead=self._lead(), deux_options=True)

    def test_golden_les_deux_familles_sont_composees(self):
        devis = self._construire()
        lignes = self._par_designation(devis)
        self.assertEqual(lignes['Panneau Jinko 550W'][0], Decimal('10'))
        self.assertIn('Onduleur réseau Huawei 5kW Monophasé', lignes)
        self.assertIn('Onduleur hybride Deye 5kW Monophasé', lignes)
        self.assertIn('Batterie Dyness 5 kWh', lignes)
        self._assert_ordre_explicite(devis)

    def test_golden_le_scenario_stocke_est_les_deux(self):
        devis = self._construire()
        self.assertEqual((devis.etude_params or {})['scenario'],
                         'Les deux (Sans + Avec)')


class LesQuatreEtudesSontUnAjout(_Base3D):
    """QJR95 — GAIN ASSUMÉ, testé comme un ajout et non comme une égalité.

    ``build_devis_from_layout`` n'appelait AUCUN des quatre rafraîchisseurs. Un
    devis né du calepinage partait donc sans bloc horaire, sans tableau de
    dimensionnement et sans profils comparatifs, et n'en recevait qu'au premier
    enregistrement ultérieur — c'est-à-dire jamais, pour un devis envoyé tel
    quel au client.
    """

    def test_les_quatre_rafraichisseurs_tournent(self):
        journal = self._espionner_les_quatre()
        build_devis_from_layout(
            layout={'scenario': 'reseau',
                    'result': {'panels': 12, 'kwc': 6.6}},
            user=self.user, company=self.company, lead=self._lead())
        self.assertEqual(journal, [
            'rafraichir_etude_horaire_devis',
            'rafraichir_dimensionnement_devis',
            'rafraichir_profils_comparatifs_devis',
            'rafraichir_conception_electrique_devis',
        ])


class LaPreVerificationRefuseAvantDEcrire(_Base3D):
    """QJR95 — GAIN ASSUMÉ : le catalogue est vérifié AVANT toute écriture.

    REFUSER VAUT MIEUX QUE CRÉER PUIS EFFACER : un devis effacé rendrait sa
    référence au compteur, et le numéro suivant la reprendrait. Les messages
    sont ceux, VERBATIM, que le calepinage prononçait déjà dans sa vue — le
    commercial lit donc la même phrase, quel que soit le bouton par lequel le
    devis est né.
    """

    def test_sans_onduleur_reseau_tarife_le_devis_est_refuse(self):
        Produit.objects.filter(pk=self.reseau.pk).update(
            prix_vente=Decimal('0'))
        with self.assertRaises(AutoDevisError) as leve:
            build_devis_from_layout(
                layout={'scenario': 'reseau',
                        'result': {'panels': 12, 'kwc': 6.6}},
                user=self.user, company=self.company, lead=self._lead())
        self.assertIn(MSG_SANS_ONDULEUR_RESEAU, str(leve.exception))
        # AVANT toute écriture : aucun devis, donc aucun numéro consommé.
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_sans_batterie_tarifee_un_devis_avec_batterie_est_refuse(self):
        Produit.objects.filter(pk=self.batterie.pk).update(
            prix_vente=Decimal('0'))
        with self.assertRaises(AutoDevisError) as leve:
            build_devis_from_layout(
                layout={'scenario': 'avec_batterie',
                        'result': {'panels': 10, 'kwc': 5.5}},
                user=self.user, company=self.company, lead=self._lead())
        self.assertIn(MSG_SANS_BATTERIE, str(leve.exception))
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_un_devis_a_deux_options_exige_LES_DEUX_cotes(self):
        """C'est le cas que la pré-vérification MONO-SCÉNARIO ne savait pas
        exprimer : un devis à deux options pouvait naître avec un seul onduleur
        composable, et ne servir qu'une des deux options qu'il promet."""
        Produit.objects.filter(pk=self.hybride.pk).update(
            prix_vente=Decimal('0'))
        with self.assertRaises(AutoDevisError):
            build_devis_from_layout(
                layout={'result': {'panels': 10, 'kwc': 5.5}},
                user=self.user, company=self.company, lead=self._lead(),
                deux_options=True)
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_un_layout_sans_panneau_est_refuse_avec_le_message_du_calepinage(
            self):
        with self.assertRaises(AutoDevisError) as leve:
            build_devis_from_layout(
                layout={'scenario': 'reseau', 'result': {}},
                user=self.user, company=self.company, lead=self._lead())
        self.assertIn(MSG_AUCUN_PANNEAU, str(leve.exception))
        self.assertEqual(Devis.objects.filter(company=self.company).count(), 0)

    def test_ni_lead_ni_client_reste_refuse_par_l_adaptateur(self):
        """Le message de CETTE fonction est conservé : il précède le pipeline
        et n'a pas bougé."""
        with self.assertRaises(ValueError) as leve:
            build_devis_from_layout(
                layout={'result': {'panels': 4, 'kwc': 2.2}},
                user=self.user, company=self.company)
        self.assertIn('requires a lead or client', str(leve.exception))
