# flake8: noqa  (sonde de contre-visite « vérifie AFAC » 2e clôture, rejouable par scripts/sonde.py — AMET93)
"""AFAC99 — oracle 10 (`manage.py audit_coherence` sans violation sur la société démo) jamais joué :
l'enregistrement `docs/audits/acceptation/AFAC/2026-10-29-0cd6d9cbd.md` le porte NA sur les 13 étapes et le
DONE LOG ne lie aucune sortie. Cette sonde rejoue l'auditeur de cohérence EN LECTURE SEULE
(`run_audit(persist=False)`) sur la société démo locale `taqinor-demo` (qui porte les factures créées par
la spec `frontend/e2e/acceptation/afac.spec.js`) et rapporte les violations par règle, en isolant celles
qui visent une facture / un avoir / un paiement. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AFAC-VER2-030", "sha": "1dfa7986c",
         "attendu": "run_audit(taqinor-demo, persist=False) : 0 violation sur les objets de facturation (facture, avoir, paiement, note de débit) ; sinon la liste des règles violées = oracle 10 d'AFAC99 rouge",
         "modeles": ["ventes.ViolationCoherence", "facturation.Facture", "ventes.Paiement"]}


def sonde(ctx):
    from collections import Counter
    from authentication.models import Company
    from apps.ventes.coherence.moteur import run_audit
    co = Company.objects.filter(slug='taqinor-demo').first()
    if co is None:
        return {'repro': False, 'erreur': 'société démo taqinor-demo absente de la base locale'}
    rep = run_audit(company=co, persist=False).as_json()
    viol = rep['violations']
    # Seuls les objets de FACTURATION (object_type 'facture') : les règles ETU_/CAL_/QUOTE_BUILD visent des devis.
    fact = [v for v in viol if v.get('object_type') == 'facture']
    err_fact = [e for e in rep['rule_errors'] if e.get('object_type') == 'facture']
    par_regle = Counter(v['rule'] for v in viol)
    par_regle_fact = Counter(v['rule'] for v in fact)
    exemples = [{k: v.get(k) for k in ('rule', 'severity', 'object_type', 'reference', 'message', 'values')}
                for v in fact[:12]]
    from apps.ventes.models import Facture
    detail = []
    for v in fact[:12]:
        f = Facture.objects.filter(pk=v.get('object_id')).first()
        if f is not None:
            detail.append({'ref': f.reference, 'statut': f.statut, 'date_emission': str(f.date_emission),
                           'date_echeance': str(getattr(f, 'date_echeance', None)), 'ttc': str(f.montant_ttc),
                           'du': str(f.montant_du), 'date_creation': str(getattr(f, 'date_creation', getattr(f, 'date', '')))})
    obs = {'checked': rep['checked'], 'total_violations': len(viol), 'par_regle': dict(par_regle),
           'violations_facturation': len(fact), 'par_regle_facturation': dict(par_regle_fact),
           'rule_errors_facture': err_fact[:10], 'nb_rule_errors_devis': len(rep['rule_errors']) - len(err_fact),
           'exemples_facturation': exemples, 'detail_factures': detail}
    print(f'obs={obs}')
    # REPRO = l'oracle 10 est VERT (aucune violation de facturation, aucune erreur de règle).
    return {'repro': not fact and not err_fact, **obs}
