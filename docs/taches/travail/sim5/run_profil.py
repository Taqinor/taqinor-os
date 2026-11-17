"""Seuils du profil : taux de faux constats sur un utilisateur SANS effet réel, et puissance quand l'effet
existe. python run_profil.py. Données synthétiques (5 000 tirages par cas)."""
import random
import statistics

N_TIR = 5000


def creneau(n_par_creneau, ecart_min, p_matin, p_aprem, rng):
    """Constat « tu finis rarement ce que tu planifies l'après-midi » : écart de taux de plan tenu
    matin vs après-midi >= ecart_min, avec n_par_creneau lignes de plan dans chaque créneau."""
    a = sum(rng.random() < p_matin for _ in range(n_par_creneau)) / n_par_creneau
    b = sum(rng.random() < p_aprem for _ in range(n_par_creneau)) / n_par_creneau
    return (a - b) >= ecart_min


def jour_faible(n_par_jour, ecart_min, effet, rng, sd=1.2):
    """Constat « le <jour> est ton jour le plus léger » : moyenne d'un jour de semaine <= moyenne
    générale - ecart_min, n_par_jour jours évalués par jour de semaine (5 jours)."""
    jours = [[5 + (-effet if j == 4 else 0) + rng.gauss(0, sd) for _ in range(n_par_jour)] for j in range(5)]
    tout = statistics.mean(x for j in jours for x in j)
    return any(statistics.mean(j) <= tout - ecart_min for j in jours)


def main():
    rng = random.Random(7)
    print('Constat créneau (faux = aucun écart réel, taux 0,7/0,7 ; puissance = 0,8 matin / 0,5 après-midi)')
    for n in (10, 20, 30):
        for ec in (0.20, 0.25):
            faux = sum(creneau(n, ec, 0.7, 0.7, rng) for _ in range(N_TIR)) / N_TIR
            pui = sum(creneau(n, ec, 0.8, 0.5, rng) for _ in range(N_TIR)) / N_TIR
            print('   %2d lignes/créneau, écart >= %2.0f pts : faux %4.1f %%  puissance %4.1f %%' % (n, 100 * ec, 100 * faux, 100 * pui))
    faux = sum(creneau(15, 0.30, 0.7, 0.7, rng) for _ in range(N_TIR)) / N_TIR
    pui = sum(creneau(15, 0.30, 0.9, 0.5, rng) for _ in range(N_TIR)) / N_TIR
    print('Constat essentiel en tête (15 jours par groupe, écart >= 30 pts) : faux %.1f %%  puissance (0,9 vs 0,5) %.1f %%'
          % (100 * faux, 100 * pui))
    print('Constat jour faible (faux = aucun effet ; puissance = vendredi 2 tâches plus bas ; sd 1,2)')
    for n in (4, 6, 8):
        for ec in (1.0, 1.5):
            faux = sum(jour_faible(n, ec, 0.0, rng) for _ in range(N_TIR)) / N_TIR
            pui = sum(jour_faible(n, ec, 2.0, rng) for _ in range(N_TIR)) / N_TIR
            print('   %d jours/jour de semaine, écart >= %.1f : faux %4.1f %%  puissance %4.1f %%' % (n, ec, 100 * faux, 100 * pui))


if __name__ == '__main__':
    main()
