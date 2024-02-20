# QONTO 2 FEC

## A quoi sert ce projet ?

Génération d'un fichier comptable au format FEC directement depuis les transactions du compte pro sous Qonto.

## Dans quel état est le code sur ce dépôt ?

Fonctionnel mais toujours en cours de développement.
Ce code est utilisé pour générer les écritures pour mon expert comptable.

En pratique, je développe les différents cas dont j'ai besoin au fur et à mesure qu'il se présente à moi.
Les regles de ce dépôts correspondent donc aux opérations que j'ai réalisé, pas plus.

Les principales limites :
 - Ecritures automatiques pour la fin d'un exercice non supportées à 100%
 - Bascule d'exercice non développé
 - Gestion des immobilisations non développé
 - Vente sans TVA non supporté
 - Gestion des engagements sans ligne en banque non supporté (facture émises non payées, factures fournisseurs reçue non payée)
 - Pas de gestion de prévisionnel (budget prévisionnel et suivi)

## Comment l'utiliser ?

1 - Créer un fichier .env avec les valeurs suivantes :

company-siren=xxx
qonto-api-key=xxx-xxx-xxx
qonto-api-slug=xx-xx
qonto-api-iban=FRxx
accounting-period-start-date=202x-xx-xx
accounting-period-end-date=202x-xx-xx

2 - Créer vos compte analytique de suivi comptable dans Qonto (labels)

3 - Paramétrer votre plan comptable dans config/accounting_plan.cfg

4 - Adapter les règles comptables pour votre société dans la méthode apply_accouting_rules de la classe fec_accounting.py

5 - Exécuter le main.py

Si vous aimez ce projet et qu'il peut vous être utile ou si vous souhaitez me dire "merci".

Voici mon lien de parainage Qonto : https://qonto.com/r/crajqe

## Pourquoi tu as développé ça ? 

J'ai créé ma société en 2023 (EURL à l'IS) et je souhaitais réaliser ma comptabilité par moi-même.

J'ai d'abord penser prendre un logiciel comptable et faire mes saisies.

Mais je me suis rendu compte que mon expert comptable, tout comme l'administration fiscale, ne souhaitait que deux choses à la fin de l'exercice :
 - Un fichier FEC
 - Les justificatifs certifiés

J'ai donc décidé de :
 - Prendre comme banque Qonto car l'API est très simple d'utilisation et le prix des services modéré
 - Utiliser qonto pour mes justificatifs et factures car leur système est à valeur probante et très ergonomique
 - Déclarer seul ma TVA (mensuelle CA3)
 - Prendre un expert comptable pour une mission de contrôle et certification des comptes en fin d'exercice (pour relecture)
 - Ne pas prendre de logiciel comptable et réaliser par moi-même un fichier FEC via un code en python
 - Documenter et partager ma solution (ce dépôt de code)
 - Une fois la solution robuste, la faire connaître

 Ainsi, ce programme vous permet, depuis votre compte qonto de :
 - récupérer les valeurs pour votre déclaration mensuelle de TVA
 - réaliser automatiquement votre compta (format FEC) comme les cabinets comptables qui utilisent des logiciels de pré-comptabilités avec leur client. Sauf qu'ici, vous savez ce qu'il se passe sous le capot si vous le souhaitez ;o)

Je précise que je n'ai pas fait ce travail pour faire des économies mais bien pour apprendre et que j'avais quelques bases en comptabilité.

C'est un projet sérieux, utilisé au quotidien pour mon entreprise mais qui vise la simplicité avant la généricité pour être adaptable à toutes les sociétés.

Le résultat sera contrôlé et certifié par mon expert comptable début 2025.

Le fichier FEC a été validé avec :
 - (FEC Expert)[https://www.fec-expert.fr/]
 - (Compta secure)[https://app.comptasecure.fr/]

Il est conforme à l’(arrêté du 29 Juillet 2013)[http://legifrance.gouv.fr/eli/arrete/2013/7/29/BUDE1315492A/jo/texte] portant modification des dispositions de l’article A. 47 A-1 du livre des procédures fiscales.
Cet arrêté prévoit l’obligation pour les sociétés ayant une comptabilité informatisée de pouvoir fournir à l’administration fiscale un fichier regroupant l’ensemble des écritures comptables de l’exercice. Le format de ce fichier, appelé FEC, est définit dans l’arrêté. Le détail du format du FEC est spécifié dans le bulletin officiel des finances publiques (BOI-CF-IOR-60-40-20-2013121)[https://bofip.impots.gouv.fr/bofip/9028-PGP.html/identifiant%3DBOI-CF-IOR-60-40-20-20131213]

## Comment ca marche ?

Le logiciel extrait les opérations bancaires depuis l'API de qonto.
A partir de là, il reconstitue toutes les écritures à partir de règles.

## Notice pour l'administration fiscale

Lors d'un contrôle, le fichier FEC doit être accompagné d’une notice explicative qui doit comporter toutes les informations nécessaires à la bonne compréhension des codifications utilisées.
Cette notice sera réalisé lors de mon premier bilan.

## Cas particulier - Les déclarations de TVA

Sous qonto, quand la TVA est prélevée, j'ajoute sur la transaction une note au format suivant pour comptabiliser la déclaration et le paiement :

TVAchapitredeclaration:valeur
```
TVA08:xxx
TVA20:xxx
TVA22:xxx
```

Le chapitre 08 débite le compte 44571 "TVA collectée 20%".
Le chapitre 20 + 22 crédite les comptes 445661 "TVA déductible sur autres biens et services"

## Immobilisations

Non supporté pour le moment
