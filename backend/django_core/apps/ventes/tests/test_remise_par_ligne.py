"""QJRREM — LA REMISE GLOBALE, LIGNE PAR LIGNE (fondateur, 07/09/2026).

« La remise de 5 % est gardée partout et s'applique aussi à chaque poste de la
liste des composants, de l'installation, de tout. »

CE QUE CE MODULE GARDE, EN TROIS ÉTAGES :

1. LE NOYAU — ``domain.argent.repartir_remise_par_ligne`` : la somme des lignes
   remisées vaut EXACTEMENT le Total HT net, au centime (invariant #10 de
   ``docs/invariants.md``). Un cas d'école (trois lignes à 33,33 remisées de
   5 %) suffit à faire dériver trois arrondis indépendants du total imprimé
   juste dessous : le client additionne et ne retombe pas.
2. LA CHARGE UTILE — le moteur PDF pose sur chaque item ``pu_ht_remise`` /
   ``total_ht_remise`` / ``pu_ttc_remise`` / ``total_ttc_remise``, et la somme
   des totaux remisés d'un panier vaut le ``ht_net`` de CE panier.
3. LE DOCUMENT — le PDF imprime le prix catalogue barré et le prix remisé, dit
   en UNE phrase ce qu'il montre, ne bouge d'AUCUNE page (3 / 4 avec étude /
   une page), et ne laisse JAMAIS fuiter ``Produit.prix_achat`` (règle #4).

LA TABLE ``FIXTURES`` CI-DESSOUS EST LA MÊME, CAS POUR CAS ET VALEUR POUR
VALEUR, que celle du miroir JS ``frontend/src/features/ventes/remise.test.mjs``
(constante ``FIXTURES``). Les deux implémentations DOIVENT rendre la même
répartition : sans cette table partagée, l'écran du vendeur et le PDF du client
peuvent se contredire d'un centime sans que rien ne devienne rouge.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_remise_par_ligne -v 2
"""

import re
from decimal import Decimal

from django.test import SimpleTestCase, TestCase, tag

from apps.ventes.tests._quote_engine_common import (
    DEUX_OPTIONS, make_client, make_company, make_devis, make_user,
)


