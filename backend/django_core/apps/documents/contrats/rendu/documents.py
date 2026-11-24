"""Les quatre actes : un ``contenu`` → une page HTML complète.

L'ordre suit ce qui se lit le mieux (docs/contrats/conception.md) : l'essentiel
d'abord (quoi, combien, quand), le détail ensuite, les clauses de risque à la
fin, la signature en dernier.
"""
from . import composants as c
from . import style

TYPES = tuple(t for t, _, _ in c.PARCOURS)


def _page(contenu, corps, *, paraphes=True, classe=''):
    titre_doc = c.esc(contenu.get('titre') or 'Acte')
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        f'<title>{titre_doc} — {c.esc(contenu.get("reference"))}</title>'
        f'<style>{style.css()}</style></head><body class="{classe}">'
        f'{c.pied(contenu, paraphes=paraphes)}'
        f'{c.bandeau(contenu)}{c.parcours(contenu["type"])}'
        f'<div class="corps">{corps}</div></body></html>')


def _resume_systeme(systeme):
    kwc = systeme.get('puissance_kwc')
    valeur = (f'{c.nombre(kwc, 2).rstrip("0").rstrip(",")}{c.INSECABLE}kWc'
              if kwc else 'Installation solaire')
    return valeur, c.esc(systeme.get('resume') or '')


def _garantie_la_plus_longue(garanties):
    mois = max([int(g.get('duree_mois') or 0) for g in garanties or []] or [0])
    return c.duree_mois(mois)


def _conditions_particulieres(contenu):
    texte = (contenu.get('conditions_particulieres') or '').strip()
    if not texte:
        return ''
    return (c.h2('Conditions particulières',
                 'Ce qui a été convenu en plus pour votre chantier ; ces '
                 'lignes priment sur les conditions générales ci-dessus.')
            + c.encadre('Convenu entre nous',
                        c.paragraphes([texte]), 'net'))


def _conclusion(contenu):
    """Le conseiller et le lieu de conclusion (mentions de l'article 48 de la
    loi n° 31-08 pour un contrat signé au domicile du client)."""
    conclusion = contenu.get('conclusion') or {}
    morceaux = []
    if conclusion.get('conseiller'):
        morceaux.append(f'Votre conseiller : <b>{c.esc(conclusion["conseiller"])}</b>')
    if conclusion.get('lieu'):
        morceaux.append(f'Contrat conclu à : <b>{c.esc(conclusion["lieu"])}</b>')
    if not morceaux:
        return ''
    return f'<p class="conclusion">{" · ".join(morceaux)}</p>'


def _annexe_retractation(contenu):
    """Annexe du contrat signé à domicile : le droit de rétractation, le texte
    des articles 47 à 50 et le formulaire détachable."""
    retractation = contenu.get('retractation') or {}
    if not retractation.get('actif'):
        return ''
    societe = contenu.get('societe') or {}
    client = contenu.get('client') or {}
    nom = c.esc(societe.get('nom_court') or societe.get('nom'))
    lois = ''.join(
        f'<div class="loi"><b>{c.esc(titre)}</b>'
        + ''.join(f'<p>{c.esc(ligne)}</p>' for ligne in texte.split('\n'))
        + '</div>'
        for titre, texte in retractation.get('articles') or [])
    trou = '<span class="trou">&nbsp;</span>'
    bordereau = (
        '<div class="bordereau"><div class="ciseaux">✂ Formulaire détachable'
        ' — à renvoyer seulement si vous renoncez au contrat</div>'
        '<h3>Rétractation</h3>'
        f'<p>À l\'attention de <b>{c.esc(societe.get("nom"))}</b>, '
        f'{c.esc(societe.get("adresse"))}.</p>'
        f'<p>Je soussigné(e) <b>{c.esc(client.get("nom_complet"))}</b>, '
        f'demeurant {c.esc(client.get("adresse")) or trou}, déclare me '
        f'rétracter du contrat <b>{c.esc(contenu.get("reference"))}</b> '
        f'signé le {c.esc(c.date_longue(contenu.get("date_document"))) or trou}'
        f', portant sur une installation solaire photovoltaïque.</p>'
        f'<div class="bas"><div>Fait à {trou}<br>le {trou}</div>'
        f'<div>Signature du client :</div></div></div>')
    return (
        '<div class="suite"></div><div class="annexe">'
        + c.h2('Annexe — Votre droit de rétractation',
               f'Vous avez signé ce contrat chez vous : la loi vous laisse '
               f'<b>sept jours</b> pour changer d\'avis, sans motif et sans '
               f'frais. Pendant ces sept jours, {nom} ne vous demande aucun '
               f'paiement et ne commence aucun travail. Pour renoncer, '
               f'remplissez ce formulaire et faites-le parvenir à {nom} par '
               f'un moyen qui prouve sa réception : lettre recommandée, '
               f'remise contre signature ou message écrit dont vous gardez '
               f'la trace.')
        + bordereau
        + c.h2('Loi n° 31-08, articles 47 à 50')
        + lois + '</div>')


