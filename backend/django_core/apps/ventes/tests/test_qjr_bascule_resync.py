# -*- coding: utf-8 -*-
"""QJR97 (M5, bascule 5/5a) — la RESYNCHRONISATION passe en mode « réconcilier ».

``sync_devis_from_layout`` (784 l) et le chemin apply-taille
(``offres_tailles.appliquer_au_devis``) deviennent le MODE ``'reconcilier'``
d'``appliquer`` : l'adaptateur LIT le calepinage, le pipeline ordonne, et le
geste chirurgical lui-même vit dans l'étape ``reconcilier``
(``domain/resynchronisation``) — comme ``composer`` vit dans
``domain/composition`` et ``ecrire_lignes`` dans ``domain/lignes``.

CETTE BASCULE EST GOLDEN-IDENTIQUE : ELLE NE CORRIGE RIEN. Chaque assertion de
ce fichier décrit ce que le dépôt faisait DÉJÀ ; toute différence serait un
défaut de la bascule, jamais une amélioration. La correction de la boucle de
plafond de variante est QJR98 (scission R4-C.5), et elle a son propre test
ROUGE-puis-VERT — c'est pourquoi
:class:`GoldenPlafondDeVarianteAvantQJR98` épingle ici le comportement
D'AUJOURD'HUI, y compris son défaut.

QUATRE FIXTURES DE RESYNCHRO :

1. le devis MONO porté à un nouveau compte (le cas d'hier, prix négociés
   préservés) ;
2. la BATTERIE qui entre, et l'onduleur réseau qui devient hybride ;
3. le devis VARIANTÉ « Les deux » sous la règle du PLAFOND (une option rognée,
   l'autre jamais augmentée) ;
4. ``cible_exacte=True`` — le chemin apply-taille : les DEUX options portées au
   compte TAPÉ, à la hausse comme à la baisse.

Lancer :
    docker compose exec django_core python manage.py test \\
        apps.ventes.tests.test_qjr_bascule_resync -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.crm.models import Client
from apps.ventes.domain import pipeline
from apps.ventes.models import Devis
from apps.ventes.services import (
    SCENARIO_LES_DEUX, SyncLayoutError, layout_hash, sync_devis_from_layout,
)

# Fixtures PARTAGÉES avec le module PV18 : mêmes désignations catalogue (c'est
# par elles que le classifieur range les produits), même fabrique de layout. On
# importe des FONCTIONS et des CONSTANTES seulement — jamais une classe
# ``TestCase``, qui serait alors collectée deux fois.
from apps.ventes.tests.test_pv18_sync_layout import (
    BAREMES_FORFAIT, CATALOGUE_KIT, layout, make_company,
)

User = get_user_model()

PANNEAU = 'Panneau Jinko 550W'
RESEAU = 'Onduleur réseau Huawei 5kW'
HYBRIDE = 'Onduleur hybride Deye 5kW'
BATTERIE = 'Batterie Dyness 5 kWh'

#: La forme GELÉE du résultat de resynchro. La bascule la traverse : l'appelant
#: (le viewset PV18, ``appliquer_au_devis``) lit exactement les mêmes clés.
CLES_RESULTAT = {'inchange', 'panneaux', 'kwc', 'scenario', 'batterie',
                 'lignes_modifiees', 'lignes_ajoutees', 'avertissements'}


class _BaseResync(TestCase):
    def setUp(self):
        from apps.stock.models import Produit

        self.company = make_company('qjr97-co')
        self.user = User.objects.create_user(
            username='qjr97user', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client QJR97')
        self.produits = {}
        for nom, sku, prix in CATALOGUE_KIT:
            fixe, par_panneau = BAREMES_FORFAIT.get(sku, (None, None))
            self.produits[nom] = Produit.objects.create(
                company=self.company, nom=nom, sku='QJR97-%s' % sku,
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500,
                prix_fixe_ht=None if fixe is None else Decimal(fixe),
                prix_par_panneau_ht=(None if par_panneau is None
                                     else Decimal(par_panneau)))
        self.compteur = 0

    def _devis(self, *, etude=None, statut=Devis.Statut.BROUILLON,
               hash_layout=None):
        self.compteur += 1
        return Devis.objects.create(
            company=self.company, reference='DEV-QJR97-%s' % self.compteur,
            client=self.client_obj, statut=statut, created_by=self.user,
            etude_params=etude, layout_hash=hash_layout)

    def _ligne(self, devis, nom, quantite, *, prix=None, remise='0',
               variante='', ordre=1):
        return devis.lignes.create(
            produit=self.produits[nom], designation=nom,
            quantite=Decimal(str(quantite)),
            prix_unitaire=Decimal(str(
                prix if prix is not None
                else self.produits[nom].prix_vente)),
            remise=Decimal(remise), variante=variante, ordre=ordre)

    def _qte(self, devis, nom, *, variante=None):
        lignes = devis.lignes.filter(designation=nom)
        if variante is not None:
            lignes = lignes.filter(variante=variante)
        return int(lignes.get().quantite)


class GoldenDevisMono(_BaseResync):
    """FIXTURE 1 — le devis MONO porté de 12 à 16 panneaux.

    C'est la règle historique, mot pour mot : l'écart va sur la PLUS GROSSE
    ligne panneau, elle seule, et TOUT le reste est intact — le prix négocié
    (980 au lieu de 1 100 catalogue), la remise (5 %), la ligne onduleur.

    DÉRIVATION. Le layout porte ``result.panels = 16`` et ``panelWatt = 550`` :
    la cible est 16, le devis en a 12, l'écart de +4 va sur la ligne dominante
    (la seule). Le kWc rendu est celui du layout (8,8), et le kWc STOCKÉ vient
    de son propriétaire (QJR63) sur les lignes RÉELLEMENT posées :
    16 × 550 W = 8,80 kWc — ici les deux coïncident.
    """

    def _devis_mono(self):
        devis = self._devis()
        self._ligne(devis, PANNEAU, 12, prix='980', remise='5', ordre=1)
        self._ligne(devis, RESEAU, 1, prix='13500', ordre=2)
        return devis

    def test_golden_le_compte_est_porte_a_la_cible(self):
        devis = self._devis_mono()
        resultat = sync_devis_from_layout(
            devis, layout(panels=16, kwc=8.8), user=self.user)

        self.assertEqual(set(resultat), CLES_RESULTAT)
        self.assertFalse(resultat['inchange'])
        self.assertEqual(resultat['panneaux'], 16)
        self.assertEqual(resultat['kwc'], 8.8)
        self.assertEqual(resultat['scenario'], 'reseau')
        self.assertFalse(resultat['batterie'])
        self.assertEqual(self._qte(devis, PANNEAU), 16)

    def test_golden_les_prix_negocies_sont_intacts(self):
        """« On touche les quantités, RIEN d'autre » — la garantie que PV18
        existe pour tenir, et que la bascule doit traverser sans l'entamer."""
        devis = self._devis_mono()
        sync_devis_from_layout(devis, layout(panels=16, kwc=8.8),
                               user=self.user)

        panneau = devis.lignes.get(designation=PANNEAU)
        self.assertEqual(panneau.prix_unitaire, Decimal('980'))
        self.assertEqual(panneau.remise, Decimal('5'))
        onduleur = devis.lignes.get(designation=RESEAU)
        self.assertEqual(int(onduleur.quantite), 1)
        self.assertEqual(onduleur.prix_unitaire, Decimal('13500'))

    def test_golden_l_etude_et_le_layout_sont_reposes(self):
        devis = self._devis_mono()
        corps = layout(panels=16, kwc=8.8)
        sync_devis_from_layout(devis, corps, user=self.user)

        devis.refresh_from_db()
        etude = devis.etude_params or {}
        self.assertEqual(etude['production_annuelle'], 14000)
        self.assertEqual(etude['economies_annuelles'], 12000)
        self.assertEqual(etude['puissance_kwc'], 8.8)
        self.assertEqual(etude['scenario'], 'Sans batterie')
        self.assertEqual(devis.layout_hash, layout_hash(corps))
        self.assertEqual(devis.roof_layout['result']['panels'], 16)
        # Règle #4 — le statut est LU, jamais écrit.
        self.assertEqual(devis.statut, Devis.Statut.BROUILLON)

    def test_golden_le_court_circuit_meme_empreinte(self):
        corps = layout(panels=16, kwc=8.8)
        devis = self._devis(hash_layout=layout_hash(corps))
        self._ligne(devis, PANNEAU, 12, prix='980', remise='5', ordre=1)

        resultat = sync_devis_from_layout(devis, corps, user=self.user)
        self.assertTrue(resultat['inchange'])
        self.assertEqual(resultat['lignes_modifiees'], 0)
        # Le court-circuit précède TOUTE écriture : la quantité n'a pas bougé.
        self.assertEqual(self._qte(devis, PANNEAU), 12)
        devis.refresh_from_db()
        self.assertIsNone(devis.roof_layout)

    def test_golden_la_garde_de_statut_refuse_avant_toute_ecriture(self):
        for statut, revision in ((Devis.Statut.ENVOYE, True),
                                 (Devis.Statut.ACCEPTE, False),
                                 (Devis.Statut.REFUSE, False),
                                 (Devis.Statut.EXPIRE, False)):
            with self.subTest(statut=statut):
                devis = self._devis(statut=statut)
                self._ligne(devis, PANNEAU, 12, ordre=1)
                with self.assertRaises(SyncLayoutError) as leve:
                    sync_devis_from_layout(devis, layout(panels=16, kwc=8.8),
                                           user=self.user)
                self.assertEqual(leve.exception.revision_possible, revision)
                self.assertEqual(self._qte(devis, PANNEAU), 12)
                devis.refresh_from_db()
                self.assertEqual(devis.statut, statut)
                self.assertIsNone(devis.roof_layout)


