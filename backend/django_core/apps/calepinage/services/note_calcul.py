"""CAL176 — la NOTE DE CALCUL du calepinage, hypothèses SOURCÉES.

Le constat
==========
La note de calcul existe, mais elle est AO-only et lit un contexte de dossier
d'appel d'offres GELÉ (``apps/ao/fabrique/rendus/note_calcul.py``, contexte
AOF111). Un calepinage hors AO — la villa, l'atelier, la ferme — n'en avait
aucune. Le technicien qui voulait justifier un chiffre n'avait qu'un écran.

La doctrine, reprise mot pour mot d'AOF134
===========================================
Dans le dossier réel du 27/07/2026, la note de calcul portait des bilans
SAISIS : la pièce la plus lue était la plus fausse (264 modules annoncés quand
la donnée en disait 314). Ce module ne SAISIT rien et ne DÉRIVE rien :

* il LIT ``Calepinage.resultat`` (la forme publiée du moteur, figée par
  ``contract_samples/calepinage_resultat.json``) et il MET EN PAGE ;
* une grandeur INDISPENSABLE absente fait ÉCHOUER le rendu (``NoteRefusee``)
  en la NOMMANT, au lieu d'être inventée ou laissée à zéro. Un blanc est un
  défaut visible ; un zéro silencieux est un mensonge ;
* chaque hypothèse paraît AVEC SA SOURCE (``pvgis`` / ``fiche`` / ``mesure`` /
  ``hypothese`` / ``saisie``). Une hypothèse sans source affichée est une
  hypothèse qu'on ne peut pas contester — et deux notes de deux dossiers
  peuvent alors diverger sans que personne ne sache pourquoi.

Étanchéité
==========
La note est une pièce TECHNIQUE : elle ne porte ni prix d'achat, ni coût de
revient, ni marge. Les clés de coût sont REFUSÉES À L'ENTRÉE plutôt que
filtrées à la sortie — une omission de filtre est silencieuse, un refus ne
l'est pas. Elle n'est pas non plus un devis client : le PDF de devis reste
rendu par le seul moteur premium (règle #4).

Provenance sur CHAQUE page
==========================
L'empreinte d'entrée et la version du moteur sont posées dans la boîte de marge
``@bottom-left`` du ``@page`` : elles paraissent donc sur TOUTES les pages, pas
seulement la première. Une page détachée d'une note reste rattachable à sa
conception.
"""
from __future__ import annotations

from html import escape

__all__ = [
    'CLES_INTERDITES', 'NoteRefusee', 'CLES_VERDICT', 'CLES_MARGES',
    'construire_note_calcul', 'verdict_de_preuve', 'html_de_note_calcul',
    'rendre_note_calcul',
]

#: Clés dont la seule PRÉSENCE dans la donnée d'entrée est un défaut
#: d'étanchéité (même esprit qu'AOF129, volontairement en dur : c'est une
#: règle, pas une donnée). L'appariement se fait sur des JETONS ENTIERS
#: (``_prix_achat_`` dans ``_prix_achat_total_``), jamais sur une
#: sous-chaîne — « marge » est un mot du MÉTIER GÉOMÉTRIQUE ici (``marges``,
#: ``marge_troncon_min`` : les jeux mesurés entre rangées et obstacles), et un
#: appariement par sous-chaîne refusait le régime de preuve du moteur
#: lui-même. Le défaut a été vu par les essais de CAL177, pas deviné.
CLES_INTERDITES = (
    'prix_achat', 'prix_vente', 'prix_unitaire', 'cout_revient',
    'cout_de_revient', 'marge_brute', 'marge_nette', 'marge_commerciale',
    'taux_marge', 'benefice', 'remise',
)

#: Clés interdites à l'IDENTIQUE — celles dont le nom nu est déjà un aveu.
CLES_INTERDITES_EXACTES = ('marge', 'prix', 'cout', 'coefficient')

