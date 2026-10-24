"""Parser tests: SDUI layout detection and followers/connections split."""

from linkedin_mcp_server.domain.models.person import PersonMainProfile, PersonPostsSection
from linkedin_mcp_server.domain.parsers import (
    SDUI_UNSUPPORTED_MESSAGE,
    is_empty_section,
    unsupported_layout_reason,
)
from linkedin_mcp_server.domain.parsers.common import is_sdui_markup
from linkedin_mcp_server.domain.parsers.person import parse_person_main_profile

SDUI_PROFILE_HTML = """
<div componentkey="0122fe71-5883-483e-8150-0a1b2c3d4e5f" class="_27506df7 e3900514">
  <a aria-label="Jane Doe" href="/in/janedoe/"><h2 class="c816e7f7">Jane Doe</h2></a>
  <p class="_37677861">Jane Doe</p>
  <div componentkey="ProfileVerificationTriggerRef-janedoe"></div>
</div>
"""

LEGACY_PROFILE_HTML = """
<section class="artdeco-card pv-top-card">
  <h1 class="text-heading-xlarge">Jane Doe</h1>
  <div class="text-body-medium break-words">Engineer at Acme</div>
  <span class="text-body-small inline t-black--light break-words">Lille, France</span>
  <ul>
    {items}
  </ul>
</section>
"""


def _legacy(*items: str) -> str:
    return LEGACY_PROFILE_HTML.format(items="\n".join(items))


# ── SDUI detection ───────────────────────────────────────────────────────────


def test_is_sdui_markup_detects_componentkey_and_sdui_markers():
    assert is_sdui_markup(SDUI_PROFILE_HTML)
    assert is_sdui_markup('<div data-sdui-screen="profile"></div>')


def test_is_sdui_markup_ignores_legacy_and_empty_html():
    assert not is_sdui_markup(_legacy())
    assert not is_sdui_markup("")


def test_is_empty_section_ignores_raw():
    assert is_empty_section(PersonMainProfile(raw="<html></html>"))
    assert not is_empty_section(PersonMainProfile(name="Jane"))
    assert is_empty_section(PersonPostsSection(posts=[]))


def test_unsupported_layout_reason_flags_empty_sdui_parse():
    parsed = parse_person_main_profile(SDUI_PROFILE_HTML)
    assert is_empty_section(parsed)
    assert unsupported_layout_reason(SDUI_PROFILE_HTML, parsed) == SDUI_UNSUPPORTED_MESSAGE


def test_unsupported_layout_reason_trusts_legacy_and_non_empty_results():
    legacy_empty = "<section><p>Nothing here</p></section>"
    assert unsupported_layout_reason(legacy_empty, parse_person_main_profile(legacy_empty)) is None
    # SDUI markers but the parser still found data → keep the result
    assert unsupported_layout_reason(SDUI_PROFILE_HTML, PersonMainProfile(name="Jane")) is None


# ── Followers / connections split ────────────────────────────────────────────


def test_main_profile_english_followers_and_connections():
    result = parse_person_main_profile(
        _legacy(
            '<li class="text-body-small"><span class="t-bold">1,234</span> followers</li>',
            '<li class="text-body-small"><span class="t-bold">500+</span> connections</li>',
        )
    )
    assert result.name == "Jane Doe"
    assert result.location == "Lille, France"
    assert result.followers == "1,234 followers"
    assert result.connections == "500+ connections"


def test_main_profile_french_followers_and_connections_by_position():
    result = parse_person_main_profile(
        _legacy(
            '<li class="text-body-small"><span class="t-bold">1 234</span> abonnés</li>',
            '<li class="text-body-small"><span class="t-bold">345</span> relations</li>',
        )
    )
    assert result.followers == "1 234 abonnés"
    assert result.connections == "345 relations"


def test_main_profile_capped_count_identifies_connections_in_any_order():
    result = parse_person_main_profile(
        _legacy(
            '<li class="text-body-small"><span class="t-bold">500+</span> relations</li>',
            '<li class="text-body-small"><span class="t-bold">2 345</span> abonnés</li>',
        )
    )
    assert result.connections == "500+ relations"
    assert result.followers == "2 345 abonnés"


def test_main_profile_link_targets_identify_counts():
    result = parse_person_main_profile(
        _legacy(
            '<li class="text-body-small"><a href="/search/results/people/?connectionOf=x">'
            '<span class="t-bold">87</span> Kontakte</a></li>',
            '<li class="text-body-small"><a href="/feed/followers/">'
            '<span class="t-bold">90</span> Follower:innen</a></li>',
        )
    )
    assert result.connections == "87 Kontakte"
    assert result.followers == "90 Follower:innen"


def test_main_profile_lone_count_is_connections():
    result = parse_person_main_profile(
        _legacy('<li class="text-body-small"><span class="t-bold">345</span> relations</li>')
    )
    assert result.connections == "345 relations"
    assert result.followers is None


def test_main_profile_ignores_counts_outside_the_top_card_list():
    html = (
        _legacy(
            '<li class="text-body-small"><span class="t-bold">1 234</span> abonnés</li>',
            '<li class="text-body-small"><span class="t-bold">345</span> relations</li>',
        )
        + '<ul><li class="text-body-small">Promo 2019 · 3 ans</li></ul>'
    )
    result = parse_person_main_profile(html)
    assert result.followers == "1 234 abonnés"
    assert result.connections == "345 relations"


def test_main_profile_without_counts():
    result = parse_person_main_profile(_legacy('<li class="text-body-small">Contact info</li>'))
    assert result.followers is None
    assert result.connections is None
