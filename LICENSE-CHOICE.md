# Choix de licence — motif écrit, rien de signé

**Décision d'Alex.** Ce fichier documente le raisonnement pour qu'il n'ait pas à le refaire ;
il ne vaut pas signature et aucun fichier `LICENSE` n'a été posé.

## Ce qui est EXCLU, et pourquoi

**BSL 1.1 — écartée.** C'est la licence de TruthGuard, le seul outil comparable trouvé.
Elle interdit explicitement de bâtir un produit de vérification concurrent, et bascule en MIT
en mars 2030. Deux raisons de ne pas la reprendre :

1. **Elle a mesurablement échoué à son objet.** TruthGuard a deux étoiles. Une licence qui
   repousse les contributeurs sur un outil dont toute la valeur est l'adoption est un
   auto-sabotage de distribution, pas une protection.
2. **Symétrie.** On ne peut pas reprocher à un concurrent d'interdire la concurrence et faire
   pareil.

## Les deux options réelles

| | MIT | Apache-2.0 |
|---|---|---|
| Longueur | ~170 mots | ~10 000 mots |
| Clause brevets | aucune | oui, concession explicite + révocation en cas de litige |
| Attribution requise | oui | oui |
| Adoption en entreprise | très large | très large, préférée quand des brevets sont en jeu |
| Compatible avec le reste du portefeuille | à vérifier | à vérifier |

## Recommandation : **MIT**

- Le projet **n'a aucune surface brevetable** : des expressions régulières, une lecture de
  JSON, aucune invention d'algorithme. La clause brevets d'Apache protège contre un risque
  qui n'existe pas ici.
- Sa valeur est l'**adoption**, et MIT est le plus court chemin vers un `pip install` sans
  qu'un service juridique ait à lire quoi que ce soit.
- Le README porte déjà les garde-fous qui comptent (le plafond annoncé, la couverture
  affichée) — ce sont eux qui protègent la réputation de l'outil, pas la licence.

## Ce qui reste à faire, et qui n'est pas de mon ressort
- déposer le fichier `LICENSE` avec le nom et l'année ;
- décider si le dépôt devient public.
