SONDE = {"constat": "C-AMOT-HXH-COHERENCE", "sha": "673ec3f92",
         "attendu": "P4.1 — `audit_coherence --json --no-persist` (toutes sociétés, registre par défaut) : aucune "
                    "violation NOUVELLE, c.-à-d. absente des violations non résolues persistées par la dernière passe "
                    "nocturne locale (ventes_violationcoherence) ; aucune erreur de règle autre que le refus de sécurité « aucune option ne contient d'onduleur » ; détail des règles moteur "
                    "DOC_* (dont DOC_RENDU_SANS_MARGE et DOC_POMPAGE_SANS_OND*)"}


def sonde(ctx):
    import io
    import json
    from collections import Counter
    from django.core.management import call_command
    from django.db.models import Max
    from apps.ventes.models_coherence import ViolationCoherence
    buf = io.StringIO()
    call_command('audit_coherence', '--json', '--no-persist', stdout=buf)
    brut = buf.getvalue()
    rep = json.loads(brut[brut.index('{'):])
    connues = set(ViolationCoherence.objects.filter(resolved_at__isnull=True)
                  .values_list('rule_id', 'object_type', 'object_id'))
    base = ViolationCoherence.objects.aggregate(m=Max('last_seen'))['m']
    viol = rep.get('violations') or []
    nouvelles = [v for v in viol if (v.get('rule'), v.get('object_type'), v.get('object_id')) not in connues]
    par_regle = Counter(v.get('rule') for v in viol)
    out = {'base_persistee_last_seen': str(base), 'violations_connues_non_resolues': len(connues),
           'violations_rejeu': len(viol), 'par_regle': dict(par_regle.most_common()),
           'nouvelles': len(nouvelles),
           'nouvelles_detail': [{k: v.get(k) for k in ('rule', 'company', 'object_type', 'object_id', 'reference',
                                                       'message')} for v in nouvelles[:12]],
           'rule_errors': len(rep.get('rule_errors') or []),
           'rule_errors_detail': (rep.get('rule_errors') or [])[:5],
           'checked': rep.get('checked'), 'duration_s': rep.get('duration_s'),
           'doc_rendu_sans_marge_exemples': [{k: v.get(k) for k in ('company', 'reference', 'message')}
                                             for v in viol if v.get('rule') == 'DOC_RENDU_SANS_MARGE'][:4]}
    errs = rep.get('rule_errors') or []
    refus_securite = [e for e in errs if "aucune option ne contient d'onduleur" in (e.get('error') or '')]
    out['rule_errors_refus_sans_onduleur'] = len(refus_securite)
    out['rule_errors_autres'] = [e for e in errs if e not in refus_securite][:5]
    # une erreur de règle n'est pas une violation : seules comptent celles qui ne sont PAS le refus de sécurité
    # « aucune option ne contient d'onduleur » (devis démo sans onduleur, 409 par conception)
    out['repro'] = not nouvelles and len(refus_securite) == len(errs)
    return out
