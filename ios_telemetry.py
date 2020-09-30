#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""telemetry_netconf Console Script.

Copyright (c) 2020 Cisco and/or its affiliates.

This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at

               https://developer.cisco.com/docs/licenses

All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.

"""

__author__ = "Russell Johnston"
__email__ = "rujohns2@cisco.com"
__version__ = "0.1.0"
__copyright__ = "Copyright (c) 2020 Cisco and/or its affiliates."
__license__ = "Cisco Sample Code License, Version 1.1"



from ncclient import manager
import xmltodict
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table


console = Console()

class NetDevice:
    def __init__(self, connect_info):
        self.host = connect_info['host']
        self.user = connect_info['user']
        self.password = connect_info['password']
        self.device_type = connect_info['dev_type']
        if 'port' in connect_info.keys():
            self.port = connect_info['port']
        else:
            self.port = 830
    
    def device_connect(self):
        self.session = manager.connect(
            host = self.host,
            port = self.port,
            username = self.user,
            password = self.password,
            hostkey_verify = False,
            device_params = {'name':self.device_type})
  

def get_subscriptions(filter, device):
    """
    Takes provided filer and device object and displays results
    in Table for device"""
    
    subscription_config = query_device(device.session, filter)
    
    if subscription_config is None:
        console.print(f"Error No Subscriptions Configured", style='red')
        return

    table = Table(title=f"Configured Telemetry Subscriptions {device.host}")
    table.add_column("ID", justify='right', style='cyan', no_wrap=True)
    table.add_column("Path", justify='center', style='magenta', no_wrap=False)
    table.add_column("Receiver", justify='center', style='green', no_wrap=False)
    table.add_column("Receiver Port", justify='center', style='green', no_wrap=False)

    subscriptions = subscription_config['mdt-config-data']['mdt-subscription']

    # is device has multiple subscriptions the returned value is stored in a list test for list to properly handle data structure
    if type(subscriptions) is list:
        for data in subscriptions:
            table.add_row(
                data['subscription-id'],
                data['base']['xpath'],
                data['mdt-receivers']['address'],
                data['mdt-receivers']['port'])
    else:
        table.add_row(
            subscriptions['subscription-id'],
            subscriptions['base']['xpath'],
            subscriptions['mdt-receivers']['address'],
            subscriptions['mdt-receivers']['port'])

    console.print(table)
    
    return subscription_config
    
def query_device(device, filter=None):
    # query a device for its configuration, a filter limits the scope

    query = device.get_config(source = 'running', filter = filter)
    data = xmltodict.parse(query.xml)['rpc-reply']['data']
    return data

def config_device(device, sub_id, xpath, recvr_ip):
    # using a Jinja2 template to store yang model and render with passed variables
    config_template = env.get_template('telemetry_config.jinja2')
    config = config_template.render(
        sub_id = sub_id,
        path = xpath,
        recvr = recvr_ip
    )
    config_resp = device.edit_config(config, target= 'running')
    console.print(config_resp)

def del_subscription(device, sub_id):
    del_template = f"""
    <config>
        <mdt-config-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-mdt-cfg">
            <mdt-subscription operation="delete">
                <subscription-id>{sub_id}</subscription-id>
            </mdt-subscription>
        </mdt-config-data>
    </config>
    """
    try:
        del_response = device.edit_config(del_template, target='running')
        console.print(del_response)
        return del_response
    except:
        console.print(f"Error Subscription {sub_id} not Configured", style='red')

    

if __name__ == "__main__":
    
    # list of devices, update with device information and add additional
    # dictionaries of devices, if a non-standard port for netconf add 'port'
    # key and value 
    devices = [
        {
            'host':'{{fqdn_or_deviceIP}}',
            'user':'{{username}}',
            'password':'{{password}}',
            'dev_type':'iosxe'
        }
    ]

    # Set the current directory for source of environment
    file_loader = FileSystemLoader('.')
    env = Environment(loader=file_loader)

    filter = """
        <filter>
        <mdt-config-data xmlns="http://cisco.com/ns/yang/Cisco-IOS-XE-mdt-cfg">
            <mdt-subscription></mdt-subscription>
        </mdt-config-data>
        </filter>
        """
    option = ''
    connections = []
    while option is not '4':
            
        print('Select an Option Below')
        option = input("""
1 - Get Current Subscription
2 - Configure New Subscription
3 - Delete Subscription
4 - Exit
    
""")
        if len(connections) is 0:
            # Set up connections to devices
            for device in devices:
                session = NetDevice(device)
                session.device_connect()
                connections.append(session)

        if option == '1':
            # Get the Currently Configured Subscriptions On Each Device
            for session in connections:
                get_subscriptions(filter, session)
        
        elif option == '2':
            new_sub = int(input("Enter Subscription Number:\n"))
            xpath = input("Enter Subscription xpath:\n")
            reciever = input("Enter Destination Reciever IP Address:\n")
            
            for session in connections:
                config_device(session.session, new_sub, xpath, reciever)
        
        elif option == '3':
            del_sub = int(input("Enter Subscription Number:\n"))
            for session in connections:
                del_subscription(session.session, del_sub)
    
    console.print('Closing Connections to Devices')
    for session in connections:
        if session.session.connected:
            session.session.close_session()

    console.print('Sessions Graceful Disconnected')
