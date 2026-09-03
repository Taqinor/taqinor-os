"""QJR116 — UN SEUL cloneur de lignes pour les trois chemins de copie.

CE QUE CE MODULE ÉPINGLE, ET POURQUOI.

Constats CS1 / CS2 / CS3 de l'audit du 30/08/2026 : ``dupliquer_devis``,
``creer_variante_gamme`` et ``renouveler_devis`` nommaient CHACUN sa liste de
champs à cloner, à la main. Les listes avaient déjà divergé — le renouvellement
clonait ``optionnelle`` sans ``variante``, les deux autres clonaient les deux,
et AUCUN des trois ne clonait ``lot``.

Le coût n'est pas cosmétique. Sans ``variante``, le découpage en deux options
retombe sur le filtre par MOTS-CLÉS (``quote_engine/builder._repartir_options``)
et les panneaux, structures et pose des DEUX options tombent dans les DEUX
paniers : la copie d'un devis à deux optimums divergents publie un prix « sans
batterie » qui contient le champ PV de l'option « avec ». Sans ``optionnelle``,
un add-on hors totaux (``LigneDevis.compte_dans_totaux``) redevient une ligne
facturée et gonfle le TTC.

Les tests ci-dessous prennent donc UN devis à deux optimums VOLONTAIREMENT
divergents (8 panneaux sans batterie, 14 avec) et comparent les totaux des DEUX
options AVANT et APRÈS chacune des trois copies. C'est la seule mesure qui
prouve que le découpage a survécu au clonage.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_qjr116_clonage_lignes -v 2
"""
import ast
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from apps.ventes.domain.lignes import CHAMPS_LIGNE, CHAMPS_CLONES, creer_ligne
from apps.ventes.utils.options import (
    AVEC_BATTERIE, SANS_BATTERIE, option_totaux,
)

User = get_user_model()

RACINE_VENTES = Path(__file__).resolve().parent.parent

#: Les trois chemins de copie et le module qui les porte depuis M3.
CHEMINS_DE_COPIE = (
    ('domain/creation.py', 'dupliquer_devis'),
    ('domain/gammes.py', 'creer_variante_gamme'),
    ('domain/cycle_vie.py', 'renouveler_devis'),
)

#: QJR407 (02/09/2026) — LE CLONEUR DE DEVIS DU DOMAINE, seule délégation
#: admise. Un chemin de copie satisfait l'invariant « un seul cloneur de
#: lignes » de DEUX façons : il appelle ``cloner_lignes`` lui-même, ou il
#: délègue TOUT son corps à ``cloner_devis`` — qui, lui, est tenu par la même
#: garde (``test_le_cloneur_delegue_clone_bien_les_lignes`` ci-dessous, sans
#: quoi la délégation serait un trou). C'est exactement ce que QJR407 a fait de
#: ``dupliquer_devis`` : la liste de champs n'y est plus écrite du tout.
#:
#: UN SEUL niveau de délégation : la chaîne reste vérifiable d'un coup d'œil,
#: et un chemin qui déléguerait à un quatrième intermédiaire échoue ici.
CLONEUR_DELEGUE = ('domain/creation.py', 'cloner_devis')


def _appels_de(chemin, nom_fonction):
    """Les noms de fonctions appelées à l'intérieur de ``nom_fonction``.

    Lecture AST, jamais un grep : un appel cité dans un commentaire ou une
    docstring ne doit ni compter ni manquer.
    """
    arbre = ast.parse((RACINE_VENTES / chemin).read_text(encoding='utf-8'),
                      filename=str(chemin))
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if noeud.name != nom_fonction:
            continue
        appels = set()
        for enfant in ast.walk(noeud):
            if isinstance(enfant, ast.Call):
                cible = enfant.func
                if isinstance(cible, ast.Name):
                    appels.add(cible.id)
                elif isinstance(cible, ast.Attribute):
                    appels.add(cible.attr)
        return appels
    raise AssertionError(
        '%s : fonction « %s » introuvable — le chemin de copie a été renommé '
        'ou déplacé ; mettez CHEMINS_DE_COPIE à jour dans le MÊME commit.'
        % (chemin, nom_fonction))


