from __future__ import absolute_import
from datetime import datetime
import logging
import sys
import json

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import wrapper
from DCMGClasses.resources.misc import listparse
from DCMGClasses.resources import resource


from . import settings
utils.setup_logging()
_log = logging.getLogger(__name__)

class UtilityAgent(Agent):
    def __init__(self,config_path,**kwargs):
        super(UtilityAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config['agent_id']
        
        
        self.name = self.config["name"]
        
        
        self.customers = []
        
    @Core.receiver('onstart')
    def setup(selfself,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        self.vip.pubsub.subscribe('pubsub','energymarket', callback = self.marketfeed)
        self.vip.pubsub.subscribe('pubsub','demandresponse',callback = self.DRfeed)
        
    def solicitDREnrollment(self):
        pass
    
    @Core.periodic(settings.LT_PLAN_INTERVAL)
    def planLongTerm(self):
        pass
    
    @Core.periodic(settings.ST_PLAN_INTERVAL)
    def planShortTerm(self):
        pass
    
    def discoverCustomers(self):
        pass
    
    def marketfeed(self, peer, sender, bus, topic, headers, message):
        pass
    
    def DRfeed(self, peer, sender, bus, topic, headers, message):
        pass
        