class GoldenBatterieEtPermutationOnduleur(_BaseResync):
    """FIXTURE 2 — la batterie ENTRE, et l'onduleur la suit (PVSCE).

    Sans la permutation, la batterie serait « fantôme » : comptée dans le total
    du devis mais absente du PDF, que le moteur rendrait en « Sans batterie »
    faute d'onduleur hybride.

    DÉRIVATION. Cible 12 = compte du devis ⇒ AUCUNE ligne panneau ne bouge. Le
    layout veut une batterie : une ligne est créée au prix catalogue
    (16 000, remise 0), puis la ligne d'onduleur RÉSEAU est permutée en
    HYBRIDE — à QUANTITÉ INCHANGÉE, seuls le produit, la désignation et le prix
    catalogue changent (17 000).
    """

    def _devis_reseau(self):
        devis = self._devis()
        self._ligne(devis, PANNEAU, 12, ordre=1)
        self._ligne(devis, RESEAU, 1, prix='13500', ordre=2)
        return devis

    def test_golden_la_batterie_entre_et_l_onduleur_devient_hybride(self):
        devis = self._devis_reseau()
        resultat = sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='avec_batterie'),
            user=self.user)

        self.assertTrue(resultat['batterie'])
        self.assertEqual(resultat['scenario'], 'avec_batterie')
        self.assertEqual(self._qte(devis, PANNEAU), 12)
        self.assertEqual(self._qte(devis, BATTERIE), 1)
        # La ligne d'onduleur a été PERMUTÉE, pas dupliquée : plus de réseau.
        self.assertFalse(devis.lignes.filter(designation=RESEAU).exists())
        hybride = devis.lignes.get(designation=HYBRIDE)
        self.assertEqual(int(hybride.quantite), 1)
        self.assertEqual(hybride.prix_unitaire, Decimal('17000'))

    def test_golden_le_scenario_stocke_suit_les_lignes(self):
        devis = self._devis_reseau()
        sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='avec_batterie'),
            user=self.user)
        devis.refresh_from_db()
        self.assertEqual((devis.etude_params or {})['scenario'],
                         'Avec batterie')


