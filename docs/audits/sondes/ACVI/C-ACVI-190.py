# flake8: noqa  (sonde de critique de complétude PA1 — Fable B.6, rejouable par scripts/sonde.py)
"""C-ACVI-190 — le questionnaire PUBLIC (`public/questionnaire/<token>/`, AllowAny) est une porte
d'ÉCRITURE sur le lead que personne n'a jouée : `resoudre` ne ferme le lien qu'au soft-delete (docstring :
« un lead simplement ARCHIVÉ reste ouvert »), et `appliquer_section` écrit `setattr(lead, …)` + recalcul du
score + signal client + touche signal + file devis auto, sans regarder perdu / opposé / absorbé par fusion.
Cas joués (société démo, transaction annulée) : (0) ce que le GET expose au porteur du jeton ; (1) lead A
absorbé par fusion dans B (archivé, QuestionnaireLien resté sur A — C-ACVI-021) : le client répond sur le
jeton d'A → où vont ses réponses ? (2) lead perdu ; (3) lead « ne plus contacter » ; (4) valeur tapée par
un humain (marquée `saisies_humaines`) puis réponse client différente sans `prefill_vu` ; (5) témoin vivant.
Attendu (C17/C5) : une réponse client sur une fiche close est refusée ou redirigée vers le survivant ;
jamais une file devis / une touche sur un opposé."""
SONDE = {"constat": "C-ACVI-190", "sha": "352ae5455",
         "attendu": "fiche absorbée : réponse refusée ou portée au survivant ; opposé/perdu : aucune touche, "
                    "aucune file devis ; défaut supposé : écriture sur l'archivé, survivant intact",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.QuestionnaireLien",
                     "notifications.Notification"]}


