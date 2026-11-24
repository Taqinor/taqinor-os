"""Textes PAR DÉFAUT des quatre actes — tous modifiables dans l'ERP.

Règles de rédaction (docs/contrats/conception.md § Contenu) :

- français simple, phrases courtes, « le Client » et le nom de la société ;
- aucune clause que la loi n° 31-08 range parmi les clauses abusives : pas de
  modification unilatérale du prix ou du matériel, pas de pénalité à sens
  unique, pas de clause attributive de compétence, la garantie légale toujours
  rappelée ;
- aucun chiffre inventé : une durée, un montant ou un délai vient du devis, des
  fiches produit, des réglages de la société ou du ``contexte`` ; ce qui manque
  s'imprime « à préciser » et se complète dans l'ERP avant l'envoi ;
- les références de loi citées ont été lues dans le texte consolidé officiel
  (loi n° 31-08, Dahir des obligations et des contrats, loi n° 82-21, loi
  n° 09-08) — la liste et les points laissés à un juriste sont dans
  docs/contrats/juridique.md.

Chaque fabrique rend des dictionnaires simples (``cle``, ``titre``,
``paragraphes``) : ce sont eux que l'écran modifie et que le rendu imprime.
"""

A_PRECISER = 'à préciser'


class _Contexte(dict):
    """Un repère absent s'imprime « à préciser », jamais une accolade."""

    def __missing__(self, cle):
        return A_PRECISER


def _f(texte, ctx):
    return texte.format_map(_Contexte(ctx or {}))


def _article(cle, titre, paragraphes, ctx):
    return {'cle': cle, 'titre': _f(titre, ctx),
            'paragraphes': [_f(p, ctx) for p in paragraphes if p]}


# Une seule règle de garde, la même au contrat (Propriété), à l'acte 2
# (Garde, avec « sans l'ouvrir ni le déplacer ») et à l'acte 3 (la dernière
# proposition seule) — revue 1, T8.
_GARDE_LIVRAISON = (
    "De la livraison au début de la pose, le Client a la garde du matériel "
    "livré : il le conserve à l'abri, dans un lieu fermé, ")
_GARDE_SANS_OUVRIR = "sans l'ouvrir ni le déplacer, "
_GARDE_REPOND = (
    "et répond des pertes ou des dégradations dues à son fait ou à un "
    "défaut de surveillance. ")
_GARDE_POSE = (
    "Pendant la pose et jusqu'à la réception, {societe} a la garde du "
    "chantier ; à la réception, ")
_GARDE_TRANSFERT = "la garde de l'installation passe au Client."


def _regle_de_garde(sans_ouvrir=False):
    return (_GARDE_LIVRAISON + (_GARDE_SANS_OUVRIR if sans_ouvrir else '')
            + _GARDE_REPOND + _GARDE_POSE + _GARDE_TRANSFERT)


# Textes communs au contrat et au certificat de garantie (acte 4).
_GARANTIE_LEGALE = (
    "Ces garanties s'ajoutent à la **garantie légale** des défauts et vices "
    "cachés (articles 549 à 575 du Dahir des obligations et des contrats, "
    "article 65 de la loi n° 31-08 et, pour le travail de pose, articles "
    "767 et 772 du même Dahir), que {societe} doit dans tous les cas.")
# Exclusions liées à la cause du dommage (revue 1, T9).
_EXCLUSIONS = (
    "une intervention ou une modification de l'installation par un tiers "
    "sans l'accord de {societe}, lorsqu'elle est la cause du dommage",
    "un choc, un incendie, une inondation, la foudre ou une surtension du "
    "réseau, sauf défaut des protections posées par {societe}",
    "un défaut de l'entretien décrit dans les notices remises à la "
    "réception, ou un usage contraire à ces notices",
)
_TRIBUNAL_DU_SIEGE = (
    "le litige est porté devant le tribunal compétent du siège de "
    "{societe}.")


# ── Acte 1 — Contrat d'installation ─────────────────────────────────────────

