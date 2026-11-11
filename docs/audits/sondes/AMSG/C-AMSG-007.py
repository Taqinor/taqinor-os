# flake8: noqa  (sonde HÔTE d'audit PF8 « messages envoyés aux clients », groupe AMSG — sans Django, sans base, sans réseau)
"""C-AMSG-007 — l'action de l'assistant IA `crm.lead.whatsapp_prepare` (« Prépare le WhatsApp du devis ») : VRAI relais
FastAPI (`action_tools.py::run_catalogue_action` → `_execute_catalogue_action` → `_build_path`, risque lu dans le VRAI
catalogue `apps/crm/agent_actions.py::PREPARER_ENVOI_WHATSAPP`), puis la VRAIE vue Django désignée par l'endpoint
(retrouvée par son `url_path`) et le VRAI `ventes/domain/envoi.py::mark_devis_sent` ; ORM, gel et événement bouchonnés.
Scénario : un devis BROUILLON du lead 12, l'assistant appelle l'action sans que personne ne confirme ni n'envoie rien."""
SONDE = {"constat": "C-AMSG-007", "sha": "3acfee471",
         "attendu": "risque « internal » ⇒ exécuté au vol sans proposition ; la vue COMMIT whatsapp_devis appelle "
                    "mark_devis_sent : devis brouillon → envoye + événement devis_sent (étape du lead, cadence)"}
import ast, contextlib, copy, json, logging, pathlib, re, sys, types, typing, urllib.parse
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ, IA = RACINE / "backend/django_core", RACINE / "backend/fastapi_ia"
NS = types.SimpleNamespace


def _arbre(p, _c={}): return _c[p] if p in _c else _c.setdefault(p, ast.parse(p.read_text(encoding="utf-8")))


class _SansImport(ast.NodeTransformer):  # imports (même imbriqués) → pass : leurs noms viennent de l'espace fourni
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


def reel(p, noms, ns, corps=None):  # exécute les nœuds RÉELS ``noms`` (fonctions, classes, affectations) dans ``ns``
    pris = []
    for n in corps if corps is not None else _arbre(p).body:
        nom = getattr(n, "name", None) or (getattr(n.targets[0], "id", None) if isinstance(n, ast.Assign) else None)
        if nom in noms:
            n = copy.deepcopy(n)  # l'arbre en cache reste intact (décorateurs relus par vue_de)
            for f in ast.walk(n):
                if isinstance(f, (ast.FunctionDef, ast.ClassDef)): f.decorator_list = []
            pris.append(_SansImport().visit(n))
    exec(compile(ast.fix_missing_locations(ast.Module(body=pris, type_ignores=[])), str(p), "exec"), ns)
    return ns


def action_du_catalogue():  # la VRAIE déclaration AgentAction, risque résolu par les constantes de apps/agent/registry.py
    risques = {n.targets[0].id: n.value.value for n in _arbre(DJ / "apps/agent/registry.py").body
               if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "").startswith("RISK_") and isinstance(n.value, ast.Constant)}
    decl = next(n.value for n in _arbre(DJ / "apps/crm/agent_actions.py").body
                if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "PREPARER_ENVOI_WHATSAPP")
    kw = {k.arg: k.value for k in decl.keywords}
    out = {k: ast.literal_eval(v) for k, v in kw.items() if k in ("key", "label", "endpoint", "method", "inputs")}
    out["risk"] = risques.get(getattr(kw.get("risk"), "id", ""), ast.literal_eval(kw["risk"]) if isinstance(kw.get("risk"), ast.Constant) else "internal")
    return out


def vue_de(segment):  # (fichier, classe, méthode) de apps/crm dont l'@action porte ce url_path
    for f in sorted((DJ / "apps/crm").glob("*.py")):
        for c in (n for n in _arbre(f).body if isinstance(n, ast.ClassDef)):
            for m in (x for x in c.body if isinstance(x, ast.FunctionDef)):
                for d in m.decorator_list:
                    if any(k.arg == "url_path" and getattr(k.value, "value", None) == segment for k in getattr(d, "keywords", [])):
                        return f, c.name, m.name
    return None


