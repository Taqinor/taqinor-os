"""Tests du moteur NATIF de l'assistant (boucle d'outils sur l'API Messages).

Aucune clé, aucun réseau : un FAUX client rejoue des réponses JSON scriptées
(forme brute de l'API Messages) et un FAUX Redis garde la conversation. Un test
passe par le VRAI SDK installé avec un transport httpx simulé, pour vérifier le
corps réellement envoyé. Lancer depuis backend/fastapi_ia :

    DJANGO_SECRET_KEY=test-secret python -m unittest tests.test_moteur_natif -v
"""
import copy
import json
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import moteur_natif as mn  # noqa: E402 — après sys.path (D-ENF22)

MODELE = "claude-sonnet-5-5"
SYSTEME = [{"type": "text", "text": "Consignes stables."}]


def _rep(contenu, stop="end_turn", usage=None, **extra):
    """Une réponse brute de l'API Messages."""
    corps = {"id": "msg", "type": "message", "role": "assistant", "model": MODELE,
             "content": contenu, "stop_reason": stop,
             "usage": usage or {"input_tokens": 10, "output_tokens": 5,
                                "cache_read_input_tokens": 100,
                                "cache_creation_input_tokens": 20}}
    corps.update(extra)
    return corps


def _texte(t):
    return {"type": "text", "text": t}


def _appel(id_, nom, entrees=None):
    return {"type": "tool_use", "id": id_, "name": nom, "input": entrees or {}}


class _Erreur400(Exception):
    status_code = 400


class _Http:
    def __init__(self, corps):
        self._corps = corps

    def json(self):
        return copy.deepcopy(self._corps)


