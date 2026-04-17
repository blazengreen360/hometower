"""Rate limiting configuration.

Provides a module-level Limiter instance wired with the remote-address
key function. Import `limiter` wherever rate limit decorators are needed.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter: Limiter = Limiter(key_func=get_remote_address)
