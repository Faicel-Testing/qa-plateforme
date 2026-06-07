# Spécification — Mise à jour du profil utilisateur

_Reformulé à partir des user stories extraites par spec-agent_
_Tickets Jira : SCRUM-18, SCRUM-19, SCRUM-20_

---

## [Id06] Mise à jour du mot de passe
**Jira :** [SCRUM-18](https://kaysganem.atlassian.net/browse/SCRUM-18) | **Priorité :** High
**Feature :** `src/features/Id06_PasswordUpdate.feature`

> En tant qu'utilisateur connecté,
> je veux modifier mon mot de passe,
> afin de sécuriser mon compte.

### Critères d'acceptation

**Scénario positif — Modifier le mot de passe avec succès**
- Etant donné que je suis connecté
- Lorsque je suis sur la page Profil
- Lorsque je modifie mon mot de passe avec un nouveau mot de passe valide
- Alors un message de succès s'affiche

**Scénario négatif — Modifier le mot de passe avec échec**
- Etant donné que je suis connecté
- Lorsque je suis sur la page Profil
- Lorsque je modifie mon mot de passe avec un mot de passe actuel incorrect
- Alors un message d'erreur s'affiche

### Règles métier
- Le mot de passe actuel est obligatoire pour confirmer le changement
- Le nouveau mot de passe doit contenir minimum 8 caractères
- Tags : `@ui @id06 @profile @security`

---

## [Id07] Mise à jour de l'email
**Jira :** [SCRUM-19](https://kaysganem.atlassian.net/browse/SCRUM-19) | **Priorité :** Medium
**Feature :** `src/features/Id07_EmailUpdate.feature`

> En tant qu'utilisateur connecté,
> je veux modifier mon adresse email,
> afin de mettre à jour mes informations de contact.

### Critères d'acceptation

**Scénario positif — Modifier l'email avec succès**
- Etant donné que je suis connecté
- Lorsque je suis sur la page Profil
- Lorsque je modifie mon email avec une adresse valide
- Alors un email de confirmation est envoyé à la nouvelle adresse

**Scénario négatif — Modifier l'email avec échec**
- Etant donné que je suis connecté
- Lorsque je suis sur la page Profil
- Lorsque je modifie mon email avec une adresse déjà utilisée
- Alors un message d'erreur s'affiche

### Règles métier
- L'email doit respecter le format standard (ex: user@domain.com)
- Un email déjà associé à un autre compte est refusé
- Tags : `@ui @id07 @profile @contact`

---

## [Id08] Suppression du compte
**Jira :** [SCRUM-20](https://kaysganem.atlassian.net/browse/SCRUM-20) | **Priorité :** Highest
**Feature :** `src/features/Id08_AccountDeletion.feature`

> En tant qu'utilisateur connecté,
> je veux supprimer mon compte,
> afin d'effacer mes données personnelles.

### Critères d'acceptation

**Scénario positif — Supprimer le compte avec succès**
- Etant donné que je suis connecté
- Lorsque je suis sur la page Profil
- Lorsque je confirme la suppression de mon compte
- Alors je suis redirigé vers la page d'accueil

**Scénario négatif — Annuler la suppression**
- Etant donné que je suis connecté
- Lorsque je suis sur la page Profil
- Lorsque je ne confirme pas la suppression de mon compte
- Alors la suppression est annulée

### Règles métier
- Une confirmation explicite est requise avant toute suppression
- Toutes les données de l'utilisateur sont effacées après suppression
- Tags : `@ui @id08 @profile @security`

---

## Traçabilité

| ID | Titre | Jira | Feature | Priorité |
|----|-------|------|---------|----------|
| Id06 | Mise à jour du mot de passe | [SCRUM-18](https://kaysganem.atlassian.net/browse/SCRUM-18) | Id06_PasswordUpdate.feature | High |
| Id07 | Mise à jour de l'email | [SCRUM-19](https://kaysganem.atlassian.net/browse/SCRUM-19) | Id07_EmailUpdate.feature | Medium |
| Id08 | Suppression du compte | [SCRUM-20](https://kaysganem.atlassian.net/browse/SCRUM-20) | Id08_AccountDeletion.feature | Highest |