# ── Acte 1 — Contrat d'installation ─────────────────────────────────────────

def contrat_installation(contenu):
    societe = contenu.get('societe') or {}
    systeme = contenu.get('systeme') or {}
    prix = contenu.get('prix') or {}
    delais = contenu.get('delais') or {}
    garanties = contenu.get('garanties') or []
    echeancier = contenu.get('echeancier') or []
    nom = c.esc(societe.get('nom_court') or societe.get('nom'))
    valeur_sys, detail_sys = _resume_systeme(systeme)

    detail_prix = 'toutes taxes comprises'
    if prix.get('total_ht') and prix.get('tva'):
        detail_prix = (f'TTC · soit {c.esc(c.montant(prix["total_ht"]))} hors '
                       f'taxes et {c.esc(c.montant(prix["tva"]))} de TVA')
    plus_longue = _garantie_la_plus_longue(garanties)
    apercu_garanties = ' · '.join(
        f'{c.esc(g.get("designation"))} <b>'
        f'{c.esc(g.get("duree_libelle") or c.duree_mois(g.get("duree_mois")))}'
        f'</b>' for g in garanties[:5])

    corps = c.titre(
        'contrat_installation', contenu.get('titre') or
        "Contrat d'installation photovoltaïque",
        f'Ce contrat fixe ce que {nom} installe chez vous, à quel prix, en '
        f'combien de paiements, dans quels délais et avec quelles garanties. '
        f"<b>L'essentiel tient sur cette page</b> ; le détail suit.",
        contenu.get('reference'))
    corps += c.h2("L'essentiel")
    corps += c.cartes(
        c.carte('Votre installation', valeur_sys, detail_sys),
        c.carte('Prix convenu', c.esc(c.montant(prix.get('total_ttc'))),
                detail_prix, forte=True),
        c.carte('Terminé au plus tard le',
                c.esc(c.date_longue(delais.get('date_limite'))
                      or delais.get('resume') or 'À préciser'),
                c.esc(delais.get('detail') or '')),
        c.carte('Vos garanties',
                (f"Jusqu'à {c.esc(plus_longue)}" if plus_longue
                 else 'Garanties fabricant'),
                apercu_garanties),
    )
    corps += c.h2(
        f'Votre paiement en {len(echeancier)} étape'
        f'{"s" if len(echeancier) > 1 else ""}',
        'Chaque étape correspond à un moment précis du chantier : vous ne '
        'payez jamais en avance sur ce qui a été fait.')
    corps += c.frise(echeancier)
    if contenu.get('paiement', {}).get('modalites'):
        corps += f'<p class="petit">{c.esc(contenu["paiement"]["modalites"])}</p>'

    corps += c.h2('Entre les soussignés')
    corps += c.parties(contenu)
    corps += _conclusion(contenu)

    corps += c.h2('Ce que nous installons',
                  f'Le matériel et les prestations sont ceux du devis '
                  f'{c.esc((contenu.get("chantier") or {}).get("devis_reference"))}'
                  f', que vous avez accepté et qui fait partie du contrat.')
    corps += c.tableau_materiel(systeme.get('lignes'))

    corps += c.h2('Vos garanties',
                  'Elles commencent le jour de la réception des travaux.')
    corps += c.tableau_garanties(garanties)

    corps += c.h2('Les conditions du contrat')
    corps += c.articles(contenu.get('articles'))
    corps += _conditions_particulieres(contenu)
    corps += c.signatures(
        contenu,
        mention_client='Signature précédée de la mention manuscrite '
                       '« Lu et approuvé, bon pour accord »')
    corps += _annexe_retractation(contenu)
    return _page(contenu, corps)