def _contrat_installation(ctx, options):
    consommateur = options.get('consommateur', True)
    arts = [
        ('objet', 'Objet du contrat', [
            "{societe} fournit, pose et met en service chez le Client, à "
            "l'adresse du chantier, l'installation solaire décrite au devis "
            "{devis_reference}{devis_accepte_le}.",
            "L'installation est livrée **clé en main** : étude, fourniture "
            "du matériel, pose, raccordement à l'installation électrique du "
            "Client, mise en service et explication du fonctionnement.",
            "Le devis accepté fait partie du contrat. Si deux lignes se "
            "contredisent, les conditions particulières l'emportent, puis le "
            "présent contrat, puis le devis.",
        ]),
        ('prix', 'Prix', [
            "Le prix est **ferme et définitif** : {total_ttc} toutes taxes "
            "comprises ({total_lettres}). Il comprend le matériel, la pose, "
            "la mise en service et les taxes.",
            "Tout travail qui ne figure pas au devis fait l'objet d'un devis "
            "complémentaire, accepté par écrit par le Client avant d'être "
            "réalisé.",
            "{societe} ne modifie seule ni le prix ni le matériel prévu. Si "
            "un matériel devient indisponible, elle propose au Client un "
            "matériel de qualité au moins équivalente, sans supplément de "
            "prix ; le Client donne son accord par écrit.",
        ]),
        ('paiement', 'Paiement', [
            "Le prix est payé en {nombre_etapes}, chacune liée à un moment "
            "précis du chantier :",
            "{liste_tranches}",
            "« À la signature » : le jour où le contrat est signé. « À la "
            "livraison » : le jour où le matériel est déposé à l'adresse du "
            "chantier, constaté par le procès-verbal de livraison. « À la "
            "réception » : le jour où le procès-verbal de réception est "
            "signé.",
            "Chaque paiement donne lieu à une facture. {modalites_paiement}",
            "La commande du matériel est lancée dès l'encaissement du "
            "premier paiement.",
        ]),
        ('delais', 'Délais', [
            "{societe} s'engage à avoir livré le matériel, posé "
            "l'installation et l'avoir mise en service **au plus tard "
            "{date_limite}**.",
            "Ce délai est suspendu pendant un cas de force majeure, pendant "
            "les intempéries qui rendent le travail en toiture dangereux, "
            "pendant tout retard dû au Client (accès au chantier impossible, "
            "paiement en attente, travaux préalables à sa charge non "
            "terminés) et pendant l'attente de la réponse du gestionnaire "
            "du réseau, lorsque son accord est requis avant les travaux. "
            "{societe} prévient le Client par écrit de toute suspension.",
            ("Si la date limite, prolongée des suspensions ci-dessus, est "
             "dépassée de plus de sept jours, le Client peut, dans les cinq "
             "jours qui suivent, mettre fin au contrat par écrit (articles "
             "12 à 14 de la loi n° 31-08) ; {societe} lui rembourse alors "
             "les sommes versées dans les sept jours."
             if consommateur else ''),
        ]),
        ('engagements_societe', "Ce que {societe} s'engage à faire", [
            "- réaliser les travaux dans les règles de l'art et selon les "
            "normes de sécurité électrique en vigueur ;\n"
            "- employer un personnel qualifié et le matériel prévu au devis, "
            "neuf et garanti par son fabricant ;\n"
            "- protéger les lieux pendant le chantier et les laisser propres "
            "à la fin ;\n"
            "- remettre au Client, à la réception, les notices et les fiches "
            "techniques et, à la clôture, le certificat de garantie.",
        ]),
        ('engagements_client', "Ce que le Client s'engage à faire", [
            "- donner accès au chantier, à l'eau et à l'électricité aux "
            "dates convenues ;\n"
            "- garantir qu'il est propriétaire des lieux ou qu'il a obtenu "
            "l'autorisation nécessaire (propriétaire, copropriété) ;\n"
            "- signaler avant le début des travaux tout ce qui peut les "
            "gêner ou les rendre dangereux : état de la toiture, étanchéité, "
            "installation électrique ancienne ;\n"
            "- payer chaque étape au moment prévu à l'article Paiement.",
        ]),
    ]
    if options.get('raccorde_reseau', True):
        arts.append(('demarches', "Démarches auprès du réseau électrique", [
            "La loi n° 82-21 sur l'autoproduction d'électricité demande au "
            "propriétaire d'une installation raccordée au réseau de la "
            "déclarer au gestionnaire du réseau avant les travaux ou, selon "
            "sa puissance, d'obtenir son accord de raccordement.",
            "Le Client charge {societe} de préparer ce dossier et de le "
            "suivre pour lui ; il signe les documents demandés. Les frais "
            "éventuels du gestionnaire du réseau, dont ceux du compteur, "
            "restent à la charge du Client.",
        ]))
    if options.get('reserve_propriete', True):
        arts.append(('propriete', 'Propriété du matériel', [
            "Le matériel reste la propriété de {societe} jusqu'au paiement "
            "complet du prix (articles 618-21 et suivants du Dahir des "
            "obligations et des contrats). Jusque-là, le Client ne peut ni "
            "le vendre, ni le donner en garantie, ni le faire démonter.",
        ]))
    # La garde ne dépend pas de la réserve de propriété : article toujours
    # présent (revue 1, T8 bis).
    arts.append(('garde', 'Garde du matériel', [_regle_de_garde()]))
    arts += [
        ('reception', 'Réception des travaux', [
            "À la fin de la pose, {societe} met l'installation en service en "
            "présence du Client et lui en explique le fonctionnement. Les "
            "deux parties signent alors un procès-verbal de réception.",
            "Le Client peut y inscrire des réserves ; {societe} les lève "
            "dans le délai noté au procès-verbal. Des réserves n'empêchent "
            "pas d'utiliser l'installation. Si des réserves sont inscrites, "
            "les parties peuvent y chiffrer, d'un commun accord, une part du "
            "solde retenue jusqu'à leur levée, sans dépasser la valeur des "
            "travaux qui restent à faire ; sans montant chiffré, aucune "
            "retenue ne s'applique.",
            "Si le Client refuse de signer le procès-verbal, il indique par "
            "écrit, dans les sept jours qui suivent la mise en service, les "
            "défauts qui motivent son refus ; {societe} y remédie, puis une "
            "nouvelle réception est proposée. Sans réponse écrite dans ce "
            "délai, {societe} peut mettre le Client en demeure de recevoir "
            "les travaux (article 774 du Dahir des obligations et des "
            "contrats).",
            "La réception marque le point de départ des garanties et rend "
            "exigible le solde du prix.",
        ]),
        ('garanties', 'Garanties', [
            "Le Client bénéficie des garanties du tableau « Vos garanties » : "
            "celles des fabricants sur le matériel, et celle de {societe} "
            "sur son travail de pose pendant {garantie_installation}.",
            "Pendant ces durées, {societe} est l'interlocuteur unique du "
            "Client : elle fait le diagnostic, traite la demande auprès du "
            "fabricant et prend à sa charge les frais de transport du "
            "matériel garanti. La durée d'une garantie est prolongée du "
            "temps pendant lequel le matériel est immobilisé pour "
            "réparation. {pieces_detachees}",
            _GARANTIE_LEGALE,
            "Elles ne couvrent pas : " + " ; ".join(_EXCLUSIONS) + ".",
        ]),
        ('estimations', 'Production et économies estimées', [
            "Les chiffres de production et d'économies du devis sont des "
            "estimations, calculées à partir de l'ensoleillement moyen du "
            "site et de la consommation déclarée par le Client. La "
            "production réelle varie avec la météo, l'ombrage et l'usage : "
            "ces chiffres ne sont pas une promesse de résultat.",
        ]),
    ]
    retard = [
        "Si un paiement n'est pas fait à la date prévue, {societe} adresse "
        "au Client une mise en demeure écrite. Si elle reste sans effet "
        "pendant {delai_mise_en_demeure}, {societe} peut suspendre les "
        "travaux, puis demander en justice le paiement des sommes dues ou "
        "la restitution du matériel resté sa propriété.",
    ]
    if options.get('penalite_retard_pct'):
        retard.append(
            "Passé ce délai, une indemnité forfaitaire de {penalite_retard} "
            "des sommes impayées est due à {societe}, une seule fois, quels "
            "que soient la durée du retard et le nombre de relances.")
    arts += [
        ('retard', 'Retard de paiement', retard),
        ('fin_anticipee', 'Fin anticipée du contrat', [
            "Si le Client renonce au contrat alors que le matériel est "
            "commandé ou les travaux commencés, {societe} "
            "conserve, sur les sommes versées et sur justificatifs, le coût "
            "du matériel commandé pour lui et des travaux déjà réalisés ; "
            "le reste lui est remboursé. Le matériel ainsi payé est remis au "
            "Client ; si {societe} peut le rendre à son fournisseur ou le "
            "réutiliser, elle ne retient que les frais de retour justifiés.",
            "Si {societe} ne peut pas exécuter le contrat, elle rembourse "
            "au Client l'intégralité des sommes versées.",
        ]),
        ('donnees', 'Données personnelles', [
            "{societe} utilise les données du Client (identité, "
            "coordonnées, adresse, consommation d'électricité) pour établir "
            "le devis, exécuter le contrat, assurer les garanties et le "
            "service après-vente. Elles ne sont transmises qu'à ceux qui "
            "interviennent sur le chantier ou sur les garanties (fabricants, "
            "gestionnaire du réseau), au fabricant de l'onduleur, dont "
            "l'application de suivi peut héberger les données de production "
            "et de consommation hors du Maroc, et aux autorités ou conseils "
            "lorsque la loi ou le recouvrement d'une somme due l'exige.",
            "Conformément à la loi n° 09-08, le Client peut accéder à ses "
            "données, les faire rectifier ou s'opposer à leur utilisation "
            "en écrivant à {email_societe}.{cndp}",
        ]),
        ('differends', 'En cas de désaccord', [
            "Les parties cherchent d'abord une solution amiable : le Client "
            "écrit à {societe}, qui lui répond dans les {delai_reponse}.",
            ("À défaut d'accord, le litige est porté devant le tribunal "
             "compétent selon la loi ; le Client peut saisir celui de son "
             "domicile (article 202 de la loi n° 31-08)." if consommateur
             else "À défaut d'accord, " + _TRIBUNAL_DU_SIEGE),
        ]),
        ('dispositions_finales', 'Modifications et exemplaires', [
            "Toute modification du contrat fait l'objet d'un avenant écrit, "
            "signé des deux parties. Le contrat est établi en deux "
            "exemplaires originaux, un pour chaque partie.",
            ("Le contrat est accompagné de sa traduction en arabe, remise en "
             "même temps (loi n° 31-08, article 206). En cas de différence "
             "entre les deux textes, l'interprétation la plus favorable au "
             "Client s'applique (article 9 de la même loi)."
             if consommateur else ''),
        ]),
    ]
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


