"""QA-FIGURES — un même chiffre est IDENTIQUE sur toutes les surfaces qui le montrent.

HISTOIRE. 12 des 30 bugs « chiffre faux » de l'audit QA
(docs/decisions/COUV-HOR/audit-qa-complet.md) étaient le MÊME chiffre affiché
différemment entre l'écran, le PDF, la page publique et l'API — chacun corrigé
avec SON test écrit à la main pour SA paire de chiffres (test_pv86,
test_qjr115, test_err_qah_total_divergence_creation…). Ce module est la
vérification GÉNÉRIQUE qui les remplace : chaque chiffre client porte un
marqueur ``data-figure`` (vocabulaire unique : ``quote_engine/figures.py``),
et UNE comparaison confronte toutes les surfaces. Tout chiffre marqué demain
est couvert sans une ligne de plus ici.

LES SURFACES, pour un devis réel construit en base :
  * ``pdf_full`` / ``pdf_onepage`` / ``pdf_etude`` — le HTML EXACT que le
    moteur envoie à WeasyPrint, choisi par le MÊME registre de renderers que
    ``builder.generate_premium_devis_pdf`` (règle #4 : on relit le seul chemin
    /proposal, sans WeasyPrint ni MinIO — rien n'est rendu autrement) ;
  * ``proposition`` — ``GET /api/django/public/proposal/<token>/data/``, la
    charge utile que rend la page publique (apps/web) ;
  * ``api_devis`` — ``GET /api/django/ventes/devis/<id>/``, ce que lisent la
    liste et l'écran interne.

ATOT29 — L'ARITHMÉTIQUE INTERNE de chaque surface : la parité confronte un
chiffre à lui-même d'une surface à l'autre (deux surfaces qui impriment la même
chaîne fausse passeraient) ; ``figures.verifier_chaine`` relit CHAQUE surface
et vérifie que Sous-total − Remise − Arrondi = Total HT et Total HT + Σ TVA
par taux = TTC (tolérance de résolution). Scénarios dédiés : taux mixtes
10/20, commercial et industriel remisés (``FiguresChaineInterneTests``).

DEUX GARDES en plus de la parité :
  * chaque clé de ``FIGURE_KEYS`` apparaît au moins une fois dans le corpus
    de documents rendus (un marqueur ne disparaît pas en silence) ;
  * aucun marqueur n'utilise une clé non déclarée.

KNOWN_MISMATCHES — écarts RÉELS constatés et pas encore corrigés. Cette liste
ne peut que RÉTRÉCIR : une entrée qui ne se reproduit plus fait échouer le test
(« retirez-la »), et on n'en ajoute une qu'avec un repro et une tâche
ERR-* ouverte. Ne jamais affaiblir une tolérance pour faire passer un écart.

Run:
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_figures_parite -v 2
"""
import importlib
import itertools
import json
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.ventes.quote_engine import figures
from apps.ventes.quote_engine.figures import (
    FIGURE_KEYS, cle_de, cles_inconnues, compare_surfaces, extract_figures,
    figures_depuis_devis_api, figures_depuis_proposition,
    identites_comparees, options_de_chaine, verifier_chaine,
)

User = get_user_model()

_seq = itertools.count(1)

#: ``(cas, identité)`` des écarts réels connus — NE PEUT QUE RÉTRÉCIR.
#: Format d'une entrée : ``("residentiel_deux_options", "total_ttc@avec")``
#: suivi d'un commentaire (repro + tâche ERR-* ouverte).
# (ERR-QAH-FIG-KPI-ECO-RESEAU-SEUL corrigée : la vignette KPI de la couverture
# lit l'économie de l'option ``eco_option`` — test_residentiel_reseau_seul.)
KNOWN_MISMATCHES: set[tuple[str, str]] = set()