# nom, lignes [(montant HT, type de ligne, optionnelle)], remise globale en %,
# puis ce que la chaîne canonique arrête (remise, ht_net) et la répartition
# attendue, ``None`` pour une ligne qui n'entre pas dans les totaux.
FIXTURES = (
    {
        'nom': 'trois lignes à 33,33 — remise 5 %',
        'lignes': (('33.33', 'produit', False), ('33.33', 'produit', False),
                   ('33.33', 'produit', False)),
        'pct': '5', 'remise': '5.00', 'ht_net': '94.99',
        'attendus': ('31.67', '31.66', '31.66'),
    },
    {
        'nom': 'sept panneaux + onduleur + pose — remise 5 %',
        'lignes': (('8166.69', 'produit', False), ('12500', 'produit', False),
                   ('3333.33', 'produit', False)),
        'pct': '5', 'remise': '1200.00', 'ht_net': '22800.02',
        'attendus': ('7758.36', '11875.00', '3166.66'),
    },
    {
        'nom': 'remise DE LIGNE déjà appliquée — remise globale 8 %',
        'lignes': (('1425.00', 'produit', False), ('950.00', 'produit', False),
                   ('47.50', 'produit', False)),
        'pct': '8', 'remise': '193.80', 'ht_net': '2228.70',
        'attendus': ('1311.00', '874.00', '43.70'),
    },
    {
        'nom': 'remise nulle — aucun changement',
        'lignes': (('33.33', 'produit', False), ('11.11', 'produit', False)),
        'pct': '0', 'remise': '0.00', 'ht_net': '44.44',
        'attendus': ('33.33', '11.11'),
    },
    {
        'nom': 'section et add-on non activé — aucune part',
        'lignes': (('1000', 'produit', False), ('0', 'section', False),
                   ('500', 'produit', True), ('333.33', 'produit', False)),
        'pct': '15', 'remise': '200.00', 'ht_net': '1133.33',
        'attendus': ('850.00', None, None, '283.33'),
    },
    {
        'nom': 'taux mixtes 10 / 20 — remise 12 %',
        'lignes': (('16000', 'produit', False), ('24000', 'produit', False),
                   ('1234.56', 'produit', False)),
        'pct': '12', 'remise': '4948.15', 'ht_net': '36286.41',
        'attendus': ('14080.00', '21120.00', '1086.41'),
    },
    {
        'nom': 'résidu NÉGATIF — un centime retiré à la première ligne',
        'lignes': (('0.07', 'produit', False), ('0.07', 'produit', False),
                   ('0.07', 'produit', False)),
        'pct': '5', 'remise': '0.01', 'ht_net': '0.20',
        'attendus': ('0.06', '0.07', '0.07'),
    },
    {
        'nom': 'devis complet de dix lignes — remise 5 %',
        'lignes': tuple((v, 'produit', False) for v in (
            '11700', '24000', '15400', '14000', '5250',
            '2010', '1667', '1667', '4000', '1000')),
        'pct': '5', 'remise': '4034.70', 'ht_net': '76659.30',
        'attendus': ('11115.00', '22800.00', '14630.00', '13300.00',
                     '4987.50', '1909.50', '1583.65', '1583.65',
                     '3800.00', '950.00'),
    },
    {
        'nom': 'devis complet de dix lignes — remise 15 %',
        'lignes': tuple((v, 'produit', False) for v in (
            '11700', '24000', '15400', '14000', '5250',
            '2010', '1667', '1667', '4000', '1000')),
        'pct': '15', 'remise': '12104.10', 'ht_net': '68589.90',
        'attendus': ('9945.00', '20400.00', '13090.00', '11900.00',
                     '4462.50', '1708.50', '1416.95', '1416.95',
                     '3400.00', '850.00'),
    },
    {
        'nom': 'une seule ligne — remise 7,5 %',
        'lignes': (('10000', 'produit', False),),
        'pct': '7.5', 'remise': '750.00', 'ht_net': '9250.00',
        'attendus': ('9250.00',),
    },
)


class _Ligne:
    """Une ligne telle que le noyau la lit : un montant et deux drapeaux.

    Les deux drapeaux sont ceux de ``selectors.ligne_compte_dans_totaux`` —
    aucun autre attribut n'est lu par la répartition.
    """

    def __init__(self, total_ht, type_ligne='produit', optionnelle=False):
        self.total_ht = Decimal(str(total_ht))
        self.type_ligne = type_ligne
        self.optionnelle = optionnelle


def _lignes_du_cas(cas):
    return [_Ligne(m, t, o) for m, t, o in cas['lignes']]