# ── Acte 2 — Procès-verbal de livraison ─────────────────────────────────────

def _pv_livraison(ctx, options, variante):
    arts = [
        ('constat', 'Ce que constate ce procès-verbal', [
            "Le Client a vérifié, en présence de {societe}, le matériel "
            "listé ci-dessus. Ce qui est coché est constaté ; toute "
            "anomalie visible est notée dans les réserves.",
            "Un défaut qui ne pouvait pas se voir à la livraison reste "
            "couvert par les garanties du contrat.",
        ]),
        ('garde', 'Garde du matériel', [
            _regle_de_garde(sans_ouvrir=True),
        ]),
    ]
    if options.get('reserve_propriete', True):
        arts.append(('propriete', 'Propriété', [
            "Le matériel reste la propriété de {societe} jusqu'au paiement "
            "complet du prix, comme prévu au contrat {contrat_reference}.",
        ]))
    if variante == 'tranche_reglee':
        arts.append(('paiement', 'Paiement', [
            "{societe} confirme avoir encaissé à ce jour {total_regle}, soit "
            "{pourcentage_regle} du prix. Rien n'est à payer à la "
            "livraison.",
            "Le reste du prix, soit {reste_a_regler}, sera exigible à la "
            "réception des travaux.",
        ]))
    else:
        arts.append(('paiement', 'Paiement de cette étape', [
            "Selon l'échéancier du contrat {contrat_reference}, les sommes "
            "dues à la date de ce procès-verbal s'élèvent à "
            "{exigible_maintenant} ({exigible_lettres}). Le Client reconnaît "
            "avoir reçu le matériel listé ci-dessus et devoir cette somme à "
            "{societe}.",
            "La pose est programmée dès l'encaissement de cette somme.",
        ]))
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


