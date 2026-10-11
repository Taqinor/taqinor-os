SONDE = {"constat": "C-ADOC-VER-006", "sha": "6f3191ad7",
         "attendu": "regénérer depuis un modèle modifié un document dont une demande de signature est en attente est refusé (SignatureEnCoursError), le document garde UNE version"}


def sonde(ctx):
    from authentication.models import Company
    from apps.ged.models import ModeleDocument, DocumentVersion
    from apps.ged import services
    co = Company.objects.create(nom='SONDE-ADOC-VER-006', slug='sonde-adoc-ver-006')
    modele = ModeleDocument.objects.create(company=co, nom='M', corps_html='<p>{{ nom }} v1</p>')
    doc, c1 = services.generer_document(modele, {'nom': 'A'}, company=co)
    services.demander_signature(doc, signataire_nom='C', signataire_email='c@sonde.invalid', company=co, notifier=False)
    modele.corps_html = '<p>{{ nom }} v2</p>'
    modele.save()
    try:
        doc2, c2 = services.generer_document(modele, {'nom': 'A'}, company=co)
        refuse = False
        print(f"regénération acceptée : meme_doc={doc2.pk == doc.pk} cree={c2}")
    except Exception as exc:  # noqa: BLE001 — on veut voir le refus
        refuse = True
        print(f"refus : {type(exc).__name__} : {exc}")
    n = DocumentVersion.objects.filter(document=doc).count()
    print(f"création initiale cree={c1} ; versions du document après regénération = {n}")
    return {'repro': (not refuse) and n > 1}