class UnSeulCloneurDeLignes(SimpleTestCase):
    """La garde STATIQUE : aucune des trois copies ne re-tape sa liste."""

    def test_le_cloneur_delegue_clone_bien_les_lignes(self):
        """QJR407 — LE PIED DE LA CHAÎNE. Sans cette assertion, déléguer à
        ``cloner_devis`` suffirait à verdir le test suivant même si le cloneur
        avait cessé d'appeler ``cloner_lignes``."""
        chemin, fonction = CLONEUR_DELEGUE
        self.assertIn(
            'cloner_lignes', _appels_de(chemin, fonction),
            '%s.%s — le cloneur du domaine ne clone plus les lignes par '
            'domain/lignes.cloner_lignes : la délégation admise par '
            'CLONEUR_DELEGUE est devenue un trou.' % (chemin, fonction))

    def test_les_trois_chemins_passent_par_cloner_lignes(self):
        for chemin, fonction in CHEMINS_DE_COPIE:
            with self.subTest(chemin=chemin, fonction=fonction):
                appels = _appels_de(chemin, fonction)
                self.assertTrue(
                    'cloner_lignes' in appels
                    or CLONEUR_DELEGUE[1] in appels,
                    '%s.%s ne clone plus par domain/lignes.cloner_lignes, ni '
                    'directement ni en déléguant à %s : un quatrième jeu de '
                    'champs maintenu à la main est réapparu.'
                    % (chemin, fonction, CLONEUR_DELEGUE[1]))

    def test_aucun_chemin_de_copie_ne_cree_de_ligne_lui_meme(self):
        """``creer_ligne`` reste l'écrivain unique, mais une COPIE ne
        l'appelle plus directement : elle passerait à côté d'un champ.

        QJR407 — le cloneur DÉLÉGUÉ subit la même règle : sans lui dans la
        liste, un chemin pourrait déplacer sa liste de champs d'un cran.
        """
        for chemin, fonction in CHEMINS_DE_COPIE + (CLONEUR_DELEGUE,):
            with self.subTest(chemin=chemin, fonction=fonction):
                self.assertNotIn(
                    'creer_ligne', _appels_de(chemin, fonction),
                    '%s.%s énumère de nouveau les champs d\'une ligne : '
                    'c\'est exactement ce que CS1/CS2/CS3 ont coûté.'
                    % (chemin, fonction))

    def test_le_jeu_clone_est_derive_du_jeu_complet(self):
        """``CHAMPS_CLONES`` n'est jamais retapé : un champ ajouté au modèle
        entre dans les trois copies par le seul ajout à ``CHAMPS_LIGNE``."""
        self.assertEqual(
            set(CHAMPS_CLONES),
            set(CHAMPS_LIGNE) - {'produit_id', 'lot_id'})


