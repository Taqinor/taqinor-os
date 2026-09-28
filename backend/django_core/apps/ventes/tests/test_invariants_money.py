"""QAH2 — Invariants Hypothesis sur la chaîne d'argent des documents ventes.

Couvre le NOYAU PARTAGÉ (jamais une septième chaîne) : ``selectors.
_canonical_totaux`` / ``selectors.tva_buckets`` (Devis + référentiel DC23),
``domain.argent.totaux``/``repartir_remise_par_ligne`` (façade NOMMÉE du
devis, QJR49/QJRREM — c'est EXACTEMENT ce que consomme
``quote_engine/builder.py`` via ``domain.argent.totaux(vue=Vue.AFFICHAGE)``,
vérifié en lecture seule — jamais modifié ici) et
``apps.facturation.totaux.TotauxDocumentMixin`` (Facture/Avoir/NoteDebit,
AUD105-107).

Deux paliers :

* :class:`MoneyChainPureInvariants` — SimpleTestCase, AUCUNE base de données
  (les « lignes » sont des instances ``LigneDevis``/``LigneFacture`` non
  sauvegardées : leurs propriétés ``total_ht``/``taux_tva_effectif`` ne
  touchent jamais la base tant que ``taux_tva`` est posé explicitement).
  Tourne en local : ``python manage.py test
  apps.ventes.tests.test_invariants_money.MoneyChainPureInvariants``.
* :class:`MoneySerializerModelInvariants` — Hypothesis+Django ``TestCase``,
  CI SEULEMENT (Postgres requis) : vérifie que le MODÈLE réellement
  sauvegardé (``Devis``) et le SÉRIALISEUR qui l'expose
  (``BonCommandeSerializer``) rendent le même chiffre que le noyau pur.

Toute divergence trouvée reste ICI comme ``@unittest.expectedFailure`` avec un
identifiant ``ERR-QAH-VENTES-<SLUG>`` dans sa docstring — jamais un test
assoupli ni une correction du code de production dans cette tâche (QAH2 ne
touche que des tests + ``requirements-dev.txt``).
"""
import unittest
from decimal import Decimal

from django.test import SimpleTestCase, tag
from hypothesis import HealthCheck, example, given, settings
from hypothesis import strategies as st
from hypothesis.extra.django import TestCase as HypothesisDjangoTestCase

from apps.facturation.models import LigneFacture
from apps.facturation.totaux import TotauxDocumentMixin
from apps.ventes.domain.argent import Vue, repartir_remise_par_ligne
from apps.ventes.domain.argent import totaux as argent_totaux
from apps.ventes.models import BonCommande, Devis, LigneDevis
from apps.ventes.selectors import TAUX_TVA_REFERENTIEL, _canonical_totaux
from apps.ventes.serializers import BonCommandeSerializer
from apps.ventes.tests._quote_engine_common import make_client, make_company
from core.money import quantize_mad

# ── Taux de TVA légaux (référentiel unique DC23 — jamais une valeur en dur) ──
TAUX_LEGAUX = tuple(
    sorted(Decimal(str(v)) for v in TAUX_TVA_REFERENTIEL.values()))

# ── Profils Hypothesis — CI-friendly, déterministes (derandomize) ───────────
PUR = settings(
    max_examples=80, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow])
DB = settings(
    max_examples=10, deadline=None, derandomize=True,
    suppress_health_check=[HealthCheck.too_slow])

# ── Stratégies partagées ─────────────────────────────────────────────────────
# st.decimals(places=2) sur quantité/prix/remise (plan QAH2) ; taux_tva pris
# dans le référentiel légal marocain (0 / 10 / 20), jamais une valeur inventée.
quantite_st = st.decimals(
    min_value=Decimal('0.01'), max_value=Decimal('500'), places=2)
prix_st = st.decimals(
    min_value=Decimal('0'), max_value=Decimal('20000'), places=2)
remise_ligne_st = st.decimals(
    min_value=Decimal('0'), max_value=Decimal('100'), places=2)
remise_globale_st = st.decimals(
    min_value=Decimal('0'), max_value=Decimal('100'), places=2)
taux_st = st.sampled_from(TAUX_LEGAUX)

ligne_spec_st = st.tuples(quantite_st, prix_st, remise_ligne_st, taux_st)
lignes_specs_st = st.lists(ligne_spec_st, min_size=1, max_size=6)


