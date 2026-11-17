"""TENIR AVANT / APRÈS + détails POUSSER (refus, week-end, bascules). python run_tenir.py. Synthétique."""
import statistics
import banc
import personas as P

T0 = ((0, 'tenir'),)
GR = banc.GRAINES


def alertes(fab, jours=120, change_a=None):
    out = {}
    for regle in ('AVANT', 'APRÈS'):
        n, faux, delais = [], [], []
        for g in GR:
            if regle == 'AVANT':
                rows, al = banc.avant(fab(), jours, g, T0)
            else:
                rows, al, _ = banc.apres(fab(), jours, g, T0)
            n.append(len(al))
            if change_a is None:
                faux.append(len(al))
            else:
                faux.append(sum(1 for a in al if a[0] < change_a))
                apres_ = [a[0] - change_a for a in al if a[0] >= change_a]
                if apres_:
                    delais.append(apres_[0])
        out[regle] = (statistics.mean(n), statistics.mean(faux),
                      statistics.mean(delais) if delais else None, len(delais))
    return out


def main():
    print('| Profil TENIR (120 j) | AVANT : alertes / fausses / délai de détection | APRÈS : alertes / fausses / délai |')
    print('|---|---|---|')
    cas = [
        ('régulier 5 ± 1,2', P.regulier, None),
        ('régulier 5 ± 2,0', lambda: P.regulier(sd=2.0), None),
        ('rafales puis creux', P.rafales, None),
        ('froid enthousiaste (8,8,8 puis 3)', lambda: P.froid(enthousiaste=3), None),
        ('baisse durable 5 → 3 au j50', lambda: P.change(5.0, 3.0, 50), 50),
        ('surchauffe 5 → 7 au j50', lambda: P.change(5.0, 7.0, 50), 50),
    ]
    for nom, fab, ca in cas:
        o = alertes(fab, change_a=ca)

        def f(t):
            d = '—' if t[2] is None else '%.0f j (%d/30)' % (t[2], t[3])
            return '%.1f / %.1f / %s' % (t[0], t[1], d)
        print('| %s | %s | %s |' % (nom, f(o['AVANT']), f(o['APRÈS'])))

    print('\n-- refuse tout (progresse) : jours des propositions de montée, graines 1-3')
    for g in (1, 2, 3):
        _, _, pr = banc.apres(P.progresse(), 120, g, rep='non')
        print('   graine %d :' % g, [(p['i'], p['dec']) for p in pr])
    print('-- oui à tout (régulier) : suite des paliers, graines 1-3')
    for g in (1, 2, 3):
        rows, _, pr = banc.apres(P.regulier(), 120, g, rep='oui')
        print('   graine %d :' % g, [(p['i'], p['dec'], p['N'], p['tenus']) for p in pr])
    print('-- au plafond K=6, oui à tout : propositions, graines 1-3')
    for g in (1, 2, 3):
        rows, _, pr = banc.apres(P.plafond(), 120, g, rep='oui')
        print('   graine %d :' % g, [(p['i'], p['dec'], p['N'], p['tenus']) for p in pr])

    print('\n-- week-end : objectif moyen des lundis, samedi jamais travaillé vs toujours travaillé (2 tâches)')
    for regle in ('AVANT', 'APRÈS'):
        a, b = [], []
        for g in GR:
            for p_sam, acc in ((0.0, a), (1.0, b)):
                fab = P.interrompu(conge=(0, 0), p_sam=p_sam, p_dim=0.0)
                if regle == 'AVANT':
                    rows, _ = banc.avant(fab, 120, g)
                else:
                    rows, _, _ = banc.apres(fab, 120, g)
                acc.append(statistics.mean(r['T'] for r in rows[20:]
                                           if (banc.START.toordinal() + r['i']) % 7 == 0 and r['T']))
        print('   %s : sans samedi %.2f, avec samedi %.2f, écart %+.2f' % (
            regle, statistics.mean(a), statistics.mean(b), statistics.mean(b) - statistics.mean(a)))

    print('\n-- congé déclaré de 10 j (j40-49) : graines où l\'objectif du 1er jour de retour (j50) < veille (j39)')
    for regle in ('AVANT', 'APRÈS'):
        baisse = 0
        for g in GR:
            if regle == 'AVANT':
                rows, _ = banc.avant(P.interrompu(), 120, g)
            else:
                rows, _, _ = banc.apres(P.interrompu(), 120, g)
            baisse += rows[50]['T'] < rows[39]['T']
        print('   %s : %d / 30' % (regle, baisse))
    print('-- retour d\'un congé de 4 semaines (j30-57), objectif affiché au retour : source')
    for regle in ('AVANT', 'APRÈS'):
        src = []
        for g in GR:
            if regle == 'AVANT':
                rows, _ = banc.avant(P.interrompu(conge=(30, 58)), 120, g)
                src.append('défaut' if rows[59]['T'] == 5 and rows[29]['T'] != 5 else 'calculé')
            else:
                rows, _, _ = banc.apres(P.interrompu(conge=(30, 58)), 120, g)
                src.append(rows[59]['src'] + ('=' if rows[59]['T'] == rows[29]['T'] else '≠'))
        print('   %s :' % regle, {s: src.count(s) for s in set(src)})

    print('\n-- alterne P(j0) -> T(j35) -> L(j70) -> P(j85), régulier : objectif médian aux jours 34/36/60/72/86/100')
    sch = ((0, 'pousser'), (35, 'tenir'), (70, 'libre'), (85, 'pousser'))
    for regle in ('AVANT', 'APRÈS'):
        lignes = []
        for g in GR:
            rows = banc.avant(P.regulier(), 120, g, sch)[0] if regle == 'AVANT' else \
                banc.apres(P.regulier(), 120, g, sch)[0]
            lignes.append(rows)
        print('   %s :' % regle, banc.trajectoire(lignes, (34, 36, 60, 72, 86, 100)))


if __name__ == '__main__':
    main()
