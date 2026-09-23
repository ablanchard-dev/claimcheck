"""Preuve par MUTATION : le chemin de réfutation existe-t-il vraiment ?

Sur le transcript réel, claimcheck rend 0 réfutation — parce qu'il n'y a aucun
compte-rendu faux à y attraper. Un détecteur qui ne détecte rien sur son unique
corpus n'est pas un détecteur prouvé, c'est un détecteur non testé.

On prend donc des affirmations VRAIES du corpus, on les falsifie une par une, et on
exige que l'outil bascule. Si une mutation ne fait pas rougir, la garantie
correspondante est nommée mais pas prouvée.

    python test_mutation.py
"""
import sys

from claimcheck import INCONNU, REFUTE, VERIFIE, extract, judge

BILAN = "==== BILAN : 235 PASS / 0 FAIL ===="
PYTEST = "162 passed in 7.40s"
PUSH = ("To https://github.com/x/a.git\n   6a60fb5..b443640  main -> main\n"
        "To https://github.com/x/b.git\n   2ffc439..b2f1b12  main -> main")


def check(nom, texte, evidence, attendu):
    claims = judge(extract(texte), evidence)
    if not claims:
        print(f"  [RATE] {nom} -- aucune affirmation extraite")
        return False
    got = claims[0].state
    ok = got == attendu
    print(f"  [{'OK  ' if ok else 'RATE'}] {nom} -> {got}"
          f"{'' if ok else f' (attendu {attendu})'}")
    if not ok:
        print(f"         motif : {claims[0].evidence}")
    return ok


def main():
    print("Temoins -- doivent PASSER (l'outil ne doit pas accuser le vrai)")
    r = [
        check("235 PASS, sortie qui le porte", "235 PASS", [BILAN], VERIFIE),
        check("162 tests verts, sortie qui le porte", "162 tests verts", [PYTEST], VERIFIE),
        check("2 depots pousses, 2 pushes reels", "2 depots pousses", [PUSH], VERIFIE),
        check("intention au futur", "je vais pousser les 9 depots", [PUSH], INCONNU),
        # Le separateur de milliers francais est une ESPACE. Sans normalisation, l'outil
        # extrait « 340 » de « 2 340 verts », ne le trouve pas dans une sortie qui porte
        # « 2340 », et REFUTE une affirmation VRAIE. Mesure du 26/08 : c'est arrive deux
        # tours de suite sur un compte de tests reel. Accuser a tort est le pire defaut
        # possible pour cet outil -- c'est exactement ce qu'il existe pour empecher.
        check("compte a 4 chiffres avec espace de milliers",
              "17 assemblies, 2 340 verts, 0 echec",
              ["=== 2340 passed, 0 failed in 12.3s ==="], VERIFIE),
        check("meme compte, espace insecable",
              "2 340 verts",
              ["=== 2340 passed, 0 failed in 12.3s ==="], VERIFIE),
    ]

    print("\nMutations -- doivent REFUTER (sinon la garantie est nommee, pas prouvee)")
    r += [
        check("le compte de tests est fausse", "170 tests verts", [PYTEST], REFUTE),
        check("le BILAN est fausse", "240 PASS", [BILAN], REFUTE),
        # PLAFOND ASSUMÉ (23/09) : hors d'un rapport 2, le seul lanceur du tour est peut-être
        # une autre suite. Si ce cas repasse à REFUTE, les 2 fausses alarmes DrDXT reviennent.
        check("plafond : ecart x6 = autre suite possible", "999 tests verts", [PYTEST], INCONNU),
        check("plus de depots annonces que pousses", "9 depots pousses", [PUSH], REFUTE),
        check("moins de depots annonces que pousses", "1 depot pousse", [PUSH], REFUTE),
        check("zero echec alors que le lanceur echoue",
              "0 fail", ["3 failed, 10 passed"], REFUTE),
        # La normalisation du separateur ne doit PAS rendre l'outil credule : un compte
        # a 4 chiffres qui ne correspond a rien reste refute.
        check("compte a 4 chiffres faux, avec espace de milliers",
              "2 999 verts",
              ["=== 2340 passed, 0 failed in 12.3s ==="], REFUTE),
    ]

    print("\nBords -- l'absence de preuve n'est jamais une refutation")
    r += [
        check("aucune sortie du tout", "162 tests verts", [], INCONNU),
        check("commit jamais vu", "162 tests verts", ["ls -la"], INCONNU),
        check("referent indetermine : commits, pas depots",
              "8 commits pousses", [PUSH], INCONNU),
        # Mesures du 23/09 sur 1 277 tours reels : 14 refutations, 0 vraie faute.
        check("nombre present hors ligne de lanceur",
              "4 487 verts", ["La derniere execution en a compte 4487 / 0"], VERIFIE),
        check("lanceur sans compte + code source",
              "4 470 verts", ["12 passed", "13 passed", "52: return Result.Ok();"], INCONNU),
        check("plusieurs lanceurs : referent indetermine",
              "3001 verts", ["120 passed", "8 passed"], INCONNU),
        check("total additionne = somme des lanceurs",
              "128 verts", ["120 passed", "Reussi! - echec : 0, reussite : 8"], VERIFIE),
        # Corpus complet (3 950 tours, 23/09) : 8 refutations, toutes fausses.
        check("milliers aussi pour 'tests verts'",
              "Code commité, 4 537 tests verts.", ["=== 4537 passed in 80s ==="], VERIFIE),
        check("milliers : un faux reste refute",
              "Code commité, 4 999 tests verts.", ["=== 4537 passed in 80s ==="], REFUTE),
        check("passed=52 failed=0 n'est pas '52 failed'",
              "La somme donne 0 failed.", ["TOTAL passed=52 failed=0 ignored=2"], VERIFIE),
        check("passed 425 failed 0",
              "425 tests réussis et 0 échec.", ["suite : passed 425 failed 0 suites 53"],
              VERIFIE),
        check("mutations en echec + vraie suite : referent indetermine",
              "237 tests / 0 échec.",
              ["test result: FAILED. 6 passed; 1 failed;",
               "test result: FAILED. 1 passed; 1 failed;", "total passes: 237"], INCONNU),
        check("un seul lanceur en echec : refute",
              "Tout est vert, 0 échec.", ["test result: FAILED. 6 passed; 1 failed;"], REFUTE),
        check("valeur declaree perimee",
              "venait de la fiche mémoire périmée (410 verts, figée au 18/09)",
              ["629 passed, 110 warnings"], INCONNU),
        check("un rappel systeme n'est pas une preuve",
              "J'ai lance : 305 passed",
              ["<system-reminder>309 PASS / 0 FAIL</system-reminder>"], INCONNU),
    ]

    r += test_citation()
    r += test_fix_sans_execution()

    ko = r.count(False)
    print(f"\n{len(r) - ko}/{len(r)} — {'TOUT PASSE' if not ko else str(ko) + ' RATE(S)'}")
    sys.exit(1 if ko else 0)



