#!/usr/bin/env python3
"""VEIL21 — Tri IA HORS LIGNE des fiches de veille par la session Claude de Reda.

D-VEIL-8 : pendant le pilote, le tri passe par l'abonnement Claude (CLI
``claude -p``), jetons COMPTÉS ; aucune clé API dans l'ERP. Python standard
seulement.

    python tools/veille_tri/trier.py fiches.jsonl verdicts.jsonl
    python tools/veille_tri/trier.py fiches.jsonl verdicts.jsonl --a-blanc

1. Lit le JSONL exporté par ``manage.py veille_exporter_fiches``.
2. Premier passage par lots : ``claude -p --model <tri> --output-format json``
   (défaut ``haiku``), consigne versionnée
   ``backend/django_core/apps/adsengine/data/veille_consigne/v1.md``.
3. Second passage (défaut ``sonnet`` ; options CLI supplémentaires, p. ex.
   un effort bas, par ``--options-ambigu``) sur les verdicts de confiance <
   ``--seuil`` ou marqués dropshipper ``oui``.
4. Écrit un JSONL ``{page_id, classe, confiance, dropshipper, indices,
   motif_fr, modele, jetons_entree, jetons_sortie}`` à relire par
   ``manage.py veille_importer_verdicts``.

Les jetons viennent du champ ``usage`` de la sortie JSON de la CLI (entrée =
``input_tokens`` + jetons de cache ; sortie = ``output_tokens``), répartis à
parts égales entre les fiches d'un lot. ``total_cost_usd`` n'est JAMAIS lu.
``--a-blanc`` : aucun appel, verdicts ``incertain`` à 0 jeton (essai de la
chaîne).
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
CONSIGNE = (RACINE / 'backend' / 'django_core' / 'apps' / 'adsengine' / 'data'
            / 'veille_consigne' / 'v1.md')
CLASSES = ('vendeur', 'place_de_marche', 'hors_sujet', 'pas_vendeur',
           'doublon', 'incertain')
TAILLE_LOT = 20


def lire_fiches(chemin):
    fiches = []
    with open(chemin, encoding='utf-8') as fichier:
        for brut in fichier:
            if brut.strip():
                fiches.append(json.loads(brut))
    return fiches


def lots(liste, taille):
    for i in range(0, len(liste), taille):
        yield liste[i:i + taille]


def jetons_de(usage):
    usage = usage or {}
    entree = sum(int(usage.get(k) or 0) for k in (
        'input_tokens', 'cache_creation_input_tokens',
        'cache_read_input_tokens'))
    return entree, int(usage.get('output_tokens') or 0)


def repartir(total, n):
    """Répartit ``total`` jetons sur ``n`` fiches (somme exacte)."""
    if n <= 0:
        return []
    base, reste = divmod(total, n)
    return [base + (1 if i < reste else 0) for i in range(n)]


def _extraire_json(texte):
    texte = (texte or '').strip()
    if texte.startswith('```'):
        texte = texte.strip('`')
        texte = texte[texte.find('['):]
    debut, fin = texte.find('['), texte.rfind(']')
    if debut < 0 or fin < debut:
        raise ValueError('réponse sans liste JSON')
    return json.loads(texte[debut:fin + 1])


def appeler_claude(modele, prompt, options=(), executer=subprocess.run):
    """UN appel ``claude -p`` ; renvoie ``(verdicts, jetons_entree,
    jetons_sortie, modele_effectif)``."""
    commande = ['claude', '-p', '--model', modele, '--output-format', 'json',
                *options]
    resultat = executer(commande, input=prompt, capture_output=True,
                        text=True, encoding='utf-8', check=True)
    sortie = json.loads(resultat.stdout)
    entree, sortie_jetons = jetons_de(sortie.get('usage'))
    modeles = list((sortie.get('modelUsage') or {}).keys())
    return (_extraire_json(sortie.get('result')), entree, sortie_jetons,
            modeles[0] if len(modeles) == 1 else modele)


def construire_prompt(consigne, fiches):
    return (consigne + '\n\n## Fiches\n\n'
            + json.dumps(fiches, ensure_ascii=False, indent=1))


def normaliser_verdict(brut, page_id, modele, entree, sortie):
    classe = brut.get('classe') if brut.get('classe') in CLASSES \
        else 'incertain'
    dropshipper = brut.get('dropshipper') \
        if brut.get('dropshipper') in ('oui', 'non', 'incertain') \
        else 'incertain'
    try:
        confiance = max(0.0, min(1.0, float(brut.get('confiance'))))
    except (TypeError, ValueError):
        confiance = 0.0
    return {
        'page_id': page_id, 'classe': classe, 'confiance': confiance,
        'dropshipper': dropshipper,
        'indices': [i for i in (brut.get('indices') or [])
                    if isinstance(i, dict)],
        'motif_fr': str(brut.get('motif_fr') or '')[:500],
        'modele': modele, 'jetons_entree': entree, 'jetons_sortie': sortie,
    }


def trier_lot(fiches, modele, consigne, options=(), executer=subprocess.run):
    verdicts, entree, sortie, effectif = appeler_claude(
        modele, construire_prompt(consigne, fiches), options, executer)
    par_page = {str(v.get('page_id')): v for v in verdicts
                if isinstance(v, dict)}
    parts_e = repartir(entree, len(fiches))
    parts_s = repartir(sortie, len(fiches))
    return [normaliser_verdict(par_page.get(str(f['page_id']), {}),
                               str(f['page_id']), effectif, parts_e[i],
                               parts_s[i])
            for i, f in enumerate(fiches)]


def trier(fiches, *, modele_tri='haiku', modele_ambigu='sonnet', seuil=0.7,
          taille_lot=TAILLE_LOT, options_ambigu=(), a_blanc=False,
          executer=subprocess.run):
    if a_blanc:
        return [normaliser_verdict({}, str(f['page_id']), 'a-blanc', 0, 0)
                for f in fiches]
    consigne = CONSIGNE.read_text(encoding='utf-8')
    resultats = {}
    for lot in lots(fiches, taille_lot):
        for verdict in trier_lot(lot, modele_tri, consigne, (), executer):
            resultats[verdict['page_id']] = verdict
    ambigus = [f for f in fiches
               if resultats[str(f['page_id'])]['confiance'] < seuil
               or resultats[str(f['page_id'])]['dropshipper'] == 'oui']
    for lot in lots(ambigus, taille_lot):
        for verdict in trier_lot(lot, modele_ambigu, consigne,
                                 tuple(options_ambigu), executer):
            premier = resultats[verdict['page_id']]
            # les jetons des deux passages sont cumulés sur le verdict final
            verdict['jetons_entree'] += premier['jetons_entree']
            verdict['jetons_sortie'] += premier['jetons_sortie']
            resultats[verdict['page_id']] = verdict
    return [resultats[str(f['page_id'])] for f in fiches]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('fiches')
    parser.add_argument('sortie')
    parser.add_argument('--modele-tri', default='haiku')
    parser.add_argument('--modele-ambigu', default='sonnet')
    parser.add_argument('--seuil', type=float, default=0.7)
    parser.add_argument('--taille-lot', type=int, default=TAILLE_LOT)
    parser.add_argument('--options-ambigu', default='',
                        help='Options CLI ajoutées au second passage.')
    parser.add_argument('--a-blanc', action='store_true',
                        help='Aucun appel : verdicts incertains à 0 jeton.')
    args = parser.parse_args(argv)
    fiches = lire_fiches(args.fiches)
    verdicts = trier(
        fiches, modele_tri=args.modele_tri, modele_ambigu=args.modele_ambigu,
        seuil=args.seuil, taille_lot=args.taille_lot,
        options_ambigu=shlex.split(args.options_ambigu),
        a_blanc=args.a_blanc)
    with open(args.sortie, 'w', encoding='utf-8') as fichier:
        for verdict in verdicts:
            fichier.write(json.dumps(verdict, ensure_ascii=False) + '\n')
    total_e = sum(v['jetons_entree'] for v in verdicts)
    total_s = sum(v['jetons_sortie'] for v in verdicts)
    print(f'{len(verdicts)} verdict(s) ; jetons entrée {total_e}, '
          f'sortie {total_s}.', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
