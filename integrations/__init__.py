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
from integrations.openrouter.openrouter_integration import OpenRouterIntegration
from integrations.home_assistant.home_assistant import HomeAssistantIntegration, home_assistant_integration
from integrations.calendar.calendar_integration import CalendarIntegration, calendar_integration
from integrations.finance.finance_integration import FinanceIntegration, finance_integration

# Auto-register all integrations
integration_registry.register(SystemDiagnosticsIntegration())
integration_registry.register(GitHubIntegration())
integration_registry.register(OpenRouterIntegration())
integration_registry.register(HomeAssistantIntegration())
integration_registry.register(CalendarIntegration())
integration_registry.register(FinanceIntegration())

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
    "OpenRouterIntegration",
    "HomeAssistantIntegration",
    "home_assistant_integration",
    "CalendarIntegration",
    "calendar_integration",
    "FinanceIntegration",
    "finance_integration",
]
