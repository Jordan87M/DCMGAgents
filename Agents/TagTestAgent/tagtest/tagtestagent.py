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
        
        tagClient.startTagServer()
        print(tagClient.readTags(["BRANCH1_BUS1_LOAD2_DUMMY"]))
        print(tagClient.readTags(["BRANCH1_BUS1_LOAD2_Voltage"]))
        print(tagClient.readTags(["BRANCH1_BUS2_LOAD2_Voltage","BRANCH1_BUS2_LOAD2_Current"]))

        
def main(argv = sys.argv):
    try:
        utils.vip_main(TagTestAgent)
    except Exception as e:
        _log.exception("unhandled exception")
        
if __name__ == '__main__':
    sys.exit(main())