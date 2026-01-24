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

import asyncio

from PIL.Image import init
from nextion import EventType

from klipmi.model.ui import BasePage
from klipmi.utils import classproperty

import logging


HMI_VERSION_MAJOR = '1' # version when you make incompatible API changes
HMI_VERSION_MINOR = '7' # version when you add functionality in a backward compatible manner
HMI_VERSION_PATCH = '1' # version when you make backward compatible bug fixes

MAX_EXTRUDER_TEMP = 370
MAX_HEATER_BED_TEMP = 120
MAX_CHAMBER_TEMP = 60


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


async def check_component_vis(self, component_name: str) -> bool:
    try:
        # Try to get the visibility value of the component
        await self.state.display.get(f"{component_name}.vis")
        return True
    except:
        return False

class HeaterManager:
    HEATERS = {
        "extruder": {
            "name": "extruder",
            "title": "Extruder",
            "max_digits": 3
        },
        "bed": {
            "name": "heater_bed", 
            "title": "Bed",
            "max_digits": 2
        },
        "chamber": {
            "name": "chamber",
            "title": "Chamber",
            "max_digits": 2
        }
    }

    heater_data = None

    def __init__(self, printer):
        self.printer = printer

    def set_temperature(self, heater: str, temperature: int):
        self.printer.runMacro("SET_HEATER_TEMPERATURE", 
                             HEATER=heater, 
                             TARGET=temperature)
        self.heater_data = None


    def get_heater_config(self, heater_key: str) -> dict:
        heater = self.HEATERS[heater_key]
        return {
            "name": heater["name"],
            "title": heater["title"],
            "max_digits": heater["max_digits"],
            "callback": lambda t: self.set_temperature(heater["name"], t)
        }
    
    def set_heater_data(self, heater_key: str):
        self.heater_data = self.get_heater_config(heater_key)
        

class OpenP4Page(BasePage):

    _current_page_id = 0
    _previous_page_id = 0

    _numeric_input = 0
    _first_into_tool = 0
    _set_mode = "Language"

    _page_files_pages = 0
    _page_files_current_pages = 0
    _page_files_folder_layers = 0
    _file_list_refreshed = 0
    _file_mode = "Local"

    _printer_bed_leveling = 0

    _show_preview_complete = 0

    _printer_ready = 0
    _printer_muted = 0
    _mute_setted = 0

    _main_picture_detected = 0
    _main_picture_refreshed = 0

    _preview_pop_1_on = 0
    _preview_pop_2_on = 0

    _current_time = 0 #puVar20 = (undefined4 *)time((time_t *)0x0);
    _calibrate_step = 0
    _calibrate_last_time = 0 #puVar20 = (undefined4 *)time((time_t *)0x0);

    _on_process = 0
    _auto_level_button_enabled = 0

    _page_wifi_current_pages = 0
    _page_wifi_list_ssid_button_enabled = 0
    _printing_wifi_keyboard_enabled = 0

    _qr_enabled = 0
    _m_device = 0

    _preview_pop_1_on = 0
    _preview_pop_2_on = 0

    _drying_step = 0

    _page_filament_extrude_button = 0

    _load_mode = 0
    _load_target = 0
    _load_position_inited = 0
    _unload_step = 0
    _unload_finished = 0

    _move_fan_setting = 0

    _printer_move_dist = 0.0
    _printer_filament_extruedr_dist = 0.0

    _printer_webhooks_state = "shutdown"

    _unhomed_move_mode = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not hasattr(self.state, 'heater_manager'):
            self.state.heater_manager = HeaterManager(self.state.printer)
        if not hasattr(self.state, 'return_page'):
            self.state.return_page = MainPage

    def handleNavBarButtons(self, component_id: int):
        if component_id == 33: #t33.txt="Home"
            # 0x21 go_to_main();
            self.changePage(MainPage)
        elif component_id == 34: #t34.txt="Ctrl"
            # 0x22 go_to_control();
            self.changePage(ControlPage)
        elif component_id == 35: #t35.txt="Doc"
            # 0x23 go_to_file_list();
            self.changePage(FileListPage)
        elif component_id == 36: #t36.txt="Tool"
            # 0x24 go_to_adjust();
            self.changePage(ToolSelectPage)
        elif component_id == 37: #t37.txt="Set"
            # 0x25 go_to_setting();
            self.changePage(LanguagePage)

    def handleScreenSleep(self, page_id: int):
        if page_id == 43: # screen_sleep
            log.info(f"handleScreenSleep: current page class: {self.__class__}")
            self.state.return_page = self.__class__  # Store current page class
            #self._previous_page_id = self._current_page_id;
            #self._current_page_id = param_1;
            self.changePage(ScreenSleepPage)

    def go_to_main(self):
        state = self.data["print_stats"]["state"]
        if state == "printing" or state == "paused":
            self.changePage(PrintingPage)
        else:
            self.changePage(MainPage)

    def go_to_control(self):
        pass

    def go_to_file_list(self):
        self._first_into_tool = 1
        if self._file_mode == "Local":
            self.changePage(FileListPage)
            if self._file_list_refreshed != 1:
                self._page_files_pages = 0
                self._page_files_current_pages = 0
                self._page_files_folder_layers = 0
                self._page_files_previous_path = ""
                self._page_files_root_path = "gcodes/"
                self._page_files_path = ""
            self.refresh_page_files(self._page_files_current_pages)
            self.refresh_page_files_list()
            self.get_object_status()
        else:
            pass
        """
        bool bVar1;
        first_into_tool = 1;
        bVar1 = std::operator==((string *)file_mode[abi:cxx11],"Local");
        if (bVar1) {
            page_to(4);
            if (file_list_refreshed != '\x01') {
            page_files_pages = 0;
            page_files_current_pages = 0;
            page_files_folder_layers = 0;
            std::__cxx11::string::operator=((string *)page_files_previous_path[abi:cxx11],"");
            std::__cxx11::string::operator=((string *)page_files_root_path[abi:cxx11],"gcodes/");
            std::__cxx11::string::operator=((string *)page_files_path[abi:cxx11],"");
            }
            refresh_page_files(page_files_current_pages);
            refresh_page_files_list();
            get_object_status();
        }
        else {
            page_to(4);
            if (file_list_refreshed != '\x01') {
            page_files_pages = 0;
            page_files_current_pages = 0;
            page_files_folder_layers = 1;
            std::__cxx11::string::operator=((string *)page_files_previous_path[abi:cxx11],"");
            std::__cxx11::string::operator=((string *)page_files_root_path[abi:cxx11],"gcodes/");
            std::__cxx11::string::operator=((string *)page_files_path[abi:cxx11],"/sda1");
            }
            refresh_page_files(page_files_current_pages);
            refresh_page_files_list();
            get_object_status();
        }
        return;
        """


    def refresh_page_files(self, page_files_current_pages: int):
        pass
        """
        string asStack_20 [32];
        
        std::operator+((string *)page_files_root_path[abi:cxx11],(string *)page_files_path[abi:cxx11]);
                            /* try { // try from 0063a190 to 0063a193 has its CatchHandler @ 0063a1a8 */
        get_page_files_filelist(asStack_20);
        std::__cxx11::string::~string(asStack_20);
        set_page_files_show_list(param_1);
        return;
        """

    def get_page_files_filelist(self):
        pass

    def set_page_files_show_list(self):
        pass

    def refresh_page_files_list(self):
        pass

    def get_object_status(self):
        pass

    def go_to_adjust(self):
        pass

    def go_to_setting(self):
        self._first_into_tool = 1
        if self._set_mode == "Language":
            self.changePage(LanguagePage) #page_to(0x15);
        elif self._set_mode == "Network":
            self.changePage(NetworkPage) #go_to_network();
        elif self._set_mode == "System":
            self.changePage(ResetPage) #go_to_reset();
        elif self._set_mode == "Update":
            self.changePage(UpdatePage) #page_to(0x20);
        else:
            self.changePage(MorePage) #page_to(0x21);

    def go_to_network(self):
        #get_wlan0_status();
        #get_wlan0_ip[abi:cxx11]();
        #std::__cxx11::string::~string(asStack_20);
        #page_to(0x3e);
        #get_mks_ethernet();
        pass

    def go_to_reset(self):
        if self._printer_webhooks_state == "shutdown" or self._printer_webhooks_state == "error":
            self.changePage(ResetPage)
        else:
            self.changePage(SystemOkPage)

    def check_conflict(self):
        self.result = 0  # Initialize the return value
        if (self._printer_webhooks_state == "shutdown") or (self._printer_webhooks_state == "error") or (self._on_process != 0):
            self.result = 1
        else:
            self.result = 0
        if self.result == 1:
            self.state.return_page = self.__class__  # Store current page class
            self.changePage(BtnConflictPage)
        return self.result


