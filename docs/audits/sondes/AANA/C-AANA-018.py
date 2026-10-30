"""Sonde AANA50 : rejoue C-AANA-018 (audit analyse du 05/10, F12) : les exports exposaient `{'leads':['token'],'devis':['marge_snapshot'],…}`."""
SONDE = {
    'constat': 'C-AANA-018',
    'sha': '5908d43bb',
    'attendu': "défaut absent : aucune colonne token / marge / prix_achat dans le registre d'export, ni dans un export réel (leads, devis, produits)",
}


def sonde(ctx):
    import csv
    import io
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.dataimport.export_registry import REGISTRY
    mots = ('token', 'marge', 'prix_achat')
    fautes = {k: [c for c in s.header() if any(m in c for m in mots)] for k, s in REGISTRY.items()}
    fautes = {k: v for k, v in fautes.items() if v}
    co = Company.objects.create(nom='Sonde 018', slug='sonde-aana-018')
    u = get_user_model().objects.create_user(username='sonde-aana-018', password='x', company=co, role_legacy='admin')
    api = APIClient()
    api.force_authenticate(u)
    reels = {}
    for cle in ('leads', 'devis', 'produits', 'products'):
        if cle not in REGISTRY:
            continue
        r = api.post('/api/django/imports/export-object/', {'object': cle, 'format': 'csv'}, format='json', HTTP_HOST='localhost')
        if r.status_code != 200:
            reels[cle] = 'HTTP %s' % r.status_code
            continue
        entete = next(csv.reader(io.StringIO(r.content.decode('utf-8-sig'))), [])
        reels[cle] = [c for c in entete if any(m in c.lower() for m in mots)]
    mauvais = {k: v for k, v in reels.items() if v}
    print('registre=%d objets, colonnes sensibles=%s ; exports réels=%s' % (len(REGISTRY), fautes, reels))
    return {'repro': not fautes and not mauvais and bool(reels), 'registre': fautes, 'exports': reels}
