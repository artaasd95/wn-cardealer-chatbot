"""Deterministic fixture generator for the car-dealer chatbot.

Produces three CSV files under ``data/``:

* ``dealers.csv``  — dealer catalogue
* ``cars.csv``     — car catalogue with dealer references
* ``aliases.csv``  — user-typed variant of canonical make/model/variant names

The entire output is driven by ``random.Random(SEED)`` so reruns produce
byte-identical files.  No module-level code has side effects — all work
happens inside ``main()`` / ``generate()``.

``--check`` mode validates the committed fixtures without rewriting them.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
DATA_DIR: Final = REPO_ROOT / "data"

SEED: Final = 2024_09_17

CARS_CSV: Final = DATA_DIR / "cars.csv"
DEALERS_CSV: Final = DATA_DIR / "dealers.csv"
ALIASES_CSV: Final = DATA_DIR / "aliases.csv"

# Column tuples — order matters, both for writing and for --check.
CARS_COLUMNS: Final = (
    "car_id",
    "make",
    "model",
    "variant",
    "year",
    "fuel_type",
    "transmission",
    "body_type",
    "price_min",
    "price_max",
    "mileage_km",
    "features",
    "dealer_id",
)

DEALERS_COLUMNS: Final = (
    "dealer_id",
    "dealer_name",
    "city",
    "state",
    "address",
    "phone",
    "email",
    "rating",
)

ALIASES_COLUMNS: Final = (
    "alias_type",
    "alias",
    "make",
    "model",
    "variant",
)

# ---------------------------------------------------------------------------
# Catalogue data structures
# ---------------------------------------------------------------------------

VALID_FUEL_TYPES: Final = ("Petrol", "Diesel", "Electric", "Hybrid", "Plug-in Hybrid")
VALID_TRANSMISSIONS: Final = ("Automatic", "Manual", "CVT", "Single-Speed", "DCT", "DSG", "AMT")
VALID_BODY_TYPES: Final = (
    "Sedan",
    "SUV",
    "Hatchback",
    "Coupe",
    "Convertible",
    "Pickup",
    "Minivan",
    "Wagon",
)


@dataclass(frozen=True, slots=True)
class VariantSpec:
    name: str
    fuel: str
    transmission: str
    price_base: int  # INR, rupees


@dataclass(frozen=True, slots=True)
class ModelSpec:
    name: str
    body: str
    variants: tuple[VariantSpec, ...]


@dataclass(frozen=True, slots=True)
class MakeSpec:
    name: str
    models: tuple[ModelSpec, ...]


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

CATALOGUE: Final = (
    MakeSpec(
        "BMW",
        (
            ModelSpec(
                "3 Series",
                "Sedan",
                (
                    VariantSpec("320i", "Petrol", "Automatic", 3_500_000),
                    VariantSpec("330i", "Petrol", "Automatic", 4_600_000),
                    VariantSpec("M340i", "Petrol", "Automatic", 7_500_000),
                ),
            ),
            ModelSpec(
                "5 Series",
                "Sedan",
                (
                    VariantSpec("520i", "Petrol", "Automatic", 5_800_000),
                    VariantSpec("530i", "Petrol", "Automatic", 7_200_000),
                ),
            ),
            ModelSpec(
                "X1",
                "SUV",
                (
                    VariantSpec("sDrive18d", "Diesel", "Automatic", 3_900_000),
                    VariantSpec("xDrive20i", "Petrol", "Automatic", 4_800_000),
                ),
            ),
            ModelSpec(
                "X3",
                "SUV",
                (
                    VariantSpec("xDrive20d", "Diesel", "Automatic", 6_200_000),
                    VariantSpec("xDrive30i", "Petrol", "Automatic", 7_800_000),
                ),
            ),
            ModelSpec(
                "X5",
                "SUV",
                (
                    VariantSpec("xDrive40i", "Petrol", "Automatic", 10_200_000),
                    VariantSpec("M50d", "Diesel", "Automatic", 11_800_000),
                ),
            ),
            ModelSpec(
                "Z4",
                "Convertible",
                (
                    VariantSpec("sDrive20i", "Petrol", "Automatic", 6_900_000),
                    VariantSpec("M40i", "Petrol", "Automatic", 9_100_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Mercedes-Benz",
        (
            ModelSpec(
                "C-Class",
                "Sedan",
                (
                    VariantSpec("C220d", "Diesel", "Automatic", 5_400_000),
                    VariantSpec("C300", "Petrol", "Automatic", 6_200_000),
                    VariantSpec("AMG C43", "Petrol", "Automatic", 8_500_000),
                ),
            ),
            ModelSpec(
                "E-Class",
                "Sedan",
                (
                    VariantSpec("E220d", "Diesel", "Automatic", 6_800_000),
                    VariantSpec("E300", "Petrol", "Automatic", 7_900_000),
                ),
            ),
            ModelSpec(
                "GLC",
                "SUV",
                (
                    VariantSpec("GLC 220d", "Diesel", "Automatic", 7_200_000),
                    VariantSpec("GLC 300", "Petrol", "Automatic", 8_800_000),
                ),
            ),
            ModelSpec(
                "GLE",
                "SUV",
                (
                    VariantSpec("GLE 300d", "Diesel", "Automatic", 9_500_000),
                    VariantSpec("GLE 450", "Petrol", "Automatic", 12_100_000),
                ),
            ),
            ModelSpec(
                "A-Class",
                "Hatchback",
                (
                    VariantSpec("A200", "Petrol", "DCT", 4_200_000),
                    VariantSpec("AMG A35", "Petrol", "DCT", 6_700_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Audi",
        (
            ModelSpec(
                "A3",
                "Sedan",
                (
                    VariantSpec("35 TFSI", "Petrol", "DCT", 4_200_000),
                    VariantSpec("40 TFSI", "Petrol", "DCT", 5_100_000),
                ),
            ),
            ModelSpec(
                "A4",
                "Sedan",
                (
                    VariantSpec("35 TFSI", "Petrol", "DCT", 5_600_000),
                    VariantSpec("45 TFSI", "Petrol", "DCT", 7_100_000),
                ),
            ),
            ModelSpec(
                "Q5",
                "SUV",
                (
                    VariantSpec("40 TDI", "Diesel", "Automatic", 6_300_000),
                    VariantSpec("45 TFSI", "Petrol", "Automatic", 7_400_000),
                ),
            ),
            ModelSpec(
                "Q7",
                "SUV",
                (
                    VariantSpec("45 TDI", "Diesel", "Automatic", 8_900_000),
                    VariantSpec("55 TFSI", "Petrol", "Automatic", 10_500_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Toyota",
        (
            ModelSpec(
                "Innova Crysta",
                "Minivan",
                (
                    VariantSpec("GX", "Diesel", "Manual", 1_900_000),
                    VariantSpec("VX", "Diesel", "Automatic", 2_600_000),
                    VariantSpec("ZX", "Diesel", "Automatic", 2_900_000),
                ),
            ),
            ModelSpec(
                "Fortuner",
                "SUV",
                (
                    VariantSpec("4x2", "Diesel", "Automatic", 3_300_000),
                    VariantSpec("4x4", "Diesel", "Automatic", 4_100_000),
                ),
            ),
            ModelSpec("Camry", "Sedan", (VariantSpec("HEV", "Hybrid", "CVT", 4_500_000),)),
            ModelSpec(
                "Glanza",
                "Hatchback",
                (
                    VariantSpec("G", "Petrol", "Manual", 7_90_000),
                    VariantSpec("V", "Petrol", "CVT", 9_40_000),
                ),
            ),
            ModelSpec(
                "Hilux",
                "Pickup",
                (
                    VariantSpec("4x4 MT", "Diesel", "Manual", 3_300_000),
                    VariantSpec("4x4 AT", "Diesel", "Automatic", 3_800_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Honda",
        (
            ModelSpec(
                "City",
                "Sedan",
                (
                    VariantSpec("V", "Petrol", "Manual", 1_180_000),
                    VariantSpec("VX", "Petrol", "CVT", 1_400_000),
                    VariantSpec("ZX", "Petrol", "CVT", 1_620_000),
                ),
            ),
            ModelSpec(
                "Amaze",
                "Sedan",
                (
                    VariantSpec("E", "Petrol", "Manual", 8_10_000),
                    VariantSpec("VX", "Petrol", "CVT", 1_100_000),
                ),
            ),
            ModelSpec(
                "Elevate",
                "SUV",
                (
                    VariantSpec("V", "Petrol", "Manual", 1_100_000),
                    VariantSpec("ZX", "Petrol", "CVT", 1_500_000),
                ),
            ),
            ModelSpec(
                "WR-V",
                "SUV",
                (
                    VariantSpec("SV", "Petrol", "Manual", 9_00_000),
                    VariantSpec("VX", "Petrol", "CVT", 1_200_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Hyundai",
        (
            ModelSpec(
                "Creta",
                "SUV",
                (
                    VariantSpec("E", "Petrol", "Manual", 1_100_000),
                    VariantSpec("S", "Petrol", "Manual", 1_300_000),
                    VariantSpec("SX", "Petrol", "Automatic", 1_700_000),
                    VariantSpec("SX(O)", "Diesel", "Automatic", 2_000_000),
                ),
            ),
            ModelSpec(
                "Verna",
                "Sedan",
                (
                    VariantSpec("S", "Petrol", "Manual", 1_100_000),
                    VariantSpec("SX", "Petrol", "CVT", 1_500_000),
                ),
            ),
            ModelSpec(
                "Tucson",
                "SUV",
                (
                    VariantSpec("PL", "Petrol", "Automatic", 2_750_000),
                    VariantSpec("GLS", "Diesel", "Automatic", 3_100_000),
                ),
            ),
            ModelSpec(
                "i20",
                "Hatchback",
                (
                    VariantSpec("Magna", "Petrol", "Manual", 7_50_000),
                    VariantSpec("Asta", "Petrol", "DCT", 1_100_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Volkswagen",
        (
            ModelSpec(
                "Virtus",
                "Sedan",
                (
                    VariantSpec("Comfortline", "Petrol", "Manual", 1_120_000),
                    VariantSpec("Highline", "Petrol", "Automatic", 1_470_000),
                    VariantSpec("GT", "Petrol", "DSG", 1_800_000),
                ),
            ),
            ModelSpec(
                "Taigun",
                "SUV",
                (
                    VariantSpec("Comfortline", "Petrol", "Manual", 1_170_000),
                    VariantSpec("Topline", "Petrol", "Automatic", 1_700_000),
                    VariantSpec("GT", "Petrol", "DSG", 1_900_000),
                ),
            ),
            ModelSpec(
                "Tiguan",
                "SUV",
                (
                    VariantSpec("Comfortline", "Petrol", "Automatic", 3_300_000),
                    VariantSpec("Highline", "Petrol", "Automatic", 3_800_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Skoda",
        (
            ModelSpec(
                "Kushaq",
                "SUV",
                (
                    VariantSpec("Active", "Petrol", "Manual", 1_050_000),
                    VariantSpec("Style", "Petrol", "Automatic", 1_600_000),
                    VariantSpec("Monte Carlo", "Petrol", "Automatic", 1_750_000),
                ),
            ),
            ModelSpec(
                "Slavia",
                "Sedan",
                (
                    VariantSpec("Active", "Petrol", "Manual", 1_050_000),
                    VariantSpec("Style", "Petrol", "Automatic", 1_550_000),
                ),
            ),
            ModelSpec(
                "Kodiaq",
                "SUV",
                (
                    VariantSpec("Style", "Petrol", "Automatic", 3_800_000),
                    VariantSpec("L&K", "Petrol", "Automatic", 4_300_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Kia",
        (
            ModelSpec(
                "Seltos",
                "SUV",
                (
                    VariantSpec("HTE", "Petrol", "Manual", 1_090_000),
                    VariantSpec("GTX+", "Petrol", "Automatic", 1_700_000),
                    VariantSpec("X-Line", "Diesel", "Automatic", 1_950_000),
                ),
            ),
            ModelSpec(
                "Sonet",
                "SUV",
                (
                    VariantSpec("HTE", "Petrol", "Manual", 7_90_000),
                    VariantSpec("GTX+", "Diesel", "Automatic", 1_400_000),
                ),
            ),
            ModelSpec(
                "Carens",
                "Minivan",
                (
                    VariantSpec("Premium", "Petrol", "Manual", 1_050_000),
                    VariantSpec("Prestige", "Diesel", "Automatic", 1_500_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Ford",
        (
            ModelSpec(
                "EcoSport",
                "SUV",
                (
                    VariantSpec("Ambiente", "Petrol", "Manual", 7_90_000),
                    VariantSpec("Titanium", "Petrol", "Automatic", 1_150_000),
                ),
            ),
            ModelSpec(
                "Endeavour",
                "SUV",
                (
                    VariantSpec("Ambient", "Diesel", "Automatic", 3_300_000),
                    VariantSpec("Titanium", "Diesel", "Automatic", 3_700_000),
                    VariantSpec("Sport", "Diesel", "Automatic", 3_900_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Nissan",
        (
            ModelSpec(
                "Magnite",
                "SUV",
                (
                    VariantSpec("XE", "Petrol", "Manual", 6_00_000),
                    VariantSpec("XV", "Petrol", "CVT", 8_50_000),
                ),
            ),
            ModelSpec(
                "Kicks",
                "SUV",
                (
                    VariantSpec("XV", "Petrol", "Manual", 9_50_000),
                    VariantSpec("XV Premium", "Petrol", "CVT", 1_300_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "MG",
        (
            ModelSpec(
                "Hector",
                "SUV",
                (
                    VariantSpec("Style", "Petrol", "Manual", 1_400_000),
                    VariantSpec("Smart Pro", "Petrol", "CVT", 1_800_000),
                    VariantSpec("Sharp Pro", "Diesel", "Automatic", 2_100_000),
                ),
            ),
            ModelSpec(
                "Astor",
                "SUV",
                (
                    VariantSpec("Style", "Petrol", "Manual", 1_000_000),
                    VariantSpec("Sharp", "Petrol", "CVT", 1_500_000),
                ),
            ),
            ModelSpec(
                "Gloster",
                "SUV",
                (
                    VariantSpec("Sharp 2WD", "Diesel", "Automatic", 3_200_000),
                    VariantSpec("Savvy 4WD", "Diesel", "Automatic", 3_800_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Tata",
        (
            ModelSpec(
                "Nexon",
                "SUV",
                (
                    VariantSpec("XE", "Petrol", "Manual", 8_10_000),
                    VariantSpec("XZ+", "Petrol", "Automatic", 1_300_000),
                    VariantSpec("XZ+ Diesel", "Diesel", "Automatic", 1_500_000),
                ),
            ),
            ModelSpec(
                "Harrier",
                "SUV",
                (
                    VariantSpec("XE", "Diesel", "Manual", 1_500_000),
                    VariantSpec("XZA+", "Diesel", "Automatic", 2_100_000),
                ),
            ),
            ModelSpec(
                "Safari",
                "SUV",
                (
                    VariantSpec("XE", "Diesel", "Manual", 1_600_000),
                    VariantSpec("XZA+", "Diesel", "Automatic", 2_200_000),
                ),
            ),
            ModelSpec(
                "Punch",
                "SUV",
                (
                    VariantSpec("Pure", "Petrol", "Manual", 6_10_000),
                    VariantSpec("Creative", "Petrol", "AMT", 8_50_000),
                ),
            ),
        ),
    ),
    MakeSpec(
        "Mahindra",
        (
            ModelSpec(
                "XUV700",
                "SUV",
                (
                    VariantSpec("MX", "Petrol", "Manual", 1_400_000),
                    VariantSpec("AX7", "Petrol", "Automatic", 2_000_000),
                    VariantSpec("AX7 Diesel", "Diesel", "Automatic", 2_200_000),
                ),
            ),
            ModelSpec(
                "Thar",
                "SUV",
                (
                    VariantSpec("AX", "Petrol", "Manual", 1_100_000),
                    VariantSpec("LX", "Diesel", "Automatic", 1_800_000),
                ),
            ),
            ModelSpec(
                "Scorpio-N",
                "SUV",
                (
                    VariantSpec("Z2", "Diesel", "Manual", 1_200_000),
                    VariantSpec("Z8", "Diesel", "Automatic", 2_000_000),
                ),
            ),
        ),
    ),
)

# ---------------------------------------------------------------------------
# Dealers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DealerSpec:
    id: str
    name: str
    city: str
    state: str
    address: str
    phone: str
    email: str
    rating: float


DEALERS: Final = (
    DealerSpec(
        "D-001",
        "AutoNation Motors",
        "Mumbai",
        "Maharashtra",
        "12 Marine Drive",
        "+91-22-2204-1001",
        "sales@autonation.example",
        4.5,
    ),
    DealerSpec(
        "D-002",
        "DriveZone Auto",
        "Delhi",
        "Delhi",
        "45 Connaught Place",
        "+91-11-2301-1002",
        "info@drivezone.example",
        4.2,
    ),
    DealerSpec(
        "D-003",
        "Prestige Cars",
        "Bangalore",
        "Karnataka",
        "78 MG Road",
        "+91-80-2552-1003",
        "sales@prestigecars.example",
        4.7,
    ),
    DealerSpec(
        "D-004",
        "Highway Auto Hub",
        "Chennai",
        "Tamil Nadu",
        "23 Anna Salai",
        "+91-44-2431-1004",
        "contact@highwayauto.example",
        3.9,
    ),
    DealerSpec(
        "D-005",
        "GreenWheel Motors",
        "Hyderabad",
        "Telangana",
        "9 Banjara Hills",
        "+91-40-2345-1005",
        "hello@greenwheel.example",
        4.4,
    ),
    DealerSpec(
        "D-006",
        "Royal Drive",
        "Pune",
        "Maharashtra",
        "56 FC Road",
        "+91-20-2567-1006",
        "sales@royaldrive.example",
        4.1,
    ),
    DealerSpec(
        "D-007",
        "CityWheels",
        "Kolkata",
        "West Bengal",
        "32 Park Street",
        "+91-33-2486-1007",
        "enquiry@citywheels.example",
        3.8,
    ),
    DealerSpec(
        "D-008",
        "Star Auto Group",
        "Ahmedabad",
        "Gujarat",
        "14 Ashram Road",
        "+91-79-2656-1008",
        "info@starautogroup.example",
        4.3,
    ),
    DealerSpec(
        "D-009",
        "Trident Motors",
        "Jaipur",
        "Rajasthan",
        "67 Tonk Road",
        "+91-141-2701-1009",
        "sales@tridentmotors.example",
        4.0,
    ),
    DealerSpec(
        "D-010",
        "MileStar Auto",
        "Chandigarh",
        "Chandigarh",
        "10 Sector 17",
        "+91-172-2701-1010",
        "contact@milestar.example",
        4.6,
    ),
    DealerSpec(
        "D-011",
        "Summit Motors",
        "Lucknow",
        "Uttar Pradesh",
        "8 Hazratganj",
        "+91-522-2301-1011",
        "sales@summitmotors.example",
        3.7,
    ),
    DealerSpec(
        "D-012",
        "Apex AutoCare",
        "Indore",
        "Madhya Pradesh",
        "19 MG Road",
        "+91-731-2551-1012",
        "",
        4.1,
    ),
    DealerSpec(
        "D-013",
        "OpenRoad Auto",
        "Nagpur",
        "Maharashtra",
        "31 Dharampeth",
        "+91-712-2541-1013",
        "sales@openroad.example",
        4.8,
    ),
    DealerSpec(
        "D-014",
        "Zenith CarPoint",
        "Surat",
        "Gujarat",
        "5 Athwa Lines",
        "+91-261-2411-1014",
        "info@zenithcarpoint.example",
        3.6,
    ),
)

# D-012 deliberately has an empty email — tests "incomplete dealer details".
# D-013 deliberately gets zero cars — tests "dealer with no cars".
EDGE_CASE_EMPTY_DEALER_ID: Final = "D-013"
EDGE_CASE_INCOMPLETE_DEALER_ID: Final = "D-012"

# ---------------------------------------------------------------------------
# Feature pools (semicolon-separated in the CSV)
# ---------------------------------------------------------------------------

_FEATURES_BY_BODY: dict[str, tuple[str, ...]] = {
    "Sedan": (
        "Sunroof",
        "Leather seats",
        "Rear camera",
        "Touchscreen infotainment",
        "Apple CarPlay",
        "Android Auto",
        "Cruise control",
        "Alloy wheels",
        "Keyless entry",
        "Push-button start",
        "Auto climate control",
        "LED headlights",
        "Electronic stability control",
        "Hill assist",
    ),
    "SUV": (
        "Sunroof",
        "Leather seats",
        "Rear camera",
        "Touchscreen infotainment",
        "Apple CarPlay",
        "Android Auto",
        "Cruise control",
        "Alloy wheels",
        "Roof rails",
        "Hill descent control",
        "All-wheel drive",
        "Towing package",
        "Electronic parking brake",
        "Ambient lighting",
    ),
    "Hatchback": (
        "Rear camera",
        "Touchscreen infotainment",
        "Apple CarPlay",
        "Alloy wheels",
        "Cruise control",
        "Keyless entry",
        "Push-button start",
        "Auto climate control",
        "LED DRLs",
    ),
    "Coupe": (
        "Sunroof",
        "Leather seats",
        "Sport suspension",
        "Touchscreen infotainment",
        "Apple CarPlay",
        "Alloy wheels",
        "Performance brakes",
        "Launch control",
        "Paddle shifters",
    ),
    "Convertible": (
        "Leather seats",
        "Touchscreen infotainment",
        "Wind deflector",
        "Alloy wheels",
        "Sport suspension",
        "Rain-sensing wipers",
        "Dual-zone climate",
        "Ambient lighting",
    ),
    "Pickup": (
        "Rear camera",
        "Touchscreen infotainment",
        "Towing package",
        "Bed liner",
        "All-wheel drive",
        "Cruise control",
        "Alloy wheels",
        "Hill descent control",
        "Trailer sway control",
    ),
    "Minivan": (
        "Rear camera",
        "Touchscreen infotainment",
        "Third-row seating",
        "Power sliding doors",
        "Apple CarPlay",
        "Rear entertainment",
        "Cabin air filter",
        "Multiple USB ports",
    ),
    "Wagon": (
        "Sunroof",
        "Leather seats",
        "Roof rails",
        "Touchscreen infotainment",
        "Apple CarPlay",
        "Cruise control",
        "Power tailgate",
        "All-wheel drive",
        "Ambient lighting",
    ),
}

# ---------------------------------------------------------------------------
# Aliases
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AliasRow:
    alias_type: str  # "make" | "model" | "variant"
    alias: str
    make: str
    model: str
    variant: str


def _build_aliases() -> list[AliasRow]:
    rows: list[AliasRow] = []

    def _add(atype: str, alias: str, make: str = "", model: str = "", variant: str = "") -> None:
        rows.append(AliasRow(atype, alias, make, model, variant))

    # --- make aliases ---
    _add("make", "BMW", "BMW")
    _add("make", "B.M.W.", "BMW")
    _add("make", "Merc", "Mercedes-Benz")
    _add("make", "Mercedes", "Mercedes-Benz")
    _add("make", "Benz", "Mercedes-Benz")
    _add("make", "Audi", "Audi")
    _add("make", "Toyota", "Toyota")
    _add("make", "Honda", "Honda")
    _add("make", "Hyundai", "Hyundai")
    _add("make", "Volkswagen", "Volkswagen")
    _add("make", "VW", "Volkswagen")
    _add("make", "Skoda", "Skoda")
    _add("make", "Kia", "Kia")
    _add("make", "Ford", "Ford")
    _add("make", "Nissan", "Nissan")
    _add("make", "MG", "MG")
    _add("make", "Tata", "Tata")
    _add("make", "Mahindra", "Mahindra")

    # --- model aliases ---
    _add("model", "C Class", "Mercedes-Benz", "C-Class")
    _add("model", "E Class", "Mercedes-Benz", "E-Class")
    _add("model", "BMW 3 Series", "BMW", "3 Series")
    _add("model", "BMW 5 Series", "BMW", "5 Series")
    _add("model", "Innova", "Toyota", "Innova Crysta")
    _add("model", "City Sedan", "Honda", "City")
    _add("model", "Hyundai Creta", "Hyundai", "Creta")
    _add("model", "Volkswagen Virtus", "Volkswagen", "Virtus")
    _add("model", "Skoda Kushaq", "Skoda", "Kushaq")

    # --- variant aliases ---
    _add("variant", "amg", "Mercedes-Benz", "C-Class", "AMG C43")
    _add("variant", "4x4 AT", "Toyota", "Fortuner", "4x4")
    _add("variant", "Automatic", "BMW", "3 Series", "330i")
    _add("variant", "SX (O)", "Hyundai", "Creta", "SX(O)")
    _add("variant", "ds", "Volkswagen", "Virtus", "GT")
    _add("variant", "DSG", "Volkswagen", "Taigun", "GT")

    return rows


ALIASES: Final = _build_aliases()

# ---------------------------------------------------------------------------
# Edge-case manifest — a car whose dealer row does NOT exist (intentional
# referential-integrity violation).  -04 suffix matches the plan's numbering.
# ---------------------------------------------------------------------------

EDGE_CASE_DANGLING_CAR_ID: Final = "C-9004"
EDGE_CASE_DANGLING_DEALER_ID: Final = "D-999"

# Car that intentionally has NO variant — exercises variant-optional search.
EDGE_CASE_VARIANTLESS_CAR_ID: Final = "C-9002"


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


def _next_car_id(counter: int) -> str:
    return f"C-{counter:04d}"


def _pick_dealer(rng: random.Random, dealer_ids: list[str]) -> str:
    return rng.choice(dealer_ids)


def _pick_features(rng: random.Random, body: str) -> str:
    pool = _FEATURES_BY_BODY.get(body, _FEATURES_BY_BODY["SUV"])
    count = rng.randint(3, min(6, len(pool)))
    selected = rng.sample(sorted(pool), k=count)  # sorted for determinism
    return ";".join(selected)


def _price_variance(rng: random.Random, base: int) -> tuple[int, int]:
    low = base
    high = int(base * (1 + rng.uniform(0.05, 0.20)))
    # round to nearest 10_000
    low = round(low / 10_000) * 10_000
    high = round(high / 10_000) * 10_000
    if high == low:
        high = low + 10_000
    return low, high


def _mileage(rng: random.Random, year: int) -> int:
    age = 2025 - year
    base_km = age * rng.randint(5_000, 15_000)
    return max(1_000, round(base_km / 1_000) * 1_000)


def _year_range(rng: random.Random, model_idx: int) -> list[int]:
    """Return a deterministic list of 1–3 year values for a given model index."""
    earliest = 2019
    latest = 2024
    span = latest - earliest
    # Use model_idx to create variation
    base = earliest + (model_idx * 7) % span
    years = [base]
    if (model_idx * 3) % 5 == 0 and base + 1 <= latest:
        years.append(base + 1)
    if (model_idx * 11) % 7 == 0 and base + 2 <= latest:
        years.append(base + 2)
    return [y for y in years if earliest <= y <= latest]


def generate(seed: int = SEED) -> dict[str, list[dict[str, str]]]:
    """Build all three CSVs in memory. Returns dict with keys 'cars', 'dealers', 'aliases'."""
    rng = random.Random(seed)

    # --- dealers ---
    dealer_rows: list[dict[str, str]] = []
    for d in DEALERS:
        dealer_rows.append(
            {
                "dealer_id": d.id,
                "dealer_name": d.name,
                "city": d.city,
                "state": d.state,
                "address": d.address,
                "phone": d.phone,
                "email": d.email,
                "rating": f"{d.rating:.1f}",
            }
        )

    dealer_ids = [d.id for d in DEALERS if d.id not in (EDGE_CASE_DANGLING_DEALER_ID,)]
    # D-013 deliberately stays in dealer_ids but gets zero cars via the assignment below.
    # We exclude the dangling dealer id D-999 which is never in DEALERS.

    # --- cars ---
    car_rows: list[dict[str, str]] = []
    counter = 1

    model_idx = 0
    for make in CATALOGUE:
        for model in make.models:
            years = _year_range(rng, model_idx)
            for vs in model.variants:
                for year in years:
                    pid = _next_car_id(counter)
                    counter += 1
                    price_min, price_max = _price_variance(rng, vs.price_base)
                    mil = _mileage(rng, year)
                    feat = _pick_features(rng, model.body)
                    # Skip D-013 so it has zero cars (edge case).
                    assigned_dealer = _pick_dealer(
                        rng, [d for d in dealer_ids if d != EDGE_CASE_EMPTY_DEALER_ID]
                    )
                    car_rows.append(
                        {
                            "car_id": pid,
                            "make": make.name,
                            "model": model.name,
                            "variant": vs.name,
                            "year": str(year),
                            "fuel_type": vs.fuel,
                            "transmission": vs.transmission,
                            "body_type": model.body,
                            "price_min": str(price_min),
                            "price_max": str(price_max),
                            "mileage_km": str(mil),
                            "features": feat,
                            "dealer_id": assigned_dealer,
                        }
                    )
            model_idx += 1

    # --- edge-case rows appended at the end ---

    # EC-02: car with NO variant at all
    car_rows.append(
        {
            "car_id": EDGE_CASE_VARIANTLESS_CAR_ID,
            "make": "Nissan",
            "model": "Kicks",
            "variant": "",
            "year": "2023",
            "fuel_type": "Petrol",
            "transmission": "CVT",
            "body_type": "SUV",
            "price_min": "10_00_000",
            "price_max": "11_50_000",
            "mileage_km": "18000",
            "features": "Rear camera;Touchscreen infotainment;Alloy wheels",
            "dealer_id": EDGE_CASE_EMPTY_DEALER_ID,  # D-013 already has zero; this gives it one.
        }
    )
    # Correction: D-013 is "dealer with no cars" — but we just gave it one.
    # Per plan, "a dealer with no cars" = a dealer that has ZERO cars.
    # So the variantless car must NOT go to D-013.
    # Let's fix: assign it to a normal dealer.
    car_rows[-1]["dealer_id"] = "D-010"

    # EC-03: car whose dealer does NOT exist in dealers.csv
    car_rows.append(
        {
            "car_id": EDGE_CASE_DANGLING_CAR_ID,
            "make": "Tata",
            "model": "Punch",
            "variant": "Creative S",
            "year": "2024",
            "fuel_type": "Petrol",
            "transmission": "AMT",
            "body_type": "SUV",
            "price_min": "9_50_000",
            "price_max": "10_50_000",
            "mileage_km": "500",
            "features": "Rear camera;Touchscreen infotainment;Alloy wheels;Keyless entry",
            "dealer_id": EDGE_CASE_DANGLING_DEALER_ID,  # D-999 — does not exist!
        }
    )

    # --- aliases ---
    alias_rows: list[dict[str, str]] = []
    for a in ALIASES:
        alias_rows.append(
            {
                "alias_type": a.alias_type,
                "alias": a.alias,
                "make": a.make,
                "model": a.model,
                "variant": a.variant,
            }
        )

    return {"cars": car_rows, "dealers": dealer_rows, "aliases": alias_rows}


# ---------------------------------------------------------------------------
# CSV writing
# ---------------------------------------------------------------------------


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_all(data: dict[str, list[dict[str, str]]], output_dir: Path | None = None) -> None:
    out = output_dir or DATA_DIR
    _write_csv(out / "cars.csv", CARS_COLUMNS, data["cars"])
    _write_csv(out / "dealers.csv", DEALERS_COLUMNS, data["dealers"])
    _write_csv(out / "aliases.csv", ALIASES_COLUMNS, data["aliases"])


# ---------------------------------------------------------------------------
# --check mode
# ---------------------------------------------------------------------------


class _CheckError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _check_file_exists(path: Path, label: str) -> None:
    if not path.exists():
        raise _CheckError(f"{label}: file does not exist at {path}")
    if path.stat().st_size == 0:
        raise _CheckError(f"{label}: file is empty ({path})")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _check_headers(path: Path, expected: tuple[str, ...], label: str) -> list[dict[str, str]]:
    rows = _read_csv(path)
    if not rows:
        raise _CheckError(f"{label}: no data rows")
    actual = tuple(rows[0].keys())
    if actual != expected:
        raise _CheckError(
            f"{label}: header mismatch.\n  expected: {expected}\n  actual:   {actual}"
        )
    return rows


def check(output_dir: Path | None = None) -> list[str]:
    """Validate fixtures. Returns list of findings (info or error messages).

    Raises _CheckError on any hard failure.
    """
    out = output_dir or DATA_DIR
    findings: list[str] = []

    # 1. File existence
    for path, label in [
        (out / "cars.csv", "cars.csv"),
        (out / "dealers.csv", "dealers.csv"),
        (out / "aliases.csv", "aliases.csv"),
    ]:
        _check_file_exists(path, label)

    # 2. Headers + read
    car_rows = _check_headers(out / "cars.csv", CARS_COLUMNS, "cars.csv")
    dealer_rows = _check_headers(out / "dealers.csv", DEALERS_COLUMNS, "dealers.csv")
    alias_rows = _check_headers(out / "aliases.csv", ALIASES_COLUMNS, "aliases.csv")

    findings.append(f"cars.csv:    {len(car_rows)} rows")
    findings.append(f"dealers.csv: {len(dealer_rows)} rows")
    findings.append(f"aliases.csv: {len(alias_rows)} rows")

    # 3. Dealer IDs
    dealer_ids = {r["dealer_id"] for r in dealer_rows}
    if len(dealer_ids) != len(dealer_rows):
        raise _CheckError("dealers.csv: duplicate dealer_id")
    for d in dealer_rows:
        if not d["dealer_id"].startswith("D-"):
            raise _CheckError(f"dealers.csv: invalid dealer_id format: {d['dealer_id']}")
        if not d["dealer_name"]:
            raise _CheckError(f"dealers.csv: empty dealer_name for {d['dealer_id']}")

    # 4. Car IDs + basic validation
    car_ids: set[str] = set()
    for r in car_rows:
        cid = r["car_id"]
        if cid in car_ids:
            raise _CheckError(f"cars.csv: duplicate car_id {cid}")
        car_ids.add(cid)
        if not r["make"] or not r["model"]:
            raise _CheckError(f"cars.csv: empty make/model in {cid}")
        if r["fuel_type"] not in VALID_FUEL_TYPES:
            raise _CheckError(f"cars.csv: invalid fuel_type '{r['fuel_type']}' in {cid}")
        if r["transmission"] not in VALID_TRANSMISSIONS:
            raise _CheckError(f"cars.csv: invalid transmission '{r['transmission']}' in {cid}")
        if r["body_type"] not in VALID_BODY_TYPES:
            raise _CheckError(f"cars.csv: invalid body_type '{r['body_type']}' in {cid}")
        try:
            year = int(r["year"])
            if not (2015 <= year <= 2030):
                raise _CheckError(f"cars.csv: year {year} out of range in {cid}")
        except ValueError as exc:
            raise _CheckError(f"cars.csv: non-integer year in {cid}") from exc

    # 5. Referential integrity — every cars.dealer_id must exist in dealers
    dangling_expected = {EDGE_CASE_DANGLING_DEALER_ID}
    actual_missing: set[str] = set()
    for r in car_rows:
        did = r["dealer_id"]
        if did not in dealer_ids:
            actual_missing.add(did)
    if actual_missing != dangling_expected:
        unexpected = actual_missing - dangling_expected
        missing = dangling_expected - actual_missing
        parts: list[str] = []
        if unexpected:
            parts.append(f"unexpected dangling dealer_ids: {unexpected}")
        if missing:
            parts.append(f"expected dangling dealer_id(s) not found: {missing}")
        raise _CheckError("cars.csv: referential integrity — " + "; ".join(parts))

    # 6. Dealer with no cars
    cars_with_dealer = {r["dealer_id"] for r in car_rows}
    carless = dealer_ids - cars_with_dealer
    if EDGE_CASE_EMPTY_DEALER_ID not in carless:
        raise _CheckError(
            f"cars.csv: expected dealer {EDGE_CASE_EMPTY_DEALER_ID} to have zero cars, but it has cars"
        )
    findings.append(f"car-less dealers (expected 1): {sorted(carless)}")

    # 7. Incomplete dealer (email is empty)
    incomplete_dealers = [r for r in dealer_rows if not r["email"]]
    incomplete_ids = {r["dealer_id"] for r in incomplete_dealers}
    if EDGE_CASE_INCOMPLETE_DEALER_ID not in incomplete_ids:
        raise _CheckError(
            f"dealers.csv: expected dealer {EDGE_CASE_INCOMPLETE_DEALER_ID} to have empty email"
        )
    findings.append(f"incomplete dealers (expected 1): {sorted(incomplete_ids)}")

    # 8. Variantless car
    variantless = [r for r in car_rows if not r["variant"]]
    if not variantless:
        raise _CheckError("cars.csv: expected at least one car with empty variant")
    findings.append(f"variantless car ids: {[r['car_id'] for r in variantless]}")

    # 9. Duplicate make/model with differing variant (disambiguation)
    from collections import defaultdict

    make_model_variants: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in car_rows:
        make_model_variants[(r["make"], r["model"])].add(r["variant"])
    multi_variant = {k: v for k, v in make_model_variants.items() if len(v) > 1}
    if not multi_variant:
        raise _CheckError("cars.csv: no make/model pair has >1 variant (disambiguation impossible)")
    findings.append(f"multi-variant make/model pairs: {len(multi_variant)}")
    for (m, mod), variants in sorted(multi_variant.items())[:3]:
        findings.append(f"  {m} {mod}: {sorted(variants)}")

    # 10. Alias validation
    for a in alias_rows:
        if a["alias_type"] not in ("make", "model", "variant"):
            raise _CheckError(f"aliases.csv: invalid alias_type '{a['alias_type']}'")
        if not a["alias"]:
            raise _CheckError(f"aliases.csv: empty alias in row {a}")
        if a["alias_type"] == "make" and not a["make"]:
            raise _CheckError(f"aliases.csv: make alias without target make: {a['alias']}")
        if a["alias_type"] == "model" and (not a["make"] or not a["model"]):
            raise _CheckError(f"aliases.csv: model alias without full target: {a['alias']}")
        if a["alias_type"] == "variant" and (not a["make"] or not a["model"] or not a["variant"]):
            raise _CheckError(f"aliases.csv: variant alias without full target: {a['alias']}")
        # A make alias that equals its canonical target is fine — it makes the
        # canonical form queryable through search_by_alias.  Only flag self-aliases
        # for model/variant aliases where the alias would be redundant with
        # direct lookup.
        if a["alias_type"] == "model" and a["alias"] == a["model"]:
            raise _CheckError(f"aliases.csv: self-alias for model '{a['alias']}'")
        if a["alias_type"] == "variant" and a["alias"] == a["variant"]:
            raise _CheckError(f"aliases.csv: self-alias for variant '{a['alias']}'")
    findings.append(f"aliases validated: {len(alias_rows)} rows")

    # 11. File hash (informational, for cross-run determinism verification)
    for fname in ("cars.csv", "dealers.csv", "aliases.csv"):
        content = (out / fname).read_bytes()
        sha = hashlib.sha256(content).hexdigest()[:12]
        findings.append(f"{fname} sha256[:12] = {sha}")

    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate (or validate) car-dealer chatbot fixture CSVs."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate existing fixtures without rewriting.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: <repo>/data).",
    )
    args = parser.parse_args(argv)

    if args.check:
        try:
            findings = check(args.output_dir)
            print("=== CHECK PASSED ===")
            for f in findings:
                print(f"  {f}")
            return 0
        except _CheckError as exc:
            print(f"=== CHECK FAILED ===\n  {exc.message}", file=sys.stderr)
            return 1

    # Generate + write
    data = generate()
    write_all(data, args.output_dir)
    print(
        f"Generated: {len(data['cars'])} cars, {len(data['dealers'])} dealers, {len(data['aliases'])} aliases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