# ── Compositions (calquées sur test_quote_engine_snapshot / test_pv86) ───────
FULL_LINES = [
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
RESEAU_LINES = [
    ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Structures acier', '14', '375'),
    ('Installation', '1', '4000'),
]
BATTERIE_LINES = [
    ('Onduleur hybride Deye 10kW Triphasé', '1', '24000'),
    ('Batterie Dyness 10 kWh', '1', '14000'),
    ('Panneau Canadien Solar 710W', '14', '1100'),
    ('Structures acier', '14', '375'),
    ('Installation', '1', '4000'),
]
#: ATOT29 — taux MIXTES : panneaux à 10 %, le reste (onduleurs, batterie,
#: pose) au taux du devis (20 %). 4e élément = ``LigneDevis.taux_tva``.
TAUX_MIXTES_LINES = [
    (desig, qte, pu, '10' if desig.startswith('Panneau') else '20')
    for desig, qte, pu in FULL_LINES
]
AGRICOLE_LINES = [
    ('Pompe immergée OSP 30/8 10 CV', '1', '9166.67'),
    ('VARIATEUR VEICHI SI23 7.5KW 380V', '1', '3333.33'),
    ('Panneau mono 710W', '15', '1166.67'),
    ('Installation', '1', '4000'),
]

#: Douze factures RÉELLES saisonnières (MAD) — l'ancrage que sème le devis
#: auto résidentiel (``etude_params.factures_mensuelles_reelles``).
FACTURES = [900, 850, 800, 750, 800, 950, 1100, 1150, 1000, 850, 800, 900]
ANCRAGE = {'factures_mensuelles_reelles': FACTURES, 'distributeur': 'onee',
           'ville': 'casablanca'}
DEUX_OPTIONS = {'scenario': 'Les deux (Sans + Avec)'}
ETUDE = {
    'kwc': 9.94, 'production_annuelle': 12486, 'conso_annuelle': 120000,
    'taux_autoconso': 100, 'taux_couverture': 10.4,
    'economies_annuelles': 21851, 'payback': 3.0, 'prix_kwc': 6543,
    'prod_mensuelle': [1040] * 12, 'conso_mensuelle': [10000] * 12,
}
AGRICOLE_ETUDE = {
    'pompe_cv': '10', 'pompe_kw': 7.5,
    'pompe_nom': 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)',
    'type_pompe': 'immergee', 'alim': 'tri',
    'hmt_m': '60', 'debit_souhaite_m3h': '30',
    'debit_hmt_m3h': 30, 'heures_pompage': 7, 'm3_jour': 210,
    'champ_kwc': 17.5,
}

#: CIQ307 — la sortie du moteur C&I telle que le rafraîchisseur la stocke
#: (``etude_params.etude_ci``, contrat partagé ``etude_ci_preview.json``) :
#: le PDF ET /proposition lisent ``synthese_ci`` sur elle.
_ETUDE_CI = json.loads(
    (Path(__file__).resolve().parents[1] / 'contract_samples'
     / 'etude_ci_preview.json').read_text(encoding='utf-8'))
ETUDE_CI_BT = {'etude_ci': _ETUDE_CI['exemple'],
               'tarif_declare': {'contrat': 'bt_patente'}}
ETUDE_CI_MT = {'etude_ci': _ETUDE_CI['exemple_industriel_mt']}

FORMATS = {
    'full': {'pdf_mode': 'full'},
    'onepage': {'pdf_mode': 'onepage'},
    'etude': {'pdf_mode': 'full', 'include_etude': True},
}