#: Libellé lisible des sources publiées par le moteur.
LIBELLE_SOURCE = {
    'pvgis': 'PVGIS',
    'fiche': 'fiche produit',
    'mesure': 'mesure',
    'hypothese': 'hypothèse société',
    'saisie': 'saisie société',
    'trace': 'tracé',
}

#: Ce qu'une note ne peut pas ne pas dire. Chemin -> libellé de la grandeur.
GRANDEURS_INDISPENSABLES = (
    ('pose.total_modules', 'nombre de modules posés'),
    ('pose.kwc', 'puissance crête posée (kWc)'),
    ('production.base.source', "source de l'irradiance"),
    ('production.total.p50_kwh', 'production annuelle P50 (kWh)'),
)


# ── CAL177 — le RÉGIME DE PREUVE, reporté tel quel ─────────────────────────
#
# ``core/calepinage`` ne rend pas un simple verdict : il rend un RÉGIME DE
# PREUVE (méthode, méthode exacte ou non, optimalité, borne supérieure, marges
# mesurées, contrôles passés). Jusqu'ici il n'était consommé que par le studio
# AO (``VerdictBar.jsx``) — AUCUNE sortie imprimable ne le portait. Or un compte
# de modules SANS son régime n'est pas opposable : « 314 modules » ne dit pas
# s'ils sont prouvés optimaux ou simplement posés par une heuristique.
#
# LA RÈGLE EST L'ÉGALITÉ. Le verdict imprimé est RECOPIÉ du résultat, clé par
# clé, jamais recalculé à l'impression : c'est ce qui garantit qu'il est
# identique à celui que l'API des variantes affiche pour le MÊME résultat. Un
# écart entre l'écran et la pièce remise, c'est l'incident du 27/07/2026
# (264 modules annoncés, 314 dans la donnée) sous un autre nom.

#: Les clés du régime de preuve, dans l'ordre d'impression — celles que le
#: moteur publie (``preuve``) et que le comparateur de variantes republie à
#: plat : les deux graphies du MÊME régime.
CLES_VERDICT = ('methode', 'methode_exacte', 'optimal', 'total_retenu',
                'total_optimal', 'borne_superieure', 'libelle', 'pas_cm',
                'nb_optima')

#: Les marges MESURÉES. Discipline du null : une marge NON MESURÉE vaut
#: ``None`` — jamais ``0``, qui se lirait « au ras ».
CLES_MARGES = ('troncon_min_cm', 'bande_min_cm', 'rangee_critique',
               'obstacle_critique')


def verdict_de_preuve(resultat):
    """Le régime de preuve du résultat, RECOPIÉ — aucune grandeur recalculée.

    Deux graphies du même régime coexistent dans le dépôt, et les deux sont
    lues : le moteur publié le range sous ``preuve`` (``pose.json``), le
    comparateur de variantes le republie À PLAT (``methode``, ``optimal``,
    ``marges``…). Refuser l'une des deux aurait fait mentir la pièce devant un
    producteur réel. Le PLAT prime : c'est la forme que l'API des variantes
    affiche, donc celle dont l'égalité est exigée.

    Toutes les clés sont TOUJOURS présentes, à ``None`` quand la grandeur n'a
    pas été mesurée : une clé absente ne se lit pas, un ``0`` inventé se lit
    faux.
    """
    resultat = resultat if isinstance(resultat, dict) else {}
    preuve = resultat.get('preuve')
    preuve = preuve if isinstance(preuve, dict) else {}
    marges = resultat.get('marges')
    if not isinstance(marges, dict):
        marges = preuve.get('marges') \
            if isinstance(preuve.get('marges'), dict) else {}

    regime = {}
    for cle in CLES_VERDICT:
        valeur = resultat.get(cle)
        regime[cle] = preuve.get(cle) if valeur is None else valeur

    def plat(cle):
        valeur = resultat.get(cle)
        return preuve.get(cle) if valeur is None else valeur

    return {
        'regime': regime,
        'marges': {cle: marges.get(cle) for cle in CLES_MARGES},
        'marge_troncon_min': plat('marge_troncon_min'),
        'marge_bande_min': plat('marge_bande_min'),
        'controles': list(preuve.get('controles') or []),
        # Les hypothèses encore ouvertes : une cote À CONFIRMER qui ne
        # remonterait pas ici serait une hypothèse INVISIBLE dans une pièce
        # technique.
        'cotes_a_confirmer': list(resultat.get('cotes_a_confirmer') or []),
        'motifs_non_engageable': list(
            resultat.get('motifs_non_engageable') or []),
        'engageable': resultat.get('engageable'),
    }


