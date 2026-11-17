"""Tableau AVANT / APRÈS, 30 graines, 120 jours (python run_all.py). Données synthétiques."""
import statistics
import banc
import personas as P

POUSSER = ((0, 'pousser'),)
ALTERNE = ((0, 'pousser'), (35, 'tenir'), (70, 'libre'), (85, 'pousser'))

PROFILS = [
    ('1 régulier', P.regulier, POUSSER, 'raisonnable'),
    ('2 progresse si poussé', P.progresse, POUSSER, 'raisonnable'),
    ('3 rafales puis creux', P.rafales, POUSSER, 'raisonnable'),
    ('4 tricheur (découpe)', P.tricheur, POUSSER, 'oui'),
    ('5 interrompu (congé déclaré)', P.interrompu, POUSSER, 'raisonnable'),
    ('5b interrompu (congé non déclaré)', lambda: P.interrompu(declare=False), POUSSER, 'raisonnable'),
    ('6 effondrement puis reprise', P.effondrement, POUSSER, 'raisonnable'),
    ('7 démarrage à froid (vrai 3)', P.froid, POUSSER, 'raisonnable'),
    ('7b froid enthousiaste (8,8,8 puis 3)', lambda: P.froid(enthousiaste=3), POUSSER, 'raisonnable'),
    ('8 au plafond (K=6) en POUSSER', P.plafond, POUSSER, 'oui'),
    ('9 alterne P→T→L→P', P.regulier, ALTERNE, 'raisonnable'),
    ('10 refuse tout (progresse)', P.progresse, POUSSER, 'non'),
    ('11 oui à tout (régulier)', P.regulier, POUSSER, 'oui'),
    ('11b oui à tout (progresse)', P.progresse, POUSSER, 'oui'),
]


def f1(x):
    return '—' if x is None else ('%.1f' % x if isinstance(x, float) else str(x))


def main(profils=PROFILS, jours=120):
    print('| Profil | Règle | objectif j14/30/45/60/90/119 (médiane) | min–max | moy. | plus grand saut | '
          'changements | propositions ↑/↓ (acceptées) | fausses baisses | jours tenus | fait (20 derniers) |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    for nom, fab, sch, rep in profils:
        n, A, B, tA, tB = banc.comparer(nom, fab, jours, sch, rep)
        print('| %s | AVANT | %s | %s–%s | %s | %+d / %+d | %s | — | %s imposées | %s %% | %s |' % (
            nom, tA, f1(A['Tmin']), f1(A['Tmax']), f1(A['Tmoy']), A['up'], A['down'], f1(A['changements']),
            f1(A['imposees']), f1(A['tenus']), f1(A['fait_fin'])))
        print('| | APRÈS | %s | %s–%s | %s | %+d / %+d | %s | %s/%s (%s/%s)%s | %s | %s %% | %s |' % (
            tB, f1(B['Tmin']), f1(B['Tmax']), f1(B['Tmoy']), B['up'], B['down'], f1(B['changements']),
            f1(B['p_up']), f1(B['p_dn']), f1(B['acc_up']), f1(B['acc_dn']),
            (' + %s garde taille' % f1(B['taille'])) if B['taille'] else '', f1(B['fausses']),
            f1(B['tenus']), f1(B['fait_fin'])))


if __name__ == '__main__':
    main()
