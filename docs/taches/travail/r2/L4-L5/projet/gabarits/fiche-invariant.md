# Fiche d'invariant — classe `K-<nom>` (une classe de défaut → une garde)

Pourquoi : au run du 19-20/11, la même classe (« une frappe se perd ») est revenue QUATRE fois — en ligne lent, après
un choix, hors ligne, champ non validé — parce que chaque lane corrigeait un symptôme. Une classe se nomme à la
consolidation, s'écrit ici, et se corrige partout à la fois.

- **Invariant** (une phrase, vérifiable) : « <…> »
- **Née de** (ids du registre, tous tours) : <T1-F1-007, T2-S1-003, …>
- **Où il peut être violé** — liste GREPPÉE, pas devinée :
  - commande : `git grep -n "<motif>" <sha> -- <chemins>` (sur la tête de la consolidation)
  - résultat (un endroit par ligne, ancre `fichier::symbole`, état) :
    | Endroit | Viole aujourd'hui ? | Couvert par la garde ? |
    |---|---|---|
  - ce que le grep ne voit pas (autres façons d'écrire le même geste) : <…>
- **Garde** (UNE par classe, dans une famille existante — jamais une par constat : METHODE anti-pattern 15) :
  - type : <test d'invariant dans le module de test existant | test par propriétés | spec e2e | règle de lint |
    garde `scripts/check_*` existante étendue>
  - fichier et nom : `<chemin::nom>` ; écrite par : <test-writer du tour, pas la lane qui corrige>
  - **preuve qu'elle est ROUGE sur le défaut d'origine** : <commit d'origine ou mutant, commande, sortie rouge>
    (L4 : rouge sur la tête avant correction ; L5 : rouge aussi sur le commit qui a introduit le défaut)
  - preuve qu'elle est verte après : <commande, sortie>
- **Propriétaire** : <unité / plan du propriétaire> ; une garde sous `scripts/` = une tâche `[ ]` de son propriétaire
  (elle déclenche les jobs lourds de la CI et exige un propriétaire), jamais glissée dans une PR de documentation.
- **Ce qu'elle ne couvre pas** : <…>
- **Revue** : à la rétro de chaque run L4 / L5 qui touche ce périmètre, et au moins une fois l'an : la garde
  attrape-t-elle encore ? fait-elle du bruit (faux rouges) ? la retirer si l'invariant n'a plus d'objet.
- **Question de sortie** : « le système l'attraperait-il tout seul la prochaine fois ? » — <oui, par … | non, parce que
  … → tâche `[ ]` <id>>
