"""
This module implements the interface to Motion Blinds.

:copyright: (c) 2020 starkillerOG.
:license: MIT, see LICENSE for more details.
"""
import logging
import socket
import json
import datetime
from Cryptodome.Cipher import AES
from threading import Thread
import time

_LOGGER = logging.getLogger(__name__)

blindsDeviceType = ['10000000', '10000002']
hubDeviceType = '02000001'
udpIpAddress = '238.0.0.18'
sendPort = 32100
receivePort = 32101
bufferSize = 2048
one_way_wirelessMode = [0, 2]
two_way_wirelessMode = [1, 3, 4]

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)


def getMsgId():
    """get msgid"""
    msgId = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[0: 17]
    return msgId


def sendData(data):
    s.sendto(bytes(json.dumps(data), 'utf-8'), (udpIpAddress, sendPort))


class ConnectorHub:
    """Main class"""

    def __init__(self, ip, key):
        self._ip = ip
        self._key = key
        self._token = None
        self._accessToken = None
        self._thread01 = None
        self._exit_thread = False
        self.s = None
        self.ANY = "0.0.0.0"
        self._deviceList = {}

    def _joinGroupControl(self):
        try:
            # s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.ANY, receivePort))
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
            s.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                socket.inet_aton(udpIpAddress) + socket.inet_aton(self.ANY)
            )
            s.setblocking(True)
        except OSError:
            _LOGGER.error("Port is occupied")
        except Exception as e:
            _LOGGER.error(e)
        else:
            _LOGGER.info("连接端口成功")

    def _get_access_token(self, token):
        """To get the accessToken"""
        if token is None:
            return None
        if self._key is None:
            return None
        token_bytes = bytes(token, 'utf-8')
        key_bytes = bytes(self._key, 'utf-8')
        cipher = AES.new(key_bytes, AES.MODE_ECB)
        encrypted_bytes = cipher.encrypt(token_bytes)
        self._accessToken = encrypted_bytes.hex().upper()
        return self._accessToken

    def _receive_data(self):
        while True:
            if self._exit_thread:
                break
            try:
                data, address = s.recvfrom(2048)
                data_json = json.loads(data.decode("UTF-8"))
                if address[0] in self._ip:
                    if hasattr(self, data_json['msgType']):
                        attr = getattr(self, data_json['msgType'])
                        attr(data_json)
                else:
                    pass
            except Exception as e:
                print(e)
                pass

    def GetDeviceListAck(self, data):
        self._get_access_token(data['token'])
        self._deviceList[data['mac']] = Hub(mac=data['mac'], version=data['ProtocolVersion'], token=data['token'],
                                            accessToken=self._accessToken, deviceType=data['deviceType'])
        for item in data['data']:
            if item['deviceType'] in blindsDeviceType:
                self._get_device_info(mac=item['mac'], deviceType=item['deviceType'])

    def ReadDeviceAck(self, data):
        hub_mac = data['mac'][:12]
        self._deviceList[hub_mac].add_blinds(data)

    def Report(self, data):
        """return the hub mac"""
        print("进入了report")
        hub_mac = data['mac'][:12]
        blind_mac = data['mac']
        currentPosition = data['data']['currentPosition']
        currentAngle = data['data']['currentAngle']
        self._deviceList[hub_mac].blinds[blind_mac].setAngle(currentAngle)
        self._deviceList[hub_mac].blinds[blind_mac].setPosition(currentPosition)
        self._deviceList[hub_mac].blinds[blind_mac].runCallback()

    def _get_device_info(self, mac, deviceType):
        data = {"msgType": "ReadDevice",
                "msgID": getMsgId(),
                "deviceType": deviceType,
                "mac": mac,
                "AccessToken": self._accessToken}
        sendData(data)

    def close_receive_data(self):
        self._exit_thread = True
        s.close()

    def start_receive_data(self):
        self._joinGroupControl()
        self._exit_thread = False
        self._thread01 = Thread(target=self._receive_data)
        self._thread01.start()
        self.get_device_list()

    def _isMacInList(self, mac):
        """Is the mac address in the list?"""
        for hub in self.deviceList:
            for blind in hub['blinds']:
                if blind['mac'] == mac:
                    return blind['deviceType']
        return None

    def get_device_list(self):
        """Get device list"""
        data = {"msgType": "GetDeviceList", "msgID": getMsgId()}
        self._deviceList = {}
        sendData(data)

    def blindType(self, mac):
        """get the type of blind"""
        pass

    @property
    def deviceList(self):
        """return the device list"""
        time.sleep(3)
        return self._deviceList


