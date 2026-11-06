"""JARVIS NVIDIA NIM Rotator (re-export module for jarvis.core.api_key_rotator).

Exposes `NvidiaNimKeyRotator` and the global `nvidia_nim_rotator` singleton
for consumers that import provider rotators through dedicated modules.
"""

from jarvis.core.api_key_rotator import NvidiaNimKeyRotator, nvidia_nim_rotator

__all__ = ["NvidiaNimKeyRotator", "nvidia_nim_rotator"]