class GoldenPlafondDeVarianteAvantQJR98(_BaseResync):
    """FIXTURE 3 — le devis VARIANTÉ « Les deux » sous la RÈGLE DU PLAFOND.

    Le calepinage dit combien de panneaux TIENNENT sur le toit : une option qui
    DÉPASSE ce plafond est ramenée dessus, une option qui reste EN DESSOUS n'est
    JAMAIS augmentée — on ne vend pas au client des panneaux que l'optimum a
    délibérément écartés.

    DÉRIVATION. L'option « sans » porte 10 panneaux (ligne ``variante='sans'``),
    l'option « avec » en porte 14 (ligne ``variante='avec'``), le plafond du
    calepinage est 12.

        · « sans » : 10 < 12 ⇒ INCHANGÉE (10) ;
        · « avec » : 14 > 12 ⇒ rognée sur SA ligne propre : 14 − (14 − 12) = 12.

    ``panneaux`` rendu est le compte de l'option SANS (l'option 1), jamais la
    somme des deux — un nombre qui ne décrirait aucune installation.

    ÉTAT D'AUJOURD'HUI, ÉPINGLÉ TEL QUEL. QJR98 corrigera le cas voisin — celui
    où l'option rognée n'a PAS de ligne propre et où la boucle retombe sur une
    ligne COMMUNE, rétrécissant LES DEUX options. Ici chaque option a sa ligne
    propre, donc ce défaut ne se manifeste pas : cette fixture reste verte
    AVANT comme APRÈS QJR98, et c'est voulu.
    """

    def _devis_variante(self, *, sans=10, avec=14):
        devis = self._devis(etude={'scenario': SCENARIO_LES_DEUX})
        self._ligne(devis, PANNEAU, sans, variante='sans', ordre=1)
        self._ligne(devis, PANNEAU, avec, variante='avec', ordre=2)
        self._ligne(devis, RESEAU, 1, ordre=3)
        self._ligne(devis, HYBRIDE, 1, ordre=4)
        self._ligne(devis, BATTERIE, 1, ordre=5)
        return devis

    def test_golden_l_option_au_dessus_est_rognee_l_autre_intacte(self):
        devis = self._devis_variante()
        resultat = sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='avec_batterie'),
            user=self.user)

        self.assertEqual(self._qte(devis, PANNEAU, variante='sans'), 10)
        self.assertEqual(self._qte(devis, PANNEAU, variante='avec'), 12)
        self.assertEqual(resultat['panneaux'], 10)

    def test_golden_les_deux_options_survivent(self):
        """L-2OPT — un devis né « Les deux » sort de la resynchro toujours à
        deux options : aucun onduleur n'est un intrus, la batterie n'est jamais
        retirée, et le scénario re-stocké reste « Les deux »."""
        devis = self._devis_variante()
        resultat = sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='reseau'),
            user=self.user)

        self.assertTrue(devis.lignes.filter(designation=RESEAU).exists())
        self.assertTrue(devis.lignes.filter(designation=HYBRIDE).exists())
        self.assertTrue(devis.lignes.filter(designation=BATTERIE).exists())
        self.assertEqual(resultat['scenario'], 'les_deux')
        devis.refresh_from_db()
        self.assertEqual((devis.etude_params or {})['scenario'],
                         SCENARIO_LES_DEUX)


