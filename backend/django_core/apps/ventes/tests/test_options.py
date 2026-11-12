"""Tests A3 — l'option acceptée est autoritative en aval (facture + chantier).

Un devis à deux options (réseau + hybride/batterie) accepté « Sans batterie »
doit facturer et gélifier la nomenclature SUR LES SEULES lignes sans batterie ;
« Avec batterie » sur les seules lignes avec batterie ; un devis à option unique
reste strictement inchangé.
"""
import ast
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis
from apps.ventes.utils.options import (
    filter_lines_for_option, option_lines, option_totaux, panier_de_ligne,
    panier_du_moteur,
)
from apps.ventes.utils.echeancier import next_tranche
from apps.installations.services import _freeze_bom

User = get_user_model()
MONTH = timezone.now().strftime('%Y%m')


class _StubLigne:
    def __init__(self, designation, nom=''):
        self.designation = designation
        self.produit = type('P', (), {'nom': nom})()


class TestPureFilter(SimpleTestCase):
    """Découpage PUR (pas de base) — garde rapide de la classification."""

    def setUp(self):
        self.lignes = [
            _StubLigne('Onduleur réseau 5kW'),
            _StubLigne('Onduleur hybride 5kW'),
            _StubLigne('Panneau mono 550W', nom='Jinko'),
            _StubLigne('Batterie lithium 5 kWh'),
            _StubLigne('Installation complète'),
        ]

    def _names(self, rows):
        return [r.designation for r in rows]

    def test_sans_batterie_drops_battery_and_hybrid(self):
        names = self._names(filter_lines_for_option(self.lignes, 'sans_batterie'))
        self.assertIn('Onduleur réseau 5kW', names)
        self.assertIn('Panneau mono 550W', names)
        self.assertNotIn('Batterie lithium 5 kWh', names)
        self.assertNotIn('Onduleur hybride 5kW', names)

    def test_avec_batterie_drops_reseau(self):
        names = self._names(filter_lines_for_option(self.lignes, 'avec_batterie'))
        self.assertNotIn('Onduleur réseau 5kW', names)
        self.assertIn('Onduleur hybride 5kW', names)
        self.assertIn('Batterie lithium 5 kWh', names)

    def test_empty_option_keeps_all(self):
        self.assertEqual(len(filter_lines_for_option(self.lignes, '')), 5)

    def test_classement_suit_le_contrat_classement_options(self):
        """ADVS5 — rouge si le noyau ignore le rôle (Dyness dans « sans »)."""
        cas = json.loads(
            (Path(__file__).resolve().parents[1] / 'contract_samples'
             / 'classement_options.json').read_text(encoding='utf-8')
        )['exemple']['cas']
        self.assertTrue(cas)
        for c in cas:
            attendu = (c['sans'], c['avec'])
            ligne = SimpleNamespace(
                designation=c['designation'], produit=None,
                role_devis=c['role_devis'], variante=c['variante'])
            with self.subTest(designation=c['designation'],
                              role=c['role_devis'], variante=c['variante']):
                self.assertEqual(panier_de_ligne(
                    c['variante'], c['role_devis'], c['designation']), attendu)
                self.assertEqual(
                    (bool(filter_lines_for_option([ligne], 'sans_batterie')),
                     bool(filter_lines_for_option([ligne], 'avec_batterie'))),
                    attendu)

    @staticmethod
    def _lignes_a_roles():
        return [
            SimpleNamespace(designation=nom, produit=None, role_devis=role,
                            variante='')
            for nom, role in (
                ('Panneau Jinko 550W', 'panneau'),
                ('Onduleur réseau 5kW', 'onduleur_reseau'),
                ('Onduleur hybride 5kW', 'onduleur_hybride'),
                ('Dyness BX51100', 'batterie'),
                ('Câble batterie DC 25 mm²', 'cable_dc'))]

    def test_niveau_9_garde_le_noyau_d_hier(self):
        """ADVS5/ADVS6 — nouveaux rendus seulement : au niveau 9 le noyau ne lit
        pas le rôle (Dyness, sans mot-clé, reste dans « sans » : l'acompte reçu)."""
        envoye = SimpleNamespace(regles_calcul=9)
        lignes = self._lignes_a_roles()
        self.assertEqual(
            self._names(filter_lines_for_option(lignes, 'sans_batterie', devis=envoye)),
            ['Panneau Jinko 550W', 'Onduleur réseau 5kW', 'Dyness BX51100'])
        self.assertEqual(
            self._names(filter_lines_for_option(lignes, 'avec_batterie', devis=envoye)),
            ['Panneau Jinko 550W', 'Onduleur hybride 5kW', 'Dyness BX51100',
             'Câble batterie DC 25 mm²'])

    def test_niveau_10_prend_la_regle_unique(self):
        neuf = SimpleNamespace(regles_calcul=10)
        self.assertEqual(
            self._names(filter_lines_for_option(
                self._lignes_a_roles(), 'sans_batterie', devis=neuf)),
            ['Panneau Jinko 550W', 'Onduleur réseau 5kW'])

    def test_moteur_niveau_9_role_seul_niveau_10_regle_unique(self):
        """Le PDF reçu au niveau 9 gardait le câble dans les deux options."""
        cable = 'Câble batterie DC 25 mm²'
        envoye = SimpleNamespace(regles_calcul=9)
        self.assertEqual(panier_du_moteur('cable_dc', cable, envoye), (True, True))
        self.assertEqual(panier_du_moteur('batterie', 'Dyness BX51100', envoye),
                         (False, True))
        self.assertEqual(panier_du_moteur(None, cable, envoye), (False, True))
        self.assertEqual(
            panier_du_moteur('cable_dc', cable, SimpleNamespace(regles_calcul=10)),
            (False, True))

    def test_tout_appelant_passe_le_niveau_du_devis(self):
        """Un appel de production sans ``devis=`` classerait un envoyé sur la
        règle courante : son total d'option changerait au re-rendu."""
        vus = 0
        for chemin in Path(__file__).resolve().parents[2].rglob('*.py'):
            if ('tests' in chemin.parts or 'migrations' in chemin.parts
                    or chemin.name.startswith('test')):
                continue
            source = chemin.read_text(encoding='utf-8')
            if 'filter_lines_for_option' not in source:
                continue
            for noeud in ast.walk(ast.parse(source)):
                if (isinstance(noeud, ast.Call) and getattr(noeud.func, 'id', '')
                        in ('filter_lines_for_option', '_filtrer_opt')):
                    vus += 1
                    self.assertIn('devis', [k.arg for k in noeud.keywords],
                                  f'{chemin}:{noeud.lineno}')
        self.assertGreaterEqual(vus, 8)

    def test_batterie_et_son_cable_dans_avec_seulement(self):
        lignes = self._lignes_a_roles()
        self.assertEqual(
            self._names(filter_lines_for_option(lignes, 'sans_batterie')),
            ['Panneau Jinko 550W', 'Onduleur réseau 5kW'])
        self.assertEqual(
            self._names(filter_lines_for_option(lignes, 'avec_batterie')),
            ['Panneau Jinko 550W', 'Onduleur hybride 5kW', 'Dyness BX51100',
             'Câble batterie DC 25 mm²'])


