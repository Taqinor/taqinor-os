"""QJR416 (QJR4-03, COMBINÉE) — UNE primitive d'adresse IP, et elle lit le
DERNIER saut de confiance.

TROIS DÉFAUTS, UNE RACINE : il n'existait pas de primitive unique, et celle qui
existait lisait le mauvais saut.

(i)  **Preuve légale de signature** — ``ventes/public_views._client_ip`` faisait
     ``fwd.split(',')[0].strip()`` : le PREMIER saut de ``X-Forwarded-For``,
     c'est-à-dire une valeur **choisie par l'appelant**. C'est le champ de
     preuve du registre immuable de signature électronique (loi 53-05) :
     n'importe qui pouvait écrire l'adresse qui serait opposée à un signataire.
(ii) **Limitation de débit** — 36 sous-classes de ``SimpleRateThrottle`` dans le
     backend, **zéro** ``get_ident`` surchargé, et ``NUM_PROXIES`` absent des
     réglages : le ``get_ident`` de DRF retombe alors sur le premier saut, donc
     le seau de limitation était **adressable par l'appelant** (il suffisait de
     changer un en-tête pour repartir d'un seau vierge).
(iii) **Journal de consultation (QJR4-11, requalifié qualité-de-données)** —
     ``crm/public_views._hash_ip`` était un SHA-256 **non salé** de
     ``REMOTE_ADDR`` : derrière le proxy, la valeur est constante pour tous les
     visiteurs, donc le journal NTCRM18 ne distinguait personne.

CORRECTIF À LA RACINE : ``core.throttling.ip_de_requete`` (fondation, base
layer) lit le dernier saut de confiance ; ``crm.visites.ip_de_requete`` n'est
plus qu'une délégation ; la preuve légale, les throttles publics
(``IdentIpPartageeMixin``) et le journal s'y branchent. Le journal est en plus
salé PAR LIEN.

LA MOITIÉ ``apps/web`` (le proxy Astro qui doit transmettre les en-têtes) est
SORTIE de cette tâche : c'est QJW25 dans ``docs/WEB_PLAN.md``.
"""
import ast
from pathlib import Path
from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.crm import public_views as crm_public
from apps.crm import visites
from apps.ventes import public_views as ventes_public
from core.throttling import ip_de_requete


#: Une chaîne réaliste : le visiteur a forgé « 9.9.9.9 » en tête, notre nginx a
#: APPENDU l'adresse qu'il a réellement vue.
_FORGEE = '9.9.9.9'


def _requete(xff=None, remote='10.0.0.1', cf=None):
    extra = {'REMOTE_ADDR': remote}
    if xff is not None:
        extra['HTTP_X_FORWARDED_FOR'] = xff
    if cf is not None:
        extra['HTTP_CF_CONNECTING_IP'] = cf
    return RequestFactory().get('/public/', **extra)


class DernierSautDeConfianceTests(SimpleTestCase):
    """La primitive ne rend JAMAIS la valeur choisie par l'appelant."""

    def test_le_saut_forge_en_tete_est_ignore(self):
        self.assertEqual(
            ip_de_requete(_requete(xff='%s, 203.0.113.9' % _FORGEE)),
            '203.0.113.9')

    def test_num_proxies_saute_nos_propres_proxies(self):
        """``NUM_PROXIES=1`` : notre proxy ajoute UNE entrée, on la saute."""
        with override_settings(NUM_PROXIES=1):
            self.assertEqual(
                ip_de_requete(_requete(
                    xff='%s, 203.0.113.9, 10.0.0.7' % _FORGEE)),
                '203.0.113.9')

    def test_une_chaine_plus_courte_que_les_proxies_declares_ne_leve_pas(self):
        with override_settings(NUM_PROXIES=5):
            self.assertEqual(
                ip_de_requete(_requete(xff='203.0.113.9')), '203.0.113.9')

    def test_cf_connecting_ip_n_est_pas_honore_par_defaut(self):
        """Un en-tête Cloudflare est DÉCLARATIF : forgeable sans configuration."""
        self.assertEqual(
            ip_de_requete(_requete(xff=None, remote='198.51.100.4',
                                   cf=_FORGEE)),
            '198.51.100.4')

    def test_cf_connecting_ip_honore_quand_le_deploiement_le_declare(self):
        with override_settings(CF_CONNECTING_IP_TRUSTED=True):
            self.assertEqual(
                ip_de_requete(_requete(xff=None, remote='198.51.100.4',
                                       cf='203.0.113.77')),
                '203.0.113.77')

    def test_sans_en_tete_on_lit_le_pair_tcp(self):
        self.assertEqual(
            ip_de_requete(_requete(xff=None, remote='198.51.100.4')),
            '198.51.100.4')

    def test_une_requete_absente_ne_leve_pas(self):
        self.assertEqual(ip_de_requete(None), '')

    def test_visites_delegue_a_la_primitive(self):
        requete = _requete(xff='%s, 203.0.113.9' % _FORGEE)
        self.assertEqual(visites.ip_de_requete(requete),
                         ip_de_requete(requete))


