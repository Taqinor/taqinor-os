# SONDE = {'constat': 'C-ADOC-VER-001', 'sha': '1a186a82c', 'attendu': "un employé non propriétaire du coffre ne voit PAS le lien_signature d'un document du coffre d'un collègue via /ged/signataires-demande/ (aujourd'hui : visible, puis le PDF est servi par le jeton)"}
# Écart de la garde ADOC37 : SignataireDemande (FK demande, pas document) échappe au balayage de visibilité.
import json, secrets
from rest_framework.test import APIClient
from authentication.models import CustomUser, Company
from apps.ged.models import Coffre, Cabinet, Folder, Document, DemandeSignatureDocument, SignataireDemande
from apps.ged import selectors
try:
    with transaction.atomic():
        co = Company.objects.create(nom='SONDE-ADOC-VER-001') if 'nom' in [f.name for f in Company._meta.fields] else Company.objects.create(name='SONDE-ADOC-VER-001')
        emp1 = CustomUser.objects.create(username='sonde_emp1', email='e1@sonde.invalid', company=co)
        emp2 = CustomUser.objects.create(username='sonde_emp2', email='e2@sonde.invalid', company=co)
        print('roles', getattr(emp1, 'role', None), getattr(emp2, 'role', None))
        cab = Cabinet.objects.create(company=co, nom='CAB')
        fol = Folder.objects.create(company=co, cabinet=cab, nom='F')
        cof = Coffre.objects.create(company=co, nom='Coffre emp1', proprietaire=emp1)
        d = Document.objects.create(company=co, folder=fol, coffre=cof, nom='SALAIRE-EMP1-CONFIDENTIEL.pdf')
        print('D visible emp2 ?', selectors.documents_visible_to_user(emp2).filter(pk=d.pk).exists())
        dem = DemandeSignatureDocument.objects.create(company=co, document=d, signataire_nom='X', signataire_email='x@sonde.invalid', token=secrets.token_urlsafe(16), routage='parallele')
        s = SignataireDemande.objects.create(company=co, demande=dem, nom='Y', email='y@sonde.invalid', token=secrets.token_urlsafe(16))
        c = APIClient(); c.force_authenticate(user=emp2)
        for url in ['/api/django/ged/demandes-signature/', '/api/django/ged/signataires-demande/', '/api/django/ged/champs-signature/']:
            r = c.get(url)
            body = json.dumps(r.json() if r.status_code == 200 else r.status_code, ensure_ascii=False)
            print(url, r.status_code, 'fuite_jeton=', s.token in body or dem.token in body, 'fuite_lien=', 'signataire/' in body)
        r = APIClient().get(f'/api/django/ged/signataire/{s.token}/')
        print('page publique du signataire (anonyme, jeton lu dans la liste)', r.status_code, str(r.content[:160]))
        print('mails', len(mail.outbox), 'celery', _CELERY_CALLS)
        raise R()
except R:
    print('ROLLED BACK')
