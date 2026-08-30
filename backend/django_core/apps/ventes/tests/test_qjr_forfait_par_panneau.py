# -*- coding: utf-8 -*-
"""QJR83 — les forfaits TARIFÉS AU PANNEAU suivent le compte du devis.

CE QUE CES TESTS VERROUILLENT, ET POURQUOI.

Constat QB83 (audit L3 du 29/08/2026), vérifié en code : AUCUN chemin ne
re-tarifait les lignes de forfait par panneau (pose/installation, tableau
AC/DC, accessoires…) après un changement de compte. Un devis resynchronisé de
9 à 20 panneaux gardait une pose facturée POUR 9 — alors que la docstring de
``prix_forfait_ht`` affirme précisément le contraire (« changer le nombre de
panneaux requote mécaniquement les forfaits »). Elle ne disait vrai que pour
une COMPOSITION NEUVE : dès que le devis existait, plus rien ne repassait sur
ses lignes.

La re-tarification vit désormais chez L'ÉCRIVAIN UNIQUE
(``domain/lignes.remplacer_lignes``, QJR73) : tout chemin qui finit par écrire
les lignes d'un devis l'obtient, et aucun n'a sa propre copie de la règle. Le
barème reste au STOCK (``prix_fixe_ht`` / ``prix_par_panneau_ht``) : aucun
montant n'est écrit dans le code.

D12 (décision fondateur du 29/08/2026) — une ligne ``prix_manuel`` n'est
JAMAIS réécrite. Ce qui change, c'est qu'on le DIT, en français, au lieu de
laisser croire que le barème a joué.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr_forfait_par_panneau -v 2
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.stock.models import Produit
from apps.ventes.domain import lignes as _lignes
from apps.ventes.domain.catalogue import (porte_bareme_par_panneau,
                                          prix_forfait_ht)

User = get_user_model()

#: Le barème du fondateur pour la POSE, tel que ``seed_catalogue`` le pose :
#: 2 000 HT de part fixe + 250 HT par panneau. 9 panneaux → 4 250 ;
#: 20 panneaux → 7 000. Aucun de ces nombres n'est écrit en dur ci-dessous :
#: ils sont tous DÉRIVÉS de ``prix_forfait_ht``, la seule formule.
POSE_FIXE, POSE_PAR_PANNEAU = '2000', '250'


# ── La moitié PURE : aucune base, tout est exécutable en l'état ──────────────

class _FauxProduit:
    def __init__(self, nom, prix_vente, fixe=None, par_panneau=None):
        self.nom = nom
        self.prix_vente = Decimal(prix_vente)
        self.prix_fixe_ht = None if fixe is None else Decimal(fixe)
        self.prix_par_panneau_ht = (None if par_panneau is None
                                    else Decimal(par_panneau))


class _FausseLigne:
    def __init__(self, designation, quantite, prix, produit=None,
                 variante='', prix_manuel=False):
        self.designation = designation
        self.quantite = Decimal(str(quantite))
        self.prix_unitaire = Decimal(str(prix))
        self.produit = produit
        self.variante = variante
        self.prix_manuel = prix_manuel
        self.type_ligne = 'produit'
        self.enregistrements = []

    def save(self, update_fields=None):
        self.enregistrements.append(tuple(update_fields or ()))


class _FauxDevis:
    """Le strict minimum que ``_lignes_produit`` demande : ``.lignes.all()``."""

    def __init__(self, lignes):
        self._lignes = list(lignes)

    class _Manager:
        def __init__(self, lignes):
            self._lignes = lignes

        def all(self):
            return list(self._lignes)

    @property
    def lignes(self):
        return self._Manager(self._lignes)


def _panneau(quantite, variante=''):
    produit = _FauxProduit('Panneau Jinko 550W', '1100')
    return _FausseLigne('Panneau Jinko 550W', quantite, '1100',
                        produit=produit, variante=variante)


def _pose(prix, variante='', prix_manuel=False):
    produit = _FauxProduit('Installation', '4800',
                           fixe=POSE_FIXE, par_panneau=POSE_PAR_PANNEAU)
    return _FausseLigne('Installation', 1, prix, produit=produit,
                        variante=variante, prix_manuel=prix_manuel)


class LeBaremeSeReconnaitSansCalculerDePrix(SimpleTestCase):
    """``porte_bareme_par_panneau`` — le prédicat sorti de ``prix_forfait_ht``."""

    def test_un_forfait_porte_un_bareme(self):
        self.assertTrue(porte_bareme_par_panneau(
            _FauxProduit('Installation', '4800', fixe=POSE_FIXE,
                         par_panneau=POSE_PAR_PANNEAU)))

    def test_une_seule_part_suffit(self):
        self.assertTrue(porte_bareme_par_panneau(
            _FauxProduit('Transport', '1000', par_panneau='40')))

    def test_le_reste_du_catalogue_nen_porte_pas(self):
        self.assertFalse(porte_bareme_par_panneau(
            _FauxProduit('Panneau Jinko 550W', '1100')))
        self.assertFalse(porte_bareme_par_panneau(None))


class LeCompteDePanneauxSeLitParOption(SimpleTestCase):
    """``_comptes_panneaux`` — la base de toute re-tarification."""

    def test_devis_non_variante_un_seul_compte(self):
        comptes = _lignes._comptes_panneaux([_panneau(9), _pose('4250')])
        self.assertEqual(comptes, {'': 9, 'sans': 9, 'avec': 9})

    def test_devis_variante_chaque_option_compte_le_sien(self):
        comptes = _lignes._comptes_panneaux(
            [_panneau(8, 'sans'), _panneau(12, 'avec')])
        self.assertEqual(comptes['sans'], 8)
        self.assertEqual(comptes['avec'], 12)
        # Aucun compte ne décrit LES DEUX : la clé commune vaut None.
        self.assertIsNone(comptes[''])

    def test_les_lignes_communes_comptent_dans_les_deux_vues(self):
        comptes = _lignes._comptes_panneaux(
            [_panneau(6, ''), _panneau(2, 'sans'), _panneau(6, 'avec')])
        self.assertEqual(comptes['sans'], 8)
        self.assertEqual(comptes['avec'], 12)

    def test_deux_options_au_meme_champ_pv_redonnent_un_compte_commun(self):
        comptes = _lignes._comptes_panneaux(
            [_panneau(12, 'sans'), _panneau(12, 'avec')])
        self.assertEqual(comptes[''], 12)


class LaRetarificationSuitLeCompte(SimpleTestCase):
    """Le cœur de QJR83, sans base : 9 → 20 panneaux, et les abstentions."""

    def test_neuf_vers_vingt_panneaux_la_pose_suit(self):
        pose = _pose(prix_forfait_ht(
            _FauxProduit('Installation', '4800', fixe=POSE_FIXE,
                         par_panneau=POSE_PAR_PANNEAU), 9))
        devis = _FauxDevis([_panneau(20), pose])

        messages = _lignes.retarifer_forfaits_par_panneau(devis)

        self.assertEqual(messages, [])
        self.assertEqual(pose.prix_unitaire,
                         prix_forfait_ht(pose.produit, 20))
        self.assertEqual(pose.enregistrements, [('prix_unitaire',)])

    def test_un_prix_deja_au_bareme_nest_pas_reecrit(self):
        """Une ligne inchangée ne doit pas voir sa date de modification
        bouger : aucune écriture."""
        produit = _FauxProduit('Installation', '4800', fixe=POSE_FIXE,
                               par_panneau=POSE_PAR_PANNEAU)
        pose = _pose(prix_forfait_ht(produit, 20))
        devis = _FauxDevis([_panneau(20), pose])

        self.assertEqual(_lignes.retarifer_forfaits_par_panneau(devis), [])
        self.assertEqual(pose.enregistrements, [])

    def test_prix_manuel_ne_bouge_pas_et_un_avertissement_fr_le_dit(self):
        """D12 — le prix négocié tapé par le commercial est SOUVERAIN."""
        pose = _pose('3000', prix_manuel=True)
        devis = _FauxDevis([_panneau(20), pose])

        messages = _lignes.retarifer_forfaits_par_panneau(devis)

        self.assertEqual(pose.prix_unitaire, Decimal('3000'))
        self.assertEqual(pose.enregistrements, [])
        self.assertEqual(len(messages), 1)
        self.assertIn('prix saisi à la main', messages[0])
        self.assertIn('20 panneaux', messages[0])
        self.assertIn(str(prix_forfait_ht(pose.produit, 20)), messages[0])

    def test_un_forfait_commun_a_deux_options_divergentes_sabstient(self):
        """Zéro chiffre inventé : aucun compte ne décrit les deux options."""
        pose = _pose('4250')
        devis = _FauxDevis([_panneau(8, 'sans'), _panneau(12, 'avec'), pose])

        messages = _lignes.retarifer_forfaits_par_panneau(devis)

        self.assertEqual(pose.prix_unitaire, Decimal('4250'))
        self.assertEqual(pose.enregistrements, [])
        self.assertEqual(len(messages), 1)
        self.assertIn('COMMUN aux deux options', messages[0])

    def test_un_forfait_variante_suit_le_compte_de_SON_option(self):
        pose_sans = _pose('0', variante='sans')
        pose_avec = _pose('0', variante='avec')
        devis = _FauxDevis([_panneau(8, 'sans'), _panneau(12, 'avec'),
                            pose_sans, pose_avec])

        self.assertEqual(_lignes.retarifer_forfaits_par_panneau(devis), [])
        self.assertEqual(pose_sans.prix_unitaire,
                         prix_forfait_ht(pose_sans.produit, 8))
        self.assertEqual(pose_avec.prix_unitaire,
                         prix_forfait_ht(pose_avec.produit, 12))

    def test_le_reste_du_catalogue_nest_jamais_retarife(self):
        """Un prix NÉGOCIÉ sur un produit sans barème reste intouché — la
        re-tarification ne concerne QUE les forfaits."""
        panneau = _panneau(20)
        panneau.prix_unitaire = Decimal('950')  # prix négocié
        devis = _FauxDevis([panneau])

        self.assertEqual(_lignes.retarifer_forfaits_par_panneau(devis), [])
        self.assertEqual(panneau.prix_unitaire, Decimal('950'))
        self.assertEqual(panneau.enregistrements, [])

    def test_le_canal_avertissements_est_enrichi_sur_place(self):
        recu = []
        devis = _FauxDevis([_panneau(20), _pose('3000', prix_manuel=True)])
        rendu = _lignes.retarifer_forfaits_par_panneau(devis,
                                                       avertissements=recu)
        self.assertIs(rendu, recu)
        self.assertEqual(len(recu), 1)


# ── La moitié BOUT-EN-BOUT : l'écrivain unique, sur de vraies lignes ────────

class LEcrivainUniqueRetarifeCeQuIlEcrit(TestCase):
    """``remplacer_lignes`` — le SEUL chemin d'écriture des lignes de l'écran."""

    def setUp(self):
        from authentication.models import Company

        self.company, _ = Company.objects.get_or_create(
            slug='qjr83-forfait', defaults={'nom': 'qjr83-forfait'})
        self.user = User.objects.create_user(
            username='qjr83', password='x', company=self.company,
            role_legacy='admin')
        self.panneau = Produit.objects.create(
            company=self.company, nom='Panneau Jinko 550W',
            sku='QJR83-PAN', prix_vente=Decimal('1100'),
            prix_achat=Decimal('1'), quantite_stock=500)
        self.pose = Produit.objects.create(
            company=self.company, nom='Installation', sku='QJR83-INST',
            prix_vente=Decimal('4800'), prix_achat=Decimal('1'),
            quantite_stock=500,
            prix_fixe_ht=Decimal(POSE_FIXE),
            prix_par_panneau_ht=Decimal(POSE_PAR_PANNEAU))

    def _devis(self):
        from apps.crm.models import Client
        from apps.ventes.models import Devis
        # Devis.client est NOT NULL en base — la fixture doit porter un client
        # réel (première exécution CI : NotNullViolation sans lui).
        client, _ = Client.objects.get_or_create(
            company=self.company, email='qjr83@example.com',
            defaults={'nom': 'QJR83', 'prenom': 'Forfait',
                      'telephone': '+212600000083'})
        return Devis.objects.create(
            company=self.company, client=client, reference='DEV-QJR83-1',
            statut=Devis.Statut.BROUILLON, created_by=self.user)

    def _corps(self, nb_panneaux, *, prix_pose, prix_manuel=False):
        return [
            {'produit': self.panneau.id, 'designation': 'Panneau Jinko 550W',
             'quantite': nb_panneaux, 'prix_unitaire': '1100', 'ordre': 0},
            {'produit': self.pose.id, 'designation': 'Installation',
             'quantite': 1, 'prix_unitaire': str(prix_pose), 'ordre': 1,
             'prix_manuel': prix_manuel},
        ]

    def test_de_neuf_a_vingt_panneaux_la_pose_suit(self):
        devis = self._devis()
        pose_a_9 = prix_forfait_ht(self.pose, 9)
        _lignes.remplacer_lignes(
            devis, self._corps(9, prix_pose=pose_a_9), self.company)
        self.assertEqual(
            devis.lignes.get(designation='Installation').prix_unitaire,
            pose_a_9)

        # Le devis grossit — c'est le scénario de l'incident QB83.
        avertissements = _lignes.remplacer_lignes(
            devis, self._corps(20, prix_pose=pose_a_9), self.company)

        self.assertEqual(avertissements, [])
        self.assertEqual(
            devis.lignes.get(designation='Installation').prix_unitaire,
            prix_forfait_ht(self.pose, 20))

    def test_prix_manuel_la_pose_ne_bouge_pas_et_on_le_dit(self):
        devis = self._devis()
        avertissements = _lignes.remplacer_lignes(
            devis, self._corps(20, prix_pose='3000', prix_manuel=True),
            self.company)

        ligne = devis.lignes.get(designation='Installation')
        self.assertEqual(ligne.prix_unitaire, Decimal('3000.00'))
        self.assertTrue(ligne.prix_manuel)
        self.assertEqual(len(avertissements), 1)
        self.assertIn('prix saisi à la main', avertissements[0])
        self.assertIn('20 panneaux', avertissements[0])

    def test_les_lignes_sans_bareme_gardent_leur_prix_negocie(self):
        devis = self._devis()
        corps = self._corps(20, prix_pose=prix_forfait_ht(self.pose, 20))
        corps[0]['prix_unitaire'] = '950'   # panneau NÉGOCIÉ
        _lignes.remplacer_lignes(devis, corps, self.company)
        self.assertEqual(
            devis.lignes.get(designation='Panneau Jinko 550W').prix_unitaire,
            Decimal('950.00'))
