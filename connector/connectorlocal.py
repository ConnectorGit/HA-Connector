"""This module implements the interface to Connector Hub.

:copyright: (c) 2023 Connector.
:license: MIT, see LICENSE for more details.
"""

import datetime
import json
import logging
import socket
from threading import Thread, Timer
from Cryptodome.Cipher import AES
import asyncio

_LOGGER = logging.getLogger(__name__)
BLINDSDEVICETYPE = ["10000000", "10000002", "10000011"]
HUBDEVICETYPE = "02000001"
WIFIMOTORTYPE = ["22000002", "22000000", "22000005"]
VENETIANTYPE = [2]
UDPIPADDRESS = "238.0.0.18"
SENDPORT = 32100
RECEIVEPORT = 32101
BUFFERSIZE = 2048
ONEWAYWIRELESSMODE = [0, 2]
TWOWAYWIRELESSMODE = [1, 3, 4]


def get_msgid():
    """Get msgid."""
    msgid = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[0:17]
    return msgid


async def delay(seconds):
    await asyncio.sleep(seconds)


class ConnectorHub:
    """Main class."""

    def __init__(self, ip, key):
        """Init ConnectorHub class."""
        self._ip = ip
        self._key = key
        self._token = None
        self._accesstoken = None
        self._thread01 = None
        self._exit_thread = False
        self.any = "0.0.0.0"
        self._device_list = {}
        self._listening = False
        self._mysocket = None
        self._isconnected = False
        self._errorcode = 1000
        self._test = 10
        self._need_read_devicelist = []
        self._readdevicelist_havedone = False
        self._have_readdevice_thread = False

    def _join_group_control(self):
        """Use it to join Group Control."""
        try:
            self._mysocket = socket.socket(
                socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP
            )
            self._mysocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._mysocket.bind((self.any, RECEIVEPORT))
            self._mysocket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            self._mysocket.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                socket.inet_aton(UDPIPADDRESS) + socket.inet_aton(self.any),
            )
            self._mysocket.setblocking(True)
            self._isconnected = True
            self._isconnected = 1000
        except OSError:
            _LOGGER.error("Port is occupied")
            self._mysocket.close()
            self._isconnected = False
            self._errorcode = 1002
        else:
            _LOGGER.info("Open port success")

    def _get_access_token(self, token):
        """To get the accessToken."""
        if token is None:
            return None
        if self._key is None:
            return None
        token_bytes = bytes(token, "utf-8")
        key_bytes = bytes(self._key, "utf-8")
        cipher = AES.new(key_bytes, AES.MODE_ECB)
        encrypted_bytes = cipher.encrypt(token_bytes)
        self._accesstoken = encrypted_bytes.hex().upper()
        return self._accesstoken

    def _receive_data(self):
        """Receive data from udp group port."""
        while not self._exit_thread:
            try:
                data, address = self._mysocket.recvfrom(4096)
                data_json = json.loads(data.decode("UTF-8"))
                if address[0] in self._ip:
                    msg_type = data_json["msgType"]
                    if "actionResult" in data_json:
                        if data_json["actionResult"] == "AccessToken error":
                            self._errorcode = 1001
                            break
                    if msg_type == "Report":
                        self._report(data_json)
                    elif msg_type == "GetDeviceListAck":
                        t = Thread(
                            target=self._get_devicelist_ack, kwargs={"data": data_json}
                        )
                        t.start()
                    elif msg_type == "ReadDeviceAck":
                        self._read_deviceack(data_json)
                    elif msg_type == "WriteDeviceAck":
                        self._write_deviceack(data_json)
                else:
                    _LOGGER.info("This message is not in the IP list")
            except OSError:
                _LOGGER.error("Port is occupied")
                self._errorcode = 1002
                self._isconnected = False
                break

    def _send_data(self, data):
        """Send data to UDP Port."""
        try:
            self._mysocket.sendto(
                bytes(json.dumps(data), "utf-8"), (UDPIPADDRESS, SENDPORT)
            )
        except socket.timeout:
            _LOGGER.warning("Send data time out")
        except OSError:
            self._isconnected = False
            self._errorcode = 1002
            _LOGGER.warning("Send port is occupied")
        except AttributeError:
            _LOGGER.warning("Socket object is none")

    def _get_devicelist_ack(self, data):
        """Deal with GetDeviceListAck message."""
        self._get_access_token(data["token"])
        if data["deviceType"] in WIFIMOTORTYPE:
            self._device_list[data["mac"]] = TwoWayBlind(
                mac=data["mac"],
                accesstoken=self._accesstoken,
                devicetype=data["deviceType"],
                func=self._send_data,
            )
        else:
            self._device_list[data["mac"]] = Hub(
                mac=data["mac"],
                version=data["fwVersion"],
                token=data["token"],
                access_token=self._accesstoken,
                devicetype=data["deviceType"],
                func=self._send_data,
            )
        for item in data["data"]:
            if item["deviceType"] in BLINDSDEVICETYPE:
                self._need_read_devicelist.append(item)
        if not self._have_readdevice_thread:
            t = Timer(3, self.read_devicelist)
            t.start()
            self._have_readdevice_thread = True

    def read_devicelist(self):
        count = 0
        while len(self._need_read_devicelist) != 0 and count < 3:
            for item in self._need_read_devicelist:
                self._get_device_info(mac=item["mac"], devicetype=item["deviceType"])
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(delay(0.5))
                loop.close()
            count += 1
        self._readdevicelist_havedone = True

    def _read_deviceack(self, data):
        """Deal with ReadDeviceAck message."""
        hub_mac = data["mac"][:12]
        self._device_list[hub_mac].add_blinds(data)

    def _write_deviceack(self, data):
        """Deal with WriteDeviceAck message"""
        hub_mac = data["mac"][:12]
        self._device_list[hub_mac].add_blinds(data)
        if self._need_read_devicelist:
            try:
                self._need_read_devicelist.remove(
                    {"mac": data["mac"], "deviceType": data["deviceType"]}
                )
            except ValueError:
                _LOGGER.warning("Remove device not in list")

    def _report(self, data):
        """return the hub mac."""
        if data["deviceType"] in WIFIMOTORTYPE:
            mac = data["mac"]
            current_position = data["data"]["currentPosition"]
            current_angle = data["data"]["currentAngle"]
            self._device_list[mac].set_angle(current_angle)
            self._device_list[mac].set_position(current_position)
            self._device_list[mac].run_callback()
        else:
            hub_mac = data["mac"][:12]
            blind_mac = data["mac"]
            if "wirelessMode" in data["data"]:
                if data["data"]["wirelessMode"] in TWOWAYWIRELESSMODE:
                    current_position = data["data"]["currentPosition"]
                    current_angle = data["data"]["currentAngle"]
                    try:
                        self._device_list[hub_mac].blinds_list[blind_mac].set_angle(
                            current_angle
                        )
                        self._device_list[hub_mac].blinds_list[blind_mac].set_position(
                            current_position
                        )
                        self._device_list[hub_mac].blinds_list[blind_mac].run_callback()
                    except KeyError:
                        _LOGGER.warning(
                            "This motor is a newly added motor in the APP and is not synchronized to HA"
                        )

    def _get_device_info(self, mac, devicetype):
        """Get device info."""
        data = {
            "msgType": "WriteDevice",
            "msgID": get_msgid(),
            "deviceType": devicetype,
            "mac": mac,
            "AccessToken": self._accesstoken,
            "data": {"operation": 5},
        }
        self._send_data(data)

    def start_receive_data(self):
        """Join UDP multicast and create threads."""
        if self._listening:
            _LOGGER.info("32101 is listening")
        else:
            self._listening = True
            self._join_group_control()
            self._exit_thread = False
            self._thread01 = Thread(target=self._receive_data)
            self._thread01.start()
            self.get_device_list()
            self.get_device_list()

    def close_receive_data(self):
        """Close receive thread."""
        self._listening = False
        self._exit_thread = True
        if self._mysocket is not None:
            self._mysocket.close()
            self._mysocket = None

    def get_device_list(self):
        """Get device list."""
        data = {"msgType": "GetDeviceList", "msgID": get_msgid()}
        self._send_data(data)

    async def device_list(self):
        """Return the device list."""
        for i in range(20):
            if self._readdevicelist_havedone:
                return self._device_list
            await asyncio.sleep(1)
        return None

    @property
    def is_connected(self):
        """Return the connect status"""
        return self._isconnected

    @property
    def error_code(self):
        """Return the error code"""
        return self._errorcode


