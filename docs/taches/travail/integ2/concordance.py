"""Script JETABLE : tout identifiant cité entre accents graves dans regles.md / textes.md existe-t-il dans
donnees.md / api.md (révision 2) ? Bibliothèque standard. Usage : python -I concordance.py <dossier reference>."""
import re
import sys
sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

ref = Path(sys.argv[1])
corpus = (ref / 'donnees.md').read_text(encoding='utf-8') + (ref / 'api.md').read_text(encoding='utf-8')
mots = set(re.findall(r'[^\W\d][\w]*', corpus))

# Noms définis ailleurs, cités volontairement (fichiers du dépôt, fonctions d'aide internes aux modules purs,
# variables de gabarit, notation) : chaque famille est nommée, rien n'est ignoré en silence.
HORS_REFERENCE = {
    'aides internes de saisie.py (§1.12)': {'masquer_guillemets', 'MOTIFS', 'candidats', 'filtrer_contexte', 'choisir',
        'conv_jour', 'conv_heure', 'conv_moment', 'conv_echeance', 'conv_duree', 'conv_recurrence', 'conv_rappel',
        'conv_priorite', 'conv_projet', 'conv_section', 'conv_etiquette', 'assembler', 'deriver_heure',
        'deriver_rappel', 'nettoyer_ligne', 'est_titre_groupe', 'projet_premiere_ligne', 'marquer_doublons',
        'dates_pures', 'contexte', 'cands', 'masque', 'choisis'},
    'aides du moteur (signatures de regles.md)': {'derive_pousser_journee', 'journee_type', 'repondre_premier',
        'est_ouvre', 'is_jour_ouvre', 'occurrence_du_', 'comptes10', 'minutes_9j', 'jours_28', 'etat', 'statuts',
        'compte', 'plan', 'app', 'ouvre', 'conge', 'choisis', 'faits', 'dit', 'nombre', 'sens', 'decision', 'reponse',
        'silence', 'comptes', 'jour', 'mode', 'jours', 'taches', 'activites', 'objectif', 'capacite', 'exclure',
        'inclure', 'pool', 'item', 'n_ouvres', 'reglage', 'J', 'R', 'x', 'type', 'cle', 'donnees', 'variante',
        'maintenant', 'prefs', 'fenetre', 'candidats', 'ignorees', 'journal', 'ordinal', 'regle', 'aujourdhui',
        'fait_le', 'usage', 'obj', 'projets', 'faites_14j', 'zone', 'int', 'str', 'bool', 'dict', 'list', 'float',
        'None', 'textes', 'texte', 'porte', 'ignorer', 'etiquettes', 'dates', 'delta', 'est_travaille', 'contenu',
        'date_lancement', 'projet_dict', 'inclure_notes', 'reglages', 'tache', 'version', 'compter_report'},
    'existants du dépôt (lus, cités)': {'records', 'activities', 'done', 'core', 'dsr', 'reporting', 'calendar',
        'build_ics', 'notify', 'badge', 'clearAppBadge', 'NOTIFICATIONS_TOUJOURS_IMMEDIATES', 'sweeps',
        'jours_ouvres_entre', 'calendar_utils', 'apps', 'taches', 'saisie', 'moteur', 'recurrence', 'classement',
        'sante', 'rythme', 'sollicitations', 'flux', 'confidentialite', 'receivers', 'py', 'md', 'mjs', 'json',
        'tests', 'test_prompt_copilote', 'MAJUSCULES_COACH', 'CONSIGNES_COACH', 'i18n', 'catalogs', 'fr', 'en', 'ar',
        'frontend', 'src', 'nav', 'section', 'taches_aujourdhui', 'taches_a_trier', 'taches_projets',
        'taches_agenda', 'label', 'k', 'coverage', 'test', 'keys', 'no', 'raw', 'key', 'docs', 'travail', 'integ2',
        'recalcul', 'verif23', 'recherche', 'design', 'existant', 'role', 'status', 'aria', 'live', 'envoyer',
        'true', 'false', 'null', 'verif', 'specs', 'spec', 'ecrans', 'securite', 'langage', 'visuel', 'reference',
        'travaux', 'fastapi_ia', 'requete', 'reponse', 'n', 'u', 'et', 'pk', 'id', 'reports', 'heure', 'heures',
        'ou', 'via', 'to', 'tqc_', 'tqf_', 'tqt_', 'toordinal', 'p1', 'p2', 'p3', 'NhMM', 'Nh', 'ignoree'},
    'variables et pseudo-code des règles, définis dans regles.md': {'ceil', 'max', 'min', 'regex', 'convertisseur',
        'i', 'places', 'pmax', 'ouverts_du_jour', 'travailles', 'taille', 'cible'},
    'exemples de jetons de saisie (§1.2-§1.5), motifs et touches': {'demainx', 'p12', 'every', 'deux_jour', '_',
        'aaaammjj', 'Maj', 'TACHES_'},
    'caractères et pseudo-code de la normalisation et des formules': {'æ', 'œ', 'ʼ', 'médiane'},
    'existants du dépôt cités (signaux, ICS, gardes)': {'avenant_de', 'crm_lead_id', 'installation', 'lead_id',
        'due_date', 'Canari', 'Cache', 'Control', 'DESCRIPTION', 'SUMMARY', 'calname', 'start_dt', 'end_dt',
        'forme_code', 'fonction_neuve'},
    'variables de gabarit de textes.md (§0)': {'proposees', 'n_autres', 'restes', 'projets', 'p60', 'pt', 'pl', 'ef',
        'ep', 'h', 'cap', 'N1', 'N_1', 'med', 'ref', 'm', 'moyenne', 'bas', 'haut', 'oa', 'je', 'e', 'prec', 'f28',
        'j28', 'besoin', 'reste', 'k', 'd', 'priorite_autre', 'autre', 'etape', 'b', 'q', 'a', 'na', 'nb', 'f', 'f1',
        'm1', 'm2', 'n1', 'n2', 'h1', 'h2', 'ratio', 'tenus', 'sur', 'B', 'T', 'debut', 'fin', 'HH', 'MM'},
}
admis = set().union(*HORS_REFERENCE.values())