class _DevisADeuxOptimumsDivergents(TestCase):
    """Le devis de référence : deux options qui n'ont PAS le même champ PV."""

    slug = 'qjr116'

    #: Ce que chaque option doit valoir en HT, avant comme après une copie.
    #: 8 × 1100 + 9000 + 500 = 18 300 · 14 × 1100 + 11 000 + 9 000 + 500
    #: = 35 900. L'add-on optionnel (7 000) n'entre dans AUCUN des deux.
    #:
    #: QJR400 (02/09/2026) — LES DEUX MONTANTS SONT INCHANGÉS AU CENTIME ;
    #: seule la COMPOSITION du panier « avec » a été rendue servable. Le noyau
    #: exige désormais que la variante remplace la DÉCLARATION, jamais la
    #: SERVABILITÉ (:func:`familles_servables`) : un panier « avec » n'existe
    #: qu'avec un onduleur HYBRIDE (ou autonome) **et** une batterie réelle.
    #: L'ancien montage — batterie seule à 20 000, aucun onduleur hybride —
    #: décrivait un devis que le document n'aurait jamais rendu ; le noyau le
    #: voyait donc mono-option et servait la somme des deux paniers (53 700).
    #: Les 20 000 du panier « avec » sont simplement redécoupés en
    #: 11 000 (onduleur hybride) + 9 000 (batterie).
    HT_SANS = Decimal('18300.00')
    HT_AVEC = Decimal('35900.00')

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client
        from apps.stock.models import Produit
        from apps.ventes.models import Devis

        self.company, _ = Company.objects.get_or_create(
            slug=self.slug, defaults={'nom': self.slug})
        self.user = User.objects.create_user(
            username='qjr116-%s' % self.slug, password='x',
            company=self.company, role_legacy='admin')
        # Devis.client est NOT NULL en base.
        self.client_crm, _ = Client.objects.get_or_create(
            company=self.company, email='qjr116-%s@example.com' % self.slug,
            defaults={'nom': 'QJR116', 'prenom': self.slug,
                      'telephone': '+212600000116'})

        def _produit(nom, sku, prix):
            return Produit.objects.create(
                company=self.company, nom=nom,
                sku='QJR116-%s-%s' % (sku, self.company.pk),
                prix_vente=Decimal(prix), prix_achat=Decimal('1'),
                quantite_stock=500)

        # Les prix de ligne VALENT le prix catalogue : le renouvellement
        # re-tarife réellement (sa raison d'être) sans déplacer les totaux,
        # donc l'écart mesuré ne peut venir que du découpage en options.
        self.panneau = _produit('Panneau Jinko 550W', 'PAN', '1100')
        self.batterie = _produit('Batterie LiFePO4 16 kWh', 'BAT', '9000')
        self.onduleur = _produit('Onduleur réseau 8 kW', 'OND', '9000')
        # QJR400 — l'option « avec » a besoin de SON onduleur hybride pour être
        # servable (sans lui, le noyau la refuse et sert la somme des deux).
        self.hybride = _produit('Onduleur hybride 8 kW', 'ONDH', '11000')
        self.cable = _produit('Câble solaire 6 mm²', 'CAB', '500')
        self.addon = _produit('Supervision à distance', 'SUP', '7000')

        self.devis = Devis.objects.create(
            company=self.company, client=self.client_crm,
            reference='DEV-QJR116-1', statut=Devis.Statut.BROUILLON,
            created_by=self.user)

        def _ligne(produit, quantite, *, variante='', optionnelle=False,
                   ordre=0):
            return creer_ligne(
                self.devis, produit=produit, designation=produit.nom,
                quantite=Decimal(str(quantite)),
                prix_unitaire=produit.prix_vente, remise=Decimal('0'),
                ordre=ordre, variante=variante, optionnelle=optionnelle)

        # LES DEUX OPTIMUMS DIVERGENT : c'est tout l'intérêt du cas.
        self.pan_sans = _ligne(self.panneau, 8, variante='sans', ordre=1)
        self.pan_avec = _ligne(self.panneau, 14, variante='avec', ordre=2)
        self.l_onduleur = _ligne(self.onduleur, 1, variante='sans', ordre=3)
        self.l_hybride = _ligne(self.hybride, 1, variante='avec', ordre=4)
        self.l_batterie = _ligne(self.batterie, 1, variante='avec', ordre=5)
        # Ligne COMMUNE (aucune variante) : elle appartient aux deux paniers.
        self.l_cable = _ligne(self.cable, 1, ordre=6)
        # Add-on FACULTATIF : hors totaux tant qu'il n'est pas activé.
        self.l_addon = _ligne(self.addon, 1, optionnelle=True, ordre=7)

    @staticmethod
    def _totaux_des_deux_options(devis):
        return (option_totaux(devis, SANS_BATTERIE),
                option_totaux(devis, AVEC_BATTERIE))

    def _verifier_le_decoupage(self, devis, quoi):
        sans, avec = self._totaux_des_deux_options(devis)
        self.assertEqual(
            sans['ht'], self.HT_SANS,
            '%s : le panier « sans batterie » ne vaut plus son propre champ '
            'PV (il a probablement absorbé les 14 panneaux de l\'option '
            'avec).' % quoi)
        self.assertEqual(
            avec['ht'], self.HT_AVEC,
            '%s : le panier « avec batterie » a changé de périmètre.' % quoi)
        return sans, avec


class LeDevisSourceEstBienDivergent(_DevisADeuxOptimumsDivergents):
    """Le témoin : sans lui, les trois tests suivants pourraient être verts
    parce que les deux options ont toujours été identiques."""

    slug = 'qjr116-source'

    def test_les_deux_options_ne_valent_pas_la_meme_chose(self):
        sans, avec = self._verifier_le_decoupage(self.devis, 'source')
        self.assertNotEqual(sans['ht'], avec['ht'])

    def test_l_add_on_optionnel_pese_7000_une_fois_active(self):
        """La mesure de ce que ``optionnelle`` retient : activée, la ligne
        ajoute 7 000 MAD aux DEUX paniers. C'est exactement le montant qu'une
        copie qui perd le champ facturerait au client sans qu'il l'ait
        demandé."""
        self._verifier_le_decoupage(self.devis, 'source')
        self.l_addon.optionnelle = False
        self.l_addon.save(update_fields=['optionnelle'])
        sans, avec = self._totaux_des_deux_options(self.devis)
        self.assertEqual(sans['ht'] - self.HT_SANS, Decimal('7000.00'))
        self.assertEqual(avec['ht'] - self.HT_AVEC, Decimal('7000.00'))


