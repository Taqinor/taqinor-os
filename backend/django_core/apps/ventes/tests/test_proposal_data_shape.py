"""QJR7 — test de forme de `proposal_data` contre son contrat PACT10 (QJR3).

`public_views.proposal_data` est un dict de ~570 lignes ASSEMBLÉ À LA MAIN,
sans sérialiseur : le générateur de schéma DRF ne sait pas l'introspecter (un
commentaire du module le reconnaît). Il n'a donc AUCUNE forme déclarée que la
CI puisse vérifier — chaque consommateur (la page publique `apps/web`, les
tests, le prochain écran) invente sa propre hypothèse sur ce qu'il reçoit.
C'est exactement l'incident PACT10 du 03/08/2026 (l'écran AO Tableau de bord,
0 clé sur 6 concordante), rejoué sur la surface la plus visible du parcours.

Ce test est la réponse LITTÉRALE de PACT10 à ce dict : il compare la carte
`clé → nature` de la charge utile VIVANTE à l'échantillon
`apps/ventes/contract_samples/proposal_data.json`, **aux deux niveaux de
partage** (`standard` et `confiance`).

Ce qui devient ROUGE
--------------------
1. Une clé du serveur qui n'est PAS déclarée dans le contrat (le mode d'échec
   PACT10 : le backend sert `foo`, la page en attend `bar`).
2. Une clé déclarée qui CHANGE DE NATURE en silence (un objet devenu texte,
   une liste devenue objet) — le consommateur casse sans que rien ne l'ait dit.
3. Une des 44 clés de BASE qui DISPARAÎT de la réponse.
4. Une clé ADDITIVE servie à `null` (le contrat, bloc `additif_vs_null` : une
   clé de base sans rien à montrer vaut `null` et RESTE ; une clé additive sans
   rien à montrer est ABSENTE — jamais `"bankable": null`).

Ce qui reste VERT, volontairement
---------------------------------
* Une clé ADDITIVE absente : les ~17 clés additives dépendent de ce que le
  devis porte et des cases du dialogue d'envoi. Exiger leur présence ferait
  dépendre le test du hasard de la fixture, pas du contrat.
* Une clé de base à `null` : c'est la forme déclarée du « rien à montrer ».
* La forme INTERNE de `quote` : hors périmètre du contrat (bloc
  `portee_de_quote`) — d'autres contrats la documentent.
* Une clé dont le contrat ne montre QUE `null` dans ses trois exemples
  (`mode_kpis`, `multi_villa`…) : le contrat ne déclare alors aucune nature
  non nulle, il n'y a rien à comparer. Le test le dit plutôt que d'inventer.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_proposal_data_shape -v 2
"""
import copy
import json
import uuid
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client as DjangoClient, TestCase

from authentication.models import Company
from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis, ShareLink

User = get_user_model()

CONTRAT = (Path(__file__).resolve().parent.parent
           / 'contract_samples' / 'proposal_data.json')

#: Les trois exemples du contrat. Ensemble, ils disent : ce qui est TOUJOURS
#: là (leur intersection = les clés de base), ce qui peut s'ajouter (leur
#: union = tout le déclaré) et quelle nature chaque clé peut prendre.
EXEMPLES = ('exemple', 'exemple_standard', 'exemple_sections_masquees')

#: Compté sur le code serveur au moment du contrat (QJR3, 29/08/2026) ET
#: écrit dans `notes.structure_de_la_reponse`. Si ces deux nombres bougent,
#: le contrat ET cette constante changent ensemble — jamais l'un sans l'autre.
NB_CLES_BASE = 44
NB_CLES_ADDITIVES = 17

NUL = 'nul'


# ═══════════════════════════════════════════════════════════════════════════
# La carte clé → nature
# ═══════════════════════════════════════════════════════════════════════════

def nature(valeur):
    """Nature JSON d'une valeur, au vocabulaire du contrat.

    Volontairement GROSSIÈRE sur les nombres : `14` et `14.0` sont la même
    nature. Un contrat qui distinguerait entier et flottant deviendrait rouge
    au premier arrondi, sans qu'aucun consommateur ne casse.
    """
    if valeur is None:
        return NUL
    if isinstance(valeur, bool):  # AVANT int : bool est un sous-type de int
        return 'booleen'
    if isinstance(valeur, (int, float)):
        return 'nombre'
    if isinstance(valeur, str):
        return 'texte'
    if isinstance(valeur, list):
        return 'liste'
    if isinstance(valeur, dict):
        return 'objet'
    return type(valeur).__name__


def carte_des_natures(payload):
    """Carte `clé → nature` du premier niveau d'une charge utile."""
    return {cle: nature(valeur) for cle, valeur in payload.items()}