# ── Acte 3 — Procès-verbal de réception ─────────────────────────────────────

def _pv_reception(ctx, options):
    arts = [
        ('portee', 'Ce que vaut la réception', [
            "En signant, le Client reconnaît que {societe} a achevé les "
            "travaux prévus au contrat {contrat_reference}{contrat_du} et au "
            "devis {devis_reference}, que l'installation est conforme à ces "
            "documents et fonctionne, et qu'il n'a constaté aucun défaut "
            "apparent en dehors des réserves écrites ci-dessus.",
            "À la réception, " + _GARDE_TRANSFERT + " "
            "{societe} lève les réserves éventuelles dans le délai "
            "indiqué ; leur levée est constatée par écrit et signée du "
            "Client.",
            "Les garanties prévues au contrat **commencent ce jour**. Les "
            "notices et les fiches techniques sont remises au Client ce "
            "jour ; le certificat de garantie récapitulatif lui est remis "
            "avec l'acte de clôture.",
        ]),
        ('solde', 'Solde du prix', [
            "Le Client reconnaît devoir à {societe} la somme de "
            "{exigible_maintenant} ({exigible_lettres}), reste du prix du "
            "contrat {contrat_reference} encore dû à ce jour, payable à la "
            "signature du présent procès-verbal.",
            "Si des réserves sont inscrites, les parties chiffrent "
            "ci-dessus, d'un commun accord, la part du solde retenue jusqu'à "
            "leur levée ; elle ne peut dépasser la valeur des travaux qui "
            "restent à faire. Le reste est payable à la signature ; la part "
            "retenue est payable dans les huit jours qui suivent le constat "
            "écrit de la levée. Sans montant chiffré, aucune retenue ne "
            "s'applique.",
        ] + (["Jusqu'au paiement complet, le matériel reste la propriété "
              "de {societe}."]
             if options.get('reserve_propriete', True) else [])),
        ('retard', 'Retard de paiement', [
            "Si le solde n'est pas réglé, {societe} adresse au Client une "
            "mise en demeure écrite. Si elle reste sans effet pendant "
            "{delai_mise_en_demeure}, {societe} peut demander en justice "
            "le paiement du solde ou la restitution du matériel resté sa "
            "propriété.",
        ] + (["Passé ce délai, une indemnité forfaitaire de "
              "{penalite_retard} des sommes impayées est due à {societe}, "
              "une seule fois."]
             if options.get('penalite_retard_pct') else [])),
    ]
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


