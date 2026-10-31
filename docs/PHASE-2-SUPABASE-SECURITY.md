\# PayFlow AI — Phase 2: Supabase Database \& Authentication



\## 1. Overview



Phase 2 establishes the database, authentication and security foundation of PayFlow AI.



Technologies:

\- Supabase PostgreSQL

\- Supabase Auth

\- FastAPI

\- Python

\- Pydantic

\- Supabase Python SDK



\## 2. Database Architecture



The project contains eight database tables.



| Table | Purpose |

|---|---|

| profiles | User and business profile information |

| customers | Customer details |

| invoices | Invoice records |

| invoice\_items | Individual invoice line items |

| payments | Payment transaction records |

| reminders | Payment reminder schedules |

| ai\_action\_approvals | AI actions requiring user approval |

| audit\_logs | Records important application activities |



\## 3. Authentication Architecture



1\. The user authenticates through Supabase Auth.

2\. Supabase issues an access token.

3\. The frontend sends the token to FastAPI using the Bearer authorization header.

4\. FastAPI verifies the JWT signature and expiration.

5\. FastAPI extracts the verified user ID.

6\. The user is confirmed through Supabase Auth.

7\. A user-scoped Supabase database client is created.

8\. Database operations execute using the authenticated user's token.



\## 4. Database Security



Row Level Security (RLS) is enabled on all eight public tables.



Policies restrict authenticated users to records they own.



The customers table supports user-scoped CRUD operations.



Financial and sensitive operational tables restrict direct client-side modifications. Protected operations are intended to go through trusted backend services.



The backend must derive ownership from the verified authenticated user rather than trusting frontend-supplied user IDs.



\## 5. Supabase Client Architecture



Two types of Supabase clients are configured.



\*\*User-scoped client\*\*

\- Uses the authenticated user's JWT.

\- Applies database RLS policies.

\- Used for operations performed on behalf of authenticated users.



\*\*Service-role client\*\*

\- Uses the backend-only secret key.

\- Bypasses RLS.

\- Must only be used in trusted backend operations.

\- Requires explicit ownership validation.



Secret keys must never be exposed to the frontend.



\## 6. Database Relationships



\- profiles → customers: One-to-many

\- profiles → invoices: One-to-many

\- customers → invoices: One-to-many

\- invoices → invoice\_items: One-to-many

\- invoices → payments: One-to-many

\- invoices → reminders: One-to-many

\- invoices → ai\_action\_approvals: One-to-many

\- profiles → audit\_logs: One-to-many



Foreign keys and composite ownership constraints help prevent cross-user record associations.



\## 7. Security Testing



Two separate Supabase test accounts were used to validate access isolation.



The consolidated security suite completed:



\- 16 cross-user read-isolation checks

\- 36 unauthorized database write checks

\- 2 customer ownership-spoofing checks

\- 2 customer ownership-transfer checks



\*\*Total: 56 passed, 0 failed.\*\*



The suite was executed again after changing synchronous authentication dependencies. The regression run also completed with 56 passed and 0 failed.



\## 8. Database Permission Verification



All eight tables were checked.



\- RLS enabled: 8/8

\- Anonymous SELECT access: denied on 8/8

\- Authenticated SELECT access: available on 8/8

\- Backend SELECT access: available on 8/8

\- At least one RLS policy per table: 8/8



\## 9. Test Data Cleanup



Temporary security-test records were removed after testing.



The final cleanup verification returned zero records for:

\- Test customers

\- Test invoices

\- Test payments

\- Test reminders

\- Test AI approvals

\- Test audit logs



The two Supabase authentication test accounts and their profiles were retained.



\## 10. Security Considerations



\- Never expose Supabase secret keys to the frontend.

\- Never trust frontend-supplied user IDs for ownership.

\- Verify PayPal webhook signatures before processing events.

\- Make webhook processing idempotent.

\- Require explicit approval before executing sensitive AI actions.

\- Record important financial operations in audit logs.

\- Apply ownership checks to every service-role database operation.



\## 11. Remaining Production Hardening



The following areas require further attention during subsequent development:



\- Review service-role ownership checks as backend services are implemented.

\- Add authentication rate limiting.

\- Improve authentication client reuse.

\- Test PayPal webhook verification.

\- Test financial business logic and approval enforcement.

\- Review unexpected authentication and network exceptions.



\## 12. Phase 2 Outcome



The Supabase database, authentication flow, user-scoped access and core database security controls have been implemented and tested.



\*\*Core Phase 2 implementation: Completed.\*\*



Further production hardening and integration-specific security testing will continue during later development phases.
