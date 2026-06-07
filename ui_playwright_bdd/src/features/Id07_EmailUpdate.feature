@ui @id07 @profile @contact
Feature: Mise à jour de l'email

  Scenario: Id07_EmailUpdate - Modifier l'email avec succès
    Etant donné que je suis connecté
    Lorsque je suis sur la page Profil
    Lorsque je modifie mon email avec une adresse valide
    Alors un email de confirmation est envoyé à la nouvelle adresse

  Scenario: Id07_EmailUpdate - Modifier l'email avec échec
    Etant donné que je suis connecté
    Lorsque je suis sur la page Profil
    Lorsque je modifie mon email avec une adresse déjà utilisée
    Alors un message d'erreur s'affiche
