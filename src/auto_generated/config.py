import math

DOMAIN_NAME = 'ethylene_conversion'
DOMAIN_DESCRIPTION = 'Extraction of catalytic data for ethylene conversion reactions, including catalyst properties and performance metrics.'
INPUT_MARKDOWN_DIR = 'markdowns/'

SUB_DOMAIN_NAMES = {
    "catalyst": "Catalyst Properties",
    "conditions": "Reaction Conditions",
    "performance": "Catalytic Performance",
    "metadata": "Paper Metadata"
}

VALIDATION_BOUNDS = {'catalyst.surface_area': {'min': 0.1, 'max': 3000, 'target_unit': 'm2/g', 'allowed_units': ['m2/g', 'm²/g']}, 'conditions.temperature': {'min': -50, 'max': 1500, 'target_unit': 'Celsius', 'allowed_units': ['Celsius', 'Kelvin']}, 'conditions.pressure': {'min': 0.01, 'max': 1000, 'target_unit': 'atm', 'allowed_units': ['atm', 'bar', 'MPa', 'psi', 'kPa']}, 'conditions.space_velocity': {'min': 0.01, 'max': 1000000, 'target_unit': 'h-1', 'allowed_units': ['h-1', 'mL/g/h', 'L/kg/h', 'WHSV', 'GHSV']}, 'conditions.testing_time': {'min': 0.01, 'max': 10000, 'target_unit': 'hours', 'allowed_units': ['hours', 'days', 'minutes']}, 'performance.ethylene_conversion': {'min': 0, 'max': 100, 'target_unit': '%', 'allowed_units': ['%']}, 'performance.c8_c16_selectivity': {'min': 0, 'max': 100, 'target_unit': '%', 'allowed_units': ['%']}, 'performance.isomers_selectivity': {'min': 0, 'max': 100, 'target_unit': '%', 'allowed_units': ['%']}, 'performance.yield': {'min': 0, 'max': 100, 'target_unit': '%', 'allowed_units': ['%']}, 'performance.reaction_rate': {'min': 0, 'max': None, 'target_unit': 'mol/g/h', 'allowed_units': ['mol/g/h', 'mmol/g/h', 'g/g/h']}, 'performance.turnover_frequency': {'min': 0, 'max': None, 'target_unit': 's-1', 'allowed_units': ['s-1', 'h-1']}, 'metadata.year_of_publication': {'min': 1900, 'max': 2100, 'target_unit': None, 'allowed_units': []}}

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