def _lignes_devis(specs):
    """``LigneDevis`` NON sauvegardées — la formule ``total_ht`` réelle du
    modèle (jamais réimplémentée ici), sans toucher la base tant que
    ``taux_tva`` est posé (court-circuite l'accès à ``self.devis``)."""
    return [
        LigneDevis(quantite=q, prix_unitaire=pu, remise=r, taux_tva=t,
                   type_ligne=LigneDevis.TypeLigne.PRODUIT)
        for (q, pu, r, t) in specs
    ]


def _lignes_facture(specs):
    """Miroir ``LigneFacture`` — même formule ``total_ht``, même garde."""
    return [
        LigneFacture(quantite=q, prix_unitaire=pu, remise=r, taux_tva=t)
        for (q, pu, r, t) in specs
    ]


class _FakeManager:
    """Le SEUL contrat que ``TotauxDocumentMixin`` attend de ``self.lignes`` :
    un ``.all()`` qui rend les lignes du document. Aucun ORM requis — le
    mixin ne lit jamais autre chose sur ce relation-manager."""

    def __init__(self, lignes):
        self._lignes = list(lignes)

    def all(self):
        return list(self._lignes)


class _FakeDocumentTotaux(TotauxDocumentMixin):
    """Hôte minimal du mixin partagé Facture/Avoir/NoteDebit (AUD105-107) —
    mêmes attributs exigés par sa docstring, aucune écriture en base."""

    def __init__(self, lignes, *, remise_globale=Decimal('0'),
                 taux_tva=Decimal('20'), montant_ht=None, montant_tva=None,
                 montant_ttc=None):
        self.lignes = _FakeManager(lignes)
        self.remise_globale = remise_globale
        self.taux_tva = taux_tva
        self.montant_ht = montant_ht
        self.montant_tva = montant_tva
        self.montant_ttc = montant_ttc


class _FakeDevisPourArgent:
    """Le SEUL contrat que ``domain.argent.totaux(devis, vue=..., lignes=...)``
    lit sur ``devis`` QUAND des lignes sont fournies explicitement :
    ``remise_globale`` et ``taux_tva`` — ``option`` reste ``None`` sur ce
    chemin (cf. ``_totaux_canoniques``), donc ``has_two_options(devis)``
    n'est jamais consultée et aucun autre attribut n'est lu. C'est
    EXACTEMENT le chemin qu'emprunte ``quote_engine/builder.py`` quand il a
    déjà ses propres lignes découpées (vérifié en lecture seule, jamais
    modifié)."""

    def __init__(self, remise_globale=Decimal('0'), taux_tva=Decimal('20')):
        self.remise_globale = remise_globale
        self.taux_tva = taux_tva


