"""External data sources: rainfall from public weather APIs.

    python -m external.rainfall --help

Everything here is OPTIONAL. The system measures its own rainfall with the
tipping bucket on the ESP32; these sources fill gaps and provide the forecast
leg, and nothing breaks when they are unreachable.
"""
