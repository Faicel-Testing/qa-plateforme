# SauceLabs My Demo App — User Stories

**Projet** : SauceLabs My Demo App (MDA)  
**Date** : 2026-06-12  
**Total** : 28 user stories  


## F-001 — Login

### US-001 — Connexion avec identifiants valides

🔴 **Priority**: High | **Points**: 5 | **Labels**: mobile, android, appium, login

**As a** Utilisateur enregistré  
**I want** Me connecter avec mes identifiants valides  
**So that** J'ai accès à mon compte et à mes informations personnelles  

**Gherkin Scenario:**
```gherkin
Given I am on the login page
When I enter valid username 'bob@example.com' and password '10203040'
Then I should be logged in and see my account dashboard
```

**Acceptance Criteria:**
- L'utilisateur est redirigé vers la page d'accueil après connexion
- Les informations de compte de l'utilisateur sont affichées
- L'utilisateur peut accéder à ses commandes passées
- Le bouton de déconnexion est visible et fonctionnel
- Les erreurs de connexion ne sont pas affichées

### US-002 — Connexion avec mot de passe incorrect

🔴 **Priority**: High | **Points**: 3 | **Labels**: mobile, android, appium, login

**As a** Utilisateur enregistré  
**I want** Essayer de me connecter avec un mot de passe incorrect  
**So that** Je suis informé que mon mot de passe est incorrect  

**Gherkin Scenario:**
```gherkin
Given I am on the login page
When I enter valid username 'bob@example.com' and invalid password 'wrongpassword'
Then I should see an error message indicating that my password is incorrect
```

**Acceptance Criteria:**
- Un message d'erreur est affiché lorsque le mot de passe est incorrect
- L'utilisateur ne peut pas accéder à son compte avec un mot de passe incorrect
- Le bouton de connexion est désactivé après plusieurs tentatives de connexion échouées
- L'utilisateur peut réessayer de se connecter avec un nouveau mot de passe
- Les informations de compte de l'utilisateur ne sont pas modifiées

### US-003 — Connexion avec compte verrouillé

🔴 **Priority**: High | **Points**: 5 | **Labels**: mobile, android, appium, login

**As a** Utilisateur enregistré  
**I want** Essayer de me connecter avec un compte verrouillé  
**So that** Je suis informé que mon compte est verrouillé  

**Gherkin Scenario:**
```gherkin
Given I am on the login page
When I enter valid username 'bob@example.com' and password '10203040' with a locked account
Then I should see an error message indicating that my account is locked
```

**Acceptance Criteria:**
- Un message d'erreur est affiché lorsque le compte est verrouillé
- L'utilisateur ne peut pas accéder à son compte avec un compte verrouillé
- Le bouton de connexion est désactivé après plusieurs tentatives de connexion échouées
- L'utilisateur peut contacter le support pour déverrouiller son compte
- Les informations de compte de l'utilisateur ne sont pas modifiées

### US-004 — Connexion avec champs vides

🟡 **Priority**: Medium | **Points**: 2 | **Labels**: mobile, android, appium, login

**As a** Utilisateur enregistré  
**I want** Essayer de me connecter avec des champs vides  
**So that** Je suis informé que les champs sont obligatoires  

**Gherkin Scenario:**
```gherkin
Given I am on the login page
When I enter empty username and password
Then I should see an error message indicating that the fields are required
```

**Acceptance Criteria:**
- Un message d'erreur est affiché lorsque les champs sont vides
- L'utilisateur ne peut pas accéder à son compte avec des champs vides
- Les champs de connexion sont obligatoires
- L'utilisateur peut remplir les champs pour se connecter
- Les informations de compte de l'utilisateur ne sont pas modifiées

### US-005 — Déconnexion depuis le menu

🟡 **Priority**: Medium | **Points**: 3 | **Labels**: mobile, android, appium, login

**As a** Utilisateur connecté  
**I want** Me déconnecter depuis le menu  
**So that** Je suis déconnecté de mon compte  

**Gherkin Scenario:**
```gherkin
Given I am logged in
When I click on the menu and select 'Logout'
Then I should be logged out and see the login page
```

**Acceptance Criteria:**
- L'utilisateur est déconnecté après avoir cliqué sur 'Logout'
- L'utilisateur est redirigé vers la page de connexion après déconnexion
- Les informations de compte de l'utilisateur ne sont pas accessibles après déconnexion
- L'utilisateur peut se reconnecter avec ses identifiants valides
- Les erreurs de déconnexion ne sont pas affichées


## F-002 — Products Catalog

### US-002-1 — Display product list after login