class Hub:
    """Hub Class."""

    def __init__(self, mac, version, token, access_token, devicetype, func):
        """Init Hub class."""
        self._mac = mac
        self._version = version
        self._toen = token
        self._accesstoken = access_token
        self._blinds = {}
        self._devicetype = devicetype
        self._send_data = func

    def add_blinds(self, blind):
        """Add blinds to blind list."""
        mac = blind["mac"]
        if mac not in self._blinds:
            if blind["data"]["wirelessMode"] in ONEWAYWIRELESSMODE:
                self._blinds[mac] = OneWayBlind(
                    mac=blind["mac"],
                    devicetype=blind["deviceType"],
                    wirelessmode=blind["data"]["wirelessMode"],
                    accesstoken=self._accesstoken,
                    blind_type=blind["data"]["type"],
                    func=self._send_data,
                )
            elif blind["data"]["wirelessMode"] in TWOWAYWIRELESSMODE:
                self._blinds[mac] = TwoWayBlind(
                    mac=blind["mac"],
                    devicetype=blind["deviceType"],
                    wirelessmode=blind["data"]["wirelessMode"],
                    accesstoken=self._accesstoken,
                    position=blind["data"]["currentPosition"],
                    blind_type=blind["data"]["type"],
                    angle=blind["data"]["currentAngle"],
                    func=self._send_data,
                )
            else:
                _LOGGER.warning("This wirelessMode not support")

    @property
    def blinds_list(self):
        """return all blinds."""
        return self._blinds

    @property
    def hub_version(self):
        """return hub version."""
        return self._version

    @property
    def hub_mac(self):
        """return hub mac."""
        return self._mac

    @property
    def devicetype(self):
        """return devicetype."""
        return self._devicetype

    def update_blinds(self):
        """update the position of the blinds."""
        for device in self._blinds.values():
            if device.wireless_mode in TWOWAYWIRELESSMODE:
                device.update_state()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(delay(0.5))
                loop.close()