class GoldenCibleExacteLeCompteTape(_BaseResync):
    """FIXTURE 4 — ``cible_exacte=True`` : LE CHEMIN APPLY-TAILLE.

    Quand la cible vient d'un NOMBRE TAPÉ par le vendeur (la carte
    « Recommandé »), elle ne décrit pas une contenance de toit mais le devis
    voulu : les DEUX options y sont portées, à la hausse comme à la baisse.
    Sans ce commutateur, taper un compte PLUS GRAND ne faisait STRICTEMENT
    RIEN — configuration consommée, message de succès, devis inchangé.

    DÉRIVATION. « sans » 10 → 12 (HAUSSE, impossible sous la règle du plafond),
    « avec » 14 → 12 (baisse).
    """

    def _devis_variante(self):
        devis = self._devis(etude={'scenario': SCENARIO_LES_DEUX})
        self._ligne(devis, PANNEAU, 10, variante='sans', ordre=1)
        self._ligne(devis, PANNEAU, 14, variante='avec', ordre=2)
        self._ligne(devis, RESEAU, 1, ordre=3)
        self._ligne(devis, HYBRIDE, 1, ordre=4)
        self._ligne(devis, BATTERIE, 1, ordre=5)
        return devis

    def test_golden_les_deux_options_vont_au_compte_tape(self):
        devis = self._devis_variante()
        sync_devis_from_layout(
            devis, layout(panels=12, kwc=6.6, scenario='avec_batterie'),
            user=self.user, cible_exacte=True)

        self.assertEqual(self._qte(devis, PANNEAU, variante='sans'), 12)
        self.assertEqual(self._qte(devis, PANNEAU, variante='avec'), 12)