🟡 **Priority**: Medium | **Points**: 5 | **Labels**: mobile, android, appium, catalog

**As a** logged-in user  
**I want** to see the list of available products  
**So that** I can browse and purchase products  

**Gherkin Scenario:**
```gherkin
Given I am logged in as bob@example.com / 10203040
When I navigate to the products catalog
Then I should see a list of products
```

**Acceptance Criteria:**
- The product list is displayed after successful login
- The product list contains at least 10 products
- Each product has a name, price, and image

### US-002-2 — Sort products by name A-Z

🟡 **Priority**: Medium | **Points**: 3 | **Labels**: mobile, android, appium, catalog

**As a** user browsing the catalog  
**I want** to sort products by name in ascending order  
**So that** I can easily find a specific product  

**Gherkin Scenario:**
```gherkin
Given I am on the products catalog page
When I select the 'Name A-Z' sorting option
Then the products should be sorted in ascending order by name
```

**Acceptance Criteria:**
- The products are sorted in ascending order by name
- The sorting option is visible and accessible
- The sorting option is persistent across page reloads

### US-002-3 — Sort products by price croissant

🟡 **Priority**: Medium | **Points**: 3 | **Labels**: mobile, android, appium, catalog

**As a** user browsing the catalog  
**I want** to sort products by price in ascending order  
**So that** I can find the cheapest products  

**Gherkin Scenario:**
```gherkin
Given I am on the products catalog page
When I select the 'Price' sorting option
Then the products should be sorted in ascending order by price
```

**Acceptance Criteria:**
- The products are sorted in ascending order by price
- The sorting option is visible and accessible
- The sorting option is persistent across page reloads

### US-002-4 — Navigate to product details

🟢 **Priority**: Low | **Points**: 2 | **Labels**: mobile, android, appium, catalog

**As a** user browsing the catalog  
**I want** to navigate to the details page of a product  
**So that** I can view more information about the product  

**Gherkin Scenario:**
```gherkin
Given I am on the products catalog page
When I click on a product
Then I should be taken to the product details page
```

**Acceptance Criteria:**
- The product details page is displayed
- The product details page contains the product name, price, and image
- The product details page has a 'Back' button to return to the catalog


## F-003 — Product Detail

### US-001 — Display Product Details

🟡 **Priority**: Medium | **Points**: 3 | **Labels**: mobile, android, appium, product_detail

**As a** mobile user  
**I want** to view product details such as name, price, description, and image  
**So that** I can make an informed purchasing decision  

**Gherkin Scenario:**
```gherkin
Given I am on the product list page
When I click on a product
Then I should see the product name, price, description, and image
```

**Acceptance Criteria:**
- The product name is displayed correctly
- The product price is displayed correctly
- The product description is displayed correctly
- The product image is displayed correctly

### US-002 — Add Product to Cart from Detail

🟡 **Priority**: Medium | **Points**: 5 | **Labels**: mobile, android, appium, product_detail, cart

**As a** mobile user  
**I want** to add a product to my cart from the product detail page  
**So that** I can purchase the product later  

**Gherkin Scenario:**
```gherkin
Given I am on the product detail page
When I click the add to cart button
Then I should see the product added to my cart
```

**Acceptance Criteria:**
- The product is added to the cart successfully
- The cart count is updated correctly
- The product details are displayed correctly in the cart
- The user is redirected to the cart page after adding the product

### US-003 — Modify Product Quantity Before Adding to Cart

🟡 **Priority**: Medium | **Points**: 5 | **Labels**: mobile, android, appium, product_detail, cart

**As a** mobile user  
**I want** to modify the quantity of a product before adding it to my cart  
**So that** I can purchase the correct quantity of the product  

**Gherkin Scenario:**
```gherkin
Given I am on the product detail page
When I modify the quantity of the product
And I click the add to cart button
Then I should see the product added to my cart with the modified quantity
```

**Acceptance Criteria:**
- The product quantity can be modified correctly
- The modified quantity is reflected in the cart
- The user is redirected to the cart page after adding the product with modified quantity
- The total cost is updated correctly based on the modified quantity


## F-004 — Shopping Cart

### US-001 — Add product to cart from catalogue

🟡 **Priority**: Medium | **Points**: 5 | **Labels**: mobile, android, appium, shopping-cart

**As a** mobile user  
**I want** to add a product to my shopping cart from the catalogue  
**So that** I can purchase the product later  

**Gherkin Scenario:**
```gherkin
Given I am on the catalogue page
When I select a product and click add to cart
Then the product is added to my shopping cart
```

