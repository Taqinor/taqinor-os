"""MRY12 — Les textes des touches, et la garantie qu'ils ne dérivent PAS.

La vraie garde de ce fichier n'est pas « chaque clé a un défaut non vide »
(trivial) : c'est que chaque défaut est encore EXACTEMENT le texte validé par
le fondateur dans `docs/crm/messages_meryem.md`. Le test RE-DÉRIVE ce fichier
et compare. Une reformulation, une espace en trop, un « TAQINOR » devenu
« Taqinor » : rouge immédiat, et le message part vers de vrais clients.

Il verrouille aussi la règle absolue du lot : aucun chiffre n'est un
placeholder, et aucun `{…}` hors de la liste autorisée ne peut se glisser dans
un texte (une clé inconnue s'afficherait telle quelle chez le client).
"""
import json
import pathlib
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from authentication.models import Company

from apps.parametres.models_messages import (
    CLES_RELANCE, MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
    PLACEHOLDERS_RELANCE, MessageTemplate,
)

User = get_user_model()

MESSAGES_URL = '/api/django/parametres/messages/'

#: Conversion crochet → placeholder, dictée par l'en-tête du fichier source.
#: Tout AUTRE crochet reste un crochet : montant, raison réelle, jour et heure
#: de rappel se saisissent à la main — jamais un défaut inventé.
_CROCHETS = [
    (r'\[Prénom\]', '{prenom}'),
    (r'\[prénom\]', '{prenom}'),
    (r'\[الاسم\]', '{prenom}'),
    (r'\[date\]', '{date_validite}'),
    (r'\[référence\]', '{reference}'),
    (r'\[المرجع\]', '{reference}'),
    # 08/09/2026 — la PREUVE de `j4_preuve` (catalogue « Réalisations »).
    # `[lien preuve]` passe AVANT toute autre règle de lien : la conversion
    # est une SUITE de `re.sub`, donc une règle « lien » plus large appliquée
    # d'abord l'avalerait et rendrait `{lien}` (le lien du devis) à la place
    # du lien de la réalisation — deux liens différents dans le même message.
    (r'\[lien preuve\]', '{lien_preuve}'),
    (r'\[puissance preuve\]', '{puissance_preuve}'),
    (r'\[lien de la fiche TAQINOR\]', '{lien}'),
    (r'\[lien de votre proposition\]', '{lien}'),
    (r'\[mois\]', '{mois_preuve}'),
    (r'\[ville\]', '{ville_preuve}'),
    (r'\[Conseiller\]', '{conseiller}'),
    (r'\[المستشار\]', '{conseiller}'),
]

_TOKEN_RE = re.compile(r'\{[^{}]*\}')


def _fichier_source():
    """`docs/crm/messages_meryem.md`, remonté depuis ce fichier de test."""
    ici = pathlib.Path(__file__).resolve()
    for parent in ici.parents:
        candidat = parent / 'docs' / 'crm' / 'messages_meryem.md'
        if candidat.exists():
            return candidat
    raise AssertionError(
        'docs/crm/messages_meryem.md introuvable — c\'est la SOURCE DE VÉRITÉ '
        'des textes de relance, elle ne peut pas disparaître.')


def _textes_valides():
    """`{cle: {fr, darija}}` re-dérivé du fichier validé (jamais retapé)."""
    lignes = _fichier_source().read_text(
        encoding='utf-8').replace('\r\n', '\n').split('\n')
    textes, cle = {}, None
    for ligne in lignes:
        if ligne.startswith('### '):
            cle = ligne[4:].split(' ')[0].strip()
            textes[cle] = {'fr': '', 'darija': ''}
        elif cle and ligne.startswith('FR : '):
            textes[cle]['fr'] = _convertir(ligne[5:].strip())
        elif cle and ligne.startswith('DARIJA : '):
            textes[cle]['darija'] = _convertir(ligne[9:].strip())
    return textes


def _convertir(texte):
    for motif, remplacement in _CROCHETS:
        texte = re.sub(motif, remplacement, texte)
    return texte


