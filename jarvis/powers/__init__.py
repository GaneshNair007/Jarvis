"""Power implementations categorized by operational domain."""

from jarvis.powers.browser_powers import browser_powers
from jarvis.powers.desktop_powers import desktop_powers
from jarvis.powers.instant_powers import instant_powers
from jarvis.powers.it_admin_powers import it_admin_powers
from jarvis.powers.career_powers import career_powers
from jarvis.powers.multiagent_powers import multiagent_powers
from jarvis.powers.developer_powers import developer_powers
from jarvis.powers.security_powers import security_powers
from jarvis.powers.finance_powers import finance_powers
from jarvis.powers.smart_home_powers import smart_home_powers
from jarvis.powers.automation_powers import automation_powers

__all__ = [
    "browser_powers",
    "desktop_powers",
    "instant_powers",
    "it_admin_powers",
    "career_powers",
    "multiagent_powers",
    "developer_powers",
    "security_powers",
    "finance_powers",
    "smart_home_powers",
    "automation_powers",
]
