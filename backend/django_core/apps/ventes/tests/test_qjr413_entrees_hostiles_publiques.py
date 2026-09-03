"""QJR413 (« QJR4-07 sécurité ») — plus aucun 500 public non authentifié.

DEUX FAMILLES, UNE SEULE RACINE : « une entrée hostile fait planter un endpoint
public au lieu de se faire refuser ».

(a) ``hmac.compare_digest`` sur des CHAÎNES — 10 sites d'invocation répartis
    sur 7 apps. Un seul octet non-ASCII arrivant d'un en-tête ou d'une chaîne
    de requête y levait un ``TypeError`` NON INTERCEPTÉ, donc un **HTTP 500 non
    authentifié** ; pire, la trame d'erreur portait la valeur ATTENDUE en clair
    (divulgation potentielle de secret tant que DEBUG n'est pas certifié
    coupé). Les 10 comparent désormais des BYTES, comme le faisaient déjà
    ``ventes/domain/cycle_vie.py`` — le patron de référence, INCHANGÉ ici.

(b) Gardes de type sur les corps JSON publics — 6 sites, tous dans
    ``apps/ventes/public_views.py`` : ``(request.data.get('x') or '').strip()``
    levait un ``AttributeError`` sur un champ valant un nombre, un objet ou une
    liste, donc un 500 sur des POST publics.

CE QUE CE FICHIER PROUVE, ET COMMENT. Les dix sites du (a) sont exercés
DIRECTEMENT (fonction de vérification ou vue de poignée de main), avec une
valeur hostile réelle : aucun n'a le droit de lever, tous doivent REFUSER, et
aucune réponse ne doit contenir la valeur attendue. Les six sites du (b) sont
exercés par la primitive partagée qu'ils appellent tous
(``public_views._texte_du_corps``) PLUS une garde structurelle (AST) qui prouve
qu'aucun d'eux n'est resté sur l'ancien patron.

NOTE HONNÊTE SUR ``null``. La garde du (b) refuse en 400 toute valeur qui n'est
pas une chaîne, ``null`` EXPLICITE compris (la clé est présente dans le corps).
Une clé ABSENTE reste, elle, le défaut d'aujourd'hui — byte-identique : c'est
ce que le client réel envoie (``apps/web/src/lib/proposition.ts
buildAcceptBodyRich`` construit son corps par assignation conditionnelle et
n'émet jamais ``null``).
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.ventes import public_views


#: Valeur hostile : un caractère non-ASCII suffisait à faire lever
#: ``compare_digest(str, str)``. « é » et l'espace de largeur nulle U+200B
#: (celui qui a motivé le correctif QJR146 de ``cycle_vie``) sont tous deux
#: testés — le second survit à un copier-coller depuis un email.
_HOSTILES = ('sha256=café', 'sha256=abc​def', 'téémoin')

#: Secret ATTENDU : aucune réponse de refus n'a le droit de le contenir.
_SECRET = 'secret-attendu-0123456789abcdef'


def _requete_signee(hostile):
    """Requête POST publique portant un ``X-Hub-Signature-256`` hostile."""
    return RequestFactory().post(
        '/webhook/', data=b'{}', content_type='application/json',
        HTTP_X_HUB_SIGNATURE_256=hostile)


class CompareDigestBytesTests(SimpleTestCase):
    """(a) — les 10 sites `str` refusent au lieu de lever (HTTP 500)."""

    # ── 1. apps/ecommerce_connect/common.py ────────────────────────────────

    def test_ecommerce_connect_verify_hmac_base64(self):
        from apps.ecommerce_connect.common import verify_hmac_base64
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                self.assertFalse(
                    verify_hmac_base64(_SECRET, b'{}', hostile))

    # ── 2. apps/crm/webhooks.py — ``_secret_ok`` ───────────────────────────

    @override_settings(WEBSITE_LEAD_WEBHOOK_SECRET=_SECRET)
    def test_crm_secret_ok(self):
        from apps.crm import webhooks
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                requete = RequestFactory().post(
                    '/webhook/', data=b'{}',
                    content_type='application/json',
                    HTTP_X_WEBHOOK_SECRET=hostile)
                self.assertFalse(webhooks._secret_ok(requete))

    # ── 3. apps/crm/webhooks.py — signature Meta Lead Ads ──────────────────

    def test_crm_check_meta_lead_ads_signature(self):
        from apps.crm import webhooks
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                self.assertFalse(webhooks._check_meta_lead_ads_signature(
                    _requete_signee(hostile), _SECRET))

    # ── 4. apps/crm/webhooks.py — poignée de main GET ──────────────────────

    @override_settings(META_LEAD_ADS_VERIFY_TOKEN=_SECRET)
    def test_crm_meta_lead_ads_handshake(self):
        from apps.crm import webhooks
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                requete = RequestFactory().get(
                    '/webhook/', {'hub.mode': 'subscribe',
                                  'hub.verify_token': hostile,
                                  'hub.challenge': 'X'})
                reponse = webhooks.meta_lead_ads_webhook(requete)
                self.assertEqual(reponse.status_code, 403)
                self.assertNotIn(_SECRET.encode(), reponse.content)

    # ── 5. apps/automation/public_views.py ─────────────────────────────────

    def test_automation_verify_signature(self):
        from apps.automation import public_views as automation_views
        trigger = SimpleNamespace(hmac_secret=_SECRET)
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                self.assertFalse(automation_views._verify_signature(
                    trigger, b'{}', hostile))

    # ── 6. apps/notifications/views_whatsapp_bsp.py — signature ────────────

    def test_notifications_bsp_check_signature(self):
        from apps.notifications import views_whatsapp_bsp as bsp
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                self.assertFalse(
                    bsp._check_signature(_requete_signee(hostile), _SECRET))

    # ── 7. apps/notifications/views_whatsapp_bsp.py — poignée de main ──────

    def test_notifications_bsp_handshake(self):
        from apps.notifications import views_whatsapp_bsp as bsp
        vue = bsp.WhatsAppBspWebhookView()
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                requete = RequestFactory().get(
                    '/webhook/', {'hub.mode': 'subscribe',
                                  'hub.verify_token': hostile,
                                  'hub.challenge': 'X'})
                with mock.patch.object(bsp, '_verify_token',
                                       return_value=_SECRET):
                    reponse = vue.get(requete)
                self.assertEqual(reponse.status_code, 403)
                self.assertNotIn(_SECRET.encode(), reponse.content)

    # ── 8. apps/publicapi/delivery.py ──────────────────────────────────────

    def test_publicapi_verify_signature_v2(self):
        from apps.publicapi.delivery import verify_signature_v2
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                entete = 't=%d,v1=%s' % (1_800_000_000, hostile)
                self.assertFalse(verify_signature_v2(
                    _SECRET, b'{}', entete, now=1_800_000_000))

    # ── 9. apps/adsengine/whatsapp_webhook.py — signature ──────────────────

    def test_adsengine_check_signature(self):
        from apps.adsengine import whatsapp_webhook as wa
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                self.assertFalse(
                    wa._check_signature(_requete_signee(hostile), _SECRET))

    # ── 10. apps/adsengine/whatsapp_webhook.py — poignée de main ───────────

    @override_settings(WHATSAPP_CLOUD_VERIFY_TOKEN=_SECRET,
                       WHATSAPP_CLOUD_APP_SECRET=_SECRET)
    def test_adsengine_handshake(self):
        from apps.adsengine import whatsapp_webhook as wa
        vue = wa.WhatsAppCloudWebhookView()
        for hostile in _HOSTILES:
            with self.subTest(hostile=hostile):
                requete = RequestFactory().get(
                    '/webhook/', {'hub.mode': 'subscribe',
                                  'hub.verify_token': hostile,
                                  'hub.challenge': 'X'})
                reponse = vue.get(requete)
                self.assertEqual(reponse.status_code, 403)
                self.assertNotIn(_SECRET.encode(), reponse.content)

    # ── Le chemin NOMINAL n'a pas bougé ────────────────────────────────────

    def test_une_signature_valide_reste_acceptee(self):
        """La bascule en bytes ne change RIEN pour une entrée légitime."""
        import hashlib
        import hmac as _hmac

        from apps.adsengine import whatsapp_webhook as wa
        bonne = 'sha256=' + _hmac.new(
            _SECRET.encode(), b'{}', hashlib.sha256).hexdigest()
        requete = RequestFactory().post(
            '/webhook/', data=b'{}', content_type='application/json',
            HTTP_X_HUB_SIGNATURE_256=bonne)
        self.assertTrue(wa._check_signature(requete, _SECRET))


class GardeStructurelleCompareDigestTests(SimpleTestCase):
    """Aucun des 12 sites du dépôt ne compare plus deux `str`."""

    #: Les 7 modules qui invoquent ``compare_digest`` hors tests, plus les DEUX
    #: sites déjà en bytes de ``cycle_vie`` (troisième test du `Done` : ils
    #: doivent rester tels quels).
    _MODULES = (
        'apps/adsengine/whatsapp_webhook.py',
        'apps/automation/public_views.py',
        'apps/crm/webhooks.py',
        'apps/ecommerce_connect/common.py',
        'apps/notifications/views_whatsapp_bsp.py',
        'apps/publicapi/delivery.py',
        'apps/ventes/domain/cycle_vie.py',
    )

    @staticmethod
    def _racine():
        # …/apps/ventes/tests/<ce fichier> → …/ (backend/django_core)
        return Path(__file__).resolve().parents[3]

    def _sites(self, chemin_relatif):
        source = (self._racine() / chemin_relatif).read_text(encoding='utf-8')
        arbre = ast.parse(source)
        return [
            noeud for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.Call)
            and isinstance(noeud.func, ast.Attribute)
            and noeud.func.attr == 'compare_digest'
        ]

    def test_les_deux_operandes_sont_toujours_des_bytes(self):
        total = 0
        for chemin in self._MODULES:
            for site in self._sites(chemin):
                total += 1
                self.assertEqual(
                    len(site.args), 2,
                    '%s:%d — compare_digest attend 2 opérandes'
                    % (chemin, site.lineno))
                for argument in site.args:
                    rendu = ast.unparse(argument)
                    self.assertIn(
                        ".encode(", rendu,
                        "%s:%d — opérande encore en `str` : %s"
                        % (chemin, site.lineno, rendu))
        # 10 sites recalés par QJR413 + les 2 de ``cycle_vie`` déjà en bytes.
        self.assertEqual(total, 12, '%d sites trouvés' % total)

    def test_les_deux_sites_de_cycle_vie_sont_inchanges(self):
        """Troisième test du `Done` : ils appartiennent à une autre lane."""
        sites = self._sites('apps/ventes/domain/cycle_vie.py')
        self.assertEqual(len(sites), 2)
        for site in sites:
            gauche, droite = (ast.unparse(a) for a in site.args)
            self.assertEqual(gauche, "str(stored).encode('utf-8')")
            self.assertEqual(droite, "otp_code.strip().encode('utf-8')")


class TexteDuCorpsTests(SimpleTestCase):
    """(b) — la primitive partagée que les 6 sites appellent tous."""

    @staticmethod
    def _requete(corps):
        return SimpleNamespace(data=corps)

    def test_une_valeur_non_textuelle_rend_un_400_jamais_un_500(self):
        for valeur in (5, 5.5, True, None, {'a': 1}, [1, 2], {}, []):
            with self.subTest(valeur=valeur):
                texte, refus = public_views._texte_du_corps(
                    self._requete({'champ': valeur}), 'champ')
                self.assertIsNone(texte)
                self.assertIsNotNone(refus)
                self.assertEqual(refus.status_code, 400)
                self.assertIn('champ', refus.data['detail'])

    def test_le_refus_ne_renvoie_jamais_la_valeur_recue(self):
        _texte, refus = public_views._texte_du_corps(
            self._requete({'champ': {'secret': 'ne-doit-pas-fuir'}}), 'champ')
        self.assertNotIn('ne-doit-pas-fuir', refus.data['detail'])

    def test_une_cle_absente_vaut_le_defaut_comportement_inchange(self):
        texte, refus = public_views._texte_du_corps(
            self._requete({}), 'champ', defaut='')
        self.assertIsNone(refus)
        self.assertEqual(texte, '')

    def test_une_chaine_est_rendue_nettoyee_comme_avant(self):
        texte, refus = public_views._texte_du_corps(
            self._requete({'champ': '  Ali  '}), 'champ')
        self.assertIsNone(refus)
        self.assertEqual(texte, 'Ali')

    def test_la_bascule_de_cle_suit_l_ancien_or(self):
        """``nom`` puis ``name`` : mêmes bascules que ``a or b or ''``."""
        requete = self._requete({'nom': '', 'name': 'Ali'})
        self.assertEqual(
            public_views._texte_du_corps(requete, 'nom', 'name')[0], 'Ali')
        # Une chaîne d'espaces reste une valeur FOURNIE : elle ne bascule pas.
        requete = self._requete({'nom': '   ', 'name': 'Ali'})
        self.assertEqual(
            public_views._texte_du_corps(requete, 'nom', 'name')[0], '')

    def test_un_corps_qui_n_est_pas_un_objet_est_refuse(self):
        for corps in ([1, 2], 'texte', 42):
            with self.subTest(corps=corps):
                texte, refus = public_views._texte_du_corps(
                    self._requete(corps), 'champ')
                self.assertIsNone(texte)
                self.assertEqual(refus.status_code, 400)


class GardeStructurelleCorpsPublicTests(SimpleTestCase):
    """Aucun des 6 sites n'est resté sur ``request.data.get(...).strip()``."""

    #: Les six champs recensés par QJR413 (b), avec leur vue.
    _CHAMPS = ('otp_code', 'nom', 'name', 'option', 'on_behalf_of', 'site_web')

    def test_plus_aucun_strip_nu_sur_le_corps_de_requete(self):
        source = Path(public_views.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(source)
        fautifs = []
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr == 'strip'):
                continue
            rendu = ast.unparse(noeud.func.value)
            if 'request.data.get' not in rendu:
                continue
            # ``str(...)`` neutralise déjà le défaut (aucun 500 possible) —
            # ces sites-là sont hors périmètre de QJR413.
            if rendu.startswith('str(') or '(str(' in rendu:
                continue
            fautifs.append('ligne %d : %s' % (noeud.lineno, rendu))
        self.assertEqual(fautifs, [], 'sites non gardés : %r' % (fautifs,))

    def test_les_six_champs_passent_par_la_primitive_partagee(self):
        source = Path(public_views.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(source)
        lus = set()
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call)
                    and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == '_texte_du_corps'):
                for argument in noeud.args[1:]:
                    if isinstance(argument, ast.Constant):
                        lus.add(argument.value)
        for champ in self._CHAMPS:
            self.assertIn(champ, lus,
                          '« %s » ne passe pas par _texte_du_corps' % champ)
