"""Exécute les VRAIES ged/services.py::verifier_integrite_archives, _notifier_alteration_archives, _hash_constate_pour_archivage et _fetch_version_bytes (ast) sur un stockage factice : une archive intacte, une altérée, une introuvable ; compte les alertes envoyées et les notifications ERP."""
SONDE = {"constat": "C-ACEL-003", "sha": "3acfee471",
         "attendu": "l'archive introuvable ne déclenche aucune alerte ; l'archive altérée ne prévient que par send_mail(fail_silently=True) : 0 Notification ERP"}
import ast, hashlib, pathlib, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
NOMS = ("compute_checksum", "_fetch_version_bytes", "_hash_constate_pour_archivage", "verifier_integrite_archives", "_notifier_alteration_archives")


class Sans(ast.NodeTransformer):  # imports (même locaux) remplacés par pass : leurs noms viennent de ns
    visit_Import = visit_ImportFrom = lambda s, n: ast.Pass()


class QS(list):
    def select_related(self, *a): return self


def sonde(ctx=None):
    arbre = ast.parse((DJ / "apps/ged/services.py").read_text(encoding="utf-8"))
    fns = [Sans().visit(n) for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name in NOMS]
    octets = {"k-ok": b"contenu ok", "k-altere": b"contenu MODIFIE"}  # "k-absent" n'existe pas dans le stockage
    cree, mails, notifs = [], [], []
    def archive(nom, cle, original):
        v = types.SimpleNamespace(pk=1, company_id=1, file_key=cle)
        return types.SimpleNamespace(document=types.SimpleNamespace(nom=nom), version=v, hash_integrite=hashlib.sha256(original).hexdigest())
    archives = [archive("contrat-ok.pdf", "k-ok", b"contenu ok"), archive("facture-alteree.pdf", "k-altere", b"contenu original"),
                archive("pv-introuvable.pdf", "k-absent", b"contenu perdu")]
    rec = lambda *a, **k: notifs.append((a, k))
    ns = {"hashlib": hashlib, "logger": types.SimpleNamespace(warning=lambda *a, **k: None),
          "cle_d_une_autre_societe": lambda cid, cle: False,
          "fetch_attachment": lambda cle: (octets[cle], None) if cle in octets else (None, "Fichier introuvable."),  # stockage factice
          "ArchivageLegal": types.SimpleNamespace(objects=types.SimpleNamespace(filter=lambda **k: QS(archives))),
          "ControleIntegrite": types.SimpleNamespace(objects=types.SimpleNamespace(create=lambda **k: cree.append(k["resultat"]))),
          "CONTROLE_RESULTAT_OK": "ok", "CONTROLE_RESULTAT_ALTERE": "altere", "CONTROLE_RESULTAT_INDISPONIBLE": "indisponible",
          "CustomUser": types.SimpleNamespace(admins_actifs_qs=lambda c: [types.SimpleNamespace(email="admin@example.invalid")]),
          "settings": types.SimpleNamespace(DEFAULT_FROM_EMAIL="noreply@example.invalid"),
          "send_mail": lambda sujet, corps, de, a, fail_silently=False: (mails.append({"sujet": sujet, "corps": corps, "fail_silently": fail_silently}), 1)[1],
          # toute voie de notification ERP : comptée
          "notify": rec, "notify_many": rec, "resolve_recipients": lambda *a, **k: [],
          "Notification": types.SimpleNamespace(objects=types.SimpleNamespace(create=rec)),
          "EventType": types.SimpleNamespace(**{n: n for n in ("GED_ARCHIVE_ALTEREE", "GED_ARCHIVE_INDISPONIBLE", "GED_INTEGRITE")})}
    exec(compile(ast.fix_missing_locations(ast.Module(fns, [])), "services.py", "exec"), ns)
    try:
        synthese = ns["verifier_integrite_archives"](types.SimpleNamespace(id=1))
    except Exception as e:  # noqa: BLE001 — un correctif qui change les dépendances rend la sonde non concluante
        return {"repro": False, "observe": {"methode": "ast + stockage factice", "inconclusif": f"{type(e).__name__}: {e}"}}
    texte = " ".join(m["sujet"] + m["corps"] for m in mails) + " ".join(str(n) for n in notifs)
    alerte_introuvable = "pv-introuvable" in texte
    alerte_alteree = "facture-alteree" in texte
    seulement_mail_silencieux = bool(mails) and all(m["fail_silently"] for m in mails)
    demi_defaut_introuvable = synthese["indisponible"] == 1 and not alerte_introuvable
    demi_defaut_alteree = synthese["altere"] == 1 and not notifs
    return {"repro": demi_defaut_introuvable or demi_defaut_alteree, "observe": {
        "methode": "VRAIES fonctions exécutées (ast) ; stockage objet factice, e-mail et notifications enregistreurs (rien n'est envoyé)",
        "fonction": "apps/ged/services.py::verifier_integrite_archives / ::_notifier_alteration_archives",
        "scenario": "3 archives : intacte, altérée, introuvable dans le stockage", "synthese": synthese, "lignes_controle_integrite": cree,
        "send_mail_appeles": [{"sujet": m["sujet"], "fail_silently": m["fail_silently"]} for m in mails],
        "notifications_erp_creees": len(notifs), "alerte_pour_archive_introuvable": alerte_introuvable,
        "alerte_pour_archive_alteree": alerte_alteree, "alertes_seulement_par_mail_silencieux": seulement_mail_silencieux}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