class Hub:
    def __init__(self, mac, version, token, accessToken, deviceType):
        self._mac = mac
        self._version = version
        self._toen = token
        self._accesstoken = accessToken
        self._blinds = {}
        self._deviceType = deviceType
        # self._blinds = {}

    def add_blinds(self, blind):
        print("添加设备")
        mac = blind['mac']
        if blind['data']['wirelessMode'] in one_way_wirelessMode:
            self._blinds[mac] = OneWayBlind(mac=blind['mac'],
                                            deviceType=blind['deviceType'],
                                            wirelessMode=blind['data']['wirelessMode'],
                                            accessToken=self._accesstoken,
                                            type=blind['data']['type'])
        elif blind['data']['wirelessMode'] in two_way_wirelessMode:
            self._blinds[mac] = TwoWayBlind(mac=blind['mac'],
                                            deviceType=blind['deviceType'],
                                            wirelessMode=blind['data']['wirelessMode'],
                                            accessToken=self._accesstoken,
                                            position=blind['data']['currentPosition'],
                                            type=blind['data']['type'],
                                            angle=blind['data']['currentAngle'])
        else:
            _LOGGER.warning("This wirelessMode not support")

    @property
    def blinds_list(self):
        """return all blinds"""
        return self._blinds

    @property
    def hub_version(self):
        """return hub version"""
        return self._version

    @property
    def hub_mac(self):
        """return hub mac"""
        return self._mac

    @property
    def blinds(self):
        """return blinds list"""
        return self._blinds


class OneWayBlind:
    def __init__(self, mac, deviceType, wirelessMode, accessToken, type):
        self._mac = mac
        self._deviceType = deviceType
        self._wirelessMode = wirelessMode
        self._accessToken = accessToken
        self._callBack = None
        self._type = type

    def Open(self):
        operation = {"operation": 1}
        self._WriteDevice(operation)

    def Close(self):
        operation = {"operation": 0}
        self._WriteDevice(operation)

    def Stop(self):
        operation = {"operation": 2}
        self._WriteDevice(operation)

    def _WriteDevice(self, operation):
        data = {"msgType": "WriteDevice",
                "msgID": getMsgId(),
                "deviceType": self._deviceType,
                "mac": self._mac,
                "AccessToken": self._accessToken,
                "data": operation}
        sendData(data)

    @property
    def mac(self):
        """return blind mac"""
        return self._mac

    @property
    def type(self):
        """return blind type"""
        return self._type

    @property
    def wirelessMode(self):
        """return blind wirelessMode"""
        return self._wirelessMode

    def registerCallback(self, func):
        """register the callback"""
        print("进入了注册callback")
        self._callBack = func

    def removeCallback(self):
        """remove the callback"""
        self._callBack = None

    def runCallback(self):
        """run the call back function"""
        print("进入了运行callback")
        if self._callBack is None:
            _LOGGER.warning("This blind not register callback function")
            return
        self._callBack()


class TwoWayBlind:
    def __init__(self, mac, deviceType, wirelessMode, accessToken, position, type, angle: int = None):
        self._mac = mac
        self._deviceType = deviceType
        self._wirelessMode = wirelessMode
        self._accessToken = accessToken
        self.isOpening = False
        self.isClosing = False
        self._position = position
        self._callBack = None
        self._type = type
        self._angle = angle
        print("添加了双向设备")

    def Open(self):
        operation = {"operation": 1}
        self._WriteDevice(operation)

    def Close(self):
        operation = {"operation": 0}
        self._WriteDevice(operation)

    def Stop(self):
        operation = {"operation": 2}
        self._WriteDevice(operation)

    def TargetPosition(self, percent):
        if int(percent) > 100 or int(percent) < 0:
            _LOGGER.warning("Percent must in 0~100")
        operation = {"targetPosition": percent}
        self._WriteDevice(operation)

    def TargetAngle(self, angle):
        if int(angle) > 180 or int(angle) < 0:
            _LOGGER.warning("Angle must in 0~180")
            return
        operation = {"targetAngle": int(angle)}
        self._WriteDevice(operation)

    def updateState(self):
        operation = {"operation": 5}
        self._WriteDevice(operation)
        pass

    def _WriteDevice(self, operation):
        data = {"msgType": "WriteDevice",
                "msgID": getMsgId(),
                "deviceType": self._deviceType,
                "mac": self._mac,
                "AccessToken": self._accessToken,
                "data": operation}
        sendData(data)

    @property
    def mac(self):
        """return blind mac"""
        return self._mac

    @property
    def isClosed(self):
        """return if the cover is closed or not"""
        return self._position == 100

    @property
    def position(self):
        """return current position of the blind"""
        return self._position

    @property
    def angle(self):
        """return current angle of the blind"""
        return self._angle

    @property
    def type(self):
        """return blind type"""
        return self._type

    @property
    def wirelessMode(self):
        """return blind wirelessMode"""
        return self._wirelessMode

    def setPosition(self, position):
        """when receive the report, use this to change position"""
        self._position = position

    def setAngle(self, angle):
        """when receive the report, use this to change angle"""
        self._angle = angle

    def registerCallback(self, func):
        """register the callback"""
        print("进入了注册callback")
        self._callBack = func

    def removeCallback(self):
        """remove the callback"""
        self._callBack = None

    def runCallback(self):
        """run the call back function"""
        print("进入了运行callback")
        if self._callBack is None:
            _LOGGER.warning("This blind not register callback function")
            return
        self._callBack()


# if __name__ == "__main__":
#     hub = ConnectorHub(key="83680a64-15f4-40", ip=["192.168.31.69", "192.168.50.50"])
#     hub.start_receive_data()
#     hubs = hub.deviceList
#     print("hubs:", hubs)
#     for hub in hubs.values():
#         for blind in hub.blinds.values():
#             print(hub.blinds)
#             blind.Open()