class TestOptionDownstream(TestCase):
    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='opt-co', defaults={'nom': 'Opt Co'})
        self.user = User.objects.create_user(
            username='opt_resp', password='x', role_legacy='responsable',
            company=self.company)
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Opt',
            email='opt@example.com', telephone='+212600000009')

    def _two_option_devis(self, num=40, lignes=None):
        # PV86 — un document à DEUX options déclare son alternative dans
        # ``etude_params['scenario']`` (ce que le générateur persiste
        # toujours). Sans déclaration, deux onduleurs en lignes non
        # optionnelles sont un artefact de données : le devis n'a qu'une
        # réalité, l'aval ne filtre plus par option et facture toutes ses
        # lignes.
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'),
            etude_params={'scenario': 'Les deux (Sans + Avec)'})
        lignes = lignes or [
            ('Onduleur réseau', '1', '11700'),
            ('Onduleur hybride', '1', '24000'),
            ('Panneau mono 550W', '14', '1100'),
            ('Batterie 5 kWh', '1', '14000'),
            ('Installation', '1', '4000'),
        ]
        for desig, qty, pu, *role in lignes:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{num}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), role_devis=(role or [None])[0])
        return devis

    def test_detail_ci_garde_le_panier_du_niveau_du_devis(self):
        """ATST25 (C-ATST-013) — ``lignes_pour_economie_ci`` joué sur un devis
        en base : au niveau 9 Dyness (sans mot-clé) reste dans « sans » ; au
        niveau 10 panneau et onduleur réseau seuls (filtre pur au même niveau)."""
        from apps.ventes.economie_ci import lignes_pour_economie_ci
        roles = [(li.designation, '1', '1000', li.role_devis)
                 for li in TestPureFilter._lignes_a_roles()]
        devis = self._two_option_devis(num=25, lignes=roles)
        for niveau, attendu in (
                (9, ['Panneau Jinko 550W', 'Onduleur réseau 5kW', 'Dyness BX51100']),
                (10, ['Panneau Jinko 550W', 'Onduleur réseau 5kW'])):
            Devis.objects.filter(pk=devis.pk).update(regles_calcul=niveau)
            with self.subTest(niveau=niveau):
                self.assertEqual([li['designation'] for li in lignes_pour_economie_ci(
                    Devis.objects.get(pk=devis.pk), 'sans_batterie')], attendu)

    def _single_option_devis(self, num=50):
        devis = Devis.objects.create(
            company=self.company, reference=f'DEV-{MONTH}-{num:04d}',
            client=self.client_obj, statut=Devis.Statut.ENVOYE,
            taux_tva=Decimal('20'))
        for desig, qty, pu in [
            ('Onduleur réseau', '1', '11700'),
            ('Panneau mono 550W', '14', '1100'),
        ]:
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{num}-{desig[:10]}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qty), prix_unitaire=Decimal(pu),
                remise=Decimal('0'))
        return devis

    def test_option_totaux_sans(self):
        devis = self._two_option_devis(num=41)
        devis.option_acceptee = 'sans_batterie'
        devis.save(update_fields=['option_acceptee'])
        t = option_totaux(devis)
        # réseau 11700 + panneaux 15400 + installation 4000 = 31100 HT brut
        # ARRONDI-100 : TTC 37320 → 37300, par une baisse de HT de 16,67
        # (ht 31100 → 31083.33, tva 6220 → 6216.67). Les lignes ne bougent pas.
        self.assertEqual(t['ht_brut'], Decimal('31100.00'))
        self.assertEqual(t['arrondi'], Decimal('16.67'))
        self.assertEqual(t['ht'], Decimal('31083.33'))
        self.assertEqual(t['tva'], Decimal('6216.67'))
        self.assertEqual(t['ttc'], Decimal('37300.00'))

    def test_option_totaux_avec(self):
        devis = self._two_option_devis(num=42)
        devis.option_acceptee = 'avec_batterie'
        devis.save(update_fields=['option_acceptee'])
        t = option_totaux(devis)
        # hybride 24000 + panneaux 15400 + batterie 14000 + installation 4000
        # = 57400 HT brut. ARRONDI-100 : TTC 68880 → 68800 (HT 57400 → 57333.33,
        # arrondi 66.67).
        self.assertEqual(t['ht_brut'], Decimal('57400.00'))
        self.assertEqual(t['arrondi'], Decimal('66.67'))
        self.assertEqual(t['ht'], Decimal('57333.33'))
        self.assertEqual(t['ttc'], Decimal('68800.00'))

    def test_echeancier_acompte_uses_accepted_option(self):
        devis = self._two_option_devis(num=43)
        devis.option_acceptee = 'sans_batterie'
        devis.statut = Devis.Statut.ACCEPTE
        devis.save(update_fields=['option_acceptee', 'statut'])
        tr = next_tranche(devis)
        # acompte 30 % du TTC de l'option « sans » (37300 après ARRONDI-100),
        # pas du total mêlé.
        self.assertEqual(tr['key'], 'acompte')
        # ARRONDI-100 : 11196.00 → 11190.00
        self.assertEqual(tr['ttc'], Decimal('11190.00'))

    def test_bom_excludes_battery_for_sans(self):
        devis = self._two_option_devis(num=44)
        devis.option_acceptee = 'sans_batterie'
        devis.save(update_fields=['option_acceptee'])
        designations = [li['designation'] for li in _freeze_bom(devis)]
        self.assertIn('Onduleur réseau', designations)
        self.assertNotIn('Batterie 5 kWh', designations)
        self.assertNotIn('Onduleur hybride', designations)

    def test_bom_includes_battery_for_avec(self):
        devis = self._two_option_devis(num=45)
        devis.option_acceptee = 'avec_batterie'
        devis.save(update_fields=['option_acceptee'])
        designations = [li['designation'] for li in _freeze_bom(devis)]
        self.assertIn('Batterie 5 kWh', designations)
        self.assertIn('Onduleur hybride', designations)
        self.assertNotIn('Onduleur réseau', designations)

    def test_single_option_unchanged(self):
        """Devis à option unique : option_totaux = totaux complets, BOM complet,
        même si une option est posée (déduite). Comportement historique."""
        devis = self._single_option_devis(num=51)
        devis.option_acceptee = 'sans_batterie'  # déduite par A1
        devis.save(update_fields=['option_acceptee'])
        t = option_totaux(devis)
        self.assertEqual(t['ht'], Decimal(str(devis.total_ht)))
        self.assertEqual(t['ttc'], Decimal(str(devis.total_ttc)))
        self.assertEqual(len(option_lines(devis)), 2)

    def test_lecture_seule_lead_lignes_de_l_option(self):
        """AANA88 — le panneau visite d'un devis deux options accepté « sans »
        ne liste que les lignes de l'option retenue, sous son total TTC."""
        from apps.crm.models import Lead
        from apps.ventes.selectors import devis_lecture_seule_pour_lead
        lead = Lead.objects.create(company=self.company, nom='Lead AANA88')
        devis = self._two_option_devis(num=88)
        Devis.objects.filter(pk=devis.pk).update(
            lead=lead, statut=Devis.Statut.ACCEPTE,
            option_acceptee='sans_batterie')
        (dossier,) = devis_lecture_seule_pour_lead(lead)
        self.assertEqual(
            [li['designation'] for li in dossier['lignes']],
            [li.designation for li in option_lines(Devis.objects.get(pk=devis.pk))])
        noms = ' '.join(li['designation'] for li in dossier['lignes'])
        self.assertNotIn('Batterie', noms)
        self.assertNotIn('hybride', noms)
        self.assertEqual(len(dossier['lignes']), 3)
        self.assertEqual(Decimal(dossier['total_ttc']),
                         Decimal(str(Devis.objects.get(pk=devis.pk).total_ttc)))

    def test_devis_pour_projet_option_retenue(self):
        """AANA89 — le budget projet d'un deux-options accepté « sans » ne
        ventile que les lignes de l'option retenue."""
        from apps.ventes.selectors import devis_pour_projet
        devis = self._two_option_devis(num=89)
        Devis.objects.filter(pk=devis.pk).update(
            statut=Devis.Statut.ACCEPTE, option_acceptee='sans_batterie')
        res = devis_pour_projet(devis.id, self.company)
        attendu = sum((Decimal(str(li.total_ht)) for li in option_lines(
            Devis.objects.get(pk=devis.pk))), Decimal('0'))
        self.assertEqual(attendu, Decimal('31100'))
        self.assertEqual(
            Decimal(str(res['montant_materiel'])) + Decimal(str(res['montant_main_oeuvre'])),
            attendu)
        self.assertEqual(res['nb_lignes_materiel'] + res['nb_lignes_main_oeuvre'], 3)