#: La MATRICE. ``requis`` : identités qui DOIVENT être confrontées au moins
#: une fois (``cle@*`` = cette clé, n'importe quelle option ; ``cle*`` = cette
#: clé, avec ou sans option) — sans quoi un marqueur disparu ferait passer le
#: test pour rien.
CAS = {
    'residentiel_deux_options': dict(
        lignes=FULL_LINES, etude_params={**DEUX_OPTIONS, **ANCRAGE},
        formats=('full', 'onepage'),
        requis=('total_ttc@sans', 'total_ttc@avec', 'puissance_kwc',
                'production_annuelle_kwh', 'total_affiche')),
    'residentiel_deux_options_etude': dict(
        lignes=FULL_LINES, etude_params={**DEUX_OPTIONS, **ANCRAGE, **ETUDE},
        formats=('full', 'onepage', 'etude'),
        requis=('total_ttc@sans', 'total_ttc@avec', 'puissance_kwc')),
    'residentiel_remise': dict(
        lignes=FULL_LINES, etude_params={**DEUX_OPTIONS, **ANCRAGE},
        remise='5', formats=('full', 'onepage'),
        requis=('total_ttc@sans', 'total_ttc@avec', 'remise@*',
                'total_ht@*')),
    'residentiel_reseau_seul': dict(
        lignes=RESEAU_LINES, etude_params=dict(ANCRAGE),
        formats=('full', 'onepage'),
        requis=('total_ttc*', 'puissance_kwc')),
    'residentiel_avec_batterie': dict(
        lignes=BATTERIE_LINES,
        etude_params={'scenario': 'Avec batterie', **ANCRAGE},
        formats=('full', 'onepage'),
        requis=('total_ttc*', 'puissance_kwc')),
    'agricole_pompage': dict(
        lignes=AGRICOLE_LINES, mode='agricole',
        etude_params=dict(AGRICOLE_ETUDE), formats=('full', 'onepage'),
        requis=('total_ttc*', 'pompe_hmt_m', 'pompe_debit_m3h',
                'pompe_volume_m3_jour')),
    # CIQ307 — production, taux, économie et payback : ceux de
    # ``synthese_ci`` (moteur C&I) sur le PDF ET la proposition.
    # CIQ210 (complément) — le UNE-PAGE aussi (``chiffres_cles``). Les clés
    # d'étude JS (``ETUDE``) restent dans la fixture : plus personne ne les lit.
    'industriel': dict(
        lignes=FULL_LINES, mode='industriel',
        etude_params={**DEUX_OPTIONS, **ETUDE, **ETUDE_CI_MT},
        formats=('full', 'onepage'),
        requis=('puissance_kwc', 'total_affiche', 'couverture_pct',
                'autoconsommation_pct', 'production_annuelle_kwh',
                'economie_annuelle*', 'payback_ans*')),
    'commercial': dict(
        lignes=FULL_LINES, mode='commercial',
        etude_params={**DEUX_OPTIONS, **ETUDE, **ETUDE_CI_BT,
                      'categorie_commerciale': 'hotel'},
        formats=('full', 'onepage'),
        requis=('puissance_kwc', 'total_affiche', 'total_ttc*',
                'couverture_pct', 'autoconsommation_pct',
                'economie_annuelle*', 'payback_ans*')),
    # Le une-page C&I (moteur legacy) sans étude moteur : puissance et total.
    'industriel_une_page': dict(
        lignes=FULL_LINES, mode='industriel',
        etude_params={**DEUX_OPTIONS, **ETUDE}, formats=('full', 'onepage'),
        requis=('puissance_kwc', 'total_affiche')),
    # ATOT29 — chaîne à DEUX taux (10 % panneaux, 20 % le reste) : la TVA est
    # imprimée par taux, et Σ TVA par taux doit refermer le TTC.
    'residentiel_taux_mixtes': dict(
        lignes=TAUX_MIXTES_LINES, etude_params={**DEUX_OPTIONS, **ANCRAGE},
        formats=('full', 'onepage'),
        requis=('total_ttc@sans', 'total_ttc@avec', 'tva_taux:10@*',
                'tva_taux:20@*')),
    # ATOT29 — C&I REMISÉS : la remise (et l'arrondi) entrent dans la chaîne
    # HT des gabarits commercial / industriel.
    'commercial_remise': dict(
        lignes=FULL_LINES, mode='commercial', remise='5',
        etude_params={**DEUX_OPTIONS, **ETUDE, **ETUDE_CI_BT,
                      'categorie_commerciale': 'hotel'},
        formats=('full', 'onepage'),
        requis=('total_ttc*', 'total_ht*')),
    'industriel_remise': dict(
        lignes=FULL_LINES, mode='industriel', remise='5',
        etude_params={**DEUX_OPTIONS, **ETUDE, **ETUDE_CI_MT},
        formats=('full', 'onepage'),
        requis=('total_ttc*', 'total_ht*')),
}


def rendre_html(devis, pdf_options):
    """``(marché, html)`` — le HTML EXACT que ``generate_premium_devis_pdf``
    enverrait à WeasyPrint pour ces options, sans WeasyPrint ni MinIO.

    Miroir LECTURE SEULE du dispatch du builder (même registre, même mode
    normalisé, même échappement des textes client, même repli legacy) : aucun
    chemin de rendu nouveau, aucun statut touché (règle #4)."""
    from apps.ventes.quote_engine import clean_pdf_options
    from apps.ventes.quote_engine import generate_devis_premium as legacy
    from apps.ventes.quote_engine.builder import (
        build_quote_data, echapper_textes_client, registre_renderers,
    )

    opts = clean_pdf_options(dict(pdf_options))
    data = build_quote_data(devis, dict(opts))
    data_rendu = echapper_textes_client(data)
    opts_dispatch = dict(opts)
    opts_dispatch['pdf_mode'] = (
        data.get('pdf_mode') or opts_dispatch.get('pdf_mode') or 'full')
    for marche, renderer, sert in registre_renderers():
        if not sert(devis, opts_dispatch):
            continue
        try:
            d = renderer._augment(data_rendu)
        except renderer.Unsupported:
            break  # repli legacy NOMMÉ en production — même chose ici
        paquet = renderer.__name__.rsplit('.', 1)[0]
        render = importlib.import_module(f'{paquet}.render')
        return marche, render.build_html(d)
    return 'legacy', legacy.render_html_for(data)


def _requis_satisfait(motif, comparees):
    if motif.endswith('@*'):
        cle = motif[:-2]
        return any(i.startswith(cle + '@') for i in comparees)
    if motif.endswith('*'):
        cle = motif[:-1]
        return any(cle_de(i) == cle for i in comparees)
    return motif in comparees


