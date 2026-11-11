"""Rejoue la vraie apps/crm/fiche_api_publique.py::update_lead_from_public_api (PATCH leads-write/ et import upsert de l'API publique) sur un lead Signé mis au Froid : la vraie garde _bulk_stage_allowed laisse passer, le vrai parquer_lead range le lead, desaccepter_devis_du_lead n'est jamais appelé (l'écran, lui, l'appelle)."""
SONDE = {"constat": "C-APUB-008", "sha": "ae5a7ae4c",
         "attendu": "lead Signé → Froid par l'API publique : étape finale Froid, desaccepter_devis_du_lead appelé 0 fois ; témoin Signé → Contacté refusé"}
import ast, copy, pathlib, runpy, sys, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
API, FUNNEL = "apps/crm/fiche_api_publique.py", "apps/crm/fiche_funnel.py"


def morceaux(chemin, noms):
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    garde = [n for n in arbre.body if getattr(n, "name", None) in noms
             or (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in noms for t in n.targets))]
    return ast.Module(body=garde, type_ignores=[])


def appelle(chemin, classe, fonction, cible):
    """Vrai si ``fonction`` (méthode de ``classe`` ou fonction de module) référence ``cible``."""
    arbre = ast.parse((DJ / chemin).read_text(encoding="utf-8"))
    corps = next(n for n in arbre.body if isinstance(n, ast.ClassDef) and n.name == classe).body if classe else arbre.body
    f = next(n for n in corps if isinstance(n, ast.FunctionDef) and n.name == fonction)
    return any(isinstance(n, (ast.Name, ast.alias)) and getattr(n, "id", getattr(n, "name", None)) == cible for n in ast.walk(f))


class ErreurChamp(Exception): pass


def jouer(S, depart, cible, champs):
    appels = []
    def desaccepter_devis_du_lead(lead, user, *, motif=""): appels.append(lead.pk)
    rien = lambda *a, **k: None
    stages = types.SimpleNamespace(**{k: v for k, v in vars(S).items() if k.isupper()})
    lead = types.SimpleNamespace(pk=1637, company="C", stage=depart, perdu=False, parc_etat=None, parc_raison=None,
                                 parc_jusqu_au=None, nom="Client", save=rien)
    Lead = types.SimpleNamespace(objects=types.SimpleNamespace(get=lambda **kw: lead if "company" in kw else copy.copy(lead)))
    commun = {"stages": stages, "activity": types.SimpleNamespace(log_changes=rien, log_bulk_change=rien),
              "_emit_stage_changed": rien, "_refus_parcage": lambda *a: None, "ParcRefuse": ErreurChamp,
              "desaccepter_devis_du_lead": desaccepter_devis_du_lead, "SortieSigneBloquee": ErreurChamp}
    ff = dict(commun, **vars(stages))  # vraies garde funnel, mise au Froid et parcage (fiche_funnel.py) ; constantes d'étape de STAGES.py
    exec(compile(morceaux(FUNNEL, {"_rang_funnel", "_bulk_stage_allowed", "avancer_stage_lead_vers", "ETAT_PAR_RAISON",
                                   "refus_mise_au_froid", "parquer_lead"}), FUNNEL, "exec"), ff)
    mod_ff = types.ModuleType("apps.crm.fiche_funnel"); mod_ff.__dict__.update(ff)  # imports paresseux d'un correctif
    ns = dict(commun, __name__="apps.crm.fiche_api_publique", __package__="apps.crm", Lead=Lead, DRFValidationError=ErreurChamp,
              _bulk_stage_allowed=ff["_bulk_stage_allowed"], parquer_lead=ff["parquer_lead"],
              refus_mise_au_froid=ff["refus_mise_au_froid"], sync_relance_activity=rien, maybe_set_first_contacted_at=rien,
              recompute_lead_score=rien)
    exec(compile(morceaux(API, {"PUBLIC_LEAD_WRITABLE_FIELDS", "PUBLIC_LEAD_COLONNES_DERIVEES", "update_lead_from_public_api"}),
                 API, "exec"), ns)
    vieux = {n: sys.modules.get(n) for n in ("apps", "apps.crm", "apps.crm.fiche_funnel")}
    sys.modules.update({"apps": types.ModuleType("apps"), "apps.crm": types.ModuleType("apps.crm"), "apps.crm.fiche_funnel": mod_ff})
    try:
        ns["update_lead_from_public_api"](company="C", lead_id=lead.pk, fields=dict(champs, stage=cible))
        issue = "accepté"
    except (ValueError, ErreurChamp) as exc:
        issue = f"refusé ({type(exc).__name__}: {exc})"
    finally:
        for n, m in vieux.items():
            if m is None: sys.modules.pop(n, None)
            else: sys.modules[n] = m
    return {"issue": issue, "etape_finale": S.STAGE_LABELS.get(lead.stage, lead.stage),
            "est_froid": lead.stage == S.COLD, "desaccepter_appels": len(appels), "parc_raison": lead.parc_raison}


def sonde(ctx=None):
    S = types.SimpleNamespace(**{k: v for k, v in runpy.run_path(str(RACINE / "STAGES.py")).items() if k.isupper()})
    table = ast.literal_eval(morceaux(FUNNEL, {"ETAT_PAR_RAISON"}).body[0].value)
    raison = next(k for k, v in table.items() if v == "nurture")  # une raison Nurture valide, lue du dépôt
    froid = jouer(S, S.SIGNED, S.COLD, {"parc_raison": raison})
    recul = jouer(S, S.SIGNED, S.CONTACTED, {})
    ecran = appelle("apps/crm/views.py", "LeadViewSet", "perform_update", "desaccepter_devis_du_lead")
    repro = froid["issue"] == "accepté" and froid["est_froid"] and froid["desaccepter_appels"] == 0
    return {"repro": repro, "observe": {
        "methode": "exécution (vraies update_lead_from_public_api, _bulk_stage_allowed, refus_mise_au_froid, parquer_lead, "
                   "avancer_stage_lead_vers extraites par ast ; ORM et _refus_parcage bouchonnés)",
        "routes": "PATCH /api/public/v1/leads-write/<pk>/ (publicapi/public_write_views.py) et upsert publicapi/bulk.py",
        "signe_vers_froid": froid, "temoin_signe_vers_contacte": recul["issue"],
        "ecran_LeadViewSet_perform_update_appelle_desaccepter": ecran,
        "effet": "devis laissé « accepté », chantier et commission auto non défaits, 409 « facture émise » contourné"
                 if repro else "dés-acceptation appliquée ou sortie refusée"}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1))