class FauxClient:
    """``client.messages.with_raw_response.create(**corps)`` scripté : chaque
    élément de ``reponses`` est un dict (réponse) ou une exception (levée)."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []
        self.messages = self
        self.with_raw_response = self

    def create(self, **corps):
        self.appels.append(copy.deepcopy(corps))
        suivant = self.reponses.pop(0)
        if isinstance(suivant, BaseException):
            raise suivant
        return mock.Mock(http_response=_Http(suivant))


def _outil(nom, fonction=None):
    return mn.OutilNatif(nom=nom, description="Outil %s." % nom,
                         schema={"type": "object", "properties": {}},
                         executer=fonction or (lambda entrees: "ok %s" % nom))


class _Base(unittest.TestCase):
    def jouer(self, reponses, outils=(), question="Bonjour", conversation="",
              **kw):
        self.client = FauxClient(reponses)
        with mock.patch.object(mn, "_client", return_value=self.client):
            return mn.executer(question=question, systeme=SYSTEME,
                               outils=list(outils), conversation=conversation,
                               modele=MODELE, **kw)


class BoucleTests(_Base):
    def test_fin_simple_rend_le_texte_sans_la_pensee(self):
        r = self.jouer([_rep([{"type": "thinking", "thinking": "secret",
                               "signature": "s"}, _texte("Voici.")])])
        self.assertEqual(r["answer"], "Voici.")
        self.assertEqual(r["arret"], mn.ARRET_FIN)
        self.assertEqual(r["outils_appeles"], [])
        self.assertEqual(r["modele"], MODELE)

    def test_appariement_tool_use_tool_result_et_plusieurs_outils(self):
        vus = []
        outils = [_outil("a", lambda e: vus.append(("a", e)) or "res a"),
                  _outil("b", lambda e: vus.append(("b", e)) or "res b")]
        r = self.jouer([
            _rep([_texte("Je cherche."), _appel("t1", "a", {"x": 1}),
                  _appel("t2", "b", {"y": 2})], stop="tool_use"),
            _rep([_texte("Fini.")])], outils)
        self.assertEqual(vus, [("a", {"x": 1}), ("b", {"y": 2})])
        self.assertEqual(r["outils_appeles"], ["a", "b"])
        retour = self.client.appels[1]["messages"][-1]
        self.assertEqual(retour["role"], "user")
        self.assertEqual([(b["type"], b["tool_use_id"], b["content"])
                          for b in retour["content"]],
                         [("tool_result", "t1", "res a"), ("tool_result", "t2", "res b")])
        self.assertNotIn("is_error", retour["content"][0])

    def test_pensee_conservee_telle_quelle_dans_le_tour(self):
        pensee = {"type": "thinking", "thinking": "", "signature": "sig-1"}
        inconnu = {"type": "bloc_futur_2027", "charge": {"a": [1, 2]}}
        reponse1 = [pensee, inconnu, _appel("t1", "a")]
        self.jouer([_rep(reponse1, stop="tool_use"), _rep([_texte("ok")])],
                   [_outil("a")])
        assistant = self.client.appels[1]["messages"][1]
        self.assertEqual(assistant, {"role": "assistant", "content": reponse1})

    def test_outil_qui_leve_rend_une_erreur_et_continue(self):
        def casse(_e):
            raise ValueError("boum interne")
        r = self.jouer([_rep([_appel("t1", "a")], stop="tool_use"),
                        _rep([_texte("Désolé.")])], [_outil("a", casse)])
        res = self.client.appels[1]["messages"][-1]["content"][0]
        self.assertTrue(res["is_error"])
        self.assertIn("ValueError", res["content"])
        self.assertNotIn("boum interne", res["content"])
        self.assertEqual(r["arret"], mn.ARRET_FIN)
        self.assertEqual(r["outils_appeles"], ["a"])

    def test_outil_inconnu_rend_une_erreur_sans_exception(self):
        r = self.jouer([_rep([_appel("t1", "fantome")], stop="tool_use"),
                        _rep([_texte("Ok.")])], [_outil("a")])
        res = self.client.appels[1]["messages"][-1]["content"][0]
        self.assertEqual(res["tool_use_id"], "t1")
        self.assertTrue(res["is_error"])
        self.assertEqual(r["outils_appeles"], [])

    def test_nom_d_outil_a_la_casse_pres_est_accepte(self):
        r = self.jouer([_rep([_appel("t1", "CRM_Lead")], stop="tool_use"),
                        _rep([_texte("Ok.")])], [_outil("crm_lead")])
        self.assertEqual(r["outils_appeles"], ["crm_lead"])

    def test_usage_cumule_sur_le_tour(self):
        r = self.jouer([_rep([_appel("t1", "a")], stop="tool_use"),
                        _rep([_texte("Ok.")], usage={
                            "input_tokens": 1, "output_tokens": 2,
                            "cache_read_input_tokens": None})], [_outil("a")])
        self.assertEqual(r["tokens"], {"input": 11, "output": 7,
                                       "cache_read": 100, "cache_write": 20})

    def test_refus(self):
        r = self.jouer([_rep([], stop="refusal",
                             stop_details={"category": "general_harms"})])
        self.assertEqual(r["arret"], mn.ARRET_REFUS)
        self.assertIn("Reformule", r["answer"])

    def test_max_tokens_avec_texte(self):
        r = self.jouer([_rep([_texte("Début de réponse")], stop="max_tokens")])
        self.assertEqual(r["arret"], mn.ARRET_LIMITE)
        self.assertTrue(r["answer"].startswith("Début de réponse"))

    def test_max_tokens_en_plein_appel_d_outil_ne_l_execute_pas(self):
        vus = []
        r = self.jouer([_rep([_appel("t1", "a", {"x": 1})], stop="max_tokens")],
                       [_outil("a", lambda e: vus.append(e) or "x")])
        self.assertEqual(vus, [])
        self.assertEqual(r["arret"], mn.ARRET_LIMITE)

    def test_limite_d_iterations_reponse_francaise_honnete(self):
        boucle = [_rep([_texte("J'avance."), _appel("t%d" % i, "a")],
                       stop="tool_use") for i in range(3)]
        vus = []
        r = self.jouer(boucle, [_outil("a", lambda e: vus.append(1) or "x")],
                       max_iterations=3)
        self.assertEqual(r["arret"], mn.ARRET_LIMITE)
        self.assertEqual(len(self.client.appels), 3)
        self.assertEqual(len(vus), 2)  # les outils du DERNIER appel ne tournent pas
        self.assertIn("Déjà fait", r["answer"])
        self.assertIn("Le reste n'est pas fait", r["answer"])

    def test_400_pensee_retire_toutes_les_pensees_et_reessaie_une_fois(self):
        pensee = {"type": "thinking", "thinking": "", "signature": "s"}
        r = self.jouer([
            _rep([pensee, _appel("t1", "a")], stop="tool_use"),
            _Erreur400("Invalid signature in thinking block"),
            _rep([_texte("Repris.")])], [_outil("a")])
        self.assertEqual(r["answer"], "Repris.")
        self.assertEqual(len(self.client.appels), 3)
        self.assertIn(pensee, self.client.appels[1]["messages"][1]["content"])
        rejoue = json.dumps(self.client.appels[2]["messages"])
        self.assertNotIn('"thinking"', rejoue)
        self.assertIn('"tool_use"', rejoue)

    def test_400_pensee_deux_fois_ne_reessaie_qu_une_fois(self):
        pensee = {"type": "thinking", "thinking": "", "signature": "s"}
        r = self.jouer([
            _rep([pensee, _appel("t1", "a")], stop="tool_use"),
            _Erreur400("thinking signature"), _Erreur400("thinking signature")],
            [_outil("a")])
        self.assertEqual(r["arret"], mn.ARRET_ERREUR)
        self.assertEqual(len(self.client.appels), 3)

    def test_erreur_avant_tout_outil_leve_moteur_indisponible(self):
        with self.assertRaises(mn.MoteurIndisponible):
            self.jouer([RuntimeError("529 overloaded")])

    def test_erreur_apres_un_outil_rend_une_fin_honnete(self):
        r = self.jouer([_rep([_appel("t1", "a")], stop="tool_use"),
                        RuntimeError("500")], [_outil("a")])
        self.assertEqual(r["arret"], mn.ARRET_ERREUR)
        self.assertIn("a", r["outils_appeles"])
        self.assertIn("Déjà fait", r["answer"])

    def test_cle_absente_moteur_indisponible(self):
        with mock.patch("app.core.config.CLAUDE_API_KEY", ""):
            with self.assertRaises(mn.MoteurIndisponible):
                mn.executer(question="x", systeme=SYSTEME, outils=[],
                            conversation="", modele=MODELE)

    def test_parametres_de_la_requete(self):
        self.jouer([_rep([_texte("ok")])], [_outil("a")], effort="Medium",
                   max_tokens=2048)
        corps = self.client.appels[0]
        self.assertEqual(corps["thinking"], {"type": "adaptive"})
        self.assertEqual(corps["output_config"], {"effort": "medium"})
        self.assertEqual(corps["tool_choice"], {"type": "auto"})
        self.assertEqual(corps["max_tokens"], 2048)
        self.assertEqual(corps["model"], MODELE)
        self.assertEqual([t["name"] for t in corps["tools"]], ["a"])


class CacheTests(_Base):
    UNE_HEURE = {"type": "ephemeral", "ttl": "1h"}

    def test_points_de_cache(self):
        systeme = [{"type": "text", "text": "A",
                    "cache_control": {"type": "ephemeral"}},
                   {"type": "text", "text": "B"}]
        self.client = FauxClient([_rep([_appel("t1", "z")], stop="tool_use"),
                                  _rep([_texte("ok")])])
        with mock.patch.object(mn, "_client", return_value=self.client):
            mn.executer(question="q", systeme=systeme,
                        outils=[_outil("z"), _outil("a"), _outil("m")],
                        conversation="", modele=MODELE)
        for corps in self.client.appels:
            self.assertEqual(corps["system"][-1]["cache_control"], self.UNE_HEURE)
            self.assertNotIn("cache_control", corps["system"][0])
            self.assertEqual(corps["cache_control"], self.UNE_HEURE)
            self.assertEqual([t["name"] for t in corps["tools"]], ["z", "a", "m"])
            self.assertFalse(any("cache_control" in t for t in corps["tools"]))
            self.assertNotIn("cache_control", json.dumps(corps["messages"]))
            self.assertLessEqual(json.dumps(corps).count('"cache_control"'), 4)
        self.assertNotIn("cache_control", systeme[1])  # entrée non modifiée

    def test_sans_systeme_le_point_va_sur_le_dernier_outil(self):
        self.client = FauxClient([_rep([_texte("ok")])])
        with mock.patch.object(mn, "_client", return_value=self.client):
            mn.executer(question="q", systeme=[], outils=[_outil("a"), _outil("b")],
                        conversation="", modele=MODELE)
        corps = self.client.appels[0]
        self.assertNotIn("system", corps)
        self.assertEqual(corps["tools"][-1]["cache_control"], self.UNE_HEURE)
        self.assertNotIn("cache_control", corps["tools"][0])


class VraiSdkTests(unittest.TestCase):
    """Le corps RÉELLEMENT sérialisé par le SDK installé (transport simulé)."""

    def test_corps_envoye_par_le_sdk(self):
        # Le SDK est une dépendance du service : son absence doit faire ÉCHOUER
        # ce test (jamais le sauter en silence — ENF23).
        import anthropic
        import httpx
        envoyes = []
        inconnu = {"type": "bloc_futur_2027", "x": 1}
        reponses = [_rep([inconnu, _appel("t1", "a")], stop="tool_use"),
                    _rep([_texte("ok")])]

        def transport(requete):
            envoyes.append(json.loads(requete.content))
            return httpx.Response(200, json=reponses.pop(0))
        client = anthropic.Anthropic(api_key="k", max_retries=0,
                                     http_client=httpx.Client(
                                         transport=httpx.MockTransport(transport)))
        with mock.patch.object(mn, "_client", return_value=client):
            r = mn.executer(question="q", systeme=SYSTEME, outils=[_outil("a")],
                            conversation="", modele=MODELE)
        self.assertEqual(r["answer"], "ok")
        self.assertEqual(envoyes[1]["messages"][1]["content"][0], inconnu)
        self.assertEqual(envoyes[0]["cache_control"], {"type": "ephemeral", "ttl": "1h"})
        self.assertEqual(envoyes[0]["thinking"], {"type": "adaptive"})

    def test_image_envoyee_par_le_sdk(self):
        """F5 — le bloc image (forme des types du SDK installé : source base64)
        part tel quel, avant le texte de la question, après l'avis « DONNÉE »."""
        import anthropic
        import httpx
        envoyes = []

        def transport(requete):
            envoyes.append(json.loads(requete.content))
            return httpx.Response(200, json=_rep([_texte("Lu.")]))
        client = anthropic.Anthropic(api_key="k", max_retries=0, http_client=httpx.Client(
            transport=httpx.MockTransport(transport)))
        with mock.patch.object(mn, "_client", return_value=client):
            r = mn.executer(question="q", systeme=SYSTEME, outils=[], conversation="",
                            modele=MODELE, images=[IMAGE])
        self.assertEqual(r["answer"], "Lu.")
        self.assertEqual(envoyes[0]["messages"][0]["content"], [
            _texte(mn.AVIS_IMAGES),
            {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                         "data": IMAGE["data"]}},
            _texte("q")])