class TestRepartitionRemiseParLigne(SimpleTestCase):
    """Le noyau : ``domain.argent.repartir_remise_par_ligne``."""

    def test_la_somme_des_lignes_remisees_est_le_total_net(self):
        """INVARIANT #10 — Σ lignes remisées affichées == Total HT net.

        Sur CHAQUE cas de la table partagée, au centime EXACT : c'est la seule
        chose qui empêche N arrondis indépendants de dériver du total imprimé
        juste sous le tableau.
        """
        from apps.ventes.domain.argent import repartir_remise_par_ligne

        for cas in FIXTURES:
            with self.subTest(cas=cas['nom']):
                parts = repartir_remise_par_ligne(
                    _lignes_du_cas(cas), Decimal(cas['remise']))
                somme = sum((p for p in parts if p is not None), Decimal('0'))
                self.assertEqual(somme, Decimal(cas['ht_net']))

    def test_repartition_identique_a_la_table_partagee_avec_le_miroir_js(self):
        """La répartition, valeur par valeur — la MÊME table que remise.test.mjs."""
        from apps.ventes.domain.argent import repartir_remise_par_ligne

        for cas in FIXTURES:
            with self.subTest(cas=cas['nom']):
                parts = repartir_remise_par_ligne(
                    _lignes_du_cas(cas), Decimal(cas['remise']))
                rendus = [None if p is None else f'{p:.2f}' for p in parts]
                self.assertEqual(rendus, list(cas['attendus']))

    def test_la_remise_de_la_table_est_bien_celle_de_la_chaine_canonique(self):
        """``remise`` = ``arrondi(ht_brut × pct / 100)`` — la table ne peut pas
        épingler un montant de remise que le noyau ne produirait pas."""
        from core.money import quantize_mad

        from apps.ventes.selectors import ligne_compte_dans_totaux

        for cas in FIXTURES:
            with self.subTest(cas=cas['nom']):
                comptees = [li for li in _lignes_du_cas(cas)
                            if ligne_compte_dans_totaux(li)]
                ht_brut = sum((li.total_ht for li in comptees), Decimal('0'))
                pct = Decimal(cas['pct'])
                attendu = (quantize_mad(ht_brut * pct / Decimal('100'))
                           if pct > 0 else Decimal('0'))
                self.assertEqual(attendu, Decimal(cas['remise']))
                self.assertEqual(quantize_mad(ht_brut - attendu),
                                 Decimal(cas['ht_net']))

    def test_remise_nulle_ne_change_aucune_ligne(self):
        """Remise nulle ⇒ chaque ligne rend son propre montant, à l'identique."""
        from apps.ventes.domain.argent import repartir_remise_par_ligne

        lignes = [_Ligne('1500.00'), _Ligne('2333.33'), _Ligne('47.50')]
        self.assertEqual(
            repartir_remise_par_ligne(lignes, Decimal('0')),
            [Decimal('1500.00'), Decimal('2333.33'), Decimal('47.50')])

    def test_les_lignes_hors_totaux_ne_recoivent_aucune_part(self):
        """Section, note et add-on non activé rendent ``None`` à leur position."""
        from apps.ventes.domain.argent import repartir_remise_par_ligne

        lignes = [_Ligne('10', 'note'), _Ligne('5', 'produit', True)]
        self.assertEqual(repartir_remise_par_ligne(lignes, Decimal('1')),
                         [None, None])
        self.assertEqual(repartir_remise_par_ligne([], Decimal('1')), [])

    def test_la_repartition_est_deterministe(self):
        """Deux appels sur les mêmes lignes rendent le MÊME découpage.

        C'est ce qui interdit à l'écran, au PDF et à un re-rendu du même devis
        de se contredire d'un centime.
        """
        from apps.ventes.domain.argent import repartir_remise_par_ligne

        lignes = [_Ligne('33.33'), _Ligne('33.33'), _Ligne('33.33')]
        premier = repartir_remise_par_ligne(lignes, Decimal('5.00'))
        second = repartir_remise_par_ligne(lignes, Decimal('5.00'))
        self.assertEqual(premier, second)

    def test_pu_remise_derive_du_total_reparti(self):
        """Le P.U. affiché vient du TOTAL réparti / quantité, au centime."""
        from apps.ventes.domain.argent import pu_remise

        self.assertEqual(pu_remise(Decimal('100.00'), 3), Decimal('33.33'))
        self.assertEqual(pu_remise(Decimal('7758.36'), 7), Decimal('1108.34'))
        self.assertEqual(pu_remise(Decimal('93.75'), Decimal('2.5')),
                         Decimal('37.50'))
        # Quantité nulle ou absente ⇒ 0, jamais une division par zéro.
        self.assertEqual(pu_remise(Decimal('100.00'), 0), Decimal('0.00'))
        self.assertEqual(pu_remise(None, None), Decimal('0.00'))

    def test_la_remise_ne_touche_aucun_autre_etage_de_la_chaine(self):
        """La répartition ne recalcule NI ht_net NI tva NI ttc — elle répartit.

        Le montant de remise est une ENTRÉE : passer un montant arbitraire
        déplace la somme d'autant, exactement, sans qu'aucun pourcentage ne
        soit ré-appliqué quelque part.
        """
        from apps.ventes.domain.argent import repartir_remise_par_ligne

        lignes = [_Ligne('1000.00'), _Ligne('500.00')]
        for remise in ('0', '1.00', '123.45', '1500.00'):
            with self.subTest(remise=remise):
                parts = repartir_remise_par_ligne(lignes, Decimal(remise))
                self.assertEqual(sum(parts, Decimal('0')),
                                 Decimal('1500.00') - Decimal(remise))


