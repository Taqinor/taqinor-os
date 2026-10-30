SONDE = {"constat": "C-ASEC-014", "sha": "5908d43bb",
         "attendu": "refusé / inchangé : l'utilisateur dont l'ACL du document est en lecture seule -> 403 sur "
                    "purger, restaurer-corbeille, création de lien, fusionner ; opération par lot sans effet ; "
                    "document toujours en corbeille / non purgé / non lié ; le rédacteur ACL -> 201/200/204"}


def sonde(ctx):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ged.models import AclGed, Cabinet, Document, DocumentLien, Folder
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASEC014', slug='sonde-asec014-a')
    Company.objects.create(nom='Sonde ASEC014 B', slug='sonde-asec014-b')
    lecteur = User.objects.create_user(username='sonde-asec014-lecteur', password='x', company=co,
                                       role_legacy='responsable')
    redacteur = User.objects.create_user(username='sonde-asec014-redacteur', password='x', company=co,
                                         role_legacy='responsable')
    cab = Cabinet.objects.create(company=co, nom='Sonde cab')
    folder = Folder.objects.create(company=co, cabinet=cab, nom='Racine')
    doc = Document.objects.create(company=co, folder=folder, nom='sonde-contrat.pdf')
    autre = Document.objects.create(company=co, folder=folder, nom='sonde-annexe.pdf')
    AclGed.objects.create(company=co, document=doc, utilisateur=lecteur, niveau='lecture')
    AclGed.objects.create(company=co, document=doc, utilisateur=redacteur, niveau='ecriture')
    cli = Client.objects.create(company=co, nom='Sonde Cli')
    B = '/api/django/ged/'

    def api_de(u):
        api = APIClient()
        api.force_authenticate(u)
        return api

    def corbeille():
        Document.objects.filter(pk=doc.pk).update(supprime_le=timezone.now())

    def en_corbeille():
        d = Document.objects.filter(pk=doc.pk).first()
        return d is not None and d.supprime_le is not None

    gestes, refus_ok = {}, True
    corbeille()
    api = api_de(lecteur)
    r = api.post(f'{B}documents/{doc.pk}/purger/', **H)
    gestes['purger'] = [r.status_code, 'toujours_en_corbeille=%s' % en_corbeille()]
    refus_ok &= r.status_code == 403 and en_corbeille()
    r = api.post(f'{B}documents/{doc.pk}/restaurer-corbeille/', **H)
    gestes['restaurer_corbeille'] = [r.status_code, 'toujours_en_corbeille=%s' % en_corbeille()]
    refus_ok &= r.status_code == 403 and en_corbeille()
    Document.objects.filter(pk=doc.pk).update(supprime_le=None)
    r = api.post(f'{B}liens/', {'document': doc.pk, 'model': 'crm.client', 'id': cli.pk}, format='json', **H)
    lie = DocumentLien.objects.filter(document=doc).exists()
    gestes['creer_lien'] = [r.status_code, 'lien_cree=%s' % lie]
    refus_ok &= r.status_code == 403 and not lie
    r = api.post(f'{B}documents/fusionner/', {'documents': [autre.pk, doc.pk], 'cible': doc.pk}, format='json', **H)
    gestes['fusionner'] = [r.status_code, 'versions=%s' % doc.versions.count()]
    refus_ok &= r.status_code == 403 and doc.versions.count() == 0
    r = api.post(f'{B}documents/operations-lot/', {'documents': [doc.pk], 'operation': 'corbeille'},
                 format='json', **H)
    doc.refresh_from_db()
    lot_ok = r.status_code == 200 and r.data.get('resultats') == [] and len(r.data.get('erreurs', [])) == 1 \
        and doc.supprime_le is None
    gestes['operations_lot'] = [r.status_code, 'resultats=%s' % r.data.get('resultats'),
                                'erreurs=%d' % len(r.data.get('erreurs', [])), 'supprime_le=%s' % doc.supprime_le]
    refus_ok &= lot_ok

    # parcours legitime : redacteur ACL (ecriture)
    api = api_de(redacteur)
    r1 = api.post(f'{B}liens/', {'document': doc.pk, 'model': 'crm.client', 'id': cli.pk}, format='json', **H)
    corbeille()
    r2 = api.post(f'{B}documents/{doc.pk}/restaurer-corbeille/', **H)
    corbeille()
    r3 = api.post(f'{B}documents/{doc.pk}/purger/', **H)
    purge = not Document.objects.filter(pk=doc.pk).exists()
    leg = {'lien': r1.status_code, 'restaurer': r2.status_code, 'purger': r3.status_code, 'document_purge': purge}
    leg_ok = (r1.status_code, r2.status_code, r3.status_code) == (201, 200, 204) and purge
    return {'lecteur_acl_lecture': gestes, 'redacteur_acl_ecriture': leg, 'refus_ok': bool(refus_ok),
            'repro': bool(refus_ok and leg_ok)}
