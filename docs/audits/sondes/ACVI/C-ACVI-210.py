# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py — AMET93)
"""C-11 — double « Fait » de la MÊME instance de touche (`marquer_etape_relance` deux fois, séquentiel) : deux
lignes de chatter de tentative ? Cas 1 : la touche APPEL « Appel d'ouverture » (ordre 2) ; cas 2 : la touche
WhatsApp « Message d'identité » (ordre 1). Comptage de TOUTES les LeadActivity créées (tous kinds) et de
`nb_contacts_humains`. Témoin d'unicité : une seule touche suivante. Transaction annulée."""
SONDE = {"constat": "C-ACVI-210", "sha": "352ae5455",
         "attendu": "défaut : 2 lignes de tentative (kind appel / whatsapp) pour la même touche, nb_contacts_humains +2",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape"]}


def sonde(ctx):
    import traceback
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm.cadence_plan import demarrer_cadence_contact
    from apps.crm.cadence_touche import marquer_etape_relance
    from apps.crm import fiche_funnel
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    obs = {}
    for i, ordre in enumerate((2, 1)):
        try:
            with transaction.atomic():
                l = Lead.objects.create(company=c, nom='Double%d' % ordre, prenom='ACVI210', owner=ua,
                                        telephone='+21260021000%d' % i, email='acvi210-%d@example.invalid' % i)
                demarrer_cadence_contact(l, user=ua, origine='sonde')
                t = RelanceEtape.objects.filter(lead=l, cadence='contact', ordre=ordre).first()
                if t is None:
                    obs['ordre_%d' % ordre] = {'touches': list(RelanceEtape.objects.filter(lead=l).values_list('cadence', 'ordre', 'libelle'))}
                    continue
                ids0 = set(LeadActivity.objects.filter(lead=l).values_list('id', flat=True))
                nb0 = fiche_funnel.nb_contacts_humains(l) if hasattr(fiche_funnel, 'nb_contacts_humains') else None
                res = []
                for _ in range(2):
                    try:
                        marquer_etape_relance(t, ua, 'fait', outcome='non_joint')
                        res.append('ok')
                    except Exception as e:
                        res.append('%s: %s' % (type(e).__name__, str(e)[:100]))
                nouvelles = list(LeadActivity.objects.filter(lead=l).exclude(id__in=ids0)
                                 .values_list('kind', 'user_id', 'body'))
                nb1 = fiche_funnel.nb_contacts_humains(l) if nb0 is not None else None
                obs['ordre_%d' % ordre] = {
                    'touche': (t.canal, t.libelle), 'appels': res,
                    'lignes_creees': [(k, bool(u), (b or '')[:70]) for k, u, b in nouvelles],
                    'nb_contacts_humains': [nb0, nb1],
                    'touches_apres': list(RelanceEtape.objects.filter(lead=l).order_by('id')
                                          .values_list('ordre', 'libelle', 'statut')),
                    'defaut': sum(1 for k, u, b in nouvelles if k in ('appel', 'whatsapp') and 'Touche' in (b or '')) >= 2,
                }
        except Exception:
            obs['ordre_%d' % ordre] = {'ERREUR': traceback.format_exc()[-500:]}
    return {'repro': any(isinstance(v, dict) and v.get('defaut') for v in obs.values()), 'observe': obs}