def sonde(ctx):
    from apps.crm import stages
    import json
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from rest_framework.test import APIClient
    from apps.crm.models import Lead, LeadActivity, QuestionnaireLien
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.questionnaire import mint_lien
    from apps.crm.leads_fusion import merge_leads
    from apps.notifications.models import Notification
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    api = APIClient()
    api.force_authenticate(ua)
    pub = APIClient()  # anonyme : le client

    def url(token):
        return f'/api/django/crm/public/questionnaire/{token}/'

    def appel(cl, meth, u, corps=None):
        try:
            with transaction.atomic():
                r = getattr(cl, meth)(u, corps or {}, format='json', HTTP_HOST='localhost')
            try:
                return r.status_code, json.loads(r.content.decode('utf-8', 'replace'))
            except Exception:
                return r.status_code, {}
        except Exception as e:
            return 599, {'_exc': repr(e)[:200]}

    def lead(nom, tel, **kw):
        return Lead.objects.create(company=c, nom=nom, prenom='Sonde', telephone=tel, ville='Casablanca',
                                   type_installation='residentiel', owner=ua, facture_hiver=Decimal('900'), **kw)

    def etat(l):
        l.refresh_from_db()
        return {'fh': str(l.facture_hiver), 'kwh': str(l.conso_mensuelle_kwh), 'score': l.score,
                'arch': l.is_archived, 'perdu': l.perdu, 'npc': l.ne_plus_contacter,
                'sh': l.saisies_humaines, 'act': LeadActivity.objects.filter(lead=l).count(),
                'touches': list(RelanceEtape.objects.filter(lead=l, statut='a_faire')
                                .values_list('libelle', flat=True)[:3]),
                'notifs': Notification.objects.filter(company=c).count()}

    def repondre(token, reponses, section='energie'):
        cel = len(ctx['celery'])
        s, r = appel(pub, 'post', url(token), {'section': section, 'reponses': reponses})
        return {'statut': s, 'corps': (r if s != 200 else {k: r.get(k) for k in ('enregistrees', 'ignorees', 'devis_possible')}),
                'celery': ctx['celery'][cel:]}

    obs = {}
    # 0. exposition du GET
    A = lead('Absorbe', '0661000190')
    lienA, _, _ = mint_lien(A, user=ua)
    s, g = appel(pub, 'get', url(lienA.token))
    pf = (g.get('prefill') or {}) if isinstance(g, dict) else {}
    obs['get_public'] = {'statut': s, 'cles': sorted(g.keys()) if isinstance(g, dict) else g,
                         'prefill_non_nuls': {k: v for k, v in pf.items() if v not in (None, False)},
                         'nb_colonnes_prefill': len(pf), 'prenom': g.get('prenom') if isinstance(g, dict) else None}
    # 1. fusion : A absorbé par B
    B = lead('Survivant', '0661000190')
    merge_leads(B, [A], ua)
    s_get, _ = appel(pub, 'get', url(lienA.token))
    av_A, av_B = etat(A), etat(B)
    rep = repondre(lienA.token, {'facture_hiver': 1500, 'conso_mensuelle_kwh': 650})
    ap_A, ap_B = etat(A), etat(B)
    obs['absorbe'] = {'get_apres_fusion': s_get, 'lien_sur': QuestionnaireLien.objects.get(pk=lienA.pk).lead_id,
                      'A_id': A.id, 'B_id': B.id, 'post': rep, 'A_avant': av_A, 'A_apres': ap_A,
                      'B_avant': av_B, 'B_apres': ap_B,
                      'notes_A': [(b or '')[:60] for b in LeadActivity.objects.filter(lead=A).order_by('-id')
                                  .values_list('body', flat=True)[:3]]}
    # 2. perdu
    C = lead('Perdu', '0661000191', perdu=True, motif_perte='sonde')
    lienC, _, _ = mint_lien(C, user=ua)
    av = etat(C)
    rep = repondre(lienC.token, {'facture_hiver': 1500})
    obs['perdu'] = {'post': rep, 'avant': av, 'apres': etat(C)}
    # 3. ne plus contacter
    D = lead('Oppose', '0661000192', ne_plus_contacter=True)
    lienD, _, _ = mint_lien(D, user=ua)
    av = etat(D)
    rep = repondre(lienD.token, {'facture_hiver': 1500})
    obs['oppose'] = {'post': rep, 'avant': av, 'apres': etat(D)}
    # 4. humain marqué puis client (sans prefill_vu)
    E = lead('Humain', '0661000193')
    s, _ = appel(api, 'patch', f'/api/django/crm/leads/{E.id}/', {'facture_hiver': '950'})
    lienE, _, _ = mint_lien(E, user=ua)
    av = etat(E)
    rep = repondre(lienE.token, {'facture_hiver': 1500})
    obs['humain_puis_client'] = {'patch': s, 'post': rep, 'avant': av, 'apres': etat(E)}
    # 5. témoin vivant
    F = lead('Vivant', '0661000194')
    lienF, _, _ = mint_lien(F, user=ua)
    av = etat(F)
    rep = repondre(lienF.token, {'facture_hiver': 1500, 'conso_mensuelle_kwh': 650})
    obs['temoin_vivant'] = {'post': rep, 'avant': av, 'apres': etat(F)}
    # 6. section hors whitelist / clé hors section
    rep = repondre(lienF.token, {'stage': stages.SIGNED, 'owner': None, 'ne_plus_contacter': False,
                                 'score_ajustement': 100, 'facture_hiver': 1600})
    F.refresh_from_db()
    obs['cles_hors_section'] = {'post': rep, 'stage': F.stage, 'facture_hiver': str(F.facture_hiver)}
    rep = repondre(lienF.token, {'nom': 'X'}, section='pipeline')
    obs['section_inconnue'] = rep['statut']

    absorbe = obs['absorbe']
    repro = (absorbe['post']['statut'] == 200
             and absorbe['A_apres']['fh'] != absorbe['A_avant']['fh']
             and absorbe['B_apres']['fh'] == absorbe['B_avant']['fh'])
    return {'repro': repro, 'observe': obs}
