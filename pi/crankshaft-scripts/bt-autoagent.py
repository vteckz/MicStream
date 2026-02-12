#!/usr/bin/python3
"""Bluetooth auto-accept agent for CrankshaftNG"""
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

BUS_NAME = 'org.bluez'
AGENT_INTERFACE = 'org.bluez.Agent1'
AGENT_PATH = '/crankshaft/agent'

class AutoAcceptAgent(dbus.service.Object):
    @dbus.service.method(AGENT_INTERFACE, in_signature='', out_signature='')
    def Release(self):
        pass

    @dbus.service.method(AGENT_INTERFACE, in_signature='os', out_signature='')
    def AuthorizeService(self, device, uuid):
        print(f'AuthorizeService: {device} {uuid}')
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature='o', out_signature='s')
    def RequestPinCode(self, device):
        print(f'RequestPinCode: {device}')
        return '0000'

    @dbus.service.method(AGENT_INTERFACE, in_signature='o', out_signature='u')
    def RequestPasskey(self, device):
        print(f'RequestPasskey: {device}')
        return dbus.UInt32(0)

    @dbus.service.method(AGENT_INTERFACE, in_signature='ouq', out_signature='')
    def DisplayPasskey(self, device, passkey, entered):
        print(f'DisplayPasskey: {device} {passkey}')

    @dbus.service.method(AGENT_INTERFACE, in_signature='os', out_signature='')
    def DisplayPinCode(self, device, pincode):
        print(f'DisplayPinCode: {device} {pincode}')

    @dbus.service.method(AGENT_INTERFACE, in_signature='ou', out_signature='')
    def RequestConfirmation(self, device, passkey):
        print(f'RequestConfirmation: {device} {passkey} -> auto-accepting')
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature='o', out_signature='')
    def RequestAuthorization(self, device):
        print(f'RequestAuthorization: {device} -> auto-accepting')
        return

    @dbus.service.method(AGENT_INTERFACE, in_signature='', out_signature='')
    def Cancel(self):
        print('Cancel')

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    agent = AutoAcceptAgent(bus, AGENT_PATH)
    manager = dbus.Interface(bus.get_object(BUS_NAME, '/org/bluez'), 'org.bluez.AgentManager1')
    manager.RegisterAgent(AGENT_PATH, 'NoInputNoOutput')
    manager.RequestDefaultAgent(AGENT_PATH)
    print('Auto-accept agent registered')
    GLib.MainLoop().run()
