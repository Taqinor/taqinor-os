SONDE = {"constat": "C-ADOC-VER-013", "sha": "56d5b623a",
         "attendu": "une demande GED à chaîne en deux étapes approuvée depuis la boîte centrale des approbations "
                    "(/reporting/approbations-en-attente/decider/) par l'approbateur de l'étape 1 n'avance que "
                    "l'étape 1 (demande « en_attente », approbateur = étape 2), jamais une approbation finale"}


def sonde(ctx):
    from rest_framework.test import APIClient
    from authentication.models import Company
    from django.contrib.auth import get_user_model
    from apps.ged.models import Cabinet, Folder, Document, ChaineApprobationGed
    from apps.ged import services
    U = get_user_model()
    co = Company.objects.create(nom='SONDE-ADOC-VER-013', slug='sonde-adoc-ver-013')

    def _u(nom):
        # collaborateurs internes ordinaires (ni admin ni superuser) : a1 est l'approbateur désigné de l'étape 1
        return U.objects.create_user(username=f'sonde-adoc-ver-013-{nom}', password='x', company=co)
    demandeur, a1, a2 = _u('dem'), _u('a1'), _u('a2')
    cab = Cabinet.objects.create(company=co, nom='CAB')
    f = Folder.objects.create(company=co, cabinet=cab, nom='F')
    doc = Document.objects.create(company=co, folder=f, nom='procedure.pdf')
    dem = services.request_review(doc, user=demandeur, approbateur=a1)
    ChaineApprobationGed.objects.create(
        company=co, demande=dem, etape_courante=0,
        etapes=[{'approbateur_id': a1.pk, 'statut': 'en_cours', 'decision_le': None},
                {'approbateur_id': a2.pk, 'statut': 'en_attente', 'decision_le': None}])
    api = APIClient(raise_request_exception=False)
    api.force_authenticate(a1)
    r = api.post('/api/django/reporting/approbations-en-attente/decider/',
                 {'source': 'ged', 'id': dem.pk, 'decision': 'approuver', 'motif': ''},
                 format='json', HTTP_HOST='localhost')
    dem.refresh_from_db()
    doc.refresh_from_db()
    chaine = ChaineApprobationGed.objects.get(demande=dem)
    print(f"decider -> {r.status_code} ; demande.statut={dem.statut} ; approbateur={dem.approbateur_id} "
          f"(a2={a2.pk}) ; document.statut={doc.statut} ; etape_courante={chaine.etape_courante} ; "
          f"etapes={[e['statut'] for e in chaine.etapes]}")
    return {'repro': dem.statut != 'en_attente' and chaine.etapes[1]['statut'] != 'approuve'}