# ── Acte 2 — Procès-verbal de livraison du matériel ─────────────────────────

def _encadre_paiement_livraison(contenu):
    paiement = contenu.get('paiement') or {}
    regle = paiement.get('total_regle')
    if contenu.get('variante') == 'tranche_reglee':
        part = c.pourcent(paiement.get('pourcentage_regle'))
        quoi = (f'<b>{c.esc(part)}</b> du prix' if part
                else 'les sommes dues à ce jour')
        texte = (
            f'<div class="grand">{c.esc(c.montant(regle))}</div>'
            f"<p>Vous avez réglé {quoi} : rien n'est à payer à la "
            f'livraison.</p>')
        reste = paiement.get('reste_a_regler')
        if reste not in (None, '', 0, '0', '0.00'):
            texte += (f'<p>Il restera <b>{c.esc(c.montant(reste))}</b>, à '
                      f'régler à la réception des travaux.</p>')
        return c.encadre('Réglé à ce jour', texte, 'ok')
    du = paiement.get('exigible_maintenant')
    texte = f'<div class="grand">{c.esc(c.montant(du))}</div>'
    if paiement.get('exigible_en_lettres'):
        texte += f'<p class="lettres">{c.esc(paiement["exigible_en_lettres"])}</p>'
    lignes = []
    if regle not in (None, ''):
        lignes.append(f'Déjà réglé : <b>{c.esc(c.montant(regle))}</b>')
    if paiement.get('restera_ensuite') not in (None, ''):
        lignes.append(f'Restera à régler à la réception des travaux : '
                      f'<b>{c.esc(c.montant(paiement["restera_ensuite"]))}</b>')
    if lignes:
        texte += '<p>' + ' · '.join(lignes) + '</p>'
    if paiement.get('modalites'):
        texte += f'<p class="petit">{c.esc(paiement["modalites"])}</p>'
    return c.encadre('À régler à la livraison', texte)


def pv_livraison(contenu):
    societe = contenu.get('societe') or {}
    chantier = contenu.get('chantier') or {}
    systeme = contenu.get('systeme') or {}
    livraison = contenu.get('livraison') or {}
    nom = c.esc(societe.get('nom_court') or societe.get('nom'))

    corps = c.titre(
        'pv_livraison', contenu.get('titre') or
        'Procès-verbal de livraison du matériel',
        'Le matériel de votre installation est arrivé chez vous. Ce document '
        'constate ce qui a été livré, dans quel état, et fait le point sur '
        'votre paiement à cette étape.', contenu.get('reference'))
    corps += c.cartes(
        c.carte('Livré le',
                c.esc(c.date_longue(livraison.get('date')) or 'Date à porter'),
                c.esc(chantier.get('adresse') or '')),
        c.carte('Étape suivante', c.esc(livraison.get('suite') or 'La pose'),
                c.esc(livraison.get('suite_detail') or '')),
    )
    corps += c.h2('Le matériel livré',
                  f'Conformément au devis '
                  f'{c.esc(chantier.get("devis_reference"))}.')
    corps += c.tableau_materiel(systeme.get('lignes'), avec_series=bool(
        livraison.get('avec_series')))

    corps += c.h2('Vos constatations')
    corps += c.cases(contenu.get('constats'))
    corps += c.encadre(
        'Réserves éventuelles',
        '<p class="petit">Colis abîmé, pièce manquante, référence '
        'différente : notez-le ici, nous le corrigeons avant la pose.</p>'
        + (c.paragraphes(contenu.get('reserves'))
           if contenu.get('reserves') else c.lignes_a_ecrire(2)), 'net')

    corps += c.h2('Votre paiement à cette étape')
    corps += c.frise(contenu.get('echeancier'), avec_etats=True)
    corps += _encadre_paiement_livraison(contenu)

    corps += c.h2(f'Ce que {nom} et vous convenez')
    corps += c.articles(contenu.get('articles'))
    corps += _conditions_particulieres(contenu)
    corps += c.signatures(
        contenu,
        mention_client='Signature précédée de la mention manuscrite '
                       '« Reçu le matériel ci-dessus »')
    return _page(contenu, corps, classe='proces')


# ── Acte 3 — Procès-verbal de réception des travaux ─────────────────────────

