# flake8: noqa  (sonde de vérification PA1, rejouable par scripts/sonde.py — AMET93)
"""Cadence v4 (lane C), société démo, services réels du moteur — chaque cas dans son point de sauvegarde :
C-1 (avenant sur lead SIGNÉ : clôture « fait » de l'étape posée par `poser_tache_avenant` → barreau `generique`
ordre 2 naît ? + variante touche signal close `non_joint`) ; C-7 (`appliquer_visite_planifiee` : touche `contact`
intacte ?) ; C-8 (parcage au Froid : étape de filet `generique` reste À FAIRE ?) ; C-9 (`erase_crm` : touches
continuent ?) ; C-10 (`annuler_touche_relance` sur lead archivé entre-temps) ; C-11 (double « fait » de la même
instance : 2 lignes `appel`) ; C-12 (rappel convenu glissé par une touche signal). Transaction annulée."""
SONDE = {"constat": "C-ACVI-200+206+207+208+209+210+211", "sha": "352ae5455",
         "attendu": "défaut : generique ordre 2 a_faire sur SIGNÉ ; touche contact non recalée ; filet generique a_faire "
                    "au Froid ; touches a_faire après effacement ; touche remise a_faire sur archivé ; 2 lignes appel ; "
                    "due_at ≠ rappel convenu",
         "modeles": ["crm.Lead", "crm.LeadActivity", "crm.RelanceEtape", "crm.CadenceRelanceEtape"]}


