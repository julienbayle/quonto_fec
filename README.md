# QONTO TO FEC

## A quoi sert ce projet ?

Génération d'un fichier comptable au format FEC directement depuis les transactions de votre compte pro sous Qonto
accompagné de quelques écritures manuelles complémentaire pour le bilan (opérations diverses, ventes non encaissées, factures à recevoir)

Il aide également à réaliser les déclarations de TVA mensuelles avec un affichage des balances par mois.

## Quel est l'avancement de ce projet ?

Fonctionnel mais toujours en cours de développement.
Ce code est utilisé pour générer les écritures pour mon expert comptable chaque année.

En pratique, je développe les différents cas dont j'ai besoin au fur et à mesure des besoins de ma société.
Les regles comptables en places dans ce projet correspondent donc aux opérations que j'ai déjà réalisé, pas plus.

## Comment l'utiliser ?

1 - Créer un fichier .env avec les valeurs suivantes :

company-siren=xxx
qonto-api-key=xxx-xxx-xxx
qonto-api-slug=xx-xx
qonto-api-iban=FRxx
accounting-period-start-date=202x-xx-xx
accounting-period-end-date=202x-xx-xx

2 - Créer vos compte de suivi comptable dans Qonto (labels)

3 - Paramétrer votre plan comptable dans config/accounting.cfg

4 - Adapter les règles comptables pour votre société dans la méthode *doAccounting* du fichier *accounting.py*

5 - Exécuter le main.py

Si vous aimez ce projet et qu'il peut vous être utile ou si vous souhaitez me dire "merci".
Voici mon [lien de parainage Qonto](https://qonto.com/r/crajqe)

## Pourquoi avoir développer ce projet ?

J'ai créé ma société en 2023 (EURL à l'IS) et je souhaitais réaliser ma comptabilité par moi-même.

J'ai d'abord penser prendre un logiciel comptable et faire mes saisies.

Mais je me suis rendu compte que mon expert comptable, tout comme l'administration fiscale, ne souhaitait que deux choses à la fin de l'exercice :

- Un fichier FEC
- Des justificatifs certifiés

J'ai donc décidé de :

- Prendre comme banque Qonto car l'API est très simple d'utilisation et le prix des services modéré
- Utiliser Qonto pour mes justificatifs et factures car leur système est à valeur probante et très ergonomique
- Déclarer seul ma TVA (mensuelle CA3)
- Prendre un expert comptable pour une mission de contrôle et certification des comptes en fin d'exercice
- Ne pas prendre de logiciel comptable et réaliser par moi-même un fichier FEC via un code en python
- Documenter et partager ma solution pour tous (ce dépôt de code)
- Une fois la solution robuste, au bout de quelques années, la faire connaître

Ainsi, ce programme vous permet, à partir de votre compte qonto de réaliser automatiquement votre compta (format FEC)
comme les cabinets comptables qui utilisent des logiciels de pré-comptabilités avec leur client.
Sauf qu'ici, vous savez ce qu'il se passe sous le capot.

Je précise que je n'ai pas fait ce travail pour faire des économies mais bien pour apprendre et réaliser ma comptabilité.

C'est un projet sérieux, utilisé au quotidien pour mon entreprise mais qui vise la simplicité pour mes besoins
avant la généricité et être adaptable à toutes les sociétés.

Le fichier FEC généré a été validé avec :

- [FEC Expert](https://www.fec-expert.fr/)
- [Compta secure](https://app.comptasecure.fr/)
- [SmartFEC](https://smartfec-plus.cncc.fr/)

Il est conforme à l’[arrêté du 29 Juillet 2013](http://legifrance.gouv.fr/eli/arrete/2013/7/29/BUDE1315492A/jo/texte) portant modification des dispositions de l’article A. 47 A-1 du livre des procédures fiscales.
Cet arrêté prévoit l’obligation pour les sociétés ayant une comptabilité informatisée de pouvoir fournir à l’administration fiscale un fichier regroupant l’ensemble des écritures comptables de l’exercice.
Le format de ce fichier, appelé FEC, est définit dans l’arrêté.

Le détail du format du FEC est spécifié dans le bulletin officiel des finances publiques [BOI-CF-IOR-60-40-20-2013121](https://bofip.impots.gouv.fr/bofip/9028-PGP.html/identifiant%3DBOI-CF-IOR-60-40-20-20131213)

## Comment ca marche ?

Le logiciel extrait les opérations bancaires depuis l'API de qonto.
A partir de là, il reconstitue toutes les écritures à partir de règles.
Il complète le fichier FEC avec les écritures manuelles complémentaires.

## Notice pour l'administration fiscale

Lors d'un contrôle, le fichier FEC doit être accompagné d’une notice explicative qui doit comporter toutes les informations nécessaires à la bonne compréhension des codifications utilisées.
Ce code vaut notice de mon point de vue pour ma société.

## Cas particulier - Les déclarations de TVA

Sous qonto, quand la TVA est prélevée, j'ajoute sur la transaction une note au format suivant pour comptabiliser la déclaration et le paiement : TVA*chapitredeclaration*:*montant*

Exemple
> TVA08:1200
> TVA20:200
> TVA22:100

Le chapitre 08 débite le compte 44571 "TVA collectée 20%".
Le chapitre 20 et 22 crédite les comptes 445661 "TVA déductible sur autres biens et services"

## Cas particulier - Indemnité kilométrique et frais mensuels

Je ne me rembourse pas directement mes frais mais je les inscrits mensuellement sur mon compte courrant d'associé.
Pour celà, le ficher config/journal.cfg répertorie tous les OD de frais mensuelle

Le format est le suivant (séparateur tabulation):
date compte de charge montant description

## Immobilisations

Non supporté pour le moment car je n'en ai pas encore fait
