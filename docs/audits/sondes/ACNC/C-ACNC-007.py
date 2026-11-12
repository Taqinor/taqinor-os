# flake8: noqa  (sonde HÔTE d'audit PF9 « doubles clics, gestes rejoués, courses », groupe ACNC — sans Django, sans base, sans Docker)
"""C-ACNC-007 — un PATCH/PUT écrit la ligne ENTIÈRE (`instance.save()` sans `update_fields`) : une transition commitée entre le `get_object()` et le
`save()` est écrasée. On exécute la VRAIE `core/mixins.py::TenantMixin.perform_update` (ast) ; DRF n'étant pas installé pour les sondes, le corps de
`ModelSerializer.update` est CITÉ ci-dessous (djangorestframework==3.18.3, requirements.txt:3 ; corps relu sur la copie 3.15.2 de l'hôte, non revérifié en 3.18.3)."""
SONDE = {"constat": "C-ACNC-007", "sha": "3acfee471",
         "attendu": "ticket résolu entre get_object et save d'un PATCH de description : statut final redevenu en_cours, date_resolution effacée"}
import ast, contextlib, pathlib, sys, textwrap, types
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
DJ = RACINE / "backend/django_core"
# rest_framework/serializers.py::ModelSerializer.update (citation)
DRF_UPDATE = textwrap.dedent('''
    def update(self, instance, validated_data):
        raise_errors_on_nested_writes('update', self, validated_data)
        info = model_meta.get_field_info(instance)
        m2m_fields = []
        for attr, value in validated_data.items():
            if attr in info.relations and info.relations[attr].to_many:
                m2m_fields.append((attr, value))
            else:
                setattr(instance, attr, value)
        instance.save()
        for attr, value in m2m_fields:
            field = getattr(instance, attr)
            field.set(value)
        return instance
''')
EMPLACEMENTS = ["apps/ventes/views/bon_commande.py::BonCommandeViewSet", "apps/sav/views.py::TicketViewSet (super().perform_update)",
                "apps/installations/views/intervention.py::InterventionViewSet", "apps/installations/views/livraison.py::LivraisonViewSet"]


def perform_update_reel():
    corps = ast.parse((DJ / "core/mixins.py").read_text(encoding="utf-8")).body
    classe = next(n for n in corps if isinstance(n, ast.ClassDef) and n.name == "TenantMixin")
    f = next(n for n in classe.body if isinstance(n, ast.FunctionDef) and n.name == "perform_update"); f.decorator_list = []
    ns = {"transaction": types.SimpleNamespace(atomic=lambda *a, **k: contextlib.nullcontext())}
    exec(compile(ast.Module([f], []), "core/mixins.py", "exec"), ns); return ns["perform_update"]


def scenario(entrelace):
    db = {"statut": "en_cours", "description": "ancienne", "date_resolution": None, "company": "C"}
    class Ticket:  # ligne chargée par get_object() ; save() = UPDATE de toutes les colonnes (ou de update_fields)
        def __init__(s): s.pk = 1; s.__dict__.update(db)
        def save(s, update_fields=None):
            for c in (update_fields if update_fields is not None else list(db)): db[c] = getattr(s, c)
        class objects:  # relecture sous verrou (un correctif par select_for_update passe par ici)
            select_for_update = staticmethod(lambda: types.SimpleNamespace(get=lambda pk: Ticket()))
    ns = {"model_meta": types.SimpleNamespace(get_field_info=lambda i: types.SimpleNamespace(relations={})), "raise_errors_on_nested_writes": lambda *a: None}
    exec(DRF_UPDATE, ns)
    class Serializer:  # BaseSerializer.save : validated_data + kwargs, puis update()
        class Meta: model = Ticket
        def __init__(s, instance, valides): s.instance, s.validated_data = instance, valides
        def save(s, **kw): s.instance = ns["update"](s, s.instance, {**s.validated_data, **kw}); return s.instance
    resoudre = lambda: (lambda b: (setattr(b, "statut", "resolu"), setattr(b, "date_resolution", "2026-11-11"), b.save(update_fields=["statut", "date_resolution"])))(Ticket())
    if not entrelace: resoudre()  # témoin : B commité AVANT le get_object() de A
    lu = Ticket()  # requête A : get_object() — statut est en lecture seule, le corps ne porte que la description
    ser = Serializer(lu, {"description": "corrigée"})
    if entrelace: resoudre()  # requête B : « Résoudre » commitée entre get_object() et save() de A
    vue = types.SimpleNamespace(request=types.SimpleNamespace(user=types.SimpleNamespace(company_id=1, company="C")))
    perform_update_reel()(vue, ser)
    return dict(db)


def sonde(ctx=None):
    seq = scenario(False); ent = scenario(True)
    ecrase = ent["statut"] != "resolu" or ent["date_resolution"] is None
    return {"repro": ecrase, "observe": {
        "methode": "rejeu (vraie TenantMixin.perform_update par ast + ModelSerializer.update DRF cité, faux ORM, transition entrelacée)",
        "scenario": "PATCH description ; entre get_object et save, B résout le ticket (statut + date_resolution commités)",
        "etat_final_entrelace": ent, "etat_final_sans_entrelacement": seq,
        "transition_ecrasee": ecrase, "emplacements_reels": EMPLACEMENTS, "serializer_drf_cite": "djangorestframework==3.18.3"}}