def charger_contrat(chemin=CONTRAT):
    """Rend (clés de base, clés additives, natures déclarées) du contrat.

    * base      = les clés présentes dans les TROIS exemples (toujours là) ;
    * additives = les autres clés déclarées quelque part ;
    * natures   = par clé, l'ensemble des natures NON NULLES observées dans
      les exemples (vide = le contrat ne montre que `null` pour cette clé).
    """
    data = json.loads(chemin.read_text(encoding='utf-8'))
    exemples = [data[nom] for nom in EXEMPLES]
    base = set(exemples[0])
    union = set()
    for ex in exemples:
        base &= set(ex)
        union |= set(ex)
    natures = {}
    for cle in union:
        vues = set()
        for ex in exemples:
            if cle in ex:
                nat = nature(ex[cle])
                if nat != NUL:
                    vues.add(nat)
        natures[cle] = vues
    return base, union - base, natures


def ecarts(payload, contrat):
    """Rend la liste (en français) des écarts de forme de cette charge utile.

    Liste vide = la charge utile respecte le contrat.
    """
    base, additives, natures = contrat
    problemes = []

    for cle in sorted(base - set(payload)):
        problemes.append(
            f"clé de BASE absente de la réponse : « {cle} » — les {NB_CLES_BASE} "
            "clés de base sont posées sans condition par le littéral "
            "`payload = {...}` ; si elle a été retirée ou renommée, le contrat "
            "apps/ventes/contract_samples/proposal_data.json doit le dire "
            "d'abord (PACT10).")

    for cle in sorted(payload):
        if cle not in natures:
            problemes.append(
                f"clé NON DÉCLARÉE servie par le serveur : « {cle} » "
                f"({nature(payload[cle])}) — la déclarer dans "
                "apps/ventes/contract_samples/proposal_data.json AVANT de la "
                "servir : sans contrat partagé, chaque consommateur invente sa "
                "propre hypothèse (incident PACT10 du 03/08/2026).")
            continue
        nat = nature(payload[cle])
        if nat == NUL:
            if cle in additives:
                problemes.append(
                    f"clé ADDITIVE servie à `null` : « {cle} » — le contrat "
                    "(bloc `additif_vs_null`) dit qu'une clé additive sans rien "
                    "à montrer est ABSENTE, jamais `null` : la page teste "
                    f"`'{cle}' in reponse` pour savoir si le bloc existe.")
            continue
        attendues = natures[cle]
        if attendues and nat not in attendues:
            problemes.append(
                f"CHANGEMENT DE NATURE sur « {cle} » : le serveur sert "
                f"« {nat} », le contrat déclare "
                f"« {' ou '.join(sorted(attendues))} ».")
    return problemes


# ═══════════════════════════════════════════════════════════════════════════
# Fixture — le patron éprouvé de test_l_niv_niveau.py
# ═══════════════════════════════════════════════════════════════════════════

def make_company(slug):
    company, _ = Company.objects.get_or_create(slug=slug, defaults={'nom': slug})
    return company


def make_user(company):
    return User.objects.create_user(
        username=f'qjr7_{company.slug}', password='x',
        role_legacy='responsable', company=company)


def make_client(company):
    return Client.objects.create(
        company=company, nom='QJR7', prenom='Forme',
        email=f'qjr7_{company.slug}@ex.com', telephone='+212600000077')


def make_devis(company, user, client_obj, reference, roof_layout=None):
    """Devis minimal qui PASSE le classifieur d'options du moteur.

    Vocabulaire imposé par `quote_engine/builder.py` (réseau/hybride) : un
    « Onduleur » nu ne tombe dans AUCUNE option → refus sécurité → 404.
    """
    devis = Devis.objects.create(
        company=company, reference=reference, client=client_obj,
        statut='envoye', taux_tva=Decimal('20.00'),
        remise_globale=Decimal('0'), created_by=user, roof_layout=roof_layout)
    for designation, quantite, prix in [
        ('Onduleur réseau Deye 8kW', '1', '14000'),
        ('Panneau Canadian Solar 550W', '10', '1400'),
    ]:
        produit = Produit.objects.create(
            company=company, nom=designation,
            sku=f'{reference[-6:]}-{designation[:8]}',
            prix_vente=Decimal(prix), prix_achat=Decimal('9999'),
            quantite_stock=50)
        LigneDevis.objects.create(
            devis=devis, produit=produit, designation=designation,
            quantite=Decimal(quantite), prix_unitaire=Decimal(prix),
            remise=Decimal('0'))
    return devis