class LesTroisCopiesGardentLesDeuxOptions(_DevisADeuxOptimumsDivergents):
    """CS1 / CS2 / CS3 — le cœur de QJR116."""

    slug = 'qjr116-copies'

    def test_dupliquer_devis_preserve_les_totaux_des_deux_options(self):
        from apps.ventes.domain.creation import dupliquer_devis

        avant = self._totaux_des_deux_options(self.devis)
        copie = dupliquer_devis(self.devis, user=self.user)
        apres = self._verifier_le_decoupage(copie, 'duplicata')
        self.assertEqual(apres, avant)

    def test_creer_variante_gamme_preserve_les_totaux_des_deux_options(self):
        from apps.ventes.domain.gammes import creer_variante_gamme

        avant = self._totaux_des_deux_options(self.devis)
        soeur = creer_variante_gamme(self.devis, 'Premium', user=self.user)
        apres = self._verifier_le_decoupage(soeur, 'gamme sœur')
        self.assertEqual(apres, avant)

    def test_renouveler_devis_preserve_les_totaux_des_deux_options(self):
        from apps.ventes.models import Devis
        from apps.ventes.domain.cycle_vie import renouveler_devis

        avant = self._totaux_des_deux_options(self.devis)
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])

        nouveau = renouveler_devis(self.devis, user=self.user)
        apres = self._verifier_le_decoupage(nouveau, 'renouvellement')
        self.assertEqual(apres, avant)

    def test_les_trois_copies_reportent_la_variante_ligne_a_ligne(self):
        """La preuve directe, sous les totaux : chaque ligne garde SA
        variante et son caractère facultatif."""
        from apps.ventes.models import Devis
        from apps.ventes.domain.creation import dupliquer_devis
        from apps.ventes.domain.gammes import creer_variante_gamme
        from apps.ventes.domain.cycle_vie import renouveler_devis

        def _empreinte(devis):
            return sorted(
                (li.designation, li.quantite, li.variante, li.optionnelle)
                for li in devis.lignes.all())

        attendue = _empreinte(self.devis)
        self.assertEqual(
            _empreinte(dupliquer_devis(self.devis, user=self.user)), attendue)
        self.assertEqual(
            _empreinte(creer_variante_gamme(self.devis, 'Premium',
                                            user=self.user)), attendue)
        self.devis.statut = Devis.Statut.ACCEPTE
        self.devis.save(update_fields=['statut'])
        self.assertEqual(
            _empreinte(renouveler_devis(self.devis, user=self.user)), attendue)


class LeLotSuitSonDevis(_DevisADeuxOptimumsDivergents):
    """NTCPQ18 — ``LigneDevis.lot`` pointe un lot qui appartient à UN devis.

    Le cloner tel quel rattacherait les lignes de la copie aux lots de la
    SOURCE ; ne pas le cloner du tout perd le découpage multi-sites. Les lots
    sont donc RECRÉÉS sur la copie et les lignes re-pointées.
    """

    slug = 'qjr116-lot'

    def setUp(self):
        super().setUp()
        from apps.ventes.models import LotDevis

        self.lot = LotDevis.objects.create(
            company=self.company, devis=self.devis, nom_lot='Villa A',
            adresse_site='Bouskoura', ordre=1)
        self.pan_sans.lot = self.lot
        self.pan_sans.save(update_fields=['lot'])

    def test_le_duplicata_recree_ses_propres_lots(self):
        from apps.ventes.domain.creation import dupliquer_devis

        copie = dupliquer_devis(self.devis, user=self.user)
        lots = list(copie.lots.all())
        self.assertEqual([lo.nom_lot for lo in lots], ['Villa A'])
        self.assertEqual(lots[0].adresse_site, 'Bouskoura')
        self.assertEqual(lots[0].company_id, self.company.pk)
        self.assertNotEqual(lots[0].pk, self.lot.pk)

        clonee = copie.lignes.get(variante='sans',
                                  designation=self.panneau.nom)
        self.assertEqual(clonee.lot_id, lots[0].pk,
                         'la ligne clonée pointe le lot de la COPIE')
        # Les autres lignes restent « hors lot », comme sur la source.
        self.assertEqual(
            copie.lignes.filter(lot__isnull=True).count(),
            self.devis.lignes.filter(lot__isnull=True).count())

    def test_un_devis_sans_lot_ne_cree_aucun_lot(self):
        """Le comportement d'hier — aucun chemin de création ne pose de lot :
        la copie d'un devis sans lot ne doit rien inventer."""
        from apps.ventes.domain.creation import dupliquer_devis

        self.pan_sans.lot = None
        self.pan_sans.save(update_fields=['lot'])
        self.lot.delete()

        copie = dupliquer_devis(self.devis, user=self.user)
        self.assertEqual(copie.lots.count(), 0)
        self.assertEqual(copie.lignes.filter(lot__isnull=False).count(), 0)