class TestChargeUtileMoteurPdf(TestCase):
    """Les quatre clés « après remise » posées par ``build_quote_data``."""

    LIGNES = [
        ('Onduleur hybride 5kW', '1', '24000'),
        ('Panneau mono 550W', '14', '1100'),
        ('Installation', '1', '4000'),
    ]
    CLES = ('pu_ht_remise', 'total_ht_remise',
            'pu_ttc_remise', 'total_ttc_remise')

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _data(self, remise_globale, reference):
        from apps.ventes.quote_engine.builder import build_quote_data
        devis = make_devis(self.company, self.user, self.client_obj,
                           self.LIGNES, remise_globale=remise_globale,
                           reference=reference)
        return build_quote_data(devis)

    @staticmethod
    def _centimes(valeur):
        return int(round(float(valeur) * 100))

    def test_chaque_ligne_rendue_porte_les_quatre_cles(self):
        data = self._data('5', 'DEV-REM-CLES')
        for cle_liste in ('sans_items', 'avec_items', 'all_items'):
            for item in data[cle_liste]:
                with self.subTest(liste=cle_liste, ligne=item['designation']):
                    for cle in self.CLES:
                        self.assertIn(cle, item)

    def test_la_somme_des_totaux_remises_est_le_ht_net_du_panier(self):
        """Le contrat du builder : par PANIER, Σ total_ht_remise == ht_net.

        Vérifié à 5 % ET à 15 % — deux taux dont les restes ne tombent pas de
        la même façon.
        """
        for pct, ref in (('5', 'DEV-REM-05'), ('15', 'DEV-REM-15')):
            data = self._data(pct, ref)
            for cle_liste, cle_tot in (('sans_items', 'totaux_sans'),
                                       ('avec_items', 'totaux_avec'),
                                       ('all_items', 'totaux_all')):
                with self.subTest(pct=pct, liste=cle_liste):
                    somme = sum(self._centimes(it['total_ht_remise'])
                                for it in data[cle_liste])
                    self.assertEqual(
                        somme, self._centimes(data[cle_tot]['ht_net']))

    def test_sans_remise_les_nouvelles_cles_valent_le_catalogue(self):
        """Remise nulle ⇒ les quatre clés sont les valeurs CATALOGUE, mot pour
        mot : un devis sans remise globale est rendu comme avant."""
        data = self._data('0', 'DEV-REM-ZERO')
        for cle_liste in ('sans_items', 'avec_items', 'all_items'):
            for it in data[cle_liste]:
                with self.subTest(liste=cle_liste, ligne=it['designation']):
                    self.assertEqual(it['pu_ht_remise'], it['prix_unit_ht'])
                    self.assertEqual(it['pu_ttc_remise'], it['prix_unit_ttc'])
                    self.assertEqual(it['total_ht_remise'],
                                     it['prix_unit_ht'] * it['quantite'])
                    self.assertEqual(it['total_ttc_remise'],
                                     it['prix_unit_ttc'] * it['quantite'])

    def test_les_cles_catalogue_gardent_leur_sens(self):
        """``prix_unit_ht``/``prix_unit_ttc`` ne bougent PAS d'un centime avec
        une remise globale : la chaîne « Sous-total HT » les additionne."""
        sans = {it['designation']: it['prix_unit_ht']
                for it in self._data('0', 'DEV-REM-CAT0')['all_items']}
        avec = {it['designation']: it['prix_unit_ht']
                for it in self._data('12', 'DEV-REM-CAT12')['all_items']}
        self.assertEqual(sans, avec)

    def test_la_ligne_remisee_est_bien_sous_le_prix_catalogue(self):
        """Le sens du chiffre : 4 000 HT remisés de 5 % font 3 800 HT."""
        data = self._data('5', 'DEV-REM-SENS')
        pose = next(it for it in data['all_items']
                    if it['designation'] == 'Installation')
        self.assertEqual(self._centimes(pose['prix_unit_ht'] * pose['quantite']),
                         400000)
        self.assertEqual(self._centimes(pose['total_ht_remise']), 380000)