class TestFamillesServables(SimpleTestCase):
    """BAT-DIFF (ordre fondateur, 17/09/2026) — servabilité PURE par familles.

    « avec » = hybride + batterie réelle, OU hybride FACE à un onduleur réseau
    (batterie différée — le client l'ajoutera plus tard). L'autonome exige
    toujours une batterie ; l'hybride SEUL reste mono-option (Z1).
    """

    def _f(self, **familles):
        from apps.ventes.utils.options import familles_servables
        base = dict(has_reseau=False, has_hybride=False, has_offgrid=False,
                    has_batterie=False)
        base.update(familles)
        return familles_servables(**base)

    def test_hybride_face_au_reseau_sans_batterie_sert_les_deux(self):
        self.assertEqual(self._f(has_reseau=True, has_hybride=True),
                         (True, True))

    def test_hybride_seul_sans_batterie_ne_sert_rien(self):
        self.assertEqual(self._f(has_hybride=True), (False, False))

    def test_hybride_et_batterie_sans_reseau(self):
        self.assertEqual(self._f(has_hybride=True, has_batterie=True),
                         (False, True))

    def test_reseau_seul(self):
        self.assertEqual(self._f(has_reseau=True), (True, False))

    def test_autonome_face_au_reseau_sans_batterie_reste_mono(self):
        self.assertEqual(self._f(has_reseau=True, has_offgrid=True),
                         (True, False))

    def test_autonome_avec_batterie(self):
        self.assertEqual(self._f(has_offgrid=True, has_batterie=True),
                         (False, True))


