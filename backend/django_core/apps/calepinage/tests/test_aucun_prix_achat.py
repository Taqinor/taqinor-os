"""CAL122 — garde de surface : AUCUNE sortie du module ne porte un coût de
revient.

``Produit.prix_achat`` alimente un indicateur de marge réservé au GÉNÉRATEUR
(CLAUDE.md, « GENERATOR-ONLY ») ; le module Calepinage publie des dicts
d'équipement complets (CAL243 et toutes les tâches suivantes) — un
sérialiseur qui reprendrait ``**specs`` sans discernement exposerait le
champ sans que personne ne le voie.

CETTE SUITE NE CONTIENT AUCUNE LISTE DE ROUTES ÉCRITE À LA MAIN — patron
``test_isolation_societe.py`` (CAL29) : elle PARCOURT LE ROUTEUR
(``django.urls.get_resolver()``), donc couvre D'OFFICE les trente routes qui
arriveront après elle, et applique la MÊME garde à chaque réponse GET
réellement servie ET à chaque échantillon de contrat committé
(``contract_samples/*.json``).

Ce qui est prouvé ici :

* le détecteur ``cles_interdites`` ROUGIT sur une clé ajoutée
  volontairement, à plat, imbriquée, ou dans une liste (la preuve de garde
  exigée par le « Done » de CAL122) ;
* AUCUNE route GET du module ne renvoie ``prix_achat``, ``cout_achat`` ni
  ``marge`` (recherche par SOUS-CHAÎNE dans le nom de la clé — attrape aussi
  ``prix_achat_ttc``, ``marge_pct``…) ;
* les échantillons ``contract_samples/*.json`` sont propres, y compris
  ``calepinage_equipements.json`` (CAL120).

Run :
    python manage.py test apps.calepinage.tests.test_aucun_prix_achat -v2
"""
import json
import unittest
from decimal import Decimal
from pathlib import Path

from django.urls import URLPattern, URLResolver, get_resolver

from apps.calepinage.models import Calepinage
from apps.stock.models import FicheTechnique, Produit
from apps.ventes.models import Devis, LigneDevis

from .test_api_liste import BaseApiCalepinage

PREFIXE = 'api/django/calepinage/'

#: Sous-chaînes interdites dans le NOM d'une clé — minuscule, comparaison par
#: sous-chaîne (attrape ``prix_achat_ttc``, ``marge_pct``, ``cout_achat_moyen``).
MOTIFS_INTERDITS = ('prix_achat', 'marge', 'cout_achat')

#: EXEMPTION NOMMÉE — le module a déjà un vocabulaire GÉOMÉTRIQUE légitime
#: qui porte le mot « marge » sans aucun rapport avec un coût de revient :
#: ``apps/calepinage/selectors.py`` (``marge_troncon_min``/``marge_bande_min``
#: /``marges``) mesure le DÉGAGEMENT restant entre deux rangées de modules
#: posés — exactement la « Marges » géométrique que
#: ``moteur_io.marges_vers_json`` publie déjà (patron cité par
#: ``contract_samples/README.md``, règle 3). Une garde qui rougirait
#: dessus serait un faux positif garanti sur du code correct — on l'exempte
#: donc PAR NOM EXACT, jamais par préfixe (une future clé ``marge_xxx``
#: inconnue de cette liste reste interdite).
CLES_GEOMETRIQUES_EXEMPTEES = frozenset({
    'marge_troncon_min', 'marge_bande_min', 'marges',
})


def _routes(resolver=None, prefixe=''):
    """Toutes les routes servies, à plat — LUES DANS LE ROUTEUR (CAL29)."""
    resolver = resolver or get_resolver()
    trouvees = []
    for motif in resolver.url_patterns:
        chemin = prefixe + str(motif.pattern)
        if isinstance(motif, URLResolver):
            trouvees.extend(_routes(motif, chemin))
        elif isinstance(motif, URLPattern):
            trouvees.append((chemin, motif.callback))
    return trouvees


def _sert_get(callback):
    """La route sert-elle GET ? Un routeur DRF le déclare sur l'action."""
    actions = getattr(callback, 'actions', None)
    if actions:
        return 'get' in actions
    classe = (getattr(callback, 'cls', None)
              or getattr(callback, 'view_class', None))
    if classe is None:
        return True
    return hasattr(classe, 'get')


def routes_get_du_module():
    """Les chemins GET de ``/api/django/calepinage/`` — jamais une liste
    écrite à la main : une route neuve entre dans le balayage d'elle-même."""
    vues = []
    for chemin, callback in _routes():
        if not chemin.startswith(PREFIXE):
            continue
        reste = chemin[len(PREFIXE):]
        if '(?P<format>' in reste or reste.startswith('<drf_format_suffix'):
            continue
        if not reste or not _sert_get(callback):
            continue
        vues.append(reste)
    return vues


def cles_interdites(objet, chemin=''):
    """``[(chemin, cle)]`` — chaque clé qui CONTIENT un motif interdit, où
    qu'elle se trouve dans une structure JSON imbriquée (dict/liste). Fonction
    PURE : aucune requête, aucune écriture — c'est elle que le test unitaire
    ci-dessous prouve ROUGE en lui donnant une clé posée volontairement."""
    trouvees = []
    if isinstance(objet, dict):
        for cle, valeur in objet.items():
            texte = str(cle).lower()
            interdite = (any(motif in texte for motif in MOTIFS_INTERDITS)
                         and texte not in CLES_GEOMETRIQUES_EXEMPTEES)
            if interdite:
                trouvees.append((chemin or '<racine>', str(cle)))
            trouvees.extend(cles_interdites(valeur, f'{chemin}.{cle}'))
    elif isinstance(objet, (list, tuple)):
        for index, item in enumerate(objet):
            trouvees.extend(cles_interdites(item, f'{chemin}[{index}]'))
    return trouvees


