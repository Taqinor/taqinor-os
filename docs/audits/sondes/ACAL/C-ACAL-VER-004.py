SONDE = {"constat": "C-ACAL-VER-004", "sha": "5ea32b58b",
         "attendu": "migration 0026 (pente racine -> pan) sur un calepinage lié à un devis ENVOYÉ : calepinage non modifié sans accord, conception_divergente reste False"}


def sonde(ctx):
    import importlib
    from django.apps import apps as registre
    from apps.ventes.models import Devis
    from apps.calepinage.models import Calepinage
    from apps.ventes.services import layout_hash
    from apps.ventes.selectors_calepinage import peremption_layout_devis
    M = importlib.import_module('apps.calepinage.migrations.0026_acal253_pente_racine_vers_pan')
    deja = Calepinage.objects.exclude(devis=None).values('devis')
    devis = Devis.objects.filter(statut='envoye').exclude(pk__in=deja).first()
    if devis is None:
        return "STATIQUE — aucun devis envoyé libre dans la base de démo"
    doc = {'version': 2, 'penteDeg': 30, 'penteSource': 'degres',
           'zones': [{'id': 'z1', 'label': 'Pan Sud', 'geometry': {'count': 4, 'azimuthDeg': 180}}]}
    h = layout_hash(doc)
    cal = Calepinage.objects.create(company=devis.company, titre='sonde ACAL VER-004', client_id=devis.client_id, lead_id=devis.lead_id)
    Calepinage.objects.filter(pk=cal.pk).update(roof_layout=doc, layout_hash=h, devis=devis)
    Devis.objects.filter(pk=devis.pk).update(layout_hash=h)
    devis.refresh_from_db(); cal.refresh_from_db()
    avant = peremption_layout_devis(devis, calepinage=cal)['conception_divergente']
    M.migrer_pente_racine(registre, None)
    cal.refresh_from_db()
    apres = peremption_layout_devis(devis, calepinage=cal)['conception_divergente']
    modifie = 'penteDeg' not in (cal.roof_layout or {})
    print(f"devis envoyé {devis.pk} : calepinage modifié={modifie}, conception_divergente {avant}->{apres}")
    return {'repro': modifie and (apres is True) and (avant is False)}