class LeGesteEstUnMODEDuPipeline(_BaseResync):
    """QJR97 — la resynchro n'est plus un chemin à part : c'est un MODE.

    ``sync_devis_from_layout`` est devenue un ADAPTATEUR ; le geste passe par
    ``pipeline.appliquer``, qui n'exécute que les étapes que le mode DÉCLARE
    (``ETAPES_PAR_MODE``) — jamais une de plus. C'est ce qui interdit à une
    bascule d'ajouter du comportement en se faisant passer pour un
    refactoring : le mode « réconcilier » ne compose pas, ne dimensionne pas,
    et ne rafraîchit pas les quatre études (ses appelants le font, comme
    avant).
    """

    def test_le_mode_reconcilier_est_declare(self):
        self.assertIn(pipeline.MODE_RECONCILIER, pipeline.MODES)
        self.assertEqual(
            pipeline.ETAPES_PAR_MODE[pipeline.MODE_RECONCILIER],
            ('reconcilier',))

    def test_l_adaptateur_passe_par_appliquer(self):
        vues = []
        vrai = pipeline.appliquer

        def _espion(devis, intention):
            vues.append((intention.origine, intention.mode, intention.exact))
            return vrai(devis, intention)

        from apps.ventes.domain import resynchronisation as _resync
        _resync.appliquer = _espion
        self.addCleanup(setattr, _resync, 'appliquer', vrai)

        devis = self._devis()
        self._ligne(devis, PANNEAU, 12, ordre=1)
        self._ligne(devis, RESEAU, 1, ordre=2)
        sync_devis_from_layout(devis, layout(panels=16, kwc=8.8),
                               user=self.user, cible_exacte=True)

        self.assertEqual(
            vues,
            [(pipeline.ORIGINE_RESYNCHRONISATION,
              pipeline.MODE_RECONCILIER, True)])

    def test_le_journal_ne_liste_que_l_etape_du_mode(self):
        devis = self._devis()
        self._ligne(devis, PANNEAU, 12, ordre=1)
        self._ligne(devis, RESEAU, 1, ordre=2)
        resultat = pipeline.appliquer(devis, pipeline.IntentionDevis(
            origine=pipeline.ORIGINE_RESYNCHRONISATION,
            company=self.company, user=self.user,
            layout=layout(panels=16, kwc=8.8),
            mode=pipeline.MODE_RECONCILIER))

        self.assertEqual(resultat['etapes'], ['reconcilier'])
        self.assertEqual(set(resultat['resynchro']), CLES_RESULTAT)
        self.assertEqual(resultat['resynchro']['panneaux'], 16)