def sonde(ctx):
    from apps.crm import stages
    import datetime as dt
    import traceback
    from types import SimpleNamespace
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.utils import timezone
    from apps.crm.models import Lead, LeadActivity
    from apps.crm.models_cadence import RelanceEtape
    from apps.crm import horaires
    from apps.crm.cadence_plan import demarrer_cadence_contact, reporter_prochaine_touche
    from apps.crm.cadence_touche import marquer_etape_relance, annuler_touche_relance
    from apps.crm.cadence_visite import appliquer_visite_planifiee
    from apps.crm.cadence_filet import assurer_prochaine_etape_apres_succes
    from apps.crm.cadence_signaux import poser_touche_signal
    from apps.crm.receivers_cadence import poser_tache_avenant
    from apps.crm.fiche_funnel import parquer_lead
    from apps.crm.dsr_provider import erase_crm
    U = get_user_model()
    ua = U.objects.filter(username='demo_admin', is_active=True).first()
    c = ua.company
    obs = {}
    n = [0]

    def lead(nom, **kw):
        n[0] += 1
        kw.setdefault('telephone', '+2126002000%02d' % n[0])
        return Lead.objects.create(company=c, nom=nom, prenom='ACVI200', owner=ua,
                                   email='acvi200-%d@example.invalid' % n[0], ville='Casablanca', **kw)

    def touches(l):
        return [(t.id, t.cadence, t.ordre, (t.libelle or '')[:45], t.statut, str(t.due_at)[:16])
                for t in RelanceEtape.objects.filter(lead=l).order_by('id')]

    def premier_contact(l):
        return RelanceEtape.objects.filter(lead=l, cadence='contact', statut='a_faire').order_by('ordre', 'id').first()

    def cas(nom, f):
        try:
            with transaction.atomic():
                obs[nom] = f()
        except Exception:
            obs[nom] = {'ERREUR': traceback.format_exc()[-500:]}

    # C-1
    def c1():
        l = lead('Avenant')
        Lead.objects.filter(pk=l.pk).update(stage=stages.SIGNED)
        l.refresh_from_db()
        e = poser_tache_avenant(l, SimpleNamespace(reference='D-ACVI200'), ua)
        av = touches(l)
        marquer_etape_relance(e, ua, 'fait')
        ap = touches(l)
        nees = [t for t in ap if t[1] == 'generique' and t[4] == 'a_faire']
        # variante : touche signal sur un lead NEW en cadence contact, close non_joint
        l2 = lead('Signal')
        demarrer_cadence_contact(l2, user=ua, origine='sonde')
        ts = poser_touche_signal(l2, 'questionnaire', user=ua)
        av2 = touches(l2)
        if ts is not None:
            marquer_etape_relance(ts, ua, 'fait', outcome='non_joint')
        ap2 = touches(l2)
        return {'stage': l.stage, 'etape_avenant': (e.cadence, e.ordre, e.libelle[:45]) if e else None,
                'avant': av, 'apres': ap, 'generique_a_faire_apres': nees,
                'variante_signal': {'touche_signal': (ts.cadence, ts.ordre, ts.libelle[:40]) if ts else None,
                                    'avant': av2, 'apres': ap2,
                                    'generique_nees': [t for t in ap2 if t[1] == 'generique' and t[4] == 'a_faire'
                                                       and t not in av2]},
                'defaut': any(t[2] == 2 for t in nees)}
    cas('C1', c1)

    # C-7
    def c7():
        l = lead('Visite')
        demarrer_cadence_contact(l, user=ua, origine='sonde')
        t = premier_contact(l)
        av = (t.id, str(t.due_at), t.statut) if t else None
        appliquer_visite_planifiee(l, ua, timezone.localdate() + dt.timedelta(days=3))
        t2 = RelanceEtape.objects.get(pk=t.pk) if t else None
        return {'avant': av, 'apres': (t2.id, str(t2.due_at), t2.statut) if t2 else None, 'touches': touches(l),
                'defaut': bool(t2 and t2.statut == 'a_faire' and str(t2.due_at) == av[1])}
    cas('C7', c7)

    # C-8
    def c8():
        l = lead('Froid')
        Lead.objects.filter(pk=l.pk).update(stage=stages.CONTACTED, first_contacted_at=timezone.now())
        l.refresh_from_db()
        filet = assurer_prochaine_etape_apres_succes(l, ua)
        av = touches(l)
        mode = 'exiger_touche=True'
        try:
            parquer_lead(l, 'pas_maintenant_sans_date', None, ua)
        except Exception as e:
            mode = 'exiger_touche=False (refus : %s)' % str(e)[:80]
            parquer_lead(l, 'pas_maintenant_sans_date', None, ua, exiger_touche=False)
        l.refresh_from_db()
        ap = touches(l)
        return {'stage': l.stage, 'parc_etat': l.parc_etat, 'mode': mode, 'avant': av, 'apres': ap,
                'defaut': l.stage == stages.COLD and any(t[1] == 'generique' and t[4] == 'a_faire' for t in ap)}
    cas('C8', c8)

    # C-9
    def c9():
        l = lead('Dsr')
        demarrer_cadence_contact(l, user=ua, origine='sonde')
        av = RelanceEtape.objects.filter(lead=l, statut='a_faire').count()
        r = erase_crm(c, l.email)
        l.refresh_from_db()
        return {'a_faire_avant': av, 'retour': str(r)[:200], 'nom_apres': l.nom, 'tel_apres': l.telephone,
                'a_faire_apres': RelanceEtape.objects.filter(lead=l, statut='a_faire').count(),
                'defaut': RelanceEtape.objects.filter(lead=l, statut='a_faire').exists()}
    cas('C9', c9)

    # C-10
    def c10():
        l = lead('Annuler')
        demarrer_cadence_contact(l, user=ua, origine='sonde')
        t = premier_contact(l)
        marquer_etape_relance(t, ua, 'fait', outcome='non_joint')
        l.refresh_from_db()
        l.is_archived = True
        l.save(update_fields=['is_archived'])
        refus = None
        try:
            annuler_touche_relance(RelanceEtape.objects.get(pk=t.pk), ua)
        except Exception as e:
            refus = '%s: %s' % (type(e).__name__, str(e)[:120])
        t.refresh_from_db()
        return {'statut_apres_annulation': t.statut, 'refus': refus, 'archive': True,
                'touches': touches(l), 'defaut': refus is None and t.statut == 'a_faire'}
    cas('C10', c10)

    # C-11
    def c11():
        l = lead('Double')
        demarrer_cadence_contact(l, user=ua, origine='sonde')
        t = premier_contact(l)
        n0 = LeadActivity.objects.filter(lead=l, kind='appel').count()
        erreurs = []
        for _ in range(2):
            try:
                marquer_etape_relance(t, ua, 'fait', outcome='non_joint')
            except Exception as e:
                erreurs.append('%s: %s' % (type(e).__name__, str(e)[:100]))
        lignes = list(LeadActivity.objects.filter(lead=l, kind='appel').values_list('body', flat=True))
        return {'lignes_appel_ajoutees': len(lignes) - n0, 'corps': [x[:70] for x in lignes], 'erreurs': erreurs,
                'touches': touches(l), 'defaut': len(lignes) - n0 >= 2}
    cas('C11', c11)

    # C-12
    def c12():
        l = lead('Convenu')
        demarrer_cadence_contact(l, user=ua, origine='sonde')
        t = premier_contact(l)
        demain = timezone.localdate() + dt.timedelta(days=1)
        quand = dt.datetime.combine(demain, dt.time(10, 0), tzinfo=horaires.CASABLANCA)
        reporter_prochaine_touche(l, ua, quand, etape=t)
        t.refresh_from_db()
        av = (str(t.due_at), str(t.rappel_convenu_le))
        ts = poser_touche_signal(l, 'proposition_rouverte', user=ua)
        t.refresh_from_db()
        return {'apres_report': av, 'touche_signal': (str(ts.due_at) if ts else None),
                'apres_signal': (str(t.due_at), str(t.rappel_convenu_le)),
                'defaut': av[0] != str(t.due_at) and str(t.rappel_convenu_le) == str(demain)}
    cas('C12', c12)

    obs['defauts'] = {k: (v.get('defaut') if isinstance(v, dict) else None) for k, v in obs.items()}
    return {'repro': any(bool(x) for x in obs['defauts'].values()), 'observe': obs}
