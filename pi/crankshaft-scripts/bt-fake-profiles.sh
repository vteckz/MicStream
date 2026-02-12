#!/bin/bash
# Register fake HFP/HSP profiles that newer Android phones need
# to identify this device as a car head unit for Android Auto
sleep 2
sdptool add --channel=12 HFAG
sdptool add --channel=13 HS
sdptool add --channel=14 HF
echo 'Fake BT profiles registered for AA'