restant = {}
for nom in ('regles.md', 'textes.md'):
    texte = re.sub(r'```.*?```', ' ', (ref / nom).read_text(encoding='utf-8'), flags=re.S).replace('\n', ' ')
    for tok in re.findall(r'`([^`]+)`', texte):
        sans_chaines = re.sub(r'"[^"]*"', ' ', tok)  # texte entre guillemets = message, pas un nom
        for atome in re.findall(r'[^\W\d][\w]*', sans_chaines):
            if atome in mots or atome in admis:
                continue
            restant.setdefault(atome, set()).add(f'{nom}: `{tok}`')

routes = set()
for nom in ('regles.md', 'textes.md'):
    texte = re.sub(r'```.*?```', ' ', (ref / nom).read_text(encoding='utf-8'), flags=re.S).replace('\n', ' ')
    for tok in re.findall(r'`([^`]*/[^`]*)`', texte):
        r = re.sub(r'\?.*$', '', tok.split(' ')[-1]).replace('/api/django/taches/', '')
        if r.startswith(('apps/', 'docs/', 'frontend/', 'core/', 'tests/', 'scripts/')) or r.endswith(('.py', '.md', '.mjs', '.json')):
            continue
        if r.strip('/') and r.strip('/') not in corpus and r not in corpus:
            routes.add(f'{nom}: `{tok}`')

# Noms RETIRÉS par la révision 2 de la référence : ne doivent apparaître entre accents graves que dans une phrase
# qui dit qu'ils sont retirés (sections « Ce que je n'ai pas repris », « Révision 2 », « Manques »).
RETIRES = ['cartes_coach', 'projet_commun', 'Preference.objectif_dit', 'mode:"complet"', 'rappel_le', 'heure_prevue',
           'saisie-rapide/apercu', 'a-venir/', 'ouvrir=', 'vue=supprimees', 'accepter_palier', 'Annulation',
           'Projet.est_confidentiel', '`demain`', 'decaler/annuler', 'TACHE_RAPPEL', 'taches_gerer']
retires = []
for nom in ('regles.md', 'textes.md'):
    corps = (ref / nom).read_text(encoding='utf-8')
    corps = corps.split("## Décisions de l'intégrateur")[0]
    for r_ in RETIRES:
        for m in re.finditer(re.escape(r_), corps):
            retires.append(f'{nom}: {r_} …{corps[max(0, m.start()-50):m.end()+30]!r}')
print('noms retirés encore cités hors des sections de suivi :', len(retires))
for x in retires:
    print(' ', x)
print('identifiants absents de donnees.md / api.md :', len(restant))
for a in sorted(restant):
    print(' ', a, '<-', '; '.join(sorted(restant[a]))[:160])
print('routes absentes :', len(routes))
for r in sorted(routes):
    print(' ', r)