class NoteRefusee(ValueError):
    """Le rendu refuse de sortir, et il NOMME la grandeur qui lui manque."""

    def __init__(self, message, *, champ=''):
        super().__init__(message)
        self.champ = champ


def _cle_interdite(cle):
    """Vrai si ``cle`` est une grandeur de coût — appariement par JETONS.

    ``marges`` et ``marge_troncon_min`` (les jeux GÉOMÉTRIQUES mesurés par le
    moteur) ne sont pas des grandeurs de coût et doivent passer ; ``marge``
    tout court, si.
    """
    normalisee = ''.join(c if c.isalnum() else '_' for c in str(cle).lower())
    if normalisee in CLES_INTERDITES_EXACTES:
        return True
    entoure = '_%s_' % normalisee.strip('_')
    return any('_%s_' % interdite in entoure for interdite in CLES_INTERDITES)


def _verifier_etancheite(donnees):
    """Refuse une entrée qui charrie une grandeur de coût de revient."""
    trouves = []

    def descendre(noeud, chemin):
        if isinstance(noeud, dict):
            for cle, valeur in noeud.items():
                complet = '.'.join(filter(None, [chemin, str(cle)]))
                if _cle_interdite(cle):
                    trouves.append(complet)
                descendre(valeur, complet)
        elif isinstance(noeud, (list, tuple)):
            for rang, valeur in enumerate(noeud):
                descendre(valeur, '%s[%d]' % (chemin, rang))

    descendre(donnees, '')
    if trouves:
        raise NoteRefusee(
            "Note de calcul (pièce technique) : la donnée porte des grandeurs "
            "de coût réservées au directeur — %s. Elles ne franchissent jamais "
            "la fabrique documentaire." % ', '.join(sorted(trouves)),
            champ=sorted(trouves)[0])


def _lire(source, chemin):
    """Lit ``a.b.c`` dans ``source``, ou ``None`` — sans jamais de défaut."""
    courant = source
    for cle in chemin.split('.'):
        if not isinstance(courant, dict) or cle not in courant:
            return None
        courant = courant[cle]
    return courant


def _exiger(source, chemin, libelle):
    """La grandeur, ou ``NoteRefusee`` qui la NOMME.

    Un ``.get(..., 0)`` transformerait une donnée manquante en bilan faux ET
    IMPRIMÉ. On préfère un rendu qui refuse de sortir.
    """
    valeur = _lire(source, chemin)
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        raise NoteRefusee(
            "Note de calcul : la grandeur « %s » (%s) est absente du résultat "
            "du moteur. Elle doit être CALCULÉE, jamais saisie dans la pièce : "
            "relancez le calcul avant de demander la note."
            % (libelle, chemin),
            champ=chemin)
    return valeur


def _source_lisible(code):
    """« PVGIS », « hypothèse société »… ou l'aveu que la source manque."""
    texte = (code or '').strip().lower()
    if not texte:
        # On n'invente pas une source : on dit qu'elle n'est pas renseignée.
        return 'source non renseignée'
    return LIBELLE_SOURCE.get(texte, str(code))