class TextesFidelesALaSourceTests(TestCase):
    """LA garde du lot : le code ne s'écarte jamais du texte validé."""

    def setUp(self):
        self.source = _textes_valides()

    def test_la_source_porte_bien_les_cles_attendues(self):
        """Anti-faux-vert : si le parseur ne trouvait rien, tous les tests de
        comparaison passeraient à vide."""
        self.assertEqual(sorted(self.source), sorted(CLES_RELANCE))

    def test_chaque_defaut_fr_est_le_texte_valide(self):
        for cle in CLES_RELANCE:
            with self.subTest(cle=cle):
                self.assertEqual(MESSAGE_TEMPLATE_DEFAULTS[cle],
                                 self.source[cle]['fr'])

    def test_chaque_defaut_darija_est_le_texte_valide(self):
        attendus = {c: v['darija'] for c, v in self.source.items()
                    if v['darija']}
        self.assertEqual(set(MESSAGE_TEMPLATE_DEFAULTS_DARIJA), set(attendus))
        for cle, texte in attendus.items():
            with self.subTest(cle=cle):
                self.assertEqual(MESSAGE_TEMPLATE_DEFAULTS_DARIJA[cle], texte)

    def test_les_cles_sans_darija_ne_sont_pas_inventees(self):
        """Une traduction automatique partirait à de vrais clients : une clé
        sans darija validée retombe sur le FR, elle n'est jamais fabriquée."""
        sans_darija = [c for c, v in self.source.items() if not v['darija']]
        self.assertTrue(sans_darija)
        for cle in sans_darija:
            self.assertNotIn(cle, MESSAGE_TEMPLATE_DEFAULTS_DARIJA)


class ClesEtDefautsTests(TestCase):
    def test_chaque_cle_de_relance_est_un_choix_du_modele(self):
        choix = {c for c, _ in MessageTemplate.Cle.choices}
        for cle in CLES_RELANCE:
            self.assertIn(cle, choix)

    def test_chaque_cle_a_un_defaut_non_vide(self):
        for cle in CLES_RELANCE:
            with self.subTest(cle=cle):
                self.assertTrue(
                    (MESSAGE_TEMPLATE_DEFAULTS.get(cle) or '').strip())

    def test_les_cles_sans_texte_valide_ne_sont_PAS_ajoutees(self):
        """`visite_veille`/`visite_matin`/`apres_visite` : aucun texte validé
        n'existe dans le Guide — on n'invente pas un message client."""
        choix = {c for c, _ in MessageTemplate.Cle.choices}
        for cle in ('visite_veille', 'visite_matin', 'apres_visite'):
            self.assertNotIn(cle, choix)

    def test_les_cles_historiques_sont_intactes(self):
        """Additif : aucun message existant n'est retiré ni réécrit."""
        for cle in ('devis_unique', 'facture', 'relance', 'rappel_rdv'):
            self.assertIn(cle, MESSAGE_TEMPLATE_DEFAULTS)
        self.assertIn('{reference}', MESSAGE_TEMPLATE_DEFAULTS['facture'])


class ReglePasDePrenomCodeEnDurTests(TestCase):
    """Règle fondateur du 08/09/2026 : aucun prénom de personne (Meryem, Reda)
    n'est codé en dur dans un texte qui atteint le client — l'expéditeur est
    désormais `{conseiller}`, résolu côté serveur depuis le RESPONSABLE du
    lead. On teste les TEXTES (les valeurs), jamais les clés : les clés
    `annonce_appel_reda`/`offre_reda` contiennent la sous-chaîne « reda » par
    construction (identifiants internes, jamais renommés)."""

    INTERDITS = ('Meryem', 'مريم', 'Reda', 'رضا')

    def test_aucun_defaut_fr_ne_code_un_prenom_en_dur(self):
        for cle, texte in MESSAGE_TEMPLATE_DEFAULTS.items():
            with self.subTest(cle=cle):
                for mot in self.INTERDITS:
                    self.assertNotIn(
                        mot, texte,
                        f'{cle} (FR) contient « {mot} » en dur — utiliser '
                        '{conseiller} ou « le fondateur ».')

    def test_aucun_defaut_darija_ne_code_un_prenom_en_dur(self):
        for cle, texte in MESSAGE_TEMPLATE_DEFAULTS_DARIJA.items():
            with self.subTest(cle=cle):
                for mot in self.INTERDITS:
                    self.assertNotIn(
                        mot, texte,
                        f'{cle} (darija) contient « {mot} » en dur — '
                        'utiliser {conseiller} ou « le fondateur ».')


class PlaceholdersTests(TestCase):
    def test_aucun_token_hors_de_la_liste_autorisee(self):
        autorises = set(PLACEHOLDERS_RELANCE)
        for source in (MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
                       {c: MESSAGE_TEMPLATE_DEFAULTS[c] for c in CLES_RELANCE}):
            for cle, texte in source.items():
                inconnus = [t for t in _TOKEN_RE.findall(texte)
                            if t not in autorises]
                self.assertEqual(
                    inconnus, [],
                    f'{cle} : placeholder(s) non autorisé(s) {inconnus} — '
                    'ils s\'afficheraient tels quels chez le client.')

    def test_aucun_chiffre_nest_un_placeholder(self):
        """Prix, kWc, économies restent dans le devis et la proposition."""
        interdits = {'{prix}', '{montant}', '{kwc}', '{economie}',
                     '{economies}', '{total}', '{total_ttc}', '{puissance}'}
        self.assertEqual(interdits & set(PLACEHOLDERS_RELANCE), set())


class GetCorpsTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='MRY12', slug='mry12')

    def test_sans_ligne_le_defaut_fr_sort(self):
        self.assertEqual(
            MessageTemplate.get_corps(self.company, 'identite'),
            MESSAGE_TEMPLATE_DEFAULTS['identite'])

    def test_darija_vide_retombe_sur_le_fr(self):
        MessageTemplate.objects.create(
            company=self.company, cle='j1_pdf',
            corps_fr='Texte maison', corps_darija='')
        self.assertEqual(
            MessageTemplate.get_corps(self.company, 'j1_pdf', 'darija'),
            'Texte maison')

    def test_darija_renseignee_prime(self):
        MessageTemplate.objects.create(
            company=self.company, cle='identite',
            corps_fr='FR maison', corps_darija='DARIJA maison')
        self.assertEqual(
            MessageTemplate.get_corps(self.company, 'identite', 'darija'),
            'DARIJA maison')

    def test_isolation_entre_societes(self):
        autre = Company.objects.create(nom='MRY12b', slug='mry12b')
        MessageTemplate.objects.create(
            company=autre, cle='identite', corps_fr='Chez le voisin')
        self.assertEqual(
            MessageTemplate.get_corps(self.company, 'identite'),
            MESSAGE_TEMPLATE_DEFAULTS['identite'])

    def test_darija_defaut_valide_sort_sans_aucune_ligne(self):
        """Défaut MAJEUR (données mortes) : sans ligne enregistrée, le défaut
        Darija validé doit sortir — pas le défaut FR."""
        self.assertEqual(
            MessageTemplate.get_corps(self.company, 'identite', 'darija'),
            MESSAGE_TEMPLATE_DEFAULTS_DARIJA['identite'])

    def test_darija_sans_defaut_valide_et_sans_ligne_retombe_sur_le_fr(self):
        """`j1_pdf` n'a pas de défaut Darija validé (chaîne "Après devis") :
        sans ligne, le repli est le défaut FR — jamais une clé inventée."""
        self.assertNotIn('j1_pdf', MESSAGE_TEMPLATE_DEFAULTS_DARIJA)
        self.assertEqual(
            MessageTemplate.get_corps(self.company, 'j1_pdf', 'darija'),
            MESSAGE_TEMPLATE_DEFAULTS['j1_pdf'])


class MessagesApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(nom='MRY12api', slug='mry12api')
        self.admin = User.objects.create_user(
            username='mry12-admin', password='pw', role_legacy='admin',
            company=self.company)
        self.api = APIClient()
        self.api.credentials(
            HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')

    def test_toutes_les_nouvelles_cles_sortent_avec_leur_defaut(self):
        resp = self.api.get(MESSAGES_URL)
        self.assertEqual(resp.status_code, 200)
        lignes = {r['cle']: r for r in resp.data}
        for cle in CLES_RELANCE:
            with self.subTest(cle=cle):
                self.assertIn(cle, lignes)
                self.assertEqual(lignes[cle]['default_fr'],
                                 MESSAGE_TEMPLATE_DEFAULTS[cle])

    def test_default_darija_expose_pour_identite(self):
        """Défaut MAJEUR (données mortes) : l'écran Paramètres → Messages
        doit recevoir le défaut Darija validé, comme il reçoit `default_fr`."""
        resp = self.api.get(MESSAGES_URL)
        self.assertEqual(resp.status_code, 200)
        lignes = {r['cle']: r for r in resp.data}
        self.assertEqual(lignes['identite']['default_darija'],
                         MESSAGE_TEMPLATE_DEFAULTS_DARIJA['identite'])
        # Une clé sans défaut Darija validé (`j1_pdf`) n'en invente pas un.
        self.assertEqual(lignes['j1_pdf']['default_darija'], '')

    def test_une_cle_de_relance_est_enregistrable_avec_ses_placeholders(self):
        """Sans entrée dans `_MESSAGE_PLACEHOLDERS`, la sauvegarde aurait été
        refusée : une clé absente y prend un ensemble autorisé VIDE."""
        resp = self.api.put(MESSAGES_URL, {
            'cle': 'j9_validite',
            'corps_fr': 'Votre proposition {reference} est valable jusqu\'au '
                        '{date_validite} — {lien}',
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(
            MessageTemplate.objects.filter(
                company=self.company, cle='j9_validite').count(), 1)

    def test_un_placeholder_inconnu_reste_refuse(self):
        resp = self.api.put(MESSAGES_URL, {
            'cle': 'j9_validite', 'corps_fr': 'Prix : {prix_total}',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('prix_total', json.dumps(resp.data, ensure_ascii=False))
