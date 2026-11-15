import math

import pytest

from src.normalize import norm_city, norm_postcode, norm_street_number, split_name


@pytest.mark.parametrize("name, core, legal, countries", [
    ("ENERGI HOBRO TELE A/S", "ENERGI HOBRO TELE", ("A/S",), ()),
    ("24-SEVEN MEDIA NETWORK (PRIVATE) LIMITED", "24 SEVEN MEDIA NETWORK", ("PVT LTD",), ()),
    ("LeasePlan Sverige AB", "LEASEPLAN", ("AB",), ("SE",)),
    ("TINEX GROUP AS", "TINEX GROUP", ("AS",), ()),
    ("IPG MEDIABRANDS (SINGAPORE) PTE. LTD.", "IPG MEDIABRANDS", ("PTE LTD",), ("SG",)),
    ("Thai Beverage Thailand Co., Ltd.", "THAI BEVERAGE", ("CO LTD",), ("TH",)),
    ("Teliti Teknik (M) Sdn. Bhd.", "TELITI TEKNIK", ("SDN BHD",), ("MY",)),
    ("Siemens Danmark A/S", "SIEMENS", ("A/S",), ("DK",)),
    ("Example Nederland B.V.", "EXAMPLE", ("BV",), ("NL",)),
    ("CommScope Solutions (S) Pte. Ltd.", "COMMSCOPE SOLUTIONS", ("PTE LTD",), ("SG",)),
    ("HOPPECKE Batterien GmbH & Co. KG", "HOPPECKE BATTERIEN", ("GMBH AND CO KG",), ()),
    ("Shenzhen Center Power Tech Co.Ltd", "SHENZHEN CENTER POWER TECH", ("CO LTD",), ()),
    ("Telenor d.o.o.", "TELENOR", ("DOO",), ()),
    ("NTT DATA Business Solutions Korlátolt Felelősségű Társaság", "NTT DATA BUSINESS SOLUTIONS", ("KFT",), ()),
    ("NemTilmeld.dk", "NEMTILMELD", (), ()),
    ("NemTilmeld.dk ApS", "NEMTILMELD", ("APS",), ()),
    ("Samsung Electronics Nordic Aktiebolag", "SAMSUNG ELECTRONICS NORDIC", ("AB",), ()),
    ("Thailife Insurance Public Company Limited", "THAILIFE INSURANCE", ("PCL",), ()),
    ("OM Technologies Sdn.Bhd.", "OM TECHNOLOGIES", ("SDN BHD",), ()),
])
def test_split_name(name, core, legal, countries):
    parts = split_name(name)
    assert parts.core == core
    assert parts.legal_forms == legal
    assert parts.country_words == countries


def test_split_name_strips_several_legal_forms():
    parts = split_name("Zte (Malaysia) Corporation Sdn. Bhd.")
    assert parts.core == "ZTE"
    assert set(parts.legal_forms) == {"SDN BHD", "CORP"}
    assert parts.country_words == ("MY",)


def test_split_name_branch_marker():
    parts = split_name("KLM-ROYAL DUTCH AIRLINES Filial av utenlandsk foretak.")
    assert parts.core == "KLM ROYAL DUTCH AIRLINES"
    assert parts.branch == "FILIAL AV UTENLANDSK FORETAK"


def test_split_name_branch_of_named_parent():
    parts = split_name("NORDEA BANK ABP FILIAL I NORGE")
    assert parts.core == "NORDEA BANK"
    assert parts.legal_forms == ("ABP",)
    assert parts.branch == "FILIAL I NORGE"


def test_split_name_never_empties_core():
    assert split_name("AS").core == "AS"
    assert split_name("Danmark A/S").core == "DANMARK"


def test_split_name_keeps_group_in_core():
    assert split_name("TINEX Group").core == "TINEX GROUP"


@pytest.mark.parametrize("city, expected", [
    ("Aalborg Municipality", "AALBORG"),
    ("Tønder Municipality", "TONDER"),
    ("Karachi Division", "KARACHI"),
    ("Solna", "SOLNA"),
    (math.nan, None),
])
def test_norm_city(city, expected):
    assert norm_city(city) == expected


@pytest.mark.parametrize("postcode, country, expected", [
    (668, "NO", "0668"),
    (1364, "NO", "1364"),
    ("118 53", "SE", "11853"),
    (68804, "SG", "068804"),
    (2610, "FI", "02610"),
    ("SE1 2QG", "GB", "SE12QG"),
    ("2517 KR", "NL", "2517KR"),
    (0, "HK", None),
    (math.nan, "NO", None),
])
def test_norm_postcode(postcode, country, expected):
    assert norm_postcode(postcode, country) == expected


@pytest.mark.parametrize("number, expected", [("2 A", "2A"), ("3f", "3F"), (12, "12"), (math.nan, None)])
def test_norm_street_number(number, expected):
    assert norm_street_number(number) == expected


def test_split_name_nationality_before_branch():
    parts = split_name("Amazon Web Services EMEA SARL, Norwegian branch")
    assert parts.core == "AMAZON WEB SERVICES EMEA"
    assert parts.legal_forms == ("SARL",)
    assert parts.country_words == ("NO",)
    assert parts.branch == "BRANCH"


@pytest.mark.parametrize("name", ["Campana Group Private Limited", "Example Private Ltd"])
def test_private_limited_is_valid_in_singapore_and_malaysia(name):  # D52
    assert {"SG", "MY"} <= split_name(name).legal_countries


@pytest.mark.parametrize("name, core, legal, country", [
    ("ATREBO SL", "ATREBO", "SL", "ES"),
    ("AWAN DISTRIBUTION FZC", "AWAN DISTRIBUTION", "FZC", "AE"),
    ("CENTERFORENINGEN FISKETORVET F.M.B.A.", "CENTERFORENINGEN FISKETORVET", "FMBA", "DK"),
    ("Tradium Randers S/I", "TRADIUM RANDERS", "S/I", "DK"),
    ("ENETEK POWER SPOLKA Z OGRANICZONA ODPOWIEDZIALNOSCIA", "ENETEK POWER", "SP Z OO", "PL"),
    ("Radio Frequency Systems Gesellschaft mit beschrankter Haftung", "RADIO FREQUENCY SYSTEMS", "GMBH", "DE"),
    ("ACME UNLIMITED COMPANY", "ACME", "UC", "IE"),
    ("Telenor Magyarorszag Zrt.", "TELENOR MAGYARORSZAG", "ZRT", "HU"),
])
def test_more_legal_forms(name, core, legal, country):  # D56
    parts = split_name(name)
    assert (parts.core, parts.legal_forms) == (core, (legal,))
    assert country in parts.legal_countries
