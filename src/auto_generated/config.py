import math

DOMAIN_NAME = 'ethylene_conversion'
DOMAIN_DESCRIPTION = 'Extraction of catalyst identity, preparation, characterization, and ethylene reaction conditions.'
INPUT_MARKDOWN_DIR = 'markdowns/'
TARGET_REACTION = 'oligomerization of ethylene to produce C6-C12 olefins, or any reaction involving ethylene conversion to higher hydrocarbons.'

SUB_DOMAIN_NAMES = {
    "catalyst": "Catalyst Properties",
    "conditions": "Reaction Conditions"
}

VALIDATION_BOUNDS = {'catalyst.surface_area': {'min': 0, 'max': 3000, 'target_unit': None, 'allowed_units': ['m2/g', 'm²/g']}, 'conditions.temperature': {'min': -50, 'max': 1500, 'target_unit': 'Celsius', 'allowed_units': ['Celsius', 'Kelvin']}, 'conditions.total_pressure': {'min': 0.01, 'max': 1000, 'target_unit': 'atm', 'allowed_units': ['atm', 'bar', 'MPa', 'psi', 'kPa']}, 'conditions.ethylene_partial_pressure': {'min': 0.01, 'max': 1000, 'target_unit': 'atm', 'allowed_units': ['atm', 'bar', 'MPa', 'psi', 'kPa']}, 'conditions.whsv': {'min': 0.01, 'max': 1000000, 'target_unit': None, 'allowed_units': ['h-1', 'h⁻¹', 'g_feed/g_cat/h', 'g_feed g_cat-1 h-1', 'WHSV']}, 'conditions.ghsv': {'min': 0.01, 'max': 1000000, 'target_unit': None, 'allowed_units': ['h-1', 'h⁻¹', 'mL/g/h', 'L/kg/h', 'mL/mL/h', 'cm3/cm3/h', 'GHSV']}, 'conditions.time_on_stream': {'min': 0.01, 'max': 10000, 'target_unit': 'hours', 'allowed_units': ['hours', 'days', 'minutes', 'seconds']}}

UNIT_CONVERSIONS = {
    ('K', 'Celsius'): lambda x: x - 273.15,
    ('Kelvin', 'Celsius'): lambda x: x - 273.15,
    ('Fahrenheit', 'Celsius'): lambda x: (x - 32) * 5.0/9.0,
    ('kg', 'g'): lambda x: x * 1000.0,
    ('mg', 'g'): lambda x: x / 1000.0,
    ('lb', 'g'): lambda x: x * 453.592,
    ('minutes', 'hours'): lambda x: x / 60.0,
    ('seconds', 'hours'): lambda x: x / 3600.0,
    ('days', 'hours'): lambda x: x * 24.0,
    ('L/min', 'mL/min'): lambda x: x * 1000.0,
    ('L/h', 'mL/min'): lambda x: x * 1000.0 / 60.0,
    ('cm3/min', 'mL/min'): lambda x: x,
    ('bar', 'atm'): lambda x: x * 0.986923,
    ('kPa', 'atm'): lambda x: x / 101.325,
    ('MPa', 'atm'): lambda x: x * 9.86923,
    ('psi', 'atm'): lambda x: x / 14.6959,
    ('mmol/g', 'umol/g'): lambda x: x * 1000.0,
    ('h-1', 's-1'): lambda x: x / 3600.0,
}

VALIDATION_RULES = []

CONFIDENCE_SCALE = {5: 'Explicitly stated with exact values and units', 4: 'Clearly inferable from context or figures', 3: 'Requires some interpretation or minor ambiguity', 2: 'High ambiguity or missing key information', 1: 'Could not be confidently extracted'}

REVIEW_THRESHOLD = 3