def sample_layout():
    return {
        'version': 1, 'scenario': 'reseau',
        'result': {'panels': 10, 'kwc': 5.5, 'annualKwh': 9000},
        'zones': [{
            'id': 'z1', 'label': 'Pan Sud',
            'vertices': [[0, 0], [10, 0], [10, 6], [0, 6]],
            'obstacles': [], 'roofType': 'pitched', 'pitchDeg': 30,
            'facingAzimuthDeg': 0, 'neededPanels': 10,
        }],
        '_pans_geometry': [{
            'label': 'Pan Sud', 'orientation': 'Sud', 'azimut_deg': 0,
            'inclinaison_deg': 30, 'nb_panneaux': 10, 'kwc': 5.5,
            'roof_type': 'pitched',
        }],
    }


# ═══════════════════════════════════════════════════════════════════════════
# (a) Le contrat lui-même est lisible et cohérent avec sa propre prose
# ═══════════════════════════════════════════════════════════════════════════

class TestContratLisible(TestCase):
    def test_le_contrat_declare_44_cles_de_base_et_17_additives(self):
        base, additives, _natures = charger_contrat()
        self.assertEqual(
            len(base), NB_CLES_BASE,
            "le nombre de clés TOUJOURS présentes a bougé : mettre à jour "
            "ENSEMBLE `notes.structure_de_la_reponse` du contrat et la "
            "constante NB_CLES_BASE de ce test.")
        self.assertEqual(
            len(additives), NB_CLES_ADDITIVES,
            "le nombre de clés ADDITIVES a bougé : mettre à jour ENSEMBLE "
            "`notes.cles_additives_15_a_17` du contrat et NB_CLES_ADDITIVES.")

    def test_les_cles_pivots_sont_bien_classees(self):
        base, additives, natures = charger_contrat()
        for cle in ('niveau', 'quote', 'option_totals', 'niveau_masque',
                    'variantes_servables', 'monthly_production'):
            self.assertIn(cle, base)
        for cle in ('bankable', 'courbes_journalieres', 'offres_tailles',
                    'couverture_batterie', 'parametres_site'):
            self.assertIn(cle, additives)
        self.assertEqual(natures['option_totals'], {'objet'})
        self.assertEqual(natures['niveau'], {'texte'})
        self.assertEqual(natures['paliers_batterie'], {'liste'})


# ═══════════════════════════════════════════════════════════════════════════
# (b) La charge utile VIVANTE, aux DEUX niveaux
# ═══════════════════════════════════════════════════════════════════════════