class TestEtudeHoraireSansStockage(SimpleTestCase):
    """BAT-DIFF — un bloc horaire calculé AVEC batterie est ramené à « sans »."""

    def test_avec_prend_les_chiffres_de_sans(self):
        from apps.ventes.quote_engine.builder import _etude_horaire_sans_stockage
        bloc = {
            'kwc': 9.94,
            'annuel': {'economie_sans_mad': 9000.0, 'economie_avec_mad': 14000.0,
                       'taux_autoconso_sans': 0.55, 'taux_autoconso_avec': 0.9,
                       'facture_apres_sans_mad': 3000.0,
                       'facture_apres_avec_mad': 1000.0},
            'mois': [{'economie_sans_mad': 700.0, 'economie_avec_mad': 1200.0}],
        }
        copie = _etude_horaire_sans_stockage(bloc)
        self.assertEqual(copie['annuel']['economie_avec_mad'], 9000.0)
        self.assertEqual(copie['annuel']['taux_autoconso_avec'], 0.55)
        self.assertEqual(copie['annuel']['facture_apres_avec_mad'], 3000.0)
        self.assertEqual(copie['mois'][0]['economie_avec_mad'], 700.0)
        # Le bloc d'origine n'est pas muté (fonction pure).
        self.assertEqual(bloc['annuel']['economie_avec_mad'], 14000.0)
        self.assertEqual(bloc['mois'][0]['economie_avec_mad'], 1200.0)

    def test_bloc_illisible_rendu_tel_quel(self):
        from apps.ventes.quote_engine.builder import _etude_horaire_sans_stockage
        self.assertIsNone(_etude_horaire_sans_stockage(None))
        self.assertEqual(_etude_horaire_sans_stockage('x'), 'x')