class BootPage(BasePage):
    @classproperty
    def name(cls) -> str:
        return "logo"

    @classproperty
    def id(cls) -> int:
        return 0

    async def init(self):
        await self.state.display.set(
            "version.val", 
            int(HMI_VERSION_MAJOR) * 10000 + 
            int(HMI_VERSION_MINOR) * 100 + 
            int(HMI_VERSION_PATCH), 
            self.state.options.timeout
        )

    async def onDisplayEvent(self, type: EventType, data):
        pass

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class RestartPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "retart"

    @classproperty
    def id(cls) -> int:
        return 1

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ShutdownPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "shutdown"

    @classproperty
    def id(cls) -> int:
        return 2

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class MainPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "main"

    @classproperty
    def id(cls) -> int:
        return 3

    # Element image id's
    _regular = 32
    _highlight = 33

    # Caselight image id's
    _caselight_regular = 11
    _caselight_highlight = 12

    # Caselight image id's
    _fontcolor_regular = 65535
    _fontcolor_highlight = 63488

    # Thumbnail
    filename = ""

    def isHeating(self, heaterData: dict) -> bool:
        return heaterData["target"] > heaterData["temperature"]

    def isTarget(self, heaterData: dict) -> bool:
        return heaterData["target"] > 0

    async def setHighlight(self, element: str, highlight: bool):
        await self.state.display.set(
            "%s.picc" % element, self._highlight if highlight else self._regular
        )

    async def setCaselight(self, element: str, highlight: bool):
        await self.state.display.set(
            "%s.picc" % element, 12 if highlight else 11
        )
        await self.state.display.set(
            "%s.picc2" % element, 10 if highlight else 9
        )

    async def setFontColor(self, element: str, highlight: bool):
        await self.state.display.set(
            "%s.pco" % element, self._fontcolor_highlight if highlight else self._fontcolor_regular
        )

    async def clear_cp0_image(self):
        await self.state.display.command("vis cp0,0") # send_cmd_cp_close
        await self.state.display.set("cp0_text.txt", "") # send_cmd_txt -> ("cp0_text",".txt="");
        await self.state.display.set("add.txt", "") # send_cmd_txt -> ("add",".txt="");
        # get_sub_dir_files_list

    async def init(self):
        # Trun off logging DEBUG
        logging.getLogger().setLevel(logging.INFO)
        await self.state.display.set("b3.picc", 31)

    async def onDisplayEvent(self, type: EventType, data):
        #log.info(f"MainPage: onDisplayEvent: EventType: {type}, data: {data}")

        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)

            # parse_cmd_msg_from_tjc_screen -> tjc_event_clicked_handler -> led_on_off;
            if data.component_id == 0:
                self.state.printer.togglePin("caselight")

            # parse_cmd_msg_from_tjc_screen -> tjc_event_clicked_handler -> go_to_network;
            elif data.component_id == 1:
                #TODO MainPage: go_to_network
                #get_wlan0_status();
                #get_wlan0_ip[abi:cxx11]();

                #page_to(0x3e);
                self.state.return_page = self.__class__  # Store current page class
                self.changePage(NetworkPage)
                #get_mks_ethernet();
            
            # parse_cmd_msg_from_tjc_screen -> tjc_event_clicked_handler -> motors_off -> FIRMWARE_RESTART;
            elif data.component_id == 2:
                self.state.printer.firmwareRestart()
                #self.state.printer.emergencyStop()

            # parse_cmd_msg_from_tjc_screen -> tjc_event_clicked_handler -> motors_off -> FIRMWARE_RESTART;
            elif data.component_id == 3:
                # cp0 or t3 = click b3,1
                self.page_files_pages = 0
                self.page_files_current_pages = 0
                self.page_files_folder_layers = 0

                retuVal = self.check_conflict()
                if retuVal == 0:
                    pass

                #TODO Main page filename
                """
                check_timelapse_state();
                uVar10 = check_conflict();
                puVar20 = (undefined4 *)(ulong)(uVar10 & 0xff);
                if ((uVar10 & 0xff) == 0) {
                    page_files_pages = 0;
                    page_files_current_pages = 0;
                    page_files_folder_layers = 0;
                    std::__cxx11::string::operator=((string *)page_files_previous_path[abi:cxx11],"");
                    std::__cxx11::string::operator=((string *)page_files_root_path[abi:cxx11],"gcodes/");
                    std::__cxx11::string::operator=((string *)page_files_path[abi:cxx11],"");
                    refresh_page_files(page_files_current_pages);
                    bVar8 = std::operator==((string *)page_files_list_show_type[abi:cxx11],"[c]");
                    puVar20 = (undefined4 *)(ulong)bVar8;
                    if (bVar8) {
                    clear_cp0_image();
                    get_sub_dir_files_list(0);
                    puVar20 = (undefined4 *)
                                std::__cxx11::string::operator=((string *)file_mode[abi:cxx11],"Local");
                    }
                }
                }

                void refresh_page_files(int param_1)

                {
                string asStack_20 [32];
                
                std::operator+((string *)page_files_root_path[abi:cxx11],(string *)page_files_path[abi:cxx11]);
                                    /* try { // try from 0063a190 to 0063a193 has its CatchHandler @ 0063a1a8 */
                get_page_files_filelist(asStack_20);
                std::__cxx11::string::~string(asStack_20);
                set_page_files_show_list(param_1);
                return;
                }

                """

            # parse_cmd_msg_from_tjc_screen -> tjc_event_clicked_handler -> filament_extruder_target -> 
            elif data.component_id == 4:
                self.state.heater_manager.set_heater_data("extruder")
                self.state.return_page = self.__class__ # Store current page class
                self.changePage(KeypadPage)
            
            # parse_cmd_msg_from_tjc_screen -> tjc_event_clicked_handler -> filament_heater_bed_target -> set_heater_bed_target -> set_target(set_target, 60);
            elif data.component_id == 5:
                self.state.heater_manager.set_heater_data("bed")
                self.state.return_page = self.__class__ # Store current page class
                self.changePage(KeypadPage)
                
            # parse_cmd_msg_from_tjc_screen -> tjc_event_clicked_handler -> filament_hot_target -> set_hot_target -> set_target -> M141 Sx;
            elif data.component_id == 6:
                self.state.heater_manager.set_heater_data("chamber")
                self.state.return_page = self.__class__ # Store current page class
                self.changePage(KeypadPage)
            else:
                self.handleNavBarButtons(data.component_id)

        elif type == EventType.NUMERIC_INPUT:
            if data.component_id == 0: # Extruder target temperature
                self._numeric_input = data.value
            elif data.component_id == 1: # Heatbed target temperature
                self._numeric_input = data.value
            elif data.component_id == 2: # Chamber target temperature
                self._numeric_input = data.value
            else:
                log.info(f"MainPage: onDisplayEvent: EventType: {type}, data: {data}")

    async def onPrinterStatusUpdate(self, data: dict):
        #log.info(f"MainPage: onPrinterStatusUpdate: EventType: {type}, data: {data}")

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))
        await self.setFontColor("b4", self.isTarget(data["extruder"]))

        # Heatbed
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))
        await self.setFontColor("b5", self.isTarget(data["heater_bed"]))

        # Chamber
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )
        await self.setFontColor("b6", self.isTarget(data["heater_generic chamber"]))

        # Caselight
        await self.setCaselight("b0", data["output_pin caselight"]["value"] > 0)

        # W-LAN
        #await self.setHighlight("b1", data["output_pin caselight"]["value"] > 0)

        # Sound
        #await self.setHighlight("b1", data["output_pin sound"]["value"] > 0)

        #TODO Main page filename
        """
        filename = data["print_stats"]["filename"]
        await self.state.display.set("t3.txt", filename)

        if filename == "":
            await self.state.display.command("vis cp0,0")
        else:
            if filename != self.filename:
                self.filename = filename
                await self.uploadThumbnail("cp0", 160, "4d4d4d", self.filename)
                await self.state.display.command("vis cp0,1")
        """


class FileListPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "file_list"

    @classproperty
    def id(cls) -> int:
        return 4

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(PrintingPage)
            #elif data.component_id == 1: # Load and go to page | 17  | 0x11 | printing
            #elif data.component_id == 2:
            #elif data.component_id == 3:
            #elif data.component_id == 4:
            #elif data.component_id == 5:
            #elif data.component_id == 6: # LOCAL
            #elif data.component_id == 7: # USB
            #elif data.component_id == 8: # enter
            #elif data.component_id == 9: # up
            #elif data.component_id == 10: # down
            #else:  
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        #t0
        #t1
        #t2
        #t3
        #t4
        #t5

class PreviewPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "preview"

    @classproperty
    def id(cls) -> int:
        return 5

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            #elif data.component_id == 3:
                #uVar10 = check_conflict();
                #if ((uVar10 & 0xff) == 0) {
                #    on_process = 1;
                #    puVar20 = (undefined4 *)go_to_syntony_move();
                #}
                #self.changePage(SyntonyMovePage)
            if data.component_id == 4:
                self.changePage(ToolSelectPage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PreviewPop1Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "preview_pop_1"

    @classproperty
    def id(cls) -> int:
        return 6

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PreviewPop2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "preview_pop_2"

    @classproperty
    def id(cls) -> int:
        return 7

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


# Start resonance test
class SyntonyPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "syntony"

    @classproperty
    def id(cls) -> int:
        return 8

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


# Input shaping running
class SyntonyMovePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "syntony_move"

    @classproperty
    def id(cls) -> int:
        return 9

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BedCalibratePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "bed_calibrate"

    @classproperty
    def id(cls) -> int:
        return 10

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PreCalibratePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "pre_calibrate"

    @classproperty
    def id(cls) -> int:
        return 11

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class CalibrateSrcPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "calibrate_scr"

    @classproperty
    def id(cls) -> int:
        return 12

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class CalibrateMovePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "calibrate_move"

    @classproperty
    def id(cls) -> int:
        return 13

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class AutoLevelPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "auto_level"

    @classproperty
    def id(cls) -> int:
        return 14

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class AutoMovePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "auto_move"

    @classproperty
    def id(cls) -> int:
        return 15

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ZOffsetPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "zoffset"

    @classproperty
    def id(cls) -> int:
        return 16

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PrintingPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "printing"

    @classproperty
    def id(cls) -> int:
        return 17
    
    # Element image id's
    _regular = 51
    _highlight = 52

    # Thumbnail
    filename = ""

    def isHeating(self, heaterData: dict) -> bool:
        return heaterData["target"] > heaterData["temperature"]

    async def setHighlight(self, element: str, highlight: bool):
        await self.state.display.set(
            "%s.picc" % element, self._highlight if highlight else self._regular
        )

    async def init(self):
        pass
        #await self.state.display.set("n4.val", 0) # Hotend fan # "heater_fan hotend_fan": ["speed"],      
        #await self.state.display.set("n5.val", 0) # Part cooling  "fan_generic cooling_fan": ["speed"],        
        #await self.state.display.set("n6.val", 0) # Chamber fan # "heater_fan chamber_fan": ["speed"],          

    def format_time(self, seconds: float) -> str:
        """Format seconds into HH:MM format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours:02d}:{minutes:02d}"
    
    async def onDisplayEvent(self, type: EventType, data):
        #log.info(f"PrintingPage: onDisplayEvent: EventType: {type}, data: {data}")

        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)

            if data.component_id == 0:
                self.state.printer.emergencyStop()
            elif data.component_id == 1:
                self.state.printer.pausePrint()
                #TODO self.changePage(PausePage)
                #temporary back to home
                #self.changePage(MainPage)
            elif data.component_id == 2:
                log.info(f"PrintingPage: onDisplayEvent: EventType: {type}, data: {data}")
            elif data.component_id == 3:
                log.info(f"PrintingPage: onDisplayEvent: EventType: {type}, data: {data}")
            elif data.component_id == 4:
                log.info(f"PrintingPage: onDisplayEvent: EventType: {type}, data: {data}")
            elif data.component_id == 5:
                self.state.printer.togglePin("caselight")
            elif data.component_id == 6:
                self.changePage(ControlPage)

                """
                elif data.component_id == 11:
                    pass

                elif data.component_id == 21:  # extruder
                    self.state.heater_manager.set_heater_data("extruder")
                    self.state.return_page = self.__class__  # Store current page class
                    self.changePage(KeypadPage)
                    
                elif data.component_id == 22:  # bed
                    self.state.heater_manager.set_heater_data("bed")
                    self.state.return_page = self.__class__  # Store current page class
                    self.changePage(KeypadPage)
                    
                elif data.component_id == 23:  # chamber
                    self.state.heater_manager.set_heater_data("chamber")
                    self.state.return_page = self.__class__  # Store current page class
                    self.changePage(KeypadPage)

                elif data.component_id == 2:
                    self.changePage(PrintingPage2)
                """
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        #log.info(f"PrintingPage: onPrinterStatusUpdate: {data}")

        # Extruder
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))
        await self.setHighlight("b0", self.isHeating(data["extruder"]))
        extruder_target = int(data["extruder"]["target"])
        await self.state.display.set("t0.txt", f"{extruder_target}")

        # Bed
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))
        await self.setHighlight("b1", self.isHeating(data["heater_bed"]))
        bed_target = int(data["heater_bed"]["target"])
        await self.state.display.set("t1.txt", f"{bed_target}")

        # Chamber
        await self.state.display.set("n2.val", int(data["heater_generic chamber"]["temperature"]))
        await self.setHighlight("b7", self.isHeating(data["heater_generic chamber"]))
        chamber_target = int(data["heater_generic chamber"]["target"])
        await self.state.display.set("t5.txt", f"{chamber_target}")

        # Caselight
        await self.setHighlight("b3", data["output_pin caselight"]["value"] < 1)

        # Progress tracking
        progress = data["display_status"]["progress"] * 100
        print_duration = data["print_stats"]["print_duration"]
        total_duration = data["print_stats"]["total_duration"]
        
        # Progress bar and percentage
        await self.state.display.set("p0.val", int(progress))
        await self.state.display.set("t7.txt", int(progress))
        
        # Time display
        if print_duration > 0:
            # Current time
            await self.state.display.set("t2.txt", self.format_time(print_duration))
            
            # Estimated total time
            if progress > 0:
                estimated_total = print_duration / (progress / 100)
                await self.state.display.set("t3.txt", self.format_time(estimated_total))
            else:
                await self.state.display.set("t3.txt", "--:--")
        else:
            # Clear time displays if not printing
            await self.state.display.set("t2.txt", "--:--")
            await self.state.display.set("t3.txt", "--:--")


class PrintingKbPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "printing_kb"

    @classproperty
    def id(cls) -> int:
        return 18

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PrintingZOffsetPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "printing_zoffsett"

    @classproperty
    def id(cls) -> int:
        return 19

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PrintingFinishPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "printing_finisch"

    @classproperty
    def id(cls) -> int:
        return 20

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PrintingFinishPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "printing_finisch"

    @classproperty
    def id(cls) -> int:
        return 20

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


#------------------------------------------------------------------------------
# SETTINGS
#------------------------------------------------------------------------------

class LanguagePage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "language"

    @classproperty
    def id(cls) -> int:
        return 21

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class Language2Page(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "language_2"

    @classproperty
    def id(cls) -> int:
        return 69

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class WiFiPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "wifi"

    @classproperty
    def id(cls) -> int:
        return 22

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class WiFiKbPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "wifi_kb"

    @classproperty
    def id(cls) -> int:
        return 23

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class WiFiConnectPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "wifi_connect"

    @classproperty
    def id(cls) -> int:
        return 24

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class WiFiSavingPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "wifi_saveing"

    @classproperty
    def id(cls) -> int:
        return 25

    async def init(self):
        pass
    
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class WiFiSuccessPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "wifi_success"

    @classproperty
    def id(cls) -> int:
        return 26

    async def init(self):
        pass
    
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class WiFiFailPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "wifi_fail"

    @classproperty
    def id(cls) -> int:
        return 27

    async def init(self):
        pass
    
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ShowGrPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "show_gr"

    @classproperty
    def id(cls) -> int:
        return 28

    async def init(self):
        pass
    
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class SystemOkPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "system_ok"

    @classproperty
    def id(cls) -> int:
        return 29

    async def init(self):
        pass
    
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ResetPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "reset"

    @classproperty
    def id(cls) -> int:
        return 30
    
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            elif data.component_id == 6:
                self.changePage(ExportLogPage)
            elif data.component_id == 7: # restart klipper
                self.state.printer.restart()
            elif data.component_id == 8: # restart firmware
                self.state.printer.firmwareRestart()
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # Error message
        #await self.state.display.set("t6.txt", )


class SleepModePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "sleep_mode"

    @classproperty
    def id(cls) -> int:
        return 31

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            elif data.component_id == 6: # 5 minutes
                pass
            elif data.component_id == 7: # 15 minutes
                pass
            elif data.component_id == 8: # 30 minutes
                pass
            elif data.component_id == 9: # never
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class UpdatePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "update"

    @classproperty
    def id(cls) -> int:
        return 32

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            #elif data.component_id == 6: # offline update
            #elif data.component_id == 7: # online update
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        # Version:
        await self.state.display.set("t6.txt", "V" + HMI_VERSION_MAJOR + "." + HMI_VERSION_MINOR + "." + HMI_VERSION_PATCH)


class MorePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "more"

    @classproperty
    def id(cls) -> int:
        return 33

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                #if (current_page_id == 0x21) {
                #    puVar20 = (undefined4 *)set_mks_oobe_enabled(true);
                #}
                #else {
                #    puVar20 = (undefined4 *)page_to(0x21);
                #}
                self.changePage(MorePage)
            elif data.component_id == 3: # Screen Timeout
                self.changePage(SleepModePage)
            elif data.component_id == 6: # After-sales Support
                self.changePage(ServicePage)
            elif data.component_id == 7: # Sound
                pass
                #SET_PIN PIN=beeper VALUE=1
                #SET_PIN PIN=beeper VALUE=0
                #void beep_on_off(void)
                #if (printer_out_pin_beep_value == 0.0) {
                #    "beep_on"
                #else
                #    "beep_off"

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ServicePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "service"

    @classproperty
    def id(cls) -> int:
        return 34

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ControlPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "control"

    @classproperty
    def id(cls) -> int:
        return 35
    
    # Initialize display components
    async def init(self):
        self.input_value = ""

    async def onDisplayEvent(self, type: EventType, data):
        #log.info(f"ControlPage: onPrinterStatusUpdate: {data}")
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                pass
            elif data.component_id == 1: # filament_heater_bed_target();
                pass
            elif data.component_id == 2: # filament_hot_target();
                pass
            elif data.component_id < 6: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 6: # Button 1mm
                self._printer_move_dist = 1.0
                self._printer_filament_extruedr_dist = 1.0
            elif data.component_id == 7: # Button 10mm
                self._printer_move_dist = 10.0
                self._printer_filament_extruedr_dist = 10.0
            elif data.component_id == 8: # Button 50mm
                self._printer_move_dist = 50.0
                self._printer_filament_extruedr_dist = 50.0
            elif data.component_id == 9: # Button 100mm
                self._printer_move_dist = 100.0
                self._printer_filament_extruedr_dist = 100.0
            elif data.component_id == 10: # Button home
                #self.check_conflict()
                #uVar10 = check_conflict();
                #puVar20 = (undefined4 *)(ulong)(uVar10 & 0xff);
                #if ((uVar10 & 0xff) == 0) {
                #G28 - Auto Home
                self.state.printer.runGcode(f"G28") 
                pass
            elif data.component_id == 11: # Button motors off
                #self.check_conflict()
                # M84 - Disable steppers
                self.state.printer.runGcode(f"M84")
            elif data.component_id == 13: # Button box
                #MultiColorSlots::SetSelectedSlotIndex((MultiColorSlots *)slot,-1);
                #MultiColorSlots::SetSelectedBoxIndex((MultiColorSlots *)slot,0);
                #puVar20 = (undefined4 *)MultiColorSlots::SlotParamsSetConfirm((MultiColorSlots *)slot);
                #TODO Box count
                box_count = 0
                if box_count == 0:
                    self.changePage(ZeroBoxPage) 
                else:
                    self.changePage(OneBoxPage)
            elif data.component_id == 14: # Button y increase
                #self.check_conflict(
                self._unhomed_move_mode = 3
                self.state.printer.runGcode(f"Y{str(self._printer_move_dist)}")
                #FORCE_MOVE STEPPER=stepper_x DISTANCE=1 VELOCITY=130 ACCEL=20000
            elif data.component_id == 15: # Button y decrease
                #self.check_conflict()
                self._unhomed_move_mode = 4
                self.state.printer.runGcode(f"Y-{str(self._printer_move_dist)}")
            elif data.component_id == 16: # Button x decrease
                #self.check_conflict()
                self._unhomed_move_mode = 2
                self.state.printer.runGcode(f"X-{str(self._printer_move_dist)}")
            elif data.component_id == 17: # Button x increase
                #self.check_conflict()
                self._unhomed_move_mode = 1
                self.state.printer.runGcode(f"X{str(self._printer_move_dist)}")
            elif data.component_id == 18: # Button z decrease
                #self.check_conflict()
                self._unhomed_move_mode = 5
                self.state.printer.runGcode(f"Z-{str(self._printer_move_dist)}")
            elif data.component_id == 19: # Button z increase
                #self.check_conflict()
                self._unhomed_move_mode = 6
                self.state.printer.runGcode(f"Z{str(self._printer_move_dist)}")
            elif data.component_id == 20: # Button filament retract
                state = data["print_stats"]["state"]
                if state == "printing":
                    if self._page_filament_extrude_button == 0:
                        self._printer_idle_timeout_state = "Printing"
                        self._page_filament_extrude_button = 1
                        await self.state.display.set("vis gm1,1")
                        self.start_retract()
                else:
                    self.changePage(BtnConflictPage)
            elif data.component_id == 21: # Button filament extrude
                state = data["print_stats"]["state"]
                if state == "printing":
                    if self._page_filament_extrude_button == 0:
                        self._printer_idle_timeout_state = "Printing"
                        self._page_filament_extrude_button = 1
                        await self.state.display.set("vis gm0,1")
                        self.start_extrude()
                else:
                    self.changePage(BtnConflictPage)
            elif data.component_id == 22: # Fan control
                self.changePage(ControlSetFanPage)
            else:
                self.handleNavBarButtons(data.component_id)
        elif type == EventType.NUMERIC_INPUT:
            if data.component_id == 0: # Extruder target temperature
                if MAX_EXTRUDER_TEMP < data.value:
                    self._numeric_input = MAX_EXTRUDER_TEMP
                else:
                    self._numeric_input = data.value
                self.state.printer.runGcode(f"SET_HEATER_TEMPERATURE HEATER=extruder TARGET={str(self._numeric_input)}")
            elif data.component_id == 1: # Heatbed target temperature
                if MAX_HEATER_BED_TEMP < data.value:
                    self._numeric_input = MAX_HEATER_BED_TEMP
                else:
                    self._numeric_input = data.value
                self.state.printer.runGcode(f"SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={str(self._numeric_input)}")
            elif data.component_id == 2: # Chamber target temperature
                if MAX_CHAMBER_TEMP < data.value:
                    self._numeric_input = MAX_CHAMBER_TEMP
                else:
                    self._numeric_input = data.value
                self.state.printer.runGcode(f"SET_HEATER_TEMPERATURE HEATER=chamber TARGET={str(self._numeric_input)}")
            else:
                log.info(f"ControlKbPage: onDisplayEvent: EventType: {type}, data: {data}")

    async def onPrinterStatusUpdate(self, data: dict):
        #log.info(f"ControlPage: onPrinterStatusUpdate: {data}")

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder actual value
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))

        # Heatbed actual value
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))

        # Chamber actual value
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )

        """
        # Fans handling with null checks
        def get_fan_speed(fan_data: dict) -> int:
            #Safely get fan speed as percentage
            if not fan_data or fan_data.get("speed") is None:
                return 0
            return int(fan_data["speed"] * 100)

        fan_speed_1 = get_fan_speed(data.get("fan_generic cooling_fan"))
        await self.state.display.set("n6.val", fan_speed_1)

        fan_speed_2 = get_fan_speed(data.get("fan_generic auxiliary_cooling_fan"))
        await self.state.display.set("n7.val", fan_speed_2)

        fan_speed_3 = get_fan_speed(data.get("heater_fan chamber_fan"))
        await self.state.display.set("n8.val", fan_speed_3)

        await self.setHighlight("b6", fan_speed_1 > 0)
        await self.setHighlight("b7", fan_speed_2 > 0)
        await self.setHighlight("b8", fan_speed_3 > 0)
        """

    def start_retract(self):
        #self.state.printer.runGcode(f"M83\nG1 E-{str(self._printer_filament_extruedr_dist)} F300\n")
        pass

    def start_extrude(self):
        #self.state.printer.runGcode(f"M83\nG1 E{str(self._printer_filament_extruedr_dist)} F300\n")
        pass

class ControlKbPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "control_kb"

    @classproperty
    def id(cls) -> int:
        return 36
    
    # Initialize display components
    async def init(self):
        self.input_value = ""

    async def onDisplayEvent(self, type: EventType, data):
        #log.info(f"ControlKbPage: onDisplayEvent: EventType: {type}, data: {data}")
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                pass
            elif data.component_id == 1: # filament_heater_bed_target();
                pass
            elif data.component_id == 2: # filament_hot_target();
                pass
            elif data.component_id < 6: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 6: # Button 1mm
                self._printer_move_dist = 1.0
                self._printer_filament_extruedr_dist = 1.0
            elif data.component_id == 7: # Button 10mm
                self._printer_move_dist = 10.0
                self._printer_filament_extruedr_dist = 10.0
            elif data.component_id == 8: # Button 50mm
                self._printer_move_dist = 50.0
                self._printer_filament_extruedr_dist = 50.0
            elif data.component_id == 9: # Button 100mm
                self._printer_move_dist = 100.0
                self._printer_filament_extruedr_dist = 100.0
            elif data.component_id == 10: # Button home
                #self.check_conflict()
                #uVar10 = check_conflict();
                #puVar20 = (undefined4 *)(ulong)(uVar10 & 0xff);
                #if ((uVar10 & 0xff) == 0) {
                #G28 - Auto Home
                self.state.printer.runGcode(f"G28") 
                pass
            elif data.component_id == 11: # Button motors off
                #self.check_conflict()
                # M84 - Disable steppers
                self.state.printer.runGcode(f"M84")
            elif data.component_id == 13: # Button box
                #MultiColorSlots::SetSelectedSlotIndex((MultiColorSlots *)slot,-1);
                #MultiColorSlots::SetSelectedBoxIndex((MultiColorSlots *)slot,0);
                #puVar20 = (undefined4 *)MultiColorSlots::SlotParamsSetConfirm((MultiColorSlots *)slot);
                pass
            elif data.component_id == 14: # Button y increase
                #self.check_conflict(
                self._unhomed_move_mode = 3
                self.state.printer.runGcode(f"Y{str(self._printer_move_dist)}")
                #FORCE_MOVE STEPPER=stepper_x DISTANCE=1 VELOCITY=130 ACCEL=20000
            elif data.component_id == 15: # Button y decrease
                #self.check_conflict()
                self._unhomed_move_mode = 4
                self.state.printer.runGcode(f"Y-{str(self._printer_move_dist)}")
            elif data.component_id == 16: # Button x decrease
                #self.check_conflict()
                self._unhomed_move_mode = 2
                self.state.printer.runGcode(f"X-{str(self._printer_move_dist)}")
            elif data.component_id == 17: # Button x increase
                #self.check_conflict()
                self._unhomed_move_mode = 1
                self.state.printer.runGcode(f"X{str(self._printer_move_dist)}")
            elif data.component_id == 18: # Button z decrease
                #self.check_conflict()
                self._unhomed_move_mode = 5
                self.state.printer.runGcode(f"Z-{str(self._printer_move_dist)}")
            elif data.component_id == 19: # Button z increase
                #self.check_conflict()
                self._unhomed_move_mode = 6
                self.state.printer.runGcode(f"Z{str(self._printer_move_dist)}")
            elif data.component_id == 20: # Button filament retract
                state = data["print_stats"]["state"]
                if state == "printing":
                    if self._page_filament_extrude_button == 0:
                        self._printer_idle_timeout_state = "Printing"
                        self._page_filament_extrude_button = 1
                        await self.state.display.set("vis gm1,1")
                        self.start_retract()
                else:
                    self.changePage(BtnConflictPage)
            elif data.component_id == 21: # Button filament extrude
                state = data["print_stats"]["state"]
                if state == "printing":
                    if self._page_filament_extrude_button == 0:
                        self._printer_idle_timeout_state = "Printing"
                        self._page_filament_extrude_button = 1
                        await self.state.display.set("vis gm0,1")
                        self.start_extrude()
                else:
                    self.changePage(BtnConflictPage)
            elif data.component_id == 22: # Fan control
                self.changePage(ControlSetFanPage)
            else:
                self.handleNavBarButtons(data.component_id)
        elif type == EventType.NUMERIC_INPUT:
            if data.component_id == 0: # Extruder target temperature
                if MAX_EXTRUDER_TEMP < data.value:
                    self._numeric_input = MAX_EXTRUDER_TEMP
                else:
                    self._numeric_input = data.value
                self.state.printer.runGcode(f"SET_HEATER_TEMPERATURE HEATER=extruder TARGET={str(self._numeric_input)}")
            elif data.component_id == 1: # Heatbed target temperature
                if MAX_HEATER_BED_TEMP < data.value:
                    self._numeric_input = MAX_HEATER_BED_TEMP
                else:
                    self._numeric_input = data.value
                self.state.printer.runGcode(f"SET_HEATER_TEMPERATURE HEATER=heater_bed TARGET={str(self._numeric_input)}")
            elif data.component_id == 2: # Chamber target temperature
                if MAX_CHAMBER_TEMP < data.value:
                    self._numeric_input = MAX_CHAMBER_TEMP
                else:
                    self._numeric_input = data.value
                self.state.printer.runGcode(f"SET_HEATER_TEMPERATURE HEATER=chamber TARGET={str(self._numeric_input)}")
            else:
                log.info(f"ControlKbPage: onDisplayEvent: EventType: {type}, data: {data}")

    async def onPrinterStatusUpdate(self, data: dict):
        #log.info(f"ControlKbPage: onPrinterStatusUpdate: {data}")

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder actual value
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))

        # Heatbed actual value
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))

        # Chamber actual value
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )


class PreLoadPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "pre_load"

    @classproperty
    def id(cls) -> int:
        return 37

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                log.info(f"PreLoadPage: Button Extruder")
            elif data.component_id == 1: # filament_heater_bed_target();
                log.info(f"PreLoadPage: Button Bed")
            elif data.component_id == 2: # filament_hot_target();
                log.info(f"PreLoadPage: Button Camber")
            elif data.component_id == 3: # page_to(0x25);
                self.changePage(PreLoadPage)
            elif data.component_id == 4: # page_to(0x25);
                self.changePage(PreLoadPage)
            elif data.component_id == 5: # page_to(0x25);
                self.changePage(PreLoadPage)
            elif data.component_id == 9:
                log.info(f"PreLoadPage: Button Next")
            elif data.component_id == 10: # finish_unload(); -> page_to(0x71);
                log.info(f"PreLoadPage: Button Back")
            elif data.component_id == 22:
                log.info(f"PreLoadPage: Button FanBack")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder actual value
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))

        # Heatbed actual value
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))

        # Chamber actual value
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )


class PreUnloadPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "pre_unload"

    @classproperty
    def id(cls) -> int:
        return 38

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                log.info(f"PreLoadPage: Button Extruder")
            elif data.component_id == 1: # filament_heater_bed_target();
                log.info(f"PreLoadPage: Button Bed")
            elif data.component_id == 2: # filament_hot_target();
                log.info(f"PreLoadPage: Button Camber")
            elif data.component_id == 3: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 4: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 5: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 9:
                log.info(f"PreLoadPage: Button Next")
            elif data.component_id == 10: # finish_unload(); -> page_to(0x71);
                log.info(f"PreLoadPage: Button Back")
            elif data.component_id == 22:
                log.info(f"PreLoadPage: Button FanBack")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder actual value
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))

        # Heatbed actual value
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))

        # Chamber actual value
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )


class PreHeatPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "pre_head"

    @classproperty
    def id(cls) -> int:
        return 39

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                log.info(f"PreHeatPage: Button Extruder")
            elif data.component_id == 1: # filament_heater_bed_target();
                log.info(f"PreHeatPage: Button Bed")
            elif data.component_id == 2: # filament_hot_target();
                log.info(f"PreHeatPage: Button Camber")
            elif data.component_id == 3: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 4: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 5: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 6:
                log.info(f"PreHeatPage: Button 220°C")
            elif data.component_id == 7:
                log.info(f"PreHeatPage: Button 250°C")
            elif data.component_id == 8:
                log.info(f"PreHeatPage: Button 300°C")
            elif data.component_id == 9:
                log.info(f"PreHeatPage: Button Next")
            elif data.component_id == 10: # finish_unload(); -> page_to(0x71);
                log.info(f"PreHeatPage: Button Back")
            elif data.component_id == 22:
                log.info(f"PreHeatPage: Button FanBack")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder actual value
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))

        # Heatbed actual value
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))

        # Chamber actual value
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )


class UnloadPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "unload"

    @classproperty
    def id(cls) -> int:
        return 40

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                log.info(f"UnloadPage: Button Extruder")
            elif data.component_id == 1: # filament_heater_bed_target();
                log.info(f"UnloadPage: Button Bed")
            elif data.component_id == 2: # filament_hot_target();
                log.info(f"UnloadPage: Button Camber")
            elif data.component_id == 3: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 4: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 5: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 9:
                log.info(f"UnloadPage: Button Next")
            elif data.component_id == 10: # finish_unload(); -> page_to(0x71);
                log.info(f"UnloadPage: Button Back")
            elif data.component_id == 22:
                log.info(f"UnloadPage: Button FanBack")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder actual value
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))

        # Heatbed actual value
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))

        # Chamber actual value
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )

        # vis t0,1 Please remove the filament from the PTFE tube

        # gm0 Heating up.

        # gm1 Heating Returning materials.

        # filament unload completed.


class LoadPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "load"

    @classproperty
    def id(cls) -> int:
        return 41

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                log.info(f"LoadPage: Button Extruder")
            elif data.component_id == 1: # filament_heater_bed_target();
                log.info(f"LoadPage: Button Bed")
            elif data.component_id == 2: # filament_hot_target();
                log.info(f"LoadPage: Button Camber")
            elif data.component_id == 3: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 4: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 5: # page_to(0x24);
                self.changePage(ControlKbPage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # Extruder actual value
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))

        # Heatbed actual value
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))

        # Chamber actual value
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["temperature"])
        )

        # t0.txt Heating up...


class MovePop1Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "move_pop_1"

    @classproperty
    def id(cls) -> int:
        return 42

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"MovePop1Page: Button Confirm")
            elif data.component_id == 1:
                log.info(f"MovePop1Page: Button Cancel")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # t0.txt All the axies need to home reset before acces the manual control, do you want to home position?


class ScreenSleepPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "screen_sleep"

    @classproperty
    def id(cls) -> int:
        return 43

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            #prints 0x65,1
            #prints dp,1
            #prints 0,1
            #prints 0xff,1
            #prints 0xff,1
            #prints 0xff,1
            if data.component_id == 0:
                self.changePage(self.state.return_page)
                self.state.return_page = None  # Clear return page
            elif data.component_id == 1:
                log.info(f"ScreenSleepPage: component_id = 1")
            else:
                pass

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DetectErrorPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "detect_error"

    @classproperty
    def id(cls) -> int:
        return 44

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"DetectErrorPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt error_message


class GCodeErrorPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "gcode_error"

    @classproperty
    def id(cls) -> int:
        return 45

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"GCodeErrorPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt gcode_error


class UpdateSuccessPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "update_success"

    @classproperty
    def id(cls) -> int:
        return 46

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"UpdateSuccessPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt Update finished.


class UpdatingPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "updating"

    @classproperty
    def id(cls) -> int:
        return 47

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        pass

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # j0.val progress
        # t0.txt Updating in progress...
        # t1.txt ?
        # t2.txt ?


class UpdateFinishPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "update_finish"

    @classproperty
    def id(cls) -> int:
        return 48

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            pass

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt Please turn off the power supply, reboot after \r20 seconds, and then it will start updating."


class PrintNoFilPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "print_no_fil"

    @classproperty
    def id(cls) -> int:
        return 49

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"PrintNoFilPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt Filament ran-out, \rplease re-load filament.


class PrintNoFil2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "print_no_fil2"

    @classproperty
    def id(cls) -> int:
        return 50

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"PrintNoFil2Page: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt Filament ran-out, \rplease re-load filament.


class PrintLogSuccessPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "print_log_s"

    @classproperty
    def id(cls) -> int:
        return 51

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"PrintLogSuccessPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt Export logs successfully.


class PrintLogFailedPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "print_log_f"

    @classproperty
    def id(cls) -> int:
        return 52

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"PrintLogFailedPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt Failed to export logs. Please make \rsure the USB drive is inserted.


class PrintStopPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "print_stop"

    @classproperty
    def id(cls) -> int:
        return 53

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"PrintStopPage: Button Confirm")
            if data.component_id == 1:
                log.info(f"PrintStopPage: Button Cancel")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt Are you sure you want \rto stop printing?


class MovePop2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "move_pop_2"

    @classproperty
    def id(cls) -> int:
        return 54

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"MovePop2Page: Button Confirm")

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt
        # Movement beyond range of provisions.
        # Bewegung über den den Grenzbereich \rdes Bauraums hinaus.


class PrintStoppingPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "print_stopping"

    @classproperty
    def id(cls) -> int:
        return 55

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"PrintStoppingPage: Button Confirm")

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt
        # Movement Stop processing,please wait...
        # Bewegung Werte Messdaten aus,\rbitte warten...


class ResumePrintPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "resume_print"

    @classproperty
    def id(cls) -> int:
        return 56

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"ResumePrintPage: Button Confirm")
            if data.component_id == 1:
                log.info(f"ResumePrintPage: Button Cancel")

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt
        # Movement Print was interrupted last \rtime, continue printing?
        # Bewegung Druck wurde das letzte Mal \runterbrochen, Druck fortsetzen?


class MemoryWarningPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "memory_warning"

    @classproperty
    def id(cls) -> int:
        return 57

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                log.info(f"MemoryWarningPage: Button Confirm")

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt
        # Memory space is full. \rPlease clear the memory.
        # Der Speicher ist voll. \rBitte den Speicher leeren.


class ControlSetFanPage(OpenP4Page):

    _fan0_speed = 0.0
    _fan2_speed = 0.0
    _fan3_speed = 0.0

    @classproperty
    def name(cls) -> str:
        return "control_setfan"

    @classproperty
    def id(cls) -> int:
        return 58

    async def init(self):
        pass

    def isHeating(self, heaterData: dict) -> bool:
        return heaterData["target"] > heaterData["temperature"]

    def isTarget(self, heaterData: dict) -> bool:
        return heaterData["target"] > 0

    def filament_fan0(self): # Cooling Fan
        if self._fan0_speed == 0.0:
            self.set_fan0_speed(255)
        else:
            self.set_fan0_speed(0)

    def set_fan0(self):
        pass

    def set_fan0_speed(self, speed: int):
        self.state.printer.runGcode(f"M106 P0 S{str(speed)}")
        #SET_FAN_SPEED FAN=cooling_fan SPEED=0.3 #30%

    def filament_fan2(self): # Auxiliary Cooling Fan
        if self._fan2_speed == 0.0:
            self.set_fan2_speed(255)
        else:
            self.set_fan2_speed(0)

    def set_fan2_speed(self, speed: int):
        self.state.printer.runGcode(f"M106 P2 S{str(speed)}")
        #SET_FAN_SPEED FAN=auxiliary_cooling_fan SPEED=0.3 #30%

    def filament_fan3(self): # Exhaust Fan
        if self._fan3_speed == 0.0:
            self.set_fan3_speed(255)
        else:
            self.set_fan3_speed(0)

    def set_fan3_speed(self, speed: int):
        self.state.printer.runGcode(f"M106 P3 S{str(speed)}")
        #SET_FAN_SPEED FAN=exhaust_fan SPEED=0.3 #30%

    async def setHighlightHeater(self, element: str, highlight: bool):
        await self.state.display.set(
            "%s.picc" % element, 115 if highlight else 114
        )
        await self.state.display.set(
            "%s.picc2" % element, 118 if highlight else 116
        )
        await self.state.display.set(
            "%s.pco" % element, 63488 if highlight else 65535
        )

    async def setHighlightFan(self, element: str, highlight: bool):
        await self.state.display.set(
            "%s.picc" % element, 134 if highlight else 131
        )
        await self.state.display.set(
            "%s.picc2" % element, 136 if highlight else 135
        )

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # filament_extruder_target();
                log.info(f"ControlSetFanPage: Button Extruder")
            elif data.component_id == 1: # filament_heater_bed_target();
                log.info(f"ControlSetFanPage: Button Bed")
            elif data.component_id == 2: # filament_hot_target();
                log.info(f"ControlSetFanPage: Button Camber")
            elif data.component_id == 3: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 4: # page_to(0x24);
                self.changePage(ControlKbPage)
            elif data.component_id == 5: # page_to(0x24);
                self.changePage(ControlKbPage)

            elif data.component_id == 6: # Button Cooling Fan
                #self.filament_fan0()
                if self._fan0_speed == 0.0:
                    self.state.printer.runGcode(f"M106 P0 S255")
                    #SET_FAN_SPEED FAN=cooling_fan SPEED=0.3 #30%
                else:
                    self.state.printer.runGcode(f"M106 P0 S0")
            elif data.component_id == 7: # Button Auxiliary Cooling Fan
                self.filament_fan2()
            elif data.component_id == 8: # Button Chamber Circulation Fan
                self.filament_fan3()

            elif data.component_id == 9:
                log.info(f"ControlSetFanPage: Button + Cooling Fan")
            elif data.component_id == 10:
                log.info(f"ControlSetFanPage: Button + Auxiliary Cooling Fan")
            elif data.component_id == 11:
                log.info(f"ControlSetFanPage: Button + Chamber Circulation Fan")

            elif data.component_id == 12:
                log.info(f"ControlSetFanPage: Button - Cooling Fan")
            elif data.component_id == 13:
                log.info(f"ControlSetFanPage: Button - Auxiliary Cooling Fan")
            elif data.component_id == 14:
                log.info(f"ControlSetFanPage: Button - Chamber Circulation Fan")

            elif data.component_id == 15:
                log.info(f"ControlSetFanPage: Button ? Cooling Fan")
            elif data.component_id == 16:
                log.info(f"ControlSetFanPage: Button ? Cooling Fan")
            elif data.component_id == 17:
                log.info(f"ControlSetFanPage: Button ? Cooling Fan")
            elif data.component_id == 18:
                log.info(f"ControlSetFanPage: Button ? Cooling Fan")
            elif data.component_id == 19:
                log.info(f"ControlSetFanPage: Button ? Cooling Fan")

            elif data.component_id == 20:
                log.info(f"ControlSetFanPage: Button ? Auxiliary Cooling Fan")
            elif data.component_id == 21:
                log.info(f"ControlSetFanPage: Button ? Auxiliary Cooling Fan")
            elif data.component_id == 23:
                log.info(f"ControlSetFanPage: Button ? Auxiliary Cooling Fan")
            elif data.component_id == 24:
                log.info(f"ControlSetFanPage: Button ? Auxiliary Cooling Fan")
            elif data.component_id == 25:
                log.info(f"ControlSetFanPage: Button ? Auxiliary Cooling Fan")

            elif data.component_id == 26:
                log.info(f"ControlSetFanPage: Button ? Chamber Circulation Fan")
            elif data.component_id == 27:
                log.info(f"ControlSetFanPage: Button ? Chamber Circulation Fan")
            elif data.component_id == 28:
                log.info(f"ControlSetFanPage: Button ? Chamber Circulation Fan")
            elif data.component_id == 29:
                log.info(f"ControlSetFanPage: Button ? Chamber Circulation Fan")
            elif data.component_id == 30:
                log.info(f"ControlSetFanPage: Button ? Chamber Circulation Fan")

            elif data.component_id == 22: # Button Back
                log.info(f"ControlSetFanPage: Button Back")
                #self.changePage(self.state.return_page)
                self.changePage(ControlPage)
                
            elif data.component_id == 34: # ignore NavBar control button
                log.info(f"ControlSetFanPage: ignore NavBar control button")

            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)

        # void refresh_page_filament_set_fan(void)

        # Extruder
        await self.state.display.set("n0.val", int(data["extruder"]["temperature"]))
        await self.setHighlightHeater("b0", self.isHeating(data["extruder"]))
        await self.state.display.set("n3.val", int(data["extruder"]["target"]))

        # Bed
        await self.state.display.set("n1.val", int(data["heater_bed"]["temperature"]))
        await self.setHighlightHeater("b1", self.isHeating(data["heater_bed"]))
        await self.state.display.set("n4.val", int(data["heater_bed"]["target"]))

        # Chamber
        await self.state.display.set("n2.val", int(data["heater_generic chamber"]["temperature"]))
        await self.setHighlightHeater("b7", self.isHeating(data["heater_generic chamber"]))
        await self.state.display.set("n5.val", int(data["heater_generic chamber"]["target"]))

        # Fans handling with null checks
        def get_fan_speed(fan_data: dict) -> int:
            #Safely get fan speed as percentage
            if not fan_data or fan_data.get("speed") is None:
                return 0
            return int(fan_data["speed"] * 100)

        # n6.val="Cooling Fan" %
        # t0.txt="Cooling Fan"
        self._fan0_speed = get_fan_speed(data.get("fan_generic cooling_fan"))
        await self.state.display.set("n6.val", self._fan0_speed)
        await self.setHighlightFan("b6", self._fan0_speed > 0)

        # n7.val="Auxiliary \rCooling Fan" %
        # t1.txt="Auxiliary \rCooling Fan"
        self._fan2_speed = get_fan_speed(data.get("fan_generic auxiliary_cooling_fan"))
        await self.state.display.set("n7.val", self._fan2_speed)
        await self.setHighlightFan("b7", self._fan2_speed > 0)

        # n8.val="Chamber \rCirculation Fan" %
        # t2.txt="Chamber \rCirculation Fan"
        self._fan3_speed = get_fan_speed(data.get("fan_generic exhaust_fan"))
        #self._fan3_speed = get_fan_speed(data.get("heater_fan chamber_fan"))

        await self.state.display.set("n8.val", self._fan3_speed)
        await self.setHighlightFan("b8", self._fan3_speed > 0)

class SyntonyFinischPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "syntony_finisch"

    @classproperty
    def id(cls) -> int:
        return 59

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 3:
                log.info(f"SyntonyFinischPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt
        # Input shaping completed.


class BedCalFinischPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "bedcal_finisch"

    @classproperty
    def id(cls) -> int:
        return 60

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 3:
                log.info(f"BedCalFinischPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt
        # Platform calibration completed.


class AutoFinischPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "auto_finisch"

    @classproperty
    def id(cls) -> int:
        return 61

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 3:
                log.info(f"AutoFinischPage: Button Confirm")
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        # t0.txt
        # Auto Leveling Completed.


class NetworkPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "network"

    @classproperty
    def id(cls) -> int:
        return 62

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            #elif data.component_id == 6: Button WiFi connect
            #elif data.component_id == 7: Button LAN connect
            #elif data.component_id == 8: Button WiFi connection
            #elif data.component_id == 9: Button Fluidd account
            #elif data.component_id == 10: Button connection
            #elif data.component_id == 20: Button Client
            #elif data.component_id == 21: Button Server
            #elif data.component_id == 22: Button Search
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        #log.info(f"ControlKbPage: onPrinterStatusUpdate: {data}")

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)
"""
        # IP address
        await self.state.display.set("t7.txt", 1)
        # Connection (LAN connection only...)
        await self.state.display.set("t8.txt", 1)
        # 
        await self.state.display.set("t9.txt", 1)
        # 
        await self.state.display.set("t10.txt", 1)
        # 
        await self.state.display.set("t11.txt", 1)
        # 
        await self.state.display.set("t12.txt", 1)
"""


class ServerSetPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "network"

    @classproperty
    def id(cls) -> int:
        return 63

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            #elif data.component_id == 6: Button refresh
            #elif data.component_id == 7: Button up
            #elif data.component_id == 8: Button down
            #elif data.component_id == 9: Button back
            #elif data.component_id == 10: server1
            #elif data.component_id == 11: server2
            #elif data.component_id == 12: server3
            #elif data.component_id == 13: server4
            #elif data.component_id == 14: server5
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        #log.info(f"ControlKbPage: onPrinterStatusUpdate: {data}")

        state = data["print_stats"]["state"]
        if state == "printing":
            self.changePage(PrintingPage)
        
        # t3.txt="Please select the server after \rconnecting to the network \rand turning off LAN only \rconnections."
'''
        # IP address
        await self.state.display.set("t7.txt", 1)
        # Connection (LAN connection only...)
        await self.state.display.set("t8.txt", 1)
        # 
        await self.state.display.set("t9.txt", 1)
        # 
        await self.state.display.set("t10.txt", 1)
        # 
        await self.state.display.set("t11.txt", 1)
        # 
        await self.state.display.set("t12.txt", 1)
'''

class SearchServerPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "search_server"

    @classproperty
    def id(cls) -> int:
        return 64

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OnlineUpdatePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "online_update"

    @classproperty
    def id(cls) -> int:
        return 65

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OfflineUpdatePage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "offline_update"

    @classproperty
    def id(cls) -> int:
        return 66

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class InstallingPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "installing"

    @classproperty
    def id(cls) -> int:
        return 67

    async def init(self):
        pass
        # t0.txt
        # Installing....

    async def onDisplayEvent(self, type: EventType, data):
        pass

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BtnConflictPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "btn_conflict"

    @classproperty
    def id(cls) -> int:
        return 68

    async def init(self):
        pass
        # t0.txt
        # Please wait until current operation \rfinish.

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(self.state.return_page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class Language2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "language_2"

    @classproperty
    def id(cls) -> int:
        return 69

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class LowTempPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "low_temp"

    @classproperty
    def id(cls) -> int:
        return 70

    async def init(self):
        pass
        # t0.txt
        # The temperature of the nozzle is too \rlow.Please click the button again \rafter the temperature reaches the set \rtemperature.

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                self.changePage(self.state.return_page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class Load2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "load_2"

    @classproperty
    def id(cls) -> int:
        return 71

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class LoadFinishPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "load_finish"

    @classproperty
    def id(cls) -> int:
        return 72

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class AutoWarningPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "auto_warning"

    @classproperty
    def id(cls) -> int:
        return 73

    async def init(self):
        pass
        # t0.txt
        # Please set the temperature to above 35 ℃.

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                self.changePage(self.state.return_page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class CalWarningPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "cal_warning"

    @classproperty
    def id(cls) -> int:
        return 74

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                pass
            else:  
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class RePrintingPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "re_printing"

    @classproperty
    def id(cls) -> int:
        return 75

    async def init(self):
        pass
        # t0.txt
        # Restoring printing...

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                self.changePage(self.state.return_page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenLanguage1Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_language1"

    @classproperty
    def id(cls) -> int:
        return 76

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                self.changePage(self.state.return_page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenLanguage2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_language2"

    @classproperty
    def id(cls) -> int:
        return 77

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0:
                self.changePage(self.state.return_page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenSkipPopPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_skip_pop"

    @classproperty
    def id(cls) -> int:
        return 78

    async def init(self):
        pass
        # t0.txt
        # Are you sure to skip start-guide?

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Confirm
                self.changePage(self.state.return_page)
            if data.component_id == 1: # Cancel
                self.changePage(self.state.return_page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenUnpack1Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_unpack1"

    @classproperty
    def id(cls) -> int:
        return 79

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Next
                self.changePage(OpenUnpack2Page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenUnpack2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_unpack2"

    @classproperty
    def id(cls) -> int:
        return 80

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Next
                self.changePage(OpenUnpack3Page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenUnpack3Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_unpack3"

    @classproperty
    def id(cls) -> int:
        return 81

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Next
                self.changePage(OpenUnpack4Page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenUnpack4Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_unpack4"

    @classproperty
    def id(cls) -> int:
        return 82

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Next
                self.changePage(MainPage)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenLoad1Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_load1"

    @classproperty
    def id(cls) -> int:
        return 83

    async def init(self):
        pass
        #t0.txt="Language"
        #t1.txt="Unboxing"
        #t2.txt="Load"
        #t3.txt="Install the supplies holder."
        
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Next
                self.changePage(OpenUnpack2Page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenLoad2Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_load2"

    @classproperty
    def id(cls) -> int:
        return 84

    async def init(self):
        pass
        #t0.txt="Language"
        #t1.txt="Unboxing"
        #t2.txt="Load"
        #t3.txt="Keep pushing the filament \rinto the filament tube \runtill reach extruder."
        
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Next
                self.changePage(OpenUnpack3Page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenLoad3Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_load3"

    @classproperty
    def id(cls) -> int:
        return 85

    async def init(self):
        pass
        #t0.txt="Language"
        #t1.txt="Unboxing"
        #t2.txt="Load"
        #t3.txt="Set the corresponding \rnozzle temperature for \rthe filament and start \rheating."
        #t4.txt="Attention: Wait for the \rnozzle temperature to \rreach the set temperature \rbefore clicking Next."

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: # Next
                self.changePage(OpenUnpack4Page)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenLoad4Page(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_load4"

    @classproperty
    def id(cls) -> int:
        return 86

    async def init(self):
        pass
        #t0.txt="Language"
        #t1.txt="Unboxing"
        #t2.txt="Load"
        #t3.txt="Click load button and keep \rpushing the filament until it come out from the nozzle."

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: #b0.txt="Next"
                self.changePage(OpenFinishPage)
            if data.component_id == 1: #b1.txt="Load"
                pass

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OpenFinishPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "open_finish"

    @classproperty
    def id(cls) -> int:
        return 86

    async def init(self):
        pass
        #t0.txt="Language"
        #t1.txt="Unboxing"
        #t2.txt="Load"
        #t3.txt="Congrats!guide tutorial finished."
        #t4.txt="Attention: Input shaping will be \rautomatically performed."
        
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: #b0.txt="Completed"
                self.changePage(MainPage) # Input shaping will be \rautomatically performed."

    async def onPrinterStatusUpdate(self, data: dict):
        pass

'''
| 88  | 0x58 | connect_set         |
| 89  | 0x59 | account_list        |
| 90  | 0x5A | add_account         |
| 91  | 0x5B | reset_account       |
| 92  | 0x5C | account_kb          |
| 93  | 0x5D | account_pop         |
'''


class MorePopPage(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "more_pop"

    @classproperty
    def id(cls) -> int:
        return 894

    async def init(self):
        pass
        #t0.txt="Do you want to restore factory \rsettings?"
        
    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            if data.component_id == 0: #b0.txt="Confirm"
                pass
            if data.component_id == 1: #b1.txt="Cancel"
                pass

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ToolSelectPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "tool_select"

    @classproperty
    def id(cls) -> int:
        return 95

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(PlatformResetPage)
            elif data.component_id == 1:
                self.changePage(AutoBedLevelingPage)
            elif data.component_id == 2:
                self.changePage(InputShapingPage)
            elif data.component_id == 3:
                self.changePage(ConsumablesDryingPage)
            elif data.component_id == 4:
                self.changePage(BoxDryingPage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DryPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "dry"

    @classproperty
    def id(cls) -> int:
        return 96

    async def init(self):
        pass
        #t0.txt="1. Please check the platform and the bottom of the \rmachine to ensure that there are no debris. \r2. After initialization, cover the consumables with a \rbox and start drying by selecting the filament type."
        #t1.txt="Attention: Please use a box that is resistant to \rhigh temperatures."

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: # Play
                pass
            elif data.component_id == 1:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DryPreparePage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "dry_prepare"

    @classproperty
    def id(cls) -> int:
        return 97

    async def init(self):
        pass
        #t0.txt="Initializing location, please wait..."

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            elif data.component_id == 1:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DryTipsPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "dry_tips"

    @classproperty
    def id(cls) -> int:
        return 98

    async def init(self):
        pass
        #t0.txt="Please select consumables in the \rupper left corner"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Back"
                pass
            elif data.component_id == 1: #b1.txt="Start"
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DrySelectPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "dry_select"

    @classproperty
    def id(cls) -> int:
        return 99

    async def init(self):
        pass
        #t0.txt="Please select consumables in the \rupper left corner"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            elif data.component_id == 1:
                pass
            elif data.component_id == 2:
                pass
            elif data.component_id == 3:
                pass
            elif data.component_id == 4:
                pass
            elif data.component_id == 5:
                pass
            elif data.component_id == 6: #button up
                pass
            elif data.component_id == 7: #button down
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        #t1.txt
        #t2.txt
        #t3.txt
        #t4.txt
        #t5.txt
        #t11.txt
        #t12.txt
        pass


class DryingPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "drying"

    @classproperty
    def id(cls) -> int:
        return 100

    async def init(self):
        pass
        #t0.txt="Suggest flipping the consumables \revery 6 hours"
        #t1.txt="Caution: Be careful of high \rtemperature burns"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Stop"
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        #t2.txt
        #t11.txt
        #t12.txt
        #t13.txt
        #t14.txt
        #t15.txt
        pass


class DryingFinishPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "dry_finish"

    @classproperty
    def id(cls) -> int:
        return 101

    async def init(self):
        pass
        #t0.txt="Remove the consumables as soon as they \rcool down."
        #t1.txt="It is recommended to put the consumables \rin a protective box to avoid moisture again."

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Confirm"
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DebugPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "debug"

    @classproperty
    def id(cls) -> int:
        return 102

    async def init(self):
        pass
        #t0.txt="温腔"
        #t1.txt="挤出机"
        #t2.txt="热床"
        #t3.txt="热传保护"
        #t9.txt="重试次数"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #Exit"
                self.changePage(MainPage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        #t4.txt="0°C"
        #t5.txt="0°C"
        #t6.txt="0°C"
        #t7.txt="0°C"
        #t10.txt="0°C"


class DryWarn1Page(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "dry_warn1"

    @classproperty
    def id(cls) -> int:
        return 103

    async def init(self):
        pass
        #t0.txt="Please configure consumables \rbefore use"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #Confirm"
                self.changePage(MainPage)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DryWarn2Page(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "dry_warn2"

    @classproperty
    def id(cls) -> int:
        return 104

    async def init(self):
        pass
        #t0.txt="Please select the type of consumables"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #Confirm"
                self.changePage(MainPage)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class UserInfoPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "user_info"

    @classproperty
    def id(cls) -> int:
        return 105

    async def init(self):
        pass
        #t0.txt="Languages"
        #t1.txt="Network"
        #t2.txt="System message"
        #t4.txt="Check for updates"
        #t5.txt="more"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        #t6.txt="Device code:"
        #t3.txt=""
        #t7.txt=""
        #t8.txt=""


class NetworkTestPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "network_test"

    @classproperty
    def id(cls) -> int:
        return 106

    async def init(self):
        pass
        #t0.txt="Languages"
        #t1.txt="Network"
        #t2.txt="System message"
        #t4.txt="Check for updates"
        #t5.txt="more"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(LanguagePage)
            elif data.component_id == 1:
                self.changePage(NetworkPage)
            elif data.component_id == 2:
                self.changePage(ResetPage)
            elif data.component_id == 4:
                self.changePage(UpdatePage)
            elif data.component_id == 5:
                self.changePage(MorePage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
        #t11.txt="No network connection"
        #t12.txt="Local network connected"
        #t3.txt="Router delay"
        #t6.txt="Testing..."
        #t8.txt="Server delay"
        #t13.txt="Testing..."
        #t7.txt="(Average delay: "
        #t14.txt="(Average delay: "
        #t16.txt="Test failed, please check the network"
        #t17.txt="Test failed, please check the network"


class UserExitPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "user_exit"

    @classproperty
    def id(cls) -> int:
        return 107

    async def init(self):
        pass
        #t0.txt="Do you want to \rlog out of the account?"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Confirm"
                self.changePage(MainPage)
            elif data.component_id == 1: #b1.txt="Cancel"
                self.changePage(MainPage)
 
    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ConnectServerPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "connect_server"

    @classproperty
    def id(cls) -> int:
        return 108

    async def init(self):
        pass
        #t0.txt="Switching servers..."

    async def onDisplayEvent(self, type: EventType, data):
        pass
 
    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ServerSuccessPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "server_success"

    @classproperty
    def id(cls) -> int:
        return 109

    async def init(self):
        pass
        #t0.txt="Successfully switched servers"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Confirm"
                self.changePage(MainPage)
 
    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ServerFailPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "server_fail"

    @classproperty
    def id(cls) -> int:
        return 110

    async def init(self):
        pass
        #t0.txt="Server switching failed"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Confirm"
                self.changePage(MainPage)
 
    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ForgetPwdPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "forget_pwd"

    @classproperty
    def id(cls) -> int:
        return 111

    async def init(self):
        pass
        #t0.txt="Are you sure you want to\rremove this connection?"

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Confirm"
                self.changePage(MainPage)
            elif data.component_id == 1: #b1.txt="Cancel"
                self.changePage(MainPage)
 
    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BedHeatRulesPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "bed_heat_rules"

    @classproperty
    def id(cls) -> int:
        return 112

    async def init(self):
        pass
        #t0.txt="The hotbed temperature is too low,\rand it will automatically heat up."

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0: #b0.txt="Confirm"
                self.changePage(MainPage)
 
    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ZeroBoxPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "zero_box_page"

    @classproperty
    def id(cls) -> int:
        return 113

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            elif data.component_id == 1:
                #page_to(0x23);
                self.changePage(ControlPage)
            elif data.component_id == 2:
                self.changePage(UserGuidePage)
                #page_to(0x74);
            elif data.component_id == 3:
                #slot[0x10bc] = 0x71;
                #MultiColorSlots::SetLoadTarget();
                self.changePage(LoadStep1Page) #page_to(0x7f);
                #send_cmd_vis(tty_fd,"gm0","1");
            elif data.component_id == 4:
                #MultiColorSlots::SetLoadTarget();
                #filament_unload();
                self.changePage(UnloadPage) #page_to(0x28);
            elif data.component_id == 5:
                pass
                #puVar20 = (undefined4 *)MultiColorSlots::UpdateBoxStates((MultiColorSlots *)slot);
            elif data.component_id == 6:
                self.changePage(SlotParamsPage) #page_to(0x75);
                #MultiColorSlots::SetSingleSlot((MultiColorSlots *)slot,"a0");
            elif data.component_id == 7:
                pass
                #MultiColorSlots::SetSelectedSlotIndex((MultiColorSlots *)slot,0);
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class OneBoxPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "one_box_page"

    @classproperty
    def id(cls) -> int:
        return 114

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(ControlPage) #page_to(0x23);
            if data.component_id == 1:
                pass
                #MultiColorSlots::HandleUninstallEvent((MultiColorSlots *)slot);
            elif data.component_id == 2:
                pass
                #MultiColorSlots::HandleLoadEvent((MultiColorSlots *)slot);
            elif data.component_id == 3:
                pass
                #MultiColorSlots::HandleUnloadEvent((MultiColorSlots *)slot);
            elif data.component_id == 4:
                self.changePage(SlotParamsPage) #page_to(0x75);
            elif data.component_id == 5:
                self.changePage(SlotParamsPage)
            elif data.component_id == 6:
                self.changePage(SlotParamsPage)
            elif data.component_id == 7:
                self.changePage(SlotParamsPage)
            elif data.component_id == 8:
                self.changePage(SlotParamsPage)
            elif data.component_id == 9:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p5");
            elif data.component_id == 10:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p6");
            elif data.component_id == 11:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p7");
            elif data.component_id == 12:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p8");
            elif data.component_id == 13:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p9");
            elif data.component_id == 15:
                pass
                #MultiColorSlots::SetSelectedSlotIndex((MultiColorSlots *)slot,-1);
                #MultiColorSlots::SetSelectedBoxIndex((MultiColorSlots *)slot,0);
            elif data.component_id == 16:
                pass
                #MultiColorSlots::SetSelectedSlotIndex((MultiColorSlots *)slot,-1);
                #MultiColorSlots::SetSelectedBoxIndex((MultiColorSlots *)slot,1);
            elif data.component_id == 17:
                pass
                #MultiColorSlots::SetSelectedSlotIndex((MultiColorSlots *)slot,-1);
                #MultiColorSlots::SetSelectedBoxIndex((MultiColorSlots *)slot,2);
            elif data.component_id == 18:
                pass
                #MultiColorSlots::SetSelectedSlotIndex((MultiColorSlots *)slot,-1);
                #MultiColorSlots::SetSelectedBoxIndex((MultiColorSlots *)slot,3);
            elif data.component_id == 19:
                self.changePage(BoxSettingsPage) #page_to(0x85);
            elif data.component_id == 20:
                pass
                #MultiColorSlots::ControlShowKeypad((MultiColorSlots *)slot,"display");
            elif data.component_id == 23:
                pass
                #MultiColorSlots::HandleRetryEvent();
            elif data.component_id == 39:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x28);
            elif data.component_id == 40:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x29);
            elif data.component_id == 41:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2a);
            elif data.component_id == 42:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2b);
            elif data.component_id == 43:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2c);
            elif data.component_id == 44:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2d);
            elif data.component_id == 45:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2e);
            elif data.component_id == 46:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2f);
            elif data.component_id == 47:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x30);
            elif data.component_id == 48:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x31);
            elif data.component_id == 49:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x32);
            elif data.component_id == 50:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x33);
            elif data.component_id == 70:
                pass
                #MultiColorSlots::HandleRfidEvent((MultiColorSlots *)slot);
            elif data.component_id == 71:
                pass
                #MultiColorSlots::HandleRfidEvent((MultiColorSlots *)slot);
            elif data.component_id == 72:
                pass
                #MultiColorSlots::HandleRfidEvent((MultiColorSlots *)slot);
            elif data.component_id == 73:
                pass
                #MultiColorSlots::HandleRfidEvent((MultiColorSlots *)slot);
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class MultiBoxPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "multi_box_page"

    @classproperty
    def id(cls) -> int:
        return 115

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(ControlPage) #page_to(0x23);
            if data.component_id == 1:
                pass
                #MultiColorSlots::HandleUninstallEvent((MultiColorSlots *)slot);
            elif data.component_id == 2:
                pass
                #MultiColorSlots::HandleLoadEvent((MultiColorSlots *)slot);
            elif data.component_id == 3:
                pass
                #MultiColorSlots::HandleUnloadEvent((MultiColorSlots *)slot);
            elif data.component_id == 4:
                pass
                #MultiColorSlots::SetSingleSlot((MultiColorSlots *)slot,"a0");
            elif data.component_id == 5:
                #MultiColorSlots::GetSelectedBox[abi:cxx11]();
                #MultiColorSlots::SetMultiColorSlot((MultiColorSlots *)slot,asStack_4b8,1);
                self.changePage(SlotParamsPage) #page_to(0x75);
            elif data.component_id == 6:
                #MultiColorSlots::GetSelectedBox[abi:cxx11]();
                #MultiColorSlots::SetMultiColorSlot((MultiColorSlots *)slot,asStack_498,2);
                self.changePage(SlotParamsPage)
            elif data.component_id == 7:
                #MultiColorSlots::GetSelectedBox[abi:cxx11]();
                #MultiColorSlots::SetMultiColorSlot((MultiColorSlots *)slot,asStack_478,3);
                self.changePage(SlotParamsPage)
            elif data.component_id == 8:
                #MultiColorSlots::GetSelectedBox[abi:cxx11]();
                #MultiColorSlots::SetMultiColorSlot((MultiColorSlots *)slot,asStack_458,4);
                self.changePage(SlotParamsPage)
            elif data.component_id == 9:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p5");
            elif data.component_id == 10:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p6");
            elif data.component_id == 11:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p7");
            elif data.component_id == 12:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p8");
            elif data.component_id == 13:
                pass
                #MultiColorSlots::UpdateSlotOperationUI((MultiColorSlots *)slot,"p9");
            elif data.component_id == 15:
                pass
                '''
                iVar9 = MultiColorSlots::GetStatusBox1((MultiColorSlots *)slot);
                if (iVar9 == 0) {
                    page_to(0x7a);
                    MultiColorSlots::GetSelectedBox[abi:cxx11]();
                            /* try { // try from 0073ae40 to 0073ae43 has its CatchHandler @ 0073ce0c */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_370);
                    puVar20 = (undefined4 *)std::__cxx11::string::~string(asStack_370);
                }
                else {
                    std::allocator<char>::allocator();
                            /* try { // try from 0073ae70 to 0073ae73 has its CatchHandler @ 0073ce30 */
                    std::__cxx11::string::string<>(asStack_350,"box1",aaStack_330);
                            /* try { // try from 0073ae84 to 0073ae87 has its CatchHandler @ 0073ce20 */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_350);
                    std::__cxx11::string::~string(asStack_350);
                    std::allocator<char>::~allocator((allocator<char> *)aaStack_330);
                    puVar20 = (undefined4 *)page_to(0x73);
                }
                '''
            elif data.component_id == 16:
                pass
                '''
                iVar9 = MultiColorSlots::GetStatusBox2((MultiColorSlots *)slot);
                if (iVar9 == 0) {
                    page_to(0x7a);
                    MultiColorSlots::GetSelectedBox[abi:cxx11]();
                            /* try { // try from 0073aef0 to 0073aef3 has its CatchHandler @ 0073ce44 */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_328);
                    puVar20 = (undefined4 *)std::__cxx11::string::~string(asStack_328);
                }
                else {
                    std::allocator<char>::allocator();
                            /* try { // try from 0073af20 to 0073af23 has its CatchHandler @ 0073ce68 */
                    std::__cxx11::string::string<>(asStack_308,"box2",aaStack_2e8);
                            /* try { // try from 0073af34 to 0073af37 has its CatchHandler @ 0073ce58 */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_308);
                    std::__cxx11::string::~string(asStack_308);
                    std::allocator<char>::~allocator((allocator<char> *)aaStack_2e8);
                    puVar20 = (undefined4 *)page_to(0x73);
                }
                '''
            elif data.component_id == 17:
                pass
                '''
                iVar9 = MultiColorSlots::GetStatusBox3((MultiColorSlots *)slot);
                if (iVar9 == 0) {
                    page_to(0x7a);
                    MultiColorSlots::GetSelectedBox[abi:cxx11]();
                            /* try { // try from 0073afa0 to 0073afa3 has its CatchHandler @ 0073ce7c */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_2e0);
                    puVar20 = (undefined4 *)std::__cxx11::string::~string(asStack_2e0);
                }
                else {
                    std::allocator<char>::allocator();
                            /* try { // try from 0073afd0 to 0073afd3 has its CatchHandler @ 0073cea0 */
                    std::__cxx11::string::string<>(asStack_2c0,"box3",aaStack_2a0);
                            /* try { // try from 0073afe4 to 0073afe7 has its CatchHandler @ 0073ce90 */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_2c0);
                    std::__cxx11::string::~string(asStack_2c0);
                    std::allocator<char>::~allocator((allocator<char> *)aaStack_2a0);
                    puVar20 = (undefined4 *)page_to(0x73);
                }
                '''
            elif data.component_id == 18:
                pass
                '''
                iVar9 = MultiColorSlots::GetStatusBox4((MultiColorSlots *)slot);
                if (iVar9 == 0) {
                    page_to(0x7a);
                    MultiColorSlots::GetSelectedBox[abi:cxx11]();
                            /* try { // try from 0073b050 to 0073b053 has its CatchHandler @ 0073ceb4 */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_298);
                    puVar20 = (undefined4 *)std::__cxx11::string::~string(asStack_298);
                }
                else {
                    std::allocator<char>::allocator();
                            /* try { // try from 0073b080 to 0073b083 has its CatchHandler @ 0073ced8 */
                    std::__cxx11::string::string<>(asStack_278,"box4",aaStack_258);
                            /* try { // try from 0073b094 to 0073b097 has its CatchHandler @ 0073cec8 */
                    MultiColorSlots::SetSelectedBox((MultiColorSlots *)slot,asStack_278);
                    std::__cxx11::string::~string(asStack_278);
                    std::allocator<char>::~allocator((allocator<char> *)aaStack_258);
                    puVar20 = (undefined4 *)page_to(0x73);
                }
                '''
            elif data.component_id == 20:
                pass
                #MultiColorSlots::ControlShowKeypad((MultiColorSlots *)slot,"display");
            elif data.component_id == 39:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x28);
            elif data.component_id == 40:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x29);
            elif data.component_id == 41:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2a);
            elif data.component_id == 42:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2b);
            elif data.component_id == 43:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2c);
            elif data.component_id == 44:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2d);
            elif data.component_id == 45:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2e);
            elif data.component_id == 46:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x2f);
            elif data.component_id == 47:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x30);
            elif data.component_id == 48:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x31);
            elif data.component_id == 49:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x32);
            elif data.component_id == 50:
                pass
                #MultiColorSlots::HandleKeypadEvent((MultiColorSlots *)slot,0x33);
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class UserGuidePage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "user_guide"

    @classproperty
    def id(cls) -> int:
        return 116

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 1:
                self.changePage(ControlPage) #page_to(0x23);
            if data.component_id == 2:
                self.changePage(ZeroBoxPage) #page_to(0x71);
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class SlotParamsPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "slot_params"

    @classproperty
    def id(cls) -> int:
        return 117

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 1:
                self.changePage(VendorSetPage) #page_to(0x76);
            if data.component_id == 2:
                self.changePage(FilamentSetPage) #page_to(0x77);
            if data.component_id == 3:
                self.changePage(ColorSetPage) #page_to(0x78);
            if data.component_id == 4:
                pass
                #MultiColorSlots::SlotParamsSetConfirm((MultiColorSlots *)slot);
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class VendorSetPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "vendor_set"

    @classproperty
    def id(cls) -> int:
        return 118

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class FilamentSetPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "filament_set"

    @classproperty
    def id(cls) -> int:
        return 119

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class ColorSetPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "color_set"

    @classproperty
    def id(cls) -> int:
        return 120

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class McPrintSetPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "mc_print_set"

    @classproperty
    def id(cls) -> int:
        return 121

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class UnconnectPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "unconnect_pop"

    @classproperty
    def id(cls) -> int:
        return 122

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class VendorPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "vendor_pop"

    @classproperty
    def id(cls) -> int:
        return 123

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BoxErrorPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "box_error_pop"

    @classproperty
    def id(cls) -> int:
        return 124

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DataPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "data_pop"

    @classproperty
    def id(cls) -> int:
        return 125

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class NoFilaPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "no_fila_pop"

    @classproperty
    def id(cls) -> int:
        return 126

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class LoadStep1Page(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "load_step1"

    @classproperty
    def id(cls) -> int:
        return 127

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class LoadStep2Page(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "load_step2"

    @classproperty
    def id(cls) -> int:
        return 128

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BoxUnlinkPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "box_unlink_pop"

    @classproperty
    def id(cls) -> int:
        return 129

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BoxLinkPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "box_link_pop"

    @classproperty
    def id(cls) -> int:
        return 130

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BoxUpdatePopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "box_update_pop"

    @classproperty
    def id(cls) -> int:
        return 131

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class LoadErrorPopPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "load_error_pop"

    @classproperty
    def id(cls) -> int:
        return 132

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BoxSettingsPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "box_setting"

    @classproperty
    def id(cls) -> int:
        return 133

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class FilaNotMatchPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "fila_not_match"

    @classproperty
    def id(cls) -> int:
        return 134

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class BoxDryingPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "box_drying"

    @classproperty
    def id(cls) -> int:
        return 135

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class DryingInspPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "drying_insp"

    @classproperty
    def id(cls) -> int:
        return 136

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class Page0Page(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "page0"

    @classproperty
    def id(cls) -> int:
        return 137

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                pass
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass

'''
class FilamentPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "filament"

    @classproperty
    def id(cls) -> int:
        return 62

    # Element image id's
    _regular = 176
    _highlight = 177

    def isHeating(self, heaterData: dict) -> bool:
        return heaterData["target"] > heaterData["temperature"]

    async def setHighlight(self, element: str, highlight: bool):
        await self.state.display.set(
            "%s.picc" % element, self._highlight if highlight else self._regular
        )

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 23:
                self.changePage(ControlPage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        await self.state.display.set(
            "t0.txt", str(int(data["extruder"]["temperature"]))
        )
        await self.state.display.set("n0.val", int(data["extruder"]["target"]))
        await self.setHighlight("b2", self.isHeating(data["extruder"]))
        await self.setHighlight("b0", self.isHeating(data["extruder"]))

        await self.state.display.set(
            "t1.txt", str(int(data["heater_bed"]["temperature"]))
        )
        await self.state.display.set("n1.val", int(data["heater_bed"]["target"]))
        await self.setHighlight("b3", self.isHeating(data["heater_bed"]))
        await self.setHighlight("b1", self.isHeating(data["heater_bed"]))

        await self.state.display.set(
            "t2.txt", str(int(data["heater_generic chamber"]["temperature"]))
        )
        await self.state.display.set(
            "n2.val", int(data["heater_generic chamber"]["target"])
        )
        await self.setHighlight("b12", self.isHeating(data["heater_generic chamber"]))
        await self.setHighlight("b13", self.isHeating(data["heater_generic chamber"]))


class CalibrationPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "level_mode"

    @classproperty
    def id(cls) -> int:
        return 27

    async def onDisplayEvent(self, type: EventType, data):
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 23:
                self.changePage(SettingsPage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class PrintingPage2(OpenP4Page):

    @classproperty
    def name(cls) -> str:
        return "printing2"

    @classproperty
    def id(cls) -> int:
        return 12
    
    # Element image id's
    _regular = 32
    _highlight = 33

    # Thumbnail
    filename = ""

    async def init(self):
        pass

    async def onDisplayEvent(self, type: EventType, data):
        #log.info(f"PrintingPage2: onDisplayEvent: EventType: {type}, data: {data}")

        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 0:
                self.changePage(PrintingPage)
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass


class KeypadPage(OpenP4Page):
    @classproperty
    def name(cls) -> str:
        return "keybdB"

    @classproperty
    def id(cls) -> int:
        return 9
    
    async def init(self):
        self.input_value = ""
        # Initialize display components

        await self.state.display.set("t2.txt", "") # start progress time
        await self.state.display.set("t3.txt", "") # end progress time
        await self.state.display.set("j0.val", 0) # progress bar
        await self.state.display.set("t4.txt", "") # progress time
        await self.state.display.set("n7.val", 0) # progress time
        await self.state.display.set("t100.txt", "") # name for what set temperature

        await self.state.display.set("inputlenth.val", 3)  # Max input length
        await self.state.display.set("show.txt", "")      # Clear display field

        # Show heater name from state
        if hasattr(self.state.heater_manager, 'heater_data'):
            heater_data = self.state.heater_manager.heater_data
            await self.state.display.set("t100.txt", heater_data["title"])
            await self.state.display.set("inputlenth.val", heater_data["max_digits"])

        if not hasattr(self.state, 'return_page'):
            self.state.return_page = MainPage

    async def onDisplayEvent(self, type: EventType, data):
        log.info(f"KeypadPage: onDisplayEvent: EventType: {type.name}, data: {data}")
        if type == EventType.TOUCH:
            self.handleScreenSleep(data.page_id)
            if data.component_id == 32:  # Back button
               self.changePage(self.state.return_page)
               self.state.return_page = None  # Clear return page
            elif data.component_id == 31: # set temperature button
                value = await self.state.display.get("input.txt")
                temp = int(value)
                log.info(f"Get temperature (int): {temp}")
                
                # Call callback function for set temperature
                heater_data = self.state.heater_manager.heater_data
                heater_data["callback"](temp)
                
                # Return to stored page
                self.changePage(self.state.return_page)
                self.state.return_page = None  # Clear return page
            else:
                self.handleNavBarButtons(data.component_id)

    async def onPrinterStatusUpdate(self, data: dict):
        pass
'''