"""Exécute la VRAIE migrate_attachments_to_ged.py::import_attachments (ast) sur un faux ORM en mémoire : import, purge définitive du Document (versions effacées, pièce jointe gardée), puis import du lundi suivant."""
SONDE = {"constat": "C-ACEL-002", "sha": "3acfee471",
         "attendu": "après la purge définitive, l'import suivant recrée un Document (et sa version) pour la pièce jointe conservée"}
import ast, contextlib, itertools, pathlib, types
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()  # copie hors dépôt : jouée depuis la racine
DJ = RACINE / "backend/django_core"
CMD = "apps/ged/management/commands/migrate_attachments_to_ged.py"


def valeur(o, chemin):  # lookup Django minimal : champ, champ__sous_cle (JSON), champ__exact/contains
    for p in chemin.split("__"):
        o = o.get(p) if isinstance(o, dict) else getattr(o, p, None)
    return o


class QS(list):
    def filter(self, **kw):
        def ok(o):
            for k, v in kw.items():
                if k.endswith("__isnull"): c = (valeur(o, k[:-8]) is None) == v
                else: c = valeur(o, k[:-7] if k.endswith("__exact") else k) == v
                if not c: return False
            return True
        return QS(o for o in self if ok(o))
    def exclude(self, **kw): return QS(o for o in self if o not in self.filter(**kw))
    def first(self): return self[0] if self else None
    def exists(self): return bool(self)
    def iterator(self): return iter(list(self))
    def all(self): return self
    def select_related(self, *a): return self


def fabrique(ids):
    class Obj:
        pass
    class Mgr:
        def __init__(s, cls): s.cls, s.rows = cls, QS()
        def filter(s, **kw): return s.rows.filter(**kw)
        def select_related(s, *a): return s.rows
        def all(s): return s.rows
        def create(s, **kw):
            o = s.cls(); o.__dict__.update(kw); o.pk = next(ids); s.rows.append(o); return o
    classes = {n: type(n, (Obj,), {}) for n in ("Attachment", "Document", "DocumentVersion")}
    for c in classes.values(): c.objects = Mgr(c)
    return classes


def sonde(ctx=None):
    arbre = ast.parse((DJ / CMD).read_text(encoding="utf-8"))
    fn = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "import_attachments")
    C = fabrique(itertools.count(1))
    ns = {**C, "transaction": types.SimpleNamespace(atomic=contextlib.nullcontext),
          "_ensure_landing_folder": lambda c: "dossier-importe", "_ensure_lien": lambda d, a: False,
          "_target_is_allowed": lambda a: False, "_origin_description": lambda a: "origine"}
    exec(compile(ast.Module([fn], []), CMD, "exec"), ns)
    imp = ns["import_attachments"]
    societe = types.SimpleNamespace(id=1)
    C["Attachment"].objects.create(company=societe, file_key="attachments/K.pdf", filename="K.pdf", size=1, mime="application/pdf",
                                   uploaded_by=None, content_type=None, object_id=1)
    docs, vers = C["Document"].objects.rows, C["DocumentVersion"].objects.rows
    lundi1 = imp(company=None)
    nb1 = len(docs)
    # purger_definitivement : Document.delete() (CASCADE sur les versions) ; la pièce jointe d'origine est gardée (ADOC192)
    purge = next(n for n in ast.parse((DJ / "apps/ged/services.py").read_text(encoding="utf-8")).body
                 if isinstance(n, ast.FunctionDef) and n.name == "purger_definitivement")
    touche_pj = any(isinstance(x, ast.Name) and x.id == "Attachment" for x in ast.walk(purge))
    for d in list(docs):
        docs.remove(d)
        vers[:] = [v for v in vers if v.document is not d]
    nb_apres_purge = len(docs)
    try:
        lundi2 = imp(company=None)
    except Exception as e:  # noqa: BLE001 — un correctif qui change les accès ORM rend la sonde non concluante, pas fausse
        return {"repro": False, "observe": {"methode": "ast + faux ORM", "inconclusif": f"{type(e).__name__}: {e}"}}
    recrees = len(docs)
    return {"repro": recrees > 0 and not touche_pj, "observe": {
        "methode": "VRAIE import_attachments exécutée sur un faux ORM (ast) ; purger_definitivement lue par ast",
        "fonction": "apps/ged/management/commands/migrate_attachments_to_ged.py::import_attachments (tâche ged.migrer_pieces_jointes)",
        "scenario": "import -> purge définitive du Document -> import du lundi suivant",
        "lundi_1": lundi1, "documents_apres_import_1": nb1, "documents_apres_purge": nb_apres_purge,
        "lundi_2": lundi2, "documents_apres_import_2": recrees,
        "purger_definitivement_touche_la_piece_jointe": touche_pj,
        "document_recree": [{"nom": d.nom, "dossier": d.folder, "custom_data": d.custom_data} for d in docs]}}


if __name__ == "__main__":
    import json
    print(json.dumps(sonde(), ensure_ascii=False, indent=1, default=str))
