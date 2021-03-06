from __future__ import absolute_import
from datetime import datetime
import logging
import sys
import json
import random

from volttron.platform.vip.agent import Agent, Core, PubSub, compat, RPC
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import tagClient
from DCMGClasses.resources.misc import listparse

from . import settings
utils.setup_logging()
_log = logging.getLogger(__name__)

class WeatherAgent(Agent):
    
    def __init__(self,config_path, **kwargs):
        super(WeatherAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config["agentid"]
        
        self.name = self.config["name"]
        self.cachedIrradiance = 0
        
        self.temperature = 25
        
        self.solarTag = "SolarSetpoint1Alias"
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config["message"])
        self._agent_id = self.config["agentid"]
        
        self.vip.pubsub.subscribe("pubsub","weatherservice",callback = self.reportRequest)
    
    @Core.periodic(settings.COLLECTION_INTERVAL)
    def pollEnvironmentVariables(self):
        #call CIP wrapper to get environment variables from SG PLC
        pass

    @RPC.export('getTemperatureRPC')
    def getTemperature(self):
        return self.temperature
        
    def getIrradiance(self):
        irradiance = .1 * tagClient.readTags([self.solarTag],"SG")
        irradiance += random.normalvariate(0,.04)
        return irradiance
    
    def getWind(self):
        return 0
    
    def getTemp(self):
        return self.temperature
        
    def reportRequest(self,peer,sender,bus,topic,headers,message):
        mesdict = json.loads(message)
        messageSubject = mesdict.get("message_subject",None)
        messageTarget = mesdict.get("message_target",None)
        messageSender = mesdict.get("message_sender",None)
        messageType = mesdict.get("message_type",None)
        if listparse.isRecipient(messageTarget,self.name):
            print("WEATHER SERVICE {me} has received a request for weather info: {type} {sub}".format(me = self.name, type = messageType, sub = messageSubject))
            resd = {}
            responses = {}
            resd["message_subject"] = messageSubject
            resd["message_target"] = messageSender
            resd["message_sender"] = self.name
            if messageSubject == "nowcast":
                resd["message_type"] = "nowcast_response"
                for comp in mesdict["requested_data"]:
                    if comp == "solar_irradiance":
                        responses["solar_irradiance"] = self.getIrradiance()
                    elif comp == "wind_speed":
                        #restypes.append((comp,0))
                        responses["wind_speed"] = self.getWind()
                    elif comp == "temperature":
                        #temporary, should eventually ask sg plc
                        #restypes.append((comp,25))
                        responses["temperature"] = self.getTemp()
                    else:
                        print("Weatheragent {me} received nowcast request for unrecognized datum".format(me = self.name))
                        
                resd["responses"] = responses
            elif messageSubject == "forecast":
                resd["message_type"] = "forecast_response"
                for comp in mesdict["requested_data"]:
                    if comp == "solar_irradiance":
                        responses["solar_irradiance"] = self.getIrradiance()
                    elif comp == "wind_speed":
                        responses["wind_speed"] = 0
                    elif comp == "temperature":
                        #temporary, should eventually ask sg plc
                        responses["wind_speed"] = 25
                    else:
                        print("Weatheragent {me} received forecast request for unrecognized datum".format(me = self.name))
                        
                resd["responses"] = responses
                resd["forecast_period"] = mesdict.get("forecast_period")
            else:
                print("Weatheragent {me} encountered unsupported request")
        
            response = json.dumps(resd)    
            if settings.DEBUGGING_LEVEL > 1:
                print("WEATHER AGENT {name} sending a report: {message}".format(name = self.name, message = response))
            self.vip.pubsub.publish(peer="pubsub", topic = "weatherservice", headers = {}, message = response)
                    
    
def main(argv = sys.argv):
    '''main method called by the eggsecutable'''
    try:
        utils.vip_main(WeatherAgent)
    except Exception as e:
        _log.exception("unhandled exception")
        
if __name__ == "__main__":
    sys.exit(main())
    