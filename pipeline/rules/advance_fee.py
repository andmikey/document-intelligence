"""Concrete rule implementations for advance fee / job scam fraud typology."""

from pipeline import flags
from pipeline.rules.base import BaseRule
from pipeline.schemas import ExtractedFields, RuleResult


class CryptoCompensationRule(BaseRule):
    """Detects mention of cryptocurrency compensation.

    Legitimate UK employers do not pay in USDT or other crypto.
    Strong standalone signal.
    """

    rule_id = "crypto_compensation"
    weight = 0.35
    bucket = "compensation"

    def evaluate(self, fields: ExtractedFields) -> RuleResult:
        triggered = flags.CRYPTO_COMPENSATION in fields.red_flags
        return RuleResult(
            rule_id=self.rule_id,
            triggered=triggered,
            weight=self.weight,
            explanation="cryptocurrency compensation mentioned" if triggered else "",
        )


class UnknownContactRule(BaseRule):
    """Detects unsolicited contact from an unknown number.

    Unsolicited contact from an unsaved number is the standard entry point
    for job scams.
    """

    rule_id = "unknown_contact_initiated"
    weight = 0.20
    bucket = "contact"

    def evaluate(self, fields: ExtractedFields) -> RuleResult:
        triggered = flags.UNKNOWN_CONTACT in fields.red_flags
        return RuleResult(
            rule_id=self.rule_id,
            triggered=triggered,
            weight=self.weight,
            explanation="unknown contact initiated conversation" if triggered else "",
        )


class PersonalMessagingPlatformRule(BaseRule):
    """Detects use of personal messaging platforms.

    Legitimate employers do not recruit via WhatsApp or Telegram cold messages.
    """

    rule_id = "personal_messaging_platform"
    weight = 0.15
    bucket = "contact"

    def evaluate(self, fields: ExtractedFields) -> RuleResult:
        triggered = False
        if fields.platform is not None:
            platform_lower = fields.platform.lower()
            triggered = platform_lower in ["whatsapp", "telegram", "signal"]

        return RuleResult(
            rule_id=self.rule_id,
            triggered=triggered,
            weight=self.weight,
            explanation="personal messaging platform used" if triggered else "",
        )


class ThirdPartyReferralRule(BaseRule):
    """Detects third-party referral or referral codes.

    Referral codes and named recruiters indicate a coordinated scam network.
    """

    rule_id = "third_party_referral"
    weight = 0.20
    bucket = "recruitment"

    def evaluate(self, fields: ExtractedFields) -> RuleResult:
        triggered = (
            flags.THIRD_PARTY_RECRUITER in fields.red_flags
            or flags.REFERRAL_CODE_PRESENT in fields.red_flags
        )
        return RuleResult(
            rule_id=self.rule_id,
            triggered=triggered,
            weight=self.weight,
            explanation="third-party referral present" if triggered else "",
        )


class VagueJobDescriptionRule(BaseRule):
    """Detects vague job descriptions requiring no skills.

    "Just operate a mobile phone" is a near-universal marker of
    task-based scam recruitment.
    """

    rule_id = "vague_job_description"
    weight = 0.15
    bucket = "recruitment"

    def evaluate(self, fields: ExtractedFields) -> RuleResult:
        triggered = flags.VAGUE_JOB_NO_SKILLS in fields.red_flags
        return RuleResult(
            rule_id=self.rule_id,
            triggered=triggered,
            weight=self.weight,
            explanation="vague job requiring no skills" if triggered else "",
        )
