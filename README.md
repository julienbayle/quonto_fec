# QONTO FEC


Créer un fichier FEC directement depuis l'API Qonto, des labels sur les écritures et un fichier de règles.

L'objectif de ce projet est de ne pas avoir de comptabilité mais de réaliser directement le fichier FEC à destination de l'expert comptable depuis la pré-comptabilité réalisée sous Qonto.

Comment ca marche ?
-------------------

Le logiciel extrait les opérations bancaires depuis l'API de qonto.
A partir de là, il reconstitue le journal 


JournalCode : Code journal de l’écriture comptable (Voir notice)
JournalLib : Libellé journal de l’écriture comptable (Voir notice)
EcritureNum : Numéro sur une séquence continue de l’écriture comptable (automatique)
EcritureDate : Date de comptabilisation de l’écriture comptable (Utilisation du jour de saisie de la pièce comptable si elle existe, le jour de l'opération bancaire sinon)
CompteNum : Numéro de compte (Respect du plan de comptable général - Réglement de l'autorité des normes comptables N°2023-03)
CompteLib : Libellé de compte (Respect du plan de comptable général - Réglement de l'autorité des normes comptables N°2023-03)
CompAuxNum : Numéro de compte auxiliaire (non utilisé)
CompAuxLib: Libellé de compte auxiliaire (non utilisé)
PieceRef : Référence de la pièce justificative (Récupéré de l'API Quonto)
PieceDate : Date de la pièce justificative (Récupéré de l'API Quonto)
EcritureLib : Libellé de l'écriture comptable (Récupére du champs note Qonto)
Debit : Montant au débit
Crédit : Montant au crédit
EcritureLet : Lettrage de l’écriture (automatique)
DateLet : Date de lettrage (automatique)
ValidDate : Date de validation de l'écriture (automatique)
Montantdevise : Montant en devise (non utilisé)
Idevise : Identifiant de la devise (non utilisé)
DateRglt : Date de règlement
ModeRglt : Mode de règlement
NatOp : Nature de l’opération
IdClient : Identification du client

Limites
-------

Pas de gestion des comptes de tiers
Pas de gestion d'une caisse (argent liquide)
Pas de gestion de stocks ou d'en cours
Pas de gestion des comptes auxiliaires
Uniquement Euro (pas de gestion multi devises)
Comptabilité d'engagement (non compatible avec entreprises agricoles ou au BNC)

Notice pour l'administration fiscale
------------------------------------

Lors d'un contrôle, le fichier FEC doit être accompagné d’une notice explicative qui doit comporter toutes les informations nécessaires à la bonne compréhension des codifications utilisées.
Voici la notice pour ce projet :

Journaux utilisés :
* OD : Operations diverses
* VE : Ventes,
* AC : Achats,
* BQ : Banque (supporte un seul compte pour toute l'entreprise, 1 seul fichier journal de banque),
* TR : Tresorerie,
* CA : Caisse (non supporté dans cette version du logiciel)

Numérotation des pièces justificatives ?

Déclaration de TVA
------------------

La date de validation des écritures comptables doit être avant la date de déclaration de la TVA de chaque mois.
Input : Fichier des déclarations de TVA réalisée
Output : Prochaine déclaration de TVA

Validation du fichier FEC
-------------------------

Le fichier généré a été validé avec :
