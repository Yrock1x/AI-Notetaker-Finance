"""Self-hosted authentication (replaces Supabase Auth).

- ``tokens``       — issue/verify self-signed session JWTs
- ``provisioning`` — first-login user + personal-org creation
- the OAuth endpoints live in app/api/v1/auth_native.py
"""