class TestMarqueFigeeDuNoyau(TestCase):
    """ADVS7 × noyau monnaie — l'accessoire Huawei suit la marque FIGÉE à l'envoi,
    comme le moteur PDF : corriger la marque au catalogue ne change pas le total
    d'un envoyé. Sans instantané : la marque du jour, comme hier."""

    def setUp(self):
        self.company, _ = Company.objects.get_or_create(
            slug='opt-marque', defaults={'nom': 'Opt Marque'})
        self.client_obj = Client.objects.create(
            company=self.company, nom='Client', prenom='Marque')
        self.onduleur = Produit.objects.create(
            company=self.company, nom='Onduleur réseau 5kW', sku='MQ-OND',
            marque='Huawei', prix_vente=Decimal('9000'),
            prix_achat=Decimal('1'), quantite_stock=10)
        self.compteur = Produit.objects.create(
            company=self.company, nom='Smart Meter DTSU666', sku='MQ-SM',
            prix_vente=Decimal('1500'), prix_achat=Decimal('1'),
            quantite_stock=10)

    def _devis(self, reference, *, statut='envoye', regles=10, fige=True):
        clauses = [{'type': 'reglages_figes', 'produits': {
            str(self.onduleur.pk): {
                'marque': 'Huawei', 'description': '', 'garantie': '',
                'garantie_mois': None, 'garantie_production_mois': None}}}]
        devis = Devis.objects.create(
            company=self.company, reference=reference, client=self.client_obj,
            statut=statut, taux_tva=Decimal('20'), regles_calcul=regles,
            clauses_appliquees=clauses if fige else [])
        for produit in (self.onduleur, self.compteur):
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=produit.nom,
                quantite=Decimal('1'), prix_unitaire=produit.prix_vente,
                remise=Decimal('0'))
        return devis

    def _garde_le_compteur(self, devis):
        """Lu sur une instance NEUVE : aucun cache de la ligne ou du produit."""
        from apps.ventes.utils.options import lignes_avec_produit
        frais = Devis.objects.get(pk=devis.pk)
        return 'Smart Meter DTSU666' in [
            li.designation for li in filter_lines_for_option(
                lignes_avec_produit(frais), 'sans_batterie', devis=frais)]

    def _corriger_la_marque(self):
        Produit.objects.filter(pk=self.onduleur.pk).update(marque='Deye')

    def test_envoye_fige_garde_son_panier(self):
        devis = self._devis(f'DEV-{MONTH}-8101')
        self.assertTrue(self._garde_le_compteur(devis))
        self._corriger_la_marque()
        self.assertTrue(self._garde_le_compteur(devis))

    def test_noyau_et_moteur_lisent_la_meme_marque(self):
        from apps.ventes.quote_engine.lignes_classement import (
            _item_marque, _line_to_item, fiches_figees)
        from apps.ventes.utils.options import _blob_marque, lignes_avec_produit
        devis = self._devis(f'DEV-{MONTH}-8102')
        self._corriger_la_marque()
        frais = Devis.objects.get(pk=devis.pk)
        for ligne in lignes_avec_produit(frais):
            item = _line_to_item(ligne, Decimal('20'), fiches_figees(frais))
            self.assertEqual(_blob_marque(ligne), _item_marque(item))
        onduleur = next(li for li in lignes_avec_produit(frais)
                        if li.produit_id == self.onduleur.pk)
        self.assertIn('Huawei', _blob_marque(onduleur))

    def test_envoye_sans_instantane_niveau_9_suit_le_catalogue(self):
        """Tous les devis ≤ 9 d'avant ce gel : à l'octet, le comportement d'hier."""
        devis = self._devis(f'DEV-{MONTH}-8103', regles=9, fige=False)
        self.assertTrue(self._garde_le_compteur(devis))
        self._corriger_la_marque()
        self.assertFalse(self._garde_le_compteur(devis))

    def test_brouillon_ignore_l_entree_heritee(self):
        devis = self._devis(f'DEV-{MONTH}-8104', statut='brouillon')
        self._corriger_la_marque()
        self.assertFalse(self._garde_le_compteur(devis))
