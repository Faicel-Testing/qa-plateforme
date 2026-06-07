@ui @id06 @profile @security
Feature: Mise à jour du mot de passe

  Scenario: Id06_PasswordUpdate - Modifier le mot de passe avec succès
    Etant donné que je suis connecté
    Lorsque je suis sur la page Profil
    Lorsque je modifie mon mot de passe avec un nouveau mot de passe valide
    Alors un message de succès s'affiche

  Scenario: Id06_PasswordUpdate - Modifier le mot de passe avec échec
    Etant donné que je suis connecté
    Lorsque je suis sur la page Profil
    Lorsque je modifie mon mot de passe avec un mot de passe actuel incorrect
    Alors un message d'erreur s'affiche