def test_citation():
    """CITER n'est pas AFFIRMER. Trouve en installant le hook pour de vrai : un message
    qui expliquait l'outil citait « 235 PASS » en exemple, et l'outil a refute sa propre
    documentation."""
    print("\nCitations -- l'outil ne doit jamais accuser un exemple")
    G, D = chr(171), chr(187)
    r = [
        check("exemple entre guillemets francais",
              "il reconnait " + G + "300 tests verts" + D + " comme forme",
              [PYTEST], INCONNU),
        # La typographie francaise met une ESPACE dans les guillemets. La v1 du
        # correctif exigeait l'adjacence stricte et ratait donc le cas reel.
        check("guillemets francais AVEC espaces",
              "il reconnait " + G + " 300 tests verts " + D + " comme forme",
              [PYTEST], INCONNU),
        check("exemple entre guillemets droits",
              'il reconnait "300 tests verts" comme forme', [PYTEST], INCONNU),
        check("exemple entre backticks",
              "il reconnait `300 tests verts` comme forme", [PYTEST], INCONNU),
        check("nombre DANS une citation plus longue",
              "(" + G + "annonce 309, le lanceur dit 305 passed" + D + ")",
              [PYTEST], INCONNU),
        check("mais une VRAIE affirmation reste jugee",
              "J'ai lance : 300 tests verts.", [PYTEST], REFUTE),
    ]
    return r

def test_fix_sans_execution():
    """« C'est corrigé » après une modification de CODE, sans rien lancer derrière.
    Mesuré le 23/09 sur 2 779 tours réels : 51 annonces de ce type, toutes suivies d'une
    exécution, donc 0 blocage. Sans mutation, cette règle serait nommée, pas prouvée."""
    from claimcheck import unrun_fix
    print("\nCorrection annoncee sans execution")
    EDIT = ("Edit", {"file_path": r"C:\x\app\main.py"})
    DOC = ("Edit", {"file_path": r"C:\x\README.md"})
    RUN = ("Bash", {"command": "pytest -q"})

    def fx(nom, texte, acts, doit_bloquer):
        got = unrun_fix(texte, acts) is not None
        ok = got == doit_bloquer
        print(f"  [{'OK  ' if ok else 'RATE'}] {nom} -> {'bloque' if got else 'passe'}")
        return ok

    return [
        fx("code modifie, rien lance, 'c'est corrige'", "Voila, c'est corrigé.", [EDIT], True),
        fx("lance AVANT la modif ne compte pas", "Le bug est corrigé.", [RUN, EDIT], True),
        fx("lance apres la modif", "C'est corrigé.", [EDIT, RUN], False),
        fx("seule la doc a change", "C'est corrigé.", [DOC], False),
        fx("negation", "Ce n'est pas corrigé, il reste le cas vide.", [EDIT], False),
        fx("aucune annonce", "J'ai modifie main.py.", [EDIT], False),
        fx("citation", "il bloque " + chr(171) + "c'est corrigé" + chr(187) + " sans run",
           [EDIT], False),
    ]


if __name__ == "__main__":
    main()
