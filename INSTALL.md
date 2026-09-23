# Installation du hook — et surtout, comment l'enlever

Poser un hook `Stop` touche **toutes** tes sessions. Donc le retrait vient en premier :
on n'installe pas un mécanisme de blocage sans savoir l'arrêter.

---

## 1. LE RETRAIT — à lire avant d'installer

Ouvre `%USERPROFILE%\.claude\settings.json` et **supprime le bloc qui contient
`claimcheck.py`** dans `hooks.Stop`. C'est tout : rien d'autre n'est modifié sur la machine,
aucun service, aucune tâche planifiée, aucune clé de registre.

Si tu veux couper sans éditer le JSON : **renomme le dossier `claimcheck`**. La commande
échoue, le hook ne rend rien, et Claude Code continue normalement — c'est prévu (voir §4).

Vérifier que c'est bien parti :

```
py -c "import json,io;d=json.load(io.open(r'%USERPROFILE%\.claude\settings.json',encoding='utf-8'));print('claimcheck present :', 'claimcheck' in json.dumps(d))"
```

---

## 2. Le bloc à ajouter

Dans `hooks.Stop`, **en plus** de ce qui s'y trouve déjà (un tableau accepte plusieurs
entrées, l'existant n'est pas remplacé) :

```json
{
  "hooks": [
    {
      "type": "command",
      "command": "py \"C:\\chemin\\vers\\claimcheck\\claimcheck.py\" --hook"
    }
  ]
}
```

> ⚠️ **`py`, pas `python`.** Sur cette machine, `python` résout via le PATH vers le venv d'un
> ancien projet. Le jour où ce dossier disparaît, le hook meurt **sans aucune
> erreur visible** : plus rien n'est vérifié et rien ne le dit. `py` est le lanceur Windows,
> il ne dépend d'aucun venv. Mesuré le 18/09 : même sortie avec les deux.

**Testé, pas supposé** : cette commande a été lancée **via bash**, comme Claude Code le fait,
et elle rend bien `{"decision": "block", ...}` sur un compte-rendu faux.

> ⚠️ **Le piège du `$`, et pourquoi il ne s'applique PAS ici.** Sur cette machine, les hooks
> PowerShell ont dû voir leurs `$` échappés en `\$` parce que Claude Code passe la commande à
> **bash**, qui les mange. Cette commande-ci **ne contient aucun `$`**, donc rien à échapper.
> Vérifié en la lançant, pas déduit.

L'installation a été répétée sur une **copie** de `settings.json` : le fichier reste du JSON
valide, le hook mémoire existant est intact, et le nombre d'entrées `Stop` passe de 1 à 2.

---

## 3. Vérifier que c'est posé, sans attendre un blocage

Ne compte pas sur « je verrai bien quand ça bloquera » : si le hook est mal posé, tu ne verras
jamais rien et tu croiras qu'il veille. Force le cas :

```
cd C:\chemin\vers\claimcheck
py check_all.py
```

Attendu : `TOUT PASSE`, code de retour 0. Ce banc rejoue le hook sur un faux
compte-rendu et vérifie qu'il bloque.

Pour tester la commande *exactement comme Claude Code la lance*, depuis ce dossier.
`exemple-tour.jsonl` est un tour réel minimal : pytest y a rendu `162 passed`.

```
echo {"hook_event_name":"Stop","last_assistant_message":"J'ai lance : 170 tests verts.","transcript_path":"exemple-tour.jsonl"} | bash -c "py \"C:\\chemin\\vers\\claimcheck\\claimcheck.py\" --hook"
```

Un JSON `block` en sortie = le hook fonctionne. Avec `162 tests verts` (la vérité), rien ne
sort. ⚠️ Il faut un transcript qui porte une sortie de lanceur : sans preuve, le hook ne
bloque jamais, c'est voulu (« preuve absente » n'est pas « faux »). L'ancienne version de ce
test passait un chemin fictif et ne pouvait donc **jamais** bloquer.

---

## 4. Ce qui se passe au premier blocage

L'agent finit son tour, le hook lit son message final, trouve une affirmation **contredite par
une sortie d'outil du même tour**, et **empêche l'arrêt**. L'agent repart avec la raison :
la liste des affirmations réfutées et la sortie brute qui les contredit.

Ce n'est pas une erreur, ce n'est pas un plantage. C'est le comportement voulu.

**Ce qui ne bloquera jamais :**

- une intention (« je vais pousser les 9 dépôts ») — c'est un plan, pas un compte-rendu ;
- une affirmation sans preuve dans le tour — « je n'ai pas pu regarder » n'est pas
  « c'est faux » ;
- une affirmation dont le référent est indéterminé (« 0 fail » quand plusieurs lanceurs ont
  tourné et que certains ont échoué, par exemple des mutations volontaires ; un total de
  tests face au seul lanceur d'une suite deux fois plus grande ou plus petite) ;
- **rien du tout en cas de problème** : transcript absent, JSON cassé, stdin vide, chemin
  accentué. Toutes ces situations rendent un silence. Un hook qui plante à chaque fin de tour
  se fait désinstaller le jour même, et alors plus rien n'est vérifié.

**Coût mesuré : 0,10 s** sur un transcript de 4 000 sorties d'outil, **0,17 s** sur une
session de 111 Mo (le hook n'en lit que les 8 derniers Mo). Le hook ne
relance aucune commande — il cherche la preuve déjà produite.

---

## 5. Si un blocage te paraît injustifié

C'est le défaut le plus grave possible pour cet outil, et il doit remonter, pas être toléré.
La sortie contient toujours l'affirmation en cause et la preuve opposée : les deux suffisent à
trancher. Ajoute le cas dans `test_mutation.py` comme **témoin** (il doit passer), puis
corrige — c'est ainsi que les deux erreurs d'unité de la v1 ont été trouvées.