**Acceptance Criteria:**
- The product is displayed in the shopping cart
- The product quantity in the cart is updated correctly
- The cart badge is updated with the correct number of items

### US-002 — Remove product from cart

🟡 **Priority**: Medium | **Points**: 3 | **Labels**: mobile, android, appium, shopping-cart

**As a** mobile user  
**I want** to remove a product from my shopping cart  
**So that** I can update my shopping cart contents  

**Gherkin Scenario:**
```gherkin
Given I have a product in my shopping cart
When I click remove product
Then the product is removed from my shopping cart
```

**Acceptance Criteria:**
- The product is no longer displayed in the shopping cart
- The product quantity in the cart is updated correctly
- The cart badge is updated with the correct number of items

### US-003 — Display empty cart with Go Shopping button

🟢 **Priority**: Low | **Points**: 2 | **Labels**: mobile, android, appium, shopping-cart

**As a** mobile user  
**I want** to see an empty cart with a Go Shopping button  
**So that** I can start shopping when my cart is empty  

**Gherkin Scenario:**
```gherkin
Given my shopping cart is empty
When I navigate to the cart page
Then I see a Go Shopping button
```

**Acceptance Criteria:**
- The cart page displays a message indicating the cart is empty
- The Go Shopping button is visible and clickable
- Clicking the Go Shopping button navigates to the catalogue page

### US-004 — Verify cart badge after adding product

🟡 **Priority**: Medium | **Points**: 2 | **Labels**: mobile, android, appium, shopping-cart

**As a** mobile user  
**I want** to see the correct number of items in my cart badge  
**So that** I can easily track the number of items in my cart  

**Gherkin Scenario:**
```gherkin
Given I have added a product to my shopping cart
When I navigate to the home page
Then the cart badge displays the correct number of items
```

**Acceptance Criteria:**
- The cart badge displays the correct number of items
- The cart badge is updated in real-time after adding or removing products
- The cart badge is visible on all pages


## F-005 — Checkout Address

### US-001 — Valid Address Form Submission

🔴 **Priority**: High | **Points**: 5 | **Labels**: mobile, android, appium, checkout

**As a** mobile shopping user  
**I want** to fill in the address form correctly  
**So that** I can proceed to the payment step  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I fill in the address form with valid data
Then I should be navigated to the payment step
```

**Acceptance Criteria:**
- The address form is displayed with all required fields
- The user can fill in the address form with valid data
- The user is navigated to the payment step after submitting the address form
- The address form submission is successful with a valid address
- The application displays a success message after address form submission

### US-002 — Address Form Validation

🔴 **Priority**: High | **Points**: 3 | **Labels**: mobile, android, appium, checkout

**As a** mobile shopping user  
**I want** to be prevented from submitting the address form with empty required fields  
**So that** I can ensure that my address is valid and complete  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I submit the address form with empty required fields
Then I should see an error message indicating the required fields
```

**Acceptance Criteria:**
- The application displays an error message when submitting the address form with empty required fields
- The error message indicates which fields are required
- The user cannot submit the address form with empty required fields
- The application prevents the user from proceeding to the payment step with invalid address data

### US-003 — Navigation to Payment Step

🔴 **Priority**: High | **Points**: 5 | **Labels**: mobile, android, appium, checkout

**As a** mobile shopping user  
**I want** to navigate to the payment step after submitting the address form  
**So that** I can complete my purchase  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I submit the address form with valid data
Then I should be navigated to the payment step
```

**Acceptance Criteria:**
- The user is navigated to the payment step after submitting the address form
- The payment step is displayed with all required fields
- The user can select a payment method
- The application displays a summary of the order
- The user can complete the purchase by submitting the payment information


## F-006 — Checkout Payment

### US-001 — Valid Payment Information

🔴 **Priority**: High | **Points**: 5 | **Labels**: mobile, android, appium, checkout

**As a** user  
**I want** to fill in valid payment information  
**So that** I can complete my purchase successfully  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I fill in valid payment information
Then I should see a confirmation of my purchase
```

**Acceptance Criteria:**
- The payment information form is displayed correctly
- The user can fill in valid payment information
- The purchase is confirmed and a confirmation message is displayed
- The payment information is validated correctly
- The user is redirected to the order review page

### US-002 — Invalid Card Number

🔴 **Priority**: High | **Points**: 3 | **Labels**: mobile, android, appium, checkout

