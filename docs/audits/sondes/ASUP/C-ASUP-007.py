"""Rejoue trash/services.py::_restauration_generique (module réel chargé, bouchons Django) : un lead ARCHIVÉ puis SUPPRIMÉ, restauré depuis la corbeille commune (/parametres/corbeille, crm.lead n'a pas de restaurateur enregistré), est aussi DÉSARCHIVÉ sans passer par restaurer_lead : ni historique, ni prochaine étape, archived_at / archived_by restent remplis."""
SONDE = {"constat": "C-ASUP-007", "sha": "3acfee471",
         "attendu": "après restauration générique : is_archived False alors que archived_at / archived_by restent remplis"}
import importlib.util, pathlib, sys, types
from types import SimpleNamespace
sys.dont_write_bytecode = True
RACINE = pathlib.Path(__file__).resolve().parents[4]
if not (RACINE / "backend/django_core").is_dir(): RACINE = pathlib.Path.cwd()
FICHIER = RACINE / "backend/django_core/apps/trash/services.py"


def _module(nom, **attrs):
    m = types.ModuleType(nom); m.__path__ = []; m.__dict__.update(attrs); return m


def sonde(ctx=None):
    tz = _module("django.utils.timezone", now=lambda: "MAINTENANT")
    bouchons = {"django": _module("django"), "django.utils": _module("django.utils", timezone=tz),
                "django.utils.timezone": tz, "core": _module("core"),
                "core.events": _module("core.events", record_restored=SimpleNamespace(send=lambda **k: None)),
                "apps": _module("apps"), "apps.trash": _module("apps.trash"),
                "apps.trash.models": _module("apps.trash.models", ElementSupprime=object),
                "apps.trash.registry": _module("apps.trash.registry", restaurateur=lambda cle: None)}
    gardes = {k: sys.modules.get(k) for k in bouchons}
    sys.modules.update(bouchons)
    try:
        spec = importlib.util.spec_from_file_location("apps.trash.services", FICHIER)
        services = importlib.util.module_from_spec(spec); spec.loader.exec_module(services)

        class Lead:  # comportement de crm.Lead : SoftDeleteModel.restore() ne regarde que is_deleted
            def __init__(self):
                self.is_deleted, self.is_archived = True, True
                self.archived_at, self.archived_by, self.saves = "2026-10-01", "commercial", []
            def restore(self):
                self.is_deleted = False; self.saves.append(("is_deleted",)); return self
            def save(self, update_fields=None): self.saves.append(tuple(update_fields or ()))
        lead = Lead()
        manager = SimpleNamespace(filter=lambda pk: SimpleNamespace(first=lambda: lead))
        modele = SimpleNamespace(all_objects=manager, _default_manager=manager)
        element = SimpleNamespace(content_type_id=1, object_id=7, cle_modele="crm.lead",
                                  content_type=SimpleNamespace(model_class=lambda: modele))
        services._restauration_generique(element)
    finally:
        for k, v in gardes.items():
            if v is None: sys.modules.pop(k, None)
            else: sys.modules[k] = v
    repro = (not lead.is_archived) and bool(lead.archived_at)
    return {"repro": repro, "observe": {"is_deleted": lead.is_deleted, "is_archived": lead.is_archived,
                                        "archived_at": lead.archived_at, "archived_by": lead.archived_by,
                                        "ecritures": [str(s) for s in lead.saves]}}


if __name__ == "__main__":
    print(sonde())
