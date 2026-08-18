"""PV86 — LA SEULE VÉRITÉ EST LE DEVIS : une présentation, un seul total.

Incident fondateur : pour UN MÊME devis, la page client affichait « Sans
batterie — 26 186 MAD TTC » pendant que le PDF affichait « Avec batterie —
60 186 MAD TTC » (la vraie somme des lignes), et le compteur « Voir le détail
du matériel (7 postes) » ne correspondait pas aux 9 lignes du PDF.

Cause : le devis portait LES DEUX onduleurs (réseau ET hybride + batterie) en
lignes NON optionnelles — un ARTEFACT d'anciens chemins, pas une alternative
commerciale. Le builder en déduisait ``deux_options`` et fabriquait deux
« options » dont AUCUNE n'égalait le total du devis.

Règle gravée ici :
  * une présentation « deux options » n'est légitime que si le devis DÉCLARE
    l'alternative — ``etude_params['scenario']`` (le générateur le persiste
    TOUJOURS, garantie QF7) — ou si l'add-on batterie est porté par des lignes
    XSAL5 ``optionnelle=True`` (le document reste alors mono-option) ;
  * dans TOUT autre cas : UNE seule présentation, dont le total EST la somme de
    toutes les lignes du devis, à l'écran, au PDF et dans la charge utile
    publique.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_pv86_verite_unique_devis -v 2
"""
import itertools
import json
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()

_company_seq = itertools.count(1)


def make_company():
    from authentication.models import Company
    n = next(_company_seq)
    c, _ = Company.objects.get_or_create(
        slug=f'test-pv86-co-{n}', defaults={'nom': f'Test PV86 Co {n}'})
    return c


# ── Compositions de référence ────────────────────────────────────────────────
# L'ARTEFACT du fondateur : les deux onduleurs + la batterie, TOUS en lignes
# non optionnelles, sur un devis qui ne déclare aucun scénario.
ARTEFACT_LIGNES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Batterie Dyness 10 kWh', '1', '14000'),
    ('Structures acier', '14', '375'),
    ('Socles', '30', '67'),
    ('Tableau De Protection AC/DC', '1', '1667'),
    ('Installation', '1', '4000'),
    ('Transport', '1', '1000'),
]
RESEAU_LIGNES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Installation', '1', '4000'),
]
BATTERIE_LIGNES = [
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Batterie Dyness 10 kWh', '1', '14000'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Installation', '1', '4000'),
]
POMPAGE_LIGNES = [
    ('Pompe immergée OSP 5.5 CV', '1', '9166.67'),
    ('Variateur VEICHI 5.5 kW', '1', '7000'),
    ('Installation', '1', '4000'),
]


class _Base(TestCase):
    def setUp(self):
        self.company = make_company()
        self.user = User.objects.create_user(
            username=f'pv86-{next(_company_seq)}', password='x',
            role_legacy='responsable', company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim',
            email='k_pv86@example.com', telephone='+212600000085')
        self._ref = itertools.count(1)

    def make_devis(self, lignes, etude_params=None, remise='0',
                   optionnelles=()):
        ref = f'DEV-PV86-{next(self._ref):04d}'
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal(remise), created_by=self.user,
            etude_params=etude_params)
        for i, (desig, qty, pu) in enumerate(list(lignes) + list(optionnelles)):
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{ref[-7:]}-{i}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'),
                optionnelle=i >= len(list(lignes)))
        return devis

    @staticmethod
    def build(devis, opts=None):
        from apps.ventes.quote_engine.builder import build_quote_data
        return build_quote_data(devis, opts)

    @staticmethod
    def ttc_du_devis(devis):
        """Total TTC canonique du devis, calculé de ses LIGNES (le modèle
        exclut déjà les lignes optionnelles/sections — XSAL5/XSAL14)."""
        return round(float(devis.total_ttc))