class MoneyChainPureInvariants(SimpleTestCase):
    """Chaîne d'argent pure — aucune base de données. Tourne en local."""

    databases = set()

    # ── Sous-total → Remise → Total HT ──────────────────────────────────────
    @PUR
    @given(specs=lignes_specs_st, remise_globale=remise_globale_st,
           taux_fallback=taux_st)
    def test_remise_bornee_entre_zero_et_sous_total(
            self, specs, remise_globale, taux_fallback):
        lignes = _lignes_devis(specs)
        result = _canonical_totaux(
            lignes, remise_globale_pct=remise_globale,
            fallback_taux=taux_fallback)
        self.assertGreaterEqual(result['remise'], Decimal('0'))
        self.assertLessEqual(result['remise'], result['ht_brut'])

    @PUR
    @given(specs=lignes_specs_st, remise_globale=remise_globale_st,
           taux_fallback=taux_st)
    def test_total_ht_egale_sous_total_moins_remise(
            self, specs, remise_globale, taux_fallback):
        """Total HT = Sous-total HT − Remise, AU CENTIME AFFICHÉ (les deux
        opérandes sont les valeurs déjà arrondies rendues par le noyau — la
        chaîne imprimée que le client additionne)."""
        lignes = _lignes_devis(specs)
        result = _canonical_totaux(
            lignes, remise_globale_pct=remise_globale,
            fallback_taux=taux_fallback)
        self.assertEqual(
            result['ht_net'],
            quantize_mad(result['ht_brut'] - result['remise']))

    # ── Total HT → TVA → Total TTC ───────────────────────────────────────────
    @PUR
    @given(specs=lignes_specs_st, remise_globale=remise_globale_st,
           taux_fallback=taux_st)
    def test_total_ttc_egale_total_ht_plus_tva(
            self, specs, remise_globale, taux_fallback):
        lignes = _lignes_devis(specs)
        result = _canonical_totaux(
            lignes, remise_globale_pct=remise_globale,
            fallback_taux=taux_fallback)
        self.assertEqual(
            result['ttc'], quantize_mad(result['ht_net'] + result['tva']))

    @PUR
    @given(specs=lignes_specs_st, remise_globale=remise_globale_st,
           taux_fallback=taux_st)
    def test_tva_par_taux_somme_egale_total_tva(
            self, specs, remise_globale, taux_fallback):
        """La ventilation par taux du noyau canonique se réconcilie au
        centime avec son propre total TVA (auto-cohérence — la comparaison
        AVEC ``tva_buckets`` est une question DIFFÉRENTE, couverte par
        ERR-QAH-VENTES-FACTURE-HT-NON-ARRONDI ci-dessous)."""
        lignes = _lignes_devis(specs)
        result = _canonical_totaux(
            lignes, remise_globale_pct=remise_globale,
            fallback_taux=taux_fallback)
        somme_paniers = sum(
            (b['montant'] for b in result['tva_par_taux']), Decimal('0'))
        self.assertEqual(quantize_mad(somme_paniers), result['tva'])

    # ── Lignes hors-total (XSAL5/XSAL14) ─────────────────────────────────────
    @PUR
    @given(specs=lignes_specs_st, remise_globale=remise_globale_st,
           taux_fallback=taux_st)
    def test_lignes_section_note_et_optionnelles_exclues(
            self, specs, remise_globale, taux_fallback):
        """Une ligne de section/note ou optionnelle non activée ne pèse RIEN
        dans le total — ajouter n'importe laquelle à un panier ne doit
        JAMAIS changer ht_brut/tva/ttc."""
        lignes = _lignes_devis(specs)
        base = _canonical_totaux(
            lignes, remise_globale_pct=remise_globale,
            fallback_taux=taux_fallback)

        section = LigneDevis(
            designation='Intertitre', type_ligne=LigneDevis.TypeLigne.SECTION,
            taux_tva=taux_fallback)
        note = LigneDevis(
            designation='Note libre', type_ligne=LigneDevis.TypeLigne.NOTE,
            taux_tva=taux_fallback)
        optionnelle = LigneDevis(
            quantite=Decimal('99'), prix_unitaire=Decimal('999'),
            remise=Decimal('0'), taux_tva=taux_fallback,
            type_ligne=LigneDevis.TypeLigne.PRODUIT, optionnelle=True)

        with_extra = _canonical_totaux(
            lignes + [section, note, optionnelle],
            remise_globale_pct=remise_globale, fallback_taux=taux_fallback)

        self.assertEqual(base['ht_brut'], with_extra['ht_brut'])
        self.assertEqual(base['tva'], with_extra['tva'])
        self.assertEqual(base['ttc'], with_extra['ttc'])

    # ── Répartition de la remise ligne par ligne (QJRREM) ────────────────────
    @PUR
    @given(specs=lignes_specs_st, remise_globale=remise_globale_st,
           taux_fallback=taux_st)
    def test_repartir_remise_par_ligne_somme_exacte(
            self, specs, remise_globale, taux_fallback):
        """LA GARANTIE documentée de ``repartir_remise_par_ligne`` : la somme
        des parts non nulles vaut EXACTEMENT le Total HT net, au centime —
        sinon l'affichage ligne-par-ligne ne s'additionne plus au total
        imprimé juste dessous."""
        lignes = _lignes_devis(specs)
        result = _canonical_totaux(
            lignes, remise_globale_pct=remise_globale,
            fallback_taux=taux_fallback)
        parts = repartir_remise_par_ligne(lignes, result['remise'])

        self.assertEqual(len(parts), len(lignes))
        somme = sum((p for p in parts if p is not None), Decimal('0'))
        self.assertEqual(somme, result['ht_net'])
        for p in parts:
            if p is not None:
                self.assertEqual(p, quantize_mad(p))

    # ── Cohérence Devis ↔ Facture/Avoir (même noyau, QJR49) ──────────────────
    @PUR
    @given(specs=lignes_specs_st,
           remise_globale=st.decimals(
               min_value=Decimal('0.01'), max_value=Decimal('100'),
               places=2),
           taux_fallback=taux_st)
    def test_devis_chain_egale_facture_chain_avec_remise_globale(
            self, specs, remise_globale, taux_fallback):
        """Avec une remise globale ACTIVE (> 0), Facture/Avoir empruntent le
        MÊME noyau canonique que Devis (``TotauxDocumentMixin._canonique``
        appelle ``selectors._canonical_totaux``, comme
        ``domain.argent.totaux``) : les trois totaux doivent être identiques,
        au centime, pour les mêmes lignes/remise/taux — exactement
        « totaux du sérialiseur = ceux du modèle = ceux du builder PDF »."""
        lignes_devis = _lignes_devis(specs)
        fake_devis = _FakeDevisPourArgent(
            remise_globale=remise_globale, taux_tva=taux_fallback)
        totaux_devis = argent_totaux(
            fake_devis, vue=Vue.NET, lignes=lignes_devis)

        lignes_facture = _lignes_facture(specs)
        doc_facture = _FakeDocumentTotaux(
            lignes_facture, remise_globale=remise_globale,
            taux_tva=taux_fallback)

        self.assertEqual(totaux_devis.ht_net, doc_facture.total_ht)
        self.assertEqual(totaux_devis.tva, doc_facture.total_tva)
        self.assertEqual(totaux_devis.ttc, doc_facture.total_ttc)

    # ── ERR-QAH-VENTES-FACTURE-HT-NON-ARRONDI ────────────────────────────────
    @unittest.expectedFailure
    @PUR
    @example(
        specs=[(Decimal('1.00'), Decimal('450.00'), Decimal('91.19'),
                Decimal('10'))],
        taux_fallback=Decimal('10'))
    @given(specs=lignes_specs_st, taux_fallback=taux_st)
    def test_facture_total_ht_arrondi_sans_remise_globale_ERR_QAH_VENTES_FACTURE_HT_NON_ARRONDI(  # noqa: E501
            self, specs, taux_fallback):
        """DIVERGENCE RÉELLE — ERR-QAH-VENTES-FACTURE-HT-NON-ARRONDI.

        Reproduite localement (SimpleTestCase, aucune base), DEUX symptômes
        du même défaut — ``TotauxDocumentMixin`` (Facture/Avoir/NoteDebit,
        ``apps/facturation/totaux.py``) SANS remise globale active (le cas
        COURANT : la majorité des factures n'en portent pas) ne route PAS
        par le noyau canonique ``selectors._canonical_totaux`` que
        ``Devis.total_ht``/``total_tva`` consultent TOUJOURS, remise nulle
        incluse :

        1. ``total_ht`` retombe sur ``sum(ligne.total_ht for ligne in
           self.lignes.all())`` — une somme BRUTE, JAMAIS quantifiée au
           centime (``LigneFacture.total_ht`` ne s'arrondit pas non plus :
           ``quantite*prix_unitaire*(1-remise/100)`` porte autant de
           décimales que la division l'exige). Minimal : UNE
           ``LigneFacture(quantite=3.00, prix_unitaire=10.00,
           remise=33.33, taux_tva=20)`` → ``total_ht ==
           Decimal('20.00100000')`` au lieu de ``20.00`` (``total_ttc ==
           24.00100000`` au lieu de ``24.00``).

        2. ``tva_par_taux``/``total_tva`` retombent sur ``tva_buckets``, qui
           calcule la TVA sur la base BRUTE (``base = sum(li.total_ht)``,
           puis ``q(base*taux/100)``) alors que le noyau canonique arrondit
           la base AVANT d'appliquer le taux (``ht_net = q(ht_brut -
           remise)``, puis ``q(ht_net*taux/100)``) — le classique
           arrondi-puis-multiplie vs multiplie-puis-arrondit, et les deux
           PEUVENT diverger d'un centime. Minimal (pinné en ``@example``
           pour une reproduction déterministe en CI) : UNE
           ``LigneFacture(quantite=1.00, prix_unitaire=450.00,
           remise=91.19, taux_tva=10)`` → total_ht brut = 39.645000 ;
           noyau canonique : ``ht_net=q(39.645)=39.65`` puis
           ``tva=q(39.65*10/100)=3.97`` ; ``tva_buckets`` :
           ``base=39.645`` (non arrondi) puis ``montant=q(39.645*10/100)
           =3.96`` — UN CENTIME d'écart, reproductible et déterministe.

        Un seul remède couvrirait les deux : faire toujours passer
        ``TotauxDocumentMixin`` par ``selectors._canonical_totaux``, même
        remise globale nulle — mais cette tâche (QAH2) n'écrit QUE des
        tests + ``requirements-dev.txt`` ; la propriété reste
        ``expectedFailure`` (jamais un test assoupli, jamais une correction
        de code de production ici)."""
        lignes_devis = _lignes_devis(specs)
        result = _canonical_totaux(
            lignes_devis, remise_globale_pct=Decimal('0'),
            fallback_taux=taux_fallback)

        lignes_facture = _lignes_facture(specs)
        doc_facture = _FakeDocumentTotaux(
            lignes_facture, remise_globale=Decimal('0'),
            taux_tva=taux_fallback)

        self.assertEqual(result['ht_net'], doc_facture.total_ht)
        self.assertEqual(result['ttc'], doc_facture.total_ttc)
        self.assertEqual(result['tva'], doc_facture.total_tva)