def construire_note_calcul(resultat, *, site=None, identite=None, styles=None):
    """``Calepinage.resultat`` -> la note, prête à mettre en page.

    ``site`` est le contexte géographique du calepinage
    (``selectors.contexte_geographique`` : ville, adresse, source du repère) —
    des données de SITE, jamais des grandeurs recalculées.

    CALX295 — ``identite`` (projet, client, date de production) et ``styles``
    (la marque de la société, ``gabarit_document.styles_de_societe``) sont
    IMPRIMÉS sur la page de garde ; absents, la garde les barre.
    """
    if not isinstance(resultat, dict) or not resultat:
        raise NoteRefusee(
            "Note de calcul : aucun résultat de moteur enregistré pour ce "
            "calepinage. Une note ne se rend pas à partir d'un calcul qui n'a "
            "pas eu lieu.", champ='resultat')
    _verifier_etancheite(resultat)

    for chemin, libelle in GRANDEURS_INDISPENSABLES:
        _exiger(resultat, chemin, libelle)

    site = site if isinstance(site, dict) else {}
    base = _lire(resultat, 'production.base') or {}
    total = _lire(resultat, 'production.total') or {}
    pose = _lire(resultat, 'pose') or {}
    electrique = _lire(resultat, 'electrique') or {}

    note = {
        'identite': dict(identite or {}),
        # CALX295 — la marque de la société, pour la page de garde.
        'styles': dict(styles or {}),
        'site': {
            'ville': site.get('ville'),
            'adresse': site.get('adresse'),
            # La source du REPÈRE (épingle posée / GPS du lead) — jamais une
            # coordonnée devinée : sans source, la clé vaut None.
            'source_repere': site.get('source'),
            'source_irradiance': _source_lisible(base.get('source')),
            'fenetre_annees': base.get('fenetre_annees'),
            'pertes_declarees_pct': base.get('loss_passee_pct'),
        },
        'pose': {
            'total_modules': pose.get('total_modules'),
            'kwc': pose.get('kwc'),
            'puissance_module_wc': pose.get('puissance_module_wc'),
            # Les pans sont RECOPIÉS : ce module ne somme ni ne convertit rien.
            'pans': list(pose.get('pans') or []),
        },
        'electrique': {
            'chainage': electrique.get('chainage') or {},
            'onduleurs': list(electrique.get('onduleurs') or []),
            'verdicts': list(electrique.get('verdicts') or []),
        },
        'pertes': [
            {
                'poste': perte.get('poste'),
                'libelle': perte.get('libelle') or perte.get('poste'),
                'pct': perte.get('pct'),
                'source': _source_lisible(perte.get('source')),
            }
            for perte in (resultat.get('pertes') or [])
            if isinstance(perte, dict)
        ],
        'production': {
            'p50_kwh': total.get('p50_kwh'),
            'p75_kwh': total.get('p75_kwh'),
            'p90_kwh': total.get('p90_kwh'),
            'performance_ratio': total.get('performance_ratio'),
            'specific_yield_kwh_kwc': total.get('specific_yield_kwh_kwc'),
            'par_pan': list(_lire(resultat, 'production.par_pan') or []),
        },
        # CAL177 — le régime de preuve, RECOPIÉ du résultat (jamais recalculé)
        # : c'est ce qui le rend égal à celui de l'API des variantes.
        'verdict': verdict_de_preuve(resultat),
        'avertissements': list(resultat.get('avertissements') or []),
        'provenance': {
            # Deux graphies coexistent dans le dépôt pour la MÊME empreinte
            # (`hash_entree` côté moteur publié, `entree_hash` côté comparateur
            # de variantes) : refuser l'une aurait fait échouer un producteur
            # réel.
            'hash_entree': (resultat.get('hash_entree')
                            or resultat.get('entree_hash') or ''),
            'version_moteur': resultat.get('version_moteur') or '',
            'calcule_le': resultat.get('calcule_le') or '',
            'simule': bool(resultat.get('simule')),
        },
    }
    return note


# ── Mise en page (HTML pur — aucun gabarit Django, donc testable partout) ───