class _DevisReelMixin:
    """Un devis RÉEL en base et ses surfaces (PDF /proposal, proposition
    publique, API) — partagé par la parité et la chaîne interne (ATOT29)."""

    def setUp(self):
        from authentication.models import Company
        from apps.crm.models import Client
        n = next(_seq)
        self.company, _ = Company.objects.get_or_create(
            slug=f'qa-figures-co-{n}', defaults={'nom': f'QA Figures {n}'})
        self.user = User.objects.create_user(
            username=f'qa-figures-{n}', password='x',
            role_legacy='responsable', company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.client_obj = Client.objects.create(
            company=self.company, nom='Alaoui', prenom='Karim',
            email=f'karim-figures-{n}@example.com',
            telephone='+212600000741', adresse='Hay Riad, Rabat')

    def _devis(self, cas, spec):
        from apps.stock.models import Produit
        from apps.ventes.models import Devis, LigneDevis
        ref = f'DEV-QAFIG-{next(_seq):04d}'
        devis = Devis.objects.create(
            company=self.company, reference=ref, client=self.client_obj,
            statut='envoye', taux_tva=Decimal('20.00'),
            remise_globale=Decimal(spec.get('remise', '0')),
            created_by=self.user,
            mode_installation=spec.get('mode', 'residentiel'),
            etude_params=spec.get('etude_params'))
        for i, ligne in enumerate(spec['lignes']):
            desig, qte, pu = ligne[:3]
            # ATOT29 — 4e élément optionnel : le taux de TVA de la LIGNE.
            taux = Decimal(ligne[3]) if len(ligne) > 3 else None
            produit = Produit.objects.create(
                company=self.company, nom=desig, sku=f'{ref[-8:]}-{i}',
                prix_vente=Decimal(pu), prix_achat=Decimal('1'),
                quantite_stock=100)
            LigneDevis.objects.create(
                devis=devis, produit=produit, designation=desig,
                quantite=Decimal(qte), prix_unitaire=Decimal(pu),
                remise=Decimal('0'), ordre=i, taux_tva=taux)
        return devis

    def _surfaces(self, devis, spec):
        from apps.ventes.models import ShareLink
        surfaces, marches = {}, {}
        for fmt in spec['formats']:
            marche, html = rendre_html(devis, FORMATS[fmt])
            self.assertNotIn('prix_achat', html)
            marches[f'pdf_{fmt}'] = marche
            surfaces[f'pdf_{fmt}'] = extract_figures(html)
        link = ShareLink.objects.create(company=self.company, devis=devis)
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        surfaces['proposition'] = figures_depuis_proposition(resp.json())
        detail = self.api.get(f'/api/django/ventes/devis/{devis.id}/')
        self.assertEqual(detail.status_code, 200, detail.content[:300])
        surfaces['api_devis'] = figures_depuis_devis_api(detail.json())
        return surfaces, marches

    def _chaines_fausses(self, surfaces):
        """ATOT29 — ``[(surface, anomalie)]`` : chaque surface, chaque option
        imprimée, relue par ``verifier_chaine``."""
        return [(nom, anomalie)
                for nom, figs in surfaces.items()
                for option in options_de_chaine(figs)
                for anomalie in verifier_chaine(figs, option)]


class FiguresPariteSurfacesTests(_DevisReelMixin, TestCase):
    """La matrice : chaque devis réel, toutes ses surfaces, zéro écart."""

    def _verifier(self, cas):
        spec = CAS[cas]
        devis = self._devis(cas, spec)
        surfaces, marches = self._surfaces(devis, spec)

        inconnues = sorted({i for f in surfaces.values()
                            for i in cles_inconnues(f)})
        self.assertEqual(inconnues, [], f'{cas} : clés data-figure non '
                         'déclarées dans FIGURE_KEYS')

        ecarts = compare_surfaces(surfaces)
        nouveaux = [e for e in ecarts
                    if (cas, e.identite) not in KNOWN_MISMATCHES]
        connus_vus = {(cas, e.identite) for e in ecarts}
        perimes = sorted(k for k in KNOWN_MISMATCHES
                         if k[0] == cas and k not in connus_vus)
        self.assertEqual(
            nouveaux, [],
            f'\n{cas} (renderers : {marches}) — le même chiffre diffère '
            'd\'une surface à l\'autre :\n  '
            + '\n  '.join(str(e) for e in nouveaux)
            + '\nC\'est un VRAI bug client : ne pas élargir la tolérance. '
            'Si la correction attend une tâche ERR-*, ajouter '
            + ', '.join(repr((cas, e.identite)) for e in nouveaux)
            + ' à KNOWN_MISMATCHES avec son repro.')
        self.assertEqual(
            perimes, [],
            f'{cas} : écart(s) connu(s) qui ne se reproduisent plus — '
            'retirez-les de KNOWN_MISMATCHES (la liste ne fait que rétrécir).')

        comparees = identites_comparees(surfaces)
        manquants = [m for m in spec['requis']
                     if not _requis_satisfait(m, comparees)]
        self.assertEqual(
            manquants, [],
            f'{cas} (renderers : {marches}) : ces chiffres ne sont confrontés '
            f'sur aucune paire de surfaces — un marqueur a disparu. '
            f'Identités confrontées : {sorted(comparees)}')

        # ATOT29 — et la chaîne de CHAQUE surface s'additionne.
        fausses = self._chaines_fausses(surfaces)
        self.assertEqual(
            fausses, [],
            f'\n{cas} (renderers : {marches}) — une chaîne de totaux ne '
            's\'additionne pas :\n  '
            + '\n  '.join(f'{nom} : {a}' for nom, a in fausses))

    def test_residentiel_deux_options(self):
        self._verifier('residentiel_deux_options')

    def test_residentiel_deux_options_avec_etude(self):
        self._verifier('residentiel_deux_options_etude')

    def test_residentiel_avec_remise(self):
        self._verifier('residentiel_remise')

    def test_residentiel_reseau_seul(self):
        self._verifier('residentiel_reseau_seul')

    def test_residentiel_avec_batterie(self):
        self._verifier('residentiel_avec_batterie')

    def test_agricole_pompage(self):
        self._verifier('agricole_pompage')

    def test_agricole_pompage_proposition_sans_economie_residentielle(self):
        """AGR300 — la surface proposition d'un devis agricole ne porte plus
        ``economie_annuelle`` ni ``payback_ans`` (économies résidentielles au
        tarif ONEE que le PDF du même devis n'imprime pas)."""
        spec = CAS['agricole_pompage']
        surfaces, _ = self._surfaces(self._devis('agricole_pompage', spec),
                                     spec)
        cles = [k.split('@')[0] for k in surfaces['proposition']]
        self.assertNotIn('economie_annuelle', cles)
        self.assertNotIn('payback_ans', cles)

    def test_industriel(self):
        self._verifier('industriel')

    def test_industriel_une_page(self):
        self._verifier('industriel_une_page')

    def test_commercial(self):
        self._verifier('commercial')

    def test_residentiel_taux_mixtes(self):
        self._verifier('residentiel_taux_mixtes')

    def test_commercial_remise(self):
        self._verifier('commercial_remise')

    def test_industriel_remise(self):
        self._verifier('industriel_remise')

    def test_acal_production_recalee_decimale_haute(self):
        """ACAL102 (C-ACAL-113) — la production imprimée (PDF /proposal et
        proposition publique) est celle du calepinage RECALÉE sur les lignes
        (8 × 715 W = 5,72 kWc pour un calepinage modélisé à 5,76 kWc), quelle
        que soit la décimale : la provenance est la marque
        ``production_source``, plus l'égalité ``int(round())`` qui ratait
        8843,66 stockée tronquée à 8843."""
        from apps.ventes.models import Devis
        lignes = [
            ('Onduleur réseau Huawei 10kW Triphasé', '1', '11700'),
            ('Panneau Canadien Solar 715W', '8', '1100'),
            ('Structures acier', '8', '375'),
            ('Installation', '1', '4000'),
        ]
        for annuel in (8843.49, 8843.5, 8843.66):
            with self.subTest(annuel=annuel):
                spec = dict(
                    lignes=lignes, formats=('full', 'onepage'),
                    etude_params={**ANCRAGE,
                                  # Valeur STOCKÉE tronquée (devis réels).
                                  'production_annuelle': int(annuel),
                                  'production_source': 'calepinage'})
                devis = self._devis('acal_production', spec)
                Devis.objects.filter(pk=devis.pk).update(roof_layout={
                    'scenario': 'reseau', 'panelWatt': 720,
                    'result': {'panels': 8, 'kwc': 5.76,
                               'annualKwh': annuel}})
                devis.refresh_from_db()
                attendu = Decimal(int(round(annuel * 5.72 / 5.76)))
                surfaces, marches = self._surfaces(devis, spec)
                lues = {
                    surface: [m.valeur for ident, mesures in figs.items()
                              if cle_de(ident) == 'production_annuelle_kwh'
                              for m in mesures]
                    for surface, figs in surfaces.items()
                    if surface in ('pdf_full', 'pdf_onepage', 'proposition')}
                self.assertTrue(lues['proposition'], (marches, surfaces))
                for surface, valeurs in lues.items():
                    for valeur in valeurs:
                        self.assertEqual(valeur, attendu,
                                         (surface, annuel, marches))
                self.assertEqual(compare_surfaces(surfaces), [])

    def test_ci_proposition_sans_economie_residentielle(self):
        """CIQ300 — la surface proposition d'un devis industriel ou commercial
        ne porte plus ``economie_annuelle`` ni ``payback_ans`` (modèle
        résidentiel/BT ou étude JS). CIQ307 : l'argent C&I vient de
        ``synthese_ci`` — un devis SANS sortie du moteur C&I n'en a aucun
        (les cas « moteur » sont confrontés au PDF par ``_verifier``)."""
        for cas in ('industriel_une_page',):
            with self.subTest(cas=cas):
                spec = CAS[cas]
                surfaces, _ = self._surfaces(self._devis(cas, spec), spec)
                cles = [k.split('@')[0] for k in surfaces['proposition']]
                self.assertNotIn('economie_annuelle', cles)
                self.assertNotIn('payback_ans', cles)


class FiguresChaineInterneTests(_DevisReelMixin, TestCase):
    """ATOT29 — l'oracle d'arithmétique intra-surface ATTRAPE une chaîne qui
    ne s'additionne pas, sur la charge utile RÉELLE (aucun mock)."""

    def _proposition(self, cas):
        from apps.ventes.models import ShareLink
        devis = self._devis(cas, CAS[cas])
        link = ShareLink.objects.create(company=self.company, devis=devis)
        resp = APIClient().get(
            f'/api/django/public/proposal/{link.token}/data/')
        self.assertEqual(resp.status_code, 200, resp.content[:300])
        return resp.json()

    def test_surface_sans_arrondi_detectee(self):
        payload = self._proposition('residentiel_deux_options')
        figs = figures_depuis_proposition(payload)
        # Pré-condition : l'arrondi commercial de l'option est NON nul (sinon
        # l'omettre ne changerait rien), et la chaîne réelle s'additionne.
        self.assertIn('arrondi@sans', figs)
        self.assertEqual(verifier_chaine(figs, 'sans'), [])
        copie = json.loads(json.dumps(payload))
        for totaux in ((copie.get('option_totals') or {}).get('sans_batterie'),
                       (copie.get('quote') or {}).get('totaux_sans')):
            if isinstance(totaux, dict):
                totaux.pop('arrondi', None)
        anomalies = verifier_chaine(figures_depuis_proposition(copie), 'sans')
        self.assertEqual(len(anomalies), 1, anomalies)
        self.assertIn('arrondi', anomalies[0])
        self.assertIn('chaîne HT', anomalies[0])

    def test_taux_manquant_detecte(self):
        payload = self._proposition('residentiel_taux_mixtes')
        figs = figures_depuis_proposition(payload)
        self.assertIn('tva_taux:10@avec', figs)
        self.assertIn('tva_taux:20@avec', figs)
        self.assertEqual(verifier_chaine(figs, 'avec'), [])
        copie = json.loads(json.dumps(payload))
        for totaux in ((copie.get('option_totals') or {}).get('avec_batterie'),
                       (copie.get('quote') or {}).get('totaux_avec')):
            if isinstance(totaux, dict):
                totaux['tva_par_taux'] = [
                    b for b in totaux.get('tva_par_taux') or []
                    if float(b.get('taux')) != 10]
        anomalies = verifier_chaine(figures_depuis_proposition(copie), 'avec')
        self.assertTrue(any('chaîne TTC' in a for a in anomalies), anomalies)


# ── Gardes du vocabulaire (aucune BD) ────────────────────────────────────────

def _corpus():
    """Documents rendus sur les données PURES des moteurs (aucune BD) :
    ensemble, ils doivent exercer TOUTES les clés du vocabulaire."""
    from apps.ventes.quote_engine.commercial import (
        render as c_render, renderer as c_renderer, sample_data as c_sample)
    from apps.ventes.quote_engine.industriel import (
        render as i_render, renderer as i_renderer, sample_data as i_sample)
    from apps.ventes.quote_engine.residential import sample_data

    from ._moteur_fixtures import html_legacy, html_onepage, html_residentiel

    base = sample_data.build('deux')
    ts = dict(base['totaux_sans'])
    ta = dict(base['totaux_avec'])
    # Une remise sur la chaîne résidentielle : fait sortir les lignes
    # « Remise » et « Total HT » (présence seulement — la parité se prouve
    # sur la matrice en base, pas sur ce décor).
    # ARRONDI-100 — et un « Arrondi commercial » (présence seulement).
    remise = {'totaux_sans': {**ts, 'remise': 100, 'arrondi': 0.27,
                              'ht_net': ts['ht_brut'] - 100.27},
              'totaux_avec': {**ta, 'remise': 100, 'arrondi': 0.27,
                              'ht_net': ta['ht_brut'] - 100.27}}
    return {
        'residentiel_full': html_residentiel('deux', **remise),
        'legacy_etude': html_legacy('deux', include_etude=True, etude=dict(ETUDE)),
        'legacy_onepage': html_onepage(),
        'legacy_onepage_pompage': html_onepage(etude=dict(AGRICOLE_ETUDE)),
        'industriel_full': i_render.build_html(
            i_renderer._augment(i_sample.build())),
        # CIQ342 — la page finance avec l'argent SERVI (contrat
        # ``economie_ci.json``) : TRI et cumul à 25 ans marqués.
        'industriel_argent': i_render.build_html(i_renderer._augment(
            dict(i_sample.build(), economie_ci=i_sample.economie_ci()))),
        # CIQ129 — les taux C&I viennent du seul moteur (``etude_ci`` servi
        # par ``synthese_ci``) : plus aucune clé d'étude écran ne les marque.
        'industriel_etude_ci': i_render.build_html(i_renderer._augment(
            dict(i_sample.build(), mode_installation='industriel',
                 etude={**i_sample.build()['etude'], **ETUDE_CI_MT}))),
        'commercial_full': c_render.build_html(
            c_renderer._augment(c_sample.build())),
    }


class FiguresVocabulaireTests(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.corpus = {nom: extract_figures(html)
                      for nom, html in _corpus().items()}

    def test_chaque_cle_declaree_est_marquee_quelque_part(self):
        vues = {cle_de(i) for f in self.corpus.values() for i in f}
        absentes = sorted(set(FIGURE_KEYS) - vues)
        self.assertEqual(
            absentes, [],
            'clé(s) de FIGURE_KEYS marquée(s) sur AUCUN document — le '
            'marqueur a disparu (ou la clé est morte : la retirer).')

    def test_aucun_marqueur_hors_vocabulaire(self):
        for nom, figs in self.corpus.items():
            with self.subTest(document=nom):
                self.assertEqual(cles_inconnues(figs), [])

    def test_aucun_marqueur_illisible(self):
        for nom, figs in self.corpus.items():
            for ident, mesures in figs.items():
                for m in mesures:
                    with self.subTest(document=nom, identite=ident):
                        self.assertIsNotNone(
                            m.valeur, f'{ident} : texte sans nombre {m.texte!r}')

    def test_le_document_residentiel_marque_la_couche_economique(self):
        """Le cœur de l'incident COUV-HOR : donut, −N %, facture actuelle,
        production — marqués sur la couverture du PDF résidentiel."""
        figs = self.corpus['residentiel_full']
        cles = {cle_de(i) for i in figs}
        for cle in ('couverture_pct', 'reduction_facture_pct',
                    'facture_mensuelle_avant', 'facture_annuelle_avant',
                    'production_annuelle_kwh', 'puissance_kwc',
                    'total_ttc', 'economie_annuelle', 'payback_ans'):
            self.assertIn(cle, cles)


class FiguresNormaliseurTests(SimpleTestCase):
    """Le lecteur de nombres à la française et le comparateur."""

    def test_nombres_francais(self):
        cas = {
            '117 391,16 MAD': ('117391.16', '0.01'),
            '117 391,16 MAD': ('117391.16', '0.01'),
            '37 %': ('37', '1'),
            '8,5 kWc': ('8.5', '0.1'),
            '4.7': ('4.7', '0.1'),
            '− 1 200 MAD': ('-1200', '1'),
            '&#8776; 1&#8239;234 m&#179;': ('1234', '1'),
        }
        for texte, (valeur, resolution) in cas.items():
            with self.subTest(texte=texte):
                self.assertEqual(figures.normaliser(texte),
                                 (Decimal(valeur), Decimal(resolution)))
        self.assertEqual(figures.normaliser('—')[0], None)
        self.assertEqual(figures.normaliser(12486.0)[1], Decimal(0))

    def test_extraction_attribut_et_ancre(self):
        html = ('<div><b data-figure="total_ttc" data-figure-option="avec">'
                '94 832 <span>MAD</span></b>'
                + figures.ancre('total_ttc', '94 832,40 MAD', 'avec')
                + figures.ancre('tva_taux', '1 000,00', 'sans', 20.0)
                + '<img data-figure="couverture_pct" '
                'data-figure-option="avec" data-figure-value="37"></div>')
        f = extract_figures(html)
        self.assertEqual([m.valeur for m in f['total_ttc@avec']],
                         [Decimal('94832'), Decimal('94832.40')])
        self.assertEqual(f['tva_taux:20@sans'][0].valeur, Decimal('1000.00'))
        self.assertEqual(f['couverture_pct@avec'][0].valeur, Decimal('37'))

    def test_tolerances(self):
        m = figures.mesure
        # Dirham entier vs centime exact : 0,40 d'écart, dans l'arrondi.
        self.assertEqual(compare_surfaces({
            'pdf': {'total_ttc@avec': [m('94 832')]},
            'api': {'total_ttc@avec': [m(94832.4)]}}), [])
        # Deux affichages entiers qui diffèrent d'un dirham : VRAI écart
        # (troncature contre arrondi — le bug QJR53).
        self.assertEqual(len(compare_surfaces({
            'a': {'economie_annuelle@avec': [m('12 486')]},
            'b': {'economie_annuelle@avec': [m('12 487')]}})), 1)
        # Pourcentages à 1 point.
        self.assertEqual(compare_surfaces({
            'a': {'couverture_pct@avec': [m('37')]},
            'b': {'couverture_pct@avec': [m(37.9)]}}), [])
        ecarts = compare_surfaces({
            'a': {'couverture_pct@avec': [m('37')]},
            'b': {'couverture_pct@avec': [m(28)]}})
        self.assertEqual([e.identite for e in ecarts], ['couverture_pct@avec'])
        # Une remise s'imprime « − 1 200 » : on compare les valeurs absolues.
        self.assertEqual(compare_surfaces({
            'a': {'remise@sans': [m('− 1 200')]},
            'b': {'remise@sans': [m(1200)]}}), [])
        # Une option n'est jamais confrontée à une autre.
        self.assertEqual(compare_surfaces({
            'a': {'total_ttc@sans': [m(1000)]},
            'b': {'total_ttc@avec': [m(2000)]}}), [])

    def test_verifier_chaine_sur_un_rendu(self):
        """ATOT29 — la règle seule, sur des ancres de gabarit (taux mixtes,
        remise, arrondi, affichage au centime)."""
        a = figures.ancre
        chaine = (a('sous_total_ht', '10 000,00', 'avec')
                  + a('remise', '− 500,00', 'avec')
                  + a('arrondi', '− 12,50', 'avec')
                  + a('total_ht', '9 487,50', 'avec')
                  + a('tva_taux', '300,00', 'avec', 10)
                  + a('tva_taux', '1 297,50', 'avec', 20)
                  + a('tva', '1 597,50', 'avec')
                  + a('total_ttc', '11 085,00', 'avec'))
        self.assertEqual(verifier_chaine(extract_figures(chaine), 'avec'), [])
        sans_arrondi = chaine.replace(a('arrondi', '− 12,50', 'avec'), '')
        anomalies = verifier_chaine(extract_figures(sans_arrondi), 'avec')
        self.assertEqual(len(anomalies), 1, anomalies)
        self.assertIn('arrondi', anomalies[0])
        sans_taux = chaine.replace(a('tva_taux', '300,00', 'avec', 10), '')
        self.assertTrue(verifier_chaine(extract_figures(sans_taux), 'avec'))
        # Le gabarit legacy (sans ligne « Total HT ») part du Sous-total.
        legacy = (a('sous_total_ht', '1 000,00')
                  + a('tva_taux', '200,00', None, 20)
                  + a('total_ttc', '1 200,00'))
        self.assertEqual(verifier_chaine(extract_figures(legacy)), [])
        self.assertEqual(options_de_chaine(extract_figures(chaine)), ['avec'])

    def test_mappeur_proposition(self):
        payload = {
            'quote': {'deux_options': True, 'avec_ok': True,
                      'puissance_kwc': 9.94, 'prod_kwh': 12486,
                      'eco_s_ann': 9000, 'eco_a_ann': 12000,
                      'roi_s': 4.2, 'roi_a': 5.1},
            'option_totals': {
                'sans_batterie': {'ht_brut': 1000, 'remise': 0,
                                  'ht_net': 1000, 'tva': 200, 'ttc': 1200,
                                  'tva_par_taux': [{'taux': 20,
                                                    'montant': 200}]},
                'avec_batterie': {'ht_brut': 2000, 'remise': 0,
                                  'ht_net': 2000, 'tva': 400, 'ttc': 2400},
                'display_total': 2400},
            'pct_cut': 37, 'coverage_pct': 41, 'annual_before': 12000,
            'annual_after': 7560,
        }
        f = figures_depuis_proposition(payload)
        self.assertEqual(f['total_ttc@sans'][0].valeur, Decimal('1200'))
        self.assertEqual(f['total_ttc@avec'][0].valeur, Decimal('2400'))
        self.assertEqual(f['tva_taux:20@sans'][0].valeur, Decimal('200'))
        self.assertEqual(f['total_affiche'][0].valeur, Decimal('2400'))
        self.assertEqual(f['couverture_pct@avec'][0].valeur, Decimal('41'))
        self.assertEqual(f['facture_mensuelle_avant'][0].valeur,
                         Decimal('1000'))
        self.assertEqual(f['payback_ans@sans'][0].valeur, Decimal('4.2'))
        self.assertNotIn('remise@sans', f)  # 0 = non imprimé, non comparé
