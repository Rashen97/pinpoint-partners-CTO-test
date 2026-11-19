"""Database operations will live here once a connector has verified scope.

No connector writes directly to SQLite. This separation lets the validation
stage reject blocked, incomplete, or out-of-scope extractions first.
"""