def sonde(ctx=None):
    effets, appels = [], []
    lead = NS(pk=12, id=12, whatsapp="+212600000000", telephone="", langue_preferee="fr", ne_plus_contacter=False)
    devis = NS(pk=45, id=45, reference="DEV-45", statut="brouillon", lead=lead, company=NS(id=1))
    Statut = NS(BROUILLON="brouillon", ENVOYE="envoye")
    class ConflitEtat(Exception): pass
    class RemiseNonApprouvee(Exception): pass
    dj = {"Response": lambda data=None, status=200, **k: NS(data=data, status_code=status), "logger": logging.getLogger("sonde"),
          "status": NS(HTTP_400_BAD_REQUEST=400, HTTP_403_FORBIDDEN=403), "transaction": NS(atomic=contextlib.nullcontext),
          "ConflitEtat": ConflitEtat, "MOTIF_CONTACT_REFUSE": "contact_refuse", "peut_contacter": lambda o: True,
          "pii_masquee_pour": lambda u: False, "corps_objet": lambda r: r.data, "coerce_id_list": lambda l: [int(x) for x in l],
          "devis_for_lead": lambda l, ids: [devis] if 45 in ids else [], "normalize_phone_e164": lambda p: p,
          "RemiseNonApprouvee": RemiseNonApprouvee, "exiger_approbation_remise": lambda d, u, enregistrer: None,
          "build_devis_whatsapp": lambda r, l, ds, lg: ("Bonjour, voici votre devis : https://erp.example.invalid/p/x", ["lien"]),
          "build_wa_url": lambda p, m: f"https://wa.me/{p.lstrip('+')}?text=…",
          "record": lambda *a, **k: effets.append("AuditLog WHATSAPP"), "AuditLog": NS(Action=NS(WHATSAPP="whatsapp")),
          "activity": NS(log_note=lambda *a: effets.append("note au chatter du lead"), log_devis_sent=lambda d, u: effets.append("chatter devis « envoyé »")),
          "Devis": NS(Statut=Statut, objects=NS(select_for_update=lambda: NS(get=lambda pk: devis))),
          "geste_cycle_permis": lambda d, g: (True, ""), "ENVOYER": "envoyer", "refus_kwh_declare_du_devis": lambda d: None,
          "calepinage_du_devis": lambda pk, co: None, "peremption_layout_devis": lambda d, c: {},
          "geler_document_engage": lambda d, u, statut: (setattr(d, "statut", statut), effets.append(f"gel du document, statut={statut}")),
          "_envoyer_la_soeur": lambda d, u: None,
          "devis_sent": NS(send=lambda **k: effets.append("événement devis_sent (lead → « Devis envoyé », cadence après-devis)"))}
    reel(DJ / "apps/ventes/domain/envoi.py", {"exiger_contact_permis", "mark_devis_sent"}, dj)
    reel(DJ / "apps/crm/devis_views.py", {"_refuser_si_oppose", "_refus_pii_whatsapp"}, dj)
    route = {}

    def _django_call(c, path, method="POST", payload=None):  # le relais HTTP, remplacé par l'appel de la vraie vue
        appels.append(f"{method} {path}")
        trouve = vue_de([s for s in path.split("/") if s][-1])
        if trouve is None: route["non_resolue"] = path; return {"ok": False, "status": 404, "error": "route introuvable"}
        f, classe, meth = trouve; route.update(fichier=f.relative_to(RACINE).as_posix(), vue=f"{classe}.{meth}")
        cls = reel(f, {classe}, dict(dj))[classe]
        v = type("Vue", (cls,), {"get_object": lambda s: lead, "action": meth})()
        r = getattr(v, meth)(NS(user=NS(username="commercial", is_authenticated=True), data=payload, method=method), pk=12)
        return {"ok": r.status_code < 300, "status": r.status_code, "data": r.data}
    ia = {"Any": typing.Any, "Optional": typing.Optional, "quote": urllib.parse.quote, "ActionContext": object, "json": json, "re": re,
          "logger": logging.getLogger("sonde"), "_django_call": _django_call, "_stash_proposal": lambda *a: "jeton-signé"}
    reel(IA / "app/services/action_tools.py", {"RISK_INTERNAL", "RISK_OUTWARD", "RISK_IRREVERSIBLE", "_RISK_NEEDS_CONFIRM",
         "STATUTS_REPONSE_NORMALE", "intention_pour_statut", "ActionValidationError", "_JSON_TYPE_CHECK", "validate_inputs",
         "_coerce", "_PATH_PARAM_RE", "_build_path", "_human_preview", "_execute_catalogue_action", "run_catalogue_action"}, ia)
    action, collecte = action_du_catalogue(), []
    pyc, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        sortie = ia["run_catalogue_action"](NS(), action, {"id": 12, "devis_ids": [45]}, collecte)
    finally:
        sys.dont_write_bytecode = pyc
    proposition = any(c.get("type") == "proposal" for c in collecte)
    return {"repro": devis.statut != "brouillon" and not proposition, "observe": {
        "methode": "exécution du vrai relais FastAPI + vraie vue Django (url_path) + vrai mark_devis_sent (ast, bouchons)",
        "action": action["key"], "endpoint": action["endpoint"], "risque_catalogue": action["risk"],
        "risques_a_confirmer_du_relais": sorted(ia["_RISK_NEEDS_CONFIRM"]), "proposition_a_confirmer": proposition,
        "appels_relayes": appels, "vue_executee": route, "statut_devis": f"brouillon → {devis.statut}", "effets": effets,
        "message_envoye_par_quelquun": False, "sortie_relais": str(sortie)[:160]}}


if __name__ == "__main__":
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