def _nombre_fr(valeur, decimales=2, unite=''):
    """Un nombre à la française, ou « — » quand la grandeur est ABSENTE."""
    if valeur is None or isinstance(valeur, bool):
        return '—'
    try:
        texte = ('%.*f' % (decimales, float(valeur))).replace('.', ',')
    except (TypeError, ValueError):
        return escape(str(valeur))
    if not unite:
        return texte
    # Typographie française : pas d'espace devant le degré, une espace devant
    # les autres unités (y compris « % », insécable à l'impression).
    return texte + unite if unite == '°' else texte + ' ' + unite


def _ligne(libelle, valeur):
    return ('<tr><th>%s</th><td>%s</td></tr>'
            % (escape(str(libelle)), escape(str(valeur))))


def _pied_de_page(provenance):
    """La mention de provenance, posée dans la marge de CHAQUE page."""
    termes = []
    if provenance.get('hash_entree'):
        termes.append('entrée %s' % provenance['hash_entree'][:12])
    if provenance.get('version_moteur'):
        termes.append('moteur %s' % provenance['version_moteur'])
    if provenance.get('calcule_le'):
        termes.append('calculé le %s' % provenance['calcule_le'])
    return ' · '.join(termes)


#: Libellés d'impression du régime de preuve. La note NOMME les clés du
#: moteur ; elle ne les REFORMULE pas en affirmation (« conforme », « optimal »
#: rédigé à la main engagerait le soumissionnaire — c'est au métier, jamais au
#: document, de l'écrire).
LIBELLE_VERDICT = {
    'methode': 'Méthode de pose',
    'methode_exacte': 'Méthode exacte',
    'optimal': 'Optimum prouvé',
    'total_retenu': 'Modules retenus',
    'total_optimal': 'Modules à l\'optimum',
    'borne_superieure': 'Borne supérieure',
    'libelle': 'Régime',
    'pas_cm': 'Pas de recherche (cm)',
    'nb_optima': 'Nombre d\'optima',
}

LIBELLE_MARGE = {
    'troncon_min_cm': 'Marge minimale de tronçon (cm)',
    'bande_min_cm': 'Marge minimale de bande (cm)',
    'rangee_critique': 'Rangée critique',
    'obstacle_critique': 'Obstacle critique',
}


def _valeur_verdict(valeur):
    """Une valeur de régime, telle quelle. ``None`` = NON MESURÉ, pas zéro."""
    if valeur is None:
        return 'non mesuré'
    if isinstance(valeur, bool):
        return 'oui' if valeur else 'non'
    return str(valeur)


def _section_verdict(verdict):
    """CAL177 — la section « verdict de preuve », RECOPIÉE du résultat."""
    if not verdict:
        return ''
    lignes = [_ligne(LIBELLE_VERDICT[cle], _valeur_verdict(valeur))
              for cle, valeur in (verdict.get('regime') or {}).items()
              if cle in LIBELLE_VERDICT]
    lignes += [_ligne(LIBELLE_MARGE[cle], _valeur_verdict(valeur))
               for cle, valeur in (verdict.get('marges') or {}).items()
               if cle in LIBELLE_MARGE]
    if not lignes:
        return ''
    blocs = ['<h2>Verdict de preuve</h2>',
             '<p class="note">Régime REPORTÉ du résultat du moteur, clé par '
             'clé : il est identique à celui qu\'affiche la comparaison des '
             'variantes pour ce même résultat.</p>',
             '<table>%s</table>' % ''.join(lignes)]
    controles = verdict.get('controles') or []
    if controles:
        blocs.append('<p class="note">Contrôles passés : %s</p>'
                     % escape(', '.join(str(c) for c in controles)))
    for titre, entrees in (
            ('Cotes à confirmer', verdict.get('cotes_a_confirmer') or []),
            ("Motifs de non-engageabilité",
             verdict.get('motifs_non_engageable') or [])):
        if not entrees:
            continue
        blocs.append('<p><strong>%s</strong></p><ul>%s</ul>'
                     % (escape(titre),
                        ''.join('<li>%s</li>' % escape(str(e))
                                for e in entrees)))
    return ''.join(blocs)


#: CALX295 — le titre de la note sur sa page de garde.
TITRE_NOTE = 'Note de calcul'


