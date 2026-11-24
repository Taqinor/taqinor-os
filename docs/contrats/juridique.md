# Dossier contractuel — sources juridiques et points à faire confirmer (24/11/2026)

**Ce document n'est pas un avis juridique.** Les textes par défaut des quatre actes
(`backend/django_core/apps/documents/contrats/textes.py`) ont été écrits après lecture des textes consolidés ci-dessous
(lecture du 24/11/2026). Ils doivent être relus par un juriste marocain avant un usage large ; la liste de ce qu'il
doit trancher est au § 4. Aucune règle de droit français n'a été importée : la « garantie de parfait achèvement »,
par exemple, n'existe pas dans le Dahir des obligations et des contrats (recherche dans le texte : aucune occurrence).

Niveaux : **P** = lu dans le texte officiel ; **S** = source secondaire (cabinet, presse) ; **N** = non vérifié.

## 1. Textes lus

| Clé | Texte | Adresse |
|---|---|---|
| A | Loi n° 31-08 (protection du consommateur), version consolidée + décret n° 2-12-503 en notes | adala.justice.gov.ma — « protection de consommateur » |
| C | Dahir des obligations et des contrats (DOC), version consolidée du 18/03/2021 | adala.justice.gov.ma — « Code des Obligations et des Contrats » |
| D | Loi n° 82-21 (autoproduction d'énergie électrique), Dahir 1-23-21 du 10/02/2023 | adala.justice.gov.ma |
| G | Code général des impôts 2026 | tax.gov.ma |
| I | Loi n° 43-20 (services de confiance pour les transactions électroniques) | adala.justice.gov.ma |
| J | Loi n° 09-08 (protection des données personnelles) | adala.justice.gov.ma |
| K | IEC 62446-1:2016 (aperçu officiel : documentation à remettre) | standards.iteh.ai |
| E, F | Notes de cabinet et de presse sur le décret d'application de la loi 82-21 (S) | ashurstperkinscoie.com, pv-magazine.com |

## 2. Règle → ce que les actes en font

| Règle | Référence | Niveau | Dans les actes |
|---|---|---|---|
| Une installation clé en main avec fourniture du matériel est un louage d'ouvrage | DOC art. 723, 759-760 | P | objet du contrat |
| Au-delà de 10 000 DH, la preuve se fait par écrit ; l'écrit électronique vaut le papier si le signataire est identifié et l'intégrité conservée | DOC art. 443, 417-1 | P | un acte écrit à chaque étape, PDF figé + empreinte |
| Clauses claires ; le doute profite au consommateur | 31-08 art. 9 | P | rédaction en français simple |
| Un exemplaire remis au consommateur | 31-08 art. 8 | P | « deux exemplaires originaux » |
| **Un contrat rédigé en langue étrangère est accompagné d'une traduction arabe** | 31-08 art. 206 | P | **pas encore fait — § 4 point 1** |
| Prix affiché toutes taxes comprises | 31-08 art. 5 | P | prix TTC, HT et TVA en détail |
| Au-delà de 3 000 DH, une **date limite d'exécution** écrite est obligatoire ; dépassée de plus de 7 jours hors force majeure, le consommateur peut résoudre dans les 5 jours suivants ; remboursement sous 7 jours | 31-08 art. 12-14, décret art. 28 | P | carte « Terminé au plus tard le », article Délais |
| Clauses abusives : modification unilatérale, pénalité disproportionnée, conformité jugée par le seul fournisseur, clause non lue, etc. ; nulles, d'ordre public | 31-08 art. 15-20 | P | aucune de ces clauses ; matériel de remplacement seulement avec accord écrit et sans supplément |
| Démarchage : contrat signé au domicile, « même à sa demande » → formulaire détachable, 7 jours de rétractation, aucun paiement pendant ces 7 jours | 31-08 art. 45-50 | P | **rien — décision de Reda du 24/11/2026** : ce chapitre vise la vente à domicile, pas une société que le client contacte ; non intégré (§ 4 point 2, pour mémoire) |
| Arrhes : imputées sur le prix | DOC art. 288-290 | P | le mot « acompte », à valoir sur le prix |
| Garantie légale des défauts applicable, « sans garantie » exclu, action dans l'année (meubles) ou les 2 ans (immeubles), non réductible | 31-08 art. 65 ; DOC art. 549-575 | P | rappelée dans le contrat et le certificat |
| Garantie conventionnelle : durée, portée, conditions précises ; garantie légale mentionnée ; frais de transport au fournisseur ; durée prolongée du temps d'immobilisation, reçus à l'enlèvement et au retour | 31-08 art. 66-68, 71-73 | P | tableau des garanties, articles Garanties et « Comment se passe une demande » |
| L'écrit de garantie mentionne : le garant et son adresse, le bien, les obligations du garant, les démarches et qui les supporte, la durée précise, la disponibilité des pièces, les centres de réparation | 31-08 art. 72 | P | certificat de garantie (acte 4) ; **durée de disponibilité des pièces : valeur par défaut à confirmer — § 4 point 6** |
| Le consommateur peut toujours saisir le tribunal de son domicile | 31-08 art. 202 | P | article « En cas de désaccord », aucune clause de compétence |
| Réserve de propriété valable si convenue par écrit ; opposable aux tiers après inscription au registre des sûretés mobilières ; tient après incorporation si la séparation se fait sans dommage | DOC art. 618-21 à 618-24 | P | article Propriété, rappelé aux actes 2 et 3, levée à l'acte 4 |
| Clause pénale valable, réductible par le juge si excessive | DOC art. 264 | P | pénalité optionnelle, désactivée par défaut |
| Les intérêts doivent être stipulés par écrit ; la stipulation d'intérêts entre musulmans est nulle | DOC art. 870-871 | P | aucun intérêt de retard dans les actes |
| Le maître d'ouvrage doit recevoir l'ouvrage conforme ; l'ouvrage reçu sans réserve malgré un défaut connu est réputé accepté ; refus ou restitution sous une semaine avec délai de reprise | DOC art. 768, 771, 774 | P | **le procès-verbal de réception signé prouve la conformité** ; réserves écrites avec délai |
| Le prix n'est dû qu'après l'ouvrage accompli, sauf paiement par fractions convenu | DOC art. 775 | P | tranches écrites au contrat, solde exigible à la réception |
| Le locateur d'ouvrage garantit les défauts de son travail ; clause contraire nulle | DOC art. 767, 772 | P | garantie d'installation |
| Signature électronique simple recevable ; fiabilité présumée seulement pour la signature qualifiée | 43-20 art. 2-7 ; DOC art. 417-2, 417-3 | P | signature tracée = signature simple + piste de preuve (empreinte, IP, date) ; papier toujours possible |
| Signature manuscrite de la main de la partie, au bas de l'acte ; le cachet seul ne vaut pas | DOC art. 426 | P | blocs de signature en fin d'acte |
| Information de la personne dont on collecte les données | 09-08 art. 5 | P | article Données personnelles (référence CNDP : champ à remplir) |
| Déclaration au gestionnaire du réseau avant travaux (basse tension sous le seuil) ou accord de raccordement ; compteur intelligent posé par le gestionnaire ; déclaration à la charge de l'autoproducteur | 82-21 art. 3-5, 17-19 | P (seuil 11 kW : S) | article Démarches : le Client mandate la société pour préparer le dossier |
| Documentation à remettre : données du système, schéma unifilaire, fiches techniques, mode d'emploi, garanties, résultats d'essais | IEC 62446-1 § 4 | P | liste de remise (acte 4, dossier de remise existant) |
| Droit de timbre de 0,25 % sur les quittances de paiements **en espèces** | CGI art. 252-I-B | P | rien d'imprimé ; à connaître pour un solde payé en espèces |

## 3. Conseils de consommation (acte 4) : sources

Guide ADEME « Comment réduire sa facture d'électricité » ; NSW Government « Get the most from solar energy » ; Solar
Victoria « Making the most of solar » et « Tips for winter » ; Home Energy Scotland « Solar panels ». Les conseils
imprimés ne portent **aucun chiffre** (ni pourcentage, ni kilowattheure, ni heure d'horloge) : ils disent quoi faire.

## 4. À faire trancher par un juriste (dans cet ordre)

1. **Version arabe** (31-08 art. 206) : obligatoire pour un contrat en français ? sanction si elle manque ?
2. **Démarchage** (pour mémoire — non intégré, décision de Reda du 24/11/2026) : une signature au domicile d'un
   client qui a lui-même contacté la société entre-t-elle dans le chapitre (l'article 45 dit « même à sa
   demande ») ?
3. **Contrat conclu à distance** (signature par lien) : régime des articles 25 à 44 de la loi 31-08 (non étudié ici),
   dont son propre délai de rétractation — à lire avant d'ouvrir la signature par lien.
4. Réserve de propriété sur des panneaux fixés à une toiture (DOC art. 618-23) ; intérêt de l'inscription au registre.
5. Responsabilité décennale (DOC art. 769) : une installation en toiture est-elle un « ouvrage » au sens de l'article ?
6. Durée de disponibilité des pièces de rechange (31-08 art. 10 et 72-F) : la formule par défaut (« pendant toute la
   durée des garanties ») engage la société.
7. Garde du matériel livré avant la pose : la clause (pertes dues au fait du Client ou à un défaut de surveillance)
   face à l'article 773 du DOC (perte par force majeure avant réception à la charge de l'entrepreneur).
8. Fin anticipée après commande du matériel : conservation du coût du matériel et des travaux réalisés, sur
   justificatifs.
9. Mentions de la société sur les documents (loi 5-96, ICE) : règle exacte non retrouvée dans un texte (N).
10. Taux légal d'intérêt en vigueur (DOC art. 875) : non trouvé (N) — sans objet tant qu'aucun intérêt n'est stipulé.
11. Réception refusée ou non cochée (revue 1, 25/11/2026) : le contrat demande au Client qui refuse de signer le
    procès-verbal d'indiquer par écrit, dans les sept jours qui suivent la mise en service, les défauts qui motivent
    son refus, puis permet à la société de le mettre en demeure de recevoir les travaux (DOC art. 774) ; le
    procès-verbal dit qu'une signature sans case cochée vaut réception sans réserve. Ces deux règles tiennent-elles
    face aux articles 768, 771 et 774 du DOC et à l'article 9 de la loi 31-08 (le doute profite au consommateur) ?
12. Délai d'exécution suspendu pendant l'attente de la réponse du gestionnaire du réseau, lorsque son accord est
    requis avant les travaux (loi 82-21) — revue 1, 25/11/2026 : cette suspension, que la société ne maîtrise pas,
    est-elle compatible avec la date limite écrite et la faculté de résolution des articles 12 à 14 de la loi 31-08 ?
13. **Retraits décidés par Reda le 24/11/2026** — à faire confirmer : le contrat ne dit plus quel texte l'emporte
    en cas de contradiction entre le devis et le contrat (l'interprétation revient alors au droit commun, et pour un
    consommateur à la lecture qui lui est la plus favorable, loi 31-08 art. 9).
14. L'article sur la déclaration au gestionnaire du réseau (loi 82-21) est retiré : le contrat ne dit plus qui
    prépare le dossier ni qui paie les frais du gestionnaire. L'obligation légale du propriétaire ne disparaît pas.
15. L'article « Garde du matériel » ne dit plus qui a la garde pendant la pose : la responsabilité de l'entrepreneur
    sur son ouvrage jusqu'à la réception relève alors du seul Dahir des obligations et des contrats.
16. Garantie conventionnelle : la loi 31-08 énumère les mentions de l'écrit de garantie (obligations du garant,
    démarches et qui les supporte, disponibilité des pièces — § 2 ci-dessus). Les actes ne les portent plus, à la
    demande de Reda : dire si un certificat réduit au tableau des durées, aux exclusions et à la garantie légale
    suffit, ou ce qu'il faut y remettre au minimum.