#: Une image PNG minimale (signature + octets nuls), en base64.
IMAGE = {"media_type": "image/png",
         "data": "iVBORw0KGgoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}


class FauxRedis:
    def __init__(self):
        self.donnees, self.durees = {}, {}

    def get(self, cle):
        return self.donnees.get(cle)

    def set(self, cle, valeur, ex=None):
        self.donnees[cle], self.durees[cle] = valeur, ex

    def delete(self, cle):
        self.donnees.pop(cle, None)


class _Interruption(BaseException):
    """Le processus meurt en plein tour (rien ne doit être gardé)."""


class ConversationTests(_Base):
    CONV = "7:42"

    def setUp(self):
        self.redis = FauxRedis()
        patch = mock.patch.object(mn, "_redis", return_value=self.redis)
        patch.start()
        self.addCleanup(patch.stop)

    def garde(self):
        brut = self.redis.donnees.get(mn.CLE_CONVERSATION % self.CONV)
        return json.loads(brut) if brut else None

    def tour_outil(self, question="Q1", modele=None, outils=None):
        self.client = FauxClient([
            _rep([_appel("t1", "a")], stop="tool_use"), _rep([_texte("R1")])])
        with mock.patch.object(mn, "_client", return_value=self.client):
            return mn.executer(question=question, systeme=SYSTEME,
                               outils=outils or [_outil("a")],
                               conversation=self.CONV, modele=modele or MODELE)

    def test_conversation_gardee_48h_avec_ses_blocs_d_outils(self):
        self.tour_outil()
        etat = self.garde()
        self.assertEqual(set(etat), {"version", "modele", "empreinte_outils",
                                     "messages", "contenu_tiers"})
        self.assertEqual(etat["modele"], MODELE)
        self.assertEqual([m["role"] for m in etat["messages"]],
                         ["user", "assistant", "user", "assistant"])
        self.assertEqual(self.redis.durees[mn.CLE_CONVERSATION % self.CONV],
                         48 * 3600)

    def test_image_jamais_gardee_dans_la_conversation(self):
        """F5 — l'image vit le temps de SON tour : la conversation gardée la
        remplace par un texte et perd ses blocs de pensée (le passé a changé) ;
        le tour suivant repart de ce passé, sans l'image ; le récapitulatif lit
        la question."""
        pensee = {"type": "thinking", "thinking": "", "signature": "sig-1"}
        self.client = FauxClient([_rep([pensee, _appel("t1", "a")], stop="tool_use"),
                                  _rep([pensee, _texte("C'est M. Essai.")])])
        with mock.patch.object(mn, "_client", return_value=self.client):
            mn.executer(question="Lis la capture", systeme=SYSTEME, outils=[_outil("a")],
                        conversation=self.CONV, modele=MODELE, images=[IMAGE, IMAGE])
        envoye = self.client.appels[0]["messages"][0]["content"]
        self.assertEqual([b["type"] for b in envoye], ["text", "image", "image", "text"])
        brut = self.redis.donnees[mn.CLE_CONVERSATION % self.CONV]
        self.assertNotIn(IMAGE["data"], brut)
        self.assertNotIn('"image"', brut)
        self.assertNotIn("thinking", brut)
        garde = self.garde()["messages"]
        self.assertEqual([b["text"] for b in garde[0]["content"]],
                         [mn.AVIS_IMAGES, mn.IMAGE_NON_GARDEE, mn.IMAGE_NON_GARDEE, "Lis la capture"])
        self.assertTrue(mn._point_sur(garde))
        self.assertEqual(mn._echanges(garde)[0][0], "Lis la capture")
        r = self.jouer([_rep([_texte("R2")])], [_outil("a")], question="Q2", conversation=self.CONV)
        self.assertEqual(r["answer"], "R2")
        self.assertEqual(self.client.appels[0]["messages"][:len(garde)], garde)

    def test_second_tour_en_ajout_seul(self):
        self.tour_outil()
        avant = self.garde()["messages"]
        r = self.jouer([_rep([_texte("R2")])], [_outil("a")], question="Q2",
                       conversation=self.CONV)
        envoyes = self.client.appels[0]["messages"]
        self.assertEqual(envoyes[:len(avant)], avant)
        self.assertEqual(envoyes[-1]["content"], [_texte("Q2")])
        self.assertEqual(self.garde()["messages"][:len(avant)], avant)
        self.assertEqual(r["answer"], "R2")

    def test_marque_a5_gardee_avec_la_conversation_et_dite_quand_elle_est_relue(self):
        """Revue F3 #3 — la conversation gardée porte `contenu_tiers` (ce que dit l'appelant en fin de
        tour ; sans appelant : marquée, échec fermé). Au tour suivant, `noter_relu_tiers` est appelé
        AVANT le modèle si le passé relu (tel quel ou récapitulé) est marqué, ou s'il ne dit rien
        (conversation gardée avant la correction)."""
        relus = []

        def tour(marque, question="Q"):
            self.jouer([_rep([_texte("R")])], question=question, conversation=self.CONV,
                       marque_du_tour=marque, noter_relu_tiers=lambda: relus.append(question))
        tour(lambda: True, "Q1")
        self.assertEqual((relus, self.garde()["contenu_tiers"]), ([], True))  # rien relu au 1er tour
        tour(lambda: False, "Q2")
        self.assertEqual((relus, self.garde()["contenu_tiers"]), (["Q2"], False))
        tour(lambda: False, "Q3")
        self.assertEqual(relus, ["Q2"])
        etat = self.garde()
        del etat["contenu_tiers"]  # conversation gardée avant la correction
        self.redis.set(mn.CLE_CONVERSATION % self.CONV, json.dumps(etat))
        tour(lambda: False, "Q4")
        self.assertEqual(relus, ["Q2", "Q4"])
        self.jouer([_rep([_texte("R")])], question="Q5", conversation=self.CONV)
        self.assertIs(self.garde()["contenu_tiers"], True)  # appelant muet : marquée
        self.redis.set(mn.CLE_CONVERSATION % self.CONV, json.dumps({**self.garde(), "modele": "autre"}))
        tour(lambda: False, "Q6")  # repart d'un récapitulatif : le texte marqué est encore relu
        self.assertEqual(relus, ["Q2", "Q4", "Q6"])
        mn.effacer(self.CONV)
        tour(lambda: False, "Q7")  # « Effacer » : plus rien de relu, la marque tombe
        self.assertEqual(relus, ["Q2", "Q4", "Q6"])

    def test_rien_n_est_garde_si_le_tour_meurt_en_route(self):
        self.tour_outil()
        avant = self.garde()

        def meurt(_e):
            raise _Interruption()
        with self.assertRaises(_Interruption):
            self.jouer([_rep([_appel("t9", "a")], stop="tool_use")],
                       [_outil("a", meurt)], conversation=self.CONV)
        self.assertEqual(self.garde(), avant)

    def test_point_sur(self):
        paire = [{"role": "user", "content": [_texte("q")]},
                 {"role": "assistant", "content": [_appel("t1", "a")]},
                 {"role": "user", "content": [
                     {"type": "tool_result", "tool_use_id": "t1", "content": "r"}]},
                 {"role": "assistant", "content": [_texte("fin")]}]
        self.assertTrue(mn._point_sur(paire))
        self.assertFalse(mn._point_sur(paire[:2]))
        self.assertFalse(mn._point_sur(paire[:3]))
        orphelin = paire[:2] + [{"role": "assistant", "content": [_texte("x")]}]
        self.assertFalse(mn._point_sur(orphelin))
        mn._ecrire(self.CONV, MODELE, "e", paire[:2])
        self.assertIsNone(self.garde())

    def _verifier_recommence(self, envoyes):
        self.assertEqual(len(envoyes), 1)
        recap, question = envoyes[0]["content"]
        self.assertIn("Récapitulatif", recap["text"])
        self.assertIn("Q1", recap["text"])
        self.assertIn("R1", recap["text"])
        self.assertNotIn("tool_use", json.dumps(envoyes))
        self.assertNotIn("Contexte donné par l'ERP", recap["text"])
        self.assertEqual(question, _texte("Q2"))

    def test_changement_de_modele_repart_d_un_recapitulatif(self):
        from app.services.prompt_copilote import entete_tour
        self.tour_outil(question=entete_tour() + "\nQ1")
        self.client = FauxClient([_rep([_texte("R2")])])
        with mock.patch.object(mn, "_client", return_value=self.client):
            mn.executer(question="Q2", systeme=SYSTEME, outils=[_outil("a")],
                        conversation=self.CONV, modele="claude-opus-5-5")
        self._verifier_recommence(self.client.appels[0]["messages"])
        self.assertEqual(self.garde()["modele"], "claude-opus-5-5")

    def test_longueur_depassee_repart_d_un_recapitulatif(self):
        self.tour_outil()
        with mock.patch.object(mn, "MAX_TOURS_GARDES", 1):
            self.jouer([_rep([_texte("R2")])], [_outil("a")], question="Q2",
                       conversation=self.CONV)
        self._verifier_recommence(self.client.appels[0]["messages"])

    def test_taille_depassee_repart_d_un_recapitulatif(self):
        self.tour_outil()
        with mock.patch.object(mn, "MAX_CARACTERES_GARDES", 50):
            self.jouer([_rep([_texte("R2")])], [_outil("a")], question="Q2",
                       conversation=self.CONV)
        self._verifier_recommence(self.client.appels[0]["messages"])

    def test_outils_changes_repart_d_un_recapitulatif(self):
        self.tour_outil()
        self.jouer([_rep([_texte("R2")])], [_outil("a"), _outil("b")],
                   question="Q2", conversation=self.CONV)
        self._verifier_recommence(self.client.appels[0]["messages"])

    def test_refus_ne_garde_pas_le_tour(self):
        self.tour_outil()
        avant = self.garde()
        r = self.jouer([_rep([], stop="refusal")], [_outil("a")],
                       conversation=self.CONV)
        self.assertEqual(r["arret"], mn.ARRET_REFUS)
        self.assertEqual(self.garde(), avant)

    def test_fenetre_depassee_oublie_la_conversation(self):
        self.tour_outil()
        r = self.jouer([_rep([], stop="model_context_window_exceeded")],
                       [_outil("a")], conversation=self.CONV)
        self.assertEqual(r["arret"], mn.ARRET_LIMITE)
        self.assertIsNone(self.garde())

    def test_limite_garde_un_point_sur(self):
        self.jouer([_rep([_appel("t%d" % i, "a")], stop="tool_use")
                    for i in range(2)], [_outil("a")], conversation=self.CONV,
                   max_iterations=2)
        messages = self.garde()["messages"]
        self.assertTrue(mn._point_sur(messages))
        self.assertIn("trop d'étapes", messages[-1]["content"][0]["text"])

    def test_400_pensee_retrait_garde(self):
        pensee = {"type": "thinking", "thinking": "", "signature": "s"}
        self.jouer([_rep([pensee, _appel("t1", "a")], stop="tool_use"),
                    _Erreur400("thinking: invalid signature"),
                    _rep([_texte("ok")])], [_outil("a")], conversation=self.CONV)
        self.assertNotIn('"thinking"', json.dumps(self.garde()["messages"]))

    def test_effacer(self):
        self.tour_outil()
        mn.effacer(self.CONV)
        self.assertIsNone(self.garde())

    def reprendre(self, reponses, message="[Résultat de l'ERP] confirmé"):
        self.client = FauxClient(reponses)
        with mock.patch.object(mn, "_client", return_value=self.client):
            return mn.reprendre(conversation=self.CONV, message=message,
                                systeme=SYSTEME, outils=[_outil("a")],
                                modele=MODELE)

    def test_reprendre_sans_conversation_rend_none(self):
        self.assertIsNone(self.reprendre([]))
        self.assertEqual(self.client.appels, [])

    def test_reprendre_apres_confirmation_continue_la_tache(self):
        self.tour_outil()
        avant = self.garde()["messages"]
        r = self.reprendre([_rep([_appel("t5", "a")], stop="tool_use"),
                            _rep([_texte("Étape suivante faite.")])])
        envoyes = self.client.appels[0]["messages"]
        self.assertEqual(envoyes[:len(avant)], avant)
        self.assertEqual(envoyes[len(avant)], {"role": "user", "content": [
            _texte("[Résultat de l'ERP] confirmé")]})
        self.assertEqual(r["answer"], "Étape suivante faite.")
        self.assertEqual(r["outils_appeles"], ["a"])
        self.assertEqual(r["arret"], mn.ARRET_FIN)
        self.assertEqual(len(self.garde()["messages"]), len(avant) + 4)


def _differe(nom, fonction=None):
    import dataclasses
    return dataclasses.replace(_outil(nom, fonction), differe=True)


def _references(*noms):
    return [{"type": "tool_reference", "tool_name": n} for n in noms]


class DiffereTests(_Base):
    """Copilote vague 2 (FND3) — outils différés : `defer_loading`, point de
    cache jamais sur un différé, résultat en liste posé tel quel, empreinte."""
    UNE_HEURE = {"type": "ephemeral", "ttl": "1h"}

    def test_differes_marques_et_ranges_apres_les_non_differes(self):
        self.jouer([_rep([_texte("ok")])],
                   [_differe("z_lire"), _outil("noyau_b"), _differe("c_lire"), _outil("noyau_a")])
        tools = self.client.appels[0]["tools"]
        self.assertEqual([t["name"] for t in tools], ["noyau_b", "noyau_a", "c_lire", "z_lire"])
        self.assertEqual([t.get("defer_loading") for t in tools], [None, None, True, True])
        self.assertFalse(any("cache_control" in t for t in tools))  # système présent

    def test_sans_systeme_le_point_va_sur_le_dernier_non_differe(self):
        self.client = FauxClient([_rep([_texte("ok")])])
        with mock.patch.object(mn, "_client", return_value=self.client):
            mn.executer(question="q", systeme=[], conversation="", modele=MODELE,
                        outils=[_outil("a"), _differe("d"), _outil("b")])
        tools = self.client.appels[0]["tools"]
        self.assertEqual([t["name"] for t in tools], ["a", "b", "d"])
        self.assertEqual(tools[1]["cache_control"], self.UNE_HEURE)
        self.assertNotIn("cache_control", tools[2])

    def test_tous_differes_rien_n_est_differe(self):
        self.jouer([_rep([_texte("ok")])], [_differe("b"), _differe("a")])
        tools = self.client.appels[0]["tools"]
        self.assertEqual([t["name"] for t in tools], ["b", "a"])
        self.assertFalse(any("defer_loading" in t for t in tools))

    def test_sans_differe_corps_d_avant(self):
        self.jouer([_rep([_texte("ok")])], [_outil("z"), _outil("a")])
        self.assertEqual(self.client.appels[0]["tools"], [
            {"name": "z", "description": "Outil z.", "input_schema": {"type": "object", "properties": {}}},
            {"name": "a", "description": "Outil a.", "input_schema": {"type": "object", "properties": {}}}])

    def test_resultat_en_liste_pose_tel_quel(self):
        self.jouer([_rep([_appel("t1", "charger")], stop="tool_use"), _rep([_texte("ok")])],
                   [_outil("charger", lambda e: _references("x_lire")), _differe("x_lire")])
        res = self.client.appels[1]["messages"][-1]["content"][0]
        self.assertEqual(res["content"], _references("x_lire"))
        self.assertNotIn("is_error", res)

    def test_empreinte_inchangee_sans_differe_et_changee_avec(self):
        import hashlib
        outils = [_outil("a"), _outil("b")]
        ancienne = json.dumps({"outils": [[o.nom, o.description, o.schema] for o in outils],
                               "systeme": [b.get("text") for b in SYSTEME]},
                              sort_keys=True, ensure_ascii=False, default=str)
        self.assertEqual(mn._empreinte(SYSTEME, outils),
                         hashlib.sha256(ancienne.encode("utf-8")).hexdigest()[:32])
        self.assertNotEqual(mn._empreinte(SYSTEME, [_outil("a"), _differe("b")]),
                            mn._empreinte(SYSTEME, outils))

    def test_vrai_sdk_envoie_defer_loading_et_les_references(self):
        """Le SDK installé (0.125.0, épinglé FND1) sérialise `defer_loading`
        et un `tool_result` fait de `tool_reference` sans rien changer."""
        import anthropic
        import httpx
        envoyes = []
        reponses = [_rep([_appel("t1", "charger")], stop="tool_use"), _rep([_texte("ok")])]

        def transport(requete):
            envoyes.append(json.loads(requete.content))
            return httpx.Response(200, json=reponses.pop(0))
        client = anthropic.Anthropic(api_key="k", max_retries=0, http_client=httpx.Client(
            transport=httpx.MockTransport(transport)))
        with mock.patch.object(mn, "_client", return_value=client):
            mn.executer(question="q", systeme=SYSTEME, conversation="", modele=MODELE,
                        outils=[_outil("charger", lambda e: _references("x_lire")), _differe("x_lire")])
        self.assertEqual(envoyes[0]["tools"][1]["defer_loading"], True)
        self.assertEqual(envoyes[1]["messages"][-1]["content"][0]["content"], _references("x_lire"))


class DiffereConversationTests(_Base):
    """La conversation gardée garde les références ; une conversation de la
    version 1 (avant les différés) repart d'un récapitulatif."""
    CONV = ConversationTests.CONV
    setUp = ConversationTests.setUp
    garde = ConversationTests.garde
    tour_outil = ConversationTests.tour_outil
    _verifier_recommence = ConversationTests._verifier_recommence

    def test_references_gardees_puis_relues_telles_quelles(self):
        outils = [_outil("charger", lambda e: _references("x_lire")), _differe("x_lire")]
        self.client = FauxClient([_rep([_appel("t1", "charger")], stop="tool_use"),
                                  _rep([_texte("R1")])])
        with mock.patch.object(mn, "_client", return_value=self.client):
            mn.executer(question="Q1", systeme=SYSTEME, outils=outils,
                        conversation=self.CONV, modele=MODELE)
        gardes = self.garde()["messages"]
        self.assertEqual(gardes[2]["content"][0]["content"], _references("x_lire"))
        self.jouer([_rep([_texte("R2")])], outils, question="Q2", conversation=self.CONV)
        self.assertEqual(self.client.appels[0]["messages"][:len(gardes)], gardes)

    def test_conversation_version_1_repart_d_un_recapitulatif(self):
        self.tour_outil()
        etat = self.garde()
        etat["version"] = 1
        self.redis.donnees[mn.CLE_CONVERSATION % self.CONV] = json.dumps(etat)
        self.jouer([_rep([_texte("R2")])], [_outil("a")], question="Q2", conversation=self.CONV)
        self._verifier_recommence(self.client.appels[0]["messages"])


CATALOGUE = [
    {"key": "crm.digest_matin", "noyau": True},
    {"key": "crm.lead.note"},
    {"key": "crm.visite.planifier"},
    {"key": "ged.docqa.retrieve"},
    {"key": "visites.agenda"},
]


class ChargeurTests(_Base):
    """Copilote vague 2 (FND4) — le chargeur `outils_charger` : domaines,
    index, références seules, consignes APRÈS le tool_result, appels de
    chargement hors du budget d'itérations."""

    def _outils(self):
        from app.services import chargeur_outils as ch
        outils, domaines = ch.differer([_outil(a["key"].replace(".", "_")) for a in CATALOGUE], CATALOGUE)
        return outils + [ch.outil_charger(domaines)], domaines

    def test_noyau_et_domaine_inconnu_jamais_differes_et_liste_croisee(self):
        outils, domaines = self._outils()
        self.assertEqual([o.differe for o in outils[:5]], [False, True, True, False, True])
        self.assertEqual(domaines, {"crm": ["crm_lead_note", "crm_visite_planifier"],
                                    "visites": ["crm_visite_planifier", "visites_agenda"]})
        self.assertTrue(outils[-1].hors_budget)
        self.assertEqual(outils[-1].schema["properties"]["domaines"]["items"]["enum"], ["crm", "visites"])

    def test_index_et_indice_d_ecran(self):
        from app.services import chargeur_outils as ch
        _, domaines = self._outils()
        index = ch.index_des_domaines(domaines)
        self.assertTrue(index.startswith(ch.ENTETE_INDEX))
        self.assertEqual(index.count("\n- "), 2)
        self.assertNotIn("- ventes", index)
        self.assertEqual(ch.domaine_de_l_ecran("/visites/12/calage", domaines), "visites")
        self.assertEqual(ch.domaine_de_l_ecran("/crm?id=4", domaines), "crm")
        self.assertIsNone(ch.domaine_de_l_ecran("/ventes/devis", domaines))  # rien de différé
        self.assertIsNone(ch.domaine_de_l_ecran("/crmx", domaines))
        self.assertIsNone(ch.domaine_de_l_ecran(None, domaines))

    def test_tour_scripte_chargement_puis_appel_hors_budget(self):
        from app.services import consignes_domaines
        vus = []
        outils, _ = self._outils()
        outils = [o if o.nom != "visites_agenda" else _differe("visites_agenda", lambda e: vus.append(e) or "agenda")
                  for o in outils]
        with mock.patch.dict(consignes_domaines.CONSIGNES, {"visites": "Demande qui fait la visite."}):
            r = self.jouer([_rep([_appel("t1", "outils_charger", {"domaines": ["visites"]})], stop="tool_use"),
                            _rep([_appel("t2", "visites_agenda")], stop="tool_use"),
                            _rep([_texte("Voici l'agenda.")])], outils, max_iterations=1 + 1)
        self.assertEqual((r["answer"], len(vus)), ("Voici l'agenda.", 1))
        retour = self.client.appels[1]["messages"][-1]["content"]
        self.assertEqual(retour[0]["content"], _references("crm_visite_planifier", "visites_agenda"))
        self.assertEqual(retour[1]["type"], "text")
        self.assertTrue(retour[1]["text"].startswith("[Consignes de l'ERP pour le domaine visites]"))
        self.assertEqual(r["outils_appeles"], ["outils_charger", "visites_agenda"])

    def test_domaine_inconnu_erreur_et_deja_charge(self):
        outils, _ = self._outils()
        self.jouer([_rep([_appel("t1", "outils_charger", {"domaines": ["stock"]}),
                          _appel("t2", "outils_charger", {"domaines": ["crm"]}),
                          _appel("t3", "outils_charger", {"domaines": ["crm"]})], stop="tool_use"),
                    _rep([_texte("ok")])], outils)
        inconnu, charge, deja = self.client.appels[1]["messages"][-1]["content"]
        self.assertTrue(inconnu["is_error"])
        self.assertIn("stock", inconnu["content"])
        self.assertEqual(charge["content"], _references("crm_lead_note", "crm_visite_planifier"))
        self.assertIsInstance(deja["content"], str)
        self.assertEqual(len(self.client.appels[1]["messages"][-1]["content"]), 3)  # aucune consigne

    def test_chargements_hors_budget_bornes(self):
        from app.services.moteur_natif import CHARGEMENTS_HORS_BUDGET
        outils, _ = self._outils()
        boucle = [_rep([_appel("t%d" % i, "outils_charger", {"domaines": ["crm"]})], stop="tool_use")
                  for i in range(CHARGEMENTS_HORS_BUDGET + 2)]
        r = self.jouer(boucle, outils, max_iterations=2)
        self.assertEqual(len(self.client.appels), CHARGEMENTS_HORS_BUDGET + 2)
        self.assertEqual(r["arret"], mn.ARRET_LIMITE)


class RedisAbsentTests(_Base):
    def test_tour_servi_sans_memoire(self):
        with mock.patch.object(mn, "_redis", side_effect=ConnectionError("x")):
            r = self.jouer([_rep([_texte("ok")])], conversation="7:42")
            mn.effacer("7:42")
        self.assertEqual(r["answer"], "ok")
        self.assertEqual(len(self.client.appels[0]["messages"]), 1)


if __name__ == "__main__":
    unittest.main()