class PreuveLegaleTests(SimpleTestCase):
    """(i) — le champ de preuve de la signature électronique."""

    def test_l_ip_de_preuve_est_le_dernier_saut_de_confiance(self):
        """ROUGE avant QJR416 : rendait « 9.9.9.9 », la valeur forgée."""
        requete = _requete(xff='%s, 203.0.113.9' % _FORGEE)
        self.assertEqual(ventes_public._client_ip(requete), '203.0.113.9')
        self.assertNotEqual(ventes_public._client_ip(requete), _FORGEE)


class SeauxDeLimitationTests(SimpleTestCase):
    """(ii) — deux origines réelles distinctes ⇒ deux seaux."""

    @staticmethod
    def _vue():
        return SimpleNamespace(kwargs={'token': 'jeton-qjr416'})

    def test_meme_xff_forge_mais_origines_distinctes_donnent_deux_seaux(self):
        """ROUGE avant QJR416 : les deux tombaient dans le MÊME seau."""
        throttle = ventes_public.PublicLinkRateThrottle()
        a = throttle.get_cache_key(
            _requete(xff='%s, 203.0.113.1' % _FORGEE), self._vue())
        b = throttle.get_cache_key(
            _requete(xff='%s, 203.0.113.2' % _FORGEE), self._vue())
        self.assertNotEqual(a, b)
        self.assertNotIn(_FORGEE, a)

    def test_les_trois_throttles_publics_partagent_la_primitive(self):
        requete = _requete(xff='%s, 203.0.113.5' % _FORGEE)
        for classe in (ventes_public.PublicLinkRateThrottle,
                       crm_public.PublicSalleVenteRateThrottle,
                       crm_public.PublicApporteurRateThrottle):
            with self.subTest(classe=classe.__name__):
                self.assertEqual(classe().get_ident(requete), '203.0.113.5')

    def test_sans_en_tete_le_seau_suit_le_pair_tcp(self):
        """Aucun en-tête : le seau reste celui du pair TCP, comme avant."""
        requete = _requete(xff=None, remote='198.51.100.4')
        self.assertEqual(
            ventes_public.PublicLinkRateThrottle().get_ident(requete),
            '198.51.100.4')


class IdentifiantVisiteurSaleTests(SimpleTestCase):
    """(iii) — le journal de consultation distingue à nouveau les visiteurs."""

    _SALLE_A = SimpleNamespace(token='salle-aaaa')
    _SALLE_B = SimpleNamespace(token='salle-bbbb')

    def test_deux_visiteurs_d_un_meme_lien_produisent_deux_identifiants(self):
        """ROUGE avant QJR416 : derrière le proxy, tous partageaient la MÊME
        empreinte (SHA-256 de ``REMOTE_ADDR``, constant)."""
        proxy = '10.0.0.9'   # la sortie du proxy, identique pour les deux
        un = crm_public._hash_ip(
            _requete(xff='%s, 203.0.113.1' % _FORGEE, remote=proxy),
            self._SALLE_A)
        deux = crm_public._hash_ip(
            _requete(xff='%s, 203.0.113.2' % _FORGEE, remote=proxy),
            self._SALLE_A)
        self.assertTrue(un and deux)
        self.assertNotEqual(un, deux)

    def test_un_meme_visiteur_sur_deux_liens_produit_deux_identifiants(self):
        """Sel PAR LIEN : aucun recoupement d'une salle à l'autre."""
        requete = _requete(xff='%s, 203.0.113.1' % _FORGEE)
        self.assertNotEqual(
            crm_public._hash_ip(requete, self._SALLE_A),
            crm_public._hash_ip(requete, self._SALLE_B))

    def test_le_meme_visiteur_sur_le_meme_lien_est_stable(self):
        requete = _requete(xff='%s, 203.0.113.1' % _FORGEE)
        self.assertEqual(
            crm_public._hash_ip(requete, self._SALLE_A),
            crm_public._hash_ip(requete, self._SALLE_A))

    def test_aucune_ip_en_clair_dans_l_identifiant(self):
        empreinte = crm_public._hash_ip(
            _requete(xff='%s, 203.0.113.1' % _FORGEE), self._SALLE_A)
        self.assertNotIn('203.0.113.1', empreinte)
        self.assertNotIn(_FORGEE, empreinte)
        self.assertEqual(len(empreinte), 64)  # SHA-256 hex

    def test_sans_ip_lisible_l_identifiant_est_vide(self):
        requete = RequestFactory().get('/public/')
        requete.META.pop('REMOTE_ADDR', None)
        self.assertEqual(crm_public._hash_ip(requete, self._SALLE_A), '')