@tag('pdf')  # rendu WeasyPrint complet — lourd → palier release-verify
class TestRenduPdfRemiseParLigne(TestCase):
    """Le document : prix barrés, phrase d'explication, pages inchangées."""

    # Montants ronds : 5 % de n'importe quel sous-ensemble tombe au centime,
    # donc la valeur remisée d'une ligne ne dépend pas du découpage d'options.
    LIGNES = [
        ('Onduleur réseau 10kW', '1', '12000'),
        ('Onduleur hybride 5kW', '1', '24000'),
        ('Panneau mono 550W', '14', '1100'),
        ('Batterie 5 kWh', '1', '14000'),
        ('Structures acier', '14', '375'),
        ('Installation', '1', '4000'),
        ('Transport', '1', '1000'),
    ]

    #: La signature EXACTE de la cellule « catalogue barré » posée par
    #: ``_cellule_prix_remise`` — le prix barré de la CARTE d'option porte,
    #: lui, un ``opacity`` entre les deux propriétés.
    BARRE = 'text-decoration:line-through;white-space:nowrap;">'
    PHRASE = 'appliquée sur chaque ligne'
    #: L'espace fine insécable de la maison, entre le nombre et le
    #: « % » — la même que celle du bloc de totaux.
    FINE = ' '

    def setUp(self):
        self.company = make_company()
        self.user = make_user(self.company)
        self.client_obj = make_client(self.company)

    def _devis(self, remise_globale, reference, **kwargs):
        return make_devis(self.company, self.user, self.client_obj,
                          self.LIGNES, remise_globale=remise_globale,
                          reference=reference, **kwargs)

    def _render(self, devis, pdf_options=None):
        from weasyprint import HTML

        from apps.ventes.quote_engine import generate_devis_premium as G
        from apps.ventes.quote_engine.builder import build_quote_data

        data = build_quote_data(devis, pdf_options)
        cap = {}
        orig = G._render_pdf_weasyprint
        G._render_pdf_weasyprint = lambda html, out: cap.update(html=html)
        try:
            G.generate_premium_pdf(data, '/tmp/_remise_test.pdf')
        finally:
            G._render_pdf_weasyprint = orig
        return cap['html'], HTML(string=cap['html']).render()

    def test_le_detail_trois_pages_montre_le_prix_barre_et_le_prix_remise(self):
        devis = self._devis('5', 'DEV-REM-P3', etude_params=DEUX_OPTIONS)
        html, doc = self._render(devis)
        self.assertEqual(len(doc.pages), 3)
        self.assertIn(self.BARRE, html)
        # 4 000,00 barré, 3 800,00 en chiffre principal, dans la MÊME cellule.
        self.assertRegex(html, re.compile(
            re.escape(self.BARRE) + r'4 000,00</span>\s*'
            r'<span style="white-space:nowrap;">3 800,00</span>'))
        # La chaîne de totaux est intacte : Sous-total CATALOGUE → Remise → net.
        self.assertIn('Sous-total HT', html)
        self.assertIn('Remise (5', html)
        self.assertIn('Total TTC', html)

    def test_le_une_page_montre_le_prix_barre_et_le_prix_remise(self):
        devis = self._devis('5', 'DEV-REM-1P')
        html, doc = self._render(devis, {'pdf_mode': 'onepage'})
        self.assertEqual(len(doc.pages), 1)
        self.assertIn(self.BARRE, html)
        self.assertRegex(html, re.compile(
            re.escape(self.BARRE) + r'4 000,00</span>\s*'
            r'<span style="white-space:nowrap;">3 800,00</span>'))
        self.assertIn('Sous-total HT', html)
        self.assertIn('Remise (5', html)

    def test_la_phrase_explique_le_tableau_quand_il_y_a_une_remise(self):
        """UNE phrase, sur les deux formats — et aucun nombre de plus qu'elle."""
        devis = self._devis('5', 'DEV-REM-NOTE', etude_params=DEUX_OPTIONS)
        for opts in (None, {'pdf_mode': 'onepage'}):
            with self.subTest(opts=opts):
                html, _ = self._render(devis, opts)
                self.assertIn(self.PHRASE, html)
                self.assertIn('Remise de 5' + self.FINE + '%', html)

    def test_sans_remise_ni_prix_barre_ni_phrase(self):
        """Remise nulle ⇒ le document est celui d'avant : aucun prix barré de
        ligne, aucune phrase ajoutée."""
        devis = self._devis('0', 'DEV-REM-NULLE', etude_params=DEUX_OPTIONS)
        for opts in (None, {'pdf_mode': 'onepage'}):
            with self.subTest(opts=opts):
                html, _ = self._render(devis, opts)
                self.assertNotIn(self.BARRE, html)
                self.assertNotIn(self.PHRASE, html)

    def test_les_pages_ne_bougent_pas_avec_une_remise(self):
        """3 pages, 4 avec étude, 1 en une-page — remise ou pas.

        Les deux nombres tiennent dans la MÊME cellule : aucune ligne de
        tableau n'est ajoutée, donc la pagination ne peut pas suivre la remise.
        """
        etude = {
            **DEUX_OPTIONS,
            'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
            'taux_autoconso': 100, 'taux_couverture': 10.4,
            'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
            'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
        }
        for pct, ref in (('0', 'DEV-REM-PG0'), ('5', 'DEV-REM-PG5'),
                         ('17.5', 'DEV-REM-PG17')):
            devis = self._devis(pct, ref, etude_params=etude)
            devis.mode_installation = 'industriel'
            devis.save(update_fields=['mode_installation'])
            with self.subTest(pct=pct):
                _, doc = self._render(devis)
                self.assertEqual(len(doc.pages), 3)
                _, doc_etude = self._render(devis, {'include_etude': True})
                self.assertEqual(len(doc_etude.pages), 4)
                _, doc_1p = self._render(devis, {'pdf_mode': 'onepage'})
                self.assertEqual(len(doc_1p.pages), 1)

    def test_le_prix_achat_ne_fuite_jamais_avec_une_remise(self):
        """Règle #4 — ``Produit.prix_achat`` reste GÉNÉRATEUR-ONLY, y compris
        sur un document remisé (la remise touche des prix : c'est exactement le
        moment où une marge peut fuiter)."""
        devis = self._devis('5', 'DEV-REM-ACHAT', etude_params=DEUX_OPTIONS)
        for ligne in devis.lignes.all():
            ligne.produit.prix_achat = Decimal('9876.54')
            ligne.produit.save(update_fields=['prix_achat'])
        for opts in ({'pdf_mode': 'onepage'}, None):
            with self.subTest(opts=opts):
                html, _ = self._render(devis, opts)
                for marqueur in ('9876', '9 876', '9 876',
                                 '9&#8239;876', 'achat'):
                    self.assertNotIn(marqueur, html.lower())
