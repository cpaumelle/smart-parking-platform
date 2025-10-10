# unpackers/registry.py
# Version: 0.3.0 - 2025-07-21 05:50 UTC
# Changelog:
# - Synced with device_types table
# - Added unpackers: merryiot_ms10, browan_tbms100, browan_tbdw100, imbuildings_pc1

from unpackers.environment.browan_tbhh100 import unpack as unpack_browan_tbhh100
from unpackers.environment.milesight_am103 import unpack as unpack_milesight_am103
from unpackers.environment.merryiot_co2 import unpack as unpack_merryiot_co2

from unpackers.monitoring.browan_tbdw import unpack as unpack_browan_tbdw
from unpackers.monitoring.browan_tbwl import unpack as unpack_browan_tbwl
from unpackers.monitoring.browan_tbms100 import unpack as unpack_browan_tbms100 
from unpackers.monitoring.merryiot_ms10 import unpack as unpack_merryiot_ms10 


from unpackers.monitoring.winext_an102c import unpack as unpack_winext_an102c

from unpackers.buttons.smilio_a_s import unpack as unpack_smilio_a_s

from unpackers.network.atim_acw_lw8 import unpack as unpack_atim_acw_lw8
from unpackers.network.netvox_r716 import unpack as unpack_netvox_r716

from unpackers.monitoring.imbuildings_pc1 import unpack as unpack_imbuildings_pc1

UNPACKER_REGISTRY = {
    "browan_tbhh100": unpack_browan_tbhh100,
    "milesight_am103": unpack_milesight_am103,
    "merryiot_co2": unpack_merryiot_co2,
    "merryiot_ms10": unpack_merryiot_ms10,
    "browan_tbms100": unpack_browan_tbms100,
    "browan_tbdw100": unpack_browan_tbdw,
    "browan_tbdw": unpack_browan_tbdw,
    "browan_tbwl": unpack_browan_tbwl,
    "winext_an102c": unpack_winext_an102c,
    "smilio_a_s": unpack_smilio_a_s,
    "atim_acw_lw8": unpack_atim_acw_lw8,
    "netvox_r716": unpack_netvox_r716,
    "imbuildings_pc1": unpack_imbuildings_pc1,
    "milesight_am103": unpack_milesight_am103, 
}

def get_unpacker(name: str):
    return UNPACKER_REGISTRY.get(name.strip())