class UneSeuleLectureDIpTests(SimpleTestCase):
    """Quatrième test du `Done` : plus aucune lecture d'IP à la main sur les
    TROIS surfaces de cette tâche.

    PÉRIMÈTRE, DÉCLARÉ HONNÊTEMENT. QJR416 possède cinq fichiers
    (``crm/visites.py``, ``ventes/public_views.py``, ``crm/public_views.py``,
    ``core/throttling.py`` + ce test) : la garde porte donc sur EUX. D'autres
    modules du dépôt (rh, contrats, btp_chantier, identity, ged, portail,
    authentication, core/views, crm/webhooks) portent encore leur propre
    lecture — ils appartiennent à d'autres lanes et ne sont PAS touchés ici
    (règle permanente 3 : un écrivain unique par fichier). Cette garde empêche
    au moins les trois surfaces corrigées de régresser.
    """

    _EN_TETES = ('HTTP_X_FORWARDED_FOR', 'HTTP_CF_CONNECTING_IP',
                 'REMOTE_ADDR')

    _SURFACES = (
        'apps/crm/visites.py',
        'apps/crm/public_views.py',
        'apps/ventes/public_views.py',
    )

    def test_aucune_surface_corrigee_ne_lit_un_en_tete_d_ip(self):
        """Aucun ``…get('HTTP_X_FORWARDED_FOR')`` / ``…get('REMOTE_ADDR')`` :
        seules les MENTIONS en prose subsistent (elles expliquent le
        correctif), jamais une lecture."""
        # …/backend/django_core/apps/crm/tests/<ce fichier> → django_core
        racine = Path(__file__).resolve().parents[3]
        fautifs = []
        for chemin in self._SURFACES:
            arbre = ast.parse(
                (racine / chemin).read_text(encoding='utf-8'))
            for noeud in ast.walk(arbre):
                if not (isinstance(noeud, ast.Call)
                        and isinstance(noeud.func, ast.Attribute)
                        and noeud.func.attr in ('get', 'pop')):
                    continue
                for argument in noeud.args:
                    if (isinstance(argument, ast.Constant)
                            and argument.value in self._EN_TETES):
                        fautifs.append('%s:%d — %s'
                                       % (chemin, noeud.lineno,
                                          argument.value))
        self.assertEqual(fautifs, [],
                         'lectures d\'IP à la main : %r' % (fautifs,))

    def test_la_primitive_est_bien_dans_la_fondation(self):
        """``core`` est une couche de BASE : la primitive doit y vivre pour que
        ``core.throttling`` puisse la servir sans importer une app (contrat
        import-linter ``core-foundation-is-a-base-layer``)."""
        import core.throttling as noyau

        self.assertTrue(callable(noyau.ip_de_requete))
        source = Path(noyau.__file__).read_text(encoding='utf-8')
        arbre = ast.parse(source)
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                module = getattr(noeud, 'module', '') or ''
                noms = [a.name for a in noeud.names]
                for cible in [module] + noms:
                    self.assertFalse(
                        str(cible).startswith('apps.'),
                        'core.throttling importe %s (contrat base-layer)'
                        % cible)
