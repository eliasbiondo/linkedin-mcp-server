"""Common parsing utilities shared across parser modules."""


def strip_linkedin_noise(html: str) -> str:
    """Remove LinkedIn UI noise elements from HTML content.

    This will be implemented to semantically filter out known UI element
    classes (navigation, sidebars, ads, etc.) from the HTML before parsing.
    """
    raise NotImplementedError("HTML noise stripping not yet implemented")
