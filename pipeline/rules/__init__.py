"""Rule registry - only file to edit when adding a rule."""

from pipeline.rules.advance_fee import (
    CryptoCompensationRule,
    PersonalMessagingPlatformRule,
    ThirdPartyReferralRule,
    UnknownContactRule,
    VagueJobDescriptionRule,
)
from pipeline.rules.base import BaseRule

RULES: list[BaseRule] = [
    CryptoCompensationRule(),
    UnknownContactRule(),
    PersonalMessagingPlatformRule(),
    ThirdPartyReferralRule(),
    VagueJobDescriptionRule(),
]