class GardeUnitaireTest(unittest.TestCase):
    """La PREUVE que le détecteur rougit — condition « Done » de CAL122."""

    def test_detecte_prix_achat_a_plat(self):
        self.assertEqual(
            cles_interdites({'prix_achat': 100}),
            [('<racine>', 'prix_achat')])

    def test_detecte_marge_imbriquee(self):
        trouvees = cles_interdites(
            {'panneau': {'specs': {'marge_pct': 12}}})
        self.assertEqual(trouvees, [('.panneau.specs', 'marge_pct')])

    def test_detecte_cout_achat_dans_une_liste(self):
        trouvees = cles_interdites({'lignes': [{'cout_achat_moyen': 1}]})
        self.assertEqual(len(trouvees), 1)

    def test_dict_propre_ne_declenche_rien(self):
        self.assertEqual(
            cles_interdites(
                {'produit': 1, 'quantite': 4, 'specs': {'pmax_wc': 550}}),
            [])

    def test_marges_geometriques_exemptees_par_nom_exact(self):
        """Le vocabulaire GÉOMÉTRIQUE déjà publié par
        ``apps/calepinage/selectors.py`` (dégagement entre rangées) ne
        rougit pas — c'est la condition qui rend ce garde-fou utilisable
        SANS casser du code correct."""
        self.assertEqual(
            cles_interdites({
                'marge_troncon_min': 0.3, 'marge_bande_min': 0.2,
                'marges': {'nord': 0.5},
            }),
            [])

    def test_une_autre_clé_marge_reste_interdite(self):
        """L'exemption est NOMMÉE, pas un préfixe : une clé ``marge_xxx``
        qui n'est PAS une des trois exemptées reste interdite."""
        self.assertEqual(
            cles_interdites({'marge_generateur_pct': 12}),
            [('<racine>', 'marge_generateur_pct')])


class BalayageAucunPrixAchatTest(BaseApiCalepinage):
    """Le balayage RÉEL : chaque route GET, appelée pour de vrai."""

    def setUp(self):
        super().setUp()
        self.panneau = Produit.objects.create(
            company=self.company, nom='Module PV CAL122', sku='CAL122-MOD',
            prix_achat=Decimal('1234.56'), prix_vente=Decimal('2000'),
            quantite_stock=1)
        FicheTechnique.objects.create(
            company=self.company, produit=self.panneau, type_fiche='module',
            pmax_wc=Decimal('550'))
        self.devis = Devis.objects.create(
            company=self.company, client=self.client_a,
            reference='DEV-CAL122-1')
        LigneDevis.objects.create(
            devis=self.devis, produit=self.panneau, designation='Module PV',
            quantite=Decimal('10'), prix_unitaire=Decimal('2000'),
            type_ligne='produit')
        self.calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, devis=self.devis,
            titre='Villa CAL122', roof_layout={'result': {'panels': 10}},
            layout_hash='7' * 64)

    def _url_remplie(self, reste):
        chemin = reste.lstrip('^').replace('$', '')
        chemin = (chemin.replace('<int:pk>', str(self.calepinage.pk))
                        .replace('<pk>', str(self.calepinage.pk)))
        for nom in ('variante_id', 'version_id', 'job_id'):
            chemin = (chemin.replace(f'<int:{nom}>', '0')
                            .replace(f'<{nom}>', '0')
                            .replace(f'(?P<{nom}>[^/.]+)', '0'))
        if '<' in chemin or '(?P<' in chemin:
            return None  # paramètre non couvert par ce balayage lecture
        return '/' + PREFIXE + chemin

    def test_aucune_route_get_ne_rend_un_cout_de_revient(self):
        verifiees = 0
        for reste in routes_get_du_module():
            url = self._url_remplie(reste)
            if url is None:
                continue
            reponse = self.api.get(url)
            if reponse.status_code != 200:
                continue
            trouvees = cles_interdites(reponse.data)
            self.assertEqual(
                trouvees, [],
                f'GET {url} renvoie une clé de coût de revient : {trouvees}')
            verifiees += 1
        self.assertGreater(verifiees, 0, 'aucune route GET balayée')

    def test_les_echantillons_de_contrat_sont_propres(self):
        """Les exemples committés (contract_samples/*.json) — MÊME garde,
        sur le document qui sert de référence au frontend (CAL120)."""
        racine = Path(__file__).resolve().parents[1] / 'contract_samples'
        verifies = 0
        for fichier in sorted(racine.glob('*.json')):
            document = json.loads(fichier.read_text(encoding='utf-8'))
            for cle in ('exemple', 'exemple_vide'):
                if cle not in document:
                    continue
                trouvees = cles_interdites(document[cle])
                self.assertEqual(
                    trouvees, [],
                    f'{fichier.name}[{cle}] porte une clé interdite : '
                    f'{trouvees}')
                verifies += 1
        self.assertGreater(verifies, 0, 'aucun échantillon balayé')