# ── Acte 4 — Quitus, certificat de garantie, conseils ───────────────────────

def _cloture_garanties(ctx, options):
    consommateur = options.get('consommateur', True)
    arts = [
        ('contact', 'Qui appeler', [
            "Un seul interlocuteur : le service après-vente de {societe}. "
            "Décrivez ce que vous constatez et envoyez une photo de l'écran "
            "de l'onduleur ou de l'application de suivi.",
        ]),
        ('demarche', 'Comment se passe une demande', [
            "- {societe} fait le diagnostic, à distance ou sur place ;\n"
            "- si une garantie joue, {societe} répare ou remplace le "
            "matériel et traite la demande auprès du fabricant ;\n"
            "- les réparations sont faites sur place ou à l'atelier de "
            "{societe}, {adresse_societe} ;\n"
            "- le matériel à renvoyer au fabricant passe par {societe} ;\n"
            "- les frais de transport du matériel garanti sont à la charge "
            "de {societe} ;\n"
            "- la durée de la garantie est prolongée du temps pendant "
            "lequel le matériel est immobilisé ; un reçu daté vous est "
            "remis à l'enlèvement et au retour.",
        ]),
        ('couvert', 'Ce qui est couvert', [
            "Les défauts du matériel, dans les conditions de chaque "
            "fabricant, et les défauts de pose pendant la durée de la "
            "garantie d'installation. {pieces_detachees}",
        ]),
        ('exclusions', "Ce qui ne l'est pas", [
            "- " + " ;\n- ".join(_EXCLUSIONS) + ".",
        ]),
        ('garantie_legale', 'Vos droits dans tous les cas', [
            _GARANTIE_LEGALE,
            "En cas de désaccord sur une garantie, écrivez à {societe}, "
            "qui vous répond dans les {delai_reponse} ; à défaut d'accord, "
            + ("vous pouvez saisir le tribunal de votre domicile."
               if consommateur else _TRIBUNAL_DU_SIEGE),
        ]),
    ]
    return [_article(cle, titre, par, ctx) for cle, titre, par in arts]


