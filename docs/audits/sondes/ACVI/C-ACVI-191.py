# flake8: noqa  (sonde de critique de complétude PA1 — Fable B.6, rejouable par scripts/sonde.py)
"""C-ACVI-191 — le non-risque « prix_achat : aucune réponse du parcours ne le porte » du dossier repose sur
`parcours-PA1.py`, dont le lead n'a AUCUN devis : l'oracle était vide. Ici un devis RÉEL de la démo, lié à
un lead, reçoit des sentinelles (`Produit.prix_achat` = 4321.57 sur sa première ligne, `Devis.marge_snapshot`
= 8765.43), puis toutes les surfaces de lecture de PA1 qui portent le devis sont balayées : fiche, liste,
jalons, résumé associé, historique, panneau d'appel, file de relances et message de touche, visite
(`client_panel` + devis), chaîne commerciale, export xlsx (cellules lues), message de visite, aperçu WhatsApp
devis, questionnaire public (prefill), et, en contraste PA3, le détail ventes du devis. Deux lecteurs :
`demo_admin` et un rôle Commercial créé dans la société (sans droits admin). Transaction annulée."""
SONDE = {"constat": "C-ACVI-191", "sha": "352ae5455",
         "attendu": "aucune surface PA1 (interne ou publique) ne porte prix_achat / marge_snapshot / les "
                    "sentinelles ; sinon : surface, lecteur et clé nommés",
         "modeles": ["crm.Lead", "ventes.Devis", "ventes.LigneDevis", "stock.Produit",
                     "visites.VisiteTerrain", "roles.Role"]}