class QJR98LaLigneCommuneNeRetrecitPlusLesDeuxOptions(_BaseResync):
    """QJR98 (M5, bascule 5/5b) — ROUGE avant, VERT après. Elle CHANGE le résultat.

    LE DÉFAUT. Dans la boucle de plafond de variante, le vivier de lignes
    rognables était ``propres or vue`` : quand l'option traitée n'a AUCUNE ligne
    de panneaux qui lui soit PROPRE, la boucle retombait sur ``vue``, qui
    contient les lignes COMMUNES (``variante=''``). Or une ligne commune sert
    LES DEUX options : la bouger les bouge toutes les deux — l'issue exacte que
    le commentaire deux lignes plus haut dit d'éviter (« toucher la ligne
    commune rétrécirait AUSSI l'autre option »).

    LA FIXTURE, ET POURQUOI ELLE EST CELLE-LÀ. Le chemin apply-taille
    (``exact=True``, un compte TAPÉ par le vendeur) rend le défaut visible sur
    un NOMBRE, pas seulement sur un mécanisme :

        · ligne COMMUNE (``variante=''``)      : 10 panneaux ;
        · ligne PROPRE à l'option « avec »     :  4 panneaux, quantité
          VERROUILLÉE par le vendeur (QJR60 / D12) ;
        · option « sans » = commune            = 10 ;
        · option « avec » = commune + propre   = 14 ;
        · compte TAPÉ                          = 14.

    L'option « avec » est DÉJÀ exactement au compte demandé : elle n'a rien à
    faire dans ce geste.

    AVANT (rouge). La passe « sans » ne trouve aucune ligne propre, retombe sur
    la COMMUNE et la porte de 10 à 14 — ce qui pousse l'option « avec » à 18.
    La passe « avec » essaie alors de compenser sur sa ligne propre… qui est
    verrouillée : elle ne peut pas. L'option « avec » finit à 18, soit
    QUATRE PANNEAUX de plus que ce que le vendeur a tapé, et le devis accuse la
    ligne verrouillée d'un écart qu'elle n'a pas créé.

    APRÈS (vert). Une ligne COMMUNE n'est mobilisable que si l'AUTRE option a
    besoin EXACTEMENT du même écart — c'est la seule condition sous laquelle la
    bouger sert les deux sans en léser aucune. Sinon l'écart est NOMMÉ et RIEN
    n'est écrit, exactement comme pour une quantité verrouillée. L'option
    « avec » ressort donc STRICTEMENT INCHANGÉE.
    """

    CIBLE_TAPEE = 14

    def _devis_commune_plus_propre(self):
        devis = self._devis(etude={'scenario': SCENARIO_LES_DEUX})
        self.commune = self._ligne(devis, PANNEAU, 10, variante='', ordre=1)
        self.propre_avec = self._ligne(devis, PANNEAU, 4, variante='avec',
                                       ordre=2)
        # QJR60 / D12 — la quantité de l'option « avec » est TAPÉE : la
        # resynchro n'a pas le droit de la réécrire. C'est ce qui empêche la
        # seconde passe de masquer le défaut en compensant.
        self.propre_avec.quantite_manuelle = True
        self.propre_avec.save(update_fields=['quantite_manuelle'])
        self._ligne(devis, RESEAU, 1, ordre=3)
        self._ligne(devis, HYBRIDE, 1, ordre=4)
        self._ligne(devis, BATTERIE, 1, ordre=5)
        return devis

    def _appliquer_la_cible_tapee(self, devis):
        return sync_devis_from_layout(
            devis, layout(panels=self.CIBLE_TAPEE, kwc=7.7,
                          scenario='avec_batterie'),
            user=self.user, cible_exacte=True)

    def test_l_option_non_concernee_est_strictement_inchangee(self):
        """LE test ROUGE avant / VERT après. Avant : 18 (10 + 4 + 4 de
        débordement). Après : 14, la valeur qu'elle avait en entrant."""
        devis = self._devis_commune_plus_propre()
        self._appliquer_la_cible_tapee(devis)

        self.commune.refresh_from_db()
        self.propre_avec.refresh_from_db()
        option_avec = int(self.commune.quantite) + int(
            self.propre_avec.quantite)
        self.assertEqual(option_avec, 14)

    def test_la_ligne_commune_n_est_pas_touchee(self):
        devis = self._devis_commune_plus_propre()
        self._appliquer_la_cible_tapee(devis)

        self.commune.refresh_from_db()
        self.assertEqual(int(self.commune.quantite), 10)

    def test_la_ligne_verrouillee_du_vendeur_est_intacte(self):
        devis = self._devis_commune_plus_propre()
        self._appliquer_la_cible_tapee(devis)

        self.propre_avec.refresh_from_db()
        self.assertEqual(int(self.propre_avec.quantite), 4)

    def test_l_ecart_non_applique_est_NOMME_au_lieu_d_etre_ecrit(self):
        """Rien n'est écrit EN SILENCE : le vendeur apprend l'écart, l'option
        concernée et le geste à faire — même discipline que la garde de
        quantité verrouillée."""
        devis = self._devis_commune_plus_propre()
        resultat = self._appliquer_la_cible_tapee(devis)

        message = ' '.join(resultat['avertissements'])
        self.assertIn('sans', message)
        self.assertIn('commune', message.lower())
        self.assertEqual(resultat['panneaux'], 10)

    def test_une_ligne_commune_reste_mobilisable_quand_elle_sert_LES_DEUX(self):
        """LE TÉMOIN NÉGATIF — la correction ne bloque pas le cas légitime.

        Quand les DEUX options ont EXACTEMENT le même écart à combler, la ligne
        commune les sert à l'identique : la bouger ne lèse personne, elle reste
        donc mobilisable et le plafond s'applique comme avant. C'est la seule
        condition, et c'est ce qui distingue cette correction d'un refus
        généralisé — qui, lui, aurait laissé une option au-dessus de ce que le
        toit peut physiquement porter.

        DÉRIVATION. Ligne commune 18 ; ligne propre « avec » à ZÉRO panneau
        (l'état que la garde « jamais sous zéro » de cette même boucle produit).
        Le devis est donc varianté, mais les deux options valent 18 : le plafond
        de 14 leur retire à toutes deux 4 panneaux, portés par la commune.
        """
        devis = self._devis(etude={'scenario': SCENARIO_LES_DEUX})
        commune = self._ligne(devis, PANNEAU, 18, variante='', ordre=1)
        self._ligne(devis, PANNEAU, 0, variante='avec', ordre=2)
        self._ligne(devis, RESEAU, 1, ordre=3)
        self._ligne(devis, HYBRIDE, 1, ordre=4)
        self._ligne(devis, BATTERIE, 1, ordre=5)

        sync_devis_from_layout(
            devis, layout(panels=14, kwc=7.7, scenario='avec_batterie'),
            user=self.user)

        commune.refresh_from_db()
        self.assertEqual(int(commune.quantite), 14)