def _garde_de_note(note):
    """CALX295 — la page de garde de la note (identité société et projet)."""
    from .documents.gabarit_document import page_de_garde_html

    identite = dict(note.get('identite') or {})
    identite.setdefault('titre_document', TITRE_NOTE)
    return page_de_garde_html(identite, note.get('site') or {},
                              note.get('provenance') or {},
                              note.get('styles') or {})


def html_de_note_calcul(note, *, garde=True):
    """La note en HTML autonome (aucune police distante).

    CALX295 — la note s'ouvre sur une page de GARDE (société, projet, client,
    date, empreinte) ; ``garde=False`` rend la note d'avant, et sert au
    contrôle « la note gagne exactement une page ». Aucune image n'est posée
    sans logo SAISI par la société (``TenantTheme``).
    """
    provenance = note['provenance']
    site, pose = note['site'], note['pose']
    production = note['production']

    lignes_site = [
        _ligne('Ville', site['ville'] or '—'),
        _ligne('Adresse', site['adresse'] or '—'),
        _ligne("Source de l'irradiance", site['source_irradiance']),
    ]
    if site['fenetre_annees']:
        lignes_site.append(_ligne('Fenêtre de données', site['fenetre_annees']))
    if site['source_repere']:
        lignes_site.append(_ligne('Source du repère', site['source_repere']))

    lignes_pans = ''.join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (escape(str(pan.get('pan') or '')),
           _nombre_fr(pan.get('modules'), 0),
           _nombre_fr(pan.get('kwc'), 2, 'kWc'),
           _nombre_fr(pan.get('azimut_deg'), 0, '°'),
           _nombre_fr(pan.get('inclinaison_deg'), 0, '°'))
        for pan in pose['pans'])

    chainage = note['electrique']['chainage']
    lignes_onduleurs = ''.join(
        '<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (escape(str(onduleur.get('reference') or '')),
           _nombre_fr(onduleur.get('taille_kw'), 1, 'kW'),
           _nombre_fr(onduleur.get('nombre'), 0),
           _nombre_fr(onduleur.get('ratio_dc_ac'), 3))
        for onduleur in note['electrique']['onduleurs'])

    lignes_pertes = ''.join(
        '<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (escape(str(perte['libelle'] or '')),
           _nombre_fr(perte['pct'], 1, '%'),
           escape(str(perte['source'])))
        for perte in note['pertes'])

    avertissements = ''.join(
        '<li>%s</li>' % escape(str(texte)) for texte in note['avertissements'])
    verdict = _section_verdict(note.get('verdict') or {})

    return (
        '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
        '<title>Note de calcul</title><style>'
        '@page{size:A4;margin:16mm 14mm 18mm 14mm;'
        '@bottom-left{content:"%(pied)s";font-size:7pt;color:#555;}'
        '@bottom-right{content:"page " counter(page) "/" counter(pages);'
        'font-size:7pt;color:#555;}}'
        'body{font-family:"DejaVu Sans",Arial,sans-serif;font-size:9pt;'
        'color:#111;}'
        'h1{font-size:15pt;margin:0 0 2mm 0;}'
        'h2{font-size:11pt;margin:6mm 0 2mm 0;border-bottom:0.4mm solid #111;}'
        'table{width:100%%;border-collapse:collapse;margin-bottom:2mm;}'
        'th,td{border:0.2mm solid #999;padding:1.2mm;text-align:left;'
        'vertical-align:top;}'
        'th{background:#f2f2f2;font-weight:bold;}'
        '.note{color:#555;font-size:8pt;}'
        '</style></head><body>'
        '%(garde)s'
        '<h1>Note de calcul — calepinage</h1>'
        '<p class="note">%(mention_simulee)s</p>'
        '<h2>Site et irradiance</h2><table>%(site)s</table>'
        '<h2>Pose retenue</h2><table>%(totaux)s</table>'
        '<table><tr><th>Pan</th><th>Modules</th><th>Puissance</th>'
        '<th>Azimut</th><th>Inclinaison</th></tr>%(pans)s</table>'
        '<h2>Chaînes et onduleurs</h2><table>%(chainage)s</table>'
        '<table><tr><th>Onduleur</th><th>Calibre</th><th>Nombre</th>'
        '<th>Ratio DC/AC</th></tr>%(onduleurs)s</table>'
        '<h2>Pertes déclarées</h2>'
        '<table><tr><th>Poste</th><th>Part</th><th>Source</th></tr>'
        '%(pertes)s</table>'
        '<h2>Production attendue</h2><table>%(production)s</table>'
        '%(verdict)s'
        '%(avertissements)s'
        '</body></html>'
    ) % {
        'garde': _garde_de_note(note) if garde else '',
        'pied': escape(_pied_de_page(provenance), quote=True).replace('"', ''),
        'mention_simulee': escape(
            'Grandeurs LUES du résultat du moteur — aucune n\'est saisie dans '
            'cette pièce. Chaque hypothèse paraît avec sa source.'),
        'site': ''.join(lignes_site),
        'totaux': ''.join([
            _ligne('Modules posés', _nombre_fr(pose['total_modules'], 0)),
            _ligne('Puissance crête', _nombre_fr(pose['kwc'], 2, 'kWc')),
            _ligne('Puissance unitaire du module',
                   _nombre_fr(pose['puissance_module_wc'], 0, 'Wc')),
        ]),
        'pans': lignes_pans,
        'chainage': ''.join([
            _ligne('Modules par chaîne',
                   _nombre_fr(chainage.get('modules_par_chaine'), 0)),
            _ligne('Nombre de chaînes',
                   _nombre_fr(chainage.get('chaines'), 0)),
            _ligne('Modules hors chaîne', _nombre_fr(chainage.get('reste'), 0)),
        ]),
        'onduleurs': lignes_onduleurs,
        'pertes': lignes_pertes,
        'production': ''.join([
            _ligne('Production annuelle P50',
                   _nombre_fr(production['p50_kwh'], 0, 'kWh')),
            _ligne('Production annuelle P75',
                   _nombre_fr(production['p75_kwh'], 0, 'kWh')),
            _ligne('Production annuelle P90',
                   _nombre_fr(production['p90_kwh'], 0, 'kWh')),
            _ligne('Ratio de performance',
                   _nombre_fr(production['performance_ratio'], 3)),
            _ligne('Productible spécifique',
                   _nombre_fr(production['specific_yield_kwh_kwc'], 1,
                              'kWh/kWc')),
        ]),
        'verdict': verdict,
        'avertissements': ('<h2>Avertissements du moteur</h2><ul>%s</ul>'
                           % avertissements) if avertissements else '',
    }