def pv_reception(contenu):
    societe = contenu.get('societe') or {}
    chantier = contenu.get('chantier') or {}
    systeme = contenu.get('systeme') or {}
    reception = contenu.get('reception') or {}
    paiement = contenu.get('paiement') or {}
    nom = c.esc(societe.get('nom_court') or societe.get('nom'))
    valeur_sys, detail_sys = _resume_systeme(systeme)

    corps = c.titre(
        'pv_reception', contenu.get('titre') or
        'Procès-verbal de réception des travaux',
        f'Les travaux sont terminés et votre installation fonctionne. En '
        f'signant, vous constatez avec {nom} que le travail prévu au contrat '
        f'a été réalisé ; vos garanties commencent aujourd\'hui.',
        contenu.get('reference'))
    corps += c.cartes(
        c.carte('Votre installation', valeur_sys, detail_sys),
        c.carte('Mise en service',
                c.esc(c.date_longue(reception.get('date_mise_en_service'))
                      or 'Date à porter'),
                c.esc(chantier.get('adresse') or '')),
    )
    corps += c.h2('Ce que nous avons vérifié ensemble')
    corps += c.cases(contenu.get('constats'))

    corps += c.h2('La réception',
                  'Cochez une seule des deux cases.')
    sans = not contenu.get('reserves')
    corps += c.cases([
        {'texte': '**Je prononce la réception sans réserve.** Les travaux '
                  'sont conformes au contrat et au devis accepté.',
         'cochee': bool(reception.get('prononcee')) and sans},
        {'texte': '**Je prononce la réception avec les réserves '
                  'ci-dessous**, que ' + (societe.get('nom_court')
                                          or societe.get('nom') or '')
                  + " s'engage à lever dans le délai indiqué.",
         'cochee': bool(reception.get('prononcee')) and not sans},
    ])
    delai = reception.get('delai_levee_reserves')
    corps += c.encadre(
        'Réserves' + (f' — à lever sous {delai}' if delai else ''),
        (c.paragraphes(contenu.get('reserves')) if contenu.get('reserves')
         else c.lignes_a_ecrire(2)), 'net')

    corps += c.h2('Le solde de votre installation')
    corps += c.frise(contenu.get('echeancier'), avec_etats=True)
    du = paiement.get('exigible_maintenant')
    if du in (None, '', 0, '0', '0.00'):
        corps += c.encadre(
            'Payé intégralement',
            f'<div class="grand">{c.esc(c.montant(paiement.get("total_regle")))}'
            f'</div><p>Vous avez réglé la totalité du prix. Il ne reste rien '
            f'à payer.</p>', 'ok')
    else:
        texte = f'<div class="grand">{c.esc(c.montant(du))}</div>'
        if paiement.get('exigible_en_lettres'):
            texte += (f'<p class="lettres">'
                      f'{c.esc(paiement["exigible_en_lettres"])}</p>')
        texte += (f'<p>{c.esc(paiement.get("engagement") or "")}</p>'
                  if paiement.get('engagement') else '')
        if paiement.get('modalites'):
            texte += f'<p class="petit">{c.esc(paiement["modalites"])}</p>'
        corps += c.encadre('Solde à régler à la réception', texte)

    corps += c.h2('Ce que la réception change')
    corps += c.articles(contenu.get('articles'))
    corps += _conditions_particulieres(contenu)
    corps += c.signatures(
        contenu,
        mention_client='Signature précédée de la mention manuscrite '
                       '« Lu et approuvé, bon pour réception »')
    return _page(contenu, corps, classe='proces')


# ── Acte 4 — Clôture : quitus, certificat de garantie, conseils ─────────────

def _journee(journee):
    """La journée type, du lever au coucher du soleil. Les largeurs suivent les
    parts du ``contenu`` : elles situent les moments, elles ne chiffrent rien."""
    plages = journee.get('plages') or []
    total = sum(float(p.get('part') or 0) for p in plages) or 1

    def largeur(p):
        return f'{100 * float(p.get("part") or 0) / total:.2f}%'

    rail = ''.join(
        f'<div class="{c.esc(p.get("sorte"))}" style="width:{largeur(p)}">'
        f'{c.esc(p.get("libelle") or "")}</div>' for p in plages)
    sous = ''.join(
        f'<div class="{c.esc(p.get("sorte"))}" style="width:{largeur(p)}">'
        f'{c.esc(p.get("sous") or "")}</div>' for p in plages)
    legende = (f'<p class="petit">{c.esc(journee["legende"])}</p>'
               if journee.get('legende') else '')
    return (f'<div class="journee"><div class="rail">{rail}</div>'
            f'<div class="sous">{sous}</div>{legende}</div>')