def articles_par_defaut(type_acte, variante='', ctx=None, options=None):
    """Les articles par défaut d'un acte. ``ctx`` : repères déjà mis en forme
    (montants, dates, noms) ; ``options`` : ``consommateur``,
    ``reserve_propriete``, ``raccorde_reseau``, ``penalite_retard_pct``."""
    ctx = ctx or {}
    options = options or {}
    if type_acte == 'contrat_installation':
        return _contrat_installation(ctx, options)
    if type_acte == 'pv_livraison':
        return _pv_livraison(ctx, options, variante)
    if type_acte == 'pv_reception':
        return _pv_reception(ctx, options)
    if type_acte == 'cloture_garanties':
        return _cloture_garanties(ctx, options)
    raise ValueError(f"Type d'acte inconnu : {type_acte!r}")


def quitus_par_defaut(ctx):
    return [_f(p, ctx) for p in (
        # {ecart_regle} : phrase complète précédée d'une espace (avoir,
        # retenue, abandon de créance) ou vide — la somme réellement réglée,
        # jamais le prix (revue 1, S2).
        "{societe} atteste avoir reçu de {client} la somme totale de "
        "**{total_regle}** ({total_regle_lettres}), en règlement complet du "
        "prix de l'installation objet du contrat "
        "{contrat_reference}.{ecart_regle}",
        "Le Client est quitte envers {societe} du prix de ce contrat. La "
        "propriété de l'ensemble du matériel lui est "
        "définitivement acquise.",
    )]


# ── Constats à cocher ───────────────────────────────────────────────────────

def constats_par_defaut(type_acte):
    if type_acte == 'pv_livraison':
        textes = (
            "Le matériel livré correspond au devis accepté.",
            "Les colis sont arrivés fermés et en bon état apparent.",
            "Le matériel est entreposé à l'abri, dans un lieu fermé, à "
            "l'adresse du chantier.",
        )
        return [{'texte': t, 'cochee': False} for t in textes]
    if type_acte == 'pv_reception':
        textes = (
            "L'installation posée est **conforme au devis accepté et au "
            "contrat**.",
            "Elle a été **mise en service et fonctionne**, en ma présence.",
            "Son fonctionnement, l'application de suivi et les gestes de "
            "sécurité m'ont été **expliqués**.",
            "J'ai **reçu les notices et les fiches techniques** de mon "
            "installation.",
            "Le chantier a été **laissé propre** ; je n'ai constaté aucun "
            "dégât sur ma toiture ni dans ma maison.",
        )
        return [{'texte': t, 'cochee': False} for t in textes]
    return []


# ── Conseils d'usage (acte 4) ───────────────────────────────────────────────
# Sources lues (docs/contrats/juridique.md § Conseils) : guide ADEME « Comment
# réduire sa facture d'électricité », NSW Government « Get the most from solar
# energy », Solar Victoria « Making the most of solar » et « Tips for winter »,
# Home Energy Scotland « Solar panels ». Aucun pourcentage ni kilowattheure
# n'est imprimé : les conseils disent quoi faire, pas combien on gagne.

def journee_solaire(avec_batterie):
    nuit = 'batterie, puis réseau' if avec_batterie else 'réseau'
    return {
        'plages': [
            {'sorte': 'nuit', 'part': 4, 'libelle': 'Nuit', 'sous': nuit},
            {'sorte': 'bord', 'part': 3, 'libelle': 'Matin',
             'sous': 'la production monte'},
            {'sorte': 'plein', 'part': 7, 'libelle': 'Milieu de journée',
             'sous': 'le meilleur moment pour vos gros appareils'},
            {'sorte': 'bord', 'part': 3, 'libelle': 'Fin de journée',
             'sous': 'la production baisse'},
            {'sorte': 'nuit', 'part': 5, 'libelle': 'Soir et nuit',
             'sous': nuit},
        ],
        'legende': "Votre installation produit du lever au coucher du "
                   "soleil, avec un maximum en milieu de journée.",
    }