def rendre_note_calcul(calepinage, *, company=None, site=None, identite=None,
                       styles=None):
    """Octets PDF de la note, via ``core.pdf.render_pdf`` (ARC11).

    JAMAIS un import direct de WeasyPrint (``check_platform.py`` refuserait le
    fichier, et la plomberie PDF n'a pas à être re-codée par pièce). Le site
    est LU par ``selectors.contexte_geographique`` quand l'appelant ne le
    fournit pas — jamais reconstruit ici.

    CALX295 — l'identité (projet, client, date) et la marque de la société
    sont LUES quand l'appelant ne les fournit pas : la note sort avec sa
    page de garde.
    """
    from core.pdf import render_pdf

    from .documents.gabarit_document import (
        identite_du_calepinage, styles_de_societe,
    )

    company = company or getattr(calepinage, 'company', None)
    if site is None:
        from .. import selectors

        site = selectors.contexte_geographique(calepinage)
    if identite is None:
        identite = identite_du_calepinage(calepinage,
                                          titre_document=TITRE_NOTE)
    if styles is None:
        styles = styles_de_societe(company)
    note = construire_note_calcul(getattr(calepinage, 'resultat', None),
                                  site=site, identite=identite, styles=styles)
    return render_pdf(html=html_de_note_calcul(note), company=company)