class TestFormeDeLaChargeUtileVivante(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.contrat = charger_contrat()
        cls.company = make_company('qjr7-forme')
        cls.user = make_user(cls.company)
        cls.client_obj = make_client(cls.company)
        cls.devis = make_devis(cls.company, cls.user, cls.client_obj,
                               'DEV-QJR7-A1')
        cls.devis_layout = make_devis(cls.company, cls.user, cls.client_obj,
                                      'DEV-QJR7-A2',
                                      roof_layout=sample_layout())

    def _payload(self, devis, niveau):
        token = str(uuid.uuid4())
        ShareLink.objects.create(
            company=self.company, devis=devis, token=token, niveau=niveau)
        reponse = DjangoClient().get(
            f'/api/django/public/proposal/{token}/data/')
        self.assertEqual(reponse.status_code, 200)
        return reponse.json()

    def _tous_les_payloads(self):
        for devis in (self.devis, self.devis_layout):
            for niveau in (ShareLink.NIVEAU_STANDARD,
                           ShareLink.NIVEAU_CONFIANCE):
                yield devis.reference, niveau, self._payload(devis, niveau)

    def test_la_forme_vivante_respecte_le_contrat_aux_deux_niveaux(self):
        for reference, niveau, payload in self._tous_les_payloads():
            with self.subTest(devis=reference, niveau=niveau):
                self.assertEqual(payload['niveau'], niveau)
                problemes = ecarts(payload, self.contrat)
                self.assertEqual(
                    problemes, [],
                    f"forme de proposal_data hors contrat ({reference}, "
                    f"niveau {niveau}) :\n  - "
                    + "\n  - ".join(problemes))

    def test_les_44_cles_de_base_sont_servies_aux_deux_niveaux(self):
        base, _additives, _natures = self.contrat
        for reference, niveau, payload in self._tous_les_payloads():
            with self.subTest(devis=reference, niveau=niveau):
                self.assertEqual(
                    sorted(base - set(payload)), [],
                    "des clés de base manquent à la réponse")

    def test_aucune_cle_additive_servie_a_null(self):
        _base, additives, _natures = self.contrat
        for reference, niveau, payload in self._tous_les_payloads():
            with self.subTest(devis=reference, niveau=niveau):
                nulles = sorted(cle for cle in additives
                                if cle in payload and payload[cle] is None)
                self.assertEqual(
                    nulles, [],
                    "une clé additive sans rien à montrer doit être ABSENTE, "
                    "jamais servie à `null` (contrat, `additif_vs_null`)")

    # ── Les quatre directions ROUGES, prouvées sur la charge utile RÉELLE ──

    def test_une_cle_non_declaree_rend_rouge(self):
        payload = copy.deepcopy(self._payload(self.devis,
                                              ShareLink.NIVEAU_CONFIANCE))
        payload['une_cle_que_le_contrat_ignore'] = {'x': 1}
        problemes = ecarts(payload, self.contrat)
        self.assertTrue(problemes)
        self.assertIn('une_cle_que_le_contrat_ignore', ' '.join(problemes))

    def test_un_changement_de_nature_rend_rouge(self):
        payload = copy.deepcopy(self._payload(self.devis,
                                              ShareLink.NIVEAU_CONFIANCE))
        # `option_totals` est un objet, toujours (littéral du serveur).
        self.assertIsInstance(payload['option_totals'], dict)
        payload['option_totals'] = 'devenu un texte'
        problemes = ecarts(payload, self.contrat)
        self.assertTrue(problemes)
        message = ' '.join(problemes)
        self.assertIn('option_totals', message)
        self.assertIn('CHANGEMENT DE NATURE', message)

    def test_une_cle_de_base_disparue_rend_rouge(self):
        payload = copy.deepcopy(self._payload(self.devis,
                                              ShareLink.NIVEAU_CONFIANCE))
        del payload['reference']
        problemes = ecarts(payload, self.contrat)
        self.assertTrue(problemes)
        self.assertIn('reference', ' '.join(problemes))

    def test_une_cle_additive_a_null_rend_rouge(self):
        payload = copy.deepcopy(self._payload(self.devis,
                                              ShareLink.NIVEAU_CONFIANCE))
        payload['bankable'] = None
        problemes = ecarts(payload, self.contrat)
        self.assertTrue(problemes)
        self.assertIn('bankable', ' '.join(problemes))


# ═══════════════════════════════════════════════════════════════════════════
# (c) Le comparateur lui-même — sans base, sur les exemples du contrat
# ═══════════════════════════════════════════════════════════════════════════

class TestComparateur(TestCase):
    def setUp(self):
        self.contrat = charger_contrat()
        self.exemples = json.loads(CONTRAT.read_text(encoding='utf-8'))

    def test_les_trois_exemples_du_contrat_sont_conformes(self):
        for nom in EXEMPLES:
            with self.subTest(exemple=nom):
                self.assertEqual(ecarts(self.exemples[nom], self.contrat), [])

    def test_une_cle_de_base_a_null_reste_verte(self):
        payload = copy.deepcopy(self.exemples['exemple'])
        payload['roof_image_url'] = None
        self.assertEqual(ecarts(payload, self.contrat), [])

    def test_une_cle_additive_absente_reste_verte(self):
        payload = copy.deepcopy(self.exemples['exemple'])
        del payload['bankable']
        del payload['offres_tailles']
        self.assertEqual(ecarts(payload, self.contrat), [])

    def test_la_forme_interne_de_quote_nest_pas_comparee(self):
        # `portee_de_quote` : ce contrat documente l'emballage, pas `quote`.
        payload = copy.deepcopy(self.exemples['exemple'])
        payload['quote'] = {'une_cle_interne_inconnue': [1, 2, 3]}
        self.assertEqual(ecarts(payload, self.contrat), [])

    def test_natures_grossieres_sur_les_nombres(self):
        self.assertEqual(nature(14), nature(14.0))
        self.assertEqual(nature(True), 'booleen')  # jamais 'nombre'
        self.assertEqual(nature(None), NUL)
        self.assertEqual(nature([]), 'liste')
        self.assertEqual(nature({}), 'objet')
        self.assertEqual(nature('x'), 'texte')

    def test_carte_des_natures(self):
        self.assertEqual(
            carte_des_natures({'a': 1, 'b': 'x', 'c': None, 'd': []}),
            {'a': 'nombre', 'b': 'texte', 'c': NUL, 'd': 'liste'})

    def test_une_cle_sans_nature_declaree_est_toleree(self):
        # `mode_kpis` vaut `null` dans les trois exemples : le contrat ne
        # déclare AUCUNE nature non nulle, il n'y a rien à comparer.
        _base, _additives, natures = self.contrat
        self.assertEqual(natures['mode_kpis'], set())
        payload = copy.deepcopy(self.exemples['exemple'])
        payload['mode_kpis'] = {'kpi': 1}
        self.assertEqual(ecarts(payload, self.contrat), [])
