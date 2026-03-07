# Assumptions

This document summarizes any assumptions made about the spec or project context. 

## Fraud context 
- The solution is being used to prevent scams and frauds on outbound UK Faster Payments. AML is out of scope, all other payment methods are out of scope, inbound payments are out of scope. 
- The end goal of the product is:
    - Reduce the bank's financial and reputational exposure to APP fraud, by
    - Increasing the VDR and TPR of their existing payment fraud system, by
    - Improving fraud analysts' ability + confidence at assessing whether a customer's payment is genuine or fraudulent. 
- The flow is:
    - Payment is flagged by a real-time risk scoring system as high-risk. It is intended for catch-and-release usage (reviewed by an analyst before being released or blocked).     
        - Release-and-review (the payment goes through but is reviewed by an analyst later) is out of scope.
        - Medium risk payments (automated friction steps like warning screens or a cool-off) are out of scope. 
    - Analyst picks up alert from the queue. They have insufficient information to decide whether to block or release the payment, so they contact the customer to ask for more information to show the payment is genuine.
    - The customer provides some documents for the analyst to review.
    - The analyst uploads these documents to the platform we're building. The platform returns a risk score, risk category, and explanation.
- No other information about the payment is available other than the documents provided by the customer.
    - This is an unrealistic assumption. In a real system we'd have access to the customer behaviour, possibly the counterparty behaviour, information about the payment itself, etc.
- We will only focus rules on a small subset of fraud typologies (impersonation scam 3rd party fraud). All other fraud typologies are out of scope. No historical examples are available. 

## Rules
- There is no historical dataset available to tune the rule definitions or optimize rule alerting thresholds.
- The rules will be written and maintained by a technical team, rather than by the analysts. Rules written in Python are acceptable.
- Policy rules are out of scope. 

## Model
- Errors out of scope:
    - Hallucinated field values (e.g. incorrect amount)
    - Returning a valid but incorrect category

## Inputs
- Checking input files for sensitive data is out of scope. 
- Multi-page documents are out of scope. 

# Performance 
- Whole system performance is out of scope due to no labels being available. If labels were available, would true positive rate / value detection rate at fixed false positive rate or alert rate. 