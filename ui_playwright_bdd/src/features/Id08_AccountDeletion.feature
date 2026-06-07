@ui @id08 @profile @security
Feature: Suppression du compte

  Scenario: Id08_AccountDeletion - Supprimer le compte avec succès
    Etant donné que je suis connecté
    Lorsque je suis sur la page Profil
    Lorsque je confirme la suppression de mon compte
    Alors je suis redirigé vers la page d'accueil

  Scenario: Id08_AccountDeletion - Supprimer le compte avec échec
    Etant donné que je suis connecté
    Lorsque je suis sur la page Profil
    Lorsque je ne confirme pas la suppression de mon compte
    Alors la suppression est annulée