def conseils_par_defaut(avec_batterie):
    """``(intro, conseils)`` : le texte d'ouverture et les fiches conseil."""
    if avec_batterie:
        intro = ("Le jour, vos panneaux alimentent la maison et chargent la "
                 "batterie ; le soir, la batterie prend le relais. Plus vos "
                 "gros appareils tournent au soleil, plus la batterie reste "
                 "pleine pour la nuit. Pendant une coupure du réseau, seuls "
                 "les circuits secourus restent alimentés, si votre "
                 "installation en comporte.")
    else:
        intro = ("Sans batterie, l'électricité solaire se consomme au moment "
                 "où elle est produite : le bon réflexe est de faire tourner "
                 "vos appareils quand le soleil brille. Pendant une coupure "
                 "du réseau, l'installation s'arrête : c'est une sécurité.")
    conseils = [
        {'rubrique': 'Gros appareils',
         'titre': 'Lancez-les en milieu de journée',
         'texte': "Lave-linge, lave-vaisselle, four, fer à repasser, pompe "
                  "ou surpresseur d'eau : faites-les tourner quand la "
                  "production est la plus forte. Le départ différé le fait "
                  "pour vous quand vous êtes absent."},
        {'rubrique': 'Un à la fois',
         'titre': 'Étalez plutôt que cumuler',
         'texte': "Deux gros appareils en même temps peuvent dépasser ce "
                  "que les panneaux produisent : lancez la lessive en fin "
                  "de matinée, le lave-vaisselle en début d'après-midi."},
        {'rubrique': 'Eau chaude',
         'titre': "Chauffez l'eau au soleil",
         'texte': "Si votre chauffe-eau est électrique, réglez sa plage de "
                  "chauffe sur le milieu de journée plutôt que la nuit."},
        {'rubrique': 'Climatisation',
         'titre': 'Rafraîchissez avant le soir',
         'texte': "Faites tourner la climatisation l'après-midi, tant que "
                  "les panneaux produisent, plutôt que de la démarrer à la "
                  "nuit tombée."},
    ]
    if avec_batterie:
        conseils.append(
            {'rubrique': 'Batterie',
             'titre': 'Gardez-la pour le soir',
             'texte': "Elle se charge le jour avec le surplus et vous "
                      "alimente après le coucher du soleil : évitez de la "
                      "vider l'après-midi avec de gros appareils."})
    else:
        conseils.append(
            {'rubrique': 'Veilles',
             'titre': 'Éteignez ce qui ne sert pas la nuit',
             'texte': "La nuit, tout ce qui reste branché est payé au "
                      "réseau : coupez les appareils en veille avec une "
                      "multiprise à interrupteur, sauf réfrigérateur, "
                      "congélateur et box internet ; ne coupez jamais "
                      "l'onduleur ni ses disjoncteurs."})
    conseils.append(
        {'rubrique': 'Suivi',
         'titre': "Regardez l'application une fois par semaine",
         'texte': "Elle montre ce que vous produisez et ce que vous "
                  "consommez : c'est le meilleur moyen de caler vos "
                  "habitudes sur le soleil et de repérer une anomalie."})
    return intro, conseils


def entretien_par_defaut():
    return [
        "- un coup d'œil à l'application chaque semaine : une production à "
        "zéro en plein jour doit nous être signalée ;\n"
        "- des panneaux propres : quand la poussière s'accumule, rincez à "
        "l'eau claire, sans nettoyeur haute pression ni produit, sans monter "
        "ni marcher sur les panneaux ; sur un toit en pente, appelez-nous ;\n"
        "- rien ne doit faire de l'ombre aux panneaux : antenne, linge, "
        "végétation qui pousse ;\n"
        "- avant tout travail sur la toiture ou sur l'installation "
        "électrique, prévenez-nous.",
    ]
