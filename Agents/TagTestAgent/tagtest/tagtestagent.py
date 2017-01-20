from __future__ import absolute_import
import logging
import sys

from volttron.platform.vip.agent import Agent, Core, PubSub, compat
from volttron.platform.agent import utils
from volttron.platform.messaging import headers as headers_mod

from DCMGClasses.CIP import tagClient

from . import settings
utils.setup_logging()
_log = logging.getLogger(__name__)

class TagTestAgent(Agent):
    def __init__(self,config_path,**kwargs):
        super(TagTestAgent,self).__init__(**kwargs)
        self.config = utils.load_config(config_path)
        self._agent_id = self.config['agentid']
        #read from config Structure
        
    @Core.receiver('onstart')
    def setup(self,sender,**kwargs):
        _log.info(self.config['message'])
        self._agent_id = self.config['agentid']
        
        #tagClient.startTagServer()
        print(tagClient.readTags(["BRANCH_1_BUS_1_DISTAL_DUMMY"]))
        print(tagClient.readTags(["BRANCH_1_BUS_1_LOAD_2_CurrentRaw"]))
        print(tagClient.readTags(["SOURCE_3_RegVoltageRaw","BRANCH_1_BUS_2_LOAD_2_CurrentRaw"]))
        tagClient.writeTags(["SOURCE_3_VoltageSetpoint_DUMMY"],[11.7])
        
        print(tagClient.readTags(["BRANCH_1_BUS_1_LOAD_3_NC", "SolarSetpoint1Alias"],"SG"))
        tagClient.writeTags(["SolarSetpoint1Alias", "BRANCH_2_BUS_1_LOAD_2_NC"], [1.0, True], "SG")
        
        
def main(argv = sys.argv):
    try:
        utils.vip_main(TagTestAgent)
    except Exception as e:
        _log.exception("unhandled exception")
        
if __name__ == '__main__':
    sys.exit(main())