def sonde(ctx):
    import datetime as dt
    import io
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from rest_framework.test import APIClient
    from apps.crm.models import Lead
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.questionnaire import mint_lien
    from apps.roles.models import Role
    from apps.roles.permissions_registre import COMMERCIAL_PERMISSIONS
    from apps.stock.models import Produit
    from apps.ventes.models import Devis
    from apps.visites.models import VisiteTerrain
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    SENT_PA, SENT_M = Decimal('4321.57'), Decimal('8765.43')
    MOTS = ('prix_achat', 'marge_snapshot', 'marge_ht', '4321.57', '8765.43')

    d = (Devis.objects.filter(company=c, lead__isnull=False, lignes__isnull=False, is_active=True)
         .select_related('lead').order_by('-id').first())
    if d is None:
        return 'STATIQUE : aucun devis lié à un lead dans la société démo'
    lead = d.lead
    ligne = d.lignes.order_by('id').first()
    prod = ligne.produit or Produit.objects.filter(company=c).order_by('id').first()
    prod.prix_achat = SENT_PA
    prod.save(update_fields=['prix_achat'])
    if ligne.produit_id != prod.id:
        ligne.produit = prod
        ligne.save(update_fields=['produit'])
    Devis.objects.filter(pk=d.pk).update(marge_snapshot=SENT_M)
    lead.owner = ua
    lead.save(update_fields=['owner'])

    r_com = Role.objects.create(company=c, nom='Commercial sonde 191', permissions=list(COMMERCIAL_PERMISSIONS))
    com = U.objects.create_user(username='s191-com', password='x', company=c, role=r_com)
    api_a, api_c = APIClient(), APIClient()
    api_a.force_authenticate(ua)
    api_c.force_authenticate(com)

    # une visite sur ce lead (client_panel + devis en lecture)
    demain = (timezone.localdate() + dt.timedelta(days=2)).isoformat()
    with transaction.atomic():
        rv = api_a.post('/api/django/visites/visites/', {'lead': lead.id, 'date_prevue': demain}, format='json',
                        HTTP_HOST='localhost')
    vis = VisiteTerrain.objects.filter(lead=lead).order_by('-id').first()
    touche = RelanceEtape.objects.filter(lead=lead).order_by('-id').first()
    lien, _, _ = mint_lien(lead, user=ua)

    def texte_de(r):
        ct = r.get('Content-Type', '')
        octets = bytes(getattr(r, 'content', b''))
        if 'spreadsheet' in ct or octets[:2] == b'PK':
            try:
                import openpyxl
                wb = openpyxl.load_workbook(io.BytesIO(octets), read_only=True, data_only=True)
                return ' '.join(str(v) for ws in wb.worksheets for row in ws.iter_rows(values_only=True)
                                for v in row if v is not None) + ' [xlsx]'
            except Exception as e:
                return f'[xlsx illisible {e!r}]'
        return octets.decode('utf-8', 'replace')

    def balayer(cl, meth, u, corps=None):
        try:
            with transaction.atomic():
                r = getattr(cl, meth)(u, corps or {}, format='json', HTTP_HOST='localhost')
        except Exception as e:
            return {'statut': 599, 'exc': repr(e)[:160]}
        t = texte_de(r)
        hits = {m: t.count(m) for m in MOTS if m in t}
        out = {'statut': r.status_code, 'hits': hits, 'taille': len(t)}
        if hits:
            i = min(t.find(m) for m in hits)
            out['extrait'] = t[max(0, i - 80):i + 120]
        return out

    L = f'/api/django/crm/leads/{lead.id}/'
    surfaces = [
        ('lead retrieve', 'get', L), ('lead list search', 'get', f'/api/django/crm/leads/?search={lead.nom}'),
        ('jalons-devis', 'get', L + 'jalons-devis/'), ('resume-associe', 'get', L + 'resume-associe/'),
        ('historique', 'get', L + 'historique/'), ('lead visites', 'get', L + 'visites/'),
        ('references-proches', 'get', L + 'references-proches/'),
        ('panneau-appel', 'get', L + 'panneau-appel/'),
        ('message-visite', 'get', L + 'message-visite/?cle=visite_proposition'),
        ('whatsapp-devis-apercu', 'get', L + f'whatsapp-devis-apercu/?devis={d.id}'),
        ('whatsapp-devis-apercu POST', 'post', L + 'whatsapp-devis-apercu/', {'devis': d.id, 'devis_ids': [d.id]}),
        ('relance-etapes ?lead', 'get', f'/api/django/crm/relance-etapes/?lead={lead.id}'),
        ('relance-etapes scope=all', 'get', '/api/django/crm/relance-etapes/?scope=all'),
        ('chaine-commerciale', 'get', '/api/django/crm/relance-etapes/chaine-commerciale/'),
        ('controle', 'get', '/api/django/crm/relance-etapes/controle/'),
        ('suivi', 'get', '/api/django/crm/relance-etapes/suivi/'),
        ('visites list', 'get', f'/api/django/visites/visites/?lead={lead.id}'),
        ('ma-journee', 'get', '/api/django/visites/ma-journee/?tous=1'),
        ('export-xlsx', 'get', '/api/django/crm/leads/export-xlsx/'),
        ('questionnaire public GET', 'get', f'/api/django/crm/public/questionnaire/{lien.token}/'),
        ('CONTRASTE PA3 ventes devis', 'get', f'/api/django/ventes/devis/{d.id}/'),
    ]
    if vis is not None:
        surfaces.append(('visite retrieve', 'get', f'/api/django/visites/visites/{vis.id}/'))
    if touche is not None:
        surfaces.append(('touche message', 'get', f'/api/django/crm/relance-etapes/{touche.id}/message/'))
        surfaces.append(('touche retrieve', 'get', f'/api/django/crm/relance-etapes/{touche.id}/'))
    obs = {'devis': d.id, 'lead': lead.id, 'visite': getattr(vis, 'id', None), 'touche': getattr(touche, 'id', None),
           'visite_post': rv.status_code, 'lignes': d.lignes.count(), 'produit': prod.id}
    pub = APIClient()
    res = {}
    for nom, meth, u, *corps in surfaces:
        cl = pub if nom.startswith('questionnaire') else api_a
        res[nom] = {'admin': balayer(cl, meth, u, corps[0] if corps else None)}
        if cl is api_a:
            res[nom]['commercial'] = balayer(api_c, meth, u, corps[0] if corps else None)
    obs['surfaces'] = res
    fuites = {n: {k: v for k, v in r.items() if v.get('hits')} for n, r in res.items()
              if any(v.get('hits') for v in r.values())}
    obs['fuites'] = fuites
    fuites_pa1 = {n: v for n, v in fuites.items() if not n.startswith('CONTRASTE')}
    return {'repro': bool(fuites_pa1), 'observe': obs}
