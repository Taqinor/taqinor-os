"""Mesure le coût d'une session Claude Code (orchestrateur + sous-agents) depuis ses transcripts.

Usage :
    python .claude/skills/go-deep/outils/cout_session.py <dossier de transcripts> [<dossier> ...]

Un dossier de transcripts est celui de la session sous `~/.claude/projects/` (il contient
`<id de session>.jsonl` et `<id de session>/subagents/`). Lecture seule, aucun réseau.

Les prix sont ceux de l'API (par million de tokens), relevés dans la skill claude-api : à
remettre à jour quand elle change. L'abonnement ne publie pas sa pondération : le coût au
tarif API sert d'étalon pour comparer deux lots, pas de facture.
"""
import collections
import glob
import io
import json
import os
import statistics
import sys

# entrée, relecture du cache, écriture 5 min, écriture 1 h, sortie — relevé du 26/11/2026
PRIX = {
    'fable': (8.0, 0.20, 10.0, 16.0, 40.0),
    'opus': (4.0, 0.20, 5.0, 8.0, 20.0),
    'sonnet': (2.0, 0.10, 2.5, 4.0, 10.0),
    'haiku': (0.5, 0.05, 0.625, 1.0, 2.5),
}


def palier(modele):
    nom = (modele or '').lower()
    return next((p for p in PRIX if p in nom), None)


def lire(chemin):
    """Une ligne par requête (dédoublonnée par id de message) :
    (palier, entrée, relecture, écriture 5 min, écriture 1 h, sortie)."""
    vues = collections.OrderedDict()
    with io.open(chemin, encoding='utf-8', errors='replace') as fichier:
        for ligne in fichier:
            if '"usage"' not in ligne:
                continue
            try:
                d = json.loads(ligne)
            except ValueError:
                continue
            message = d.get('message') or {}
            usage = message.get('usage')
            if d.get('type') != 'assistant' or not usage:
                continue
            ecrit = usage.get('cache_creation') or {}
            e1h = ecrit.get('ephemeral_1h_input_tokens', 0) or 0
            e5m = ecrit.get('ephemeral_5m_input_tokens', 0) or 0
            if not e1h + e5m:
                e5m = usage.get('cache_creation_input_tokens', 0) or 0
            vues[message.get('id') or d.get('uuid')] = (
                palier(message.get('model')), usage.get('input_tokens', 0) or 0,
                usage.get('cache_read_input_tokens', 0) or 0, e5m, e1h,
                usage.get('output_tokens', 0) or 0)
    return list(vues.values())


def cout(requetes):
    """Coût au tarif API, ventilé : relecture, écriture, sortie, entrée."""
    c = collections.Counter()
    for p, entree, relu, e5m, e1h, sortie in requetes:
        if p is None:
            continue
        pe, pr, p5, p1, ps = PRIX[p]
        c['relecture'] += relu * pr / 1e6
        c['ecriture'] += (e5m * p5 + e1h * p1) / 1e6
        c['sortie'] += sortie * ps / 1e6
        c['entree'] += entree * pe / 1e6
    return c


def contexte(r):
    return r[1] + r[2] + r[3] + r[4]


def mesurer(dossier):
    for principal in sorted(glob.glob(os.path.join(dossier, '*.jsonl'))):
        session = os.path.basename(principal)[:-6]
        orchestrateur = lire(principal)
        motif = os.path.join(dossier, session, 'subagents', '**', '*.jsonl')
        agents = [a for a in (lire(f) for f in glob.glob(motif, recursive=True)) if a]
        c_orch = cout(orchestrateur)
        c_agents = collections.Counter()
        par_palier = collections.Counter()
        au_dessus = 0.0
        for a in agents:
            c_agents.update(cout(a))
            par_palier[a[0][0]] += sum(cout(a).values())
            au_dessus += sum(cout([r for r in a if contexte(r) > 200_000]).values())
        total = sum(c_orch.values()) + sum(c_agents.values())
        print('SESSION %s' % session)
        print('  total au tarif API : %.0f $ (orchestrateur %.0f $, %d agents %.0f $)' % (
            total, sum(c_orch.values()), len(agents), sum(c_agents.values())))
        tout = c_orch + c_agents
        if total:
            print('  parts : ' + ', '.join(
                '%s %.0f %%' % (k, 100 * v / total) for k, v in tout.most_common()))
        print('  agents par modèle : ' + ', '.join(
            '%s %.0f $' % (k, v) for k, v in par_palier.most_common()))
        if agents:
            pas = [len(a) for a in agents]
            depart = [contexte(a[0]) for a in agents]
            pic = [max(contexte(r) for r in a) for a in agents]
            print('  par agent (médiane) : %d pas, départ %dk, pic %dk ; pas au total %d' % (
                statistics.median(pas), statistics.median(depart) // 1000,
                statistics.median(pic) // 1000, sum(pas)))
            if sum(c_agents.values()):
                print('  part du coût des agents au-dessus de 200k de contexte : %.0f %%' % (
                    100 * au_dessus / sum(c_agents.values())))
        if orchestrateur:
            print('  orchestrateur : %d pas, contexte moyen %dk, pic %dk' % (
                len(orchestrateur), sum(map(contexte, orchestrateur)) // len(orchestrateur) // 1000,
                max(map(contexte, orchestrateur)) // 1000))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for chemin in sys.argv[1:]:
        mesurer(chemin)
