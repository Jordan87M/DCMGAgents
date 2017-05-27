from datetime import datetime,timedelta
import sys

from volttron.platform.vip.agent import core, Core
from volttron.platform.agent import utils

def msfromnow(agent,ms,func,args):
	now = datetime.now()
	sched = now + timedelta(milliseconds = ms)
	agent.core.schedule(sched, func, args)