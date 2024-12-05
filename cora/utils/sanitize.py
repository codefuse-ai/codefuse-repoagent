import re

_PATTERN_PHONE_NUMBER = re.compile(
    r"(?:\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}"
)
_PATTERN_EMAIL_ADDRESS = re.compile(r"\b[\w\-.+]+@(?:[\w-]+\.)+[\w-]{2,4}\b")
_PATTERN_PASSWORD = re.compile(
    r'["\']?password["\']?\s*[=:]\s*["\']?[\w_]+["\']?', flags=re.IGNORECASE
)


def sanitize_content(content):
    content = _PATTERN_EMAIL_ADDRESS.sub("<anonymous_email_address>", content)
    content = _PATTERN_PHONE_NUMBER.sub("<anonymous_phone_number>", content)
    content = _PATTERN_PASSWORD.sub("<password_mask>", content)
    return content
