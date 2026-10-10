# SONDE = {'constat': 'C-ADOC-VER-002', 'sha': '1a186a82c', 'attendu': "un dépôt sans rapport (« facture.pdf », « certificat medecine.pdf ») ne solde JAMAIS la demande « CIN » : la checklist reste 'manquant' (aujourd'hui : soldée, 'present')"}
# Écart ADOC12 : matcher_depot_demandes rapproche par sous-chaîne et solde la demande UNIQUE en attente quel que soit le fichier.
from authentication.models import CustomUser
from apps.ged.models import Cabinet, Folder, Document, ExigenceDossier, DemandeDocument
from apps.ged import services
u = CustomUser.objects.get(username='demo_admin')
co = u.company
for nom_depot in ['facture.pdf', 'certificat medecine.pdf']:
  try:
        with transaction.atomic():
            cab = Cabinet.objects.create(company=co, nom='SONDE-ADOC12')
            f = Folder.objects.create(company=co, cabinet=cab, nom='Dossier RH sonde')
            ex = ExigenceDossier.objects.create(company=co, cabinet=cab, folder=f, libelle='CIN')
            dem = services.creer_demande_document(folder=f, company=co, libelle='CIN', created_by=u) if 'exigence' not in services.creer_demande_document.__code__.co_varnames else services.creer_demande_document(folder=f, company=co, libelle='CIN', created_by=u, exigence=ex)
            if not dem.exigence_id:
                dem.exigence = ex; dem.save(update_fields=['exigence'])
            avant = [(r.get('libelle'), r.get('statut')) for r in services.checklist_dossier(f)]
            d = Document.objects.create(company=co, folder=f, nom=nom_depot)
            soldee = services.matcher_depot_demandes(d)
            dem.refresh_from_db()
            apres = [(r.get('libelle'), r.get('statut')) for r in services.checklist_dossier(f)]
            print(f'dépôt {nom_depot!r} : checklist avant {avant} -> après {apres} ; demande CIN statut={dem.statut} document={dem.document_id == d.pk}')
            raise R()
  except R:
    pass
try:
    with transaction.atomic():
        raise R()
except R:
    print('mails', len(mail.outbox), 'celery', _CELERY_CALLS)
    print('ROLLED BACK')
