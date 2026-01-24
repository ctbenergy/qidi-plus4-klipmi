"""
Copyright 2024 Joe Maples <joe@maples.dev>

This file is part of klipmi.

klipmi is free software: you can redistribute it and/or modify it under the
terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

klipmi is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
klipmi. If not, see <https://www.gnu.org/licenses/>. 
"""

from typing import Dict, List
from klipmi.model.ui import BaseUi
from klipmi.utils.utils import classproperty
from .pages import *

class OpenP4UI(BaseUi):
    @classproperty
    def printerObjects(cls) -> Dict[str, List[str]]:
        # https://moonraker.readthedocs.io/en/latest/printer_objects
        return {
            "motion_report": ["live_position", "live_velocity"],
            "gcode_move": ["extrude_factor", "speed_factor", "homing_origin"],
            "extruder": ["temperature", "target"],
            "heater_bed": ["temperature", "target"],
            "fan": ["speed"],
            "heater_generic chamber": ["temperature", "target"],
            "print_stats": [
                "filename",
                "total_duration",
                "print_duration",
                "filename_used",
                "state",
                "message",
                "info",
            ],
            "display_status": ["progress"],
            "output_pin caselight": ["value"],
            #"output_pin sound": ["value"],

            # Fans
            "fan_generic cooling_fan": ["speed"],           # Part cooling
            "fan_generic auxiliary_cooling_fan": ["speed"], # Auxiliary cooling
            "fan_generic exhaust_fan": ["speed"],           # Exhaust fan
            "heater_fan hotend_fan": ["speed"],             # Hotend fan
            "heater_fan chamber_fan": ["speed"],            # Chamber fan
            "fan_generic exhaust_fan": ["speed"],           # Exhaust fan
        }

    def onNotReady(self):
        self.changePage(BootPage)

    def onReady(self):
        self.changePage(MainPage)
        pass

    def onStopped(self):
        pass

    def onMoonrakerError(self):
        pass

    def onKlipperError(self):
        self.changePage(ResetPage)
        pass
