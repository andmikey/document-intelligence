"""Single source of truth for red flag label constants.

Both the prompt in extract.py and the rules in advance_fee.py must import from here
— never hardcode label strings in two places.
"""

# Labels the prompt instructs the model to use.
# Rules check for exact membership using these constants.
CRYPTO_COMPENSATION = "cryptocurrency_compensation_mentioned"
UNKNOWN_CONTACT = "unknown_contact_initiated"
THIRD_PARTY_RECRUITER = "third_party_recruiter_referenced"
REFERRAL_CODE_PRESENT = "referral_code_present"
VAGUE_JOB_NO_SKILLS = "vague_job_no_skills_required"
URGENCY_LANGUAGE = "urgency_language_present"
SECRECY_INSTRUCTION = "secrecy_instruction_present"
UNVERIFIABLE_EMPLOYER = "unverifiable_employer"

# The subset that the prompt lists as examples. Used to build the prompt dynamically
# so the prompt and constants cannot diverge.
PROMPTED_FLAGS = [
    CRYPTO_COMPENSATION,
    UNKNOWN_CONTACT,
    THIRD_PARTY_RECRUITER,
    REFERRAL_CODE_PRESENT,
    VAGUE_JOB_NO_SKILLS,
    URGENCY_LANGUAGE,
    SECRECY_INSTRUCTION,
    UNVERIFIABLE_EMPLOYER,
]