class LaDerivationAntiMensongeEstUNIQUE(_BaseResync):
    """QJR97 — la garde anti-mensonge du scénario n'est plus écrite DEUX fois.

    « Les deux (Sans + Avec) » n'est stocké QUE si les lignes servent réellement
    les deux côtés : réseau d'un côté, hybride + batterie de l'autre. Cette
    règle vivait EN ENTIER à deux endroits — à la création
    (``pipeline.ecrire_etude_params``) et à la resynchro — avec deux
    formulations différentes des mêmes conditions. Une seule fonction
    (``domain.scenario.scenario_servable``) les porte désormais, et les deux
    chemins l'appellent.

    Ce test la prend par ses ENTRÉES (fonction pure, aucune base) : c'est la
    table de vérité que les deux chemins partagent maintenant.
    """

    def test_la_table_de_verite(self):
        from apps.ventes.domain.scenario import (
            SCENARIO_AVEC_BATTERIE, SCENARIO_SANS_BATTERIE, scenario_servable,
        )

        # « Les deux » demandé ET servi des deux côtés.
        self.assertEqual(
            scenario_servable(True, a_reseau=True, a_hybride=True,
                              a_batterie=True),
            SCENARIO_LES_DEUX)
        # « Les deux » demandé mais une moitié manque ⇒ DÉGRADE, honnêtement.
        self.assertEqual(
            scenario_servable(True, a_reseau=False, a_hybride=True,
                              a_batterie=True),
            SCENARIO_AVEC_BATTERIE)
        self.assertEqual(
            scenario_servable(True, a_reseau=True, a_hybride=True,
                              a_batterie=False),
            SCENARIO_SANS_BATTERIE)
        # Mono : « Avec » exige hybride ET batterie, sinon « Sans ».
        self.assertEqual(
            scenario_servable(False, a_reseau=False, a_hybride=True,
                              a_batterie=True),
            SCENARIO_AVEC_BATTERIE)
        self.assertEqual(
            scenario_servable(False, a_reseau=True, a_hybride=False,
                              a_batterie=True),
            SCENARIO_SANS_BATTERIE)