class TestArtefactDeuxOnduleurs(_Base):
    """Le cas du fondateur : deux onduleurs non optionnels, rien de déclaré."""

    def test_une_seule_option_avec_batterie_au_total_du_devis(self):
        devis = self.make_devis(ARTEFACT_LIGNES)
        data = self.build(devis)

        # UNE seule présentation — jamais deux options fabriquées.
        self.assertFalse(data['deux_options'])
        self.assertEqual(data['nb_options'], 1)
        # La réalité des lignes : une batterie non optionnelle est présente.
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertEqual(data['recommended'], 'Avec batterie')
        self.assertNotEqual(data['recommended'], 'Sans batterie')

        # Le total affiché EST le total du devis (somme de TOUTES ses lignes).
        self.assertEqual(data['display_total'], self.ttc_du_devis(devis))
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])
        # Aucun prix d'option fantôme ne subsiste dans la donnée.
        self.assertEqual(data['totaux_sans']['ttc'], data['totaux_avec']['ttc'])

        # Le compteur de postes == les lignes rendues (9), les deux onduleurs
        # et la batterie compris : c'est ce que le PDF facture.
        self.assertEqual(len(data['all_items']), len(ARTEFACT_LIGNES))
        desigs = ' '.join(it['designation'].lower() for it in data['all_items'])
        self.assertIn('réseau', desigs)
        self.assertIn('hybride', desigs)
        self.assertIn('batterie', desigs)

    def test_liste_et_document_disent_le_meme_chiffre(self):
        from apps.ventes.quote_engine.builder import display_totals
        devis = self.make_devis(ARTEFACT_LIGNES)
        dt = display_totals(devis)
        full = self.build(devis, {'pdf_mode': 'full'})
        one = self.build(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(dt['nb_options'], 1)
        self.assertEqual(dt['total'], self.ttc_du_devis(devis))
        self.assertEqual(full['display_total'], dt['total'])
        self.assertEqual(one['display_total'], dt['total'])
        self.assertEqual(one['totaux_all']['ttc'], dt['total'])
        # Le une-page ne renvoie plus vers une « option avec batterie ».
        self.assertFalse(one['onepage_note_batterie'])

    def test_avertissement_interne_devis_a_assainir(self):
        devis = self.make_devis(ARTEFACT_LIGNES)
        data = self.build(devis)
        avert = data.get('avertissements_internes') or []
        self.assertTrue(avert)
        self.assertIn('resynchronisation', ' '.join(avert))

    def test_devis_sain_ne_porte_aucun_avertissement(self):
        devis = self.make_devis(RESEAU_LIGNES)
        self.assertNotIn('avertissements_internes', self.build(devis))

    def test_remise_globale_le_total_reste_celui_des_lignes(self):
        """Avec remise globale, la vérité reste la chaîne canonique appliquée à
        TOUTES les lignes (``Devis.total_ttc`` n'intègre pas la remise
        globale — c'est le seul écart légitime au total modèle)."""
        devis = self.make_devis(ARTEFACT_LIGNES, remise='10')
        data = self.build(devis)
        ht = sum(float(li.quantite) * float(li.prix_unitaire)
                 for li in devis.lignes.all())
        self.assertEqual(data['nb_options'], 1)
        self.assertEqual(data['display_total'], round(ht * 0.9 * 1.2))
        self.assertEqual(data['display_total'], data['totaux_avec']['ttc'])


class TestAlternativeDeclaree(_Base):
    """Le contrat EXISTANT du générateur : il déclare toujours son scénario."""

    def test_deux_options_declarees_inchangees(self):
        devis = self.make_devis(
            ARTEFACT_LIGNES, {'scenario': 'Les deux (Sans + Avec)'})
        data = self.build(devis)
        self.assertTrue(data['deux_options'])
        self.assertEqual(data['nb_options'], 2)
        self.assertEqual(data['scenario'], 'Les deux (Sans + Avec)')
        # Chaque option vaut la somme de SES lignes (communes + siennes).
        self.assertEqual(
            data['totaux_sans']['ttc'],
            round(sum(it['quantite'] * it['prix_unit_ttc']
                      for it in data['sans_items'])))
        self.assertEqual(
            data['totaux_avec']['ttc'],
            round(sum(it['quantite'] * it['prix_unit_ttc']
                      for it in data['avec_items'])))
        # Le total de liste = option 1, jamais la somme mensongère des deux.
        self.assertEqual(data['display_total'], data['totaux_sans']['ttc'])
        self.assertLess(data['display_total'], self.ttc_du_devis(devis))
        # Un document à deux options n'est pas un devis à assainir.
        self.assertNotIn('avertissements_internes', data)

    def test_option_retenue_est_un_des_deux_totaux(self):
        """Le choix stocké (générateur, ou option retenue à l'acceptation)
        restreint le document à UNE option — et son total est bien l'un des
        deux totaux d'option du document à deux options."""
        deux = self.build(self.make_devis(
            ARTEFACT_LIGNES, {'scenario': 'Les deux (Sans + Avec)'}))
        totaux = (deux['totaux_sans']['ttc'], deux['totaux_avec']['ttc'])

        for choix, cle in (('Sans batterie', 'totaux_sans'),
                           ('Avec batterie', 'totaux_avec')):
            data = self.build(self.make_devis(
                ARTEFACT_LIGNES, {'scenario': choix}))
            self.assertEqual(data['nb_options'], 1)
            self.assertEqual(data['scenario'], choix)
            self.assertIn(data['display_total'], totaux)
            self.assertEqual(data['display_total'], data[cle]['ttc'])

    def test_recommandation_stockee_respectee(self):
        data = self.build(self.make_devis(ARTEFACT_LIGNES, {
            'scenario': 'Les deux (Sans + Avec)',
            'recommended_option': 'Sans batterie'}))
        self.assertEqual(data['recommended'], 'Sans batterie')


class TestInvariantMonoOption(_Base):
    """Invariant : un devis mono-option affiche la somme de SES lignes."""

    def test_total_et_nombre_de_postes_pour_chaque_composition(self):
        cas = [
            ('artefact deux onduleurs', ARTEFACT_LIGNES, None),
            ('réseau seul', RESEAU_LIGNES, None),
            ('hybride + batterie', BATTERIE_LIGNES, None),
            ('pompage (liste libre)', POMPAGE_LIGNES, None),
            ('réseau, choix stocké', RESEAU_LIGNES,
             {'scenario': 'Sans batterie'}),
            ('batterie, choix stocké', BATTERIE_LIGNES,
             {'scenario': 'Avec batterie'}),
        ]
        for libelle, lignes, etude in cas:
            with self.subTest(cas=libelle):
                devis = self.make_devis(lignes, etude)
                data = self.build(devis, {'pdf_mode': 'onepage'})
                self.assertEqual(data['nb_options'], 1)
                self.assertEqual(data['display_total'],
                                 self.ttc_du_devis(devis))
                self.assertEqual(len(data['all_items']), len(lignes))

    def test_mono_reseau_reste_sans_batterie(self):
        data = self.build(self.make_devis(RESEAU_LIGNES))
        self.assertEqual(data['scenario'], 'Sans batterie')
        self.assertEqual(data['recommended'], 'Sans batterie')
        self.assertTrue(data['sans_ok'])
        self.assertFalse(data['avec_ok'])

    def test_batterie_reelle_jamais_sans_batterie(self):
        data = self.build(self.make_devis(BATTERIE_LIGNES))
        self.assertEqual(data['scenario'], 'Avec batterie')
        self.assertEqual(data['recommended'], 'Avec batterie')


class TestOptionsXsal5(_Base):
    """L'autre alternative LÉGITIME : l'add-on batterie en ligne optionnelle."""

    def test_option_batterie_hors_total_document_mono_option(self):
        devis = self.make_devis(
            RESEAU_LIGNES,
            optionnelles=[('Batterie Dyness 10 kWh', '1', '14000')])
        data = self.build(devis)
        self.assertEqual(data['nb_options'], 1)
        self.assertFalse(data['deux_options'])
        # Le total reste la somme des lignes NON optionnelles.
        self.assertEqual(data['display_total'], self.ttc_du_devis(devis))
        self.assertEqual(len(data['all_items']), len(RESEAU_LIGNES))
        desigs = ' '.join(it['designation'].lower() for it in data['all_items'])
        self.assertNotIn('batterie', desigs)
        # …et l'add-on est proposé à part, chiffré, hors total.
        self.assertEqual(len(data['options_proposees']), 1)
        self.assertEqual(data['options_proposees'][0]['total_ttc'], 16800.0)


class TestChargeUtilePublique(_Base):
    """La page publique ne peut plus afficher un prix absent des documents."""

    def _payload(self, devis):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token)
        resp = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_artefact_une_seule_option_sans_prix_fantome(self):
        devis = self.make_devis(ARTEFACT_LIGNES)
        p = self._payload(devis)
        ot = p['option_totals']
        self.assertEqual(ot['nb_options'], 1)
        self.assertIsNone(ot['sans_batterie'])
        self.assertEqual(ot['avec_batterie']['ttc'], ot['display_total'])
        self.assertEqual(ot['display_total'], self.ttc_du_devis(devis))
        # Le second panier ne franchit pas la frontière publique.
        self.assertIsNone(p['quote']['totaux_sans'])
        self.assertEqual(p['quote']['sans_items'], [])
        # Le compteur de postes de la page == les lignes du PDF.
        self.assertEqual(len(p['quote']['avec_items']), len(ARTEFACT_LIGNES))
        # Les avertissements internes restent internes.
        self.assertNotIn('avertissements_internes', json.dumps(p))

    def test_mono_reseau_expose_uniquement_son_option(self):
        devis = self.make_devis(RESEAU_LIGNES)
        p = self._payload(devis)
        ot = p['option_totals']
        self.assertEqual(ot['nb_options'], 1)
        self.assertIsNone(ot['avec_batterie'])
        self.assertEqual(ot['sans_batterie']['ttc'], ot['display_total'])
        self.assertEqual(ot['display_total'], self.ttc_du_devis(devis))
        self.assertIsNone(p['quote']['totaux_avec'])
        self.assertEqual(p['quote']['avec_items'], [])

    def test_deux_options_declarees_exposent_les_deux(self):
        devis = self.make_devis(
            ARTEFACT_LIGNES, {'scenario': 'Les deux (Sans + Avec)'})
        p = self._payload(devis)
        ot = p['option_totals']
        self.assertEqual(ot['nb_options'], 2)
        self.assertIsNotNone(ot['sans_batterie'])
        self.assertIsNotNone(ot['avec_batterie'])
        self.assertEqual(ot['display_total'], ot['sans_batterie']['ttc'])
        self.assertNotEqual(
            ot['sans_batterie']['ttc'], ot['avec_batterie']['ttc'])