@tag('slow')
class MoneySerializerModelInvariants(HypothesisDjangoTestCase):
    """Modèle réellement sauvegardé + sérialiseur — Postgres requis (CI).

    « totaux du sérialiseur = ceux du modèle » : ``BonCommandeSerializer``
    délègue à ``domain.argent.totaux(bc.devis, vue=Vue.NET)`` — le MÊME appel
    que la propriété ``Devis.total_ht``/``total_tva``/``total_ttc``
    (AUD115). Ce test le prouve sur un devis RÉELLEMENT écrit en base
    (lignes rechargées depuis Postgres — pas seulement en mémoire).
    """

    @DB
    @given(specs=lignes_specs_st, remise_globale=remise_globale_st,
           taux_fallback=taux_st)
    def test_serializer_bc_egale_modele_devis_egale_noyau_canonique(
            self, specs, remise_globale, taux_fallback):
        from apps.stock.models import Produit
        import uuid

        company = make_company()
        client = make_client(company)
        devis = Devis.objects.create(
            company=company, reference=f'DEV-QAH2-{uuid.uuid4().hex[:10]}',
            client=client, statut=Devis.Statut.ACCEPTE,
            taux_tva=taux_fallback, remise_globale=remise_globale)
        for i, (q, pu, r, t) in enumerate(specs):
            produit = Produit.objects.create(
                company=company, nom=f'Produit {i}',
                sku=f'QAH2-{uuid.uuid4().hex[:8]}',
                prix_vente=pu, prix_achat=Decimal('1'), quantite_stock=1000)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=f'Ligne {i}',
                quantite=q, prix_unitaire=pu, remise=r, taux_tva=t)
        bc = BonCommande.objects.create(
            company=company, reference=f'BC-QAH2-{uuid.uuid4().hex[:10]}',
            devis=devis, client=client, statut=BonCommande.Statut.EN_ATTENTE)

        # Le noyau, appelé sur les lignes RECHARGÉES depuis la base.
        devis.refresh_from_db()
        lignes_recharges = list(devis.lignes.all())
        attendu = _canonical_totaux(
            lignes_recharges, remise_globale_pct=devis.remise_globale,
            fallback_taux=devis.taux_tva)

        # Le MODÈLE.
        self.assertEqual(devis.total_ht, attendu['ht_net'])
        self.assertEqual(devis.total_tva, attendu['tva'])
        self.assertEqual(devis.total_ttc, attendu['ttc'])

        # Le SÉRIALISEUR (BonCommandeSerializer._totaux → même façade AUD115).
        data = BonCommandeSerializer(bc).data
        self.assertEqual(Decimal(data['total_ht']), attendu['ht_net'])
        self.assertEqual(Decimal(data['total_tva']), attendu['tva'])
        self.assertEqual(Decimal(data['total_ttc']), attendu['ttc'])

        # Aucun prix d'achat ne fuit jamais dans une sortie client (règle #4 /
        # NE PAS FAIRE du groupe QAH) — un garde-fou bon marché à poser ici.
        self.assertNotIn('prix_achat', data)