**As a** user  
**I want** to see an error message when I enter an invalid card number  
**So that** I can correct my payment information  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I fill in an invalid card number
Then I should see an error message indicating that the card number is invalid
```

**Acceptance Criteria:**
- The error message is displayed correctly
- The user is not allowed to proceed with the purchase
- The payment information form is still displayed
- The user can correct the payment information
- The error message is cleared when the user corrects the payment information

### US-003 — Navigate to Order Review

🟡 **Priority**: Medium | **Points**: 2 | **Labels**: mobile, android, appium, checkout

**As a** user  
**I want** to navigate to the order review page after filling in my payment information  
**So that** I can review my order before completing my purchase  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I fill in my payment information and click on the 'Review Order' button
Then I should be redirected to the order review page
```

**Acceptance Criteria:**
- The user is redirected to the order review page
- The order review page displays the correct order information
- The user can review their order
- The user can proceed with the purchase or cancel the order
- The order review page is displayed correctly


## F-007 — Checkout Review & Complete

### US-007-001 — Review Order Before Validation

🔴 **Priority**: High | **Points**: 5 | **Labels**: mobile, android, appium, checkout

**As a** mobile shopping user  
**I want** to review my order details before completing the checkout  
**So that** I can ensure everything is correct and make any necessary changes  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I click on the review order button
Then I should see my order details including items, quantities, and total cost
```

**Acceptance Criteria:**
- The order review page displays all items in the cart
- The order review page displays the correct quantities for each item
- The order review page displays the correct total cost

### US-007-002 — Complete Order Successfully

🔴 **Priority**: High | **Points**: 8 | **Labels**: mobile, android, appium, checkout

**As a** mobile shopping user  
**I want** to complete my order with a valid payment method  
**So that** I can receive my purchased items  

**Gherkin Scenario:**
```gherkin
Given I am on the checkout page
When I enter valid payment information and click the complete order button
Then I should see a confirmation message and receive an order confirmation email
```

**Acceptance Criteria:**
- The application accepts valid payment information
- The application displays a confirmation message after completing the order
- The user receives an order confirmation email with order details

### US-007-003 — Display Confirmation Message

🔴 **Priority**: High | **Points**: 3 | **Labels**: mobile, android, appium, checkout

**As a** mobile shopping user  
**I want** to see a confirmation message after completing my order  
**So that** I can be sure my order was successful  

**Gherkin Scenario:**
```gherkin
Given I have completed my order
When I am on the order confirmation page
Then I should see a confirmation message with my order number and details
```

**Acceptance Criteria:**
- The application displays a confirmation message after completing the order
- The confirmation message includes the order number
- The confirmation message includes a summary of the order details


## F-008 — Navigation Menu

### US-008-001 — Ouverture du menu burger

🟢 **Priority**: Low | **Points**: 2 | **Labels**: mobile, android, appium, navigation-menu

**As a** Utilisateur de l'application  
**I want** Ouvrir le menu burger pour accéder aux options de navigation  
**So that** Je puisse naviguer facilement dans l'application  

**Gherkin Scenario:**
```gherkin
Given I am on the home screen
When I click on the burger menu icon
Then the navigation menu should be displayed
```

**Acceptance Criteria:**
- Le menu burger est visible sur l'écran d'accueil
- Le menu burger est cliquable
- Le menu de navigation s'affiche correctement après clic sur le menu burger

### US-008-002 — Navigation vers le catalogue depuis le menu

🟡 **Priority**: Medium | **Points**: 3 | **Labels**: mobile, android, appium, navigation-menu, catalogue

**As a** Utilisateur de l'application  
**I want** Naviguer vers le catalogue depuis le menu de navigation  
**So that** Je puisse parcourir les produits disponibles  

**Gherkin Scenario:**
```gherkin
Given I am on the home screen
When I click on the burger menu icon
And I click on the catalogue option
Then the catalogue screen should be displayed
```

**Acceptance Criteria:**
- Le menu de navigation contient l'option 'Catalogue'
- L'option 'Catalogue' est cliquable
- L'écran du catalogue s'affiche correctement après clic sur l'option 'Catalogue'

### US-008-003 — Navigation vers le panier depuis le menu

🟡 **Priority**: Medium | **Points**: 3 | **Labels**: mobile, android, appium, navigation-menu, panier

**As a** Utilisateur de l'application  
**I want** Naviguer vers le panier depuis le menu de navigation  
**So that** Je puisse gérer mes achats en cours  

**Gherkin Scenario:**
```gherkin
Given I am on the home screen
When I click on the burger menu icon
And I click on the cart option
Then the cart screen should be displayed
```

**Acceptance Criteria:**
- Le menu de navigation contient l'option 'Panier'
- L'option 'Panier' est cliquable
- L'écran du panier s'affiche correctement après clic sur l'option 'Panier'

---
_Generated by userstory-generator-agent.py_