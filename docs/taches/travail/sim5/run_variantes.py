"""Itération sur les paramètres de POUSSER (python run_variantes.py). Données synthétiques, 30 graines, 120 j.
Tour 1 (archivé dans spec-5a-rythme.md §6) : borne p60 et seuil 7/10 étouffent la montée.
Tour 2 (ce fichier) : seuil 6/10 sans borne ; variantes de la garde de taille et de la baisse."""
import itertools
import banc
import regles as R
import personas as P

CLES = [
    ('régulier', P.regulier, 'raisonnable'),
    ('régulier oui', P.regulier, 'oui'),
    ('progresse', P.progresse, 'raisonnable'),
    ('progresse oui', P.progresse, 'oui'),
    ('progresse T>h', lambda: P.progresse_v(seuil=0.0), 'raisonnable'),
    ('rafales oui', P.rafales, 'oui'),
    ('effondrement', P.effondrement, 'raisonnable'),
    ('plafond oui', P.plafond, 'oui'),
    ('tricheur oui', P.tricheur, 'oui'),
]


def run(jours=120):
    grille = list(itertools.product((6, 7), (0.7, 0.8), (True, False)))
    for (sm, tmin, bm) in grille:
        R.SEUIL_MONTER, R.TAILLE_MIN, R.BAISSE_MOYENNE = sm, tmin, bm
        print('== monter>=%d/10 taille>=%.0f%% baisse_moyenne=%s' % (sm, 100 * tmin, bm))
        for nom, fab, rep in CLES:
            ms = []
            for g in banc.GRAINES:
                rows, al, pr = banc.apres(fab(), jours, g, rep=rep)
                ms.append(banc.mesures(rows, al, pr))
            a = banc.agreger(ms)
            print('   %s: fin %.1f max %d fait %.1f ↑%.1f ↓%.1f garde-taille %.1f fausses-baisses %.1f tenus %d%%' % (
                nom, a['Tfin'], a['Tmax'], a['fait_fin'], a['p_up'], a['p_dn'], a['taille'], a['fausses'],
                a['tenus']))


if __name__ == '__main__':
    run()
