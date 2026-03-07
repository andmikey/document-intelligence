"""Unit tests for scoring rules."""

from pipeline import flags
from pipeline.rules.advance_fee import (
    CryptoCompensationRule,
    PersonalMessagingPlatformRule,
    ThirdPartyReferralRule,
    UnknownContactRule,
    VagueJobDescriptionRule,
)
from pipeline.schemas import ExtractedFields

# CryptoCompensationRule tests


def test_crypto_compensation_triggers():
    fields = ExtractedFields(red_flags=[flags.CRYPTO_COMPENSATION])
    result = CryptoCompensationRule().evaluate(fields)
    assert result.triggered is True
    assert result.rule_id == "crypto_compensation"
    assert result.weight == 0.35


def test_crypto_compensation_does_not_trigger():
    fields = ExtractedFields(red_flags=[])
    result = CryptoCompensationRule().evaluate(fields)
    assert result.triggered is False


# UnknownContactRule tests


def test_unknown_contact_triggers():
    fields = ExtractedFields(red_flags=[flags.UNKNOWN_CONTACT])
    result = UnknownContactRule().evaluate(fields)
    assert result.triggered is True
    assert result.rule_id == "unknown_contact_initiated"
    assert result.weight == 0.20


def test_unknown_contact_does_not_trigger():
    fields = ExtractedFields(red_flags=[])
    result = UnknownContactRule().evaluate(fields)
    assert result.triggered is False


# PersonalMessagingPlatformRule tests


def test_personal_messaging_platform_triggers_whatsapp():
    fields = ExtractedFields(platform="WhatsApp")
    result = PersonalMessagingPlatformRule().evaluate(fields)
    assert result.triggered is True
    assert result.rule_id == "personal_messaging_platform"
    assert result.weight == 0.15


def test_personal_messaging_platform_triggers_telegram():
    fields = ExtractedFields(platform="Telegram")
    result = PersonalMessagingPlatformRule().evaluate(fields)
    assert result.triggered is True


def test_personal_messaging_platform_triggers_signal():
    fields = ExtractedFields(platform="Signal")
    result = PersonalMessagingPlatformRule().evaluate(fields)
    assert result.triggered is True


def test_personal_messaging_platform_case_insensitive():
    fields = ExtractedFields(platform="telegram")
    result = PersonalMessagingPlatformRule().evaluate(fields)
    assert result.triggered is True


def test_personal_messaging_platform_does_not_trigger_legitimate():
    fields = ExtractedFields(platform="Email")
    result = PersonalMessagingPlatformRule().evaluate(fields)
    assert result.triggered is False


def test_personal_messaging_platform_does_not_trigger_none():
    fields = ExtractedFields(platform=None)
    result = PersonalMessagingPlatformRule().evaluate(fields)
    assert result.triggered is False


# ThirdPartyReferralRule tests


def test_third_party_referral_triggers_recruiter():
    fields = ExtractedFields(red_flags=[flags.THIRD_PARTY_RECRUITER])
    result = ThirdPartyReferralRule().evaluate(fields)
    assert result.triggered is True
    assert result.rule_id == "third_party_referral"
    assert result.weight == 0.20


def test_third_party_referral_triggers_referral_code():
    fields = ExtractedFields(red_flags=[flags.REFERRAL_CODE_PRESENT])
    result = ThirdPartyReferralRule().evaluate(fields)
    assert result.triggered is True


def test_third_party_referral_triggers_both():
    fields = ExtractedFields(
        red_flags=[flags.THIRD_PARTY_RECRUITER, flags.REFERRAL_CODE_PRESENT]
    )
    result = ThirdPartyReferralRule().evaluate(fields)
    assert result.triggered is True


def test_third_party_referral_does_not_trigger():
    fields = ExtractedFields(red_flags=[])
    result = ThirdPartyReferralRule().evaluate(fields)
    assert result.triggered is False


# VagueJobDescriptionRule tests


def test_vague_job_description_triggers():
    fields = ExtractedFields(red_flags=[flags.VAGUE_JOB_NO_SKILLS])
    result = VagueJobDescriptionRule().evaluate(fields)
    assert result.triggered is True
    assert result.rule_id == "vague_job_description"
    assert result.weight == 0.15


def test_vague_job_description_does_not_trigger():
    fields = ExtractedFields(red_flags=[])
    result = VagueJobDescriptionRule().evaluate(fields)
    assert result.triggered is False
