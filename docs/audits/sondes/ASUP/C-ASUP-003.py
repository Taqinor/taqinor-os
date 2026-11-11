"""Rejoue authentication/views.py::UserViewSet.destroy (corps réel, ast) : un compte ACTIF sans calepinage se supprime en dur, sans désactivation préalable ni contrôle de ses documents ; inventaire ast des liens entrants vers l'utilisateur (CASCADE emportés, SET_NULL qui effacent l'auteur des chatters, factures et paiements)."""
SONDE = {"constat": "C-ASUP-003", "sha": "3acfee471",
         "attendu": "destroy rend 204 pour un compte actif ordinaire ; des dizaines de modèles partent en CASCADE et des centaines de liens d'auteur passent à NULL"}
import ast, pathlib, sys
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
DJ = RACINE / "backend/django_core"


class ProtectedError(Exception): pass


class Resp:
    def __init__(self, data=None, status=None): self.data, self.status_code = data, status


class Parent:  # destroy de DRF : get_object puis delete ; un PROTECT lève ProtectedError (409)
    def destroy(self, request, *a, **k):
        if self._cible.protege: raise ProtectedError("PROTECT")
        return Resp(None, 204)


class Compte:
    def __init__(self, actif=True, protege=False):
        self.is_active, self.is_protected, self.is_superuser, self.protege = actif, False, False, protege
    def est_dernier_proprietaire(self): return False


def _liens_entrants():
    cascade, set_null, protect = set(), 0, 0
    for p in DJ.rglob("*.py"):
        rel = p.relative_to(DJ).as_posix()
        if "/migrations/" in rel or "/tests" in rel or p.name.startswith("test"): continue
        try: arbre = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError): continue
        for cl in (n for n in ast.walk(arbre) if isinstance(n, ast.ClassDef)):
            for st in cl.body:
                if not (isinstance(st, ast.Assign) and isinstance(st.value, ast.Call)): continue
                fn = ast.unparse(st.value.func)
                if not fn.endswith(("ForeignKey", "OneToOneField")) or not st.value.args: continue
                if "AUTH_USER_MODEL" not in ast.unparse(st.value.args[0]): continue
                od = next((ast.unparse(k.value) for k in st.value.keywords if k.arg == "on_delete"),
                          ast.unparse(st.value.args[1]) if len(st.value.args) > 1 else "")
                if od.endswith("CASCADE"): cascade.add(f"{rel.split('/')[-2]}.{cl.name}")
                elif od.endswith("SET_NULL"): set_null += 1
                elif od.endswith("PROTECT"): protect += 1
    return cascade, set_null, protect


def sonde(ctx=None):
    arbre = ast.parse((DJ / "authentication/views.py").read_text(encoding="utf-8"))
    cl = next(n for n in ast.walk(arbre) if isinstance(n, ast.ClassDef) and n.name == "UserViewSet")
    fn = next(s for s in cl.body if isinstance(s, ast.FunctionDef) and s.name == "destroy")
    fn.decorator_list = []
    module = ast.Module([ast.ClassDef(name="UserViewSet", bases=[ast.Name("Parent", ast.Load())], keywords=[], body=[fn],
                                      decorator_list=[], type_params=[])], [])
    ns = {"Response": Resp, "Parent": Parent,
          "status": type("S", (), {"HTTP_400_BAD_REQUEST": 400, "HTTP_403_FORBIDDEN": 403})}
    exec(compile(ast.fix_missing_locations(module), "destroy", "exec"), ns)

    def jouer(cible):
        v = ns["UserViewSet"](); v._cible = cible
        v.get_object, v._refus_rang = (lambda: cible), (lambda t: None)
        try: return v.destroy(type("R", (), {"user": object()})()).status_code
        except ProtectedError: return 409
    actif, avec_calepinage = jouer(Compte()), jouer(Compte(protege=True))
    cascade, set_null, protect = _liens_entrants()
    repro = actif == 204 and "is_active" not in ast.unparse(fn) and len(cascade) > 10
    return {"repro": repro, "observe": {
        "compte_actif_ordinaire": actif, "compte_responsable_de_calepinage": avec_calepinage,
        "destroy_lit_is_active": "is_active" in ast.unparse(fn),
        "modeles_emportes_en_cascade": len(cascade), "exemples": sorted(cascade)[:8],
        "liens_mis_a_null": set_null, "liens_protect": protect,
        "geste": "Administration > Utilisateurs > Supprimer (UsersManagement)"}}


if __name__ == "__main__":
    print(sonde())
