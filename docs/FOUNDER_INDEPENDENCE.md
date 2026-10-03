# Founder Independence

The project is not complete until every founder dependency has a documented path to **NONE**.

| Dependency | Current owner | Required owner | Migration mechanism | Replacement mechanism | Revocation procedure |
|------------|---------------|----------------|---------------------|-----------------------|----------------------|
| Hardware (home Sanctum) | Founder | External Sanctum steward(s) | Spore install → attestation → encrypted state → shadow ticks → lease transfer | Additional Sanctum candidates | Power off founder machine after lease transfer verified |
| Cloud accounts | Founder | Steward org / none if self-hosted | Account transfer or redeploy on steward infra | Multi-steward cloud or bare metal | Remove founder from account; rotate keys |
| Domains | Founder | Steward registrar account | Registrar transfer | New domain with dual-run cutover | Cancel founder registrar access |
| DNS | Founder | Steward DNS | Export zone; switch nameservers | Secondary DNS providers | Remove founder DNS credentials |
| Twitch | Founder | Entity-controlled / steward | Channel stewardship handoff | Secondary broadcast account (if needed) | Revoke founder Twitch tokens after handoff |
| Discord | Founder | Steward bot owner | Bot ownership / hosting transfer | Redeploy bot on Sanctum | Revoke founder Discord tokens |
| Email | Founder | Steward mailbox | Forwarding then ownership transfer | Entity ops mailbox | Disable founder mailbox access |
| LLM providers | Founder keys via FreeLLMAPI | Sanctum vault keys | Re-key FreeLLMAPI on new Sanctum | Alternate providers in fallback chain | Delete founder provider keys |
| Storage | Founder disk | Sanctum encrypted volumes | Encrypted snapshot transfer | Object storage under steward | Wipe founder copies after verify |
| Signing keys | Founder local key file | Sanctum HSM/TEE or steward quorum | Key ceremony / re-sign with new authority | Threshold signing (later) | Destroy founder private key material |
| Recovery keys | Founder | Split among stewards | Shamir / multi-party recovery | New recovery set | Invalidate founder recovery shares |
| Billing | Founder | Steward / patronage pool | Move subscriptions | Patron-funded accounts | Cancel founder payment methods |
| Stewardship | Founder sole | Multi-steward covenant | Stewardship charter + lease protocol | Rotating stewards | Founder resigns root; cannot silently resume |

## Phase status

Phase 0: founder local machine is the Sanctum. Independence paths are documented, not executed.

Ultimate test: founder machine OFF, founder credentials REVOKED, founder SSH REVOKED, entity still running.
