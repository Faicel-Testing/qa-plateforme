@regression
Feature: signupNONRegressionSteps Feature
Scenario Outline: fill in the information requested to create the invalid account
Given User is in the signupNONReg page
And User2 fill the "<firstname>" and "<lastname>" and "<email>" and "<password>" and "<confirm_password>" in the field
Then GOOD2 AFTERNOON EE should be visible

Examples:
| firstname | lastname |  email             | password | confirm_password |
| Faysal    | Ghanem   |  fa.tfa@hotmail.fr| 12345    |       12345      |
| Rami      | Ghanem   |  fa.fha@hotmail.fr | FA12     |       FA12       |

