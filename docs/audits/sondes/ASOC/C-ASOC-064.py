# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K66 — le journal WhatsApp (`notifications.WhatsAppMessageLog` : numéro + texte rendu) n'est ni
exporté, ni effacé, ni purgé.

Lead L (tél 0612000066) + 3 lignes de journal WhatsApp vers son numéro (texte contenant son prénom).
`core.dsr.exporter(company, tél)` : clés renvoyées (attendu : les messages listés) ;
`core.dsr.effacer(company, tél)` : relecture des 3 lignes (attendu : numéro et corps vidés) ;
registre de rétention : aucune politique pour le journal WhatsApp.
Témoin : le lead est bien anonymisé (scrub CRM fait)."""
SONDE = {"constat": "C-ASOC-064", "sha": "c514bd8ba",
         "attendu": "repro si après effacement les 3 logs gardent numéro+corps, export sans clé notifications, aucune politique de rétention whatsapp",
         "modeles": ["crm.Lead", "notifications.WhatsAppMessageLog"]}


def sonde(ctx):
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.notifications.models import WhatsAppMessageLog
    from core import dsr, retention
    co = Company.objects.create(nom='Sonde ASOC 064', slug='sonde-asoc-064')
    le = Lead.objects.create(company=co, nom='Idrissi', prenom='Mounir', telephone='0612000066')
    for i in range(3):
        WhatsAppMessageLog.objects.create(company=co, recipient='212612000066',
                                          body=f'Bonjour Mounir Idrissi, touche {i + 1} de votre étude solaire.')
    exp = dsr.exporter(co, '0612000066')
    res = dsr.effacer(co, '0612000066')
    le.refresh_from_db()
    logs = list(WhatsAppMessageLog.objects.filter(company=co).values('recipient', 'body'))
    politiques = retention.list_retention_policies()
    obs = {'export_cles': sorted(exp.keys()),
           'export_mentionne_whatsapp': 'Mounir Idrissi, touche' in str(exp),
           'effacer': {k: v for k, v in res.items() if k == 'crm'},
           'lead_apres': {'nom': le.nom, 'telephone': le.telephone},
           'logs_apres': logs,
           'politiques_retention': politiques,
           'politique_whatsapp': [p for p in politiques if 'whatsapp' in p.lower() or 'notif' in p.lower()]}
    print(obs)
    temoin_ok = le.telephone is None and le.nom != 'Idrissi'
    gardes = [l for l in logs if l['recipient'] == '212612000066' and 'Mounir' in l['body']]
    obs['logs_conserves'] = len(gardes)
    obs['temoin_ok'] = bool(temoin_ok)
    obs['repro'] = bool(temoin_ok and len(gardes) == 3 and not obs['export_mentionne_whatsapp'])
    return obs
