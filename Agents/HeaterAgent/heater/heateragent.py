from __future__ import absolute_import
from datetime import datetime, timedelta
import logging
import sys
import json

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import tagClient
from DCMGClasses.resources.misc import listparse
from DCMGClasses.resources.math import interpolation
from DCMGClasses.resources import resource, customer, control, financial

from . import settings
from zmq.backend.cython.constants import RATE
utils.setup_logging()
_log = logging.getLogger(__name__)

class HeaterAgent(Agent):
    def __init__(self,config_path,**kwargs):
        super(HeaterAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config["agentid"]
        #read from config Structure
        self.name = self.config["name"]
        self.owner = self.config["owner"]
        self.objectMass = self.config["objectMass"]
        self.objectSHC = self.config["objectSHC"]
        self.ambientTemp = self.config["ambientTemp"]
        self.thermalResistance = self.config["thermalResistance"]
        self.simulationStep = self.config["simulationStep"]
        self.heaterPowerMax = self.config["heaterPowerMax"]
        self.controlDeadband = self.config["controlDeadband"]
        
        self.objectTemp = self.config["objectTemp"]
        
        self.tempSetpoint = ambientTemp
        self.heaterPower = 0
        self.elementR = 144/self.heaterPowerMax
        
        self.elementON = False
        
        self.currentTag = ""
        self.voltageTag = ""
        self.relayTag = ""
        
        self.topicName = self.owner + "homenetwork"
        
        
    @Core.receiver("onstart")
    def setup(self,sender,**kwargs):
        self._agent_id = self.config["agentid"]
        
        
        self.vip.pubsub.subscribe("pubsub",self.topicName,callback = self.homefeed)
        
        self.printInfo(0)
        
    @Core.periodic(self.simulationStep)
    def simstep(self):
        if self.elementON:
            if self.objectTemp > self.tempSetpoint + .5*self.controlDeadband:
                self.elementON = False
        else:
            if self.objectTemp < self.tempSetpoint - .5*self.controlDeadband:
                self.elementON = True
        
        retval = tagClient.readTags([self.voltageTag, self.currentTag, self.relayTag])
        elementI = retval[self.voltageTag]/self.elementR
        
        if elementI <= retval[self.currentTag]:
            self.heaterPower = self.elementR*self.elementI**2
        else:
            self.heaterPower = self.elementR*retval[self.currentTag]**2
                
        self.objectTemp = (self.heaterPower - (self.objectTemp - self.ambientTemp)/self.thermalResistance)/(self.objectMass*self.objectSHC)
            
    def homefeed(self,peer,sender,bus,topic,headers,message):
        mesdict = json.loads(message)
        messageTarget = mesdict.get("message_target",None)
        messageSender = mesdict.get("message_sender",None)
        if listparse.isRecipient(messageTarget,self.name, False) and messageSender == self.owner:
            messageSubject = mesdict.get("message_subject")
            
            if messageSubject == "setpoint_change":
                self.tempSetpoint = mesdict["new_setpoint"]
            elif messageSubject == "force_disconnect":
                self.elementON = False
            elif messageSubject == "force_connect":
                self.elementON = True
        
    def printInfo(self,depth):
        tab = "    "
        print(tab*depth + "^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
        print(tab*depth + "DEVICE SUMMARY FOR HEATER: {heat}".format(heat = self.name))
        print(tab*depth + "OWNER: {own}".format(own = self.owner))
        print(tab*depth + "SETPOINT: {stp}    CURRENT: {temp}".format(stp = self.tempSetpoint, temp = objectTemp ))
        print(tab*depth)
        
def main(argv = sys.argv):
    try:
        utils.vip_main(HeaterAgent)
    except Exception as e:
        _log.exception("unhandled exception")
        
if __name__ == '__main__':
    sys.exit(main())
        
        