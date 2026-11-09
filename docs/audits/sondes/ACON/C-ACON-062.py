# flake8: noqa  (sonde d'audit de parcours PA2 « Conception », rejouable par scripts/sonde.py — METHODE §C.4)
"""T3 — le calepinage d'un devis REFUSÉ (puis EXPIRÉ) : verrouillé (`verrou.est_verrouille`), inarchivable
(`archivage._refus_devis_porte` : « détachez-le d'abord » — geste qui n'existe pas, `services/liens.py`), bouton
caché (`permissions.peut_supprimer` faux), et il reste L'ouvert du lead (`selectors._ouverts`) : « Concevoir »
(POST depuis-lead) rend l'existant verrouillé, « Nouveau calepinage » (POST calepinages/ {lead}) ⇒ 409,
Dupliquer sans cible ⇒ 409. Vraies routes. Transaction annulée."""
SONDE = {"constat": "C-ACON-062", "sha": "819fe0f8c",
         "attendu": "repro si, devis refuse : est_verrouille vrai, archiver refuse avec « détachez », peut_supprimer faux, "
                    "depuis-lead 200 cree=False sur ce calepinage, POST calepinages {lead} 409",
         "modeles": ["ventes.Devis", "calepinage.Calepinage"]}


def sonde(ctx):
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client, Lead
    from apps.ventes.models import Devis
    from apps.calepinage.models import Calepinage
    from apps.calepinage.services.liens import lier_devis
    from apps.calepinage.services.verrou import est_verrouille
    from apps.calepinage.selectors import calepinage_ouvert_du_lead
    from apps.ventes.services import layout_hash

    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ACON 062', slug='sonde-acon-062')
    u = get_user_model().objects.create_user(username='sonde_acon_062', password='x',
                                             role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    cl = Client.objects.create(company=co, nom='Client T3')
    lead = Lead.objects.create(company=co, nom='Lead T3', prenom='Retour', client=cl)
    d = Devis.objects.create(company=co, reference='DEV-T3-01', client=cl, lead=lead, taux_tva=Decimal('20'),
                             statut='brouillon', created_by=u, mode_installation='residentiel')
    L = {'scenario': 'reseau', 'panelWatt': 550, 'result': {'panels': 12, 'kwc': 6.6, 'annualKwh': 10000}}
    c = Calepinage.objects.create(company=co, lead_id=lead.pk, client_id=cl.pk, titre='Toit T3', roof_layout=L,
                                  layout_hash=layout_hash(L))
    lier_devis(c, d.pk)
    C = '/api/django/calepinage/calepinages/'
    obs = {}
    for statut in ('refuse', 'expire'):
        Devis.objects.filter(pk=d.pk).update(statut=statut)
        c.refresh_from_db()
        m = {'est_verrouille': est_verrouille(c)}
        det = api.get(f'{C}{c.pk}/', **H)
        m['detail_peut_supprimer'] = (det.data.get('permissions') or {}).get('peut_supprimer') if det.status_code == 200 else det.status_code
        ra = api.post(f'{C}{c.pk}/archiver/', {}, format='json', **H)
        m['archiver_http'] = ra.status_code
        m['archiver_corps'] = ra.data if ra.status_code >= 400 else None
        c.refresh_from_db()
        m['archive_apres'] = c.archive_le is not None
        ouvert = calepinage_ouvert_du_lead(co, lead.pk)
        m['ouvert_du_lead'] = getattr(ouvert, 'pk', None)
        rl = api.post(f'{C}depuis-lead/', {'lead': lead.pk}, format='json', **H)
        m['depuis_lead_http'] = rl.status_code
        m['depuis_lead_cree'] = rl.data.get('cree') if isinstance(rl.data, dict) else None
        m['depuis_lead_calepinage'] = (rl.data.get('calepinage') or rl.data.get('id')) if isinstance(rl.data, dict) else None
        rc = api.post(C, {'lead': lead.pk, 'titre': 'Extension de toit'}, format='json', **H)
        m['creer_http'] = rc.status_code
        m['creer_corps'] = str(rc.data)[:200] if rc.status_code >= 400 else None
        rd = api.post(f'{C}{c.pk}/dupliquer/', {}, format='json', **H)
        m['dupliquer_sans_cible_http'] = rd.status_code
        g = api.get(f'{C}{c.pk}/layout/', **H)
        w = api.post(f'{C}{c.pk}/layout/', dict(L, panelWatt=560), format='json',
                     HTTP_IF_MATCH='"%s"' % ((g.data or {}).get('empreinte_document') or ''), **H)
        m['ecrire_layout_http'] = w.status_code
        m['ecrire_layout_corps'] = str(w.data)[:160] if w.status_code >= 400 else None
        obs[statut] = m
    print(json.dumps(obs, default=str, ensure_ascii=False)[:4000])
    r = obs['refuse']
    obs['repro'] = bool(r['est_verrouille'] and r['archiver_http'] >= 400
                        and 'détachez' in str(r['archiver_corps']) and r['detail_peut_supprimer'] is False
                        and r['ouvert_du_lead'] == c.pk and r['depuis_lead_cree'] is False
                        and r['creer_http'] == 409)
    return obs
