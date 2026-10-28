from integrations.base import (
    BaseIntegration,
    IntegrationRegistry,
    integration_registry,
    CredentialManager,
    credential_manager,
    OAuthManager,
    oauth_manager,
    IntegrationRateLimiter,
    rate_limiter,
    RetryPolicy,
    default_retry_policy,
    IntegrationStatus,
    HealthReport,
)
from integrations.system.system_diagnostics import SystemDiagnosticsIntegration
from integrations.github.github_integration import GitHubIntegration

# Auto-register foundational integrations
integration_registry.register(SystemDiagnosticsIntegration())
integration_registry.register(GitHubIntegration())

__all__ = [
    "BaseIntegration",
    "IntegrationRegistry",
    "integration_registry",
    "CredentialManager",
    "credential_manager",
    "OAuthManager",
    "oauth_manager",
    "IntegrationRateLimiter",
    "rate_limiter",
    "RetryPolicy",
    "default_retry_policy",
    "IntegrationStatus",
    "HealthReport",
    "SystemDiagnosticsIntegration",
    "GitHubIntegration",
]