class OneWayBlind:
    """One way blind class."""

    def __init__(self, mac, devicetype, wirelessmode, accesstoken, blind_type, func):
        """Init OneWayBlind class."""
        self._mac = mac
        self._devicetype = devicetype
        self._wireless_mode = wirelessmode
        self._accesstoken = accesstoken
        self._callback = None
        self._type = blind_type
        self._send_data = func

    def open(self):
        """open blind."""
        operation = {"operation": 1}
        self._write_device(operation)

    def close(self):
        """close blind."""
        operation = {"operation": 0}
        self._write_device(operation)

    def stop(self):
        """stop blind."""
        operation = {"operation": 2}
        self._write_device(operation)

    def _write_device(self, operation):
        """Send message to blind."""
        data = {
            "msgType": "WriteDevice",
            "msgID": get_msgid(),
            "deviceType": self._devicetype,
            "mac": self._mac,
            "AccessToken": self._accesstoken,
            "data": operation,
        }
        self._send_data(data)

    @property
    def mac(self):
        """return blind mac."""
        return self._mac

    @property
    def device_type(self):
        """return devicetype."""
        return self._devicetype

    @property
    def type(self):
        """return blind type."""
        return self._type

    @property
    def wireless_mode(self):
        """return blind wirelessMode."""
        return self._wireless_mode

    def register_callback(self, func):
        """register the callback."""
        self._callback = func

    def remove_callback(self):
        """remove the callback."""
        self._callback = None

    def run_callback(self):
        """run the call back function."""
        if self._callback is None:
            _LOGGER.warning("This one way blind not register callback function")
            return
        self._callback()


class TwoWayBlind:
    """Two way blind class."""

    def __init__(
        self,
        func,
        mac,
        devicetype,
        accesstoken,
        blind_type=1,
        position=0,
        wirelessmode=1,
        angle=0,
    ):
        """Init TwoWayBlind class."""
        self._mac = mac
        self._send_data = func
        self._devicetype = devicetype
        self._wireless_mode = wirelessmode
        self._accesstoken = accesstoken
        self.isopening = False
        self.isclosing = False
        self._position = position
        self._callback = None
        self._type = blind_type
        self._angle = angle

    def open(self):
        """Open blind."""
        operation = {"operation": 1}
        self._write_device(operation)

    def close(self):
        """Close blind."""
        operation = {"operation": 0}
        self._write_device(operation)

    def stop(self):
        """Stop blind."""
        operation = {"operation": 2}
        self._write_device(operation)

    def target_position(self, percent):
        """Percentage control."""
        if int(percent) > 100 or int(percent) < 0:
            _LOGGER.warning("Percent must in 0~100")
        operation = {"targetPosition": percent}
        self._write_device(operation)

    def target_angle(self, angle):
        """Angle control."""
        if int(angle) > 180 or int(angle) < 0:
            _LOGGER.warning("Angle must in 0~180")
            return
        operation = {"targetAngle": int(angle)}
        self._write_device(operation)

    def update_state(self):
        """update the position of the blind."""
        operation = {"operation": 5}
        self._write_device(operation)

    def _write_device(self, operation):
        """Send message to blind."""
        data = {
            "msgType": "WriteDevice",
            "msgID": get_msgid(),
            "deviceType": self._devicetype,
            "mac": self._mac,
            "AccessToken": self._accesstoken,
            "data": operation,
        }
        self._send_data(data)

    @property
    def mac(self):
        """return blind mac."""
        return self._mac

    @property
    def devicetype(self):
        """return blind mac."""
        return self._devicetype

    @property
    def isclosed(self):
        """return if the cover is closed or not."""
        return self._position == 100

    @property
    def position(self):
        """return current position of the blind."""
        return self._position

    @property
    def angle(self):
        """return current angle of the blind."""
        return self._angle

    @property
    def type(self):
        """return blind type."""
        return self._type

    @property
    def wireless_mode(self):
        """return blind wirelessMode."""
        return self._wireless_mode

    def set_position(self, position):
        """when receive the report, use this to change position."""
        self._position = position

    def set_angle(self, angle):
        """when receive the report, use this to change angle."""
        self._angle = angle

    def register_callback(self, func):
        """register the callback."""
        self._callback = func

    def remove_callback(self):
        """remove the callback."""
        self._callback = None

    def run_callback(self):
        """run the call back function."""
        if self._callback is None:
            return
        self._callback()