def cloture_garanties(contenu):
    societe = contenu.get('societe') or {}
    chantier = contenu.get('chantier') or {}
    systeme = contenu.get('systeme') or {}
    prix = contenu.get('prix') or {}
    paiement = contenu.get('paiement') or {}
    sav = contenu.get('sav') or {}
    valeur_sys, detail_sys = _resume_systeme(systeme)

    corps = c.titre(
        'cloture_garanties', contenu.get('titre') or
        'Quitus et certificat de garantie',
        'Votre installation est payée, garantie et à vous. Gardez ce '
        'document : il prouve votre paiement, liste vos garanties et vous '
        'aide à tirer le meilleur de votre énergie solaire.',
        contenu.get('reference'))
    corps += c.cartes(
        c.carte('Votre installation', valeur_sys, detail_sys),
        c.carte('Payé intégralement',
                c.esc(c.montant(paiement.get('total_regle')
                                or prix.get('total_ttc'))),
                'Solde : <b>0,00 DH</b> · plus rien à régler', forte=True),
    )
    corps += c.h2('Attestation de paiement intégral')
    corps += c.encadre('Quitus',
                       c.paragraphes(contenu.get('quitus')), 'ok')
    corps += c.tableau_paiements(contenu.get('paiements'),
                                 paiement.get('total_regle'))
    corps += c.signatures(contenu, mention_client='', client_signe=False,
                          exemplaires=False)

    corps += c.h2('Certificat de garantie',
                  f'Garanties en vigueur depuis la réception des travaux, le '
                  f'{c.esc(c.date_longue((contenu.get("reception") or {}).get("date")) or "…")}'
                  f', à l\'adresse {c.esc(chantier.get("adresse") or "du chantier")}.')
    corps += c.tableau_garanties(contenu.get('garanties'), avec_dates=True)
    # Le matériel n'est relisté que s'il porte ses numéros de série (preuve
    # de ce qui est couvert) ; sinon le tableau des garanties suffit.
    if any(lg.get('numeros_serie') for lg in systeme.get('lignes') or []):
        corps += c.h2('Le matériel couvert')
        corps += c.tableau_materiel(systeme['lignes'], avec_series=True)
    corps += c.h2('Si quelque chose ne va pas')
    corps += c.articles(contenu.get('articles'))
    contact = ' · '.join(c.esc(x) for x in (
        sav.get('telephone'), sav.get('whatsapp'), sav.get('email')) if x)
    if contact:
        corps += c.encadre(
            f'Service après-vente {societe.get("nom_court") or societe.get("nom") or ""}',
            f'<div class="grand" style="font-size:15pt">{contact}</div>'
            f'<p class="petit">{c.esc(sav.get("horaires") or "")}</p>', 'net')

    conseils = contenu.get('conseils') or []
    if conseils:
        corps += '<div class="suite"></div>'
        corps += c.h2('Bien consommer votre énergie solaire',
                      c.esc(contenu.get('conseils_intro') or ''))
        if contenu.get('journee'):
            corps += _journee(contenu['journee'])
        corps += '<div class="conseils">' + ''.join(
            f'<div class="conseil"><div class="lbl">{c.esc(k.get("rubrique"))}'
            f'</div><h3>{c.esc(k.get("titre"))}</h3>'
            f'<p>{c.esc(k.get("texte"))}</p></div>' for k in conseils) + '</div>'
        if contenu.get('entretien'):
            corps += c.h2("L'entretien, en peu de mots")
            corps += ('<div class="article plein"><div class="texte">'
                      + c.paragraphes(contenu['entretien']) + '</div></div>')

    return _page(contenu, corps, paraphes=False, classe='cloture')


_RENDUS = {
    'contrat_installation': contrat_installation,
    'pv_livraison': pv_livraison,
    'pv_reception': pv_reception,
    'cloture_garanties': cloture_garanties,
}


def html_de(contenu):
    """HTML complet d'un acte. ``ValueError`` si le type est inconnu."""
    try:
        rendu = _RENDUS[contenu['type']]
    except KeyError:
        raise ValueError(f"Type d'acte inconnu : {contenu.get('type')!r}")
    return rendu(contenu)
