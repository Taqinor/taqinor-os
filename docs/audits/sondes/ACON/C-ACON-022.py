# flake8: noqa  (sonde d'audit PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""K22 — séparation des tâches (ACAL303, D-ACAL-11) : le concepteur D (porteur de calepinage_approuver,
un 2e approbateur E existe) peut-il approuver SA conception dès qu'un autre (C, auteur/porteur du
calepinage) a déposé la DERNIÈRE version ? Vraie route POST calepinages/<id>/approbation/ en client
API authentifié D. Cas A : C corrige un libellé de pan. Cas B : variante dessinée par D, retenue par C.
Témoin T : dernière version par D ⇒ 409 attendu. Écritures par les services réels (enregistrer_layout,
creer_variante, retenir_variante). Transaction annulée."""
SONDE = {"constat": "C-ACON-022", "sha": "33cba7f5d",
         "attendu": "repro si T=409 (garde vivante) et A ou B = 200 (accord pose par le concepteur D)",
         "modeles": ["calepinage.Calepinage", "calepinage.CalepinageVersion", "calepinage.CalepinageVariante"]}


def sonde(ctx):
    import copy
    import json
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.calepinage.models import Calepinage, CalepinageVersion
    from apps.calepinage.services.layout import enregistrer_layout
    from apps.calepinage.services.variantes import creer_variante, retenir_variante
    from apps.calepinage.tests.acal_livrables_helpers import LAYOUT_PLANCHE_SIMULABLE

    H = {'HTTP_HOST': 'localhost'}
    U = get_user_model()
    co = Company.objects.create(nom='Sonde ACON 022', slug='sonde-acon-022')
    C = U.objects.create_user(username='k22_commercial', password='x', role_legacy='admin', company=co)
    D = U.objects.create_user(username='k22_concepteur', password='x', role_legacy='admin', company=co)
    E = U.objects.create_user(username='k22_relecteur', password='x', role_legacy='admin', company=co)
    api_d = APIClient()
    api_d.force_authenticate(D)
    lead = Lead.objects.create(company=co, nom='Lead K22')
    base = copy.deepcopy(LAYOUT_PLANCHE_SIMULABLE)

    def variante_du(doc, n):
        doc = copy.deepcopy(doc)
        z = doc['zones'][0]
        z['label'] = f"{z.get('label') or 'PAN'}-v{n}"
        return doc

    def pivot(titre):
        c = Calepinage.objects.create(company=co, lead_id=lead.pk, titre=titre, roof_layout={},
                                      cree_par=C, responsable=C)
        for i in range(1, 7):  # D dessine 6 versions
            enregistrer_layout(c, variante_du(base, i), user=D, libelle=f'v{i} par D')
            c.refresh_from_db()
        return c

    def approuver(c):
        r = api_d.post(f'/api/django/calepinage/calepinages/{c.pk}/approbation/', {'decision': 'approuve'},
                       format='json', **H)
        c.refresh_from_db()
        derniere = (CalepinageVersion.objects.filter(calepinage_id=c.pk).order_by('-created_at', '-id')
                    .values_list('cree_par__username', flat=True).first())
        return {'http': r.status_code, 'corps': str(r.content[:160]),
                'versions_par_D': CalepinageVersion.objects.filter(calepinage_id=c.pk, cree_par=D).count(),
                'derniere_version_par': derniere,
                'etat': (c.approbation or {}).get('etat'),
                'decide_par': (c.approbation or {}).get('decide_par_id') == D.pk and 'D' or None}

    obs = {'E_actif_approbateur': E.is_active}
    t = pivot('K22-T')
    obs['T_temoin_derniere_par_D'] = approuver(t)
    a = pivot('K22-A')
    doc = copy.deepcopy(a.roof_layout)
    doc['zones'][0]['label'] = 'Pan sud (corrigé)'
    enregistrer_layout(a, doc, user=C, libelle='libellé corrigé par C')
    a.refresh_from_db()
    obs['A_libelle_corrige_par_C'] = approuver(a)
    b = pivot('K22-B')
    v = creer_variante(b, nom='Option B', roof_layout=variante_du(base, 99), user=D)
    obs['B_variante_cree_par'] = getattr(getattr(v, 'cree_par', None), 'username', None)
    retenir_variante(v, user=C)
    b.refresh_from_db()
    obs['B_variante_de_D_retenue_par_C'] = approuver(b)
    obs['repro'] = bool(obs['T_temoin_derniere_par_D']['http'] == 409 and (
        obs['A_libelle_corrige_par_C']['http'] == 200 or obs['B_variante_de_D_retenue_par_C']['http'] == 200))
    print(json.dumps(obs, default=str, ensure_ascii=False))
    return {'repro': obs['repro']}
